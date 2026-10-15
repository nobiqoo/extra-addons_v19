# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError

from .safra_field import DISPLAY_MODES


class SafraFabric(models.Model):
    _name = 'safra.fabric'
    _description = 'Tela / Referencia Safra'
    _order = 'name'

    _code_uniq = models.Constraint(
        'UNIQUE(code)',
        'El código de referencia debe ser único.',
    )

    code = fields.Char(string='Código', required=True, index=True)
    name = fields.Char(string='Nombre', required=True)
    # Punto 18 (OBS REU TELAS): la categoría de la referencia es una lista
    # configurable (Tela, Sesgo, …) — base del tipo de campo «referencia
    # (categoría)» del portal. El Char anterior queda como respaldo oculto.
    category = fields.Char(string='Categoría (texto anterior)')
    category_id = fields.Many2one(
        'safra.product.option', string='Categoría', ondelete='set null',
        domain=[('type', '=', 'ref_categoria')],
        help='Categoría del catálogo de referencias (Tela, Sesgo, …). '
             'Opciones configurables en Configuración → Opciones de Producto.')
    es_control = fields.Boolean(related='category_id.es_control')
    # Reunión 13-oct (filas 50-52): la presentación de las opciones se
    # configura en la referencia (antes solo en el Catálogo de campos).
    display_mode = fields.Selection(
        DISPLAY_MODES, string='Presentación de opciones',
        help='Cómo se ven en el portal las opciones de esta referencia en los '
             'campos «Referencia (categoría)». Vacío: la del campo.')
    field_ids = fields.One2many(
        'safra.field', compute='_compute_field_ids', string='Campos que la usan')

    @api.depends('category_id')
    def _compute_field_ids(self):
        Field = self.env['safra.field'].sudo()
        for rec in self:
            rec.field_ids = Field.search([('field_type', '=', 'ref_categoria'),
                                          ('ref_category_id', '=', rec.category_id.id)]) \
                if rec.category_id else Field

    def _migrate_categories(self):
        """Asigna categoría «Tela» a las referencias sin categoría nueva
        (todo lo que vive hoy en este menú son telas). Idempotente."""
        Option = self.env['safra.product.option'].sudo()
        tela = Option.search([('type', '=', 'ref_categoria'), ('name', '=', 'Tela')], limit=1)
        if not tela:
            tela = Option.create({'type': 'ref_categoria', 'name': 'Tela'})
        self.with_context(active_test=False).search(
            [('category_id', '=', False)]).write({'category_id': tela.id})
    # Parámetros físicos para las fórmulas de alto/peso máximo (hoja 3 del
    # Excel de la matriz y hoja DENSIDAD): U_Peso y U_Densidad del maestro.
    peso_gm2 = fields.Float(string='Peso tela (g/m²)', digits=(8, 2))
    grosor_mm = fields.Float(string='Grosor / densidad (mm)', digits=(6, 3))
    active = fields.Boolean(default=True)
    color_ids = fields.One2many('safra.fabric.color', 'fabric_id', string='Colores')
    # Sistemas (productos) que admiten esta tela. El portal filtra la Referencia
    # por el sistema elegido; replicamos esa relación.
    system_ids = fields.Many2many(
        'safra.system', 'safra_fabric_system_rel', 'fabric_id', 'system_id',
        string='Sistemas',
    )

    # Punto 3 (OBS REU TELAS): disponibilidad por stock mínimo, configurado
    # en la REFERENCIA. Si el stock disponible de sus artículos está por
    # debajo del mínimo, la tela no se ofrece en el portal.
    cant_min_stock = fields.Float(
        string='Cantidad mínima stock (m)', digits=(12, 2),
        help='Metros lineales mínimos de reserva. Con el mínimo configurado '
             '(> 0), la referencia solo aparece en el portal si el stock '
             'disponible de sus artículos lo supera. En 0 no se valida.')
    warehouse_ids = fields.Many2many(
        'stock.warehouse', 'safra_fabric_warehouse_rel', 'fabric_id', 'warehouse_id',
        string='Bodegas para disponibilidad',
        help='Bodegas donde se consulta el stock para la disponibilidad del '
             'portal. Vacío = todas las bodegas.')
    stock_disponible = fields.Float(
        string='Stock disponible (m)', compute='_compute_stock_disponible',
        digits=(12, 2))

    def _fabric_products(self):
        # Las cantidades se validan con los productos asociados en Colores.
        self.ensure_one()
        return self.color_ids.mapped('product_tmpl_id')

    def _compute_stock_disponible(self):
        for rec in self:
            rec.stock_disponible = rec._stock_disponible()

    def _stock_disponible(self):
        """Stock disponible: suma del qty disponible de los artículos
        vinculados (productos de los colores y de la propia referencia),
        restringido a las bodegas configuradas si las hay."""
        self.ensure_one()
        products = self._fabric_products()
        if self.warehouse_ids:
            products = products.with_context(warehouse_id=self.warehouse_ids.ids)
        return sum(products.mapped('qty_available'))

    def action_view_stock(self):
        """Smart button: existencias de los artículos de la referencia en las
        bodegas configuradas."""
        self.ensure_one()
        domain = [
            ('product_id.product_tmpl_id', 'in', self._fabric_products().ids),
            ('location_id.usage', '=', 'internal'),
        ]
        if self.warehouse_ids:
            domain.append(('location_id.warehouse_id', 'in', self.warehouse_ids.ids))
        return {
            'type': 'ir.actions.act_window',
            'name': 'Existencias — %s' % self.name,
            'res_model': 'stock.quant',
            'view_mode': 'list',
            'domain': domain,
            'context': {'search_default_internal_loc': 1},
        }

    def _is_available_for_portal(self):
        """La referencia se ofrece mientras tenga al menos UN color con stock
        suficiente; el desplegable de colores muestra solo los que cumplen."""
        self.ensure_one()
        if not self.cant_min_stock:
            return True
        return any(c._is_available_for_portal() for c in self.color_ids)

    # Flags de parametrización que habilitan campos condicionales en el portal
    is_printable = fields.Boolean(
        string='Estampable',
        help='Si la tela admite estampación, habilita la sección Diseño de Impresión.',
    )
    # Punto 8 (OBS REU TELAS): renombrado de «Doblefaz» a «Tela al revés»;
    # vive únicamente en la referencia (se retiró U_Tela Al Reves del
    # maestro de productos).
    is_doublefaced = fields.Boolean(
        string='Tela al revés',
        help='Si la tela es doblefaz, habilita la opción ¿Tela al revés? '
             'en el portal.',
    )
    # Punto 7 (OBS REU TELAS): atravesable es un desplegable de 3 opciones.
    # 'si' = la fábrica puede atravesarla (la cascada de disponibilidad la
    # usa); 'si_cliente' = además el cliente puede pedirla atravesada (se
    # muestra la opción Atravesar Tela en el portal).
    pierceable_type = fields.Selection([
        ('no', 'No'),
        ('si', 'Sí'),
        ('si_cliente', 'Sí (cliente)'),
    ], string='Atravesable', required=True, default='no')

    # Punto 6 (OBS REU TELAS): U_Añadido vive en la referencia. Tercer paso
    # de la cascada de disponibilidad de tela (ancho → atravesable → añadido;
    # el añadido requiere que la tela sea atravesable).
    is_anadido = fields.Boolean(
        string='Añadido (U_Añadido)',
        help='Si la tela permite añadirle un pedazo cuando el ancho/alto no '
             'alcanza. Solo aplica si la tela es atravesable (condicional '
             'del punto 7).',
    )
    # Revisión 17-sep: telas con franjas (Sheer Elegance y similares). La
    # distancia entre franjas varía por proveedor, así que un pedido
    # ALINEADO con esta marca exige la misma altura en todas las líneas
    # (misma referencia, color y altura) — validación obligatoria.
    # Pendientes 24-sep (10.3): «Tela con franjas» y «Familia Sheer» son lo
    # mismo — el check se retiró de la vista y la regla de altura del
    # alineado ahora mira is_sheer. El campo queda por compatibilidad y la
    # migración _merge_franjas_into_sheer traslada las marcas existentes.
    has_franjas = fields.Boolean(
        string='Tela con franjas (obsoleto: usar Familia Sheer)',
        help='Obsoleto — fusionado con Familia Sheer.')

    @api.model
    def _merge_franjas_into_sheer(self):
        """Pendientes 24-sep (10.3): toda tela marcada con franjas pasa a
        Familia Sheer (idempotente; corre en cada actualización)."""
        self.search([('has_franjas', '=', True),
                     ('is_sheer', '=', False)]).write({'is_sheer': True})
    # Revisión 17-sep: familias de tela para las reglas de los 2 en 1 y los
    # filtros de referencia (evitan listados/selecciones incorrectas).
    is_blackout = fields.Boolean(
        string='Familia Blackout',
        help='La referencia pertenece a la familia Blackout.')
    is_sheer = fields.Boolean(
        string='Familia Sheer',
        help='La referencia pertenece a la familia Sheer; los sistemas '
             '2 en 1 exigen una tela de esta familia.')
    # OBS REU GENERALES 11-sep: Blackout Texturizado. La referencia
    # «texturizada» es una máscara comercial sobre la tela blanca: al
    # elegirla, el portal ofrece el catálogo de diseños de textura.
    is_texturable = fields.Boolean(
        string='Texturizable',
        help='Si la referencia se vende texturizada (ej. Blackout '
             'Texturizado), el portal muestra el catálogo de diseños de '
             'textura para que el cliente escoja el que se imprime.',
    )
    # Punto 14 (OBS REU TELAS): Sesgable vive en la referencia y hace match
    # con el campo «Sesgo» del portal: solo se muestra si la tela lo permite.
    is_sesgable = fields.Boolean(
        string='Sesgable',
        help='Si la tela permite sesgo, habilita el campo Sesgo en el '
             'portal; afecta cálculos de precios.',
    )
    # Revisión sprint 1 (f94): la cenefa en tela con corte «Entera» solo
    # está permitida en algunas telas.
    permite_cenefa_entera = fields.Boolean(
        string='Permite corte cenefa entera',
        help='Si la tela permite cortar la cenefa entera; si no, el corte '
             '«Cenefa Entera» se bloquea en el portal.',
    )


class SafraFabricColor(models.Model):
    _name = 'safra.fabric.color'
    _description = 'Color de Tela Safra'
    _order = 'name'

    fabric_id = fields.Many2one('safra.fabric', string='Referencia', required=True, ondelete='cascade', index=True)
    # Con producto vinculado, el producto ES el color: nombre y código se
    # toman de él (Código cotizador / referencia interna). Sin producto
    # (catálogo precargado del portal) siguen siendo editables.
    # OJO: name y code usan computes SEPARADOS a propósito: el cliente web
    # envía name (dirty por onchange) pero no code (celda readonly); si
    # compartieran método, Odoo marcaría el grupo completo como asignado y el
    # código quedaría vacío al guardar.
    code = fields.Char(
        string='Código', compute='_compute_code_from_product',
        inverse='_inverse_keep', store=True, readonly=False,
        help='Con producto vinculado se toma del Código cotizador (o la '
             'referencia interna) del producto.')
    name = fields.Char(
        string='Color', compute='_compute_name_from_product',
        inverse='_inverse_keep', store=True, readonly=False,
        help='Con producto vinculado, el nombre del color es el del producto.')
    # U_color del artículo vinculado (catálogo de colores), solo lectura.
    u_color_id = fields.Many2one(
        'safra.color', string='U_color',
        related='product_tmpl_id.safra_u_color', readonly=True)
    # Punto 17 (validado con el funcional): cómo se ve el color en el
    # portal — Etiqueta si está llena; si no, el U_color; si no, el nombre
    # del producto.
    etiqueta = fields.Char(
        string='Etiqueta',
        help='Nombre con el que este color se muestra en el portal. Vacío: '
             'se usa el U_color del producto y, en su defecto, el nombre '
             'del producto.')
    active = fields.Boolean(default=True)
    # Revisión 17-sep (apunte): los sistemas permitidos también se pueden
    # acotar POR ATRIBUTO — si el color tiene sistemas, solo se ofrece en
    # ellos; vacío hereda los de la referencia.
    system_ids = fields.Many2many(
        'safra.system', 'safra_fabric_color_system_rel', 'color_id', 'system_id',
        string='Sistemas (solo estos)',
        help='Si se llena, este color/atributo solo se ofrece en estos '
             'sistemas; vacío = aplica en todos los de la referencia.')

    # Reunión 13-oct (filas 56-57): en referencias de controles, para qué
    # motores sirve la línea (vacío = todos) y cuántos canales tiene. Un
    # mismo control del maestro puede ir en dos líneas (monocanal y
    # multicanal) con etiquetas distintas.
    motor_ids = fields.Many2many(
        'product.template', 'safra_fabric_color_motor_rel', 'color_id', 'motor_id',
        string='Motores (solo estos)', domain=[('safra_is_color', '=', True)],
        help='Motores con los que se ofrece este control; vacío = todos.')
    canales = fields.Integer(
        string='Canales',
        help='Canales del control en esta línea: 1 = monocanal (el portal no '
             'pide canal). Vacío: el U_Cantidad de canales del producto.')

    @api.model
    def _lineas_control(self, motor_product, system=None):
        """Líneas de la referencia de controles que sirven para el motor
        (columna Motores vacía = todos) y el sistema. None si todavía no hay
        referencias de controles (se usa el maestro del motor)."""
        Fabric = self.env['safra.fabric'].sudo()
        fabrics = Fabric.search([('category_id.es_control', '=', True)])
        if not fabrics:
            return None
        if system:
            fabrics = fabrics.filtered(lambda f: not f.system_ids or system in f.system_ids)
        lineas = fabrics.mapped('color_ids').filtered(
            lambda l: l.active
            and (not l.system_ids or (system and system in l.system_ids))
            and (not l.motor_ids or (motor_product and motor_product in l.motor_ids)))
        return lineas.sorted(lambda l: (bool(l.product_tmpl_id), l.fabric_id.name or '', l.id))

    def _valor_control(self):
        """Valor de la opción en el portal: '0' para «Sin control» (línea
        sin producto) y 'ref-<id>' para cada línea — un mismo control del
        maestro puede estar dos veces (monocanal / multicanal)."""
        self.ensure_one()
        return 'ref-%d' % self.id if self.product_tmpl_id else '0'

    @api.model
    def _linea_desde_valor(self, value):
        """Línea de referencia a partir del valor guardado en el portal
        ('ref-<id>' o el código de la línea)."""
        value = str(value or '')
        if value.startswith('ref-') and value[4:].isdigit():
            return self.sudo().with_context(active_test=False).browse(int(value[4:])).exists()
        if not value or value in ('0', 'sin'):
            return self.browse()
        return self.sudo().with_context(active_test=False).search([('code', '=', value)], limit=1)

    def _canales_portal(self):
        """Canales efectivos de la línea (la línea manda; el maestro es
        informativo y queda de respaldo)."""
        self.ensure_one()
        return self.canales or self.product_tmpl_id.safra_u_cantidad_canales or 0

    def _portal_label(self):
        """Nombre a mostrar en el portal: Etiqueta → U_color → producto."""
        self.ensure_one()
        return (self.etiqueta
                or self.u_color_id.name
                or self.product_tmpl_id.name
                or self.name or self.code or '')

    def _stock_disponible(self):
        """Stock del artículo del color, en las bodegas de la referencia."""
        self.ensure_one()
        product = self.product_tmpl_id
        if not product:
            return 0.0
        if self.fabric_id.warehouse_ids:
            product = product.with_context(warehouse_id=self.fabric_id.warehouse_ids.ids)
        return product.qty_available

    def _is_available_for_portal(self):
        """Disponibilidad POR COLOR: con mínimo configurado en la referencia,
        el color solo se ofrece si su artículo tiene stock suficiente."""
        self.ensure_one()
        if not self.fabric_id.cant_min_stock:
            return True
        return self._stock_disponible() >= self.fabric_id.cant_min_stock

    def _rollos_disponibles(self):
        """Pendiente 12.3 (Safra confirmó el 5-oct que los rollos son los
        LOTES): {lote: metros libres} del artículo del color, en las bodegas
        de la referencia (todas si no tiene). None si el artículo no se
        controla por lotes: entonces solo aplica la disponibilidad total."""
        self.ensure_one()
        tmpl = self.product_tmpl_id
        if not tmpl or tmpl.tracking == 'none':
            return None
        domain = [('product_id.product_tmpl_id', '=', tmpl.id),
                  ('location_id.usage', '=', 'internal'),
                  ('lot_id', '!=', False)]
        if self.fabric_id.warehouse_ids:
            domain.append(('location_id', 'child_of',
                           self.fabric_id.warehouse_ids.mapped('view_location_id').ids))
        rollos = {}
        for quant in self.env['stock.quant'].sudo().search(domain):
            libre = quant.quantity - quant.reserved_quantity
            if libre > 0:
                rollos[quant.lot_id] = rollos.get(quant.lot_id, 0.0) + libre
        return rollos

    @api.depends('product_tmpl_id', 'product_tmpl_id.name', 'fabric_id.name')
    def unlink(self):
        """Sprint1-rev (17-sep): borrar un color usado por cotizaciones
        revienta con un error de base de datos ilegible — mejor explicar y
        ofrecer el archivado."""
        Line = self.env['safra.quote.line'].sudo().with_context(active_test=False)
        for color in self:
            used = Line.search_count(['|', '|', ('color_id', '=', color.id),
                                      ('color_id_2', '=', color.id),
                                      ('color_id_3', '=', color.id)])
            if used:
                raise UserError(
                    'El color «%s» no se puede eliminar porque %d cotización(es) '
                    'lo usan. Desmarca su casilla «Activo» para archivarlo: deja '
                    'de ofrecerse en el portal sin perder el histórico.'
                    % (color.display_name, used))
        pares = [(c.product_tmpl_id, c.fabric_id) for c in self if c.product_tmpl_id]
        res = super().unlink()
        self._quitar_u_referencia(pares)
        return res

    def _compute_name_from_product(self):
        for rec in self:
            if rec.product_tmpl_id:
                # El artículo del maestro se llama "Referencia + Color" (como
                # en SAP); el desplegable del portal muestra solo el color.
                pname = rec.product_tmpl_id.name or ''
                fname = rec.fabric_id.name or ''
                if fname and pname.lower().startswith(fname.lower() + ' '):
                    rec.name = pname[len(fname) + 1:] or pname
                else:
                    rec.name = pname
            else:
                # Conserva el valor manual; sin nombre, usa el código (el
                # nombre está oculto en la vista: el producto es el color).
                rec.name = rec.name or rec.code

    @api.depends('product_tmpl_id', 'product_tmpl_id.safra_code',
                 'product_tmpl_id.default_code')
    def _compute_code_from_product(self):
        for rec in self:
            product = rec.product_tmpl_id
            if product:
                rec.code = product._safra_quoter_code() or rec.code
            else:
                rec.code = rec.code

    @api.model
    def _fix_codigo_relleno(self):
        """Sprint 1.2: referencias que tomaron el «0»/«False» de relleno del
        Código cotizador del maestro se recalculan con la referencia interna
        del producto (y el nombre, que el respaldo de create copiaba del
        código). Idempotente."""
        relleno = list(self.env['product.template']._SAFRA_CODE_RELLENO)
        Color = self.with_context(active_test=False)
        Color.search([('product_tmpl_id', '!=', False),
                      ('code', 'in', relleno)])._compute_code_from_product()
        Color.search([('product_tmpl_id', '!=', False),
                      ('name', 'in', relleno)])._compute_name_from_product()

    def _inverse_keep(self):
        # La escritura manual solo aplica a colores sin producto vinculado.
        pass

    @api.model_create_multi
    def create(self, vals_list):
        # El cliente web envía code/name en falso junto al producto (la celda
        # es readonly dinámico); si llegan vacíos con producto, se descartan
        # para que el cálculo desde el producto SÍ corra.
        for vals in vals_list:
            if vals.get('product_tmpl_id'):
                for key in ('code', 'name'):
                    if key in vals and not vals[key]:
                        vals.pop(key)
        records = super().create(vals_list)
        # Respaldo: el nombre está oculto en la vista (el producto es el
        # color); un color creado solo con código toma el código como nombre.
        relleno = self.env['product.template']._SAFRA_CODE_RELLENO
        for rec in records:
            if not rec.name and rec.code and rec.code not in relleno:
                rec.name = rec.code
        records._agregar_u_referencia()
        return records

    def write(self, vals):
        # Misma protección al editar: con producto vinculado, un code/name
        # vacío enviado por el cliente no pisa el valor calculado.
        has_product = vals.get('product_tmpl_id') or (self and all(r.product_tmpl_id for r in self))
        if has_product:
            for key in ('code', 'name'):
                if key in vals and not vals[key]:
                    vals.pop(key)
        cambia = 'product_tmpl_id' in vals or 'fabric_id' in vals
        antes = [(c.product_tmpl_id, c.fabric_id) for c in self if c.product_tmpl_id] if cambia else []
        res = super().write(vals)
        if cambia:
            # Primero se quita: al escribir el U_Referencia el producto
            # recrea las líneas que le falten, y la referencia anterior
            # todavía estaría en su lista.
            self._quitar_u_referencia(antes)
            self._agregar_u_referencia()
        return res

    # Reunión 09-oct (fila 19): sincronía en el otro sentido. Hasta ahora
    # el U_Referencia del producto creaba la línea en Referencias; ahora
    # agregar (o cambiar) una línea con producto en Referencias lo agrega
    # al U_Referencia del producto, y quitarla lo saca si el producto ya no
    # queda en ninguna línea de esa referencia (activa o archivada).
    def _agregar_u_referencia(self):
        for color in self.filtered('product_tmpl_id'):
            product = color.product_tmpl_id.sudo()
            if color.fabric_id not in product.safra_u_referencia_ids:
                product.write({'safra_u_referencia_ids': [(4, color.fabric_id.id)]})

    def _quitar_u_referencia(self, pares):
        Color = self.sudo().with_context(active_test=False)
        for product, fabric in set(pares):
            if not product.exists() or not fabric.exists():
                continue
            if fabric not in product.safra_u_referencia_ids:
                continue
            if not Color.search_count([('fabric_id', '=', fabric.id),
                                       ('product_tmpl_id', '=', product.id)]):
                product.sudo().write({'safra_u_referencia_ids': [(3, fabric.id)]})
    # Imagen del producto (tela + color), mostrada en la ficha técnica del portal.
    image = fields.Image(string='Imagen producto', max_width=512, max_height=512)

    def _ensure_products(self):
        """Todo color del portal debe existir en el maestro de productos.

        Un producto por NOMBRE de color: si «Blanco» existe en varias telas,
        todas comparten el mismo producto. El producto lleva el código corto
        del color solo cuando el nombre es único (los repetidos tienen un
        código distinto por tela — p. ej. «Blanco» tiene 73 — y cada color
        del portal conserva el suyo). Idempotente: corre en cada
        actualización.
        """
        Product = self.env['product.template'].sudo()
        colors = self if self else self.with_context(active_test=False).search([])
        missing = colors.filtered(lambda c: not c.product_tmpl_id and (c.name or c.code))
        if not missing:
            return
        # Agrupar por nombre normalizado (los repetidos comparten producto).
        groups = {}
        for color in missing:
            key = (color.name or color.code).strip().lower()
            groups.setdefault(key, []).append(color)
        # Reusar productos de color ya existentes con el mismo nombre.
        existing = {
            p.name.strip().lower(): p
            for p in Product.with_context(active_test=False).search([('safra_is_color', '=', True)])
        }
        for key, group in groups.items():
            product = existing.get(key)
            if not product:
                first = group[0]
                # Nombre canónico: la variante más frecuente del grupo,
                # evitando las escritas todo en mayúsculas si hay mixtas.
                variants = [(c.name or c.code).strip() for c in group]
                variants.sort(key=lambda v: (v.isupper(), -variants.count(v)))
                vals = {
                    'name': variants[0],
                    'safra_is_color': True,
                }
                if len(group) == 1:
                    # Nombre único: el producto lleva el código del color.
                    vals['default_code'] = first.code or False
                    vals['safra_code'] = first.code or False
                    if first.image:
                        vals['image_1920'] = first.image
                product = Product.create(vals)
                existing[key] = product
            for color in group:
                color.product_tmpl_id = product.id
    # En SAP cada tela+color es un artículo: relación al producto puntual.
    product_tmpl_id = fields.Many2one(
        'product.template', string='Producto (color)', ondelete='set null',
        domain=[('safra_is_color', '=', True)],
        help='Artículo del maestro (marcado "Es color del cotizador") para '
             'esta combinación de referencia y color.')
