# -*- coding: utf-8 -*-
#################################################################################
#
# Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>; )
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>;
#
#################################################################################

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class GradeScale(models.Model):

    _name = 'wk.grade.scales'
    _description = 'Grade Scale'

    name = fields.Char(string='Name', required=True)
    gpa_calculation = fields.Boolean(string='GPA Calculation')
    scale_line_ids = fields.One2many(
        'wk.grade.scale.line', 'scale_id', string='Scale Line')


class GradeScaleLines(models.Model):

    _name = 'wk.grade.scale.line'
    _description = 'Grade Scale Lines'
    _rec_name = 'grade_symbol'

    sequence = fields.Integer(default=1)
    grade_symbol = fields.Char(string='Symbol', required=True)
    min_percent = fields.Float(string='Min(%)')
    max_percent = fields.Float(string='Max(%)')
    conversion_percent = fields.Float(string='Symbol Conversion(%)')
    points = fields.Float(string='Points')
    scale_id = fields.Many2one('wk.grade.scales', string='Grade Scale')
    description = fields.Text(string='Short Summary')
    effort = fields.Selection([
        ('E', 'Excellent'),
        ('G', 'Good'),
        ('S', 'Satisfactory'),
        ('P', 'Poor'),
        ('N', 'Needs Improvement'),
        ('U', 'Unsatisfactory')], string="Effort")

    @api.constrains('grade_symbol', 'scale_id')
    def check_for_unique_scale_line(self):
        for record in self:
            lines = self.search([
                ('grade_symbol', '=', record.grade_symbol),
                ('scale_id', '=', record.scale_id.id),
                ('id', '!=', record.id)])

            if lines:
                raise UserError(
                    _(f"{record.grade_symbol} already exists for {record.scale_id.name}."))

    @api.constrains('min_percent', 'max_percent')
    def check_min_max_percent(self):
        for record in self:
            if record.scale_id.gpa_calculation:
                if record.min_percent > record.max_percent:
                    raise ValidationError(
                        _("Min percent cannot be greater than the max percent."))
                scale_lines = self.search(
                    [('scale_id', '=', record.scale_id.id)], order='min_percent')
                if scale_lines[0].min_percent != 0.0:
                    raise ValidationError(
                        "Last Minimum Percentage should reach 0%")
                previous_max = None
                for line in scale_lines:
                    if previous_max:
                        if line.min_percent > previous_max + 0.01:
                            raise ValidationError(
                                _('There is some percentage gap.Please ensure there are no gaps to avoid any confusion.'))
                        if line.min_percent < previous_max + 0.01:
                            raise ValidationError(
                                _('There is some percentage overlap!Please make sure to remove overlaps if any.'))
                    previous_max = line.max_percent

    @api.constrains('min_percent', 'max_percent', 'conversion_percent')
    def check_min_max_conversion_percent(self):
        for record in self:
            if record.scale_id.gpa_calculation:
                if not (record.min_percent <= record.conversion_percent) or not (record.max_percent >= record.conversion_percent):
                    raise ValidationError(
                        _("Conversion percent should lie in between the max percent and the min percent."))

    @api.constrains('points')
    def check_points_greater_than_0(self):
        for record in self:
            if record.scale_id.gpa_calculation:
                if not record.points > 0:
                    raise ValidationError(
                        _("Points to be assigned should be greater than 0."))
