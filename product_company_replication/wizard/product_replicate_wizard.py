# -*- coding: utf-8 -*-

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ProductReplicateWizard(models.TransientModel):
    _name = 'product.replicate.wizard'
    _description = 'Asistente de replicación de producto entre compañías'

    product_tmpl_id = fields.Many2one(
        comodel_name='product.template',
        string='Producto',
        required=True,
        readonly=True,
    )
    empresa = fields.Many2many(
        comodel_name='res.company',
        string='Empresa',
        help='Compañías en las que se creará una copia de este producto.',
    )
    available_company_ids = fields.Many2many(
        comodel_name='res.company',
        relation='product_replicate_wizard_available_company_rel',
        string='Compañías disponibles',
        compute='_compute_available_company_ids',
    )
    existing_info = fields.Text(
        string='Compañías ya vinculadas',
        compute='_compute_existing_info',
    )
    result_log = fields.Text(
        string='Resultado',
        readonly=True,
    )
    state = fields.Selection(
        selection=[('draft', 'Borrador'), ('done', 'Completado')],
        default='draft',
    )

    @api.depends('product_tmpl_id')
    def _compute_available_company_ids(self):
        for wizard in self:
            template = wizard.product_tmpl_id
            allowed = self.env['res.company'].search([
                ('id', 'in', self.env.user.company_ids.ids),
            ])
            used = template._get_replica_group().mapped('company_id')
            own = template.company_id
            wizard.available_company_ids = allowed - used - own

    @api.depends('product_tmpl_id')
    def _compute_existing_info(self):
        for wizard in self:
            template = wizard.product_tmpl_id
            others = template._get_replica_targets()
            if not others:
                wizard.existing_info = False
                continue
            lines = []
            for other in others.sorted(lambda t: t.company_id.name or ''):
                estado = _('archivado') if not other.active else _('activo')
                lines.append('• %s (%s)' % (other.company_id.display_name, estado))
            wizard.existing_info = '\n'.join(lines)

    def action_select_all(self):
        self.ensure_one()
        self.empresa = [(6, 0, self.available_company_ids.ids)]
        return self._reopen()

    def action_deselect_all(self):
        self.ensure_one()
        self.empresa = [(5, 0, 0)]
        return self._reopen()

    def action_replicate(self):
        self.ensure_one()
        template = self.product_tmpl_id
        if not self.empresa:
            raise UserError(_('Seleccione al menos una empresa destino.'))

        created, errors = [], []
        for company in self.empresa:
            try:
                # Un savepoint por compañía: si una falla, las demás se conservan.
                with self.env.cr.savepoint():
                    new_template = template._replicate_to_company(company)
                    created.append((company, new_template))
            except Exception as error:  # noqa: BLE001 - se reporta al usuario
                _logger.warning(
                    'Replicación de %s a %s fallida: %s',
                    template.display_name, company.display_name, error,
                )
                errors.append((company, error))

        log = []
        if created:
            log.append(_('Replicado correctamente en %s compañía(s):', len(created)))
            for company, new_template in created:
                log.append('  ✔ %s → %s' % (company.display_name, new_template.display_name))
        if errors:
            log.append('')
            log.append(_('Con errores en %s compañía(s):', len(errors)))
            for company, error in errors:
                log.append('  ✘ %s: %s' % (company.display_name, error))
            log.append('')
            log.append(_('Los productos creados correctamente se conservaron.'))

        self.result_log = '\n'.join(log)
        self.state = 'done'
        return self._reopen()

    def _reopen(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Replicar producto'),
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
