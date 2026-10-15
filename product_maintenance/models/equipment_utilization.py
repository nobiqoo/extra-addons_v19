from odoo import models, fields

class EquipmentUtilization(models.Model):
    _name = 'equipment.utilization'
    _description = 'Utilización de Equipos'

    name = fields.Char('Tipo de Utilización', required=True)
