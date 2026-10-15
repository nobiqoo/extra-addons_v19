# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class ResBankTxtConfigLine(models.Model):
    _name = 'res.bank.txt_config.line'
    _description = 'Bank txt config line'

    header_setting_id = fields.Many2one('res.bank.txt_config',
                                        'Txt header generator setting')
    body_setting_id = fields.Many2one('res.bank.txt_config',
                                      'Txt body generator setting.')
    footer_setting_id = fields.Many2one('res.bank.txt_config',
                                        'Txt footer generator setting..')
    name = fields.Char('Name')
    sequence = fields.Integer('Sequence')
    size = fields.Integer('Size', required=True)
    alignment = fields.Selection([('left', 'Left'),
                                  ('right', 'Right'), ],
                                 'Alignment',
                                 required=True)
    fill = fields.Text('Filling', required=True)
    value_type = fields.Selection([('burned', 'Burned value'),
                                   ('python', 'Python'),
                                   ('call', 'Call variable')],
                                  'Value type',
                                  required=True)
    value = fields.Text('Value', required=True)
