# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare, format_list


class PurchaseServiceAcceptance(models.Model):
    _name = 'purchase.service.acceptance'
    _description = 'Purchase Service Acceptance'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(default='New', copy=False, readonly=True)
    purchase_order_id = fields.Many2one(
        comodel_name='purchase.order',
        string='Purchase Order',
        required=True,
        ondelete='cascade',
        readonly=True,
        tracking=True,
    )
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Vendor',
        related='purchase_order_id.partner_id',
        store=True,
    )
    date_order = fields.Datetime(
        string='Order Date',
        related='purchase_order_id.date_order',
        store=True,
    )
    date_planned = fields.Datetime(
        string='Expected Date',
        related='purchase_order_id.date_planned',
        store=True,
    )
    date = fields.Datetime(string='Acceptance Date', readonly=True, copy=False)
    user_id = fields.Many2one(
        comodel_name='res.users',
        string='Responsible',
        default=lambda self: self.env.user,
        tracking=True,
    )
    state = fields.Selection(
        selection=[
            ('draft', 'Pending Acceptance'),
            ('done', 'Accepted'),
            ('cancelled', 'Cancelled'),
        ],
        string='Status',
        default='draft',
        copy=False,
        tracking=True,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        related='purchase_order_id.company_id',
        store=True,
    )
    line_ids = fields.One2many(
        comodel_name='purchase.service.acceptance.line',
        inverse_name='acceptance_id',
        string='Lines',
        copy=True,
    )
    backorder_id = fields.Many2one(
        comodel_name='purchase.service.acceptance',
        string='Created From',
        readonly=True,
        copy=False,
    )
    backorder_ids = fields.One2many(
        comodel_name='purchase.service.acceptance',
        inverse_name='backorder_id',
        string='Backorders',
    )
    allowed_validator_ids = fields.Many2many(
        comodel_name='res.users',
        string='Can Validate',
        compute='_compute_allowed_validator_ids',
        help='Besides Purchase Administrators (who can always validate), only these '
             'users — the Buyer and the Requester of the purchase order — may '
             'validate this Service Acceptance. No extra setup needed: it is always '
             'derived from the purchase order itself.',
    )
    invoice_ids = fields.Many2many(
        comodel_name='account.move',
        string='Vendor Bills',
        compute='_compute_invoice_ids',
    )

    @api.depends('line_ids.purchase_line_id')
    def _compute_invoice_ids(self):
        """Any vendor bill/credit note whose line references the same PO
        line(s) this acceptance covers -- matched directly on
        purchase_line_id. This module doesn't book a provision entry, so
        there's no reconciliation to key off in the first place: a bill
        simply relates to this acceptance if it bills the same PO line,
        regardless of order (bill, then credit note, then another bill all
        stay related)."""
        for acceptance in self:
            po_lines = acceptance.line_ids.purchase_line_id
            if not po_lines:
                acceptance.invoice_ids = False
                continue
            moves = self.env['account.move.line'].search([
                ('purchase_line_id', 'in', po_lines.ids),
            ]).move_id
            acceptance.invoice_ids = moves.filtered(lambda m: m.is_purchase_document())

    def action_view_invoices(self):
        self.ensure_one()
        action = {
            'type': 'ir.actions.act_window',
            'name': _('Vendor Bills'),
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.invoice_ids.ids)],
        }
        if len(self.invoice_ids) == 1:
            action['view_mode'] = 'form'
            action['res_id'] = self.invoice_ids.id
        return action

    @api.depends('purchase_order_id.user_id', 'purchase_order_id.create_uid')
    def _compute_allowed_validator_ids(self):
        for acceptance in self:
            acceptance.allowed_validator_ids = acceptance._get_allowed_validators()

    def _get_allowed_validators(self):
        self.ensure_one()
        order = self.purchase_order_id
        return (order.user_id | order.create_uid)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('purchase.service.acceptance') or 'New'
        return super().create(vals_list)

    def action_validate(self):
        prec = self.env['decimal.precision'].precision_get('Product Unit of Measure')
        for acceptance in self:
            if acceptance.state != 'draft':
                raise UserError(_('Only draft acceptances can be validated.'))
            if not acceptance.line_ids:
                raise UserError(_('There is nothing to accept.'))

            allowed_validators = acceptance._get_allowed_validators()
            if allowed_validators and self.env.user not in allowed_validators \
                    and not self.env.user.has_group('purchase.group_purchase_manager'):
                raise UserError(_(
                    'Only %s may validate this Service Acceptance.',
                    format_list(self.env, allowed_validators.mapped('display_name')),
                ))

            # The web client only sends a field in the write() payload if the
            # user actually touched it — a line left at its default
            # qty_accepted=0 never triggers the `_check_qty_accepted`
            # constrain on its own, so it must be checked again here too.
            for line in acceptance.line_ids:
                if float_compare(line.qty_accepted, 0.0, precision_digits=prec) <= 0:
                    raise ValidationError(_(
                        'The accepted quantity must be greater than zero. '
                        'Remove the line if you are not ready to accept it yet.'
                    ))

            po_lines_to_check = self.env['purchase.order.line']
            for line in acceptance.line_ids:
                if line.qty_accepted:
                    line.purchase_line_id.qty_received += line.qty_accepted
                po_lines_to_check |= line.purchase_line_id

            acceptance.write({'date': fields.Datetime.now(), 'state': 'done'})

            remaining_po_lines = po_lines_to_check.filtered(
                lambda po_line: float_compare(
                    po_line._get_service_acceptance_qty_pending(), 0.0, precision_digits=prec
                ) > 0
            )
            if remaining_po_lines:
                acceptance._create_backorder(remaining_po_lines)

    def action_view_backorders(self):
        self.ensure_one()
        action = {
            'type': 'ir.actions.act_window',
            'name': _('Backorders'),
            'res_model': 'purchase.service.acceptance',
            'view_mode': 'list,form',
            'domain': [('backorder_id', '=', self.id)],
        }
        if len(self.backorder_ids) == 1:
            action['view_mode'] = 'form'
            action['res_id'] = self.backorder_ids.id
        return action

    def action_cancel(self):
        non_draft = self.filtered(lambda a: a.state != 'draft')
        if non_draft:
            raise UserError(_(
                'Only draft Service Acceptances can be cancelled this way. Use '
                '"Reset to Pending Acceptance" for an already-accepted one.'
            ))
        # Kept (not deleted) for the same audit-trail reason a PO cancellation
        # cascades to 'cancelled' instead of unlinking (see
        # PurchaseOrder.button_cancel()) — the purchase order line stops being
        # considered "covered" (see _create_service_acceptance()'s filter), so
        # it becomes eligible for a fresh acceptance again if needed.
        self.write({'state': 'cancelled'})

    def action_reset_to_draft(self):
        for acceptance in self:
            if acceptance.state != 'done':
                raise UserError(_('Only accepted Service Acceptances can be reset to draft.'))
            for line in acceptance.line_ids:
                if line.qty_accepted:
                    line.purchase_line_id.qty_received -= line.qty_accepted
            acceptance.state = 'draft'

    def _create_backorder(self, purchase_lines):
        self.ensure_one()
        return self.with_context(skip_qty_accepted_check=True).create({
            'purchase_order_id': self.purchase_order_id.id,
            'backorder_id': self.id,
            'line_ids': [(0, 0, {'purchase_line_id': po_line.id}) for po_line in purchase_lines],
        })

    @api.model
    def get_dashboard_stats(self):
        # Mutually exclusive by design, so the sub-counts add up exactly to
        # 'total': every `state` value falls into exactly one bucket below.
        total_domain = []
        confirmed_domain = [('state', '=', 'done')]
        waiting_domain = [('state', '=', 'draft')]
        cancelled_domain = [('state', '=', 'cancelled')]
        return {
            'total': {'count': self.search_count(total_domain), 'domain': total_domain},
            'confirmed': {'count': self.search_count(confirmed_domain), 'domain': confirmed_domain},
            'waiting': {'count': self.search_count(waiting_domain), 'domain': waiting_domain},
            'cancelled': {'count': self.search_count(cancelled_domain), 'domain': cancelled_domain},
        }
