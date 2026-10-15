from odoo import models, fields

class MaintenanceActivity(models.Model):
    _name = 'maintenance.activity'
    _description = 'Actividad de Mantenimiento'

    name = fields.Char('Nombre', required=True)
    description = fields.Text('Descripción')
    average_time = fields.Float('Tiempo Promedio (hrs)')
