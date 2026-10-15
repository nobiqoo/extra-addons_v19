# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class Appraisal360ReportWizard(models.TransientModel):
    """Asistente para generar informes de retroalimentaciones 360."""
    _name = 'appraisal.360.report.wizard'
    _description = 'Asistente de informe de retroalimentaciones 360'

    all_employee = fields.Boolean(string='Todos los empleados', default=True)
    employee_id = fields.Many2one(
        'hr.employee',
        string='Persona evaluada',
        domain=lambda self: self._get_evaluated_employee_domain())
    survey_id = fields.Many2one(
        'survey.survey',
        string='Encuesta de retroalimentación',
        domain=[('survey_type', '=', 'appraisal')])
    date_from = fields.Date(string='Fecha desde')
    date_to = fields.Date(string='Fecha hasta')

    def _get_evaluated_employee_domain(self):
        employee_ids = self.env['hr.appraisal'].sudo().search([]).mapped('employee_id').ids
        return [('id', 'in', employee_ids)]

    def _get_appraisal_domain(self):
        domain = []
        if not self.all_employee and self.employee_id:
            domain.append(('employee_id', '=', self.employee_id.id))
        return domain

    @api.onchange('all_employee')
    def _onchange_all_employee(self):
        if self.all_employee:
            self.employee_id = False

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for wizard in self:
            if wizard.date_from and wizard.date_to and wizard.date_from > wizard.date_to:
                raise UserError(_('La fecha desde no puede ser mayor que la fecha hasta.'))

    def _prepare_report_values(self):
        if not self.all_employee and not self.employee_id:
            raise UserError(_('Debe seleccionar una persona evaluada o activar la opción Todos los empleados.'))
        return {
            'all_employee': self.all_employee,
            'employee_id': False if self.all_employee else self.employee_id.id,
            'survey_id': self.survey_id.id if self.survey_id else False,
            'date_from': self.date_from,
            'date_to': self.date_to,
        }

    def _create_generated_report(self):
        self.ensure_one()
        report = self.env['hr.appraisal.360.report'].create(self._prepare_report_values())
        report.action_generate_report()
        return report

    def action_generate_report(self):
        report = self._create_generated_report()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Informe de retroalimentaciones 360'),
            'res_model': 'hr.appraisal.360.report',
            'res_id': report.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_export_excel(self):
        report = self._create_generated_report()
        return report.action_export_excel()
