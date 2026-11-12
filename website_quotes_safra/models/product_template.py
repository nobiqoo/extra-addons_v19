# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError

from .fields_vacio import FloatVacio, IntegerVacio


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    # === Clasificación para el cotizador del portal ===
    # El maestro de productos es la fuente de verdad: estos checks indican qué
    # papel juega el producto en el cotizador. Los menús del cotizador
    # (Sistemas, Referencias/Telas) se mantienen como capa de configuración
    # (campos, condiciones, orden) y quedan VINCULADOS al producto.
    safra_is_system = fields.Boolean(
        string='Es sistema del cotizador',
        help='Producto terminado que representa un sistema de persiana. Al '
             'marcarlo se crea (o vincula) su registro en el menú Sistemas '
             'del cotizador; allí se configuran sus campos y se activa.')
    # Revisión 30-oct: qué cálculo del corte de la tela usa el sistema
    # (archivos de Safra «Tipos de corte tela»); antes eran listas de códigos
    # en el programa.
    safra_calculo_corte = fields.Selection([
        ('persiana', 'Persiana'),
        ('cortina', 'Cortina'),
        ('otro', 'Otro'),
    ], string='Cálculo del corte de la tela',
        help='Sistemas: cómo se calcula el corte de la tela.\n'
             'Persiana: el ancho se compara con el ancho del rollo; si no cabe y la tela es '
             'Atravesable, el rollo se gira (corte atravesado o con añadido).\n'
             'Cortina: el alto (más dobladillos) se compara con el ancho del rollo y el '
             'ancho sale del largo del rollo; si no cabe, bajo falso o paños.\n'
             'Otro: el sistema no tiene cálculo de corte y no se revisan sus reglas (paneles, '
             'verticales, rieles…).\n'
             'Es obligatorio en los productos marcados como sistema.')
    safra_is_tela = fields.Boolean(
        string='Es referencia/tela',
        help='Referencia o tela del cotizador. Queda disponible para '
             'vincularse desde el menú Referencias / Telas.')
    # Pendientes 24-sep (10.4): el término correcto es «atributo» — cubre
    # colores, perfiles, motores y demás variables de una referencia.
    safra_is_color = fields.Boolean(
        string='¿Es un atributo del cotizador?',
        help='Artículo que actúa como atributo de una referencia (tela + '
             'color, perfil, motor…). Queda disponible para vincularse en '
             'Referencias / Telas.')
    safra_code = fields.Char(
        string='Código cotizador',
        help='Código con el que este producto se identifica en el cotizador '
             '(sistema, tela o color). Si está vacío se usa la referencia '
             'interna o un consecutivo.')
    safra_system_ids = fields.One2many(
        'safra.system', 'product_tmpl_id', string='Sistema del cotizador')

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_safra_system()
        records._assign_item_code()
        records._sync_fabric_colors()
        return records

    def write(self, vals):
        res = super().write(vals)
        # 9-nov: archivar el producto en Inventario archiva sus líneas en
        # Referencias (dejan de salir en el portal y en el backoffice se ven
        # en gris); desarchivarlo reactiva solo las que se archivaron por eso.
        if 'active' in vals and not self.env.context.get('safra_sync_activo'):
            Color = self.env['safra.fabric.color'].sudo().with_context(
                active_test=False, safra_sync_activo=True)
            if vals['active']:
                Color.search([('product_tmpl_id', 'in', self.ids), ('archivado_por', '=', 'producto')]).write(
                    {'active': True, 'archivado_por': False})
            else:
                Color.search([('product_tmpl_id', 'in', self.ids), ('active', '=', True)]).write(
                    {'active': False, 'archivado_por': 'producto'})
        if vals.get('safra_is_system'):
            self._sync_safra_system()
        if vals.get('safra_prefijo'):
            self._assign_item_code()
        # Revisión 17-sep: marcar el color y sus referencias en el maestro
        # alimenta el cotizador sin pasos adicionales.
        if vals.get('safra_is_color') or vals.get('safra_u_referencia_ids'):
            self._sync_fabric_colors()
        return res

    # Sprint 1.2: el maestro de SAP trae «0» (y a veces el texto «False»)
    # como Código cotizador de relleno en cientos de insumos; usarlo dejaba
    # perfiles, cabezales y motores con el MISMO código y el portal no los
    # distinguía. Esos valores se tratan como vacíos.
    _SAFRA_CODE_RELLENO = ('0', 'False', 'false')

    def _safra_quoter_code(self):
        """Código del producto en el cotizador: Código cotizador si es
        real; si no, la referencia interna."""
        self.ensure_one()
        code = (self.safra_code or '').strip()
        if code in self._SAFRA_CODE_RELLENO:
            code = ''
        return code or self.default_code or ''

    def _sync_fabric_colors(self):
        """Revisión 17-sep (obs de Marcela): un artículo marcado «Es color
        del cotizador» con U_Referencia diligenciada crea su línea en cada
        referencia automáticamente — ya no hay que ir al menú Referencias a
        agregarla a mano. Idempotente (si la línea existe, aunque esté
        archivada, no duplica)."""
        Color = self.env['safra.fabric.color'].sudo().with_context(active_test=False)
        for product in self.filtered(lambda p: p.safra_is_color and p.safra_u_referencia_ids):
            for fabric in product.safra_u_referencia_ids:
                if not Color.search_count([
                        ('fabric_id', '=', fabric.id),
                        ('product_tmpl_id', '=', product.id)]):
                    Color.create({
                        'fabric_id': fabric.id,
                        'product_tmpl_id': product.id,
                        'code': product._safra_quoter_code() or str(product.id),
                    })

    def _compute_safra_kit_producto_ids(self):
        for product in self:
            variantes = product.product_variant_ids
            product.safra_kit_producto_ids = self.search(
                [('safra_kit_asociado_ids', 'in', variantes.ids)]) if variantes else False

    @api.constrains('safra_item_code')
    def _check_safra_item_code(self):
        """Sprint 1.6 (fila 162): el ItemCode es la referencia única."""
        for product in self.filtered('safra_item_code'):
            otro = self.with_context(active_test=False).search([
                ('safra_item_code', '=', product.safra_item_code), ('id', '!=', product.id)], limit=1)
            if otro:
                raise ValidationError('El ItemCode %s ya lo tiene el producto %s.' % (
                    product.safra_item_code, otro.display_name))

    def _assign_item_code(self):
        """ItemCode automático (F172): prefijo + consecutivo del prefijo.

        Corre al guardar un producto con prefijo y sin ItemCode; el
        consecutivo por prefijo se administra en Opciones de Producto.
        ItemName queda con el nombre del producto si está vacío (F173).
        """
        for product in self.filtered(lambda p: p.safra_prefijo and not p.safra_item_code):
            product.safra_item_code = self.env['safra.product.option'].sudo().next_item_code(product.safra_prefijo)
            if not product.safra_item_name:
                product.safra_item_name = product.name
            # Fila 163: «[ItemCode] nombre» es el nombre que muestra Odoo.
            if not product.default_code:
                product.default_code = product.safra_item_code

    def _sync_safra_system(self):
        """Marcar 'Es sistema' crea/vincula el registro en el menú Sistemas.

        Se crea inactivo: aparece en el portal cuando se configuren sus
        campos y se active (un sistema sin campos mostraría un formulario
        vacío al cliente).
        """
        System = self.env['safra.system'].sudo()
        for product in self.filtered('safra_is_system'):
            linked = System.with_context(active_test=False).search(
                [('product_tmpl_id', '=', product.id)], limit=1)
            if linked:
                continue
            # Reusar un sistema homónimo aún sin producto antes de crear uno.
            same_name = System.with_context(active_test=False).search(
                [('name', '=ilike', product.name), ('product_tmpl_id', '=', False)], limit=1)
            if same_name:
                same_name.product_tmpl_id = product.id
                continue
            code = product._safra_quoter_code()
            if not code or System.with_context(active_test=False).search_count([('code', '=', code)]):
                code = self.env['ir.sequence'].sudo().next_by_code('safra.system.code') or ('P%d' % product.id)
            System.create({
                'name': product.name,
                'code': code,
                'product_tmpl_id': product.id,
                'active': False,
            })

    # === Campos de Parametrización (matriz unificada de variables Safra) ===
    # Marcados como 'Parametrizacion' en la columna Visible del Excel.
    # Las etiquetas (string) se mantienen TAL CUAL la columna "Variable" del documento.

    # --- General / Clasificación ---
    # (F144: "Categoria de producto" se retiró; es el campo estándar categ_id)
    safra_u_categoria = fields.Many2one(
        'safra.product.option', string='U_Categoria', ondelete='set null',
        domain=[('type', '=', 'categoria')],
        help='Segmentar las ventas por producto (ej. cortina-enrollable-telas). '
             'Opciones configurables en Cotizador Safra → Configuración → Opciones de Producto.')
    safra_u_grupo_prod = fields.Many2one(
        'safra.product.option', string='U_GrupoProd', ondelete='set null',
        domain=[('type', '=', 'grupo_prod')],
        help='Clasificar tipos de artículos: telas, perfiles, tubos, soportes, '
             'mecanismos, motores… Opciones configurables por el cliente.')
    # Sprint 1.6 (fila 132): unidad de negocio (PERSIANAS / CORTINA /
    # TOLDOS / TELAS) para segmentar los informes; las opciones se crean en
    # Opciones de Producto.
    safra_unidad_negocio_id = fields.Many2one(
        'safra.product.option', string='Unidad de negocio', ondelete='set null',
        domain=[('type', '=', 'unidad_negocio')],
        help='Unidad de negocio del producto para los informes (PERSIANAS, '
             'CORTINA, TOLDOS, TELAS…). Opciones en Cotizador Safra → '
             'Configuración → Opciones de Producto.')
    safra_u_descontinuado = fields.Boolean(string='U_Descontinuado', help='Marcar para deshabilitar/descontinuar el producto.')
    safra_asociacion_ids = fields.Many2many(
        'safra.system', 'product_safra_system_asoc_rel', 'product_id', 'system_id',
        string='Asociacion (sistemas)',
        help='Sistemas del cotizador a los que está asociada esta materia '
             'prima (F160: un insumo puede pertenecer a más de un producto).')
    safra_kit_asociado_ids = fields.Many2many(
        'product.product', 'product_safra_kit_rel', 'product_id', 'kit_id',
        string='Kit Asociado',
        help='Kits a los que está asociada esta materia prima (para la lista '
             'de materiales). Un producto puede tener más de un kit.')
    # Sprint 1.6 (fila 151): desde el kit, qué productos lo tienen asociado.
    safra_kit_producto_ids = fields.Many2many(
        'product.template', string='Productos asociados a este kit',
        compute='_compute_safra_kit_producto_ids')
    safra_u_modo_corte = fields.Many2one(
        'safra.product.option', string='U_ModoCorte', ondelete='set null',
        domain=[('type', '=', 'modo_corte')],
        help='Modo de corte (requerido para KISS). Opciones configurables.')
    safra_u_color = fields.Many2one(
        'safra.color', string='U_color', ondelete='set null',
        help='Color genérico del artículo, del catálogo de colores '
             '(Configuración → Colores). Lista independiente de las '
             'referencias; sirve para agrupar en el portal y asociar telas y '
             'kits que se afectan con el coordinado.')
    safra_u_cantidad_paquete = IntegerVacio(string='U_CantidadPaquete', help='Unidades de empaque.')
    safra_u_tolerancia = FloatVacio(string='U_TOLERANCIA', help='% de tolerancia usado en fórmulas (ej. corte de perfilería).')
    safra_cant_min_cobrar = FloatVacio(string='CantidadMinima cobrar', help='Metros cuadrados mínimos para el cobro base.')
    safra_cant_min_stock = FloatVacio(string='CantidadMinima stock', help='Metros lineales mínimos para stock de reserva.')
    safra_u_observacion = fields.Text(string='U_Observacion', help='Observaciones que se visualizarían en el portal.')

    # --- Códigos (F171-F173) ---
    safra_prefijo = fields.Many2one(
        'safra.product.option', string='Prefijo', ondelete='set null',
        domain=[('type', '=', 'prefijo')],
        help='Prefijo para el cálculo automático del ItemCode; su consecutivo '
             'se configura en Opciones de Producto.')
    safra_item_code = fields.Char(
        string='ItemCode', copy=False, index=True,
        help='Código de artículo. Se calcula automáticamente (prefijo + '
             'consecutivo) al guardar con un prefijo y sin código; no se '
             'puede repetir.')
    # Sprint 1.6 (fila 163): el nombre que muestra Odoo une ItemCode e
    # ItemName («[ItemCode] nombre»): el ItemCode pasa a la referencia
    # interna cuando está vacía.
    safra_item_name = fields.Char(string='ItemName', help='Nombre del artículo (por defecto, el nombre del producto).')

    # --- Tela / Referencia ---
    # Perfiles-P4 (OBS REU): U_Referencia es many2many — un artículo puede
    # pertenecer a varias referencias del catálogo.
    safra_u_referencia_ids = fields.Many2many(
        'safra.fabric', 'product_safra_referencia_rel', 'product_id', 'fabric_id',
        string='U_Referencia',
        help='Referencias del menú Referencias / Telas a las que pertenece este artículo.')
    # 9-nov: los números del maestro distinguen «sin digitar» (casilla vacía)
    # de «digitado en 0» (FloatVacio / IntegerVacio).
    safra_u_ancho = FloatVacio(
        string='U_Ancho',
        help='Ancho del rollo en metros (también ancho de tubo u otros '
             'insumos, en metros). Vacío: no se ha digitado; 0: se digitó 0.')
    safra_u_peso = FloatVacio(string='U_Peso', help='Tela: peso en gramos por metro cuadrado. Perfil: gramos por metro lineal.')
    safra_u_densidad = FloatVacio(string='U_Densidad', help='Densidad para cálculos de consumo.')
    safra_tela_atravesable = fields.Boolean(string='Tela Atravesable', help='Si la tela permite corte atravesado (para validar stock).')
    safra_u_forrado = fields.Boolean(string='U_Forrado', help='Cenefas y cabezales que se pueden forrar (tela y mecanismo).')
    safra_u_bolsillo = fields.Boolean(string='U_Bolsillo', help='Si la tela permite bolsillo (aumenta consumo de tela y precio).')
    safra_permite_corte_entera = fields.Boolean(
        string='Permite corte cenefa entera',
        help='Filtra el tipo de corte de la cenefa en tela (F143).')

    # --- Dimensiones / límites (F146-F149: ficha técnica y limitantes) ---
    safra_u_ancho_min = FloatVacio(string='U_AnchoMin', help='Ancho mínimo (producto terminado o padre).')
    safra_u_ancho_max = FloatVacio(string='U_AnchoMax', help='Ancho máximo (producto terminado o padre).')
    safra_u_alto_min = FloatVacio(string='U_AltoMin', help='Alto mínimo (producto terminado o padre).')
    safra_u_alto_max = FloatVacio(string='U_AltoMax', help='Alto máximo; en portal se muestra el menor entre este y el calculado.')

    # --- Motor / Mecanismo / Insumos ---
    safra_u_cantidad_canales = IntegerVacio(string='U_Cantidad de canales', help='Cantidad de canales permitidos para el control.')
    safra_u_requiere_cargador = fields.Boolean(string='U_Requiere cargador', help='Si el motor requiere cargador.')
    # Pendientes 24-sep (14.1/15.1/17.1): las asociaciones de motor viven en
    # el MAESTRO (no en los kits, que quedan para componentes/BOM): item de
    # cargador, check + item del módulo/receptor RF y controles compatibles.
    safra_u_cargador_item_id = fields.Many2one(
        'product.template', string='U_Item cargador',
        help='Artículo del maestro que se agrega como cargador cuando el '
             'cliente lo solicita.')
    safra_u_requiere_interruptor_rf = fields.Boolean(
        string='U_Requiere interruptor RF',
        help='El motor necesita módulo/receptor RF: el portal muestra el '
             'campo «Módulo de Control RF» solo para motores marcados.')
    safra_u_interruptor_item_id = fields.Many2one(
        'product.template', string='U_Item interruptor RF',
        help='Artículo del maestro del módulo/receptor RF de este motor.')
    safra_u_control_ids = fields.Many2many(
        'product.template', 'safra_motor_control_rel', 'motor_id', 'control_id',
        string='U_Controles compatibles',
        help='Controles del maestro que sirven para este motor; el campo '
             '«Control» del portal ofrece únicamente estos.')
    # Reunión 15-oct (fila 68): a qué tubos de la Estructura por Ancho
    # pertenece este insumo. Un tubo se bloquea en el portal si uno de sus
    # insumos de estructura (tubo, soporte, mecanismo…) se queda sin stock;
    # una opción del portal (p. ej. un cabezal) con tubos marcados solo se
    # ofrece con esos tubos.
    safra_tubo_ids = fields.Many2many(
        'safra.product.option', 'product_template_safra_tubo_rel',
        'product_tmpl_id', 'option_id', string='Tubos',
        domain=[('type', '=', 'tubo')],
        help='Tubos (Estructura por Ancho) a los que pertenece este insumo. '
             'Insumos de estructura: sin stock bloquean el tubo en el portal '
             'hasta que vuelva a entrar. Opciones del portal (cabezales, '
             'perfiles…): solo se ofrecen con estos tubos. Vacío: no aplica.')
    safra_carga_maxima = FloatVacio(string='Carga maxima', help='Peso máximo (insumo MECANISMO); desde qué peso se requiere motor.')
    safra_diametro_tubo = FloatVacio(string='Diametro externo Tubo', help='Diámetro externo del insumo TUBO.')
    safra_espacio_eje_techo = FloatVacio(
        string='Espacio útil',
        help='F177: en enrollables, espacio del eje central a techo (soporte/'
             'cabezal); en Onda Moderna, espacio entre rodachinas '
             '(rodachinas = ancho/espacio + 1).')
    safra_torque = FloatVacio(string='Torque', help='Torque del motor (Nm); se usa para calcular la carga máxima en enrollables.')

    # --- Consumos por insumo (F178-F183, hoy también en Estructura por Ancho) ---
    safra_desc_mando = FloatVacio(string='Descuentos mando', help='Descuento sobre el ancho al cortar (m).')
    safra_desc_terminal = FloatVacio(string='Descuentos Terminal', help='Descuento sobre el ancho al cortar (m).')
    safra_desc_soporte = FloatVacio(string='Descuento soporte', help='Descuento sobre el ancho al cortar (m).')
    # Sprint 1.6 (fila 172): campo para las fórmulas de la lista de materiales.
    safra_desc_cabezal = FloatVacio(string='Descuento Cabezal', help='Descuento sobre el ancho al cortar el cabezal (m).')
    safra_desc_corona = FloatVacio(string='Descuento Corona', help='Descuento sobre el ancho al cortar (m).')
    safra_aumento_tela_tubo = FloatVacio(string='Aumento tela del tubo', help='Tela adicional para enrollar en el tubo (m).')
    safra_aumento_tela_perfil = FloatVacio(string='Aumento / disminucion tela perfil', help='Ajuste de tela por el perfil (m).')
