# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import UserError

# Campos del maestro de producto que se replican y se mantienen sincronizados.
# Los campos marcados como opcionales solo se usan si el módulo que los define
# está instalado, para no crear dependencias duras.
CORE_REPLICATION_FIELDS = [
    'name',
    'default_code',
    'categ_id',
    'uom_id',
    'type',
    'is_storable',
    'tracking',
    'description_sale',
    'description_purchase',
    'weight',
    'volume',
]

OPTIONAL_REPLICATION_FIELDS = [
    'product_brand_id',          # product_brand
    'dian_brand',                # l10n_co_data_bloodo
    'dian_model',
    'dian_customs_code',
    'dian_unspsc_id',
    'unspsc_code_id',            # product_unspsc
    'commercial_presentation',   # stock_reception_act
    'sanitary_registration',
    'shelf_life',
    'risk_class',
]


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    replica_origin_id = fields.Many2one(
        comodel_name='product.template',
        string='Producto origen',
        help='Producto a partir del cual se generó este registro por replicación.',
        ondelete='set null',
        copy=False,
        index=True,
        readonly=True,
    )
    replica_ids = fields.Many2many(
        comodel_name='product.template',
        relation='product_template_replica_rel',
        column1='origin_id',
        column2='replica_id',
        string='Productos replicados',
        help='Productos generados a partir de este en otras compañías.',
        copy=False,
        readonly=True,
    )
    replica_count = fields.Integer(
        string='Nº de compañías vinculadas',
        compute='_compute_replica_count',
    )

    # ------------------------------------------------------------------
    # Creación
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        """Todo producto nuevo nace en una sola compañía, nunca compartido.

        Sin esto, un usuario que crea un producto sin tocar el campo "Compañía"
        obtiene un registro con `company_id=False` (compartido/global): se ve en
        las 14 compañías pero es un único registro sin apuntadores, sin trazabilidad
        y fuera del flujo de "Replicar producto". `install_mode` protege la carga de
        datos vía XML/demo (donde un producto sin compañía sí puede ser intencional).
        """
        if not self.env.context.get('install_mode'):
            for vals in vals_list:
                if not vals.get('company_id'):
                    vals['company_id'] = self.env.company.id
        return super().create(vals_list)

    # ------------------------------------------------------------------
    # Cómputos
    # ------------------------------------------------------------------
    @api.depends('replica_origin_id', 'replica_ids')
    def _compute_replica_count(self):
        for template in self:
            template.replica_count = len(template._get_replica_group()) - 1

    # ------------------------------------------------------------------
    # Helpers del grupo de réplicas
    # ------------------------------------------------------------------
    @api.model
    def _get_replication_fields(self):
        """Campos del maestro que se replican/sincronizan entre compañías.

        Un campo opcional solo se incluye si realmente existe en el modelo, de forma
        que el módulo funcione igual con o sin los addons que los definen.
        """
        fields_list = list(CORE_REPLICATION_FIELDS)
        fields_list += [f for f in OPTIONAL_REPLICATION_FIELDS if f in self._fields]
        return [f for f in fields_list if f in self._fields]

    def _get_replica_group(self):
        """Todos los productos del grupo (origen + réplicas), incluidos los archivados.

        Se puede invocar desde cualquier miembro del grupo, no solo desde el origen.
        Se busca por `replica_origin_id` (el apuntador many2one) en vez de leer solo el
        many2many `replica_ids`, para que el grupo sea siempre correcto aunque ese
        campo aún no se haya recalculado en algún registro.

        Se resuelve en `sudo()`: los miembros del grupo viven en otras compañías, y la
        regla multi-compañía de `product.template` solo deja ver las que el usuario
        tiene "activas" en el selector de la interfaz en ese momento, no todas las que
        tiene permitidas. El acceso ya quedó controlado al ofrecer solo esas compañías
        en el asistente de replicación (`env.user.company_ids`).
        """
        self.ensure_one()
        self_sudo = self.sudo()
        origin = (self_sudo.replica_origin_id or self_sudo).with_context(active_test=False)
        replicas = self.env['product.template'].sudo().with_context(active_test=False).search([
            ('replica_origin_id', '=', origin.id),
        ])
        return origin | replicas

    def _get_replica_targets(self):
        """Miembros del grupo distintos de self."""
        self.ensure_one()
        return self._get_replica_group() - self

    # ------------------------------------------------------------------
    # Lectura / escritura de los valores replicables
    # ------------------------------------------------------------------
    def _get_replication_values(self, target_company=None):
        """Valores de los campos replicables listos para create()/write()."""
        self.ensure_one()
        source = self
        if target_company:
            source = self.with_company(target_company)
        values = {}
        for fname in self._get_replication_fields():
            field = self._fields[fname]
            value = source[fname]
            if field.type == 'many2one':
                values[fname] = value.id or False
            elif field.type in ('many2many', 'one2many'):
                values[fname] = [(6, 0, value.ids)]
            else:
                values[fname] = value
        return values

    def _sync_translations(self, target):
        """Copia las traducciones de los campos traducibles hacia la réplica."""
        self.ensure_one()
        langs = self.env['res.lang'].get_installed()
        translated = [
            f for f in self._get_replication_fields()
            if self._fields[f].translate
        ]
        if not translated or len(langs) < 2:
            return
        for lang_code, _lang_name in langs:
            source = self.with_context(lang=lang_code)
            vals = {f: source[f] for f in translated}
            target.sudo().with_context(lang=lang_code, skip_replica_sync=True).write(vals)

    # ------------------------------------------------------------------
    # Diferencias entre el producto y sus réplicas
    # ------------------------------------------------------------------
    def _get_replica_differences(self):
        """Devuelve {campo: {'label':..., 'source':..., 'targets': {tmpl: valor}}}."""
        self.ensure_one()
        targets = self._get_replica_targets()
        if not targets:
            return {}

        field_descriptions = self.fields_get(self._get_replication_fields())
        differences = {}
        for fname in self._get_replication_fields():
            source_value = self[fname]
            diverging = {}
            for target in targets:
                if target[fname] != source_value:
                    diverging[target] = target[fname]
            if diverging:
                differences[fname] = {
                    'label': field_descriptions[fname]['string'],
                    'source': source_value,
                    'targets': diverging,
                }
        return differences

    @api.model
    def _format_field_value(self, value):
        if isinstance(value, models.BaseModel):
            return value.display_name or ''
        if value is False or value is None:
            return ''
        return str(value)

    # ------------------------------------------------------------------
    # Replicación
    # ------------------------------------------------------------------
    def _replicate_to_company(self, company):
        """Crea la réplica de este producto en `company`. Devuelve el nuevo registro."""
        self.ensure_one()
        origin = self.replica_origin_id or self
        values = self._get_replication_values()
        values.update({
            'company_id': company.id,
            'replica_origin_id': origin.id,
        })
        new_template = self.env['product.template'].with_company(company).with_context(
            skip_replica_sync=True,
            mail_create_nolog=True,
            mail_create_nosubscribe=True,
        ).create(values)
        # Apuntador many2many: el origen mantiene la lista de todo lo generado a partir de él.
        # sudo() porque `origin` puede estar en una compañía que el usuario no tiene
        # "activa" en el selector en este momento, aunque sí tenga permiso sobre ella.
        origin.sudo().write({'replica_ids': [(4, new_template.id)]})
        self._sync_translations(new_template)
        self._log_replica_trace(origin, new_template, company)
        return new_template

    def _sync_to_target(self, target, field_names):
        """Escribe en `target` los campos indicados tomándolos de self."""
        self.ensure_one()
        values = {}
        all_values = self._get_replication_values()
        for fname in field_names:
            if fname in all_values:
                values[fname] = all_values[fname]
        if values:
            # sudo(): el destino puede estar en una compañía no "activa" para el usuario
            # en este momento, aunque el asistente ya restringió las réplicas a
            # compañías donde el usuario tiene permiso.
            target.sudo().with_context(skip_replica_sync=True).write(values)
        self._sync_translations(target)
        self._log_sync_trace(target, values)

    # ------------------------------------------------------------------
    # Trazabilidad (chatter)
    # ------------------------------------------------------------------
    def _log_replica_trace(self, origin, new_template, company):
        """Deja constancia en el chatter de origen y réplica de quién replicó qué."""
        user_name = self.env.user.display_name
        origin.sudo().message_post(
            body=_(
                'Producto replicado hacia la compañía %(company)s por %(user)s '
                '(nuevo producto: %(product)s).',
                company=company.display_name,
                user=user_name,
                product=new_template.display_name,
            ),
            subtype_xmlid='mail.mt_note',
        )
        new_template.sudo().message_post(
            body=_(
                'Producto creado por replicación desde %(origin_company)s '
                '(%(origin_product)s), realizado por %(user)s.',
                origin_company=origin.company_id.display_name,
                origin_product=origin.display_name,
                user=user_name,
            ),
            subtype_xmlid='mail.mt_note',
        )

    def _log_sync_trace(self, target, values):
        """Deja constancia en el chatter de origen y destino de quién sincronizó qué."""
        self.ensure_one()
        if not values:
            return
        user_name = self.env.user.display_name
        field_descriptions = self.fields_get(list(values.keys()))
        field_labels = ', '.join(
            field_descriptions[fname]['string'] for fname in values
        )
        self.sudo().message_post(
            body=_(
                'Sincronización enviada hacia %(company)s por %(user)s '
                '(campos: %(fields)s).',
                company=target.company_id.display_name,
                user=user_name,
                fields=field_labels,
            ),
            subtype_xmlid='mail.mt_note',
        )
        target.sudo().message_post(
            body=_(
                'Producto actualizado por sincronización desde %(company)s, '
                'realizado por %(user)s (campos: %(fields)s).',
                company=self.company_id.display_name,
                user=user_name,
                fields=field_labels,
            ),
            subtype_xmlid='mail.mt_note',
        )

    # ------------------------------------------------------------------
    # Acciones desde el formulario
    # ------------------------------------------------------------------
    def action_open_replicate_wizard(self):
        self.ensure_one()
        if not self.id:
            raise UserError(_('Guarde el producto antes de replicarlo.'))
        wizard = self.env['product.replicate.wizard'].create({
            'product_tmpl_id': self.id,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Replicar producto'),
            'res_model': 'product.replicate.wizard',
            'view_mode': 'form',
            'res_id': wizard.id,
            'target': 'new',
        }

    def action_open_sync_wizard(self):
        """Botón manual de sincronización."""
        self.ensure_one()
        if not self._get_replica_targets():
            raise UserError(_(
                'Este producto no está vinculado a ninguna otra compañía.\n\n'
                'Use primero el botón "Replicar producto" para crearlo en las demás '
                'compañías; a partir de ese momento los cambios podrán sincronizarse.'
            ))
        differences = self._get_replica_differences()
        if not differences:
            raise UserError(_(
                'No hay diferencias por sincronizar: el producto ya está alineado '
                'en todas las compañías vinculadas.'
            ))
        return self._build_sync_action(differences)

    def action_check_replica_sync(self):
        """Llamado por el cliente web después de guardar.

        Devuelve la acción del asistente si hay algo que sincronizar, o False para que
        el guardado continúe sin interrupciones.
        """
        self.ensure_one()
        if self.env.context.get('skip_replica_sync'):
            return False
        if not self._get_replica_targets():
            return False
        differences = self._get_replica_differences()
        if not differences:
            return False
        return self._build_sync_action(differences)

    def _build_sync_action(self, differences):
        self.ensure_one()
        wizard = self.env['product.sync.wizard'].create({
            'product_tmpl_id': self.id,
            'field_names': ','.join(sorted(differences)),
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Sincronizar cambios en otras compañías'),
            'res_model': 'product.sync.wizard',
            'view_mode': 'form',
            'res_id': wizard.id,
            'target': 'new',
        }

    def action_view_replicas(self):
        self.ensure_one()
        group = self._get_replica_group()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Productos vinculados'),
            'res_model': 'product.template',
            'view_mode': 'list,form',
            'domain': [('id', 'in', group.ids)],
            'context': {'active_test': False},
        }
