# -*- coding: utf-8 -*-
from odoo import models, fields, api, release, _


class HrEmployeePublic(models.Model):
    _inherit = 'hr.employee.public'

    payroll_mail_notifier = fields.Char(readonly=True)
    address_home_id = fields.Many2one('res.partner', readonly=True)
    partner_id = fields.Many2one('res.partner', readonly=True)
    family_to_certified = fields.Many2one('hr.family.information', readonly=True)
    family_information_ids = fields.One2many('hr.family.information', readonly=True)
    coach_partner_id = fields.Many2one(
        'res.partner',
        readonly=True,
    )
