# -*- coding: utf-8 -*-
import base64

from odoo import api, fields, models
from odoo.tools import file_open



# Pendientes 24-sep (8.3) / reunión 13-oct (filas 50-52): cómo se presentan
# las opciones con imagen. Lo usan el Catálogo de campos y las Referencias.
DISPLAY_MODES = [
    ('auto', 'Automático (según imágenes)'),
    ('list', 'Lista sin foto'),
    ('list_thumbs', 'Lista con foto pequeña'),
    ('buttons', 'Botones de imagen (sin lista)'),
]

class SafraFieldSection(models.Model):
    _name = 'safra.field.section'
    _description = 'Sección de Campos del Cotizador'
    _order = 'sequence, id'

    _code_uniq = models.Constraint('UNIQUE(code)', 'El código de la sección debe ser único.')

    code = fields.Char(string='Código', required=True, index=True)
    name = fields.Char(string='Nombre', required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    # Secciones de la hoja «Matriz Unificada» (nombres y orden del cliente)
    # y a qué sección pertenece cada campo según su columna E.
    MATRIZ_SECTIONS = [
        ('basicos', 'DATOS BÁSICOS', ['exhibition', 'same_header', 'sequence_name']),
        ('dimensiones', 'DIMENSIONES',
         ['width', 'height', 'width2', 'height2', 'quantity', 'dimensiones',
          'location', 'aligned']),
        ('tela', 'TELA',
         ['fabric_id', 'color_id', 'coordinado',
          'fabric_id_2', 'color_id_2', 'fabric_id_3', 'color_id_3',
          'fabric_id_4', 'color_id_4', 'fabric_id_5', 'color_id_5',
          'tela_al_reves', 'atravesar_tela', 'tamano_traslape',
          'quantity_lamas']),
        ('estructura', 'ESTRUCTURA', ['perfil', 'perfil_sheer', 'perfileria2']),
        ('motor', 'MOTOR',
         ['has_motor', 'motor', 'interruptor_rf', 'interruptor_panel',
          'motor_support_type', 'control', 'control_channel',
          'requires_charger']),
        ('cabezal', 'CABEZAL',
         ['cabezal_tipo', 'color_cabezal', 'cabezal_forrado', 'cabezal_tela']),
        ('ficha', 'FICHA TÉCNICA', ['unificacion_mando']),
        ('accesorios', 'ACCESORIOS Y OTRAS PERSONALIZACIONES',
         ['orientation', 'mando_position']),
        ('diseno', 'DISEÑO DE IMPRESIÓN',
         ['design_print', 'custom_design', 'design_exterior', 'print_m2']),
        ('cenefa', 'CENEFA',
         ['cenefa_panel', 'cenefa_type', 'perfil_cenefa', 'cenefa_lateral',
          'cenefa_longitud', 'cenefa_dividida', 'cenefa_lined', 'cenefa_tela',
          'corte_cenefa', 'cenefa_corte', 'color_cenefa']),
        ('cover', 'PERFIL COVER LIGHT',
         ['cover_light_profile', 'coverlight_felpa', 'coverlight_45']),
        ('riel', 'RIEL',
         ['apertura', 'posicion_telo', 'ancho_telo', 'riel_tipo', 'riel_junto',
          'tipoplano_cortina', 'traslape_centro', 'riel_dividido']),
        ('cordon', 'CORDÓN / CADENA / BASTÓN',
         ['extra_chain', 'color_cordon', 'longitud_baston']),
        ('otras', 'OTRAS OPCIONES',
         ['enclosed', 'escuadras', 'sesgo', 'bolsillo_size', 'abrazadera',
          'tipo_plano', 'num_segmento', 'profundidad_onda_c',
          'profundidad_onda', 'uso_riel', 'distribucion_lamas', 'pesa_lama',
          'tipo_entretela', 'bajofalso', 'gancho_cortinero']),
    ]

    # === Revisión Sprint 1 (columna G de la matriz): unificaciones ===
    # Campos duplicados que el cliente pidió unificar (viejo → destino). Las
    # opciones del viejo pasan como override por sistema cuando aportan
    # valores propios del negocio (mandos, cenefas PVC, usos de riel).
    SPRINT1_UNIFICACIONES = [
        ('interruptor_panel', 'interruptor_rf', False),
        ('cenefa_type', 'cenefa_panel', True),
        ('cenefa_corte', 'corte_cenefa', False),
        ('uso_riel', 'profundidad_onda', True),
        ('riel_dividido', 'traslape_centro', False),
        ('mando2', 'mando_position', True),
        ('mando_panel', 'mando_position', True),
        ('mando_vertical', 'mando_position', True),
        ('mando_cortina', 'mando_position', True),
        ('alto_cortina', 'height', False),
    ]
    # Se retira del portal (se calcula con los kits, el cliente no lo ve).
    SPRINT1_RETIRAR = ['motor_support_type']
    # Al copiar las opciones de Cenefa PVC al esquema de cenefa_panel se
    # traducen los valores (1=Sin, 2=Tela, 3=Metálica) para que las
    # dependencias funcionen con una sola convención.
    SPRINT1_VALUE_MAP = {
        'cenefa_type': {'sin': '1', 'tela': '2', 'metalica': '3'},
    }
    # Campos activos que dependían de un campo unificado: nuevo padre y valor.
    SPRINT1_DEPENDS_REMAP = {
        'perfil_cenefa': ('cenefa_panel', '2'),
        'cenefa_lined': ('cenefa_panel', '!1'),
        'cenefa_lateral': ('cenefa_panel', '!1'),
    }
    # Ancho/Alto no van en los sistemas sin dimensiones digitadas
    # (Cuadro Lienzo usa el campo Dimensiones).
    SPRINT1_SIN_DIMENSIONES = [
        'CUADRO LIENZO', 'PAPEL COLGADURA', 'PELICULA SEGURIDAD',
        'ABRAZADERA CORTINA']

    @api.model
    def _apply_sprint1_revision(self, _ids=None):
        """Aplica las unificaciones/retiros pedidos en la revisión del
        sprint 1 (estados ELIMINAR / REVISAR HAY 2). Idempotente: los campos
        ya archivados se saltan."""
        Field = self.env['safra.field'].with_context(active_test=False)
        # OJO: los mapeos también tienen 'active'; buscar sin filtro para no
        # chocar con la restricción única al recrear uno archivado.
        Mapping = self.env['safra.system.field'].with_context(active_test=False)
        for old_code, new_code, copy_opts in self.SPRINT1_UNIFICACIONES:
            old = Field.search([('code', '=', old_code)], limit=1)
            new = Field.search([('code', '=', new_code)], limit=1)
            if not old or not old.active or not new:
                continue
            for m in Mapping.search([('field_id', '=', old.id)]):
                target = Mapping.search([
                    ('system_id', '=', m.system_id.id),
                    ('field_id', '=', new.id)], limit=1)
                if not target:
                    target = Mapping.create({
                        'system_id': m.system_id.id,
                        'field_id': new.id,
                        'sequence': m.sequence,
                    })
                elif not target.active:
                    # El destino existía pero archivado: hereda el lugar
                    # del campo unificado.
                    target.write({'active': True, 'sequence': m.sequence})
                if copy_opts and old.option_ids and not target.option_ids:
                    vmap = self.SPRINT1_VALUE_MAP.get(old_code, {})
                    for o in old.option_ids:
                        self.env['safra.system.field.option'].create({
                            'system_field_id': target.id,
                            'value': vmap.get(o.value, o.value),
                            'name': o.name,
                            'sequence': o.sequence,
                        })
                m.unlink()
            old.active = False
        for code in self.SPRINT1_RETIRAR:
            f = Field.search([('code', '=', code)], limit=1)
            if f and f.active:
                Mapping.search([('field_id', '=', f.id)]).unlink()
                f.active = False
        # Dependencias que apuntaban a un campo unificado: se remapean al
        # campo destino con el valor traducido; el resto se limpia.
        for code, (parent_code, value) in self.SPRINT1_DEPENDS_REMAP.items():
            f = Field.search([('code', '=', code)], limit=1)
            parent = Field.search([('code', '=', parent_code)], limit=1)
            if f and parent and (not f.depends_field_id or not f.depends_field_id.active):
                f.write({'depends_field_id': parent.id, 'depends_value': value})
        archived = Field.search([('active', '=', False)])
        Field.search([('depends_field_id', 'in', archived.ids),
                      ('active', '=', True)]).write({'depends_field_id': False})
        # Ancho/Alto fuera de los sistemas sin dimensiones digitadas.
        systems = self.env['safra.system'].with_context(active_test=False).search([
            ('name', 'in', self.SPRINT1_SIN_DIMENSIONES)])
        dims = Field.search([('code', 'in', ['width', 'height'])])
        Mapping.search([('system_id', 'in', systems.ids),
                        ('field_id', 'in', dims.ids)]).unlink()
        return True

    @api.model
    def _apply_matriz_sections(self, _ids=None):
        """Renombra/ordena las secciones como la hoja «Matriz Unificada» y
        reasigna cada campo a su sección según la matriz. Idempotente; los
        campos que no están en la matriz conservan su sección actual."""
        Field = self.env['safra.field']
        for seq, (code, name, field_codes) in enumerate(self.MATRIZ_SECTIONS, start=1):
            section = self.search([('code', '=', code)], limit=1)
            if section:
                section.write({'name': name, 'sequence': seq * 10})
            else:
                section = self.create({'code': code, 'name': name, 'sequence': seq * 10})
            fields_ = Field.with_context(active_test=False).search([
                ('code', 'in', field_codes),
                ('section_id', '!=', section.id)])
            if fields_:
                fields_.write({'section_id': section.id})
        return True


class SafraField(models.Model):
    _name = 'safra.field'
    _description = 'Campo Configurable del Cotizador'
    _order = 'sequence, id'

    _code_uniq = models.Constraint('UNIQUE(code)', 'El código del campo debe ser único.')

    FIELD_TYPES = [
        ('char', 'Texto'),
        ('integer', 'Entero'),
        ('float', 'Decimal'),
        ('boolean', 'Casilla'),
        ('selection', 'Lista desplegable'),
        ('fabric', 'Referencia (Tela)'),
        ('color', 'Color de Tela'),
        # Punto 16 (OBS REU TELAS): el campo trae los productos relacionados
        # en las referencias de una categoría (ej: Sesgo). Las opciones no se
        # digitan aquí: salen de los colores/productos de esas referencias.
        ('ref_categoria', 'Referencia (categoría)'),
        # Puntos 10-11: el campo ofrece el catálogo de diseños de impresión
        # (menú Configuración > Diseños de Impresión, modelo safra.design).
        ('design', 'Diseño de impresión (catálogo)'),
    ]

    FABRIC_FLAGS = [
        ('printable', 'Tela Estampable'),
        ('doublefaced', 'Tela Doblefaz'),
        ('pierceable', 'Tela Atravesable'),
        ('sesgable', 'Tela Sesgable'),
        ('texturable', 'Tela Texturizable'),
    ]

    code = fields.Char(
        string='Código técnico', required=True, index=True,
        help='Nombre técnico. Si coincide con una columna de safra.quote.line se guarda ahí; '
             'de lo contrario se guarda en el almacén de atributos.',
    )
    name = fields.Char(string='Etiqueta', required=True, translate=True)
    section_id = fields.Many2one('safra.field.section', string='Sección', required=True, ondelete='restrict')
    field_type = fields.Selection(FIELD_TYPES, string='Tipo', required=True, default='char')
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    placeholder = fields.Char(string='Placeholder')
    help_text = fields.Char(string='Ayuda')
    col_size = fields.Integer(string='Ancho columna (1-12)', default=4)
    required = fields.Boolean(string='Requerido por defecto')
    default_value = fields.Char(string='Valor por defecto')

    option_ids = fields.One2many('safra.field.option', 'field_id', string='Opciones')
    # Solo para tipo «Referencia (categoría)»: de qué categoría de
    # referencias salen los productos que ofrece el campo.
    ref_category_id = fields.Many2one(
        'safra.product.option', string='Categoría de referencia',
        domain=[('type', '=', 'ref_categoria')], ondelete='restrict',
        help='Las opciones del campo serán los productos (colores) de las '
             'referencias que tengan esta categoría y stock suficiente.',
    )

    # Visibilidad condicional: el campo se muestra si el campo padre tiene el valor indicado.
    depends_field_id = fields.Many2one('safra.field', string='Depende del campo', ondelete='set null')
    depends_value = fields.Char(
        string='Valor que activa',
        help="Valor del campo padre que activa este campo. Prefijo '!' para 'distinto de' "
             "(ej: '!sin' = visible cuando el padre no es 'sin').",
    )
    # Visibilidad según flag de la tela seleccionada.
    fabric_flag = fields.Selection(FABRIC_FLAGS, string='Requiere flag de tela')
    # Pendientes 24-sep (8.3): cómo se presentan las opciones con imagen.
    display_mode = fields.Selection(DISPLAY_MODES, string='Presentación de opciones', default='auto', required=True,
        help='Lista con foto pequeña: desplegable con la miniatura junto a '
             'cada opción; la imagen del elegido se amplía con un clic. '
             'Automático: lista con fotos si las opciones tienen imagen '
             '(solo botones cuando todas la tienen).')

    # Reunión 13-oct (filas 50-52): un campo «Referencia (categoría)» y su
    # referencia muestran las MISMAS opciones — las líneas del menú
    # Referencias / Telas (se editan allá).
    ref_line_ids = fields.One2many(
        'safra.fabric.color', compute='_compute_ref_line_ids',
        string='Opciones (desde Referencias)')

    @api.depends('field_type', 'ref_category_id')
    def _compute_ref_line_ids(self):
        Color = self.env['safra.fabric.color'].sudo()
        for rec in self:
            rec.ref_line_ids = Color.search(
                [('fabric_id.category_id', '=', rec.ref_category_id.id)],
                order='fabric_id, name') if (
                rec.field_type == 'ref_categoria' and rec.ref_category_id) else Color

    def action_open_referencias(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Referencias de %s' % (self.ref_category_id.name or ''),
            'res_model': 'safra.fabric',
            'view_mode': 'list,form',
            'domain': [('category_id', '=', self.ref_category_id.id)],
            'context': {'default_category_id': self.ref_category_id.id},
        }

    @api.model
    def _setup_control_referencia(self):
        """Reunión 13-oct (fila 56): el campo Control se alimenta del menú
        Referencias / Telas (categoría «Control», marcada como de controles)
        y no de opciones escritas. Reusa una categoría «Control» existente.
        Idempotente; mientras no haya referencias de esa categoría el portal
        sigue usando los controles compatibles del maestro del motor."""
        Option = self.env['safra.product.option'].sudo().with_context(active_test=False)
        cat = Option.search([('type', '=', 'ref_categoria'), ('name', '=ilike', 'control')], limit=1)
        if not cat:
            cat = Option.create({'type': 'ref_categoria', 'name': 'Control', 'sequence': 90})
        if not cat.es_control:
            cat.es_control = True
        field = self.sudo().search([('code', '=', 'control')], limit=1)
        if field and field.field_type != 'ref_categoria':
            field.write({'field_type': 'ref_categoria', 'ref_category_id': cat.id})

    @api.model
    def _migrate_display_modes(self, _ids=None):
        """29-sep: el modo «Lista + foto grande» se eliminó — los campos
        que lo tenían pasan a «Lista con foto pequeña» (idempotente)."""
        self.env.cr.execute(
            "UPDATE safra_field SET display_mode = 'list_thumbs' "
            "WHERE display_mode = 'list_preview'")
    # Visibilidad restringida a un grupo de usuarios (ej: Exhibición).
    group_id = fields.Many2one(
        'res.groups', string='Grupo que lo ve', ondelete='set null',
        help='Si se define, el campo solo aparece en el cotizador para los '
             'usuarios que pertenecen a este grupo.',
    )

    system_ids = fields.Many2many(
        'safra.system', 'safra_system_field_rel', 'field_id', 'system_id',
        string='Sistemas que lo usan', compute='_compute_system_ids', store=False,
    )
    # Mapeos editables: permite asociar/retirar sistemas desde el propio campo
    # (hallazgo de pruebas: "no me deja editar los sistemas que lo usan").
    mapping_ids = fields.One2many('safra.system.field', 'field_id', string='Mapeos por sistema')

    def _compute_system_ids(self):
        Mapping = self.env['safra.system.field']
        for rec in self:
            maps = Mapping.search([('field_id', '=', rec.id)])
            rec.system_ids = maps.mapped('system_id')

    @api.model
    def _seed_acepta_atravesado(self, _ids=None):
        """Pendientes 24-sep (12.1): la aceptación del corte atravesado se
        asocia a todos los sistemas que tienen el campo Atravesar Tela,
        justo después de él (idempotente)."""
        field = self.search([('code', '=', 'acepta_atravesado')], limit=1)
        anchor = self.search([('code', '=', 'atravesar_tela')], limit=1)
        if not field or not anchor:
            return
        Mapping = self.env['safra.system.field'].sudo()
        for m in Mapping.with_context(active_test=False).search(
                [('field_id', '=', anchor.id)]):
            if not Mapping.with_context(active_test=False).search_count(
                    [('field_id', '=', field.id),
                     ('system_id', '=', m.system_id.id)]):
                Mapping.create({'system_id': m.system_id.id,
                                'field_id': field.id,
                                'sequence': m.sequence + 1,
                                'active': m.active})

    @api.model
    def _seed_motor_comentarios(self, _ids=None):
        """29-sep (16.2): el campo Comentarios va de último en la sección
        MOTOR de todos los sistemas que tienen el campo motor
        (idempotente)."""
        field = self.search([('code', '=', 'motor_comentarios')], limit=1)
        anchor = self.search([('code', '=', 'motor')], limit=1)
        if not field or not anchor:
            return
        Mapping = self.env['safra.system.field'].sudo()
        for m in Mapping.with_context(active_test=False).search(
                [('field_id', '=', anchor.id)]):
            if not Mapping.with_context(active_test=False).search_count(
                    [('field_id', '=', field.id),
                     ('system_id', '=', m.system_id.id)]):
                Mapping.create({'system_id': m.system_id.id,
                                'field_id': field.id,
                                'sequence': 9999,
                                'active': m.active})

    @api.model
    def _seed_coordinado_tela_options(self, _ids=None):
        """OBS REU GENERALES 11-sep: los campos «Coordinado Tela N» ofrecen
        las mismas opciones del Coordinado general (idempotente: solo copia
        las que falten)."""
        source = self.search([('code', '=', 'coordinado')], limit=1)
        if not source:
            return
        Option = self.env['safra.field.option']
        for field in self.search([('code', 'like', 'coordinado_tela_%')]):
            existing = set(field.option_ids.mapped('value'))
            for opt in source.option_ids:
                if opt.value not in existing:
                    Option.create({
                        'field_id': field.id, 'value': opt.value,
                        'name': opt.name, 'sequence': opt.sequence,
                    })

    @api.model
    def _seed_perfil_display(self, _ids=None):
        """Reunión 28-sep (fila 50): el Perfil lleva la misma presentación
        del Tipo de Plano — «Lista con foto pequeña» con zoom. Solo cambia
        los que siguen en automático (respeta lo que configure el
        funcional)."""
        for field in self.search([('code', 'in', ('perfil', 'perfil_sheer', 'perfileria2'))]):
            if field.display_mode in (False, 'auto'):
                field.display_mode = 'list_thumbs'

    # Bloque 3 (planos): segmentos requeridos por plano medidos en el portal
    # actual (Enrollable Premium): A-C habilitan 2, D-H habilitan 3.
    _PLANO_SEGMENTOS = {'A': 2, 'B': 2, 'C': 2,
                        'D': 3, 'E': 3, 'F': 3, 'G': 3, 'H': 3}

    @api.model
    def _seed_plano_segmentos(self, _ids=None):
        """Bloque 3 (3.2/3.3): siembra en cada opción de Tipo de Plano la
        cantidad de segmentos que habilita y su imagen (croquis tomado del
        portal actual), y convierte Número de segmento en desplegable 1..3
        (idempotente)."""
        Option = self.env['safra.field.option'].sudo()
        plano = self.search([('code', '=', 'tipo_plano')], limit=1)
        if plano:
            # El cliente pidió verlo como «Lista con foto pequeña» (8.3).
            if plano.display_mode in (False, 'auto'):
                plano.display_mode = 'list_thumbs'
            for opt in plano.option_ids:
                code = (opt.value or '').strip().upper()
                vals = {}
                if not opt.segmentos and self._PLANO_SEGMENTOS.get(code):
                    vals['segmentos'] = self._PLANO_SEGMENTOS[code]
                if not opt.image and code in self._PLANO_SEGMENTOS:
                    try:
                        with file_open('website_quotes_safra/static/src/img/'
                                       'planos/plano_tipo_%s.jpg' % code,
                                       'rb') as fh:
                            vals['image'] = base64.b64encode(fh.read())
                    except (IOError, OSError):
                        pass
                if vals:
                    opt.write(vals)
        seg = self.search([('code', '=', 'num_segmento')], limit=1)
        if seg:
            if seg.field_type != 'selection':
                seg.field_type = 'selection'
            existing = set(seg.option_ids.mapped('value'))
            for i in ('1', '2', '3'):
                if i not in existing:
                    Option.create({'field_id': seg.id, 'value': i,
                                   'name': i, 'sequence': int(i) * 10})


class SafraFieldOption(models.Model):
    _name = 'safra.field.option'
    _description = 'Opción de Campo del Cotizador'
    _order = 'sequence, id'

    field_id = fields.Many2one('safra.field', string='Campo', required=True, ondelete='cascade', index=True)
    value = fields.Char(string='Valor', required=True)
    name = fields.Char(string='Etiqueta', required=True, translate=True)
    sequence = fields.Integer(default=10)
    # Revisión 17-sep: imagen de referencia de la opción (tipos de apertura,
    # planos, perfiles…) — el portal la muestra como miniatura elegible.
    image = fields.Image(string='Imagen', max_width=512, max_height=512)
    # Apunte 23-sep: una opción del catálogo puede acotarse a ciertos
    # sistemas sin necesidad de duplicarla como override.
    system_ids = fields.Many2many(
        'safra.system', 'safra_field_option_system_rel', 'option_id', 'system_id',
        string='Sistemas (solo estos)',
        help='Si se llena, la opción solo se ofrece en estos sistemas; '
             'vacío = todos los que usan el campo.')
    # Parámetro numérico de la opción; hoy se usa para el peso del perfil
    # (g/m lineal) en la fórmula de peso máximo (hoja 3: Estandar 136,
    # Cuadrado 276, Lujo 346).
    peso_gm = fields.Float(string='Peso (g/m)', digits=(8, 2))
    # Bloque 3 (3.2): en las opciones de Tipo de Plano, cuántos segmentos
    # habilita el plano (el desplegable Número de segmento ofrece 1..N y la
    # validación del pedido exige que estén todos, sin repetir).
    segmentos = fields.Integer(
        string='Segmentos del plano',
        help='Solo para las opciones de Tipo de Plano: cantidad de segmentos '
             'que habilita el plano (A-C: 2, D-H: 3). El desplegable Número '
             'de segmento ofrece 1..N y el pedido debe traerlos todos.')


class SafraSystemField(models.Model):
    _name = 'safra.system.field'
    _description = 'Campo habilitado por Sistema'
    _order = 'system_id, sequence, id'

    _system_field_uniq = models.Constraint(
        'UNIQUE(system_id, field_id)',
        'El campo ya está configurado para este sistema.',
    )

    system_id = fields.Many2one('safra.system', string='Sistema', required=True, ondelete='cascade', index=True)
    field_id = fields.Many2one('safra.field', string='Campo', required=True, ondelete='cascade', index=True)
    section_id = fields.Many2one(related='field_id.section_id', string='Sección', store=True)
    sequence = fields.Integer(string='Orden', default=10)
    required = fields.Boolean(string='Requerido')
    active = fields.Boolean(default=True)

    # === Overrides por sistema ===
    # Un mismo campo (p. ej. perfil, cenefa, mando) se reusa entre sistemas pero
    # con etiqueta/ayuda/opciones/dependencias distintas. Estos campos permiten
    # esa personalización por sistema sin duplicar el campo global.
    label_override = fields.Char(string='Etiqueta (override)', translate=True)
    help_override = fields.Char(string='Ayuda (override)', translate=True)
    note_override = fields.Char(string='Nota (override)')
    highlight = fields.Boolean(string='Resaltar etiqueta')
    option_ids = fields.One2many('safra.system.field.option', 'system_field_id', string='Opciones (override)')
    depends_field_id = fields.Many2one('safra.field', string='Depende del campo (override)', ondelete='set null')
    depends_value = fields.Char(string='Valor que activa (override)')
    # Limpia la dependencia global del campo en este sistema (lo muestra siempre).
    clear_depends = fields.Boolean(string='Sin dependencia')


class SafraSystemFieldOption(models.Model):
    _name = 'safra.system.field.option'
    _description = 'Opción de Campo por Sistema'
    _order = 'sequence, id'

    system_field_id = fields.Many2one('safra.system.field', string='Campo del sistema', required=True, ondelete='cascade', index=True)
    value = fields.Char(string='Valor', required=True)
    name = fields.Char(string='Etiqueta', required=True, translate=True)
    sequence = fields.Integer(default=10)
    image = fields.Image(string='Imagen', max_width=512, max_height=512)
