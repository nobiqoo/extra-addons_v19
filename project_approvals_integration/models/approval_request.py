# -*- coding: utf-8 -*-
from odoo import models, fields, api

class ApprovalRequest(models.Model):
    _inherit = "approval.request"

    project_id = fields.Many2one(
        "project.project",
        string="Proyecto",
        index=True,
        help="Proyecto relacionado con este requerimiento de aprobación."
    )

    po_number = fields.Char(
        string="N.º OC asociada",
        compute="_compute_po_number",
        store=False,
    )
    request_date_display = fields.Datetime(
        string='Fecha de solicitud',
        compute='_compute_request_date_display',
        store=False,
    )

    def _compute_request_date_display(self):
        for rec in self:
            rec.request_date_display = rec.date_start or rec.date_confirmed or rec.create_date

    def _compute_po_number(self):
        Purchase = self.env['purchase.order']
        po_fields = Purchase._fields

        for rec in self:
            names = []

            if 'purchase_order_id' in rec._fields and rec.purchase_order_id:
                names.append(rec.purchase_order_id.name)
            if 'purchase_order_ids' in rec._fields and rec.purchase_order_ids:
                names.extend(rec.purchase_order_ids.mapped('name'))
            if not names:
                dom = ['|','|','|', ('id','=',0), ('id','=',0), ('id','=',0), ('id','=',0)]

                if 'approval_request_id' in po_fields:
                    dom[0:2] = [('approval_request_id', '=', rec.id)]

                if 'approval_request_ids' in po_fields:
                    dom[2:4] = [('approval_request_ids', 'in', rec.id)]

                if 'x_approval_request_id' in po_fields:
                    dom[4:6] = [('x_approval_request_id', '=', rec.id)]

                if 'x_approval_request_ids' in po_fields:
                    dom[6:8] = [('x_approval_request_ids', 'in', rec.id)]

                pos = Purchase.search(dom, limit=1, order='id desc')
                if pos:
                    names.append(pos.name)

            if not names and 'origin' in po_fields and rec.name:
                po_guess = Purchase.search([('origin', 'ilike', rec.name)], limit=1, order='id desc')
                if po_guess:
                    names.append(po_guess.name)

            rec.po_number = names[0] if names else False

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        proj_id = (
            self.env.context.get('default_project_id')
            or self.env.context.get('task_project_id')
            or (self.env.context.get('active_id')
                if self.env.context.get('active_model') in ('project.task', 'project.project') else False)
        )
        if 'project_id' in fields_list and proj_id and not vals.get('project_id'):
            vals['project_id'] = proj_id
        return vals
