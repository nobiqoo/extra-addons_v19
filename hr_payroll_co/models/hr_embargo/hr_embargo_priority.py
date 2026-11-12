# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class HrEmbargoPriority(models.Model):
    _name = 'hr.embargo.priority'
    _description = 'Garnishment Priority Override'
    _order = 'contract_id'

    # Not required=True: it is a computed stored field, and the client never sends its value
    # on create() (it has no inverse), so the ORM's initial INSERT would violate a NOT NULL
    # constraint before the compute has a chance to run. Enforced instead via _check_contract_id.
    contract_id = fields.Many2one(
        comodel_name='hr.contract', string='Contract', domain="[('state', '=', 'open')]",
        compute='_compute_contract_id', store=True)
    employee_id = fields.Many2one(
        comodel_name='hr.employee', string='Employee')
    company_id = fields.Many2one(
        comodel_name='res.company', string='Company', default=lambda self: self.env.company)
    line_ids = fields.One2many(
        comodel_name='hr.embargo.priority.line', inverse_name='priority_id',
        string='Priority Lines')

    _contract_id_uniq = models.Constraint(
        'UNIQUE (contract_id)',
        'A contract can only have one priority configuration.',
    )

    @api.depends('employee_id')
    def _compute_contract_id(self):
        for record in self:
            record.contract_id = record.employee_id.contract_ids.filtered(
                lambda l: l.state == 'open')[:1]

    @api.constrains('contract_id')
    def _check_contract_id(self):
        for record in self:
            if not record.contract_id:
                raise ValidationError(_(
                    "Select an employee with an open contract to configure their garnishment "
                    "priority."))

    def get_priority(self, embargo_type):
        self.ensure_one()
        line = self.line_ids.filtered(lambda l: l.embargo_type_id.id == embargo_type.id)
        return line[0].priority if line else embargo_type.priority


class HrEmbargoPriorityLine(models.Model):
    _name = 'hr.embargo.priority.line'
    _description = 'Garnishment Priority Line'
    _order = 'priority'

    priority_id = fields.Many2one(
        comodel_name='hr.embargo.priority', string='Priority Configuration', required=True,
        ondelete='cascade')
    embargo_type_id = fields.Many2one(
        comodel_name='hr.embargo.type', string='Garnishment Type', required=True)
    priority = fields.Integer(string='Priority', required=True, default=1)

    _priority_id_embargo_type_id_uniq = models.Constraint(
        'UNIQUE (priority_id, embargo_type_id)',
        'This garnishment type is already configured for this contract.',
    )
