# -*- coding: utf-8 -*-
import os
import logging
from datetime import datetime, timedelta

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools import config

_logger = logging.getLogger(__name__)


class StorageAnalysis(models.Model):
    _name = 'storage.analysis'
    _description = 'Análisis de Almacenamiento'
    _order = 'analysis_date desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Nombre',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('Nuevo'),
    )
    ref_id = fields.Integer(
        string='ID de Referencia',
        copy=False,
        readonly=True,
        aggregator='sum',
    )
    analysis_date = fields.Datetime(
        string='Fecha de Análisis',
        default=fields.Datetime.now,
        readonly=True,
        tracking=True,
        aggregator='max',
    )
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('running', 'En Ejecución'),
        ('done', 'Completado'),
        ('error', 'Error'),
    ], string='Estado', default='draft', readonly=True, tracking=True)
    
    # Totales de almacenamiento
    database_size = fields.Float(
        string='Tamaño Base de Datos (MB)',
        readonly=True,
        digits=(16, 2),
    )
    filestore_size = fields.Float(
        string='Tamaño Filestore (MB)',
        readonly=True,
        digits=(16, 2),
    )
    total_size = fields.Float(
        string='Tamaño Total (MB)',
        compute='_compute_total_size',
        store=True,
        digits=(16, 2),
    )
    total_size_gb = fields.Float(
        string='Tamaño Total (GB)',
        compute='_compute_total_size_gb',
        store=True,
        digits=(16, 2),
    )
    
    # Adjuntos
    total_attachments = fields.Integer(
        string='Total de Adjuntos',
        readonly=True,
    )
    attachments_store_size = fields.Float(
        string='Adjuntos en Filestore (MB)',
        readonly=True,
        digits=(16, 2),
    )
    attachments_db_size = fields.Float(
        string='Adjuntos en BD (MB)',
        readonly=True,
        digits=(16, 2),
    )
    
    # Tablas
    table_count = fields.Integer(
        string='Tablas Analizadas',
        readonly=True,
    )
    
    # Líneas de detalle
    table_line_ids = fields.One2many(
        'storage.analysis.table',
        'analysis_id',
        string='Detalle por Tabla',
        readonly=True,
    )
    attachment_line_ids = fields.One2many(
        'storage.analysis.attachment',
        'analysis_id',
        string='Detalle de Adjuntos',
        readonly=True,
    )
    model_filetype_line_ids = fields.One2many(
        'storage.analysis.model.filetype',
        'analysis_id',
        string='Detalle por Modelo y Tipo',
        readonly=True,
    )
    
    # Notas
    note = fields.Text(
        string='Notas',
    )
    
    # Cálculos de alerta
    usage_percentage = fields.Float(
        string='Porcentaje de Uso',
        compute='_compute_usage_percentage',
        digits=(5, 2),
    )
    alert_level = fields.Selection([
        ('normal', 'Normal'),
        ('warning', 'Advertencia'),
        ('critical', 'Crítico'),
    ], string='Nivel de Alerta', compute='_compute_alert_level')

    # Marca del último análisis. Solo un registro tendra is_latest = True en
    # todo el modelo. El dashboard consume este flag como filtro unico para
    # mostrar siempre el analisis mas reciente sin depender de order-by en
    # los pivotes.
    is_latest = fields.Boolean(
        string='Último análisis',
        default=False,
        index=True,
        readonly=True,
        copy=False,
        help='Marca interna que indica el último análisis registrado.\n'
             'Solo un registro de storage.analysis puede tener este campo activo.',
    )

    @api.depends('database_size', 'filestore_size')
    def _compute_total_size(self):
        for analysis in self:
            analysis.total_size = analysis.database_size + analysis.filestore_size
    
    @api.depends('total_size')
    def _compute_total_size_gb(self):
        for analysis in self:
            analysis.total_size_gb = analysis.total_size / 1024.0
    
    def _compute_usage_percentage(self):
        params = self.env['ir.config_parameter'].sudo()
        limit_mb = float(params.get_param('storage_analyzer.storage_limit_mb', 0))
        for analysis in self:
            if limit_mb > 0:
                analysis.usage_percentage = (analysis.total_size / limit_mb) * 100
            else:
                analysis.usage_percentage = 0.0
    
    def _compute_alert_level(self):
        params = self.env['ir.config_parameter'].sudo()
        warning_pct = float(params.get_param('storage_analyzer.threshold_warning', 70))
        critical_pct = float(params.get_param('storage_analyzer.threshold_critical', 85))
        for analysis in self:
            if analysis.usage_percentage >= critical_pct:
                analysis.alert_level = 'critical'
            elif analysis.usage_percentage >= warning_pct:
                analysis.alert_level = 'warning'
            else:
                analysis.alert_level = 'normal'
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('Nuevo')) == _('Nuevo'):
                vals['name'] = self.env['ir.sequence'].next_by_code('storage.analysis') or _('Nuevo')
        res = super(StorageAnalysis, self).create(vals_list)
        for record in res:
            record.ref_id = record.id
        # Mantener un único is_latest = True tras cada creación.
        # El nuevo registro siempre sera el ultimo, asi que se asegura la marca
        # sin necesidad de recalcular toda la tabla; los registros previos
        # permanecen con su estado actual y se desmarcaran explicitamente
        # con el helper para evitar duplicar la marca.
        try:
            res._recompute_latest(sudo=True)
        except Exception as exc:  # pragma: no cover - defensivo
            _logger.warning('No se pudo recomputar is_latest tras create: %s', exc)
        return res

    def write(self, vals):
        """Sobrescribe write para recomputar is_latest cuando cambian las
        claves que afectan al orden (analysis_date o asignacion directa de
        is_latest). Garantiza que solo exista un registro marcado.
        """
        res = super(StorageAnalysis, self).write(vals)
        if 'analysis_date' in vals or 'is_latest' in vals:
            try:
                self._recompute_latest(sudo=True)
            except Exception as exc:  # pragma: no cover - defensivo
                _logger.warning('No se pudo recomputar is_latest tras write: %s', exc)
        return res

    def unlink(self):
        """Sobrescribe unlink para reasignar is_latest si se elimina el
        registro marcado como ultimo.
        """
        latest_ids = self.filtered('is_latest')
        result = super(StorageAnalysis, self).unlink()
        if latest_ids:
            try:
                # Reasignar al siguiente mas reciente segun el orden canonico.
                next_latest = self.env['storage.analysis'].sudo().search(
                    [],
                    order='analysis_date desc, id desc',
                    limit=1,
                )
                if next_latest:
                    # Pasar por write evita disparadores circulares innecesarios.
                    next_latest.write({'is_latest': True})
            except Exception as exc:  # pragma: no cover - defensivo
                _logger.warning('No se pudo reasignar is_latest tras unlink: %s', exc)
        return result

    def _recompute_latest(self, sudo=False):
        """Asegura que solo exista un registro con is_latest = True, siendo
        ese el mas reciente segun ``analysis_date desc, id desc``.

        Este metodo se invoca desde create/write para mantener consistencia.
        Se ejecuta con ``sudo=True`` para que la marca no dependa de los
        permisos del usuario que ejecuta el analisis (los analisis son
        administrados por usuarios tecnicos y la marca es interna).

        Dispone de un flag de re-entrada para evitar bucles cuando los
        writes disparados por este mismo metodo (sobre ``is_latest``)
        vuelven a invocar ``write`` -> ``_recompute_latest``.
        """
        if self.env.context.get('_storage_analysis_recompute_guard'):
            return True
        Model = self.sudo() if sudo else self
        ctx = dict(self.env.context, _storage_analysis_recompute_guard=True)
        Model = Model.with_context(ctx)
        # 1) Localizar el candidato a "ultimo" segun el orden canonico.
        latest = Model.search([], order='analysis_date desc, id desc', limit=1)
        # 2) Buscar cualquier registro que actualmente ostente la marca y
        #    no coincida con el ultimo canonico. Tambien se incluyen los
        #    candidatos a marcar para evitar dos writes separados.
        currently_marked = Model.search([('is_latest', '=', True)])
        to_unmark = currently_marked - latest
        to_mark = latest - currently_marked
        if to_unmark:
            to_unmark.write({'is_latest': False})
        if to_mark:
            to_mark.write({'is_latest': True})
        return True

    def action_draft(self):
        self.write({'state': 'draft'})
    
    def action_run(self):
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_('Solo se puede ejecutar análisis en estado borrador.'))
        self.run_analysis()
        return True
    
    def action_cancel(self):
        self.write({'state': 'draft'})
    
    # ============================================================
    # MÉTODOS DE RECOLECCIÓN DE MÉTRICAS
    # ============================================================
    
    def _get_database_size(self):
        """Obtiene el tamaño total de la base de datos en MB."""
        self.env.cr.execute("""
            SELECT pg_database_size(current_database()) / 1024.0 / 1024.0
        """)
        result = self.env.cr.fetchone()
        return result[0] if result else 0.0
    
    def _get_filestore_size(self):
        """Calcula el tamaño del directorio filestore en MB."""
        filestore_path = os.path.join(
            config['data_dir'],
            'filestore',
            self.env.cr.dbname
        )
        
        total_size = 0
        if os.path.exists(filestore_path):
            try:
                for dirpath, dirnames, filenames in os.walk(filestore_path):
                    for filename in filenames:
                        filepath = os.path.join(dirpath, filename)
                        if os.path.isfile(filepath):
                            total_size += os.path.getsize(filepath)
            except (OSError, IOError) as e:
                _logger.warning('Error al calcular tamaño de filestore: %s', str(e))
        
        return total_size / 1024.0 / 1024.0
    
    def _analyze_tables(self):
        """Analiza todas las tablas de la base de datos.

        Utiliza ``to_regclass()`` para filtrar únicamente relaciones que
        realmente existen.  ``pg_tables`` puede contener entradas que ya
        no son resolubles (p.ej. tablas temporales de otras sesiones o
        catálogo inconsistente), lo que provocaría errores en las
        funciones ``pg_*_size``.
        """
        self.env.cr.execute("""
            SELECT 
                schemaname,
                tablename,
                pg_total_relation_size(schemaname||'.'||tablename) / 1024.0 / 1024.0 as total_size,
                pg_relation_size(schemaname||'.'||tablename) / 1024.0 / 1024.0 as table_size,
                pg_indexes_size(schemaname||'.'||tablename) / 1024.0 / 1024.0 as index_size,
                COALESCE(pg_total_relation_size(schemaname||'.'||tablename) - 
                         pg_relation_size(schemaname||'.'||tablename) - 
                         pg_indexes_size(schemaname||'.'||tablename), 0) / 1024.0 / 1024.0 as toast_size
            FROM pg_tables
            WHERE schemaname = 'public'
              AND to_regclass(schemaname||'.'||tablename) IS NOT NULL
            ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
            LIMIT 20
        """)
        return self.env.cr.fetchall()
    
    def _get_model_counts(self):
        """Obtiene el conteo de registros por modelo/tabla de forma optimizada sin realizar COUNT(*) lentos en tablas gigantes."""
        counts = {}
        table_models = {}
        
        # Mapear tablas a modelos
        for model_name in self.env.registry:
            try:
                model = self.env[model_name]
                if hasattr(model, '_table') and model._table:
                    table_models[model._table] = (model_name, model._description or model_name)
            except Exception:
                continue
        
        # Obtener estimaciones de todas las tablas de PostgreSQL en una sola consulta rápida
        self.env.cr.execute("""
            SELECT c.relname, c.reltuples 
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE c.relkind = 'r' AND n.nspname = 'public'
        """)
        estimates = {row[0]: int(row[1]) for row in self.env.cr.fetchall()}
        
        # Contar registros de forma híbrida e inteligente
        for table, (model_name, model_desc) in table_models.items():
            count = 0
            estimate = estimates.get(table, 0)
            
            # Si el estimado es pequeño (< 50,000), hacemos un COUNT(*) real (rápido para tablas pequeñas)
            if estimate < 50000:
                try:
                    with self.env.cr.savepoint():
                        self.env.cr.execute("SELECT COUNT(*) FROM \"%s\"" % table)
                        count = self.env.cr.fetchone()[0]
                except Exception as e:
                    _logger.warning('No se pudo contar registros de tabla %s: %s', table, str(e))
                    count = estimate if estimate > 0 else 0
            else:
                # Para tablas grandes, usar la estimación reltuples directamente para evitar sequential scans masivos
                _logger.info('Usando estimación de PostgreSQL para tabla grande %s (%s filas estimadas)', table, estimate)
                count = estimate
                
            counts[table] = {
                'count': count,
                'model_name': model_name,
                'model_desc': model_desc,
            }
        
        return counts
    
    def _analyze_attachments(self):
        """Analiza todos los adjuntos y su almacenamiento."""
        query = """
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE type = 'binary' AND db_datas IS NOT NULL) AS db_count,
                SUM(octet_length(db_datas)) FILTER (WHERE type = 'binary' AND db_datas IS NOT NULL) AS db_size_bytes,
                COUNT(*) FILTER (WHERE store_fname IS NOT NULL AND store_fname <> '') AS filestore_count,
                SUM(file_size) FILTER (WHERE store_fname IS NOT NULL AND store_fname <> '') AS filestore_size_bytes
            FROM ir_attachment;
        """
        self.env.cr.execute(query)
        result = self.env.cr.fetchone()
        total, db_count, db_size_bytes, filestore_count, filestore_size_bytes = result
        
        return {
            'total': total,
            'db_count': db_count,
            'db_size': db_size_bytes / 1024.0 / 1024.0 if db_size_bytes else 0.0,
            'filestore_count': filestore_count,
            'filestore_size': filestore_size_bytes / 1024.0 / 1024.0 if filestore_size_bytes else 0.0,
        }
    
    def _create_table_lines(self, table_data, model_counts):
        """Crea las líneas de detalle por tabla."""
        lines = []
        total_db_size = sum((row[2] or 0.0) for row in table_data) if table_data else 0.0
        
        for row in table_data:
            schemaname, tablename, total_size, table_size, index_size, toast_size = row
            total_size = total_size or 0.0
            
            model_info = model_counts.get(tablename, {'count': 0, 'model_name': '', 'model_desc': ''})
            
            percentage = 0.0
            if total_db_size > 0:
                percentage = min(100.0, max((total_size / total_db_size) * 100.0, 0.0))
            
            lines.append((0, 0, {
                'table_name': tablename,
                'model_name': model_info['model_name'],
                'model_description': model_info['model_desc'],
                'row_count': model_info['count'],
                'table_size': table_size,
                'index_size': index_size,
                'toast_size': toast_size,
                'total_size': total_size,
                'size_percentage': percentage/100,
            }))
        
        return lines
    
    def _create_attachment_lines(self, attachment_stats):
        """Crea las líneas de detalle de adjuntos principales (top 20 por tamaño)."""
        lines = []
        
        # Obtener los 100 adjuntos más grandes
        top_attachments = self.env['ir.attachment'].sudo().search([
            '|', ('file_size', '>', 0), ('db_datas', '!=', False)
        ], order='file_size desc', limit=20)
        
        for attachment in top_attachments:
            size_mb = (attachment.file_size or 0) / 1024.0 / 1024.0
            if size_mb < 0.01:  # Ignorar archivos muy pequeños
                continue
            
            storage_type = 'db' if attachment.db_datas else 'filestore'
            
            lines.append((0, 0, {
                'attachment_id': attachment.id,
                'name': attachment.name,
                'file_size': size_mb,
                'storage_type': storage_type,
                'res_model': attachment.res_model,
                'res_id': attachment.res_id,
                'mimetype': attachment.mimetype,
                'create_date': attachment.create_date,
            }))
        
        return lines

    def _create_model_filetype_lines(self):
        """Calcula el desglose de adjuntos por modelo y tipo mediante SQL directo para alto rendimiento."""
        self.env.cr.execute("""
            SELECT 
                res_model, 
                mimetype,
                COUNT(*) as attachment_count,
                SUM(COALESCE(file_size, 0)) as total_size_bytes
            FROM 
                ir_attachment
            WHERE 
                res_model IS NOT NULL 
                AND res_model != ''
            GROUP BY 
                res_model, mimetype
            ORDER BY
                SUM(COALESCE(file_size, 0)) DESC
            LIMIT 20
        """)
        rows = self.env.cr.fetchall()
        
        # Mapear modelos a sus descripciones
        model_descriptions = {}
        for model_name in self.env.registry:
            try:
                model = self.env[model_name]
                model_descriptions[model_name] = model._description or model_name
            except Exception:
                continue

        lines = []
        for row in rows:
            res_model, mimetype, count, size_bytes = row
            total_size_mb = size_bytes / 1024.0 / 1024.0
            if total_size_mb < 0.01:  # Ignorar registros insignificantes
                continue
            o_mimetype = mimetype or ''
            # Normalizar tipo de archivo con agrupaciones informativas
            mimetype = (mimetype or '').lower()
            if 'video' in mimetype:
                file_type = 'Video (.mp4, .avi, ...)'
            elif 'pdf' in mimetype:
                file_type = 'PDF (.pdf)'
            elif 'image' in mimetype:
                file_type = 'Imagen (.png, .jpg, ...)'
            elif any(x in mimetype for x in ['zip', 'compressed', 'tar', 'rar', '7z']):
                file_type = 'Comprimido (.zip, .rar, ...)'
            elif 'xml' in mimetype:
                file_type = 'XML (.xml)'
            elif any(x in mimetype for x in ['spreadsheet', 'excel', 'sheet', 'word', 'document', 'csv', 'plain']):
                file_type = 'Documentos (.xlsx, .docx, ...)'
            else:
                file_type = 'Otros'
            
            model_desc = model_descriptions.get(res_model, res_model)
            
            lines.append((0, 0, {
                'res_model': res_model,
                'model_description': model_desc,
                'attach_file_type': o_mimetype,
                'file_type': file_type,
                'total_size': total_size_mb,
                'attachment_count': count,
            }))
        return lines

    def _purge_old_analyses(self):
        """Elimina análisis antiguos según los días de retención configurados."""
        params = self.env['ir.config_parameter'].sudo()
        retention_days = int(params.get_param('storage_analyzer.retention_days', 90))
        if retention_days <= 0:
            return True
        
        limit_date = fields.Datetime.now() - timedelta(days=retention_days)
        old_analyses = self.search([
            ('analysis_date', '<', limit_date),
            ('state', '=', 'done'),
        ])
        if old_analyses:
            _logger.info('Purgando %s análisis de almacenamiento antiguos (anteriores a %s)...', len(old_analyses), limit_date)
            old_analyses.unlink()
        return True
    
    def _purge_old_trends(self):
        """Elimina trazabilidades de acuerdo a esta regla:
            - Conservar los registros de la ultima semana.
            - Conserva un registro por semana del ultimo mes.
            - Conserva un registro por mes para los más antiguos.
        """
        today = fields.Date.today()
        week_cutoff = today - timedelta(days=7)
        month_cutoff = today - timedelta(days=30)

        trend_obj = self.env['storage.analysis.trend']
        trends = trend_obj.search([], order='analysis_date desc')
        keep = trend_obj
        seen_weeks = set()
        seen_months = set()

        for trend in trends:
            if trend.analysis_date >= week_cutoff:
                keep |= trend
                continue

            if trend.analysis_date >= month_cutoff:
                week_key = trend.analysis_date.isocalendar()[:2]  # (year, week)
                if week_key not in seen_weeks:
                    seen_weeks.add(week_key)
                    keep |= trend
                continue

            month_key = (trend.analysis_date.year, trend.analysis_date.month)
            if month_key not in seen_months:
                seen_months.add(month_key)
                keep |= trend

        to_delete = trends - keep
        if to_delete:
            _logger.info('Purgando %s registros de tendencia antiguos...', len(to_delete))
            to_delete.unlink()
        return True
    
    def _update_trends(self):
        """Actualiza o crea el registro de tendencia para la fecha actual."""
        trend_obj = self.env['storage.analysis.trend']
        today = fields.Date.today()
        
        trend = trend_obj.search([('analysis_date', '=', today)], limit=1)
        
        vals = {
            'analysis_date': today,
            'database_size': self.database_size,
            'filestore_size': self.filestore_size,
            'total_size': self.total_size,
            'total_attachments': self.total_attachments,
        }
        
        if trend:
            trend.write(vals)
        else:
            trend_obj.create(vals)
        
        return True
    
    def run_analysis(self):
        """Ejecuta el análisis completo de almacenamiento."""
        self.ensure_one()
        self.write({'state': 'running'})
        # TODO: Evaluar si es necesario hacer commit aquí para liberar locks o recursos antes de análisis pesado
        # self.env.cr.commit()
        
        try:
            _logger.info('Iniciando análisis de almacenamiento: %s', self.name)
            
            # 1. Tamaño de la base de datos
            _logger.info('Calculando tamaño de base de datos...')
            db_size = self._get_database_size()
            
            # 2. Tamaño del filestore
            _logger.info('Calculando tamaño de filestore...')
            filestore_size = self._get_filestore_size()
            
            # 3. Análisis de tablas
            _logger.info('Analizando tablas...')
            table_data = self._analyze_tables()
            table_count = len(table_data)
            
            # 4. Conteos de modelos (esto puede ser lento)
            _logger.info('Contando registros por modelo...')
            model_counts = self._get_model_counts()
            
            # 5. Análisis de adjuntos
            _logger.info('Analizando adjuntos...')
            attachment_stats = self._analyze_attachments()
            
            # 6. Crear líneas de detalle
            _logger.info('Creando líneas de análisis...')
            table_lines = self._create_table_lines(table_data, model_counts)
            attachment_lines = self._create_attachment_lines(attachment_stats)
            model_filetype_lines = self._create_model_filetype_lines()
            
            # 7. Actualizar registro principal
            self.write({
                'database_size': db_size,
                'filestore_size': filestore_size,
                'total_attachments': attachment_stats['total'],
                'attachments_store_size': attachment_stats['filestore_size'],
                'attachments_db_size': attachment_stats['db_size'],
                'table_count': table_count,
                'table_line_ids': [(5, 0, 0)] + table_lines,
                'attachment_line_ids': [(5, 0, 0)] + attachment_lines,
                'model_filetype_line_ids': [(5, 0, 0)] + model_filetype_lines,
                'state': 'done',
                'note': _('Análisis completado exitosamente. %s tablas analizadas.') % table_count,
            })
            
            # 8. Actualizar tendencias
            self._update_trends()
            
            # 9. Verificar umbrales de alerta
            self._check_thresholds()
            
            # 10. Purgar análisis antiguos (evitar crecimiento de base de datos)
            self._purge_old_analyses()

            # 11. Purgar trazabilidades antiguas (evitar crecimiento de base de datos)
            self._purge_old_trends()
            
            _logger.info('Análisis de almacenamiento completado: %s', self.name)
            
        except Exception as e:
            _logger.error('Error en análisis de almacenamiento: %s', str(e), exc_info=True)
            self.write({
                'state': 'error',
                'note': _('Error: %s') % str(e),
            })
            raise UserError(_('Error durante el análisis: %s') % str(e))
        
        return True
    
    def _check_thresholds(self):
        """Verifica los umbrales configurados y envía alertas si es necesario."""
        params = self.env['ir.config_parameter'].sudo()
        limit_mb = float(params.get_param('storage_analyzer.storage_limit_mb', 0))
        
        if not limit_mb:
            return
        
        warning_pct = float(params.get_param('storage_analyzer.threshold_warning', 70))
        critical_pct = float(params.get_param('storage_analyzer.threshold_critical', 85))
        
        usage_pct = (self.total_size / limit_mb) * 100
        
        if usage_pct >= critical_pct:
            self._send_alert('critical', usage_pct, limit_mb)
        elif usage_pct >= warning_pct:
            self._send_alert('warning', usage_pct, limit_mb)
    
    def _send_alert(self, level, usage_pct, limit_mb):
        """Envía una notificación de alerta.

        Solo envía el correo si la opción "Enviar correo de alerta" está activa
        en los ajustes. Los destinatarios configurados tienen prioridad; si no
        hay destinatarios explícitos, se recae en notificar a los
        administradores del sistema (comportamiento anterior).
        """
        params = self.env['ir.config_parameter'].sudo()
        if not params.get_param('storage_analyzer.enable_alert_email', 'True').lower() in ('1', 'true', 'yes'):
            _logger.info('Alerta de almacenamiento omitida: envío de correos deshabilitado.')
            return

        subject = _('Alerta de Almacenamiento: %s') % self.name

        # Destinatarios explícitos desde ir.config_parameter
        recipient_ids_str = params.get_param('storage_analyzer.alert_email_recipient_ids', '')
        recipient_ids = []
        if recipient_ids_str:
            try:
                recipient_ids = [int(x) for x in recipient_ids_str.split(',') if x.strip().isdigit()]
            except (ValueError, TypeError):
                _logger.warning('IDs de destinatarios de alerta inválidos: %s', recipient_ids_str)
                recipient_ids = []

        if recipient_ids:
            partners = self.env['res.partner'].sudo().browse(recipient_ids).exists()
        else:
            _logger.warning('No se enviará alerta de almacenamiento: no hay destinatarios configurados.')
            return

        if not partners:
            _logger.warning('No se encontraron destinatarios para la alerta de almacenamiento.')
            return

        if level == 'critical':
            body = _('''
                <p><strong>¡ALERTA CRÍTICA DE ALMACENAMIENTO!</strong></p>
                <p>El análisis <strong>%s</strong> ha detectado que el almacenamiento está al <strong>%.2f%%</strong> de su capacidad.</p>
                <ul>
                    <li>Límite configurado: %.2f MB (%.2f GB)</li>
                    <li>Uso actual: %.2f MB (%.2f GB)</li>
                    <li>Base de datos: %.2f MB</li>
                    <li>Filestore: %.2f MB</li>
                </ul>
                <p>Se recomienda tomar acción inmediata para liberar espacio o aumentar el límite contratado.</p>
            ''') % (self.name, usage_pct, limit_mb, limit_mb/1024, 
                   self.total_size, self.total_size_gb,
                   self.database_size, self.filestore_size)
        else:
            body = _('''
                <p><strong>Advertencia de Almacenamiento</strong></p>
                <p>El análisis <strong>%s</strong> ha detectado que el almacenamiento está al <strong>%.2f%%</strong> de su capacidad.</p>
                <ul>
                    <li>Límite configurado: %.2f MB (%.2f GB)</li>
                    <li>Uso actual: %.2f MB (%.2f GB)</li>
                    <li>Base de datos: %.2f MB</li>
                    <li>Filestore: %.2f MB</li>
                </ul>
                <p>Monitoree el crecimiento y considere acciones preventivas.</p>
            ''') % (self.name, usage_pct, limit_mb, limit_mb/1024,
                   self.total_size, self.total_size_gb,
                   self.database_size, self.filestore_size)
        
        self.message_post(
            body=body,
            subject=subject,
            partner_ids=partners.ids,
            message_type='notification',
        )
    
    @api.model
    def cron_daily_analysis(self):
        """Cron job para análisis diario automático."""
        # Verificar si ya existe un análisis para hoy
        today = fields.Date.today()
        existing = self.search([
            ('analysis_date', '>=', today),
            ('state', '=', 'done'),
        ], limit=1)
        
        if existing:
            _logger.info('Ya existe un análisis para hoy, omitiendo cron.')
            return True
        
        # Crear nuevo análisis y ejecutarlo
        analysis = self.create({
            'analysis_date': fields.Datetime.now(),
        })
        
        try:
            analysis.run_analysis()
        except Exception as e:
            _logger.error('Error en análisis automático: %s', str(e))
        
        return True

    def action_view_spreadsheet_dashboard(self):
        """Abre directamente el Spreadsheet Dashboard correspondiente a Almacenamiento."""
        dashboard = self.env.ref('storage_analyzer.spreadsheet_dashboard_storage', raise_if_not_found=False)
        return {
            'type': 'ir.actions.client',
            'tag': 'action_spreadsheet_dashboard',
            'params': {
                'dashboard_id': dashboard.id if dashboard else False,
            },
            'context': {
                'params': {
                    'dashboard_id': dashboard.id if dashboard else False,
                }
            }
        }
    
