from odoo import models, fields

class MedicalExamType(models.Model):
    _name = 'medical.exam.type'
    _description = 'Medical Exam Type'

    name = fields.Char(string="Type of Examination", required=True)