# -*- coding: utf-8 -*-
from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'

    rg_group_invoice_lines = fields.Boolean(
        string='Agrupar detalle por categoría y valor unitario',
        help='En la representación gráfica de la factura agrupa las líneas por '
             'categoría de producto y, dentro de cada una, por valor unitario. '
             'Solo cambia el PDF: el XML reportado a la DIAN no se modifica.')
    ei_fiscal_respo_en = fields.Char(
        string='Responsabilidad fiscal (inglés)',
        help='Texto de responsabilidad fiscal del encabezado para clientes de '
             'habla inglesa. Si está vacío se usa el texto en español.')
    tributary_information_en = fields.Text(
        string='Información tributaria (inglés)',
        help='Información tributaria de la representación gráfica para clientes '
             'de habla inglesa. Si está vacía se usa el texto en español.')
