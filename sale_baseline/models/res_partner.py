# -*- coding: utf-8 -*-

from odoo import fields, models, api, _
from odoo.exceptions import AccessError
from datetime import datetime

# Documentos de control de crédito
CREDIT_DOCUMENTS = (
    'promissory_note',
    'risk_bureau',
    'credit_application',
    'data_authorization',
    'insured',
)
CREDIT_DOCUMENT_GROUPS = (
    'sale_baseline.group_block_credit_limit',
    'sale_baseline.group_block_expired_invoice',
)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_blocked_not_buy = fields.Boolean('Blocked for time without buying',
                                        company_dependent=True,
                                        default=False)
    block_expired_invoice = fields.Boolean(
        'Block Expired Invoice',
        default=True)
    block_credit_limit = fields.Boolean(
        'Block Credit Limit',
        default=True)
    share_credit_limit = fields.Boolean(
        'Compartir Límite de Crédito con Contactos Hijos',
        default=False,
        help='If enabled, the credit limit of this contact will be shared '
             'with all child contacts. The total credit of this contact and '
             'all its children will be validated against this credit limit.')
    quota_limit_initial = fields.Float(
        'Quota Limit Initial')
    credit_limit_history_ids = fields.One2many(
        'credit.limit.history',
        'partner_id')
    credit_limit_readonly = fields.Boolean(
        compute='_compute_credit_limit_readonly')

    # Documentos de control de crédito
    promissory_note = fields.Boolean(
        'Promissory Note and Letter of Instructions', copy=False)
    promissory_note_file = fields.Binary(
        'Promissory Note Document', attachment=True, copy=False)
    promissory_note_filename = fields.Char(
        'Promissory Note File Name', copy=False)
    promissory_note_update_date = fields.Datetime(
        'Promissory Note Last Update', readonly=True, copy=False)
    promissory_note_update_user_id = fields.Many2one(
        'res.users', 'Promissory Note Updated By', readonly=True, copy=False)
    risk_bureau = fields.Boolean(
        'Credit Bureaus', copy=False)
    risk_bureau_file = fields.Binary(
        'Credit Bureaus Document', attachment=True, copy=False)
    risk_bureau_filename = fields.Char(
        'Credit Bureaus File Name', copy=False)
    risk_bureau_update_date = fields.Datetime(
        'Credit Bureaus Last Update', readonly=True, copy=False)
    risk_bureau_update_user_id = fields.Many2one(
        'res.users', 'Credit Bureaus Updated By', readonly=True, copy=False)
    credit_application = fields.Boolean(
        'Credit Application', copy=False)
    credit_application_file = fields.Binary(
        'Credit Application Document', attachment=True, copy=False)
    credit_application_filename = fields.Char(
        'Credit Application File Name', copy=False)
    credit_application_update_date = fields.Datetime(
        'Credit Application Last Update', readonly=True, copy=False)
    credit_application_update_user_id = fields.Many2one(
        'res.users', 'Credit Application Updated By', readonly=True,
        copy=False)
    data_authorization = fields.Boolean(
        'Data Processing Authorization', copy=False)
    data_authorization_file = fields.Binary(
        'Data Processing Authorization Document', attachment=True,
        copy=False)
    data_authorization_filename = fields.Char(
        'Data Processing Authorization File Name', copy=False)
    data_authorization_update_date = fields.Datetime(
        'Data Processing Authorization Last Update', readonly=True,
        copy=False)
    data_authorization_update_user_id = fields.Many2one(
        'res.users', 'Data Processing Authorization Updated By',
        readonly=True, copy=False)
    insured = fields.Boolean(
        'Insured', copy=False)
    insured_file = fields.Binary(
        'Insured Document', attachment=True, copy=False)
    insured_filename = fields.Char(
        'Insured File Name', copy=False)
    insured_update_date = fields.Datetime(
        'Insured Last Update', readonly=True, copy=False)
    insured_update_user_id = fields.Many2one(
        'res.users', 'Insured Updated By', readonly=True, copy=False)
    credit_documents_readonly = fields.Boolean(
        compute='_compute_credit_documents_readonly')

    def _compute_credit_limit_readonly(self):
        for record in self:
            record.credit_limit_readonly = not self.env.user.has_group(
                'sale_baseline.group_block_credit_limit')

    @api.depends_context('uid')
    def _compute_credit_documents_readonly(self):
        self.credit_documents_readonly = not self._can_edit_credit_documents()

    @api.model
    def _can_edit_credit_documents(self):
        return self.env.su or any(
            self.env.user.has_group(group) for group in CREDIT_DOCUMENT_GROUPS)

    @api.model
    def _get_credit_document_fields(self):
        return {
            f'{document}{suffix}'
            for document in CREDIT_DOCUMENTS
            for suffix in ('', '_file', '_filename', '_update_date',
                           '_update_user_id')
        }

    @api.model
    def _prepare_credit_document_vals(self, vals, only_set=False):
        touched = {
            name for name in self._get_credit_document_fields() & vals.keys()
            if not only_set or vals[name]
        }
        if not touched:
            return vals
        if not self._can_edit_credit_documents():
            raise AccessError(_(
                'You are not allowed to modify the credit documents of '
                'contacts. Ask a user with the credit limit or overdue '
                'invoices control permission.'))
        stamp = {}
        for document in CREDIT_DOCUMENTS:
            if {document, f'{document}_file'} & touched:
                stamp[f'{document}_update_date'] = fields.Datetime.now()
                stamp[f'{document}_update_user_id'] = self.env.uid
        return dict(stamp, **vals)

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = [
            self._prepare_credit_document_vals(vals, only_set=True)
            for vals in vals_list
        ]
        return super().create(vals_list)

    def write(self, vals):
        return super().write(self._prepare_credit_document_vals(vals))

    @api.onchange('credit_limit')
    def create_history_credit_partner(self):
        for record in self:
            vals = {
                'date': datetime.now(),
                'name': '',
                'user_id': self.env.user.id,
                'credit': record.credit_limit,
                'partner_id': record.id.origin
            }

            record.credit_limit_history_ids.create(vals)

    def _get_credit_limit_partner(self):
        """Returns the partner that holds the credit limit for this contact.
        If the parent has share_credit_limit enabled, returns the parent.
        Otherwise, returns self.
        """
        self.ensure_one()
        if self.parent_id and self.parent_id.share_credit_limit:
            return self.parent_id
        return self

    def _get_shared_credit_partners(self):
        """Returns all partners that share the credit limit with this contact.
        If share_credit_limit is enabled, returns self and all child contacts.
        Otherwise, returns only self.
        """
        self.ensure_one()
        if self.share_credit_limit:
            # Include self and all child contacts
            return self | self.child_ids
        return self

    def _get_total_shared_credit(self):
        """Calculates the total credit used by this partner and all contacts
        sharing the credit limit.
        """
        self.ensure_one()
        credit_partner = self._get_credit_limit_partner()
        shared_partners = credit_partner._get_shared_credit_partners()
        total_credit = sum(p.credit for p in shared_partners)
        return total_credit

    def _get_shared_orders_no_invoice_amount(self, currency_rate=1.0):
        """Calculates the total amount from confirmed orders without invoice
        for all partners sharing the credit limit.
        """
        self.ensure_one()
        credit_partner = self._get_credit_limit_partner()
        shared_partners = credit_partner._get_shared_credit_partners()
        
        orders_no_invoice = self.env['sale.order'].search([
            ('partner_id', 'in', shared_partners.ids),
            ('state', 'in', ['sale', 'done']),
        ])
        orders_no_invoice = orders_no_invoice.filtered(
            lambda o: not o.invoice_ids and not all(
                move.state == 'done' for move in o.picking_ids
            )
        )
        orders_no_invoice = orders_no_invoice.filtered(
            lambda o: not o.invoice_ids)
        
        return sum(o.amount_total / o.currency_rate for o in orders_no_invoice)
