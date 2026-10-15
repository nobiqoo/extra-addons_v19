# -*- coding: utf-8 -*-

from odoo import fields, models, _
from odoo.exceptions import UserError


class QualityCheckApprover(models.Model):
    _name = 'quality.check.approver'
    _description = 'Quality Check Approver'
    _order = 'sequence, id'

    sequence = fields.Integer('Sequence', default=10)
    check_id = fields.Many2one(
        'quality.check', string='Quality Check', required=True, ondelete='cascade')
    user_id = fields.Many2one('res.users', string='Approver', required=True)
    required = fields.Boolean('Required', default=False)
    status = fields.Selection([
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('refused', 'Refused')
    ], string='Status', default='pending')
    approval_date = fields.Datetime('Approval Date')
    company_id = fields.Many2one(
        'res.company', related='check_id.company_id', store=True, readonly=True)

    approver_sequence = fields.Boolean(
        related='check_id.approver_sequence', store=True, readonly=True)
    approval_role = fields.Selection([
        ('technical_manager', 'Technical Manager'),
        ('warehouse_manager', 'Warehouse Manager'),
        ('importations_manager', 'Importations Manager'),
        ('refurbishment_responsible', 'Refurbishment Responsible'),
        ('importations_analyst', 'Importations Analyst'),
        ('warehouse_auxiliary', 'Warehouse Auxiliary'),
        ('checklist_responsible', 'Checklist Responsible'),
    ], string='Approval Role')
    signature = fields.Binary('Signature')
    approval_role_id = fields.Many2one(
        'approval.role', string='Rol de Aprobador')

    def action_approve(self):
        for approver in self:
            if approver.user_id != self.env.user:
                raise UserError(_('Only the assigned approver can approve.'))
            if approver.status != 'pending':
                raise UserError(_('This approval has already been processed.'))

            if approver.approver_sequence:
                previous_approvers = approver.check_id.approver_ids.filtered(
                    lambda a: a.sequence < approver.sequence and a.status != 'approved')
                if previous_approvers:
                    raise UserError(
                        _('You must wait for previous approvers in the sequence.'))
            approver.write({
                'status': 'approved',
                'approval_date': fields.Datetime.now(),
            })
            if approver.user_id not in approver.check_id.approver_user_ids:
                approver.check_id.approver_user_ids = [
                    (4, approver.user_id.id)]

            approver._mark_activity_done()
            if approver.approver_sequence:
                approver._notify_next_approver()

            approver.check_id._check_approval_status()

    def action_refuse(self):
        for approver in self:
            if approver.user_id != self.env.user:
                raise UserError(_('Only the assigned approver can refuse.'))
            if approver.status != 'pending':
                raise UserError(_('This approval has already been processed.'))
            approver.write({
                'status': 'refused',
                'approval_date': fields.Datetime.now(),
            })

            approver._mark_activity_done()
            approver.check_id.write({'quality_state': 'fail'})

    def _mark_activity_done(self):
        """Marcar como completada la actividad del aprobador"""
        self.ensure_one()

        activities = self.env['mail.activity'].search([
            ('res_id', '=', self.check_id.id),
            ('res_model', '=', 'quality.check'),
            ('user_id', '=', self.user_id.id),
        ])

        for activity in activities:
            activity.action_done()

    def _notify_next_approver(self):
        """Notificar al siguiente aprobador en la secuencia"""
        self.ensure_one()

        next_approver = self.check_id.approver_ids.filtered(
            lambda a: a.status == 'pending' and a.sequence > self.sequence
        ).sorted('sequence')

        if next_approver:
            activity_type = self.env.ref(
                'mail.mail_activity_data_todo', raise_if_not_found=False)
            if not activity_type:
                activity_type = self.env['mail.activity.type'].search(
                    [('category', '=', 'default')], limit=1)

            self.check_id._create_activity_for_approver(
                next_approver[0], activity_type)
