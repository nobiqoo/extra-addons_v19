# -*- coding: utf-8 -*-
#################################################################################
#
# Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>; )
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>;
#
#################################################################################

import logging
from odoo import http
from odoo.http import request
from odoo.service.common import exp_version
from odoo.tools import py_to_js_locale, SQL
from odoo.tools.image import image_data_uri

_logger = logging.getLogger(__name__)


class StudentAttendanceKiosk(http.Controller):

    @staticmethod
    def _get_company(token):
        company = request.env['res.company'].sudo().search([('attendance_kiosk_key', '=', token)])
        return company

    @staticmethod
    def _get_student_info_response(student):
        response = {}
        if student:
            response = {
                'student_name': student.name,
                'student_avatar': student.student_image and image_data_uri(student.student_image),
            }
        return response

    @http.route('/student_attendance/kiosk_mode_menu/<int:company_id>', auth='user', type='http')
    def kiosk_menu_item_action(self, company_id):
        if request.env.user.has_group("wk_school_management.wk_school_management_officer_group"):
            # Auto log out will prevent users from forgetting to log out of their session
            # before leaving the kiosk mode open to the public. This is a prevention security
            # measure.
            if self.has_password():
                request.session.logout(keep_db=True)
            company_record = request.env['res.company'].browse(company_id)
            attendance_kiosk_url = company_record.get_base_url() + "/student_attendance/" + company_record.attendance_kiosk_key
            return request.redirect(attendance_kiosk_url)
        else:
            return request.not_found()

    @http.route(["/student_attendance/<token>"], type='http', auth='public', website=True, sitemap=True)
    def open_student_kiosk_mode(self, token, from_trial_mode=False):
        company = self._get_company(token)
        if not company:
            return request.not_found()
        else:
            has_password = self.has_password()
            if not from_trial_mode and has_password:
                request.session.logout(keep_db=True)
            version_info = exp_version()

        return request.render('wk_school_management.student_kiosk_template', {
            'kiosk_backend_info': {
                'token': token,
                'company_id': company.id,
                'company_name': company.name,
                'kiosk_mode': 'barcode',
                'from_trial_mode': from_trial_mode,
                'barcode_source': company.attendance_barcode_source,
                'lang': py_to_js_locale(company.partner_id.lang),
                'server_version_info': version_info.get('server_version_info'),
            },
        })

    @http.route('/school_management/attendance_barcode_scanned', website=True, type="jsonrpc", auth="public")
    def scan_barcode(self, token, barcode):
        company = self._get_company(token)
        if company:
            student = request.env['student.student'].sudo().search([('barcode', '=', barcode), ('company_id', '=', company.id)], limit=1)
            if student:
                student._mark_attendance(student.id)
                return self._get_student_info_response(student)
        return {}

    @http.route('/school_management/mark_attendance', type='jsonrpc', website=True, auth='public')
    def mark_attendance(self, enrollment_number, token):
        company = self._get_company(token)
        if company:
            student = request.env['student.student'].sudo().search([('current_enrollment_id', '=', enrollment_number), ('company_id', '=', company.id)], limit=1)
            student._mark_attendance(student)
            return self._get_student_info_response(student)
        return {}

    @http.route('/school_management/user_timezone', type='jsonrpc', website=True, auth='public')
    def get_user_timezone(self, **kw):
        user_tz = request.env.user.tz
        return user_tz

    def has_password(self):
        # With this method we try to know whether it's the user is on trial mode or not.
        # We assume that in trial, people have not configured their password yet and their password should be empty.
        request.env.cr.execute(
            SQL('''
                SELECT COUNT(password)
                  FROM res_users
                 WHERE id=%(user_id)s
                   AND password IS NOT NULL
                 LIMIT 1
                ''', user_id=request.env.user.id))
        return bool(request.env.cr.fetchone()[0])
