# -*- coding: utf-8 -*-
import base64
import json
import re
from markupsafe import Markup
from odoo import http
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal


class SafraPortalController(CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'safra_quote_count' in counters:
            partner = request.env.user.partner_id
            values['safra_quote_count'] = request.env['safra.quote'].sudo().search_count([
                ('partner_id', '=', partner.id),
            ])
        return values


class SafraQuoterController(http.Controller):

    # Textos de ayuda por código de campo, tomados del portal de pedidos del
    # cliente. Se usan como respaldo cuando el campo no define help_text propio.
    FIELD_HELP = {
        'coordinado': 'Seleccione el coordinado',
        'same_header': 'Configura la secuencia cuando varias persianas comparten cabezal',
        'sequence_name': 'Seleccione la secuencia',
        'perfil': 'Seleccione el tipo de Perfil para su persiana',
        'mando_position': 'Seleccione la ubicación del mando',
        'orientation': 'Seleccione la orientación del Enrollado',
        'motor': 'Seleccione el tipo de motor',
        'aligned': 'Cálculo automático que indica si las persianas quedan alineadas',
        'unificacion_mando': 'Unifica el calibre del tubo; recalcula tubo, soporte y mecanismo',
        'cabezal_tipo': 'Seleccione el Cabezal',
        'cabezal_forrado': 'Seleccione si el cabezal es forrado',
        'cabezal_tela': 'Tela con la que se forra el cabezal',
        'tipo_plano': 'Seleccione el tipo de plano',
        'num_segmento': 'Segmento del plano que ocupa este cabezal',
        'control': 'Seleccione una opción de control',
        'control_channel': 'Seleccione el canal del control',
        'motor_support_type': 'Seleccione el tipo de soporte Motor',
        'interruptor_rf': 'Seleccione un interruptor',
        'requires_charger': 'Seleccionar si desea el cargador.',
        'cenefa_type': 'Seleccione la cenefa de su preferencia',
        'cenefa_lateral': 'Seleccione la configuración de laterales de la cenefa',
        'cenefa_lined': 'Seleccione si requiere que la cenefa sea forrada',
        'cover_light_profile': 'Adición a la persiana; solo aplica para telas rígidas',
        'coverlight_felpa': 'Determina si el perfil CoverLight lleva felpa',
        'coverlight_45': 'Seleccione si requiere que el perfil lleve corte a 45°',
        'extra_chain': 'Digite la "altura total" que necesita de la cadena. Cero (0) si no requiere',
        'design_print': 'Active para elegir el diseño a imprimir',
        'custom_design': 'Elija un diseño del catálogo con imágenes, o marque «Diseño propio» para subir su imagen',
        'print_m2': 'Calculado automáticamente: ancho × alto',
        'escuadras': 'Seleccione la escuadra',
        'design_exterior': 'El diseño se instalará hacia el Exterior',
        'location': 'Seleccione la localización física donde ubicará su producto. Cada espacio representa su necesidad. Ejm: "Habitación, Oficina, Sala, Comedor, etc"',
        'tela_al_reves': 'Instrucción para producción cuando la tela es doblefaz',
        'atravesar_tela': 'Seleccione esta opción si requiere que se corte la tela atravesada',
        'enclosed': 'Seleccione esta opción si requiere una persiana con medidas exactas para Encajonar en una ventana',
        'bolsillo_size': 'Seleccione el tamaño del bolsillo para "Enrollable Toldo"',
    }
    # Notas resaltadas (amarillas) por código de campo.
    FIELD_NOTE = {
        'bolsillo_size': 'Solo usar este campo, exclusivamente para bolsillo grande',
    }
    # Campos cuya etiqueta se resalta (naranja) en el portal del cliente.
    FIELD_HIGHLIGHT = {'cenefa_type'}

    def _system_fabrics(self, system):
        """Telas que admite el sistema (filtradas por la relación tela<->sistema).

        Si el sistema no tiene telas asociadas todavía, devuelve todas las activas
        como respaldo para no dejar el desplegable vacío.
        """
        Fabric = request.env['safra.fabric'].sudo()
        fabrics = Fabric.search([('active', '=', True), ('system_ids', 'in', system.id)], order='name') if system else Fabric.browse()
        if system and not fabrics:
            fabrics = Fabric.search([('active', '=', True)], order='name')
        # Punto 3 (OBS REU TELAS): con cantidad mínima de stock configurada
        # en la referencia, la tela solo se ofrece si el stock disponible de
        # sus artículos la supera.
        # Sprint1-rev (17-sep): las telas sin stock ya no se ocultan — viajan
        # marcadas y el portal las muestra en gris (no seleccionables).
        return [{
            'id': f.id, 'name': f.name, 'code': f.code,
            'available': f._is_available_for_portal(),
            'printable': f.is_printable,
            'doublefaced': f.is_doublefaced,
            # 'si_cliente' muestra la opción Atravesar Tela al cliente;
            # el tipo completo queda para la cascada de disponibilidad.
            'pierceable': f.pierceable_type == 'si_cliente',
            'pierceable_type': f.pierceable_type,
            # Pendientes 24-sep (12.1/12.2): ancho de rollo (mayor U_Ancho
            # de los artículos) para avisar el corte atravesado en vivo.
            'rollo': max([c.product_tmpl_id.safra_u_ancho or 0.0
                          for c in f.color_ids if c.product_tmpl_id] or [0.0]),
            'anadido': f.is_anadido,
            'sesgable': f.is_sesgable,
            # OBS 11-sep: Blackout Texturizado — habilita el catálogo de
            # diseños de textura.
            'texturable': f.is_texturable,
            # Reunión 09-oct (fila 20): familias para filtrar las
            # referencias del Sheer 2 en 1.
            'blackout': f.is_blackout,
            'sheer': f.is_sheer,
            # Fase 5.1: densidad de la tela (hoja DENSIDAD, g/m²) para
            # filtrar insumos con densidad máxima (Sheer Deluxe).
            'densidad': f.peso_gm2 or 0,
        } for f in fabrics]

    @http.route('/cotizador', type='http', auth='user', website=True)
    def quoter_form(self, **kwargs):
        # El selector solo muestra sistemas cuyo producto del maestro tiene el
        # check "Es sistema del cotizador": desmarcarlo lo saca del portal.
        systems = request.env['safra.system'].sudo().search([
            ('active', '=', True),
            ('product_tmpl_id.safra_is_system', '=', True),
        ], order='name')
        # Pendientes 24-sep (1.1): sistemas restringidos por grupo de
        # usuarios (vacío = visible para todos).
        systems = systems.filtered(
            lambda s: s._visible_for_user(request.env.user))
        systems_data = [{'id': s.id, 'name': s.name} for s in systems]
        # Sin sistema preseleccionado (F3 de la matriz): el formulario se
        # pinta cuando el cliente elige el sistema.
        return request.render('website_quotes_safra.portal_quoter_form', {
            'systems_json': self._json_for_script(systems_data),
            'default_config_json': self._json_for_script({}),
            'default_system_id': 0,
        })

    def _json_for_script(self, data):
        # Markup evita que QWeb escape las comillas del JSON; escapamos '<'
        # para impedir que un '</script>' rompa el bloque embebido.
        return Markup(json.dumps(data).replace('<', '\\u003c'))

    def _ref_category_options(self, category, system=None):
        """Punto 16 (OBS REU TELAS): opciones de un campo «Referencia
        (categoría)» — la tabla de productos relacionados en las
        referencias de esa categoría (ej: Sesgo), respetando la
        disponibilidad por stock de cada color/producto.

        Misma lógica del P1 en las telas: una referencia con sistemas
        asociados solo se ofrece en esos sistemas; sin sistemas asociados
        aplica para todos."""
        # None = categoría sin referencias (el campo cae al respaldo de sus
        # opciones de catálogo); lista vacía = hay referencias pero ninguna
        # aplica (por sistema o por stock) y el campo queda sin opciones.
        if not category:
            return None
        fabrics = request.env['safra.fabric'].sudo().search([
            ('category_id', '=', category.id),
        ])
        if not fabrics:
            return None
        if system:
            fabrics = fabrics.filtered(
                lambda f: not f.system_ids or system in f.system_ids)
        multi = len(fabrics) > 1
        options = []
        for fabric in fabrics:
            for color in fabric.color_ids.filtered(
                    lambda c: c.active and c._is_available_for_portal()
                    and (not c.system_ids or (system and system in c.system_ids))):
                name = color._portal_label()
                product = color.product_tmpl_id
                # Pendientes 24-sep (8.3): imagen del atributo (línea de la
                # referencia) con respaldo en la imagen del artículo.
                img = ''
                if color.image:
                    img = '/web/image?model=safra.fabric.color&id=%d&field=image' % color.id
                elif product.image_128:
                    img = '/web/image?model=product.template&id=%d&field=image_256' % product.id
                options.append({
                    # Reunión 13-oct: una línea sin producto es la opción
                    # «Sin …» (p. ej. Sin interruptor): el portal la reconoce.
                    'sin': 0 if product else 1,
                    'value': color.code or str(color.id),
                    'label': ('%s %s' % (fabric.name, name)) if multi else name,
                    'img': img,
                    # Fase 5.1 (obs perfiles): densidad máxima de tela que
                    # soporta el insumo (U_Densidad del producto); el portal
                    # oculta la opción si la tela elegida la supera.
                    'dmax': product.safra_u_densidad or 0,
                    # Fase 5.4a: parametrización del producto que gobierna
                    # campos dependientes (¿Cabezal Forrado?, ¿Requiere
                    # Cargador?).
                    'forrado': 1 if product.safra_u_forrado else 0,
                    'cargador': 1 if product.safra_u_requiere_cargador else 0,
                    # Pendientes 24-sep (14.1): el módulo RF solo aparece
                    # para motores marcados en el maestro.
                    'interruptor': 1 if product.safra_u_requiere_interruptor_rf else 0,
                })
        options.sort(key=lambda o: o['label'])
        # Revisión 17-sep (cruce perfil x coordinado, min 00:10 de la
        # sesión): los insumos que existen en el maestro uno por color (ej.
        # perfil cuadrado blanco/ivory/...) comparten etiqueta — en el
        # portal la etiqueta repetida se muestra UNA sola vez; el artículo
        # exacto se resuelve después con el coordinado elegido (U_color).
        seen, dedup = set(), []
        for o in options:
            key = o['label'].strip().lower()
            if key in seen:
                continue
            seen.add(key)
            dedup.append(o)
        return dedup

    def _design_options(self, dtype='impresion'):
        """Puntos 10-11: catálogo de diseños (safra.design) del tipo pedido
        (impresión, o textura para el Blackout Texturizado)."""
        designs = request.env['safra.design'].sudo().search([('dtype', '=', dtype)])
        return [{'value': d.code, 'label': d.name or d.code, 'img': d._image_src()}
                for d in designs]

    def _field_options(self, field, system, opt_recs):
        """Opciones de un campo según su tipo (catálogo, categoría o diseños)."""
        if field.field_type == 'ref_categoria':
            ref_opts = self._ref_category_options(field.ref_category_id, system)
            if ref_opts is not None:
                return ref_opts
        elif field.field_type == 'design':
            return self._design_options(
                'textura' if 'textura' in (field.code or '') else 'impresion')
        # Revisión 17-sep: miniatura de la opción (aperturas, planos…).
        # Las opciones POR SISTEMA se recrean en cada actualización del
        # módulo (XML con (5,0,0)) y perderían su imagen: si no tienen una
        # propia, heredan la de la opción del CATÁLOGO con el mismo valor o
        # nombre — las imágenes se cargan una sola vez donde persisten.
        # Apunte 23-sep: una opción del catálogo con sistemas propios solo
        # se ofrece en esos sistemas.
        if opt_recs and opt_recs[0]._name == 'safra.field.option' and system:
            opt_recs = opt_recs.filtered(
                lambda o: not o.system_ids or system in o.system_ids)
        catalog = {}
        if opt_recs and opt_recs[0]._name == 'safra.system.field.option':
            for co in field.option_ids:
                if co.image:
                    catalog[str(co.value)] = co
                    catalog[(co.name or '').strip().lower()] = co

        def _img(o):
            if getattr(o, 'image', False):
                return '/web/image?model=%s&id=%d&field=image' % (o._name, o.id)
            oname = (o.name or '').strip().lower()
            co = catalog.get(str(o.value)) or catalog.get(oname)
            if not co and oname:
                # último recurso: contención de nombre («Derecha» hereda de
                # «Unilateral Derecha» y viceversa).
                for k, v in catalog.items():
                    if not k.isdigit() and (oname in k or k in oname):
                        co = v
                        break
            if co:
                return '/web/image?model=%s&id=%d&field=image' % (co._name, co.id)
            return None

        # 'seg' solo existe en el catálogo global (safra.field.option);
        # las opciones override por sistema no lo llevan.
        return [{'value': o.value, 'label': o.name, 'img': _img(o),
                 'seg': getattr(o, 'segmentos', 0) or 0} for o in opt_recs]

    @staticmethod
    def _apertura_antes_de_lamas(fields):
        """Reunión 09-oct (fila 18): con fórmula de máximo de lamas, el
        «Tipo de Apertura» (sección RIEL) es dato de entrada del cálculo y se
        muestra justo antes de «Máximo total lamas» (sección TELA). Se mueve
        solo en la presentación: la sección del campo es global y en los
        paneles sigue en RIEL."""
        codes = [f['code'] for f in fields]
        if 'apertura' not in codes or 'quantity_lamas' not in codes:
            return
        apertura = fields.pop(codes.index('apertura'))
        destino = next(i for i, f in enumerate(fields) if f['code'] == 'quantity_lamas')
        lamas = fields[destino]
        apertura.update({k: lamas[k] for k in ('section', 'section_code', 'section_seq', 'zone')})
        apertura['seq'] = lamas['seq']
        fields.insert(destino, apertura)

    def _display_mode(self, field, system):
        """Reunión 13-oct (filas 50-52): en un campo «Referencia
        (categoría)» manda la presentación definida en la referencia (la
        primera que aplique al sistema y la tenga); si no, la del campo."""
        if field.field_type == 'ref_categoria' and field.ref_category_id:
            fabrics = request.env['safra.fabric'].sudo().search([
                ('category_id', '=', field.ref_category_id.id), ('display_mode', '!=', False)])
            fabrics = fabrics.filtered(lambda f: not f.system_ids or (system and system in f.system_ids))
            if fabrics:
                return fabrics[0].display_mode
        return field.display_mode or 'auto'

    def _familias_ref(self, system):
        if (system.code or '') != '61':
            return {}
        cfg = request.env['safra.validation.rule'].sudo().get_config('V_SHEER2EN1_REF') or {}
        if cfg and not cfg.get('active', True):
            return {}
        return {'fabric_id': 'blackout', 'fabric_id_2': 'sheer'}

    def _aperturas_con_formula(self, system=None):
        """Aperturas de Panel Track que tienen valor en la fórmula de
        combinaciones del sistema o, sin regla, las cuatro del documento
        FORMULA FINAL (respaldo de compute_configs)."""
        regla = request.env['safra.panel.combo.rule'].sudo()._regla(system)
        return regla._aperturas() if regla else [
            'unilateral_derecha', 'unilateral_izquierda', 'centro', 'extremos']

    def _build_form_config(self, system):
        """Estructura de secciones y campos configurados para un sistema."""
        if not system:
            return {'fields': []}
        maps = request.env['safra.system.field'].sudo().search([
            ('system_id', '=', system.id),
            ('active', '=', True),
            ('field_id.active', '=', True),
        ])
        # Lista plana de campos ordenada por la secuencia del mapeo, igual que el
        # portal del cliente (una sola columna, sin subsecciones de color).
        # Convención de zonas: secuencia < ACC_THRESHOLD => bloque superior
        # (dimensiones, tela, coordinado); secuencia >= ACC_THRESHOLD => sección
        # "Accesorios". El bloque de Producto/Ficha/Precio se inserta entre ambas.
        ACC_THRESHOLD = 1000
        user_groups = request.env.user.all_group_ids
        fields = []
        for m in maps:
            field = m.field_id
            # Campos restringidos a un grupo (ej: Exhibición) solo se emiten
            # para usuarios que pertenecen a él.
            if field.group_id and field.group_id not in user_groups:
                continue
            # Override por sistema (opciones, dependencia) con respaldo a lo global.
            opt_recs = m.option_ids or field.option_ids
            if m.clear_depends:
                dep_field, dep_value = False, False
            elif m.depends_field_id:
                dep_field, dep_value = m.depends_field_id, m.depends_value
            else:
                dep_field, dep_value = field.depends_field_id, field.depends_value
            fields.append({
                'code': field.code,
                'label': m.label_override or field.name,
                'type': field.field_type,
                'col': field.col_size or 4,
                'required': field.required or m.required,
                'placeholder': field.placeholder or '',
                'default': field.default_value or '',
                'help': m.help_override or field.help_text or self.FIELD_HELP.get(field.code, ''),
                'note': m.note_override or self.FIELD_NOTE.get(field.code, ''),
                'highlight': m.highlight or field.code in self.FIELD_HIGHLIGHT,
                # dep_value vacío (False) viaja como '' — en el JS significa
                # «visible con cualquier valor del campo padre».
                'depends': ({'field': dep_field.code, 'value': dep_value or ''} if dep_field else None),
                'flag': field.fabric_flag or None,
                # Pendientes 24-sep (8.3): modo de presentación de opciones.
                'display': self._display_mode(field, system),
                'seq': m.sequence,
                'zone': 'acc' if m.sequence >= ACC_THRESHOLD else 'top',
                # Separadores de la hoja «Matriz Unificada»: el portal pinta
                # el título cada vez que cambia la sección.
                'section': field.section_id.name or '',
                'section_code': field.section_id.code or '',
                'section_seq': field.section_id.sequence or 0,
                # Fase 5.1: mientras la categoría no tenga referencias, el
                # campo conserva sus opciones de catálogo (respaldo de
                # transición). Con referencias existentes, la lista puede
                # quedar vacía (filtro por sistema o por stock).
                'options': self._field_options(field, system, opt_recs),
            })
        # Orden: primero por la sección de la matriz, dentro de ella por la
        # secuencia configurada del sistema.
        fields.sort(key=lambda f: (f['section_seq'], f['seq']))
        # Revisión 17-sep: sistemas con fórmula de máximo total de lamas
        # (Vertical/Vintage) — el portal calcula y fija la cantidad.
        max_lamas = bool(request.env['safra.lamas.rule'].sudo().search_count(
            [('system_ids', 'in', system.id)]))
        if max_lamas:
            self._apertura_antes_de_lamas(fields)
        return {
            'fields': fields,
            'max_lamas': max_lamas,
            # Reunión 24-sep: el filtro de combinación referencia+color
            # repetida obedece a la regla V_TELAS_REPETIDAS (hoy inactiva:
            # el cliente puede alternar la misma tela y color).
            'dup_pairs': bool((request.env['safra.validation.rule'].sudo()
                               .get_config('V_TELAS_REPETIDAS') or {}).get('active')),
            'fabrics': self._system_fabrics(system),
            # Límites efectivos: el producto terminado asociado manda
            # (U_AnchoMin/Max, U_AltoMin/Max) y el sistema es el respaldo.
            'ficha': system._tech_limits(),
            # Reunión 28-sep (fila 70): el mecanismo se calcula con la tabla
            # de estructura; solo se muestra si el sistema la tiene.
            'has_structure': bool(request.env['safra.structure.rule'].sudo().search_count(
                [('system_ids', 'in', system.id)])),
            # Reunión 28-sep (fila 3): la ficha que se muestra cuando la
            # persiana se marca como Exhibición.
            'ficha_exh': system._tech_limits(exhibition=True),
            # Reunión 09-oct (fila 20): en el Sheer 2 en 1 el orden es
            # estricto — la Referencia 1 solo ofrece telas Blackout y la
            # Referencia 2 solo Sheer (misma regla que E20009, si está
            # activa). En el Enrollable 2 en 1 no hay orden.
            'familias_ref': self._familias_ref(system),
            # Pendiente 2 (Safra, 5-oct): una apertura sin fórmula configurada
            # no se muestra en el portal (hoy, la Apertura Libre).
            'aperturas_formula': self._aperturas_con_formula(system),
            'img_group': system.img_group or '',
            'img_base': self.CLIENT_IMG_BASE,
        }

    # Repositorio público de imágenes de producto del cliente. Se usa como
    # fuente de la imagen del producto; si no existe, el portal (y nosotros)
    # mostramos el marcador "imagen no encontrada".
    CLIENT_IMG_BASE = 'https://portal.safrasas.com/Images/SafraImages'

    @http.route('/cotizador/ajax/config', type='jsonrpc', auth='user')
    def ajax_config(self, system_id=None):
        if not system_id:
            return {'fields': []}
        system = request.env['safra.system'].sudo().browse(int(system_id))
        if not system.exists() or not system._visible_for_user(request.env.user):
            return {'fields': []}
        return self._build_form_config(system)

    def _validate_lines(self, lines_vals, cross=True):
        """Motor de validaciones sobre las líneas del formulario; la lógica
        vive en safra.quote.line._validate_order (la misma que revalida una
        cotización guardada al confirmarla)."""
        return request.env['safra.quote.line'].sudo()._validate_order(
            lines_vals, cross=cross)

    @http.route('/cotizador/ajax/validar', type='jsonrpc', auth='user')
    def ajax_validar(self, single=None, **params):
        """Prevalidación del formulario antes del submit (mismos names del form).

        Con `single` (validación de UNA línea desde «Guardar línea») se
        omiten las reglas cruzadas del pedido (alineado, secuencias, canal
        compartido): con una sola línea siempre fallarían — p. ej. E20010
        exige la pareja, que sí existe en el pedido completo."""
        return self._validate_lines(self._parse_lines(params),
                                    cross=not single)

    @http.route('/cotizador/submit', type='http', auth='user', website=True, methods=['POST'], csrf=True)
    def quoter_submit(self, **post):
        partner = request.env.user.partner_id

        lines = self._parse_lines(post)
        # Respaldo servidor del motor de validaciones: los errores bloquean
        # el pedido aunque el JS no haya corrido la prevalidación.
        errors = [i for i in self._validate_lines(lines) if i['severity'] == 'error']
        # Puntos 10-11 (ajuste 10-sep): el archivo con formato de aprobación
        # solo es obligatorio para «Diseño propio» (OTROS) — los diseños del
        # catálogo ya tienen su imagen.
        files = request.httprequest.files
        for n, line_vals in enumerate(lines, start=1):
            if line_vals.get('custom_design') == 'OTROS':
                post_idx = line_vals['sequence'] // 10 - 1
                upload = files.get('design_file_%d' % post_idx)
                if not (upload and upload.filename):
                    errors.append({
                        'line': n, 'code': 'V_DISENO_ARCHIVO', 'severity': 'error',
                        'message': 'Diseño propio: adjunte el archivo '
                                   'del diseño a imprimir (JPG, PNG o PDF).',
                    })
        if errors:
            return request.render('website_quotes_safra.portal_quoter_errors', {
                'errors': errors,
            })

        quote = request.env['safra.quote'].sudo().create({
            'partner_id': partner.id,
            'user_id': request.env.user.id,
            # Revisión sprint 1: Safra Express es a nivel de pedido.
            'safra_express': bool(post.get('safra_express')),
        })
        for line_vals in lines:
            line_vals['quote_id'] = quote.id
            line = request.env['safra.quote.line'].sudo().create(line_vals)
            # Diseño personalizado: guardar el archivo, analizar sus
            # dimensiones y abrir el ticket para el área de diseño.
            if line.custom_design:
                post_idx = line_vals['sequence'] // 10 - 1
                upload = files.get('design_file_%d' % post_idx)
                if upload and upload.filename:
                    data = upload.read()
                    analysis, _warn = line._analyze_design(data, upload.filename)
                    line.write({
                        'design_image': base64.b64encode(data),
                        'design_filename': upload.filename,
                        'design_analysis': analysis,
                    })
                line._create_design_ticket()

        # Pendiente 12.3: rollo (lote) sugerido para la tela de cada persiana.
        quote._sugerir_rollos()
        # Fase 5.3: con diseños personalizados el pedido queda pendiente de
        # la aprobación del área de diseño.
        quote._update_design_state()

        return request.redirect('/mis-cotizaciones/%d' % quote.id)

    @http.route('/mis-cotizaciones', type='http', auth='user', website=True)
    def my_quotes(self, **kwargs):
        partner = request.env.user.partner_id
        quotes = request.env['safra.quote'].sudo().search([
            ('partner_id', '=', partner.id),
        ], order='date desc')
        return request.render('website_quotes_safra.portal_my_quotes', {
            'quotes': quotes,
        })

    @http.route('/mis-cotizaciones/<int:quote_id>', type='http', auth='user', website=True)
    def quote_detail(self, quote_id, **kwargs):
        partner = request.env.user.partner_id
        quote = request.env['safra.quote'].sudo().browse(quote_id)
        if not quote.exists() or quote.partner_id.id != partner.id:
            return request.not_found()
        return request.render('website_quotes_safra.portal_quote_detail', {
            'quote': quote,
            'confirmacion': request.session.pop('safra_confirmacion', None),
            'confirmables': self.PORTAL_CONFIRMABLES,
        })

    # Reunión 09-oct (fila 2): el distribuidor confirma SUS cotizaciones
    # desde el portal. Mientras el área de diseño no apruebe, la cotización
    # con diseño personalizado espera (no se ofrece el botón).
    PORTAL_CONFIRMABLES = ('draft', 'design_approved')

    @http.route('/mis-cotizaciones/<int:quote_id>/confirmar', type='http', auth='user',
                website=True, methods=['POST'])
    def quote_confirm(self, quote_id, **kwargs):
        """Misma lógica que la confirmación del backoffice: se revalida la
        cotización y, si ya no cumple, se ANULA con el motivo en su
        historial; si cumple, queda confirmada."""
        partner = request.env.user.partner_id
        quote = request.env['safra.quote'].sudo().browse(quote_id)
        if not quote.exists() or quote.partner_id.id != partner.id:
            return request.not_found()
        if quote.state in self.PORTAL_CONFIRMABLES:
            anuladas = quote._anular_si_invalida()
            if anuladas:
                request.session['safra_confirmacion'] = {
                    'ok': False,
                    'errores': [{'line': e['line'], 'message': e['message']}
                                for e in anuladas.get(quote, [])],
                }
            else:
                quote.write({'state': 'confirmed'})
                quote.message_post(body='Cotización confirmada por el cliente desde el portal.')
                request.session['safra_confirmacion'] = {'ok': True}
        return request.redirect('/mis-cotizaciones/%d' % quote.id)

    @http.route('/cotizador/ajax/colores', type='jsonrpc', auth='user')
    def ajax_colores(self, fabric_id=None, system_id=None):
        if not fabric_id:
            return []
        colors = request.env['safra.fabric.color'].sudo().search([
            ('fabric_id', '=', int(fabric_id)),
            ('active', '=', True),
        ], order='name')
        # Apunte 23-sep: sistemas permitidos POR ATRIBUTO — un color con
        # sistemas propios solo se ofrece en ellos.
        if system_id:
            sid = int(system_id)
            colors = colors.filtered(
                lambda c: not c.system_ids or sid in c.system_ids.ids)
        # Sprint1-rev (17-sep): los colores sin stock suficiente ya no se
        # ocultan — viajan con available=False y el portal los muestra en
        # gris para que el cliente sepa que existen.
        # Punto 17: el nombre visible sigue la prioridad Etiqueta → U_color
        # → nombre del producto.
        result = [{'id': c.id, 'name': c._portal_label(), 'code': c.code,
                   'available': c._is_available_for_portal()} for c in colors]
        result.sort(key=lambda r: r['name'])
        return result

    @http.route('/cotizador/ajax/motor_extras', type='jsonrpc', auth='user')
    def ajax_motor_extras(self, motor=None, system_id=None):
        """Pendientes 24-sep (15.1/16.1): asociaciones del motor en el
        MAESTRO — controles compatibles (con su cantidad de canales) y las
        marcas de módulo RF / cargador con sus items.

        Reunión 13-oct (filas 56-57): si existe la referencia de controles
        (categoría marcada «Controles de motor»), los controles salen de sus
        líneas: las que sirven para este motor (columna Motores vacía = todos)
        y en el sistema, con los canales de cada línea. Una línea sin
        producto es la opción «Sin control» con su etiqueta."""
        if not motor:
            return {}
        Color = request.env['safra.fabric.color'].sudo()
        color = Color.search([('code', '=', str(motor))], limit=1)
        if not color and str(motor).isdigit():
            color = Color.browse(int(motor))
            color = color if color.exists() else Color
        product = color.product_tmpl_id if color else None
        if not product:
            return {}
        system = None
        if system_id:
            system = request.env['safra.system'].sudo().browse(int(system_id)).exists() or None
        lineas = Color._lineas_control(product, system)
        if lineas is not None:
            controls = [{
                'value': l._valor_control(),
                'label': l._portal_label(),
                'canales': l._canales_portal(),
            } for l in lineas]
        else:
            controls = [{
                'value': c._safra_quoter_code() or str(c.id),
                'label': c.name,
                'canales': c.safra_u_cantidad_canales or 0,
            } for c in product.safra_u_control_ids]
        return {
            'interruptor': bool(product.safra_u_requiere_interruptor_rf),
            'cargador': bool(product.safra_u_requiere_cargador),
            'controls': controls,
            'desde_referencias': lineas is not None,
        }

    @http.route('/cotizador/ajax/max_lamas', type='jsonrpc', auth='user')
    def ajax_max_lamas(self, system_id=None, width=0.0, apertura=None, motorized=False,
                       campos=None):
        """Revisión 17-sep: máximo total de lamas/pantógrafos según la
        fórmula configurada (Vertical/Vintage/Vintage Std)."""
        try:
            width = float(str(width or 0).replace(',', '.'))
        except (TypeError, ValueError):
            width = 0.0
        system = request.env['safra.system'].sudo().browse(int(system_id)) if system_id else None
        ap_map = {'1': 'derecha', '2': 'izquierda', '3': 'extremos', '4': 'centro'}
        ap = ap_map.get(str(apertura or ''), str(apertura or ''))
        maximo = request.env['safra.lamas.rule'].sudo().compute_max(
            system, width, ap, motorized=bool(motorized), campos=campos)
        return {'max': maximo}

    @http.route('/cotizador/ajax/panel_lamas', type='jsonrpc', auth='user')
    def ajax_panel_lamas(self, width=0.0, traslape=None, lamas=None, campos=None, system_id=None):
        """P19: tabla de combinaciones válidas de Panel Track.

        Con `lamas` devuelve solo las configuraciones de ese total de telos;
        sin él, todas las combinaciones posibles para el ancho digitado."""
        def _f(raw, default=0.0):
            try:
                return float(str(raw).replace(',', '.'))
            except (TypeError, ValueError):
                return default
        w = _f(width)
        # Traslape por defecto 8 cm (obs H35 de la matriz).
        t = _f(traslape, 0.08) if traslape not in (None, '') else 0.08
        Panel = request.env['safra.panel.track'].sudo()
        try:
            n = int(lamas) if lamas else 0
        except (TypeError, ValueError):
            n = 0
        system = None
        if system_id:
            system = request.env['safra.system'].sudo().browse(int(system_id)).exists() or None
        rows = (Panel.compute_configs(w, t, n, campos=campos, system=system) if n
                else Panel.suggest_configs(w, t, campos=campos, system=system))
        # Sin combinaciones: se informa el rango de anchos que sí funciona
        # (pregunta de pruebas: «¿cómo veo qué configuración es permitida?»).
        return {
            'rows': rows,
            'rango': Panel.viable_width_range(t, telos=n or None, campos=campos, system=system) if not rows else None,
            'traslape': t,
        }

    @http.route('/cotizador/ajax/precio', type='jsonrpc', auth='user')
    def ajax_precio(self, fabric_id=None, color_id=None, width=0.0, height=0.0,
                    system_id=None, has_motor=False, cabezal=None, perfil=None,
                    motor=None, unificacion=None, **kwargs):
        # Placeholder: precio base por m². La lógica real se implementará
        # cuando se carguen las listas de precio de Safra.
        try:
            w = float(width)
            h = float(height)
        except (TypeError, ValueError):
            return {'price': 0}
        base = round(w * h * 1000, 0)  # valor provisional
        discount_pct = 0
        price = round(base * (1 - discount_pct / 100.0), 0)
        # Estructura por ancho (hojas 3/4/5 de la matriz): tubo, mecanismo,
        # soporte, terminal y cabezal según sistema, accionamiento y ancho,
        # más las fórmulas de alto/peso máximo cuando la tela está
        # parametrizada (peso g/m² y grosor mm).
        mechanism = None
        limits = {}
        kit_data = None
        tubo_data = None
        if system_id:
            system = request.env['safra.system'].sudo().browse(int(system_id))
            system = system if system.exists() else None
            cab = (cabezal or '').lower()
            cab_type = 'redondo' if 'redondo' in cab else ('cuadrado' if 'cuadrado' in cab else None)
            Rule = request.env['safra.structure.rule'].sudo()
            # Sprint 1.3 (fila 73): con Unificación Mando la estructura y los
            # límites salen del tubo unificado (mayor al calculado).
            base_rule, rule = Rule.resolve(system, w, motorized=bool(has_motor),
                                           cabezal=cab_type, unificacion=unificacion or None)
            if base_rule:
                tubos = Rule.tubos_ordenados(system, motorized=bool(has_motor))
                pos = tubos.index(base_rule.tubo) if base_rule.tubo in tubos else len(tubos)
                tubo_data = {
                    'base': base_rule.tubo,
                    'efectivo': rule.tubo,
                    'mayores': tubos[pos + 1:],
                    'orden': tubos,
                }
            if rule:
                mechanism = rule._mechanism_line(cabezal=cabezal or None)
                fabric = request.env['safra.fabric'].sudo().browse(int(fabric_id)) if fabric_id else None
                peso_perfil = 0.0
                if perfil:
                    opt = request.env['safra.field.option'].sudo().search([
                        ('field_id.code', 'in', ['perfil', 'perfileria2', 'perfil_sheer']),
                        ('value', '=', str(perfil)), ('peso_gm', '>', 0),
                    ], limit=1)
                    peso_perfil = opt.peso_gm
                    if not peso_perfil:
                        # Fase 5.1: el perfil viene del menú Referencias
                        # (valor = código del producto); su peso lineal se
                        # parametriza en U_Peso del artículo.
                        color = request.env['safra.fabric.color'].sudo().search(
                            [('code', '=', str(perfil))], limit=1)
                        peso_perfil = color.product_tmpl_id.safra_u_peso or 0.0
                limits = rule.compute_limits(
                    w, h,
                    peso_tela=fabric.peso_gm2 if fabric and fabric.exists() else 0.0,
                    grosor_tela=fabric.grosor_mm if fabric and fabric.exists() else 0.0,
                    peso_perfil=peso_perfil,
                    factor=system.weight_factor if system else 1.0,
                )
                # Sin motor y el peso pide más que el mecanismo manual: ¿la
                # regla motorizada del mismo ancho sí lo soporta?
                if limits.get('peso_ok') is False and not has_motor:
                    rule_motor = Rule.find_rule(system, w, motorized=True, cabezal=cab_type)
                    if rule_motor and rule_motor.carga_maxima and limits.get('peso_total'):
                        limits['requiere_motor'] = limits['peso_total'] <= rule_motor.carga_maxima
                # Kit motorizado (hoja 2): componentes y controles compatibles
                # para el motor elegido sobre el tubo de la regla.
                if has_motor and motor:
                    kit = rule._kit_for(motor)
                    if kit:
                        kit_data = {
                            'motor': kit.motor_name,
                            'tubo': kit.tubo,
                            'corona': kit.corona or '',
                            'adaptador': kit.adaptador or '',
                            'soportes': kit.soportes or '',
                            'interruptor': kit.interruptor or '',
                            'controls': [v.strip() for v in (kit.control_values or '').split(',') if v.strip()],
                            'aplica_cargador': kit.aplica_cargador,
                            'compra_completa': kit.compra_completa,
                            'nota': kit.nota or '',
                        }
        # Imagen del producto: la del color seleccionado, almacenada en Odoo.
        image_url = None
        if color_id:
            color = request.env['safra.fabric.color'].sudo().browse(int(color_id))
            if color.exists() and color.image:
                image_url = '/web/image/safra.fabric.color/%d/image' % color.id
        return {
            'base': base,
            'discount_pct': discount_pct,
            'price': price,
            'image_url': image_url,
            'mechanism': mechanism,
            'limits': limits,
            'kit': kit_data,
            'tubo': tubo_data,
        }

    def _parse_lines(self, post):
        """Construye los valores de cada línea de forma dirigida por metadatos.

        Para cada campo configurado (safra.field): si su código coincide con una
        columna de safra.quote.line se asigna ahí; de lo contrario se guarda en
        el JSON 'attribute_values'.
        """
        Line = request.env['safra.quote.line']
        line_columns = set(Line._fields.keys())
        # Catálogo de campos: code -> field_type
        all_fields = request.env['safra.field'].sudo().search([])
        field_types = {f.code: f.field_type for f in all_fields}

        def convert(ftype, raw):
            if ftype in ('integer', 'fabric', 'color'):
                try:
                    return int(raw)
                except (TypeError, ValueError):
                    return False
            if ftype == 'float':
                try:
                    return float(str(raw).replace(',', '.'))
                except (TypeError, ValueError):
                    return 0.0
            if ftype == 'boolean':
                return bool(raw)
            return raw or False

        lines = []
        # 28-sep: borrar una línea deja huecos en los índices (0, 2, 3…) y
        # el recorrido secuencial se detenía en el primero — las líneas
        # posteriores al hueco no llegaban al servidor. Se recorren los
        # índices que realmente existan en el formulario.
        idxs = sorted({int(m.group(1)) for k in post
                       for m in [re.match(r'^fabric_id_(\d+)$', str(k))] if m})
        for idx in idxs:
            system_raw = post.get('system_id_%d' % idx)
            try:
                fabric_id = int(post.get('fabric_id_%d' % idx, 0))
            except (TypeError, ValueError):
                fabric_id = 0
            if not fabric_id:
                continue

            vals = {'sequence': (idx + 1) * 10}
            try:
                vals['system_id'] = int(system_raw) if system_raw else False
            except (TypeError, ValueError):
                vals['system_id'] = False

            extra = {}
            for code, ftype in field_types.items():
                key = '%s_%d' % (code, idx)
                is_bool = ftype == 'boolean'
                if key not in post and not is_bool:
                    continue
                value = convert(ftype, post.get(key))
                if code in line_columns:
                    vals[code] = value
                else:
                    # Solo guardamos atributos con valor real
                    if value not in (False, '', 0, 0.0):
                        extra[code] = value
            if extra:
                vals['attribute_values'] = extra

            # 'description' no está en el catálogo pero existe como columna fija
            if ('description_%d' % idx) in post:
                vals['description'] = post.get('description_%d' % idx)
            # Comentario del diseño personalizado (puntos 10-11): campo
            # propio del bloque de subida, no es un safra.field.
            comment = post.get('design_comment_%d' % idx)
            if isinstance(comment, str) and comment.strip():
                vals['design_comment'] = comment.strip()
            # Fase 5.4c: piezas asignadas en el configurador de secuencia.
            for sop in ('soporte_izq', 'soporte_der'):
                value = post.get('%s_%d' % (sop, idx))
                if value in ('MANDO', 'MOTOR', 'DEP', 'INDEP', 'TERMINAL'):
                    vals[sop] = value

            # Reunión 09-oct (fila 13): con Mismo cabezal la persiana va
            # alineada aunque el formulario llegue sin la marca.
            if vals.get('same_header') and vals.get('system_id'):
                system = request.env['safra.system'].sudo().browse(vals['system_id'])
                if 'aligned' in system.mapping_ids.mapped('field_id.code'):
                    vals['aligned'] = True

            lines.append(vals)
        return lines
