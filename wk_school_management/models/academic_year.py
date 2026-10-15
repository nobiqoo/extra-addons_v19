# -*- coding: utf-8 -*-
#################################################################################
#
# Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>; )
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>;
#
#################################################################################

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import timedelta
import logging

_logger = logging.getLogger(__name__)


class AcademicYear(models.Model):

    _name = 'wk.academic.year'
    _description = 'Academic Year'
    _order = "create_date desc"

    name = fields.Char(string='Title', required=True)
    start_date = fields.Date(string="Start Date", required=True)
    end_date = fields.Date(string="End Date", required=True)
    term_ids = fields.One2many(
        'wk.grade.terms', 'academic_year_id', 'Terms', required=True)
    divide_weightage = fields.Boolean(
        string='Divide weightage equally in all terms?')
    session_id = fields.Many2one('wk.school.session', string='Session', required=True)
    session_status = fields.Selection(
        related='session_id.state', string='Session Status', store=True)
    enrollment_ids = fields.One2many(
        'student.enrollment', 'academic_year_id', string='Enrollments')
    description = fields.Text(string="Description")

    @api.constrains('term_ids')
    def _check_for_weightage(self):
        for term in self:
            total = 0
            for weightage in term.term_ids:
                total += weightage.weightage
            if total > 100:
                raise ValidationError(
                    _("Total weightage of an academic year cannot be greater than 100% !!"))
            elif total < 100 and not term.divide_weightage:
                raise ValidationError(
                    _("Total weightage of an academic year should be 100% !!"))
            elif total == 0 and not term.divide_weightage:
                raise ValidationError(
                    _("Total weightage of an academic year should be 100% !!"))

    @api.constrains('start_date', 'end_date')
    def _check_for_academic_year_duration(self):
        for record in self:
            if record.start_date > record.end_date:
                raise ValidationError(
                    _("Invalid duration.End date need to be after the start date."))

            if record.end_date > record.start_date + timedelta(days=366):
                raise ValidationError(
                    _("Academic Year's duration cannot exceed 1 year."))

    @api.constrains('start_date', 'end_date', 'session_id')
    def _check_academic_date_with_session_date(self):
        for record in self:
            if record.start_date and record.end_date and record.session_id:
                if record.start_date < record.session_id.start_date or record.end_date > record.session_id.end_date:
                    raise ValidationError(
                        _("Academic Year has to lie within Session's duration."))

    @api.model_create_multi
    def create(self, vals_list):
        years = super(AcademicYear, self).create(vals_list)
        for year in years:
            if year.divide_weightage:
                total_terms = len(year.term_ids)
                if total_terms != 0:
                    term_weightage = (100 / total_terms)
                    for term in year.term_ids:
                        term.weightage = term_weightage
        return years

    def write(self, vals):
        res = super().write(vals)
        for year in self:
            if year.divide_weightage:
                total_terms = len(year.term_ids)
                if total_terms != 0:
                    term_weightage = (100 / total_terms)
                    for term in year.term_ids:
                        term.weightage = term_weightage
        return res
