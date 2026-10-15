# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class ModelBasicPayslipNoveltyType(models.AbstractModel):
    _inherit = 'model.basic.payslip.novelty.type'

    dian_concept_id = fields.Many2one('dian.concept.type',
                        'Concepto DIAN')
    dian_ddo = fields.Selection(
        [('dev', 'Devengos'),
         ('ded', 'Deducciones')],
        'Tipo DIAN',
        compute='_compute_dian_ddo')
    
    @api.depends('category')
    def _compute_dian_ddo(self):
        for record in self:
            if record.category == 'deductions':
                record.dian_ddo = 'ded'
            else:
                record.dian_ddo = 'dev'
