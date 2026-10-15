# -*- coding: utf-8 -*-

# from odoo import models, fields, api


# class base_data_baseline(models.Model):
#     _name = 'base_data_baseline.base_data_baseline'
#     _description = 'base_data_baseline.base_data_baseline'

#     name = fields.Char()
#     value = fields.Integer()
#     value2 = fields.Float(compute="_value_pc", store=True)
#     description = fields.Text()
#
#     @api.depends('value')
#     def _value_pc(self):
#         for record in self:
#             record.value2 = float(record.value) / 100
