from odoo import fields, models


class DeliveryCarrierMaster(models.Model):
    _name = 'delivery.carrier.master'
    _description = 'Maestro de Empresas de Envio'
    _rec_name = 'name'

    name = fields.Char(string='Nombre de la Empresa de Envio', required=True)
    active = fields.Boolean(string='Activo', default=True)
