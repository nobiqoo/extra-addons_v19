# -*- coding: utf-8 -*-

import re

from odoo import api, fields, models, tools, _
from odoo.exceptions import UserError

emails_split = re.compile(r"[;,\n\r]+")


class SurveyInvite(models.TransientModel):
    _inherit = 'survey.invite'

    readonly_partners = fields.Boolean(
        string='Solo Lectura Terceros'
    )
    check_survey_mode = fields.Boolean(
        string='Validar modo de encuesta',
        default=False
    )

    def action_invite(self):
        if not self.env.context.get('repairs', False):
            return super().action_invite()
        repairs = self.env['repair.order'].search([('id', 'in', self.env.context.get('repairs', []))])

        self.ensure_one()
        Partner = self.env['res.partner']

        # compute partners and emails, try to find partners for given emails
        valid_partners = self.partner_ids
        langs = set(valid_partners.mapped('lang')) - {False}
        if len(langs) == 1:
            self = self.with_context(lang=langs.pop())
        valid_emails = []
        for email in emails_split.split(self.emails or ''):
            partner = False
            email_normalized = tools.email_normalize(email)
            if email_normalized:
                limit = None if self.survey_users_login_required else 1
                partner = Partner.search([('email_normalized', '=', email_normalized)], limit=limit)
            if partner:
                valid_partners |= partner
            else:
                email_formatted = tools.email_split_and_format(email)
                if email_formatted:
                    valid_emails.extend(email_formatted)

        if not valid_partners and not valid_emails:
            raise UserError(_("Ingrese al menos un destinatario válido."))

        answers = self._prepare_answers(valid_partners, valid_emails)
        for answer in answers:
            mail = self._send_mail(answer)
            mail.reply_to = False
            mail.send()
        
        for repair in repairs:
            repair.survey_response_id = answers[0].id
            repair.survey_id = self.survey_id.id

        return {'type': 'ir.actions.act_window_close'}

    def _prepare_answers(self, partners, emails):
        if not self.env.context.get('repairs', False):
            return super()._prepare_answers(partners, emails)
        existing_answers = self.env['survey.user_input']

        partners_done, emails_done, answers = self._get_done_partners_emails(existing_answers)

        for new_partner in partners - partners_done:
            answers |= self.survey_id._create_answer(partner=new_partner, check_attempts=False, **self._get_answers_values())
        for new_email in [email for email in emails if email not in emails_done]:
            answers |= self.survey_id._create_answer(email=new_email, check_attempts=False, **self._get_answers_values())

        return answers
