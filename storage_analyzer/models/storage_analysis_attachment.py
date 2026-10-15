# -*- coding: utf-8 -*-
from odoo import models, fields, api


class StorageAnalysisAttachment(models.Model):
    _name = 'storage.analysis.attachment'
    _description = 'Detalle de Adjuntos en Análisis'
    _order = 'file_size desc'
    
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
    
    # Referencia al adjunto original
    attachment_id = fields.Many2one(
        'ir.attachment',
        string='Adjunto Original',
    )
    
    # Información del archivo
    name = fields.Char(
        string='Nombre',
    )
    file_size = fields.Float(
        string='Tamaño (MB)',
        digits=(16, 2),
    )
    storage_type = fields.Selection([
        ('db', 'Base de Datos'),
        ('filestore', 'Filestore'),
    ], string='Tipo de Almacenamiento')
    
    # Contexto
    res_model = fields.Char(
        string='Modelo Relacionado',
    )
    res_id = fields.Integer(
        string='ID Relacionado',
    )
    mimetype = fields.Char(
        string='Tipo MIME',
    )
    create_date = fields.Datetime(
        string='Fecha de Creación',
    )
    
    # Categorización por tipo
    file_category = fields.Selection([
        ('document', 'Documento'),
        ('image', 'Imagen'),
        ('spreadsheet', 'Hoja de Cálculo'),
        ('pdf', 'PDF'),
        ('archive', 'Archivo Comprimido'),
        ('other', 'Otros'),
    ], string='Categoría', compute='_compute_file_category', store=True)
    
    @api.depends('mimetype', 'name')
    def _compute_file_category(self):
        for line in self:
            mimetype = (line.mimetype or '').lower()
            name = (line.name or '').lower()
            
            if 'pdf' in mimetype or name.endswith('.pdf'):
                line.file_category = 'pdf'
            elif 'image' in mimetype or any(name.endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']):
                line.file_category = 'image'
            elif 'spreadsheet' in mimetype or 'excel' in mimetype or any(name.endswith(ext) for ext in ['.xls', '.xlsx', '.csv']):
                line.file_category = 'spreadsheet'
            elif 'word' in mimetype or 'document' in mimetype or any(name.endswith(ext) for ext in ['.doc', '.docx', '.odt', '.txt', '.rtf']):
                line.file_category = 'document'
            elif 'zip' in mimetype or 'compressed' in mimetype or any(name.endswith(ext) for ext in ['.zip', '.rar', '.7z', '.tar', '.gz']):
                line.file_category = 'archive'
            else:
                line.file_category = 'other'
    
    def action_open_attachment(self):
        """Abre el adjunto original."""
        self.ensure_one()
        if self.attachment_id:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'ir.attachment',
                'res_id': self.attachment_id.id,
                'view_mode': 'form',
                'target': 'current',
            }
        return False
    
    def action_open_record(self):
        """Abre el registro relacionado."""
        self.ensure_one()
        if self.res_model and self.res_id:
            return {
                'type': 'ir.actions.act_window',
                'res_model': self.res_model,
                'res_id': self.res_id,
                'view_mode': 'form',
                'target': 'current',
            }
        return False
