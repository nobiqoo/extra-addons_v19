# -*- coding: utf-8 -*-

from odoo import api, models, fields
from datetime import date
from dateutil.relativedelta import relativedelta
from odoo.exceptions import ValidationError


class QualityCheck(models.Model):
    _inherit = 'quality.check'

    repair_id = fields.Many2one(
        comodel_name='repair.order',
        string='Reparación'
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'point_id' in vals and not vals.get('worksheet_template_id'):
                point = self.env['quality.point'].browse(vals['point_id'])
                if point.test_type in ('maintenance', 'maintenance_preinst'):
                    vals['worksheet_template_id'] = point.worksheet_template_id.id
        res = super().create(vals_list)
        for record in res:
            if not record.picking_id.return_id and record.test_type in ('maintenance', 'maintenance_preinst'):
                maintenance_type = 'initial_review' if record.test_type == 'maintenance' else 'pre_inst'
                repair = self.env['repair.order'].create({
                    'product_id': record.product_id.id,
                    'maintenance_type': maintenance_type,
                    'schedule_date': fields.Datetime.now(),
                    'check_required_maintenance_product': False,
                    'partner_id': record.product_id.partner_id.id
                })
                repair._onchange_technical_user_id()
                record.repair_id = repair.id
        return res

    def action_open_quality_check_wizard(self, current_check_id=None):
        check_ids = sorted(self.ids)
        check_id = self.browse(current_check_id or check_ids[0])
        if check_id.test_type in ('maintenance', 'maintenance_preinst'):
            action = check_id.action_quality_worksheet()
            quality_wizard = self.env['quality.check.wizard'].create({
                'check_ids': check_ids,
                'current_check_id': check_id.id,
            })
            action['context'].update({
                'default_check_ids': check_ids,
                'default_current_check_id': check_id.id,
                'quality_wizard_id': quality_wizard.id,
                'from_failure_form': False,
            })
            return action
        return super().action_open_quality_check_wizard(current_check_id)

    @api.onchange('point_id')
    def _onchange_point_id(self):
        super()._onchange_point_id()
        if self.point_id and self.point_id.test_type in ('maintenance', 'maintenance_preinst'):
            self.worksheet_template_id = self.point_id.worksheet_template_id

    def _is_pass_fail_applicable(self):
        return self.test_type in ('maintenance', 'maintenance_preinst') and True or super()._is_pass_fail_applicable()

    def do_pass(self):
        if self.test_type in ('maintenance', 'maintenance_preinst') and self.repair_id.state != 'done' and not self.picking_id.return_id:
            raise ValidationError(
                'No se puede aprobar el control de calidad ya que la reparación no está terminada.')
        return super().do_pass()

    def action_worksheet_check(self):
        if self.test_type in ('maintenance', 'maintenance_preinst') and self.repair_id.state != 'done' and not self.picking_id.return_id:
            raise ValidationError(
                'No se puede aprobar el control de calidad ya que la reparación no está terminada.')
        return super().action_worksheet_check()