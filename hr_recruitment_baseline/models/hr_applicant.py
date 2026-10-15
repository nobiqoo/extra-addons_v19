# -*- coding: utf-8 -*-

from odoo import models, fields, api


class HrApplicant(models.Model):
    _inherit = 'hr.applicant'

    @api.depends('stage_id.hired_stage')
    def _compute_date_closed(self):
        # Keep the hire date once set: later stages placed after the hired one
        # (e.g. "Fin del proceso") must not drop it nor the "Hired" ribbon.
        for applicant in self:
            if applicant.stage_id and applicant.stage_id.hired_stage and not applicant.date_closed:
                applicant.date_closed = fields.Datetime.now()

    def _get_employee_create_vals(self):
        vals = super()._get_employee_create_vals()
        vals.update({
            'partner_id': self.partner_id.id,
        })
        return vals
