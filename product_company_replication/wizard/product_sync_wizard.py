# -*- coding: utf-8 -*-

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ProductSyncWizard(models.TransientModel):
    _name = 'product.sync.wizard'
    _description = 'Asistente de sincronización de producto entre compañías'

    product_tmpl_id = fields.Many2one(
        comodel_name='product.template',
        string='Producto',
        required=True,
        readonly=True,
    )
    field_names = fields.Char(
        string='Campos modificados (técnico)',
        readonly=True,
    )
    changes_summary = fields.Text(
        string='Cambios a replicar',
        compute='_compute_changes_summary',
    )
    target_summary = fields.Text(
        string='Compañías destino',
        compute='_compute_target_summary',
    )
    archived_warning = fields.Text(
        string='Advertencia',
        compute='_compute_target_summary',
    )
    include_archived = fields.Boolean(
        string='Incluir productos archivados',
        default=True,
        help='Si se desmarca, las réplicas archivadas no se actualizarán.',
    )
    result_log = fields.Text(
        string='Resultado',
        readonly=True,
    )
    state = fields.Selection(
        selection=[('draft', 'Borrador'), ('done', 'Completado')],
        default='draft',
    )

    def _get_field_list(self):
        self.ensure_one()
        return [f for f in (self.field_names or '').split(',') if f]

    @api.depends('product_tmpl_id', 'field_names')
    def _compute_changes_summary(self):
        for wizard in self:
            template = wizard.product_tmpl_id
            differences = template._get_replica_differences()
            selected = wizard._get_field_list()
            lines = []
            for fname in selected:
                info = differences.get(fname)
                if not info:
                    continue
                lines.append('• %s → %s' % (
                    info['label'],
                    template._format_field_value(info['source']) or _('(vacío)'),
                ))
            wizard.changes_summary = '\n'.join(lines) or _('Sin diferencias pendientes.')

    @api.depends('product_tmpl_id')
    def _compute_target_summary(self):
        for wizard in self:
            targets = wizard.product_tmpl_id._get_replica_targets()
            lines, archived = [], []
            for target in targets.sorted(lambda t: t.company_id.name or ''):
                if target.active:
                    lines.append('• %s' % target.company_id.display_name)
                else:
                    lines.append('• %s  [%s]' % (
                        target.company_id.display_name, _('ARCHIVADO')))
                    archived.append(target.company_id.display_name)
            wizard.target_summary = '\n'.join(lines) or _('Sin compañías vinculadas.')
            if archived:
                wizard.archived_warning = _(
                    'El producto está archivado en: %s.\n'
                    'Se actualizará igualmente si mantiene marcada la casilla de abajo.',
                    ', '.join(archived),
                )
            else:
                wizard.archived_warning = False

    def action_sync(self):
        self.ensure_one()
        template = self.product_tmpl_id
        field_list = self._get_field_list()
        if not field_list:
            raise UserError(_('No hay campos por sincronizar.'))

        targets = template._get_replica_targets()
        if not self.include_archived:
            targets = targets.filtered('active')
        if not targets:
            raise UserError(_('No hay compañías destino seleccionadas.'))

        updated, errors = [], []
        for target in targets:
            try:
                # Un savepoint por compañía: un fallo no revierte los demás.
                with self.env.cr.savepoint():
                    template._sync_to_target(target, field_list)
                    updated.append(target)
            except Exception as error:  # noqa: BLE001 - se reporta al usuario
                _logger.warning(
                    'Sincronización de %s hacia %s fallida: %s',
                    template.display_name, target.company_id.display_name, error,
                )
                errors.append((target, error))

        log = []
        if updated:
            log.append(_('Actualizado en %s compañía(s):', len(updated)))
            for target in updated:
                estado = '' if target.active else _(' (archivado)')
                log.append('  ✔ %s%s' % (target.company_id.display_name, estado))
        if errors:
            log.append('')
            log.append(_('Con errores en %s compañía(s):', len(errors)))
            for target, error in errors:
                log.append('  ✘ %s: %s' % (target.company_id.display_name, error))
            log.append('')
            log.append(_('Las compañías actualizadas correctamente se conservaron.'))

        self.result_log = '\n'.join(log)
        self.state = 'done'
        return {
            'type': 'ir.actions.act_window',
            'name': _('Sincronizar cambios en otras compañías'),
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
