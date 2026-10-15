# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models, fields, _
from odoo.exceptions import ValidationError


class QualityPoint(models.Model):
    _inherit = 'quality.point'

    sequence = fields.Integer(string="Sequence")
    user_ids = fields.Many2many(
        'res.users', compute='_compute_user_ids', string="Approver Users")
    approver_ids = fields.One2many(
        'approval.quality.approver', 'quality_point_id', string='Approvers')
    approval_minimum = fields.Integer(
        string="Minimum Approval", default="1", required=True)
    invalid_minimum = fields.Boolean(compute='_compute_invalid_minimum')
    invalid_minimum_warning = fields.Char(compute='_compute_invalid_minimum')
    approver_sequence = fields.Boolean(
        'Approvers Sequence?', help="If checked, the approvers have to approve in sequence (one after the other). If Employee's Manager is selected as approver, they will be the first in line.")

    @api.depends_context('lang')
    @api.depends('approval_minimum', 'approver_ids')
    def _compute_invalid_minimum(self):
        for record in self:
            if record.approval_minimum > len(record.approver_ids):
                record.invalid_minimum = True
            else:
                record.invalid_minimum = False
            record.invalid_minimum_warning = record.invalid_minimum and _(
                'Your minimum approval exceeds the total of default approvers.')

    @api.depends('approver_ids')
    def _compute_user_ids(self):
        for record in self:
            record.user_ids = record.approver_ids.user_id

    @api.constrains('approval_minimum', 'approver_ids')
    def _constrains_approval_minimum(self):
        for record in self:
            if record.approval_minimum < len(record.approver_ids.filtered('required')):
                raise ValidationError(
                    _('Minimum Approval must be equal or superior to the sum of required Approvers.'))

    @api.constrains('approver_ids')
    def _constrains_approver_ids(self):
        # There seems to be a problem with how the database is updated which doesn't let use to an sql constraint for this
        # Issue is: records seem to be created before others are saved, meaning that if you originally have only user a
        #  change user a to user b and add a new line with user a, the second line will be created and will trigger the constraint
        #  before the first line will be updated which wouldn't trigger a ValidationError
        for record in self:
            if len(record.approver_ids) != len(record.approver_ids.user_id):
                raise ValidationError(
                    _('An user may not be in the approver list multiple times.'))

    @api.constrains('approver_sequence', 'approval_minimum')
    def _constrains_approver_sequence(self):
        if any(a.approver_sequence and not a.approval_minimum for a in self):
            raise ValidationError(
                _('Approver Sequence can only be activated with at least 1 minimum approver.'))
