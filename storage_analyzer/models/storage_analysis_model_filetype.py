# -*- coding: utf-8 -*-
from odoo import models, fields, api

class StorageAnalysisModelFiletype(models.Model):
    _name = 'storage.analysis.model.filetype'
    _description = 'Detalle de Almacenamiento por Modelo y Tipo de Archivo'
    _order = 'total_size desc'

    analysis_id = fields.Many2one(
        'storage.analysis',
        string='Análisis',
        required=True,
        ondelete='cascade',
    )
    is_latest = fields.Boolean(
        string='Último Análisis',
        related='analysis_id.is_latest',
        store=True,
    )
    analysis_date = fields.Datetime(
        related='analysis_id.analysis_date',
        store=True,
    )
    
    # Contexto y detalles de modelo
    res_model = fields.Char(
        string='Modelo Técnico',
        index=True,
    )
    model_description = fields.Char(
        string='Descripción del Modelo',
    )
    
    # Detalle de archivos
    attach_file_type = fields.Char(
        string='Tipo de Archivo',
        index=True,
    )
    file_type = fields.Char(
        string='Categoría Archivo',
        index=True,
    )
    total_size = fields.Float(
        string='Tamaño Total (MB)',
        digits=(16, 2),
    )
    attachment_count = fields.Integer(
        string='Cantidad de Adjuntos',
    )

    def action_open_attachment(self):
        """Abre los adjuntos relacionados."""
        self.ensure_one()
        if self.res_model and self.attach_file_type:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'ir.attachment',
                'domain': [
                    ('res_model', '=', self.res_model),
                    ('mimetype', '=', self.attach_file_type),
                ],
                'view_mode': 'tree,form',
                'target': 'current',
            }
        return False
