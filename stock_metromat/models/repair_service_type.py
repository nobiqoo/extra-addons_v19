from odoo import fields, models


class RepairServiceType(models.Model):
    _name = 'repair.service.type'
    _description = 'Tipo de servicio de la orden de trabajo'
    _order = 'sequence, id'

    name = fields.Char(
        string='Nombre',
        required=True,
    )
    sequence = fields.Integer(
        string='Secuencia',
        default=10,
    )
    active = fields.Boolean(
        string='Activo',
        default=True,
    )

    _name_uniq = models.Constraint(
        'unique (name)',
        'Ya existe un tipo de servicio con este nombre.',
    )
