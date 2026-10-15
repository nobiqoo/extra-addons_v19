# -*- coding: utf-8 -*-

from odoo import models, fields, api

class StockPickingType(models.Model):
    _inherit = "stock.picking.type"

    package_label_report_template_pdf = fields.Many2one('ir.actions.report',
                                      'Report Template PDF',
                                      domain="[('report_type', 'in', ['qweb-pdf']),('model','=','stock.quant.package')]")
    package_label_report_template_zpl = fields.Many2one('ir.actions.report',
                                      'Report Template ZPL',
                                      domain="[('report_type', 'in', ['qweb-text']),('model','=','stock.quant.package')]")
