# -*- coding: utf-8 -*-
from odoo import fields, models, api, _

class BiometricDeviceCommand(models.Model):
    _name = 'biometric.device.command'
    _description = 'Comando ADMS para Biométrico'
    _order = 'id desc'

    device_id = fields.Many2one(
        'biometric.device.details',
        string='Dispositivo',
        required=True,
        ondelete='cascade',
        index=True
    )
    command = fields.Char(string='Comando', required=True)
    state = fields.Selection([
        ('draft', 'Pendiente'),
        ('sent', 'Enviado'),
        ('done', 'Ejecutado con Éxito'),
        ('error', 'Error')
    ], string='Estado', default='draft', index=True)
    return_code = fields.Char(string='Código de Retorno')
    sent_at = fields.Datetime(string='Fecha Envío')
    executed_at = fields.Datetime(string='Fecha Ejecución')
