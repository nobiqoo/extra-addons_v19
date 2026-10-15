# -*- coding: utf-8 -*-

from odoo import models, fields
from datetime import date
from odoo.exceptions import ValidationError


class SendRepairSurveyWizard(models.TransientModel):
    _name = 'send.repair.survey.wizard'
    _description = 'Enviar encuesta de reparación'

    survey_id = fields.Many2one(
        comodel_name='survey.survey',
        string='Encuesta'
    )

    def share(self):
        repairs = self.env.context.get('active_ids', [])
        return self.survey_id.with_context(repairs=repairs).action_send_survey()
