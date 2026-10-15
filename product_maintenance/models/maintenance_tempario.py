from odoo import models, fields, api

class MaintenanceTempario(models.Model):
    _name = 'maintenance.tempario'
    _description = 'Tempario de Mantenimiento'
    _rec_name = 'name'

    name = fields.Char(string='Nombre', required=True)
    product_maintenance_id = fields.Many2one(
        comodel_name='product.maintenance',
        string='Producto de Mantenimiento (legacy)',
        help='Campo histórico. La aplicación real del tempario se hace por Modelos.',
    )

    utilization_type = fields.Selection([
        ('km', 'Kilómetros'),
        ('hour', 'Horómetro')
    ], string='Utilización')

    daily_use  = fields.Float('Utilización Diaria')
    frequency  = fields.Float('Frecuencia de Mantenimiento', required=True,
                              help="Distancia/horas entre mantenimientos.")

    activity_ids   = fields.One2many('maintenance.tempario.activity', 'tempario_id', string='Actividades')
    spare_part_ids = fields.One2many('maintenance.tempario.sparepart', 'tempario_id', string='Repuestos')
    model_ids      = fields.One2many('maintenance.tempario.model', 'tempario_id', string='Modelos')

class MaintenanceTemparioActivity(models.Model):
    _name = 'maintenance.tempario.activity'
    _description = 'Actividad del Tempario'

    tempario_id = fields.Many2one('maintenance.tempario', string='Tempario', required=True, ondelete='cascade')
    activity_id = fields.Many2one('maintenance.activity', string='Actividad', required=True)


class MaintenanceTemparioSparePart(models.Model):
    _name = 'maintenance.tempario.sparepart'
    _description = 'Repuesto del Tempario'

    tempario_id = fields.Many2one('maintenance.tempario', string='Tempario', required=True, ondelete='cascade')
    spare_part_id = fields.Many2one('product.template', string='Repuesto', required=True, domain="[('is_spare_part', '=', True)]")


class MaintenanceTemparioModel(models.Model):
    _name = 'maintenance.tempario.model'
    _description = 'Modelo del Tempario'

    tempario_id = fields.Many2one('maintenance.tempario', string='Tempario', required=True, ondelete='cascade', index=True)
    model_id    = fields.Many2one('product.model', string='Modelo', required=True, index=True)
