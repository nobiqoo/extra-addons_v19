# -*- coding: utf-8 -*-

from odoo import models

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    def _get_certificate_selection(self):
        selection = super()._get_certificate_selection()
        selection += [
            ('technician', 'Technician'),
            ('technologist', 'Technologist'),
            ('professional', 'Professional'),
            ('specialist', 'Specialist'),
        ]

        return selection