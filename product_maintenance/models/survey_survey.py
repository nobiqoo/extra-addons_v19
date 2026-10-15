from odoo import api, fields, models, tools, _
from odoo.exceptions import UserError


class SurveySurvey(models.Model):
    _inherit = 'survey.survey'

    is_maintenance_survey = fields.Boolean(
        string='Es Encuesta de Mantenimiento',
        default=False
    )

    def action_send_survey(self):
        self.check_validity()

        if self.is_maintenance_survey or self.env.context.get('repairs', False):
            template = self.env.ref('product_maintenance.product_maintenance_mail_user_input_invite', raise_if_not_found=False)
        else:
            template = self.env.ref('survey.mail_template_user_input_invite', raise_if_not_found=False)

        if not self.env.context.get('repairs', False):
            local_context = dict(
                self.env.context,
                default_survey_id=self.id,
                default_template_id=template and template.id or False,
                default_email_layout_xmlid='mail.mail_notification_light',
                default_send_email=(self.access_mode != 'public'),
            )
        else:
            repairs = self.env['repair.order'].search([('id', 'in', self.env.context.get('repairs', []))])
            partners = self.env['res.partner']
            for repair in repairs:
                if not repair.partner_id:
                    raise UserError(
                        'La orden {name} no tiene asociado un tercero para enviar la encuesta.'.format(name=repair.name))
                partners += repair.partner_id

            local_context = dict(
                self.env.context,
                default_survey_id=self.id,
                default_template_id=template and template.id or False,
                default_email_layout_xmlid='mail.mail_notification_light',
                default_send_email=True,
                default_readonly_partners=True,
                default_partner_ids=[(6, 0, partners.ids)],
                default_check_survey_mode=True
            )

        return {
            'type': 'ir.actions.act_window',
            'name': 'Compartir Encuesta',
            'view_mode': 'form',
            'res_model': 'survey.invite',
            'target': 'new',
            'context': local_context,
        }
