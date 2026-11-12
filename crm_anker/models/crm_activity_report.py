# -*- coding: utf-8 -*-

from odoo import fields, models


class CrmActivityReport(models.Model):
    _inherit = 'crm.activity.report'

    anker_responsible_partner_id = fields.Many2one(
        'res.partner',
        string='Encargado de la actividad',
        readonly=True,
    )

    def _select(self):
        return super()._select() + (
            ', m.anker_responsible_partner_id AS anker_responsible_partner_id'
        )
