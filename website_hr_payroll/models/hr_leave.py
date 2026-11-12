# -*- coding: utf-8 -*-
from odoo import fields, models, _
from odoo.addons.utilities_collection.time import days360

COACH_GROUP = 'website_hr_payroll.coach_payslip_group'
MONTHS = ('ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic')


class HrLeave(models.Model):
    _inherit = 'hr.leave'

    user_approval_id = fields.Many2one(
        comodel_name='res.users', string='Usuario que aprueba', readonly=True, copy=False)
    enable_button_notify = fields.Boolean(
        related='leave_type_id.enable_button_notify',
        string='Habilitar botón para notificación manual', readonly=True)
    enable_approval_flow = fields.Boolean(
        related='leave_type_id.enable_approval_flow',
        string='Habilitar flujo de aprobación', readonly=True)

    # ------------------------------------------------------------------
    # Correos destino (usados por las plantillas de correo)
    # ------------------------------------------------------------------
    def _get_website_coach_emails(self):
        """Correo del instructor (o contacto instructor) del empleado de la ausencia."""
        self.ensure_one()
        employee = self.employee_id
        # Esta opción la define hr_payroll_co; en versiones que no la tienen se usa el instructor.
        if getattr(self.company_id, 'use_partner_like_coach', False):
            return employee.coach_partner_id.email or ''
        coach = employee.coach_id
        return coach.work_email or coach.payroll_mail_notifier or coach.partner_id.email or ''

    def _get_website_employee_emails(self):
        """Correo del empleado que registró la ausencia."""
        self.ensure_one()
        employee = self.employee_id
        return employee.payroll_mail_notifier or employee.work_email or employee.partner_id.email or ''

    def _get_payroll_users_employees(self):
        self.ensure_one()
        return self.env['hr.employee'].sudo().search(
            [('user_id', 'in', self.company_id.payroll_users_ids.ids)])

    def _get_website_payroll_emails(self):
        """Correos de los usuarios notificadores de nómina de la compañía."""
        self.ensure_one()
        emails = []
        for user in self.company_id.payroll_users_ids:
            employee = self.env['hr.employee'].sudo().search([('user_id', '=', user.id)], limit=1)
            email = employee.payroll_mail_notifier or employee.work_email or user.email
            if email and email not in emails:
                emails.append(email)
        return ','.join(emails)

    def _get_approval_request_emails(self):
        """Usuarios de nómina y solicitante: pedir la validación de la ausencia confirmada."""
        self.ensure_one()
        emails = []
        for employee in self._get_payroll_users_employees():
            if employee.work_email:
                emails.append(employee.work_email)
        if self.employee_id.work_email:
            emails.append(self.employee_id.work_email)
        return ','.join(dict.fromkeys(emails))

    def _get_approval_result_emails(self):
        """Usuarios de nómina y solicitante: resultado de la aprobación."""
        self.ensure_one()
        emails = []
        for employee in self._get_payroll_users_employees():
            if employee.payroll_mail_notifier:
                emails.append(employee.payroll_mail_notifier)
        if self.employee_id.payroll_mail_notifier:
            emails.append(self.employee_id.payroll_mail_notifier)
        return ','.join(dict.fromkeys(emails))

    def _get_refuse_emails(self):
        self.ensure_one()
        return self.employee_id.work_email or ''

    # ------------------------------------------------------------------
    # Textos usados en las plantillas
    # ------------------------------------------------------------------
    @staticmethod
    def _format_short_date(value):
        return f"{value.day} {MONTHS[value.month - 1]} {value.year}" if value else ''

    def _get_requested_date_str(self):
        return self._format_short_date(self.create_date)

    def _get_start_date_str(self):
        return self._format_short_date(self.date_start)

    def _get_end_date_str(self):
        return self._format_short_date(self.date_end)

    def _get_days_qty(self):
        return days360(self.date_start, self.date_end)

    def _get_state_request(self):
        if self.state == 'validated':
            return 'APROBADO'
        if self.state == 'cancel':
            return 'RECHAZADO'
        return 'PENDIENTE'

    # ------------------------------------------------------------------
    # Flujo de aprobación
    # ------------------------------------------------------------------
    def _send_flow_mail(self, xmlid, log_message):
        template = self.env.ref(xmlid)
        for record in self:
            template.send_mail(record.id)
            record.message_post(body=log_message)

    def to_validated(self):
        res = super().to_validated()
        for record in self.filtered(lambda r: r.state == 'validated'):
            record.user_approval_id = self.env.user
        return res

    def to_confirm(self):
        flow_records = self.filtered(lambda r: r.leave_type_id.enable_approval_flow)
        # El mentor solo tiene permiso de lectura: confirma con sudo si todas las ausencias usan el flujo.
        if flow_records == self and self.env.user.has_group(COACH_GROUP):
            self = self.sudo()
            flow_records = flow_records.sudo()
        res = super(HrLeave, self).to_confirm()
        for record in flow_records.filtered(lambda r: r.state == 'confirm'):
            if record.company_id.payroll_users_ids or record.employee_id.work_email:
                record._send_flow_mail(
                    'website_hr_payroll.hr_leave_user_payroll_notification_mail_template',
                    _('Correo para validación enviado a usuarios de nómina y solicitante.'))
        return res

    def to_cancel(self):
        draft_by_coach = self.env.user.has_group(COACH_GROUP) and all(r.state == 'draft' for r in self)
        if draft_by_coach:
            self = self.sudo()
        flow_records = self.filtered(
            lambda r: r.leave_type_id.enable_approval_flow and r.employee_id.work_email)
        res = super(HrLeave, self).to_cancel()
        flow_records.filtered(lambda r: r.state == 'cancel')._send_flow_mail(
            'website_hr_payroll.leave_mail_notification_cancel_to_users',
            _('Correo de notificación de cancelación de la ausencia enviado al solicitante.'))
        return res

    def notify_to_coach(self):
        self.filtered(lambda r: r.state == 'draft')._send_flow_mail(
            'website_hr_payroll.leave_mail_to_coach',
            _('Correo para confirmación enviado al mentor.'))

    def send_mail_approval(self):
        for record in self.filtered(lambda r: r.company_id.payroll_users_ids):
            record._send_flow_mail(
                'website_hr_payroll.hr_leave_approval_notification_mail_template',
                _('Correos de aprobación enviados.'))
