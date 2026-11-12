# -*- coding: utf-8 -*-
from odoo import api, fields, models

from .fields_vacio import FloatVacio, dato_sin_digitar, vacio_en


class SafraSystem(models.Model):
    _name = 'safra.system'
    _description = 'Sistema de Persiana Safra'
    _order = 'name'

    _code_uniq = models.Constraint(
        'UNIQUE(code)',
        'El código del sistema debe ser único.',
    )

    code = fields.Char(string='Código', required=True, index=True)
    name = fields.Char(string='Sistema', required=True)
    active = fields.Boolean(default=True)
    # Relación al maestro de productos: el producto terminado que representa
    # este sistema (grupo de asociación SAP). El menú se conserva como guía;
    # el producto aporta la parametrización (pestaña Parametrización).
    product_tmpl_id = fields.Many2one(
        'product.template', string='Producto terminado', ondelete='set null',
        domain=[('safra_is_system', '=', True)],
        help='Producto del maestro (marcado "Es sistema del cotizador") '
             'asociado a este sistema del portal.')
    # Pendientes 24-sep (1.1): sistemas restringidos por grupos de usuarios
    # (p. ej. estructuras de exportación que no aplican para todos).
    group_ids = fields.Many2many(
        'res.groups', 'safra_system_group_rel', 'system_id', 'group_id',
        string='Grupos que lo ven',
        help='Si se definen, el sistema solo aparece en el cotizador para '
             'los usuarios de estos grupos; vacío = todos.')

    def _visible_for_user(self, user):
        self.ensure_one()
        return not self.group_ids or bool(self.group_ids & user.all_group_ids)
    # Campos habilitados en este sistema, editables desde el formulario.
    mapping_ids = fields.One2many('safra.system.field', 'system_id', string='Campos del sistema')

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._ensure_products()
        return records

    # 9-nov: Safra carga y edita sus datos en la base. Lo que el módulo
    # siembra (sistemas, campos, opciones, validaciones, reglas…) se crea
    # una vez y después no se vuelve a escribir al actualizar.
    _MODELOS_PROTEGIDOS = ('ir.sequence', 'ir.config_parameter', 'ir.cron', 'product.pricelist',
                           'product.pricelist.item')

    @api.model
    def _una_vez(self, modelo, metodo):
        """Corre una función de los datos del módulo una sola vez por base
        (las actualizaciones siguientes no la repiten)."""
        Param = self.env['ir.config_parameter'].sudo()
        marca = 'website_quotes_safra.una_vez.%s.%s' % (modelo, metodo)
        if Param.get_param(marca):
            return
        getattr(self.env[modelo], metodo)()
        Param.set_param(marca, '1')

    @api.model
    def _proteger_datos_del_modulo(self):
        """Marca como «no actualizar» todos los registros que siembra el
        módulo (modelos del cotizador, secuencias, parámetros, listas de
        precios): una actualización ya no los reescribe ni los borra."""
        self.env.cr.execute("""
            UPDATE ir_model_data SET noupdate = TRUE
             WHERE module = 'website_quotes_safra' AND NOT COALESCE(noupdate, FALSE)
               AND (model LIKE 'safra.%%' OR model IN %s)""", [self._MODELOS_PROTEGIDOS])

    def _ensure_products(self):
        """Todo sistema del portal debe existir en el maestro de productos.

        El selector del cotizador solo muestra sistemas cuyo producto tiene el
        check "Es sistema del cotizador"; aquí se crea y vincula el producto
        faltante (idempotente: también corre en cada actualización del módulo
        para las bases ya instaladas).
        """
        Product = self.env['product.template'].sudo()
        systems = self if self else self.with_context(active_test=False).search([])
        for system in systems:
            if system.product_tmpl_id:
                continue
            system.product_tmpl_id = Product.create({
                'name': system.name,
                'default_code': system.code,
                'safra_code': system.code,
                'safra_is_system': True,
                'sale_ok': True,
                'purchase_ok': False,
            }).id

    # === Ficha técnica (datos del producto terminado, mostrados en el portal) ===
    tech_width_min = FloatVacio(string='Ancho mínimo (m)', digits=(12, 2))
    tech_width_max = FloatVacio(string='Ancho máximo (m)', digits=(12, 2))
    tech_height_min = FloatVacio(string='Alto mínimo (m)', digits=(12, 2))
    tech_height_max = FloatVacio(string='Alto máximo (m)', digits=(12, 2))
    # Reunión 28-sep (fila 3): una persiana de exhibición tiene su propia
    # ficha de mínimos y máximos; un valor vacío usa el de la ficha normal.
    exh_width_min = FloatVacio(string='Ancho mínimo exhibición (m)', digits=(12, 2))
    exh_width_max = FloatVacio(string='Ancho máximo exhibición (m)', digits=(12, 2))
    exh_height_min = FloatVacio(string='Alto mínimo exhibición (m)', digits=(12, 2))
    exh_height_max = FloatVacio(string='Alto máximo exhibición (m)', digits=(12, 2))
    # Ajustes 20-oct (fila 79): criterios de aceptación de las imágenes del
    # diseño de impresión, por sistema (Safra enviará los definitivos).
    diseno_dpi_minimo = FloatVacio(
        string='DPI mínimo de impresión', default=40, digits=(8, 0),
        help='Resolución mínima (píxeles por pulgada a la medida de la persiana). '
             'Un diseño del catálogo por debajo no deja guardar la persiana; en el '
             'diseño propio solo se informa (lo revisa el área de diseño).\n\n'
             'Cómo se calcula (DPI efectivo):\n'
             'DPI = píxeles ÷ (metros × 39,37), en el ancho y en el alto; se toma '
             'el menor. 1 m = 39,37 pulgadas (1 pulgada = 2,54 cm).\n\n'
             'Ejemplo: imagen de 2000 × 1000 px en una persiana de 2,00 × 1,00 m\n'
             'Ancho: 2000 ÷ (2,00 × 39,37) = 25,4\n'
             'Alto: 1000 ÷ (1,00 × 39,37) = 25,4\n'
             'DPI efectivo = 25: con el mínimo en 40 no se guarda (E20043).')
    diseno_dpi_optimo = FloatVacio(
        string='DPI óptimo de impresión', default=80, digits=(8, 0),
        help='Desde esta resolución la imagen se considera óptima.')
    diseno_proporcion_max = FloatVacio(
        string='Diferencia de proporción permitida (%)', default=0, digits=(8, 1),
        help='Diferencia máxima entre la proporción de la imagen del catálogo y la '
             'de la persiana. Vacío o 0 = no se valida la proporción.')
    # Sprint 1.7 (matriz, Panel Duo): rango propio del ancho de cada telo en
    # los paneles; vacío o 0 = el de los parámetros generales de Panel Track.
    panel_telo_min = FloatVacio(
        string='Ancho mínimo del telo (m)', digits=(6, 3),
        help='Paneles: ancho mínimo de cada telo en este sistema. Vacío o 0 = el general '
             '(parámetro safra.panel.ancho_telo_min, hoy 0,35 m).')
    panel_telo_max = FloatVacio(
        string='Ancho máximo del telo (m)', digits=(6, 3),
        help='Paneles: ancho máximo de cada telo en este sistema. Vacío o 0 = el general '
             '(parámetro safra.panel.ancho_telo_max, hoy 0,95 m).')
    # Archivo de Safra «Cortinas Cálculo Tipo de Corte Tela» (26-oct): el
    # ancho de tela de una cortina es el ancho pedido por este factor.
    # Revisión 30-oct: se elige en el producto terminado (Parametrización).
    calculo_corte = fields.Selection(
        related='product_tmpl_id.safra_calculo_corte', readonly=False)
    factor_confeccion = FloatVacio(
        string='Factor de confección', digits=(6, 2),
        help='Cortinas: ancho de tela requerido = ancho pedido × factor (se usa para '
             'contar los paños del corte por paños). Vacío o 0 = 1.')
    # Reunión 28-sep (fila 70): ya no se configura ni se muestra; el
    # mecanismo se calcula con la tabla de estructura. Se conserva la
    # columna para no perder lo que estuviera diligenciado.
    tech_mechanism = fields.Char(
        string='Mecanismo (texto anterior)',
        help='Texto de la ficha técnica, p. ej. "Tubo: R8 - Mecanismo: R8SL - Cabezal: No Aplica".',
    )

    @api.model
    def _ajuste_calculo_corte(self, _ids=None):
        """Revisión 30-oct, una sola vez por base: los sistemas que el
        programa tenía en las listas del corte (o en los parámetros
        safra.corte.sistemas_persiana / _cortina, si se cambiaron) quedan con
        su Cálculo del corte de la tela en el producto terminado."""
        Param = self.env['ir.config_parameter'].sudo()
        marca = 'website_quotes_safra.ajuste_calculo_corte'
        if Param.get_param(marca):
            return
        Param.set_param(marca, '1')
        for calculo, clave, defecto in (
                ('persiana', 'safra.corte.sistemas_persiana', '01,06,08,10,39,32,61'),
                ('cortina', 'safra.corte.sistemas_cortina', '49,57')):
            codigos = [c.strip() for c in (Param.get_param(clave) or defecto).split(',') if c.strip()]
            sistemas = self.sudo().with_context(active_test=False).search([('code', 'in', codigos)])
            sistemas._ensure_products()
            sistemas.mapped('product_tmpl_id').filtered(
                lambda p: not p.safra_calculo_corte).safra_calculo_corte = calculo
            Param.search([('key', '=', clave)]).unlink()

    @api.model
    def _ajuste_calculo_corte_otro(self, _ids=None):
        """Revisión 30-oct, una sola vez por base: el Cálculo del corte de la
        tela es obligatorio; los sistemas que no son persiana ni cortina
        quedan en «Otro» (sin cálculo, como estaban)."""
        Param = self.env['ir.config_parameter'].sudo()
        marca = 'website_quotes_safra.ajuste_calculo_corte_otro'
        if Param.get_param(marca):
            return
        Param.set_param(marca, '1')
        sistemas = self.sudo().with_context(active_test=False).search([])
        sistemas._ensure_products()
        self.env['product.template'].sudo().with_context(active_test=False).search([
            ('safra_is_system', '=', True), ('safra_calculo_corte', '=', False),
        ]).safra_calculo_corte = 'otro'

    def _tech_limits(self, exhibition=False):
        """Límites efectivos de la ficha técnica (revisión sprint 1,
        f63-f66): si el producto terminado asociado tiene U_AnchoMin /
        U_AnchoMax / U_AltoMin / U_AltoMax, esos valores mandan; si no, se
        usan los del sistema. Con exhibición mandan los límites de
        exhibición del sistema que estén diligenciados."""
        self.ensure_one()
        p = self.product_tmpl_id
        lim = {
            'wmin': (p and p.safra_u_ancho_min) or self.tech_width_min or 0.0,
            'wmax': (p and p.safra_u_ancho_max) or self.tech_width_max or 0.0,
            'hmin': (p and p.safra_u_alto_min) or self.tech_height_min or 0.0,
            'hmax': (p and p.safra_u_alto_max) or self.tech_height_max or 0.0,
        }
        if exhibition:
            lim['wmin'] = self.exh_width_min or lim['wmin']
            lim['wmax'] = self.exh_width_max or lim['wmax']
            lim['hmin'] = self.exh_height_min or lim['hmin']
            lim['hmax'] = self.exh_height_max or lim['hmax']
        return lim

    # (clave de _tech_limits, campo del producto terminado, del sistema, de exhibición)
    _LIMITES_CAMPOS = [
        ('wmin', 'safra_u_ancho_min', 'tech_width_min', 'exh_width_min'),
        ('wmax', 'safra_u_ancho_max', 'tech_width_max', 'exh_width_max'),
        ('hmin', 'safra_u_alto_min', 'tech_height_min', 'exh_height_min'),
        ('hmax', 'safra_u_alto_max', 'tech_height_max', 'exh_height_max'),
    ]

    def _limites_sin_digitar(self, exhibition=False):
        """{clave de _tech_limits: dato} de los límites que no tienen ningún
        dato digitado (ni en el producto terminado ni en el sistema ni, con
        exhibición, en los de exhibición). Un 0 digitado no cuenta como
        vacío."""
        self.ensure_one()
        p = self.product_tmpl_id
        out = {}
        for clave, campo_p, campo_s, campo_e in self._LIMITES_CAMPOS:
            if p and not vacio_en(p, campo_p):
                continue
            if not vacio_en(self, campo_s) or (exhibition and not vacio_en(self, campo_e)):
                continue
            dato = dato_sin_digitar(self, campo_s)
            if p:
                dato += ' (ni el %s de su producto terminado)' % p._fields[campo_p].string
            out[clave] = dato
        return out
    # Carpeta de imágenes de producto en el repositorio de imágenes del cliente.
    img_group = fields.Char(string='Grupo de imágenes', help='Carpeta en Images/SafraImages, p. ej. "06".')
    # Multiplicador del peso de tela en las fórmulas (hoja 4: "Para Sheer,
    # Alto × 2" — la tela va doblada). 1.0 para los demás sistemas.
    weight_factor = FloatVacio(string='Factor de peso de tela', default=1.0, digits=(4, 1))
    # Revisión cálculo de tubo (27-oct, hoja 5): en 2 en 1 y Sheer 2 en 1 el
    # tubo sale solo del ancho; no se calculan alto ni peso máximo aunque la
    # estructura o sus referencias tengan espacio, diámetro o carga.
    tubo_solo_ancho = fields.Boolean(
        string='Tubo solo por ancho',
        help='El tubo se elige solo por el ancho en la Estructura por Ancho: no se '
             'calculan alto ni peso máximo (fórmulas de Ajustes) ni se muestra el cuadro '
             'de altos y pesos. Archivo de Safra, hoja 5: 2 en 1 y Sheer 2 en 1.')
