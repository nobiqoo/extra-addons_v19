# -*- coding: utf-8 -*-
#################################################################################
#
# Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>; )
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>;
#
#################################################################################
from odoo import models, api
from datetime import datetime
import logging

_logger = logging.getLogger(__name__)


class ReportStudentTranscript(models.AbstractModel):
    _name = 'report.wk_school_management.report_student_transcript'
    _description = 'Student Transcript Report'

    @api.model
    def _get_report_values(self, docids, data=None):

        session_id = data.get('session_id')
        student_id = data.get('student_id')

        return {
            'doc_ids': docids,
            'doc_model': 'student.student',
            'docs': self.env['student.student'].browse(student_id),
            'session_id': self.env['wk.school.session'].browse(session_id),
            'date': datetime.today().date()
        }
