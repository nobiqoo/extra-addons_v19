# -*- coding: utf-8 -*-
from odoo import fields, models


class HrPayslipType(models.Model):
    _inherit = 'hr.payslip.type'

    send_in_portal = fields.Boolean(
        string='Enviar nómina en portal',
        default=True,
    )
