# -*- coding: utf-8 -*-
import logging
from datetime import timedelta

from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class StorageAnalysisTrend(models.Model):
    _name = 'storage.analysis.trend'
    _description = 'Tendencia de Crecimiento de Almacenamiento'
    _order = 'analysis_date desc'
    _rec_name = 'analysis_date'
    
    ref_id = fields.Integer(
        string='ID de Referencia',
        copy=False,
        readonly=True,
        default=lambda self: self.id,
        aggregator='sum',
    )
    analysis_date = fields.Date(
        string='Fecha',
        required=True,
        index=True,
    )

    # Marca de la última tendencia registrada. Solo un registro tendra
    # is_latest = True en todo el modelo. El dashboard consume este flag
    # como filtro unico para mostrar siempre la ultima captura.
    is_latest = fields.Boolean(
        string='Última tendencia',
        default=False,
        index=True,
        readonly=True,
        copy=False,
        help='Marca interna que indica la última tendencia registrada.\n'
             'Solo un registro de storage.analysis.trend puede tener este campo activo.',
    )

    # Métricas
    database_size = fields.Float(
        string='Base de Datos (MB)',
        digits=(16, 2),
    )
    filestore_size = fields.Float(
        string='Filestore (MB)',
        digits=(16, 2),
    )
    total_size = fields.Float(
        string='Total (MB)',
        digits=(16, 2),
    )
    total_attachments = fields.Integer(
        string='Total Adjuntos',
    )
    
    # Cálculos
    daily_growth_rate = fields.Float(
        string='Tasa de Crecimiento Diario (MB)',
        compute='_compute_growth_rate',
        digits=(16, 2),
        store=True,
        aggregator='avg',
    )
    growth_percentage = fields.Float(
        string='% Crecimiento Diario',
        compute='_compute_growth_rate',
        digits=(5, 2),
        store=True,
        aggregator='avg',
    )
    projected_full_date = fields.Date(
        string='Fecha Proyectada de Llenado',
        compute='_compute_projected_date',
        store=True,
        aggregator='max',
    )
    
    @api.depends('total_size', 'analysis_date')
    def _compute_growth_rate(self):
        for trend in self:
            # Buscar el análisis anterior
            previous = self.search([
                ('analysis_date', '<', trend.analysis_date),
            ], order='analysis_date desc', limit=1)
            
            if previous:
                days_diff = (trend.analysis_date - previous.analysis_date).days
                if days_diff > 0:
                    size_diff = trend.total_size - previous.total_size
                    trend.daily_growth_rate = size_diff / days_diff
                    if previous.total_size > 0:
                        trend.growth_percentage = (size_diff / previous.total_size) * 100 / days_diff
                    else:
                        trend.growth_percentage = 0.0
                else:
                    trend.daily_growth_rate = 0.0
                    trend.growth_percentage = 0.0
            else:
                trend.daily_growth_rate = 0.0
                trend.growth_percentage = 0.0
    
    @api.depends('daily_growth_rate', 'total_size')
    def _compute_projected_date(self):
        params = self.env['ir.config_parameter'].sudo()
        limit_mb = float(params.get_param('storage_analyzer.storage_limit_mb', 0))
        
        for trend in self:
            if not limit_mb or trend.daily_growth_rate <= 0:
                trend.projected_full_date = False
                continue
            
            remaining = limit_mb - trend.total_size
            if remaining <= 0:
                trend.projected_full_date = fields.Date.today()
            else:
                days_until_full = remaining / trend.daily_growth_rate
                trend.projected_full_date = trend.analysis_date + timedelta(days=days_until_full)
    
    @api.model_create_multi
    def create(self, vals_list):
        res = super(StorageAnalysisTrend, self).create(vals_list)
        for record in res:
            record.ref_id = record.id
        try:
            res._recompute_trend_latest(sudo=True)
        except Exception as exc:  # pragma: no cover - defensivo
            _logger.warning('No se pudo recomputar is_latest de trend tras create: %s', exc)
        return res

    def write(self, vals):
        """Recompone is_latest cuando cambian claves que afectan al orden
        (analysis_date o asignacion directa de is_latest).
        """
        res = super(StorageAnalysisTrend, self).write(vals)
        if 'analysis_date' in vals or 'is_latest' in vals:
            try:
                self._recompute_trend_latest(sudo=True)
            except Exception as exc:  # pragma: no cover - defensivo
                _logger.warning('No se pudo recomputar is_latest de trend tras write: %s', exc)
        return res

    def unlink(self):
        latest_ids = self.filtered('is_latest')
        result = super(StorageAnalysisTrend, self).unlink()
        if latest_ids:
            try:
                next_latest = self.env['storage.analysis.trend'].sudo().search(
                    [],
                    order='analysis_date desc, id desc',
                    limit=1,
                )
                if next_latest:
                    next_latest.write({'is_latest': True})
            except Exception as exc:  # pragma: no cover - defensivo
                _logger.warning('No se pudo reasignar is_latest de trend tras unlink: %s', exc)
        return result

    def _recompute_trend_latest(self, sudo=False):
        """Garantiza que solo exista una tendencia con is_latest = True,
        eligiendo la mas reciente por ``analysis_date desc, id desc``.
        """
        if self.env.context.get('_storage_trend_recompute_guard'):
            return True
        Model = self.sudo() if sudo else self
        ctx = dict(self.env.context, _storage_trend_recompute_guard=True)
        Model = Model.with_context(ctx)
        latest = Model.search([], order='analysis_date desc, id desc', limit=1)
        currently_marked = Model.search([('is_latest', '=', True)])
        to_unmark = currently_marked - latest
        try:
            if to_unmark:
                to_unmark.write({'is_latest': False})
            if latest and latest not in currently_marked:
                latest.write({'is_latest': True})
        except Exception as exc:  # pragma: no cover - defensivo
            _logger.warning('No se pudo actualizar is_latest de trend: %s', exc)
        return True

    @api.model
    def get_trend_data(self, days=30):
        """Retorna datos de tendencia para gráficos."""
        date_limit = fields.Date.today() - timedelta(days=days)
        
        trends = self.search([
            ('analysis_date', '>=', date_limit),
        ], order='analysis_date asc')
        
        return [{
            'date': t.analysis_date.isoformat(),
            'database_size': t.database_size,
            'filestore_size': t.filestore_size,
            'total_size': t.total_size,
            'daily_growth': t.daily_growth_rate,
        } for t in trends]
