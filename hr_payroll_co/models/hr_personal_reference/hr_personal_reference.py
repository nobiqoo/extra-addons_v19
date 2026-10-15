from odoo import models, fields

class HrPersonalReference(models.Model):
    _name = 'hr.personal.reference'
    _description = 'Personal Reference'

    name = fields.Char('Full Name', required=True)
    reference_type = fields.Selection([
        ('work', 'Work'),
        ('family', 'Family'),
        ('other', 'Other'),
    ], string='Reference Type', required=True)
    relationship = fields.Char('Relationship', required=True)
    phone = fields.Char('Phone', required=True)
    employee_id = fields.Many2one('hr.employee', string='Employee')