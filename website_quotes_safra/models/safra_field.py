# -*- coding: utf-8 -*-
import base64

from markupsafe import Markup, escape

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import SQL, file_open

from .fields_vacio import FloatVacio, IntegerVacio
from .safra_panel import probar_formula



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
        ('ficha', 'FICHA TÉCNICA', ['unificacion_mando', 'sin_restricciones']),
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
          'tipo_plano', 'num_segmento', 'segmento_1', 'segmento_2',
          'curva_izquierda', 'curva_izquierda_m', 'curva_derecha',
          'curva_derecha_m', 'segmento_1_u', 'segmento_1_u_m', 'segmento_3',
          'segmento_3_m', 'profundidad_onda_c',
          'profundidad_onda', 'uso_riel', 'distribucion_lamas', 'pesa_lama',
          'tipo_entretela', 'bajofalso', 'gancho_cortinero', 'bastidor',
          'description']),
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


class SafraFieldAyuda(models.AbstractModel):
    """Pestaña «Ayuda de las fórmulas» de los formularios donde se
    escriben las fórmulas de las opciones."""
    _name = 'safra.ayuda.formulas.mixin'
    _description = 'Ayuda de las fórmulas de las opciones'

    ayuda_formulas = fields.Html(compute='_compute_ayuda_formulas', sanitize=False)

    def _compute_ayuda_formulas(self):
        ayuda = ayuda_formulas_html()
        for rec in self:
            rec.ayuda_formulas = ayuda


class SafraField(models.Model):
    _name = 'safra.field'
    _inherit = ['safra.ayuda.formulas.mixin']
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
        # Sprint 1.5 (fila 109): el bolsillo solo se ofrece en las telas que
        # lo permiten (marca de la referencia).
        ('bolsillo', 'Tela con bolsillo'),
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
        help="Valor del campo padre que activa este campo. Varios valores separados por coma.\n"
             "Prefijo '!' = ninguno de esos valores (ej: '!sin' = visible cuando el padre no es 'sin').\n"
             "ref:CÓDIGO = cualquier opción de esa referencia, en campos que salen de Referencias "
             "(ej: 'ref:CEN-TELA' = visible con cualquier cenefa de la referencia CEN-TELA).",
    )
    # Visibilidad según flag de la tela seleccionada.
    fabric_flag = fields.Selection(FABRIC_FLAGS, string='Requiere flag de tela')
    # Reunión 28-oct (fila 89): el campo se ofrece como lista con las telas
    # ya elegidas (antes solo «Tela de Cenefa» y «Tela Cabezal Forrado», por
    # código), para poder crear otros como «Tela de la cenefa en tela».
    opciones_telas = fields.Selection(
        [('color', 'Telas del pedido (referencia y color)'),
         ('referencia', 'Telas del pedido (solo referencia)')],
        string='Opciones: telas elegidas',
        help='El portal muestra el campo como lista con las telas ya elegidas en el pedido, '
             'con su color (como «Tela de Cenefa») o solo la referencia (como «Tela Cabezal '
             'Forrado»). Arranca con la primera. Vacío: el campo según su tipo.')
    # Barrido de la matriz (fila 124): orden en el resumen del pedido, como
    # el portal actual de Safra.
    resumen_sequence = fields.Integer(
        string='Orden en el resumen',
        help='Posición del campo en «Características» del resumen del pedido (menor primero). '
             '0: después de los que tienen orden, en el orden del formulario.')
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

    # Sprint 1.4 (tarea 12674, filas 79-96 de la matriz): sistemas en los
    # que va cada campo de Diseño de impresión, Cenefa y Perfil Cover Light.
    # Vertical Irregular (55) conserva el Tipo de Cenefa aunque la matriz no
    # lo marque: allí van la cenefa forrada, la tela y la dividida, que
    # dependen de él.
    _S14_DISENO = ['01', '06', '02', '10', '39', '11', '16', '32', '61', '40', '56']
    _S14_CENEFA = ['01', '10', '08', '11', '54', '31', '65', '40', '55', '41', '42', '63', '49', '57']
    _S14_PVC = ['01', '65', '40', '41', '42', '63', '49', '57']
    _S14_COVER = ['01', '06', '32', '61']
    SPRINT14_SISTEMAS = {
        'design_print': _S14_DISENO,
        'custom_design': _S14_DISENO,
        'design_exterior': [c for c in _S14_DISENO if c != '56'],
        'print_m2': _S14_DISENO,
        'cenefa_panel': _S14_CENEFA,
        'perfil_cenefa': ['10', '08', '11', '54', '31'],
        'cenefa_lateral': _S14_PVC,
        'cenefa_longitud': _S14_PVC,
        'cenefa_dividida': _S14_CENEFA,
        'cenefa_lined': ['01', '11', '54', '40', '55'],
        'cenefa_tela': _S14_CENEFA,
        'corte_cenefa': ['11', '54', '31', '65'],
        'color_cenefa': ['11', '54'],
        'cover_light_profile': _S14_COVER,
        'coverlight_felpa': _S14_COVER,
        'coverlight_45': _S14_COVER,
    }
    # Dependencias. Cada lista acepta los valores de las opciones de hoy y
    # las referencias de la categoría «Cenefa» por su código (ref:CÓDIGO),
    # así siguen funcionando cuando Safra cree esas referencias:
    # CEN-PVC (cenefas PVC), CEN-TELA (en tela) y CEN-MET (metálica).
    # Valores de hoy: 1 sin cenefa; 2, 4, 5, 6 formas de tela (en los
    # sistemas PVC el 2 es la PVC Moderna); 3 metálica o PVC Clásica.
    # Sprint 1.7: las cenefas de hoy son líneas de una misma referencia
    # (054328), así que además se reconocen por su etiqueta (eti:).
    _S14_TELA = '2,4,5,6,ref:CEN-TELA,eti:Cenefa en tela'
    _S14_CON = ('2,3,4,5,6,ref:CEN-PVC,ref:CEN-TELA,ref:CEN-MET,'
                'eti:PVC CLASICA,eti:METALICA,eti:Cenefa en tela')
    _S14_PVC = '2,3,ref:CEN-PVC,eti:PVC CLASICA'
    _S14_MET = '3,ref:CEN-MET,eti:METALICA'
    SPRINT14_DEPENDS = {
        'perfil_cenefa': ('cenefa_panel', _S14_TELA),
        'cenefa_lateral': ('cenefa_panel', _S14_PVC),
        'cenefa_longitud': ('cenefa_lateral', 'izquierdo,derecho,ambos'),
        'cenefa_dividida': ('cenefa_panel', _S14_CON),
        'cenefa_lined': ('cenefa_panel', _S14_CON),
        'cenefa_tela': ('cenefa_lined', '1'),
        'corte_cenefa': ('cenefa_panel', _S14_TELA),
        'color_cenefa': ('cenefa_panel', _S14_CON),
        # Ajustes 20-oct (fila 94): el Cover Light sale de Referencias y sus
        # tres líneas comparten producto: la condición va por la etiqueta.
        'coverlight_felpa': ('cover_light_profile', 'dos_laterales_5cm,eti:2 lateral,eti:2 laterales'),
        'coverlight_45': ('cover_light_profile', 'tres_laterales_5cm,eti:3 lateral,eti:3 laterales'),
    }
    # Por sistema: en los paneles la forrada va con la cenefa metálica
    # (fila 89, obs 2). Donde no hay «¿Cenefa forrada?», la tela de la
    # cenefa se pide cuando la cenefa es de tela.
    SPRINT14_DEPENDS_SISTEMA = {
        ('cenefa_lined', '11'): ('cenefa_panel', _S14_MET),
        ('cenefa_lined', '54'): ('cenefa_panel', _S14_MET),
    }
    # Valores que dejaron en las condiciones de cenefa los archivos de
    # datos de sprints anteriores y las versiones del Sprint 1.4. Solo esos
    # se reemplazan al actualizar; cualquier otro lo puso el funcional.
    _S14_VALORES_VIEJOS = {'tela', '!sin', '2', '!1', '2,4,5,6', '2,4,5,6,3'}
    _S14_VALORES_MODULO = _S14_VALORES_VIEJOS | {
        _S14_TELA, _S14_CON, _S14_PVC, _S14_MET,
        # Valores del Sprint 1.4 antes de las etiquetas (Sprint 1.7).
        '2,4,5,6,ref:CEN-TELA', '2,3,4,5,6,ref:CEN-PVC,ref:CEN-TELA,ref:CEN-MET',
        '2,3,ref:CEN-PVC', '3,ref:CEN-MET',
        'dos_laterales_5cm', 'tres_laterales_5cm'}
    SPRINT14_NOMBRES = {
        'cenefa_lateral': 'Laterales Cenefa',
        'cenefa_longitud': 'Tamaño Laterales Cenefa',
        'cenefa_dividida': '¿Cenefa dividida?',
        'cenefa_lined': '¿Cenefa forrada?',
        'cenefa_tela': 'Tela de Cenefa',
    }

    @api.model
    def _apply_sprint14(self, _ids=None):
        """Sprint 1.4: deja Diseño de impresión, Cenefa y Perfil Cover Light
        como la matriz (filas 79-96). Corre en cada actualización del módulo
        (va de último en el manifiesto) porque los archivos de datos de cada
        sistema se vuelven a aplicar y desharían estos cambios, p. ej.
        safra_panel_japones.xml archiva la cenefa forrada del panel. Es
        idempotente. Los campos que sobran en un sistema se archivan, no se
        borran."""
        Field = self.sudo().with_context(active_test=False)
        Mapping = self.env['safra.system.field'].sudo().with_context(active_test=False)
        SysOption = self.env['safra.system.field.option'].sudo()
        systems = {s.code: s for s in self.env['safra.system'].sudo().with_context(
            active_test=False).search([])}

        def campo(code):
            return Field.search([('code', '=', code)], limit=1)

        # 1. Tipo de Cenefa desde Referencias (filas 83 y 89): categoría
        # «Cenefa». Sin referencias de esa categoría el campo sigue con las
        # opciones de hoy.
        Option = self.env['safra.product.option'].sudo().with_context(active_test=False)
        cat = Option.search([('type', '=', 'ref_categoria'), ('name', '=ilike', 'cenefa')], limit=1)
        if not cat:
            cat = Option.create({'type': 'ref_categoria', 'name': 'Cenefa', 'sequence': 60})
        tipo = campo('cenefa_panel')
        if tipo:
            tipo.write({'field_type': 'ref_categoria', 'ref_category_id': cat.id,
                        'name': 'Tipo de Cenefa'})

        # 2. Sistemas de cada campo.
        for code, codigos in self.SPRINT14_SISTEMAS.items():
            field = campo(code)
            if not field:
                continue
            if not field.active:
                field.active = True
            mappings = Mapping.search([('field_id', '=', field.id)])
            for m in mappings:
                deberia = m.system_id.code in codigos
                if m.active != deberia:
                    m.active = deberia
            presentes = set(mappings.mapped('system_id.code'))
            orden = max(mappings.mapped('sequence') or [field.sequence or 10])
            for c in codigos:
                if c not in presentes and c in systems:
                    Mapping.create({'system_id': systems[c].id, 'field_id': field.id,
                                    'sequence': orden})

        # 3. Dependencias: las del campo, sin las de cada sistema que
        # quedaron apuntando a campos retirados (p. ej. «Cenefa PVC»).
        # Reunión 15-oct: Safra configura las cenefas con sus propios
        # códigos (una referencia, atributos por clase), así que solo se
        # escriben las condiciones vacías o con un valor que dejó el módulo;
        # las que editó el funcional no se tocan.
        def sembrar(rec, parent, valor):
            actual = (rec.depends_value or '').strip()
            if actual and actual not in self._S14_VALORES_MODULO:
                return
            if (rec.depends_field_id, actual) != (parent, valor):
                rec.write({'depends_field_id': parent.id, 'depends_value': valor})

        for code, (padre, valor) in self.SPRINT14_DEPENDS.items():
            field, parent = campo(code), campo(padre)
            if field and parent:
                sembrar(field, parent, valor)
                Mapping.search([('field_id', '=', field.id)]).filtered(
                    lambda m: (m.depends_field_id and not m.depends_field_id.active)
                    or (m.depends_value or '').strip() in self._S14_VALORES_VIEJOS
                ).write({'depends_field_id': False, 'depends_value': False,
                         'clear_depends': False})
        con_forrada = set(self.SPRINT14_SISTEMAS['cenefa_lined'])
        tela = campo('cenefa_tela')
        for m in Mapping.search([('field_id', '=', tela.id)]) if tela else []:
            if m.system_id.code not in con_forrada:
                sembrar(m, campo('cenefa_panel'), self._S14_TELA)
        for (code, sistema), (padre, valor) in self.SPRINT14_DEPENDS_SISTEMA.items():
            field, parent = campo(code), campo(padre)
            m = Mapping.search([('field_id', '=', field.id),
                                ('system_id.code', '=', sistema)], limit=1)
            if m and parent:
                sembrar(m, parent, valor)

        # 4. Nombres sin «PVC» en los campos que son de cualquier cenefa.
        for code, nombre in self.SPRINT14_NOMBRES.items():
            field = campo(code)
            if field:
                field.name = nombre
                Mapping.search([('field_id', '=', field.id)]).write({'label_override': False})

        # 5. Opciones del Tipo de Cenefa por sistema. La unificación de
        # septiembre copió las opciones de Cenefa PVC a todos los sistemas:
        # los paneles vuelven a las del campo (formas de tela y metálica) y
        # las Romanas a «Sin cenefa / Cenefa Tela» (fila 83).
        if tipo:
            for m in Mapping.search([('field_id', '=', tipo.id),
                                     ('system_id.code', 'in', ['11', '54'])]):
                m.option_ids.unlink()
            for m in Mapping.search([('field_id', '=', tipo.id),
                                     ('system_id.code', 'in', ['08', '10'])]):
                m.option_ids.unlink()
                SysOption.create([
                    {'system_field_id': m.id, 'value': '1', 'name': 'Sin Cenefa', 'sequence': 10},
                    {'system_field_id': m.id, 'value': '2', 'name': 'Cenefa Tela', 'sequence': 20},
                ])
        # Laterales de la Cenefa PVC repetía las opciones del campo: sin la
        # copia, cada opción se asocia a sus sistemas desde el catálogo.
        lateral = campo('cenefa_lateral')
        if lateral:
            Mapping.search([('field_id', '=', lateral.id)]).option_ids.unlink()

        # 6. Orden de la matriz dentro de cada sección, en cada sistema (el
        # de cada archivo de sistema dejaba, p. ej., el Tamaño de laterales
        # antes del Tipo de Cenefa en el Enrollable).
        orden = list(self.SPRINT14_SISTEMAS)
        for sistema in systems.values():
            mappings = Mapping.search([('system_id', '=', sistema.id),
                                       ('field_id.code', 'in', orden)])
            if not mappings:
                continue
            base = min(mappings.mapped('sequence'))
            for m in mappings.sorted(lambda m: orden.index(m.field_id.code)):
                m.sequence = base + orden.index(m.field_id.code)

        # 7. «Sin Cenefa» era una copia errada en el Perfil Cover Light.
        cover = campo('cover_light_profile')
        if cover:
            cover.option_ids.filtered(lambda o: o.value == 'sin').write({'name': 'Sin Cover Light'})
        return True

    # Sprint 1.5 (tarea 12675, filas 97-121 de la matriz): Riel, Cordón /
    # Cadena / Bastón y Otras opciones.
    # Fila 97: Posición Telo Fijo según la apertura (valores de Panel
    # Japonés y Riel Armado: 1 Derecha, 2 Izquierda, 3 Extremos, 4 Centro,
    # 5 Libre). Panel Duo solo tiene «Doble función»: solo Frente.
    SPRINT15_TELO_FIJO = [
        ('1', 'Frente', '1,2,3,4'),
        ('2', 'Atrás', '1,2,3,4'),
        ('3', 'Centro frente', '4'),
        ('4', 'Centro atrás', '4'),
        ('ninguno', 'Ninguno', '5'),
    ]
    # Fila 99: rieles de la matriz para Panel Duo y Riel Armado (Panel
    # Japonés conserva además el Riel Suizo, pendiente con Safra).
    SPRINT15_RIELES = [('0', 'Auto'), ('1', '4 Vías'), ('2', '5 Vías'),
                       ('3', '6 Vías'), ('6', 'Riel Velcrado')]
    # Fila 106 (con la fila 77): mandos por sistema. Bastón (4) y Doble
    # Bastón (5) habilitan la Longitud bastón.
    _S15_MANDO_BASTON = [('1', 'Derecho'), ('2', 'Izquierdo'), ('4', 'Bastón'),
                         ('5', 'Doble Bastón')]
    SPRINT15_MANDOS = {
        '11': _S15_MANDO_BASTON + [('3', 'Doble Mando')],
        '15': _S15_MANDO_BASTON + [('3', 'Doble Mando')],
        '49': _S15_MANDO_BASTON,
        '57': _S15_MANDO_BASTON,
        '58': _S15_MANDO_BASTON,
    }
    SPRINT15_BASTON = '4,5'
    # Filas 99, 106, 110 y 119: opciones desde el menú Referencias. Sin
    # referencias de la categoría el campo conserva sus opciones de hoy.
    SPRINT15_CATEGORIAS = {
        'riel_tipo': 'Riel',
        'longitud_baston': 'Bastón',
        'abrazadera': 'Abrazadera',
        'gancho_cortinero': 'Gancho',
        # Sprint 1.6: Safra maneja la Pesa lama y la Entretela como referencias.
        'pesa_lama': 'Pesa lama',
        'tipo_entretela': 'Entretela',
        # Ajustes 20-oct (filas 94 y 95): Cover Light y Felpa desde
        # Referencias (consumo y disponibilidad del material).
        'cover_light_profile': 'Cover Light',
        'coverlight_felpa': 'Felpa',
    }
    # Filas 100 y 115: de texto a lista desplegable.
    SPRINT15_LISTAS = {
        'riel_junto': [('0', 'No'), ('1', 'Item Siguiente'), ('2', 'Item Anterior')],
        'distribucion_lamas': [('uno_a_uno', 'Uno a Uno'), ('dos_a_dos', 'Dos a Dos')],
    }
    SPRINT15_NOMBRES = {
        'riel_tipo': 'Tipo de Riel',
        'extra_chain': 'Extra Cadena/Cordón',
        'bastidor': '¿Lleva Bastidor?',
    }
    # Fila 112: en las cortinas los segmentos salen del Riel curvo; el
    # «Segmento» de los planos A-H no aplica.
    SPRINT15_SIN_SEGMENTO = ['49', '57']

    # Fila 118 (Dobladillo o Bajo falso): cada opción se ofrece según el
    # alto y el ancho del rollo, con las palabras y medidas de la
    # descripción de la matriz (dobladillo superior 6 cm, dobladillo
    # inferior según la opción, riel y rodachina 3,5 cm, bajo falso hasta
    # + 12 cm). Los dobladillos se restan del rollo: la tela que gastan no
    # queda para el alto. La observación de la Revisión Sprint 1 pide que
    # los valores se puedan editar: el funcional los ajusta en el Catálogo
    # de campos. Sin ancho de rollo cargado se ofrecen los dobladillos
    # como antes.
    _S15_DOBLADILLO = (
        "# Fila 118: Alto real <= ancho de rollo - (dobladillo superior\n"
        "# + dobladillo inferior - tamaño riel y rodachina)\n"
        "dobladillo_superior = 0.06   # estándar 6 cm\n"
        "dobladillo_inferior = %s   # %s\n"
        "riel_rodachina = 0.035       # 3,5 cm\n"
        "bajo_falso = 0.12            # 12 cm\n"
        "# Sin ancho de rollo (U_Ancho) cargado, la opción se ofrece siempre.\n"
        "# Reunión 22-oct: con corte por paños (alto > rollo + bajo falso) también\n"
        "# se elige el dobladillo.\n"
        "result = not ancho_rollo or alto <= ancho_rollo - (dobladillo_superior + dobladillo_inferior - riel_rodachina) or alto > ancho_rollo + bajo_falso")
    SPRINT15_DOBLADILLO = [
        ('BN_FLTE', 'Bajo filete', _S15_DOBLADILLO % ('0.06', 'Bajo filete: 6 cm')),
        ('BN_03', 'Dobladillo de 3 cm', _S15_DOBLADILLO % ('0.07', 'Dobladillo 3 cm: 7 cm')),
        ('BN_10', 'Dobladillo de 10 cm', _S15_DOBLADILLO % ('0.15', 'Dobladillo 10 cm: 15 cm')),
        ('BN_15', 'Dobladillo de 15 cm', _S15_DOBLADILLO % ('0.21', 'Dobladillo 15 cm: 21 cm')),
        ('BN_FALSO', 'Bajo falso',
         "# Fila 118: no cabe ningún dobladillo (ni el bajo filete) y\n"
         "# el Alto real es menor o igual al ancho del rollo + 12 cms\n"
         "dobladillo_superior = 0.06   # estándar 6 cm\n"
         "bajo_filete = 0.06           # 6 cm\n"
         "riel_rodachina = 0.035       # 3,5 cm\n"
         "bajo_falso = 0.12            # 12 cm\n"
         "result = bool(ancho_rollo) and alto > ancho_rollo - (dobladillo_superior + bajo_filete - riel_rodachina) and alto <= ancho_rollo + bajo_falso"),
        ('BN_PANOS', 'Corte por paños',
         "# Fila 118: cuando no es ninguna de las anteriores es corte de paños\n"
         "bajo_falso = 0.12            # 12 cm\n"
         "result = bool(ancho_rollo) and alto > ancho_rollo + bajo_falso"),
    ]
    # Primera versión sembrada (constantes sueltas): pasan a la de arriba
    # solo si nadie las editó.
    _S15_DOBLADILLO_ANTERIOR = {
        'BN_FLTE': 'not ancho_rollo or alto <= ancho_rollo - 0.085',
        'BN_03': 'not ancho_rollo or alto <= ancho_rollo - 0.095',
        'BN_10': 'not ancho_rollo or alto <= ancho_rollo - 0.175',
        'BN_15': 'not ancho_rollo or alto <= ancho_rollo - 0.235',
        'BN_FALSO': 'ancho_rollo and ancho_rollo - 0.085 < alto <= ancho_rollo + 0.12',
        'BN_PANOS': 'ancho_rollo and alto > ancho_rollo + 0.12',
    }

    @api.model
    def _seed_formulas_dobladillo(self, _ids=None):
        """Sprint 1.5 (fila 118): una sola vez, deja las fórmulas iniciales
        en las opciones del Dobladillo o Bajo falso y crea «Bajo falso» y
        «Corte por paños». Después las administra el funcional: una
        actualización no pisa lo que se edite (solo pasa a la forma de la
        matriz las de la primera versión que nadie cambió)."""
        Param = self.env['ir.config_parameter'].sudo()
        marca = 'website_quotes_safra.seed_formulas_dobladillo'
        field = self.sudo().with_context(active_test=False).search([('code', '=', 'bajofalso')], limit=1)
        if not field:
            return
        por_valor = {o.value: o for o in field.option_ids}
        if Param.get_param(marca):
            for value, _name, formula in self.SPRINT15_DOBLADILLO:
                opt = por_valor.get(value)
                if opt and (opt.formula or '').strip() == self._S15_DOBLADILLO_ANTERIOR[value]:
                    opt.formula = formula
            return
        for i, (value, name, formula) in enumerate(self.SPRINT15_DOBLADILLO):
            if value in por_valor:
                por_valor[value].formula = formula
            else:
                self.env['safra.field.option'].sudo().create({
                    'field_id': field.id, 'value': value, 'name': name,
                    'formula': formula, 'sequence': (i + 1) * 10})
        Param.set_param(marca, '1')

    @api.model
    def _apply_sprint15(self, _ids=None):
        """Sprint 1.5: deja Riel, Cordón / Cadena / Bastón y Otras opciones
        como la matriz (filas 97-121). Corre en cada actualización (va de
        último en el manifiesto) porque los archivos de cada sistema
        vuelven a imponer etiquetas, opciones y activos. Es idempotente."""
        Field = self.sudo().with_context(active_test=False)
        Mapping = self.env['safra.system.field'].sudo().with_context(active_test=False)
        SysOption = self.env['safra.system.field.option'].sudo()
        Option = self.env['safra.field.option'].sudo()
        Categoria = self.env['safra.product.option'].sudo().with_context(active_test=False)

        def campo(code):
            return Field.search([('code', '=', code)], limit=1)

        def mapeos(field, sistemas=None):
            dom = [('field_id', '=', field.id)]
            if sistemas is not None:
                dom.append(('system_id.code', 'in', sistemas))
            return Mapping.search(dom)

        def opciones_sistema(mapping, opciones):
            actuales = [(o.value, o.name) for o in mapping.option_ids]
            if actuales != list(opciones):
                mapping.option_ids.unlink()
                SysOption.create([{'system_field_id': mapping.id, 'value': v,
                                   'name': n, 'sequence': (i + 1) * 10}
                                  for i, (v, n) in enumerate(opciones)])

        def opciones_campo(field, opciones):
            """Deja en el catálogo exactamente estas opciones (por valor)."""
            por_valor = {o.value: o for o in field.option_ids}
            for i, item in enumerate(opciones):
                value, name = item[0], item[1]
                vals = {'name': name, 'sequence': (i + 1) * 10}
                if len(item) > 2:
                    vals.update(depends_field_id=item[2].id, depends_value=item[3])
                if value in por_valor:
                    por_valor[value].write(vals)
                else:
                    Option.create(dict(vals, field_id=field.id, value=value))
            field.option_ids.filtered(
                lambda o: o.value not in {item[0] for item in opciones}).unlink()

        # 1. Categorías de referencia (filas 99, 106, 110, 119). La de rieles
        # muestra las columnas Canales y Velcrado en sus líneas.
        # Si Safra ya le asignó al campo otra categoría, se conserva: el
        # archivo del campo solo devuelve el tipo a «Lista desplegable».
        for code, nombre in self.SPRINT15_CATEGORIAS.items():
            field = campo(code)
            cat = field.ref_category_id if field and field.ref_category_id.type == 'ref_categoria' else False
            if not cat:
                cat = Categoria.search([('type', '=', 'ref_categoria'), ('name', '=ilike', nombre)], limit=1)
            if not cat:
                cat = Categoria.create({'type': 'ref_categoria', 'name': nombre, 'sequence': 95})
            if code == 'riel_tipo' and not cat.es_riel:
                cat.es_riel = True
            if field and (field.field_type != 'ref_categoria' or field.ref_category_id != cat):
                field.write({'field_type': 'ref_categoria', 'ref_category_id': cat.id})

        # 2. Nombres de la matriz, sin las etiquetas distintas por sistema
        # (fila 104: «Cordón Extra», «Altura Cadena…»).
        for code, nombre in self.SPRINT15_NOMBRES.items():
            field = campo(code)
            if field:
                field.name = nombre
                mapeos(field).filtered('label_override').write({'label_override': False})

        # 3. Posición Telo Fijo (fila 97).
        telo, apertura = campo('posicion_telo'), campo('apertura')
        if telo and apertura:
            opciones_campo(telo, [(v, n, apertura, dep) for v, n, dep in self.SPRINT15_TELO_FIJO])
            for m in mapeos(telo, ['54']):
                opciones_sistema(m, [('1', 'Frente')])

        # 4. Tipo de Riel (fila 99): opciones de la matriz en Panel Duo y
        # Riel Armado (que mostraba solo «Velcrado»).
        riel = campo('riel_tipo')
        if riel:
            for m in mapeos(riel, ['54', '15']):
                opciones_sistema(m, self.SPRINT15_RIELES)

        # 5. Listas desplegables (filas 100 y 115).
        for code, opciones in self.SPRINT15_LISTAS.items():
            field = campo(code)
            if not field:
                continue
            if field.field_type != 'selection':
                field.field_type = 'selection'
            opciones_campo(field, opciones)
            mapeos(field).option_ids.unlink()

        # 6. Mando y Longitud bastón (filas 77 y 106).
        mando, baston = campo('mando_position'), campo('longitud_baston')
        if mando:
            for m in mapeos(mando, list(self.SPRINT15_MANDOS)):
                if not m.active:
                    m.active = True
                opciones_sistema(m, self.SPRINT15_MANDOS[m.system_id.code])
        if baston and mando:
            baston.write({'depends_field_id': mando.id, 'depends_value': self.SPRINT15_BASTON})
            mapeos(baston).write({'depends_field_id': False, 'depends_value': False,
                                  'clear_depends': False})

        # 7. Bolsillo solo en las telas que lo permiten (fila 109).
        bolsillo = campo('bolsillo_size')
        if bolsillo and bolsillo.fabric_flag != 'bolsillo':
            bolsillo.fabric_flag = 'bolsillo'

        # 8. Cortinas: el Segmento de los planos A-H no aplica (fila 112).
        segmento = campo('num_segmento')
        if segmento:
            mapeos(segmento, self.SPRINT15_SIN_SEGMENTO).filtered('active').write({'active': False})

        # 9. Comentarios (fila 121) como campo del catálogo en todos los
        # sistemas, al final de OTRAS OPCIONES.
        comentarios = campo('description')
        if comentarios:
            presentes = set(mapeos(comentarios).mapped('system_id').ids)
            sistemas = self.env['safra.system'].sudo().with_context(active_test=False).search([])
            Mapping.create([{'system_id': s.id, 'field_id': comentarios.id, 'sequence': 5000}
                            for s in sistemas if s.id not in presentes])
        return True

    @api.model
    def _apply_15oct(self, _ids=None):
        """Reunión 15-oct (fila 74): «Pedido sin restricciones» va en la
        FICHA TÉCNICA de todos los sistemas, visible solo para el grupo que
        lo autoriza. Idempotente; corre en cada actualización."""
        campo = self.sudo().with_context(active_test=False).search(
            [('code', '=', 'sin_restricciones')], limit=1)
        if not campo:
            return True
        seccion = self.env['safra.field.section'].sudo().search([('code', '=', 'ficha')], limit=1)
        grupo = self.env.ref('website_quotes_safra.group_safra_sin_restricciones')
        vals = {'group_id': grupo.id}
        if seccion and campo.section_id != seccion:
            vals['section_id'] = seccion.id
        campo.write(vals)
        Mapping = self.env['safra.system.field'].sudo().with_context(active_test=False)
        presentes = set(Mapping.search([('field_id', '=', campo.id)]).mapped('system_id').ids)
        sistemas = self.env['safra.system'].sudo().with_context(active_test=False).search([])
        Mapping.create([{'system_id': s.id, 'field_id': campo.id, 'sequence': 4000}
                        for s in sistemas if s.id not in presentes])
        return True

    @api.model
    def _ajuste_unificar_verificacion(self):
        """Reunión 09-nov (fila 74): «Pedido sin restricciones» se unifica
        con «Requiere verificación de fabricación», que queda como el único
        campo: el de la persiana se archiva (sale del portal; las
        cotizaciones que ya lo tienen siguen su flujo) y quien podía pedirlo
        pasa a poder marcar la verificación. Una sola vez por base."""
        campo = self.sudo().search([('code', '=', 'sin_restricciones')])
        campo.write({'active': False})
        viejo = self.env.ref('website_quotes_safra.group_safra_sin_restricciones', raise_if_not_found=False)
        nuevo = self.env.ref('website_quotes_safra.group_safra_verificacion', raise_if_not_found=False)
        if viejo and nuevo:
            faltan = viejo.sudo().user_ids - nuevo.sudo().user_ids
            if faltan:
                nuevo.sudo().write({'user_ids': [(4, u.id) for u in faltan]})
        return True

    @api.model
    def _apply_sprint16(self, _ids=None):
        """Sprint 1.6 (fila 76, reunión 17-sep): la Orientación del enrollado
        es una lista con la imagen junto a cada opción y, al elegir, se ve
        la imagen. Una sola vez por base: después se cambia en el Catálogo
        de campos."""
        Param = self.env['ir.config_parameter'].sudo()
        marca = 'website_quotes_safra.sprint16_orientacion'
        if Param.get_param(marca):
            return True
        self.sudo().search([('code', '=', 'orientation'), ('display_mode', '=', 'auto')]).write(
            {'display_mode': 'list_thumbs'})
        Param.set_param(marca, '1')
        return True

    # === Ajustes Sprint 1.4 (reunión 20-oct) y Sprint 1.5 (reunión 22-oct) ===
    # Fórmulas de las opciones que se eligen solas, con su aviso. Se siembran
    # una sola vez y solo si la opción no tiene ya una: después las administra
    # el funcional en el Catálogo de campos.
    AJUSTES_1415_AUTO = {
        # Fila 88: la cenefa va dividida si el ancho supera el máximo de la
        # cenefa (U_AnchoMax del producto) o, en tela, el ancho del rollo.
        ('cenefa_dividida', '1'): (
            "# Fila 88: si el ancho supera el ancho máximo de la cenefa, va dividida.\n"
            "# ancho_max_cenefa_panel es el U_AnchoMax del producto de la cenefa\n"
            "# elegida (p. ej. PVC 3 m); sin ese dato se usa el ancho del rollo.\n"
            "maximo = ancho_max_cenefa_panel or ancho_rollo\n"
            "result = bool(maximo) and ancho > maximo",
            'Recuerde que su cenefa va a ir dividida: el ancho supera el ancho máximo de la cenefa.'),
        # Fila 91: si el ancho supera el rollo y la tela no permite cenefa
        # entera, la cenefa va añadida.
        ('corte_cenefa', '1'): (
            "# Fila 91: el ancho supera el ancho del rollo (U_Ancho) y la tela no\n"
            "# permite cenefa entera (Referencias / Telas): la cenefa va añadida.\n"
            "result = bool(ancho_rollo) and ancho > ancho_rollo and not tela_permite_cenefa_entera",
            'El ancho de la persiana excede el ancho del rollo: la cenefa va añadida.'),
        # Fila 102: el riel va dividido si el ancho supera el máximo del riel.
        ('traslape_centro', '2'): (
            "# Fila 102: si el ancho supera el ancho máximo del riel, va dividido.\n"
            "# ancho_max_riel_tipo es el U_AnchoMax del riel elegido (paneles); en\n"
            "# las cortinas el riel no se elige: 5,80 m manual y 6,00 m motorizado.\n"
            "riel_max = ancho_max_riel_tipo or ((6.00 if motorizado else 5.80) if sistema in ('49', '57', '58') else 0)\n"
            "result = bool(riel_max) and ancho > riel_max",
            'El riel será dividido porque el ancho supera el ancho máximo del riel.'),
    }
    # Fila 91: «Cenefa Entera» se ofrece por debajo del rollo o con telas que
    # la permiten.
    AJUSTES_1415_FORMULA = {
        ('corte_cenefa', '2'): (
            "# Fila 91: entera si el ancho no supera el rollo, o si la tela\n"
            "# permite cenefa entera (con cobro adicional, sprint de precios).\n"
            "result = not ancho_rollo or ancho <= ancho_rollo or tela_permite_cenefa_entera"),
    }
    # Fila 118 (reunión 22-oct): el corte por paños no se elige, es un aviso.
    AVISO_PANOS = ('Esta tela se corta por paños: el alto supera el ancho del rollo '
                   'más el bajo falso. Elija el dobladillo.')
    # Versión anterior de las fórmulas de los dobladillos (sin el corte por
    # paños), para pasar a la nueva las que nadie editó.
    _S15_DOBLADILLO_V2 = (
        "# Fila 118: Alto real <= ancho de rollo - (dobladillo superior\n"
        "# + dobladillo inferior - tamaño riel y rodachina)\n"
        "dobladillo_superior = 0.06   # estándar 6 cm\n"
        "dobladillo_inferior = %s   # %s\n"
        "riel_rodachina = 0.035       # 3,5 cm\n"
        "# Sin ancho de rollo (U_Ancho) cargado, la opción se ofrece siempre.\n"
        "result = not ancho_rollo or alto <= ancho_rollo - (dobladillo_superior + dobladillo_inferior - riel_rodachina)")
    # Fila 101 (reunión 22-oct): en el Plano U los extremos son el Segmento 1
    # y el Segmento 3 (curva de 30, 50 o más de 50 cm con su medida).
    AJUSTES_1415_SEGMENTOS = [
        # (código, nombre, tipo, padre, valor que activa, secuencia)
        ('segmento_1_u', 'Segmento 1', 'selection', 'tipoplano_cortina', 'U', 1211),
        ('segmento_1_u_m', 'Medida segmento 1', 'float', 'segmento_1_u', 'mas', 1212),
        ('segmento_3', 'Segmento 3', 'selection', 'tipoplano_cortina', 'U', 1214),
        ('segmento_3_m', 'Medida segmento 3', 'float', 'segmento_3', 'mas', 1215),
    ]
    OPCIONES_CURVA_U = [('0.30', '30 cm'), ('0.50', '50 cm'), ('mas', 'Más de 50 cm')]

    @api.model
    def _migrar_felpa(self, _ids=None):
        """Ajustes 20-oct (fila 95): «¿Coverlight con Felpa?» pasó de casilla
        a Referencias; la casilla marcada queda como «Sí» (valor 1 del
        respaldo) y la desmarcada vacía. Idempotente."""
        cr = self.env.cr
        cr.execute("""SELECT column_name FROM information_schema.columns
                      WHERE table_name = 'safra_quote_line'
                        AND column_name LIKE 'coverlight_felpa_moved%'""")
        for (columna,) in cr.fetchall():
            cr.execute(SQL('UPDATE safra_quote_line SET coverlight_felpa = %s '
                           'WHERE %s IS TRUE AND coverlight_felpa IS NULL',
                           '1', SQL.identifier(columna)))
            cr.execute(SQL('ALTER TABLE safra_quote_line DROP COLUMN %s', SQL.identifier(columna)))
        # Si Odoo convirtió la columna en texto, quedó «true» / «false».
        cr.execute("""UPDATE safra_quote_line SET coverlight_felpa = CASE
                          WHEN coverlight_felpa = 'true' THEN '1' ELSE NULL END
                      WHERE coverlight_felpa IN ('true', 'false')""")
        return True

    @api.model
    def _apply_ajustes_1415(self, _ids=None):
        """Ajustes Sprint 1.4 (20-oct) y 1.5 (22-oct). Una sola vez por base;
        respeta lo que el funcional ya haya configurado: solo llena las
        fórmulas vacías y reutiliza los campos que ya existan con el mismo
        código (p. ej. un «segmento_3» creado a mano)."""
        Param = self.env['ir.config_parameter'].sudo()
        marca = 'website_quotes_safra.ajustes_1415'
        if Param.get_param(marca):
            return True
        Field = self.sudo().with_context(active_test=False)
        Option = self.env['safra.field.option'].sudo()

        def campo(code):
            return Field.search([('code', '=', code)], limit=1)

        def opcion(code, valor):
            field = campo(code)
            return field.option_ids.filtered(lambda o: o.value == valor)[:1] if field else Option

        # 1. Opciones que se eligen solas (filas 88, 91 y 102).
        for (code, valor), (formula, aviso) in self.AJUSTES_1415_AUTO.items():
            opt = opcion(code, valor)
            if opt and not opt.auto_formula:
                opt.write({'auto_formula': formula, 'aviso': opt.aviso or aviso})
        for (code, valor), formula in self.AJUSTES_1415_FORMULA.items():
            opt = opcion(code, valor)
            if opt and not opt.formula:
                opt.formula = formula

        # 2. Fila 118: corte por paños como aviso; los dobladillos también se
        # eligen con corte por paños (solo los que nadie editó).
        panos = opcion('bajofalso', 'BN_PANOS')
        if panos and not panos.solo_aviso:
            panos.write({'solo_aviso': True, 'aviso': panos.aviso or self.AVISO_PANOS})
        dobladillo = campo('bajofalso')
        nuevas = {v: f for v, _n, f in self.SPRINT15_DOBLADILLO}
        medidas = {'BN_FLTE': ('0.06', 'Bajo filete: 6 cm'), 'BN_03': ('0.07', 'Dobladillo 3 cm: 7 cm'),
                   'BN_10': ('0.15', 'Dobladillo 10 cm: 15 cm'), 'BN_15': ('0.21', 'Dobladillo 15 cm: 21 cm')}
        for opt in dobladillo.option_ids if dobladillo else Option:
            if opt.value in medidas and (opt.formula or '').strip() == self._S15_DOBLADILLO_V2 % medidas[opt.value]:
                opt.formula = nuevas[opt.value]

        # 3. Fila 101: Segmento 1 y Segmento 3 del Plano U.
        plano = campo('tipoplano_cortina')
        seccion = campo('segmento_2').section_id or plano.section_id
        creados = {}
        for code, nombre, tipo, padre, valor, _seq in self.AJUSTES_1415_SEGMENTOS:
            field = campo(code)
            padre_rec = creados.get(padre) or campo(padre)
            if not field:
                field = Field.create({'code': code, 'name': nombre, 'field_type': tipo,
                                      'section_id': seccion.id, 'sequence': 700})
            else:
                if field.field_type != tipo:
                    field.field_type = tipo
                # Creado a mano con el código como nombre (p. ej. «segmento_3»).
                if (field.name or '').strip() == code:
                    for lang in self.env['res.lang'].get_installed():
                        field.with_context(lang=lang[0]).name = nombre
            if padre_rec and not field.depends_field_id:
                field.write({'depends_field_id': padre_rec.id, 'depends_value': valor})
            if tipo == 'selection' and not field.option_ids:
                Option.create([{'field_id': field.id, 'value': v, 'name': n, 'sequence': (i + 1) * 10}
                               for i, (v, n) in enumerate(self.OPCIONES_CURVA_U)])
            creados[code] = field
        if plano:
            Mapping = self.env['safra.system.field'].sudo().with_context(active_test=False)
            sistemas = Mapping.search([('field_id', '=', plano.id)]).mapped('system_id')
            for code, _n, _t, _p, _v, seq in self.AJUSTES_1415_SEGMENTOS:
                presentes = Mapping.search([('field_id', '=', creados[code].id)]).mapped('system_id')
                Mapping.create([{'system_id': s.id, 'field_id': creados[code].id, 'sequence': seq}
                                for s in sistemas - presentes])

        # 4. Fila 91: la cenefa entera solo se restringe por encima del rollo.
        Rule = self.env['safra.validation.rule'].sudo().with_context(active_test=False)
        for code, (cond, msg) in Rule.SEED_ANTERIORES.items():
            regla = Rule.search([('code', '=', code)], limit=1)
            if regla and (regla.condition_code or '').strip() == cond:
                regla.condition_code = Rule.SEED_CONDITIONS[code]
                if (regla.message or '').strip() == msg:
                    regla.message = Rule.SEED_MESSAGES[code]

        # 5. Fila 95: Felpa desde Referencias; mientras no haya referencia,
        # las opciones No / Sí.
        felpa = campo('coverlight_felpa')
        if felpa and not felpa.option_ids:
            Option.create([{'field_id': felpa.id, 'value': '0', 'name': 'No', 'sequence': 10},
                           {'field_id': felpa.id, 'value': '1', 'name': 'Sí', 'sequence': 20}])
        Param.set_param(marca, '1')
        return True

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


# Revisión 29-oct: ayuda de las fórmulas de las opciones, visible en el
# Catálogo de campos y en el campo de cada sistema (una sola lista).
COLUMNAS_FORMULA = [
    ('Fórmula (se ofrece si…)', 'La opción aparece en el portal solo si la fórmula da verdadero. '
                                'Vacía: siempre aparece.'),
    ('Se elige sola si…', 'Si da verdadero, el portal elige esta opción, bloquea las demás y '
                          'muestra el Aviso al cliente.'),
    ('Aviso al cliente', 'Texto que sale debajo del campo cuando la opción se elige sola o, con '
                         '«Solo aviso», cuando su fórmula da verdadero.'),
    ('Solo aviso (no se elige)', 'La opción no aparece en la lista: solo muestra su aviso cuando '
                                 'su fórmula da verdadero (p. ej. «Corte por paños»).'),
]
VARIABLES_FORMULA = [
    ('alto, ancho', 'Medidas digitadas de la persiana, en metros.', 'Cotización', 'alto <= 2.5'),
    ('cantidad', 'Cantidad de persianas de la línea.', 'Cotización', 'cantidad > 1'),
    ('sistema', 'Código del sistema, como texto.', 'Sistemas', "sistema in ('49', '57')"),
    ('motorizado', 'True si la persiana lleva motor.', 'Cotización', 'motorizado and ancho > 6'),
    ('ancho_rollo', 'Ancho del rollo del color elegido (U_Ancho del producto; vacío si el color no tiene U_Ancho digitado; 0 si se digitó 0). '
                    'Si la fórmula lo usa vacío, el portal avisa que falta digitarlo.',
     'Producto › U_Ancho', 'ancho > ancho_rollo'),
    ('vacio(…)', 'Función: verdadero si el dato numérico del maestro no se digitó (un 0 digitado '
                 'no es vacío). Aplica a todos los números de productos, referencias y sistemas '
                 '(ancho_rollo, ancho_max_<campo>…). Si la fórmula usa un dato vacío, la persiana '
                 'avisa que falta digitarlo.',
     'Fórmulas', 'vacio(ancho_rollo)'),
    ('alto_maximo_opcion', 'Alto máximo de la cortina con el dobladillo de esta opción, con la '
                           'fórmula «Alto máximo con un dobladillo» de Ajustes (hoy: ancho del '
                           'rollo + riel − dobladillo superior − su «Consumo del dobladillo»); 0 '
                           'si la opción no tiene consumo o no hay rollo.',
     'Opción › Consumo del dobladillo; Ajustes › Corte de la tela', 'alto <= alto_maximo_opcion'),
    ('ancho_max_<campo>', 'U_AnchoMax del producto elegido en un campo de Referencias, por el '
                          'código del campo (0 si el sistema no tiene ese campo; vacío si el '
                          'producto no lo tiene digitado).',
     'Producto › U_AnchoMax', 'ancho > ancho_max_riel_tipo'),
    ('tela_atravesable', 'True si la tela es atravesable (Sí o Sí/Cliente).',
     'Referencias / Telas › Atravesable', 'tela_atravesable'),
    ('tela_permite_cenefa_entera', 'True si la tela tiene marcado «Permite corte cenefa entera».',
     'Referencias / Telas', 'tela_permite_cenefa_entera'),
    ('tipo_corte', "Corte de la tela según los archivos de Safra «Tipos de corte tela»: 'normal', "
                   "'atravesado', 'anadido', 'anadido_excede' (persianas), 'bajo_falso', 'panos' "
                   "(cortinas), 'no_fabricable', 'sin_ancho_rollo' (el color no tiene U_Ancho), o vacío si "
                   "el sistema no aplica.",
     'Ajustes › Corte de la tela; Atravesable y Añadido de la tela', "tipo_corte == 'panos'"),
    ('tipo_corte_cenefa', "Cenefa en tela (reunión 28-oct): 'entera' si el ancho de la cenefa "
                          "cabe en el rollo; 'atravesada' si lo supera y la tela es atravesable "
                          "(se corta a lo largo del rollo); 'anadida' si lo supera y la tela no es "
                          "atravesable; vacío si no es cenefa en tela o falta la tela, el ancho o "
                          "el rollo.",
     'Ajustes › Corte de la tela › Cenefa en tela; Atravesable de la tela',
     "tipo_corte_cenefa == 'anadida'"),
    ('ancho_cenefa', 'Ancho de la cenefa en tela: ancho + la medida por lateral (0,11 m) por cada '
                     'lateral, en metros.', 'Ajustes › Corte de la tela › Cenefa en tela',
     'ancho_cenefa > 3'),
    ('cenefa_en_tela', 'True si el Tipo de Cenefa elegido es una cenefa en tela.', 'Tipo de Cenefa',
     'cenefa_en_tela'),
    ('<código del campo>', 'Cualquier campo del cotizador por su código técnico, con el valor '
                           'elegido como texto.', 'Catálogo de campos', "apertura == '4'"),
]


def ayuda_formulas_html():
    filas = Markup('').join(
        Markup('<tr><td><code>%s</code></td><td>%s</td><td>%s</td><td><code>%s</code></td></tr>')
        % (var, que, donde, ejemplo) for var, que, donde, ejemplo in VARIABLES_FORMULA)
    columnas = Markup('').join(Markup('<li><b>%s</b>: %s</li>') % (c, t) for c, t in COLUMNAS_FORMULA)
    return Markup(
        '<p>Cada opción del campo puede llevar fórmulas que deciden cuándo se ofrece en el portal, '
        'cuándo se elige sola y qué aviso ve el cliente.</p><ul>%s</ul>'
        '<p>Una fórmula de una línea es una condición (<code>ancho &gt; ancho_rollo</code>). Con varias '
        'líneas se calculan valores intermedios y la última asigna <code>result = …</code>. Las líneas '
        'que empiezan con <code>#</code> son comentarios. Los textos van entre comillas simples y '
        'exactos (los valores calculados van sin tildes, como <code>\'anadida\'</code>); los números, '
        'con punto decimal.</p>'
        '<table class="table table-sm table-bordered"><thead><tr><th>Variable</th><th>Qué es</th>'
        '<th>De dónde sale</th><th>Ejemplo</th></tr></thead><tbody>%s</tbody></table>') % (columnas, filas)


class SafraOptionFormula(models.AbstractModel):
    """Sprint 1.5 (fila 118): una opción puede llevar una fórmula; se
    ofrece en el portal solo si la fórmula da verdadero con las medidas y
    los campos de la persiana. Se edita en el Catálogo de campos, sin
    desarrollo (mismo motor de «Máximo de lamas»)."""
    _name = 'safra.option.formula.mixin'
    _description = 'Fórmula de una opción del cotizador'

    formula = fields.Text(
        string='Fórmula (se ofrece si…)',
        help="Expresión en Python que debe dar verdadero para que la opción\n"
             "se ofrezca; vacía = siempre se ofrece. Medidas en metros.\n"
             "Variables disponibles:\n"
             "  alto, ancho   → medidas digitadas de la persiana\n"
             "  ancho_rollo   → ancho del rollo de la tela elegida (U_Ancho del\n"
             "                  color; vacío si no se digitó, 0 si se digitó 0)\n"
             "  vacio(x)      → True si el dato numérico del maestro no se digitó\n"
             "                  (ancho_rollo, ancho_max_<campo>; un 0 digitado no es vacío)\n"
             "  cantidad      → cantidad de persianas\n"
             "  motorizado    → True si la persiana lleva motor\n"
             "  sistema       → código del sistema (p. ej. '49')\n"
             "  ancho_max_<campo> → U_AnchoMax del producto elegido en un\n"
             "                  campo de Referencias (p. ej. ancho_max_cenefa_panel;\n"
             "                  vacío si no se digitó)\n"
             "  tela_permite_cenefa_entera, tela_atravesable → marcas de la tela\n"
             "  tipo_corte    → corte de la tela: 'normal', 'atravesado', 'anadido',\n"
             "                  'bajo_falso', 'panos', 'no_fabricable', 'sin_ancho_rollo'\n"
             "                  (vacío si no aplica)\n"
             "  tipo_corte_cenefa → cenefa en tela: 'entera', 'atravesada' (supera el\n"
             "                  rollo, tela atravesable) o 'anadida'; ancho_cenefa,\n"
             "                  cenefa_en_tela\n"
             "  alto_maximo_opcion → alto máximo de la cortina con el dobladillo de esta\n"
             "                  opción (su Consumo del dobladillo)\n"
             "  y cualquier campo del cotizador por su código técnico\n"
             "Ejemplo: not ancho_rollo or alto <= ancho_rollo - 0.085")
    # Ajustes Sprint 1.4 y 1.5 (reuniones 20 y 22-oct): la opción se elige
    # sola cuando la fórmula da verdadero (p. ej. riel o cenefa dividida si
    # el ancho supera el máximo), con un aviso al cliente; las demás quedan
    # bloqueadas mientras se cumpla.
    auto_formula = fields.Text(
        string='Se elige sola si…',
        help="Fórmula (mismas variables) que, si da verdadero, elige esta\n"
             "opción, bloquea las demás y muestra el aviso al cliente.\n"
             "Ejemplo: ancho > ancho_max_riel_tipo")
    aviso = fields.Char(
        string='Aviso al cliente',
        help='Mensaje que ve el cliente cuando la opción se elige sola o, si es '
             '«Solo aviso», cuando su fórmula da verdadero.')
    # Revisión 30-oct (Dobladillo o Bajo falso): tela que consume el
    # dobladillo; con ella se calcula el alto máximo de la cortina.
    consumo_dobladillo = FloatVacio(
        string='Consumo del dobladillo (m)', digits=(6, 3),
        help='Cortinas, opciones de «Dobladillo o Bajo falso»: tela que consume el dobladillo '
             'inferior (filete 0,06; 3 cm 0,07; 10 cm 0,15; 15 cm 0,21).\n'
             'Alto máximo de la cortina con este dobladillo: fórmula «Alto máximo con un dobladillo» '
             'de Ajustes › Corte de la tela (hoy: ancho del rollo + riel − dobladillo superior − '
             'este consumo).\n'
             'El portal muestra el alto máximo en la lista, marca Sí o No según el alto pedido, y '
             'la fórmula lo recibe como alto_maximo_opcion. Vacío o 0 = la opción no es un dobladillo.')
    solo_aviso = fields.Boolean(
        string='Solo aviso (no se elige)',
        help='La opción no aparece en la lista: cuando su fórmula da verdadero '
             'el portal muestra el aviso (p. ej. «Corte por paños»).')

    @api.constrains('formula', 'auto_formula')
    def _check_formula(self):
        maximos = {'ancho_max_%s' % c: 0.0 for c in self.env['safra.field'].sudo().with_context(
            active_test=False).search([('field_type', '=', 'ref_categoria')]).mapped('code') if c}
        contextos = [dict(maximos, alto=alto, ancho=ancho, ancho_rollo=rollo, cantidad=1,
                          motorizado=False, sistema='', tela_permite_cenefa_entera=False,
                          tela_atravesable=False, tipo_corte='', tipo_corte_cenefa='',
                          ancho_cenefa=0.0, cenefa_en_tela=False, alto_maximo_opcion=0.0)
                     for alto in (1.0, 3.0) for ancho in (1.5, 7.0) for rollo in (0.0, 2.8)]
        for opt in self:
            for campo, texto in (('formula', 'La fórmula'), ('auto_formula', 'La fórmula «Se elige sola si…»')):
                if not opt[campo]:
                    continue
                error = probar_formula(self.env, opt[campo], contextos)
                if error:
                    raise ValidationError('%s de la opción «%s» tiene un error:\n%s'
                                          % (texto, opt.name, error))


class SafraFieldOption(models.Model):
    _name = 'safra.field.option'
    _inherit = ['safra.option.formula.mixin']
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
    peso_gm = FloatVacio(string='Peso (g/m)', digits=(8, 2))
    # Bloque 3 (3.2): en las opciones de Tipo de Plano, cuántos segmentos
    # habilita el plano (el desplegable Número de segmento ofrece 1..N y la
    # validación del pedido exige que estén todos, sin repetir).
    segmentos = IntegerVacio(
        string='Segmentos del plano',
        help='Solo para las opciones de Tipo de Plano: cantidad de segmentos '
             'que habilita el plano (A-C: 2, D-H: 3). El desplegable Número '
             'de segmento ofrece 1..N y el pedido debe traerlos todos.')
    # Sprint 1.5 (filas 97 y 112): una opción puede depender del valor de
    # otro campo (p. ej. «Centro frente» solo con la apertura Centro). El
    # portal la oculta y el servidor la rechaza (E20033) si no aplica.
    depends_field_id = fields.Many2one(
        'safra.field', string='Solo con el campo', ondelete='set null')
    depends_value = fields.Char(
        string='Solo con los valores',
        help="Valores del campo que habilitan esta opción, separados por coma; "
             "'!' adelante para «ninguno de estos». Vacío = cualquier valor.")


class SafraSystemField(models.Model):
    _name = 'safra.system.field'
    _inherit = ['safra.ayuda.formulas.mixin']
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
    depends_value = fields.Char(
        string='Valor que activa (override)',
        help="Igual que en el campo: valores separados por coma, '!' para negar y "
             "ref:CÓDIGO para cualquier opción de una referencia.")
    # Limpia la dependencia global del campo en este sistema (lo muestra siempre).
    clear_depends = fields.Boolean(string='Sin dependencia')
    # Las opciones propias del sistema (override) no se veían en ninguna
    # pantalla: p. ej. el Tipo de Apertura de Panel Japonés usa 1 Derecha …
    # 5 Libre, distintas de las del catálogo (derecha, centro…).
    option_count = fields.Integer(string='Opciones propias', compute='_compute_option_count')
    catalog_option_ids = fields.One2many(
        related='field_id.option_ids', string='Opciones del catálogo', readonly=True)

    @api.depends('system_id.name', 'field_id.name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '%s · %s' % (rec.system_id.name or '', rec.field_id.name or '')

    @api.depends('option_ids')
    def _compute_option_count(self):
        for rec in self:
            rec.option_count = len(rec.option_ids)

    def action_open_opciones(self):
        """Abre la ficha del campo en este sistema con sus opciones."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': '%s · %s' % (self.system_id.name, self.field_id.name),
            'res_model': 'safra.system.field',
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(self.env.ref('website_quotes_safra.view_safra_system_field_form').id, 'form')],
            'target': 'current',
        }


class SafraSystemFieldOption(models.Model):
    _name = 'safra.system.field.option'
    _inherit = ['safra.option.formula.mixin']
    _description = 'Opción de Campo por Sistema'
    _order = 'sequence, id'

    system_field_id = fields.Many2one('safra.system.field', string='Campo del sistema', required=True, ondelete='cascade', index=True)
    value = fields.Char(string='Valor', required=True)
    name = fields.Char(string='Etiqueta', required=True, translate=True)
    sequence = fields.Integer(default=10)
    image = fields.Image(string='Imagen', max_width=512, max_height=512)
    # Sprint 1.5: misma dependencia por opción del catálogo, por sistema.
    depends_field_id = fields.Many2one(
        'safra.field', string='Solo con el campo', ondelete='set null')
    depends_value = fields.Char(
        string='Solo con los valores',
        help="Valores del campo que habilitan esta opción, separados por coma; "
             "'!' adelante para «ninguno de estos». Vacío = cualquier valor.")
