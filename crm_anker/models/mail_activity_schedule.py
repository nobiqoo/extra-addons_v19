# -*- coding: utf-8 -*-

from odoo import fields, models


class MailActivitySchedule(models.TransientModel):
    _inherit = 'mail.activity.schedule'

    anker_responsible_partner_id = fields.Many2one(
        'res.partner',
        string='Encargado de la actividad',
        domain=[('is_company', '=', False)],
    )

    def _action_schedule_activities(self):
        activities = super()._action_schedule_activities()
        if self.res_model == 'crm.lead' and activities:
            activities.write({
                'anker_responsible_partner_id': self.anker_responsible_partner_id.id,
            })
        return activities
