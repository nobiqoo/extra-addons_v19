# -*- coding: utf-8 -*-
from odoo import fields, models


class HrEmployee(models.Model):
    """Inherit the model to add field"""
    _inherit = 'hr.employee'

    device_id_num = fields.Char(string='Biometric Device ID',
                                help="Give the biometric device id")

    allowed_device_ids = fields.Many2many(
        'biometric.device.details',
        string='Allowed Devices',
        help="If selected, only punches from these specific devices will be processed. If empty, all devices are accepted."
    )
