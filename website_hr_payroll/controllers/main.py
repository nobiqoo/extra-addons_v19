# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
import logging


from odoo import http
from odoo.http import request
from odoo import fields
from werkzeug.exceptions import BadRequest
from datetime import date, datetime, timedelta

_logger = logging.getLogger(__name__)


class WebsiteHrPayroll(http.Controller):

    @staticmethod
    def _json_error(message):
        return request.make_json_response({'error': message})

    @staticmethod
    def _json_ok(values):
        return request.make_json_response(values)

    @http.route(['/employee', '/<lang>/employee'], type='http', auth="public", website=True, sitemap=False)
    def website_hr_payroll_employee_root(self, **kwargs):
        return request.redirect('/employee/leave')

    @http.route(['/employee/leave'], type='http', auth="public", website=True, sitemap=True)
    def website_hr_payroll_leave(self, team=None, **kwargs):
        leave_types = request.env['hr.leave.type'].sudo().search([
            ('company_id', '=', request.env.company.id),
            ('allow_in_website', '=', True)
        ])
        result = {
            'leave_types': leave_types,
        }
        return request.render("website_hr_payroll.leave", result)

    @http.route(['/employee/detachable'], type='http', auth="public", website=True, sitemap=True)
    def website_hr_payroll_detachable(self, team=None, **kwargs):
        leave_types = request.env['hr.leave.type'].sudo().search([
            ('company_id', '=', request.env.company.id),
            ('allow_in_website', '=', True)
        ])
        years, months = self._get_range_years()
        result = {
            'leave_types': leave_types,
            'years': years,
            'months': months
        }
        return request.render("website_hr_payroll.detachable", result)

    @http.route(['/employee/certificate'], type='http', auth="public", website=True, sitemap=True)
    def website_hr_payroll_certificate(self, team=None, **kwargs):
        ceritificate_types = {
            'without_salary': 'Sin Salario',
            'with_salary': 'Con Salario',
            'with_variable_salary': 'Con Salario Variable',
        }
        result = {
            'ceritificate_types': ceritificate_types
        }
        return request.render("website_hr_payroll.certificate", result)

    @http.route(['/leave/form', '/<lang>/leave/form'], type='http', auth="public", methods=['POST'], multilang=False)
    def website_hr_payroll_leave_form_emty(self, **kwargs):
        # This is a workaround to don't add language prefix to <form action="/leave/form/" ...>
        return ""

    # Check and insert values from the form on the model <model>
    @http.route(['/leave/form/<string:model_name>', '/<lang>/leave/form/<string:model_name>'], type='http', auth="public", methods=['POST'], website=True, csrf=False)
    def website_hr_payroll_leave_form(self, model_name, **kwargs):
        csrf_token = request.params.pop('csrf_token', None)
        if request.session.uid and not request.validate_csrf(csrf_token):
            raise BadRequest('Session expired (invalid CSRF token)')

        identification_number = kwargs.get('identification_number')
        date_from = kwargs.get('date_from')
        date_to = kwargs.get('date_to')
        leave_type = kwargs.get('leave_type')
        file_leave = kwargs.get('file_leave') or kwargs.get('file_leave[0][0]') or request.httprequest.files.get('file_leave')

        if not identification_number or not date_from or not date_to:
            return self._json_error('Por favor, llene el formulario correctamente.')

        if not leave_type:
            return self._json_error('Por favor, seleccione el TIPO DE AUSENCIA.')

        date_from_obj = fields.Date.to_date(date_from)
        date_to_obj = fields.Date.to_date(date_to)
        if not date_from_obj or not date_to_obj:
            return self._json_error('Por favor, llene el formulario correctamente.')

        if date_to_obj < date_from_obj:
            return self._json_error('La fecha final no puede ser menor a la inicial.')
        
        employee = request.env['hr.employee'].sudo().search([
            ('identification_id', '=', identification_number)
        ], limit=1)

        if not employee:
            return self._json_error('No se ha econtrado información asociada al número de identificación')

        contract = request.env['hr.contract'].sudo().search([
            ('employee_id', '=', employee.id),
            ('state', '=', 'open')
        ], limit=1)
    
        if not contract:
            return self._json_error('No se ha econtrado información asociada al número de identificación.')

        try:
            leave_type_id = int(leave_type)
        except (TypeError, ValueError):
            return self._json_error('Por favor, seleccione el TIPO DE AUSENCIA.')

        leave_type = request.env['hr.leave.type'].sudo().search([
            ('id', '=', leave_type_id),
            ('allow_in_website', '=', True),
        ], limit=1)
        if not leave_type:
            return self._json_error('Por favor, seleccione el TIPO DE AUSENCIA.')

        if leave_type.need_file_in_website and not file_leave:
            return self._json_error('Es necesario adjuntar un archivo.')

        leave = request.env['hr.leave'].sudo().create({
            'company_id': request.env.company.id,
            'contract_id': contract.id,
            'employee_id': employee.id,
            'date_start': date_from_obj,
            'date_end': date_to_obj,
            'leave_type_id': leave_type.id,
        })

        if file_leave:
            attachment_data = base64.b64encode(file_leave.read()).decode('utf-8')
            attachment = request.env['ir.attachment'].sudo().create({
                'name': file_leave.filename,
                'datas': attachment_data,
                'res_model': 'hr.leave',
                'res_id': leave.id,
                'mimetype': file_leave.content_type
            })

            leave.sudo().message_post(
                body="Esta ausencia se creó a través del sitio web.",
                attachment_ids=attachment.ids
            )
        else:
            leave.sudo().message_post(
                body=("Esta ausencia se creó a través del sitio web.")
            )
        return self._json_ok({'id': leave.id})

    @http.route(['/detachable/form', '/<lang>/detachable/form'], type='http', auth="public", methods=['POST'], multilang=False)
    def website_hr_payroll_detachable_form_empty(self, **kwargs):
        # This is a workaround to don't add language prefix to <form action="/detachable/form/" ...>
        return ""

    @http.route(['/detachable/form/<string:model_name>', '/<lang>/detachable/form/<string:model_name>'], type='http', auth="public", methods=['POST'], website=True, csrf=False)
    def website_hr_payroll_detachable_form(self, model_name, **kwargs):
        csrf_token = request.params.pop('csrf_token', None)
        if request.session.uid and not request.validate_csrf(csrf_token):
            raise BadRequest('Session expired (invalid CSRF token)')

        identification_number = kwargs.get('identification_number')
        year = kwargs.get('year')
        month = kwargs.get('month')

        if not identification_number or not year or not month:
            return self._json_error('Por favor, llene el formulario correctamente.')
        
        employee = request.env['hr.employee'].sudo().search([
            ('identification_id', '=', identification_number)
        ], limit=1)

        if not employee:
            return self._json_error('No se ha econtrado información asociada al número de identificación.')

        contract = request.env['hr.contract'].sudo().search([
            ('employee_id', '=', employee.id),
            ('state', '=', 'open')
        ], limit=1)
    
        if not contract:
            return self._json_error('No se ha econtrado información asociada al número de identificación.')

        date_from, date_to = self.get_month_start_end(year, month)

        payslips = request.env['hr.payslip'].sudo().search([
            ('contract_id', '=', contract.id),
            ('period_id.start', '>=', date_from),
            ('period_id.end', '<=', date_to),
            ('state', '=', 'paid'),
            ('payslip_type_id.send_in_portal', '=', True),
        ])

        if not payslips:
            return self._json_error('No se ha econtrado información relacionada a los datos ingresados.')

        if not self.send_mail(payslips):
            return self._json_error('No fue posible enviar el correo. Por favor, contacte al área de recursos humanos.')

        return self._json_ok({'id': contract.id})

    @http.route(['/certificate/form', '/<lang>/certificate/form'], type='http', auth="public", methods=['POST'], multilang=False)
    def website_hr_payroll_certificate_form_empty(self, **kwargs):
        # This is a workaround to don't add language prefix to <form action="/certificate/form/" ...>
        return ""

    @http.route(['/certificate/form/<string:model_name>', '/<lang>/certificate/form/<string:model_name>'], type='http', auth="public", methods=['POST'], website=True, csrf=False)
    def website_hr_payroll_certificate_form(self, model_name, **kwargs):
        csrf_token = request.params.pop('csrf_token', None)
        if request.session.uid and not request.validate_csrf(csrf_token):
            raise BadRequest('Session expired (invalid CSRF token)')

        identification_number = kwargs.get('identification_number')
        ceritificate = kwargs.get('ceritificate')

        if not identification_number or not ceritificate:
            return self._json_error('Por favor, llene el formulario correctamente.')
        
        employee = request.env['hr.employee'].sudo().search([
            ('identification_id', '=', identification_number)
        ], limit=1)

        if not employee:
            return self._json_error('No se ha econtrado información asociada al número de identificación.')

        contract = request.env['hr.contract'].sudo().search([
            ('employee_id', '=', employee.id),
            ('state', '=', 'open')
        ], limit=1)
    
        if not contract:
            return self._json_error('No se ha econtrado información asociada al número de identificación.')

        if not self.send_certificate(ceritificate, contract):
            return self._json_error('No fue posible enviar el correo. Por favor, contacte al área de recursos humanos.')

        return self._json_ok({'id': contract.id})

    @http.route(['/leave-success'], type='http', auth="public", website=True, sitemap=True)
    def website_hr_payroll_leave_sucess(self, team=None, **kwargs):
        return request.render("website_hr_payroll.leave_success", {})

    @http.route(['/detachable-success'], type='http', auth="public", website=True, sitemap=True)
    def website_hr_payroll_detachable_sucess(self, team=None, **kwargs):
        return request.render("website_hr_payroll.detachable_success", {})

    @http.route(['/certificate-success'], type='http', auth="public", website=True, sitemap=True)
    def website_hr_payroll_certificate_sucess(self, team=None, **kwargs):
        return request.render("website_hr_payroll.certificate_success", {})

    def _get_range_years(self, interval=2):
        months = {
            1: 'Enero',
            2: 'Febrero',
            3: 'Marzo',
            4: 'Abril',
            5: 'Mayo',
            6: 'Junio',
            7: 'Julio',
            8: 'Agosto',
            9: 'Septiembre',
            10: 'Octubre',
            11: 'Noviembre',
            12: 'Diciembre',
        }
        years = {}
        for i in range(interval):
            year = date.today().year - i
            years[year] = year
        return years, months

    def get_month_start_end(self, year, month):
        year = int(year)
        month = int(month)
        month_start = datetime(year, month, 1).date()

        if month == 12:
            next_month_start = datetime(year + 1, 1, 1).date()
        else:
            next_month_start = datetime(year, month + 1, 1).date()

        month_end = next_month_start - timedelta(days=1)

        return month_start, month_end

    def send_mail(self, payslips):
        mail_template = request.env.ref('hr_payroll_co.hr_payroll_co_mail_template')
        for payslip in payslips:
            try:
                mail_template.sudo().send_mail(payslip.id, force_send=True, raise_exception=True)
            except Exception:
                _logger.exception(
                    'Error enviando desprendible de nómina (payslip %s) desde el sitio web', payslip.id)
                return False
        return True

    def send_certificate(self, certificate_type, contract):
        mail_template = request.env.ref('hr_payroll_co.payroll_work_certificate_mail_template')
        try:
            mail_template.sudo().with_context(
                certificate_type=certificate_type).send_mail(contract.id, force_send=True, raise_exception=True)
        except Exception:
            _logger.exception(
                'Error enviando certificado laboral (contrato %s) desde el sitio web', contract.id)
            return False
        return True
