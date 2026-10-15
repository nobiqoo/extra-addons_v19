# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'
    
    storage_limit_mb = fields.Float(
        string='Límite de Almacenamiento (MB)',
        config_parameter='storage_analyzer.storage_limit_mb',
        help='Límite de almacenamiento contratado en MB. 0 = Sin límite.',
    )
    storage_limit_gb = fields.Float(
        string='Límite de Almacenamiento (GB)',
        compute='_compute_storage_limit_gb',
        inverse='_inverse_storage_limit_gb',
    )
    threshold_warning = fields.Float(
        string='Umbral de Advertencia (%)',
        config_parameter='storage_analyzer.threshold_warning',
        default=70.0,
        help='Porcentaje del límite para lanzar advertencias.',
    )
    threshold_critical = fields.Float(
        string='Umbral Crítico (%)',
        config_parameter='storage_analyzer.threshold_critical',
        default=85.0,
        help='Porcentaje del límite para lanzar alertas críticas.',
    )
    retention_days = fields.Integer(
        string='Días de Retención',
        config_parameter='storage_analyzer.retention_days',
        default=90,
        help='Número de días para mantener análisis históricos.',
    )
    enable_auto_analysis = fields.Boolean(
        string='Análisis Automático Diario',
        config_parameter='storage_analyzer.enable_auto_analysis',
        default=True,
    )
    enable_alert_email = fields.Boolean(
        string='Enviar correo de alerta',
        config_parameter='storage_analyzer.enable_alert_email',
        default=True,
    )
    alert_email_recipient_ids = fields.Many2many(
        'res.partner',
        string='Destinatarios de alertas',
        help='Contactos que recibirán los correos de alerta de almacenamiento. '
             'Si no se selecciona ninguno, se notificará a los administradores.',
    )
    
    @api.depends('storage_limit_mb')
    def _compute_storage_limit_gb(self):
        for settings in self:
            settings.storage_limit_gb = settings.storage_limit_mb / 1024.0
    
    def _inverse_storage_limit_gb(self):
        for settings in self:
            settings.storage_limit_mb = settings.storage_limit_gb * 1024.0
    
    @api.constrains('threshold_warning', 'threshold_critical')
    def _check_thresholds(self):
        for settings in self:
            if settings.threshold_warning >= settings.threshold_critical:
                raise ValidationError(
                    'El umbral de advertencia debe ser menor que el umbral crítico.'
                )
    
    def action_run_storage_analysis(self):
        """Ejecuta un análisis manual desde configuración."""
        analysis = self.env['storage.analysis'].create({
            'analysis_date': fields.Datetime.now(),
        })
        analysis.run_analysis()
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'storage.analysis',
            'res_id': analysis.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    def get_values(self):
        res = super().get_values()
        params = self.env['ir.config_parameter'].sudo()
        recipients = params.get_param('storage_analyzer.alert_email_recipient_ids', '')
        if recipients:
            ids = [int(x) for x in recipients.split(',') if x.strip().isdigit()]
        else:
            ids = []
        res.update({
            'alert_email_recipient_ids': [(6, 0, ids)],
        })
        return res

    def set_values(self):
        super().set_values()
        params = self.env['ir.config_parameter'].sudo()
        ids = self.alert_email_recipient_ids.ids
        params.set_param('storage_analyzer.alert_email_recipient_ids', ','.join(map(str, ids)) if ids else '')
