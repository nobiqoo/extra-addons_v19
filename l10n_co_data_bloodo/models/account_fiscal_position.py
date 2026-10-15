# -*- coding: utf-8 -*-

from odoo import fields, models, _

class AccountFiscalPosition(models.Model):
    _inherit = 'account.fiscal.position'
    
    fiscal_position_local = fields.Boolean(
        'Posición Fiscal Local',
        related='company_id.fiscal_position_local')

    dian_obligation_type_ids = fields.Many2many('dian.type_code',
                                'fiscal_dian_obligation_types_rel',
                                'fiscal_id', 'type_id',
                                'Obligaciones y Responsabilidades',
                                domain=[('type', '=', 'obligation'),
                                        ('is_required_dian', '=', True)])
    dian_tax_scheme_id = fields.Many2one('dian.tax.type',
                                'Responsabilidad Fiscal',
                                domain=[('dian_code', 'in', ('01', '04', 
                                                             'ZA', 'ZZ'))])
