# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from ast import literal_eval
from odoo import api, models, fields, _, SUPERUSER_ID
from odoo.exceptions import UserError
from datetime import datetime


class QualityCheck(models.Model):
    _inherit = "quality.check"

    approver_ids = fields.One2many(
        'quality.check.approver', 'check_id', string='Approvers')
    approval_minimum = fields.Integer(
        related='point_id.approval_minimum', store=True)
    approver_sequence = fields.Boolean(
        related='point_id.approver_sequence', store=True)
    approval_count = fields.Integer(
        compute='_compute_approval_count', string='Approval Count')
    approver_user_ids = fields.Many2many('res.users', string='Approved By')
    quality_state = fields.Selection(
        selection_add=[('cancelled', 'Cancelado')]
    )

    def action_approve(self):
        approver = self.approver_ids.filtered(
            lambda a: a.user_id == self.env.user and a.status == 'pending')
        if approver:
            approver.action_approve()
        else:
            raise UserError(
                _('No tienes aprobaciones pendientes o no eres un aprobador asignado.'))

    def action_cancel(self):
        for record in self:
            record.with_context(cancel_in_progress=True).write(
                {'quality_state': 'cancelled'})

    def action_refuse(self):
        approver = self.approver_ids.filtered(
            lambda a: a.user_id == self.env.user and a.status == 'pending')
        if approver:
            approver.action_refuse()
        else:
            raise UserError(
                _('No tienes aprobaciones pendientes o no eres un aprobador asignado.'))

    @api.depends('approver_ids.status')
    def _compute_approval_count(self):
        for record in self:
            record.approval_count = len(
                record.approver_ids.filtered(lambda a: a.status == 'approved'))

    @api.depends('approver_ids.approval_role')
    def _compute_approval_role(self):
        for record in self:
            record.approval_role = record.point_id.approver_ids.approval_role

    @api.model_create_multi
    def create(self, vals_list):
        checks = super(QualityCheck, self).create(vals_list)
        for check in checks:
            if check.point_id:
                approver_vals = []
                for approver in check.point_id.approver_ids:
                    approver_vals.append((0, 0, {
                        'sequence': approver.sequence,
                        'user_id': approver.user_id.id,
                        'approval_role': approver.approval_role,
                        'signature': approver.signature,
                        'required': approver.required,
                        'status': 'pending',
                    }))
                check.approver_ids = approver_vals
                check._create_approver_activites()
        return checks

    def _create_approver_activites(self):
        """ Create activities to notify approvers of their pending approvals"""
        self.ensure_one()
        activity_type = self.env.ref(
            'mail.mail_activity_data_todo', raise_if_not_found=False)
        if not activity_type:
            activity_type = self.env['mail.activity.type'].search(
                [('category', '=', 'default')], limit=1)

        for approver in self.approver_ids.filtered(lambda a: a.status == 'pending'):
            if self.approver_sequence:
                if approver.sequence == min(self.approver_ids.filtered(lambda a: a.status == 'pending').mapped('sequence')):
                    self._create_activity_for_approver(approver, activity_type)
            else:
                self._create_activity_for_approver(approver, activity_type)

    def _create_activity_for_approver(self, approver, activity_type):
        role_name = dict(approver._fields['approval_role'].selection).get(
            approver.approval_role, '')

        summary = _('Aprobación Pendiente: Control de Calidad')
        note = _(
            '<p>Tiene una aprobación pendiente para el control de calidad <strong>%s</strong></p>'
            '<p>Rol: <strong>%s</strong></p>'
            '<p>Producto: <strong>%s</strong></p>'
            '<p>Requerido: <strong>%s</strong></p>'
        ) % (
            self.name or self.display_name,
            role_name,
            self.product_id.display_name if self.product_id else _('N/A'),
            _('Sí') if approver.required else _('No')
        )

        self.activity_schedule(
            activity_type_id=activity_type.id,
            summary=summary,
            note=note,
            user_id=approver.user_id.id,
        )

    @api.model
    def get_signature_only(self):
        for check in self:
            if check.point_id:
                return check.point_id.approver_ids.mapped('signature')
        return False

    def _check_approval_status(self):
        for record in self:
            approved_approvers = record.approver_ids.filtered(
                lambda a: a.status == 'approved')
            if len(approved_approvers) >= record.approval_minimum:
                record.write({'quality_state': 'pass'})
            else:
                record.write({'quality_state': 'none'})

    def action_quality_worksheet(self):
        action = super().action_quality_worksheet()
        context = action.get('context', {})
        if isinstance(context, str):
            context = literal_eval(context)
        worksheet_model = self.worksheet_template_id.model_id.sudo().model
        worksheet = self.env[worksheet_model].search([
            ('x_quality_check_id', '=', self.id)
        ])
        inspection_release_format = self.worksheet_template_id.inspection_release_format
        refurbishment_format = self.worksheet_template_id.refurbishment_format
        biomedical_equipment_inspection_format = self.worksheet_template_id.biomedical_equipment_inspection_format
        approver_list = self.approver_ids.filtered(
            lambda a: a.status == 'approved')
        employees = []
        approvers = []
        for approver in approver_list:
            approver_name = approver.user_id.name or ''
            approver_role = approver.approval_role or ''
            approver_signature = approver.signature or False
            approvers.append(
                {'name': approver_name, 'role': approver_role, 'signature': approver_signature})
            employee = self.env['hr.employee'].sudo().search(
                [('private_email', '=', approver.user_id.login)], limit=1)
            if employee and employee.partner_id:
                vat = employee.partner_id.vat or ''
                job = employee.job_id.id or False
                role = approver_role or ''
            else:
                vat = ''
                job = False
                role = ''
            employees.append({'vat': vat, 'job': job, 'role': role})
        technical_manager_name = next(
            (a['name'] for a in approvers if a['role'] == 'technical_manager'), '')
        technical_manager_signature = next(
            (a['signature'] for a in approvers if a['role'] == 'technical_manager'), '')
        warehouse_manager_name = next(
            (a['name'] for a in approvers if a['role'] == 'warehouse_manager'), '')
        warehouse_manager_signature = next(
            (a['signature'] for a in approvers if a['role'] == 'warehouse_manager'), '')
        importations_manager_name = next(
            (a['name'] for a in approvers if a['role'] == 'importations_manager'), '')
        importations_manager_signature = next(
            (a['signature'] for a in approvers if a['role'] == 'importations_manager'), '')
        warehouse_auxiliary_name = next(
            (a['name'] for a in approvers if a['role'] == 'warehouse_auxiliary'), '')
        warehouse_auxiliary_signature = next(
            (a['signature'] for a in approvers if a['role'] == 'warehouse_auxiliary'), '')
        importations_analyst_name = next(
            (a['name'] for a in approvers if a['role'] == 'importations_analyst'), '')
        importations_analyst_signature = next(
            (a['signature'] for a in approvers if a['role'] == 'importations_analyst'), '')
        refurbishment_responsible_name = next(
            (a['name'] for a in approvers if a['role'] == 'refurbishment_responsible'), '')
        refurbishment_responsible_signature = next(
            (a['signature'] for a in approvers if a['role'] == 'refurbishment_responsible'), '')
        reviewed_name = next(
            (a['name'] for a in approvers if a['role'] == 'checklist_responsible'), '')
        reviewed_signature = next(
            (a['signature'] for a in approvers if a['role'] == 'checklist_responsible'), '')
        vat_manager = next(
            (e['vat'] for e in employees if e['role'] == 'technical_manager'), '')
        job_manager = next(
            (e['job'] for e in employees if e['role'] == 'technical_manager'), False)
        vat_reviewed = next(
            (e['vat'] for e in employees if e['role'] == 'checklist_responsible'), '')
        job_reviewed = next(
            (e['job'] for e in employees if e['role'] == 'checklist_responsible'), False)
        if inspection_release_format or refurbishment_format:
            purchase_order = self.env['purchase.order'].search(
                [('name', '=', self.picking_id.origin)], limit=1)
            purchase_import_id = self.env['purchase.import'].search(
                [('purchases_ids', 'in', purchase_order.ids)])
            refurbishment_order_name = ''
            if purchase_import_id:
                import_name = purchase_import_id.name
                import_number = ''.join(filter(str.isdigit, import_name))
                refurbishment_order_name = f"ORD{import_number}"
            stocks = self.env['stock.move'].search(
                [('purchase_line_id.order_id', '=', purchase_order.id)])
            reported_quantity = sum(stocks.mapped('product_uom_qty'))

            stock_move_lines = self.picking_id.move_line_ids
            line_vals_list = []
            for line in stock_move_lines:
                line_vals = {
                    'x_product_id': line.product_id.id,
                    'x_invima': line.product_id.invima,
                    'x_quantity': line.quantity,
                    'x_lot_id': line.lot_id.id,
                    'x_default_code': line.product_id.default_code,
                    'x_product_uom_qty': line.quantity,
                    'x_product_uom': line.product_uom_id.id,
                    'x_expiration_date': line.lot_id.expiration_date or line.expiration_date,
                    'x_witness': line.product_id.witness,
                }
                line_vals_list.append((0, 0, line_vals))

            if worksheet:
                update_vals = {
                    'x_purchase_import_id': purchase_import_id.id if purchase_import_id else False,
                    'x_company_id': self.env.company.id,
                    'x_partner_id': purchase_order.partner_id.id if purchase_order else False,
                    'x_purchase_order_id': purchase_order.id if purchase_order else False,
                    'x_refurbishment_order': refurbishment_order_name,
                    'x_reported_quantity': reported_quantity if reported_quantity else 0.0,
                    'x_technical_manager': technical_manager_name,
                    'x_warehouse_manager': warehouse_manager_name,
                    'x_importations_manager': importations_manager_name,
                    'x_warehouse_auxiliary': warehouse_auxiliary_name,
                    'x_importations_analyst': importations_analyst_name,
                    'x_refurbishment_responsible': refurbishment_responsible_name,
                    'x_technical_manager_signature': technical_manager_signature,
                    'x_warehouse_manager_signature': warehouse_manager_signature,
                    'x_importations_manager_signature': importations_manager_signature,
                    'x_warehouse_auxiliary_signature': warehouse_auxiliary_signature,
                    'x_importations_analyst_signature': importations_analyst_signature,
                    'x_refurbishment_responsible_signature': refurbishment_responsible_signature,
                }

                if not worksheet.x_line_ids:
                    update_vals['x_line_ids'] = line_vals_list

                worksheet.write(update_vals)

            context.update({
                'default_x_inspection_release_format': inspection_release_format,
                'default_x_refurbishment_format': refurbishment_format,
                'default_x_purchase_import_id': purchase_import_id.id if purchase_import_id else False,
                'default_x_company_id': self.env.company.id,
                'default_x_partner_id': purchase_order.partner_id.id if purchase_order else False,
                'default_x_purchase_order_id': purchase_order.id if purchase_order else False,
                'default_x_refurbishment_order': refurbishment_order_name,
                'default_x_reported_quantity': reported_quantity if reported_quantity else 0.0,
                'default_x_line_ids': line_vals_list,
                'default_x_technical_manager': technical_manager_name,
                'default_x_warehouse_manager': warehouse_manager_name,
                'default_x_importations_manager': importations_manager_name,
                'default_x_warehouse_auxiliary': warehouse_auxiliary_name,
                'default_x_importations_analyst': importations_analyst_name,
                'default_x_refurbishment_responsible': refurbishment_responsible_name,
                'default_x_technical_manager_signature': technical_manager_signature,
                'default_x_warehouse_manager_signature': warehouse_manager_signature,
                'default_x_importations_manager_signature': importations_manager_signature,
                'default_x_warehouse_auxiliary_signature': warehouse_auxiliary_signature,
                'default_x_importations_analyst_signature': importations_analyst_signature,
                'default_x_refurbishment_responsible_signature': refurbishment_responsible_signature,
                'from_picking': True if self.env.context.get('from_picking') else False,
            })
            action['context'] = context
        elif biomedical_equipment_inspection_format:
            if worksheet:
                worksheet.write({
                    'x_product_name': self.product_id.name,
                    'x_product_code': self.product_id.default_code,
                    'x_lot_ids': self.picking_id.move_ids.lot_ids.filtered(lambda l: l.product_id == self.product_id).ids,
                    'x_brand_id': self.product_id.product_brand_id.id,
                    'x_technical_manager': technical_manager_name,
                    'x_vat_manager': vat_manager,
                    'x_job_manager_id': job_manager,
                    'x_name_reviewed': reviewed_name,
                    'x_name_reviewed_signature': reviewed_signature,
                    'x_vat_reviewed': vat_reviewed,
                    'x_job_id': job_reviewed,
                })
            context.update({
                'default_x_product_name': self.product_id.name,
                'default_x_product_code': self.product_id.default_code,
                'default_x_company_id': self.env.company.id,
                'default_x_lot_ids': self.picking_id.move_ids.lot_ids.filtered(lambda l: l.product_id == self.product_id).ids,
                'default_x_brand_id': self.product_id.product_brand_id.id,
                'default_x_technical_manager': technical_manager_name,
                'default_x_vat_manager': vat_manager,
                'default_x_job_manager_id': job_manager,
                'default_x_name_reviewed': reviewed_name,
                'default_x_name_reviewed_signature': reviewed_signature,
                'default_x_vat_reviewed': vat_reviewed,
                'default_x_job_id': job_reviewed,
                'from_picking': True if self.env.context.get('from_picking') else False,
            })
            action['context'] = context

        self.env.cr.commit()
        self.env['ir.ui.view'].clear_caches()
        self.env[worksheet_model].clear_caches()

        action.update({
            'res_id': worksheet.id,
            'views': [(False, 'form')],
            'target': 'current',
            'context': context,
        })

        return action

    def do_pass(self):
        if self.env.context.get('cancel_in_progress'):
            self.write({
                'user_id': self.env.user.id,
                'control_date': datetime.now()
            })
            return
        for check in self:
            required_approvers = check.point_id.approver_ids.filtered(
                lambda a: a.required)

            pending_approvers = required_approvers.filtered(
                lambda a: a.user_id not in check.approver_user_ids)

            if pending_approvers and not check.env.context.get('from_picking') and check.quality_state != 'cancelled':
                approver_names = ', '.join(
                    pending_approvers.mapped('user_id.name'))
                raise UserError(_(
                    'No puede pasar este control de calidad porque aún no han pasado los siguientes aprobadores requeridos: %s' % approver_names
                ))

            if check.point_id.approval_minimum > 0 and not check.env.context.get('from_picking') and check.quality_state != 'cancelled':
                total_approvals = len(check.approver_user_ids)
                if total_approvals < check.point_id.approval_minimum:
                    raise UserError(_(
                        'No puede pasar este control de calidad porque no se ha alcanzado el número mínimo de aprobaciones requeridas. (%s).' % check.point_id.approval_minimum
                    ))
        super().do_pass()
        if self.env.context.get('from_picking'):
            self.write({'quality_state': 'none',
                        'user_id': self.env.user.id,
                        'control_date': datetime.now()})

    def write(self, vals):
        res = super().write(vals)
        if 'quality_state' in vals and not vals.get('user_id') or not vals.get('control_date'):
            if vals.get('quality_state') == 'cancelled':
                self.with_context(cancel_in_progress=True).do_pass()
        return res
