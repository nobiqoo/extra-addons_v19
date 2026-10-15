# -*- coding: utf-8 -*-
from odoo import models, fields, api
from ..hr_payslip_period.hr_period import TYPE_BIWEEKLY

MODALITY = [
    ('EXT', 'Exento de retención'),
    ('AVP', 'Aporte voluntario de pensión'),
    ('AFC', 'Ahorro y fomento a la construcción')
]


class HrNoveltyType(models.Model):
    _name = 'hr.novelty.type'
    _inherit = 'model.basic.payslip.novelty.type'
    _description = 'Categoría de Novedades'
    _order = 'name'

    dep_days_worked = fields.Boolean(
        string='Depende de días trabajados', default=False)
    modality = fields.Selection(
        string='Modalidad de retención', selection=MODALITY, default=False)

    single_biweekly_payment = fields.Boolean('Pago único quincenal')
    biweekly_type = fields.Selection(TYPE_BIWEEKLY, string='Tipo de quincena')
    apply_in_pila = fields.Boolean(
        string='Aplicar en PILA', default=True)

    use_by_default_retroactive = fields.Boolean(
        string='Usar por defecto en novedades generadas automaticas en retroactivos'
    )
    include_like_vst_pila = fields.Boolean(
        string='Incluir en PILA como VST'
    )
