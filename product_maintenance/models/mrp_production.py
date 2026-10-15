# -*- coding: utf-8 -*-

from odoo import _, fields, models


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    product_maintenance_repair_ids = fields.One2many(
        comodel_name='repair.order',
        inverse_name='production_id',
        string='Órdenes de mantenimiento'
    )

    def _get_product_maintenance_workorder(self):
        self.ensure_one()
        return self.workorder_ids.filtered('workcenter_id')[:1]

    def _prepare_product_maintenance_repair_vals(self, workorder=False):
        self.ensure_one()
        workorder = workorder or self.env['mrp.workorder']
        if not workorder:
            workorder = self._get_product_maintenance_workorder()
        workcenter = workorder.workcenter_id if workorder else self.env['mrp.workcenter']
        equipment = workcenter.product_maintenance_ids if workcenter else self.env['product.maintenance']
        equipment = equipment.filtered(lambda product: not product.company_id or product.company_id == self.company_id)
        first_equipment = equipment[:1]

        vals = {
            'company_id': self.company_id.id,
            'origin': self.name,
            'production_id': self.id,
            'maintenance_type': 'correctives',
            'schedule_date': self.date_start or fields.Datetime.now(),
            'user_id': self.user_id.id or self.env.user.id,
        }
        if workorder:
            vals['workorder_id'] = workorder.id
        if workcenter:
            vals['workcenter_id'] = workcenter.id
        if len(equipment) == 1:
            vals['maintenance_equipment_ids'] = [(6, 0, equipment.ids)]
            vals['maintenance_product_id'] = first_equipment.id
            if first_equipment.partner_id:
                vals['partner_id'] = first_equipment.partner_id.id
            if first_equipment.lot_id:
                vals['lot_id'] = first_equipment.lot_id.id
        return vals

    def _action_product_maintenance_repair(self, workorder=False):
        self.ensure_one()
        repair = self.env['repair.order'].create(
            self._prepare_product_maintenance_repair_vals(workorder=workorder)
        )
        form_view = self.env.ref('repair.view_repair_order_form', raise_if_not_found=False)
        action = {
            'name': _('Solicitud de mantenimiento'),
            'type': 'ir.actions.act_window',
            'res_model': 'repair.order',
            'view_mode': 'form',
            'res_id': repair.id,
            'context': {
                'default_company_id': self.company_id.id,
                'default_production_id': self.id,
            },
        }
        if form_view:
            action['views'] = [(form_view.id, 'form')]
        return action

    def button_maintenance_req(self):
        self.ensure_one()
        if not self.company_id.use_product_maintenance_from_manufacturing:
            return super().button_maintenance_req()
        return self._action_product_maintenance_repair()


class MrpProductionWorkcenterLine(models.Model):
    _inherit = 'mrp.workorder'

    def button_maintenance_req(self):
        self.ensure_one()
        if not self.company_id.use_product_maintenance_from_manufacturing:
            return super().button_maintenance_req()
        return self.production_id._action_product_maintenance_repair(workorder=self)
