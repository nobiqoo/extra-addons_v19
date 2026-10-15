# -*- coding: utf-8 -*-
from odoo import api, fields, models


CONTRACT_SECTION = [
    ('adm', 'Administrativa'),
    ('com', 'Comercial'),
    ('ope', 'Operativa'),
    ('pro', 'Producción')
]

CONTRACT_TERM = [
    ('fijo', 'Fijo'),
    ('indefinido', 'Indefinido'),
    ('obra-labor', 'Obra Labor')
]

CONTRACT_CLASS = [
    ('reg', 'Regular'),
    ('apr', 'Aprendiz'),
    ('int', 'Integral')
]


class HRContractType(models.Model):
    _inherit = 'hr.contract.type'

    name = fields.Char(string='Tipo de Contrato',
                       compute='_compute_name', store=True, translate=True, required=False)
    term = fields.Selection(CONTRACT_TERM, 'Termino', required=True)
    type_class = fields.Selection(CONTRACT_CLASS, 'Clase', required=True)
    section = fields.Selection(CONTRACT_SECTION, 'Estructura', required=True)
    company_id = fields.Many2one(
        'res.company', 'Company',
        default=lambda self: self.env.company,
        index=True)

    @api.depends('term', 'type_class', 'section')
    def _compute_name(self):
        for contract_type in self:
            name_items = [(contract_type.type_class or 'NONE').upper(),
                          (contract_type.term or 'NONE').upper(),
                          (contract_type.section or 'NONE').upper()]
            content = list(filter(lambda item: item != 'NONE', name_items))
            if not content:
                contract_type.name = 'Sin Especificaciones'
                continue
            contract_type.name = ' '.join(content)
