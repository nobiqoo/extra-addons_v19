# -*- coding: utf-8 -*-

from odoo import fields, models


class AccountTax(models.Model):
    _inherit = 'account.tax'

    dian_tax_type_id = fields.Many2one('dian.tax.type',
                                       'Tipo impuesto DIAN')


# class AccountTaxTemplate(models.Model):
#     _inherit = 'account.tax.template'

#     dian_tax_type_id = fields.Many2one('dian.tax.type',
#                                        'Tipo impuesto DIAN')
