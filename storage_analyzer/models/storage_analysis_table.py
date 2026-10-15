# -*- coding: utf-8 -*-
from odoo import models, fields, api


class StorageAnalysisTable(models.Model):
    _name = 'storage.analysis.table'
    _description = 'Detalle de Análisis por Tabla'
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
    
    # Información de la tabla
    table_name = fields.Char(
        string='Nombre de Tabla',
        required=True,
    )
    model_name = fields.Char(
        string='Modelo Técnico',
    )
    model_description = fields.Char(
        string='Descripción del Modelo',
    )
    
    # Estadísticas
    row_count = fields.Integer(
        string='Registros',
    )
    row_count_formatted = fields.Char(
        string='Registros (formato)',
        compute='_compute_row_count_formatted',
    )
    
    # Tamaños
    table_size = fields.Float(
        string='Datos (MB)',
        digits=(16, 2),
    )
    index_size = fields.Float(
        string='Índices (MB)',
        digits=(16, 2),
    )
    toast_size = fields.Float(
        string='TOAST (MB)',
        digits=(16, 2),
    )
    total_size = fields.Float(
        string='Total (MB)',
        digits=(16, 2),
    )
    
    # Porcentajes y estimaciones
    size_percentage = fields.Float(
        string='% del Total',
        digits=(5, 4),
    )
    
    # Categorización
    category = fields.Selection([
        ('system', 'Sistema'),
        ('data', 'Datos de Negocio'),
        ('mail', 'Mensajería'),
        ('attachment', 'Adjuntos'),
        ('log', 'Auditoría/Logs'),
        ('other', 'Otros'),
    ], string='Categoría', compute='_compute_category', store=True)
    
    @api.depends('row_count')
    def _compute_row_count_formatted(self):
        for line in self:
            count = line.row_count
            if count >= 1000000:
                line.row_count_formatted = f"{count/1000000:.2f}M"
            elif count >= 1000:
                line.row_count_formatted = f"{count/1000:.1f}K"
            else:
                line.row_count_formatted = str(count)
    
    @api.depends('table_name', 'model_name')
    def _compute_category(self):
        system_tables = ('ir_', 'res_', 'base_')
        mail_tables = ('mail_', 'message', 'discuss')
        attachment_tables = ('attachment', 'ir_attachment')
        log_tables = ('audit', 'log', 'tracking')
        
        for line in self:
            table = line.table_name.lower()
            model = (line.model_name or '').lower()
            
            if table.startswith(attachment_tables) or 'attachment' in table:
                line.category = 'attachment'
            elif table.startswith(mail_tables) or 'message' in table:
                line.category = 'mail'
            elif table.startswith(system_tables) and 'users' not in table:
                line.category = 'system'
            elif any(log in table for log in log_tables):
                line.category = 'log'
            else:
                line.category = 'data'
