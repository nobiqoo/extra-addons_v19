# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models

class ApprovalQualityApprover(models.Model):
    """ Intermediate model between approval.quality and res.users
        To know whether an approver for this quality is required or not
    """
    _name = 'approval.quality.approver'
    _description = 'Approval Type Approver'
    _rec_name = 'user_id'
    _order = 'sequence'

    sequence = fields.Integer('Sequence', default=10)
    quality_point_id = fields.Many2one('quality.point', string='Approval Type', ondelete='cascade', required=True)
    company_id = fields.Many2one('res.company', related='quality_point_id.company_id')
    user_id = fields.Many2one('res.users', string='User', ondelete='cascade', required=True,
        check_company=True, domain="[('company_ids', 'in', company_id), ('id', 'not in', existing_user_ids)]")
    required = fields.Boolean(default=False)
    approval_role = fields.Selection([
        ('technical_manager', 'Technical Manager'),
        ('warehouse_manager', 'Warehouse Manager'),
        ('importations_manager', 'Importations Manager'),
        ('refurbishment_responsible', 'Refurbishment Responsible'),
        ('importations_analyst', 'Importations Analyst'),
        ('warehouse_auxiliary', 'Warehouse Auxiliary'),
        ('checklist_responsible', 'Checklist Responsible'),
    ])
    signature = fields.Binary('Signature')
    approval_role_id = fields.Many2one(
        'approval.role', string='Rol de Aprobador')

    existing_user_ids = fields.Many2many('res.users', compute='_compute_existing_user_ids')

    @api.depends('quality_point_id')
    def _compute_existing_user_ids(self):
        for record in self:
            record.existing_user_ids = record.quality_point_id.approver_ids.user_id