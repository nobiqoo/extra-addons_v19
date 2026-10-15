from odoo import models, fields, api
from odoo.exceptions import ValidationError


class HrFamilyInformation(models.Model):
    _name = 'hr.family.information'
    _description = 'Family Information'

    
    name = fields.Char(string='Name', required=True)
    l10n_latam_identification_type_id = fields.Many2one(
        'l10n_latam.identification.type',
        string="Tipo de Documento")
    document_type = fields.Selection([
        ('cc', 'Citizen ID'),
        ('ti', 'Identity Card'),
        ('passport', 'Passport'),
    ], string='Document Type', required=False)
    document_number = fields.Char(string='Document Number', required=True)
    relationship = fields.Selection([
        ('father', 'Father'),
        ('mother', 'Mother'),
        ('child', 'Child'),
        ('grandparent', 'Grandparent'),
        ('spouse', 'Spouse'),
        ('nephew','Nephew'),
        ('stepchild','Stepchild'),
    ], string='Relationship', required=True)
    birth_date = fields.Date(string='Date of Birth', required=True)
    dependency_status = fields.Selection([
        ('dependent', 'Dependent'),
        ('independent', 'Independent'),
    ], string='Dependency Status', required=True)
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True)
    is_in_certified = fields.Boolean(string='Se incluye en certificado')

    @api.constrains('is_in_certified')
    def _check_is_in_certified(self):
        for record in self:
            if record.is_in_certified:
                o_record = self.env['hr.family.information'].search([
                    ('id', '!=', record.id),
                    ('is_in_certified', '=', True),
                    ('employee_id', '=', record.employee_id.id)
                ])
                if o_record:
                    raise ValidationError(
                        f'Solo se puede marcar un familiar para el certificado')
