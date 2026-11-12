# -*- coding: utf-8 -*-
import base64
import json
import re
from markupsafe import Markup
from odoo import fields, http, models
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal

from .cargue import SafraCargueMixin


class SafraPortalController(CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'safra_quote_count' in counters:
            partner = request.env.user.partner_id
            values['safra_quote_count'] = request.env['safra.quote'].sudo().search_count([
                ('partner_id', '=', partner.id),
            ])
        return values


class SafraQuoterController(SafraCargueMixin, http.Controller):

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
        # Ajustes Sprint 1.6 (26-oct, fila 125): el desplegable Referencia
        # solo trae telas; una referencia de otra categoría (controles,
        # cenefas…) con sistemas asociados no aparece como tela.
        telas = Fabric._dominio_telas()
        fabrics = Fabric.search(telas + [('active', '=', True), ('system_ids', 'in', system.id)],
                                order='name') if system else Fabric.browse()
        if system and not fabrics:
            fabrics = Fabric.search(telas + [('active', '=', True)], order='name')
        # Punto 3 (OBS REU TELAS): con cantidad mínima de stock configurada
        # en la referencia, la tela solo se ofrece si el stock disponible de
        # sus artículos la supera.
        # Sprint1-rev (17-sep): las telas sin stock ya no se ocultan — viajan
        # marcadas y el portal las muestra en gris (no seleccionables).
        return [dict(f._banderas_portal(), **{
            'id': f.id, 'name': f.name, 'code': f.code,
            'available': f._is_available_for_portal(),
            'pierceable_type': f.pierceable_type,
            'anadido': f.is_anadido,
            # Reunión 09-oct (fila 20): familias para filtrar las
            # referencias del Sheer 2 en 1.
            'blackout': f.is_blackout,
            'sheer': f.is_sheer,
            # Fase 5.1: densidad de la tela (hoja DENSIDAD, g/m²) para
            # filtrar insumos con densidad máxima (Sheer Deluxe).
            'densidad': f.peso_gm2 or 0,
        }) for f in fabrics]

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
        # Sprint 1.6 (fila 123): editar una cotización que no ha iniciado
        # el flujo; el formulario se llena con sus persianas.
        editar = None
        if kwargs.get('editar'):
            editar = self._cotizacion_editable(kwargs['editar'])
            if not editar:
                return request.redirect('/mis-cotizaciones')
            # Filas 123-124: «Editar» de una persiana abre el formulario en
            # ella; «Duplicar» la agrega como copia, abierta para ajustarla.
            editar = editar.with_context(safra_linea=kwargs.get('linea'),
                                         safra_duplicar=kwargs.get('duplicar'))
        user = request.env.user
        # Sin sistema preseleccionado (F3 de la matriz): el formulario se
        # pinta cuando el cliente elige el sistema.
        return request.render('website_quotes_safra.portal_quoter_form', {
            'systems_json': self._json_for_script(systems_data),
            'default_config_json': self._json_for_script({}),
            'default_system_id': 0,
            'editar': editar,
            'editar_json': self._json_for_script(self._datos_edicion(editar) if editar else {}),
            'puede_exportar': user.has_group('website_quotes_safra.group_safra_exportacion'),
            'puede_verificar': user.has_group('website_quotes_safra.group_safra_verificacion'),
            'puede_proyectos': user.has_group('website_quotes_safra.group_safra_proyectos_especiales'),
            'embalajes': self._opciones_embalaje(),
            **self._contexto_despacho(),
            'express_pct': request.env['safra.quote.line'].sudo()._parametro('safra.express_pct', 15),
        })

    def _datos_edicion(self, quote):
        """Valores de cada persiana con los nombres del formulario."""
        lineas = []
        for line in quote.line_ids.sorted('sequence'):
            attrs = line.attribute_values or {}
            values = {'system_id': line.system_id.id}
            for code in line.system_id.mapping_ids.mapped('field_id.code'):
                if code in line._fields:
                    value = line[code]
                    if isinstance(value, models.BaseModel):
                        value = value.id
                else:
                    value = attrs.get(code)
                if value not in (None, False, ''):
                    values[code] = value
            if line.description:
                values['description'] = line.description
            # Revisión cálculo de tubo (27-oct, error 4): los soportes del
            # configurador de secuencia no son campos del catálogo; sin
            # ellos la secuencia se perdía al editar.
            for sop in ('soporte_izq', 'soporte_der'):
                if line[sop]:
                    values[sop] = line[sop]
            lineas.append(values)
        linea = str(quote.env.context.get('safra_linea') or '')
        duplicar = str(quote.env.context.get('safra_duplicar') or '')
        # Reunión 09-nov (fila 2): lo elegido que ya no está disponible se
        # avisa en cada persiana (el portal no lo cambia por su cuenta).
        user = quote.user_id or request.env.user
        no_disponibles = [[{'code': d['code'], 'motivo': d['motivo'], 'valor': d['valor'],
                            'nombre': d['nombre']} for d in line._items_no_disponibles(user)]
                          for line in quote.line_ids.sorted('sequence')]
        return {'id': quote.id, 'name': quote.name, 'lineas': lineas,
                'no_disponibles': no_disponibles,
                'safra_express': quote.safra_express, 'es_exportacion': quote.es_exportacion,
                'es_proyecto_especial': quote.es_proyecto_especial,
                'requiere_verificacion': quote.requiere_verificacion,
                'verificacion_observaciones': quote.verificacion_observaciones or '',
                'embalaje_ids': quote.embalaje_ids.ids, 'orden_compra': quote.orden_compra or '',
                'despacho': {
                    'recoge_fabrica': quote.recoge_fabrica,
                    'country_id': quote.despacho_country_id.id or 0,
                    'city_id': quote.despacho_city_id.id or 0,
                    'direccion': quote.despacho_direccion or '',
                    'destinatario': quote.despacho_destinatario or '',
                    'fecha': fields.Date.to_string(quote.despacho_fecha) if quote.despacho_fecha else '',
                } if quote.despacho_registrado else {},
                'linea': int(linea) if linea.isdigit() else 0,
                'duplicar': int(duplicar) if duplicar.isdigit() else 0}

    def _json_for_script(self, data):
        # Markup evita que QWeb escape las comillas del JSON; escapamos '<'
        # para impedir que un '</script>' rompa el bloque embebido.
        return Markup(json.dumps(data).replace('<', '\\u003c'))

    def _ref_category_options(self, category, system=None):
        """Punto 16 (OBS REU TELAS): opciones de un campo «Referencia
        (categoría)» — la tabla de productos relacionados en las
        referencias de esa categoría (ej: Sesgo). Acta del 30-oct (Tubo,
        punto 8): las líneas sin stock suficiente también vienen, con
        «available» en 0, y el portal las muestra en gris «(sin stock)».

        Misma lógica del P1 en las telas: una referencia con sistemas
        asociados solo se ofrece en esos sistemas; sin sistemas asociados
        aplica para todos."""
        # None = categoría sin referencias (el campo cae al respaldo de sus
        # opciones de catálogo); lista vacía = hay referencias pero ninguna
        # aplica al sistema y el campo queda sin opciones.
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
                    lambda c: c.active
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
                    # Acta del 30-oct (Tubo, punto 8): sin existencias la
                    # opción se ve en gris con «(sin stock)», como las telas
                    # (antes no se ofrecía). La opción «Sin …» siempre sirve.
                    'available': 1 if (not product or color._is_available_for_portal()) else 0,
                    # Sprint 1.4 (fila 83): los campos pueden depender de la
                    # referencia elegida (valor «ref:CÓDIGO» en la dependencia).
                    'ref': fabric.code or '',
                    'value': color.code or str(color.id),
                    # Ajustes 20-oct (fila 94): etiqueta de la línea para las
                    # dependencias «eti:» (atributos que comparten producto).
                    'eti': name,
                    '_id': color.id,
                    # La opción «Sin …» (línea sin producto) se lee sola.
                    'label': ('%s %s' % (fabric.name, name)) if multi and product else name,
                    'img': img,
                    # Fase 5.1 (obs perfiles): densidad máxima de tela que
                    # soporta el insumo (U_Densidad del producto); el portal
                    # oculta la opción si la tela elegida la supera.
                    'dmax': product.safra_u_densidad or 0,
                    # Fase 5.4a: parametrización del producto que gobierna
                    # campos dependientes (¿Cabezal Forrado?, ¿Requiere
                    # Cargador?).
                    'forrado': 1 if product.safra_u_forrado else 0,
                    # Pendientes 24-sep (14.1): el módulo RF solo aparece
                    # para los motores que lo requieren. Sprint 1.2
                    # (comentario del 15-oct): en las referencias de motores
                    # lo dice la línea, no el maestro.
                    'cargador': 1 if (color.requiere_cargador if category.es_motor
                                      else product.safra_u_requiere_cargador) else 0,
                    'interruptor': 1 if (color.requiere_rf if category.es_motor
                                         else product.safra_u_requiere_interruptor_rf) else 0,
                    # Reunión 15-oct: telas con las que sirve la referencia
                    # (fila 50, perfiles) y tubos con los que se fabrica el
                    # insumo (fila 68, p. ej. cabezal cuadrado R8 y R16).
                    # Vacío: sin restricción. Reunión 28-oct: telas no
                    # compatibles con la línea (p. ej. un perfil redondo).
                    'telas': color.fabric_id.tela_ids.ids,
                    'sin_telas': color._telas_excluidas().ids,
                    'tubos': [t.name for t in product.safra_tubo_ids],
                })
                if category.es_riel:
                    # Sprint 1.5 (fila 99): vías del riel y Riel Velcrado,
                    # para cruzarlo con la combinación de telos. Como en los
                    # controles, el valor es la línea (ref-<id>): el Riel
                    # Velcrado puede ser el mismo producto del riel de 6.
                    options[-1].update(canales=color.canales or 0,
                                       velcrado=1 if color.velcrado else 0)
                    if product:
                        options[-1]['value'] = color._valor_control()
        # Ajustes 20-oct (fila 94): varias líneas con el mismo producto (p. ej.
        # Cover Light de 1, 2 o 3 laterales) tendrían el mismo valor; cada
        # una se guarda por su línea para saber cuál eligió el cliente.
        repetidos = {}
        for o in options:
            repetidos[o['value']] = repetidos.get(o['value'], 0) + 1
        for o in options:
            linea = o.pop('_id')
            if repetidos[o['value']] > 1 and not o['value'].startswith('ref-'):
                o['value'] = 'ref-%d' % linea
        options.sort(key=lambda o: o['label'])
        # Revisión 17-sep (cruce perfil x coordinado, min 00:10 de la
        # sesión): los insumos que existen en el maestro uno por color (ej.
        # perfil cuadrado blanco/ivory/...) comparten etiqueta — en el
        # portal la etiqueta repetida se muestra UNA sola vez; el artículo
        # exacto se resuelve después con el coordinado elegido (U_color).
        seen, dedup = {}, []
        for o in options:
            key = o['label'].strip().lower()
            if key in seen:
                # La etiqueta agrupa varias líneas: la restricción de telas
                # y tubos es la suma de las de todas (si una no restringe,
                # ninguna).
                first = seen[key]
                for k in ('telas', 'tubos'):
                    first[k] = sorted(set(first[k]) | set(o[k])) if first[k] and o[k] else []
                # Reunión 28-oct (fila 50): basta que una de sus líneas no
                # sirva con la tela.
                first['sin_telas'] = sorted(set(first['sin_telas']) | set(o['sin_telas']))
                # Hay existencias si alguna de sus líneas las tiene.
                first['available'] = 1 if (first['available'] or o['available']) else 0
                continue
            seen[key] = o
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
        # Sprint 1.5: dependencia por opción (dep = código del campo, depv
        # = valores que la habilitan); el portal la oculta si no aplica.
        return [{'value': o.value, 'label': o.name, 'eti': o.name, 'img': _img(o),
                 'seg': getattr(o, 'segmentos', 0) or 0,
                 'dep': o.depends_field_id.code or '',
                 'depv': o.depends_value or '',
                 # Fila 118: la opción tiene fórmula; el portal pregunta si
                 # aplica (/cotizador/ajax/opciones_formula). Ajustes 20 y
                 # 22-oct: también si se elige sola. Las de «Solo aviso» no
                 # se ofrecen: el portal solo muestra su aviso.
                 'fml': 1 if (o.formula or o.auto_formula) else 0,
                 # Revisión 30-oct: dobladillo con consumo (lista con alto máximo).
                 'cons': 1 if o.consumo_dobladillo > 0 else 0}
                for o in opt_recs if not o.solo_aviso]

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
        """Aperturas de Panel Track que se ofrecen en la regla de
        combinaciones del sistema (revisión 10-nov)."""
        regla = request.env['safra.panel.combo.rule'].sudo()._regla(system)
        return regla._aperturas() if regla else []

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
                # Reunión 28-oct (fila 89): lista con las telas elegidas.
                'telas_elegidas': (field.opciones_telas or '') if field.field_type == 'char' else '',
                # Barrido de la matriz (fila 124): orden en el resumen del pedido.
                'resumen': field.resumen_sequence or 0,
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
                # Ajustes 20 y 22-oct: el campo tiene opciones con fórmula,
                # que se elige sola o «Solo aviso» (el portal consulta).
                'fml': any(o.formula or o.auto_formula or o.solo_aviso for o in opt_recs),
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
            # Ajustes 22-oct (fila 121): el cuadro de Comentarios de respaldo
            # solo va en sistemas que no tienen el campo del catálogo.
            'comentarios_libres': 'description' not in maps.mapped('field_id.code'),
            # Ajustes 20-oct (fila 79): criterios de aceptación de la imagen
            # del sistema, para el análisis del diseño propio en el portal.
            'diseno': dict(zip(('dpi_min', 'dpi_opt', 'proporcion'),
                               request.env['safra.quote.line'].sudo().new(
                                   {'system_id': system.id})._criterios_diseno())),
            'max_lamas': max_lamas,
            # Mejoras Sprint 1.1 (21-oct, fila 18): texto junto al máximo.
            'max_lamas_texto': request.env['ir.config_parameter'].sudo().get_param(
                'safra.max_lamas_texto', request.env['res.config.settings'].MAX_LAMAS_TEXTO),
            # Sprint 1.7: campos con reglas «Al digitar un campo» en este
            # sistema; al cambiarlos el portal pide la revisión.
            'reglas_campo': request.env['safra.validation.rule'].sudo()._campos_disparo(system),
            # Reunión 24-sep: el filtro de combinación referencia+color
            # repetida obedece a la regla V_TELAS_REPETIDAS (inactiva, el
            # cliente repite tela y color; activa desde el 27-oct porque el
            # archivo de Safra la marca «Mantener»).
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

    def _validate_lines(self, lines_vals, cross=True, pedido=None, campo=None):
        """Motor de validaciones sobre las líneas del formulario; la lógica
        vive en safra.quote.line._validate_order (la misma que revalida una
        cotización guardada al confirmarla)."""
        return request.env['safra.quote.line'].sudo()._validate_order(
            lines_vals, cross=cross, pedido=pedido, campo=campo)

    def _parse_pedido(self, post, quote=None):
        """Sprint 1.6 (filas 126-128): lo que se marca para todo el pedido.
        Exportación y verificación solo las marcan sus grupos; al editar, lo
        que el usuario no puede marcar conserva el valor de la cotización."""
        user = request.env.user
        pedido = {
            'safra_express': bool(post.get('safra_express')),
            'es_exportacion': bool(post.get('es_exportacion')) and user.has_group(
                'website_quotes_safra.group_safra_exportacion'),
            'requiere_verificacion': bool(post.get('requiere_verificacion')) and user.has_group(
                'website_quotes_safra.group_safra_verificacion'),
        }
        obs = post.get('verificacion_observaciones')
        pedido['verificacion_observaciones'] = (
            obs.strip() if pedido['requiere_verificacion'] and isinstance(obs, str) else False)
        # Reunión 09-nov (fila 74): al cerrar la cotización con verificación
        # el cliente acepta que el pedido se evalúa sin garantía.
        pedido['acepta_sin_garantia'] = pedido['requiere_verificacion'] and bool(
            post.get('acepta_sin_garantia'))
        # Ajustes Sprint 1.6 (26-oct): proyectos especiales (fila 128, su
        # grupo), embalaje (fila 127) y orden de compra del cliente (fila 182).
        pedido['es_proyecto_especial'] = bool(post.get('es_proyecto_especial')) and user.has_group(
            'website_quotes_safra.group_safra_proyectos_especiales')
        opciones = {o['id'] for o in self._opciones_embalaje()}
        elegidos = request.httprequest.form.getlist('embalaje') if request.httprequest.form else []
        pedido['embalaje_ids'] = sorted({int(v) for v in elegidos if str(v).isdigit()} & opciones)
        orden = post.get('orden_compra')
        pedido['orden_compra'] = orden.strip()[:60] if isinstance(orden, str) and orden.strip() else False
        pedido.update(self._parse_despacho(post))
        if quote:
            for campo, grupo in (('es_exportacion', 'group_safra_exportacion'),
                                 ('es_proyecto_especial', 'group_safra_proyectos_especiales'),
                                 ('requiere_verificacion', 'group_safra_verificacion')):
                if not user.has_group('website_quotes_safra.%s' % grupo):
                    pedido[campo] = quote[campo]
            if not user.has_group('website_quotes_safra.group_safra_verificacion'):
                pedido['verificacion_observaciones'] = quote.verificacion_observaciones or False
                pedido['acepta_sin_garantia'] = quote.verificacion_acepta_sin_garantia
        return pedido

    def _parse_despacho(self, post):
        """Matriz, Datos de despacho (filas 184-188). Si recoge en fábrica
        solo queda la fecha; la ciudad debe ser del país elegido. Sin el
        bloque en el formulario (pide_despacho) no se revisa nada."""
        def _texto(clave, largo):
            valor = post.get(clave)
            return valor.strip()[:largo] if isinstance(valor, str) and valor.strip() else ''

        def _id(clave):
            try:
                return int(post.get(clave) or 0)
            except (TypeError, ValueError):
                return 0

        datos = {'pide_despacho': bool(post.get('despacho_bloque')),
                 'recoge_fabrica': bool(post.get('recoge_fabrica')),
                 'despacho_country_id': False, 'despacho_city_id': False,
                 'despacho_direccion': '', 'despacho_destinatario': '', 'despacho_fecha': False}
        try:
            datos['despacho_fecha'] = fields.Date.to_date(_texto('despacho_fecha', 10) or False) or False
        except ValueError:
            datos['despacho_fecha'] = False
        if datos['recoge_fabrica']:
            return datos
        pais = request.env['res.country'].sudo().browse(_id('despacho_country_id')).exists()
        ciudad = request.env['res.city'].sudo().browse(_id('despacho_city_id')).exists()
        datos.update({
            'despacho_country_id': pais.id or False,
            'despacho_city_id': ciudad.id if ciudad and ciudad.country_id == pais else False,
            'despacho_direccion': _texto('despacho_direccion', 200),
            'despacho_destinatario': _texto('despacho_destinatario', 120),
        })
        return datos

    def _contexto_despacho(self):
        """Países del bloque de despacho; por defecto, el de la empresa."""
        return {'paises': request.env['res.country'].sudo().search([]),
                'pais_defecto': request.env.company.country_id,
                # Revisión 05-nov: el calendario no deja elegir días pasados
                # (hoy en Colombia; el aviso es el del navegador).
                'hoy_despacho': fields.Date.to_string(request.env['safra.quote']._hoy_colombia())}

    @http.route('/cotizador/ajax/ciudades', type='jsonrpc', auth='user')
    def ajax_ciudades(self, country_id=None):
        """Fila 186: ciudades del país elegido, para la dirección de despacho."""
        try:
            country_id = int(country_id or 0)
        except (TypeError, ValueError):
            return []
        ciudades = request.env['res.city'].sudo().search([('country_id', '=', country_id)], order='name')
        return [{'id': c.id, 'name': c.name + (' (%s)' % c.state_id.name if c.state_id else '')}
                for c in ciudades]

    def _opciones_embalaje(self):
        """Fila 127: líneas activas (con producto) de las referencias de la
        categoría Embalaje."""
        cat = request.env['safra.product.option'].sudo()._categoria_embalaje()
        if not cat:
            return []
        lineas = request.env['safra.fabric.color'].sudo().search([
            ('fabric_id.category_id', '=', cat.id), ('fabric_id.active', '=', True),
            ('active', '=', True), ('product_tmpl_id', '!=', False)])
        return sorted(({'id': l.id, 'label': l._portal_label()} for l in lineas),
                      key=lambda o: o['label'])

    def _error_sin_garantia(self):
        return {'line': 0, 'code': 'V_SIN_GARANTIA', 'severity': 'error',
                'message': 'Requiere verificación de fabricación: acepte que el pedido se evalúa '
                           'sin garantía (planta le indicará al aprobarlo si va con garantía).'}

    def _errores_pedido(self, pedido):
        errores = []
        if pedido.get('requiere_verificacion') and not pedido.get('verificacion_observaciones'):
            errores.append({
                'line': 0, 'code': 'V_VERIFICACION_OBS', 'severity': 'error',
                'message': 'Verificación de fabricación: escriba los cambios '
                           'requeridos para planta.',
            })
        return errores

    @http.route('/cotizador/ajax/validar', type='jsonrpc', auth='user')
    def ajax_validar(self, single=None, **params):
        """Prevalidación del formulario antes del submit (mismos names del form).

        Con `single` (validación de UNA línea desde «Guardar línea») se
        omiten las reglas cruzadas del pedido (alineado, secuencias, canal
        compartido): con una sola línea siempre fallarían — p. ej. E20010
        exige la pareja, que sí existe en el pedido completo."""
        pedido = self._parse_pedido(params, self._cotizacion_editable(params.get('quote_id'))
                                    if params.get('quote_id') else None)
        issues = self._validate_lines(self._parse_lines(params),
                                      cross=not single, pedido=pedido)
        return issues if single else issues + self._errores_pedido(pedido)

    @http.route('/cotizador/ajax/validar_campo', type='jsonrpc', auth='user')
    def ajax_validar_campo(self, campo=None, **params):
        """Sprint 1.7: reglas «Al digitar un campo» del campo que cambió, sobre
        la persiana que se está editando (mismos names que «Guardar línea»)."""
        if not campo:
            return []
        return self._validate_lines(self._parse_lines(params, sin_tela=True), cross=False,
                                    pedido=self._parse_pedido(params), campo=campo)

    @http.route('/cotizador/ajax/corte_tela', type='jsonrpc', auth='user')
    def ajax_corte_tela(self, **params):
        """Revisión 30-oct: tipo de corte de la tela de la persiana que se está
        editando y los mensajes de sus reglas de Validaciones, para mostrarlos
        junto a la tela mientras se digita."""
        lines = self._parse_lines(params)
        if not lines:
            return {'tipo': '', 'avisos': [], 'avisos_ficha': [], 'bloquea': False}
        return request.env['safra.quote.line'].sudo()._avisos_corte(
            lines[0], pedido=self._parse_pedido(params))

    @http.route('/cotizador/ajax/validar_secuencia', type='jsonrpc', auth='user')
    def ajax_validar_secuencia(self, secuencia_nombre=None, **params):
        """Revisión 28-oct: reglas «Al aplicar la secuencia» de Validaciones,
        con los soportes que se acaban de armar en el configurador (el
        formulario completo, con los soportes propuestos). Devuelve solo los
        mensajes de las persianas de esa secuencia, con su índice («idx») en
        el formulario."""
        lines = self._parse_lines(params, sin_tela=True)
        issues = request.env['safra.quote.line'].sudo()._validate_order(
            lines, cross=True, pedido=self._parse_pedido(params), momento='secuencia')
        nombre = (secuencia_nombre or '').strip().lower()
        propias = {n: vals for n, vals in enumerate(lines, start=1)
                   if vals.get('same_header') and (vals.get('sequence_name') or '').strip().lower() == nombre}
        salida = []
        for issue in issues:
            vals = propias.get(issue.get('line'))
            if vals or (not issue.get('line') and propias):
                salida.append(dict(issue, idx=(vals['sequence'] // 10 - 1) if vals else None))
        return salida

    @http.route('/cotizador/submit', type='http', auth='user', website=True, methods=['POST'], csrf=True)
    def quoter_submit(self, **post):
        # Sprint 1.6 (fila 123): editar una cotización guardada.
        quote = None
        if post.get('quote_id'):
            quote = self._cotizacion_editable(post.get('quote_id'))
            if not quote:
                return request.not_found()
        lines = self._parse_lines(post)
        pedido = self._parse_pedido(post, quote)
        # Respaldo servidor del motor de validaciones: los errores bloquean
        # el pedido aunque el JS no haya corrido la prevalidación.
        issues = self._validate_lines(lines, pedido=pedido) + self._errores_pedido(pedido)
        errors = [i for i in issues if i['severity'] == 'error']
        # Reunión 15-oct (fila 74): las persianas sin restricciones exigen
        # aceptar que no tienen garantía.
        if any(v.get('sin_restricciones') for v in lines) and not post.get('acepta_sin_garantia'):
            errors.append({
                'line': next(n for n, v in enumerate(lines, start=1) if v.get('sin_restricciones')),
                'code': 'V_SIN_GARANTIA', 'severity': 'error',
                'message': 'Pedido sin restricciones: acepte que las persianas '
                           'marcadas no tienen garantía.',
            })
        # Reunión 09-nov (fila 74): la verificación de fabricación (que
        # reemplaza a «Pedido sin restricciones») exige la misma aceptación.
        if pedido.get('requiere_verificacion') and not pedido.get('acepta_sin_garantia'):
            errors.append(self._error_sin_garantia())
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
        # Revisión 27-oct (pruebas de Safra): «Guardar borrador» guarda aunque
        # haya errores; el pedido no se finaliza hasta corregirlos.
        if post.get('guardar_borrador'):
            completas = [v for v in lines if v.get('system_id') and v.get('color_id')]
            for n, v in enumerate(lines, start=1):
                if v not in completas:
                    errors.append({'line': n, 'code': 'V_BORRADOR_INCOMPLETA', 'severity': 'error',
                                   'message': 'Sin referencia y color: no se guardó en el borrador.'})
            if not completas:
                return request.render('website_quotes_safra.portal_quoter_errors', {
                    'errors': [{'line': False, 'message': 'Para guardar el borrador elija al menos '
                                'sistema, referencia y color en una persiana.'}],
                })
            quote = self._guardar_cotizacion(completas, issues, pedido, files=files, quote=quote,
                                             borrador_errores=errors)
            return request.redirect('/mis-cotizaciones/%d' % quote.id)
        if errors:
            return request.render('website_quotes_safra.portal_quoter_errors', {
                'errors': errors,
            })
        quote = self._guardar_cotizacion(lines, issues, pedido, files=files, quote=quote)
        return request.redirect('/mis-cotizaciones/%d' % quote.id)

    def _guardar_cotizacion(self, lines, issues, pedido, files=None, quote=None,
                            borrador_errores=None):
        """Crea la cotización (o reemplaza las persianas de la que se edita)
        y arranca sus flujos: diseño, producción, verificación y
        exportación. También la usa el cargue masivo. Con
        `borrador_errores` (lista, puede ir vacía) queda como borrador sin
        finalizar: se guardan los errores y no arranca ningún flujo."""
        files = files or {}
        borrador = borrador_errores is not None
        errores_txt = '\n'.join(
            ('Persiana %s: %s' % (e['line'], e['message'])) if e.get('line') else e['message']
            for e in borrador_errores or [])
        vals = {
            # Revisión sprint 1: Safra Express es a nivel de pedido.
            'safra_express': pedido.get('safra_express', False),
            'es_exportacion': pedido.get('es_exportacion', False),
            'requiere_verificacion': pedido.get('requiere_verificacion', False),
            'verificacion_observaciones': pedido.get('verificacion_observaciones') or False,
            'verificacion_acepta_sin_garantia': bool(
                pedido.get('requiere_verificacion') and pedido.get('acepta_sin_garantia')),
            'es_proyecto_especial': pedido.get('es_proyecto_especial', False),
            'embalaje_ids': [(6, 0, pedido.get('embalaje_ids') or [])],
            'orden_compra': pedido.get('orden_compra') or False,
            # Datos de despacho (filas 184-188).
            'recoge_fabrica': pedido.get('recoge_fabrica', False),
            'despacho_country_id': pedido.get('despacho_country_id') or False,
            'despacho_city_id': pedido.get('despacho_city_id') or False,
            'despacho_direccion': pedido.get('despacho_direccion') or False,
            'despacho_destinatario': pedido.get('despacho_destinatario') or False,
            'despacho_fecha': pedido.get('despacho_fecha') or False,
            'despacho_registrado': bool(pedido.get('pide_despacho')),
            'verificacion_detalle': '\n'.join(
                i['message'] for i in issues if i.get('line') and i.get('saltada')
                and i['message'].startswith('Verificación')) or False,
            'borrador_portal': borrador,
            'borrador_errores': errores_txt or False,
        }
        nueva = not quote
        # Revisión 27-oct: al finalizar un borrador arranca todo como si fuera nueva.
        era_borrador = bool(quote and quote.borrador_portal)
        if quote:
            bloqueada = quote.state == 'blocked'
            quote.line_ids.unlink()
            # Fila 130: corregida tras el rechazo, la verificación empieza de
            # nuevo con un ticket nuevo.
            if quote.verificacion_rechazada:
                vals.update({'verificacion_rechazada': False, 'verificacion_rechazo_motivo': False,
                             'verificacion_aprobada': False, 'verificacion_garantia': False,
                             'verificacion_garantia_motivo': False})
            quote.write(vals)
            quote.message_post(body='Cotización editada por el cliente desde el portal.')
        else:
            quote = request.env['safra.quote'].sudo().create(dict(vals, **{
                'partner_id': request.env.user.partner_id.id,
                'user_id': request.env.user.id,
            }))
        for n, line_vals in enumerate(lines, start=1):
            line_vals['quote_id'] = quote.id
            if line_vals.get('sin_restricciones'):
                line_vals['sin_restricciones_detalle'] = '\n'.join(
                    i['message'] for i in issues if i.get('line') == n and i.get('saltada'))
            line = request.env['safra.quote.line'].sudo().create(line_vals)
            # Sprint 1.5 (fila 99): con Tipo de Riel «Auto» queda guardado
            # el riel de la combinación.
            line._guardar_riel_auto()
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
                if not borrador:
                    line._create_design_ticket()

        if borrador:
            if quote.state == 'blocked':
                quote.write({'state': 'draft', 'bloqueo_motivos': False})
            quote.message_post(body=Markup(
                '<p>Guardada como borrador desde el portal, sin finalizar.</p>%s') % (
                Markup('<ul>%s</ul>') % Markup('').join(
                    Markup('<li>%s</li>') % e for e in errores_txt.split('\n'))
                if errores_txt else ''))
            return quote

        # Mejoras Sprint 1.1 (21-oct, fila 2): la bloqueada que el cliente
        # corrige vuelve a Borrador (o sigue bloqueada con el motivo nuevo).
        if not nueva and bloqueada:
            quote._desbloquear()
        # Pendiente 12.3: rollo (lote) sugerido para la tela de cada persiana.
        quote._sugerir_rollos()
        # Reunión 15-oct (fila 74): ticket para que producción apruebe las
        # persianas sin restricciones.
        quote._create_production_ticket()
        # Sprint 1.6 (fila 128): ticket de verificación de fabricación.
        quote._create_verification_ticket()
        # Fase 5.3: con diseños personalizados el pedido queda pendiente de
        # la aprobación del área de diseño (y antes, de producción).
        quote._update_design_state()
        if nueva or era_borrador:
            # Sprint 1.6 (fila 126): aviso al área de exportaciones.
            quote._avisar_exportacion()
        return quote

    def _dominio_mis_cotizaciones(self):
        """Ajustes Sprint 1.6 (26-oct, fila 124): el administrador de
        pedidos ve los de todos los usuarios de su empresa; los demás, los
        suyos."""
        user = request.env.user
        if user.has_group('website_quotes_safra.group_safra_portal_admin'):
            return [('partner_id', 'child_of', user.commercial_partner_id.id)]
        return [('partner_id', '=', user.partner_id.id)]

    def _cotizacion_visible(self, quote_id):
        try:
            quote_id = int(quote_id)
        except (TypeError, ValueError):
            return None
        return request.env['safra.quote'].sudo().search(
            self._dominio_mis_cotizaciones() + [('id', '=', quote_id)], limit=1) or None

    def _cotizacion_consulta(self, quote_id):
        """Matriz, fila 191 (reunión 28-oct): un usuario interno de la mesa de
        ayuda ve la cotización de un ticket que puede leer, sin editarla
        (las rutas de editar, duplicar, eliminar y confirmar siguen usando
        _cotizacion_visible)."""
        user = request.env.user
        if user.share or not user.has_group('helpdesk.group_helpdesk_user'):
            return None
        try:
            quote_id = int(quote_id)
        except (TypeError, ValueError):
            return None
        tickets = request.env['helpdesk.ticket'].search([('safra_quote_id', '=', quote_id)], limit=1)
        return tickets.sudo().safra_quote_id or None

    def _cotizacion_editable(self, quote_id):
        quote = self._cotizacion_visible(quote_id)
        if not quote or not quote.editable_portal:
            return None
        return quote

    # Sprint 1.6 (fila 125): cargue masivo por Excel (lógica en cargue.py).
    @http.route('/cotizador/cargue', type='http', auth='user', website=True, methods=['GET'])
    def cargue_form(self, **kwargs):
        return self._render_cargue()

    @http.route('/cotizador/cargue/plantilla', type='http', auth='user', website=True)
    def cargue_plantilla(self, system_id=None, **kwargs):
        return self._plantilla_cargue(system_id)

    @http.route('/cotizador/cargue', type='http', auth='user', website=True,
                methods=['POST'], csrf=True)
    def cargue_subir(self, **post):
        return self._subir_cargue(post)

    @http.route('/mis-cotizaciones', type='http', auth='user', website=True)
    def my_quotes(self, **kwargs):
        quotes = request.env['safra.quote'].sudo().search(
            self._dominio_mis_cotizaciones(), order='date desc, id desc')
        return request.render('website_quotes_safra.portal_my_quotes', {
            'quotes': quotes,
            'es_admin': request.env.user.has_group('website_quotes_safra.group_safra_portal_admin'),
            'aviso': request.session.pop('safra_aviso', None),
        })

    @http.route('/mis-cotizaciones/<int:quote_id>', type='http', auth='user', website=True)
    def quote_detail(self, quote_id, **kwargs):
        quote = self._cotizacion_visible(quote_id)
        solo_lectura = False
        if not quote:
            quote = self._cotizacion_consulta(quote_id)
            solo_lectura = bool(quote)
        if not quote:
            return request.not_found()
        return request.render('website_quotes_safra.portal_quote_detail', {
            'quote': quote,
            # Fila 191: desde la mesa de ayuda solo se consulta.
            'solo_lectura': solo_lectura,
            'confirmacion': request.session.pop('safra_confirmacion', None),
            'aviso': request.session.pop('safra_aviso', None),
            'confirmables': self.PORTAL_CONFIRMABLES,
            # Fila 124: el resumen del pedido con todo lo elegido por persiana,
            # como el portal actual de Safra (barrido de la matriz).
            'resumenes': {line.id: line._resumen_portal() for line in quote.line_ids},
        })

    # Ajustes Sprint 1.6 (26-oct, filas 123 y 124): duplicar o eliminar el
    # pedido completo y duplicar o eliminar persianas desde su resumen.
    @http.route('/mis-cotizaciones/<int:quote_id>/duplicar', type='http', auth='user',
                website=True, methods=['POST'])
    def quote_duplicate(self, quote_id, **kwargs):
        quote = self._cotizacion_visible(quote_id)
        if not quote:
            return request.not_found()
        nueva = quote._duplicar_portal(request.env.user)
        request.session['safra_aviso'] = {
            'ok': nueva.state != 'blocked',
            'mensaje': 'Se creó la cotización %s, copia de %s.' % (nueva.name, quote.name)}
        return request.redirect('/mis-cotizaciones/%d' % nueva.id)

    @http.route('/mis-cotizaciones/<int:quote_id>/eliminar', type='http', auth='user',
                website=True, methods=['POST'])
    def quote_delete(self, quote_id, **kwargs):
        quote = self._cotizacion_editable(quote_id)
        if not quote:
            return request.not_found()
        nombre = quote.name
        quote.unlink()
        request.session['safra_aviso'] = {'ok': True, 'mensaje': 'Se eliminó la cotización %s.' % nombre}
        return request.redirect('/mis-cotizaciones')

    @http.route('/mis-cotizaciones/<int:quote_id>/linea/<int:line_id>/eliminar',
                type='http', auth='user', website=True, methods=['POST'])
    def quote_line_delete(self, quote_id, line_id, **kwargs):
        quote = self._cotizacion_editable(quote_id)
        line = quote and quote.line_ids.filtered(lambda l: l.id == line_id)
        if not line:
            return request.not_found()
        errores = quote._eliminar_linea_portal(line)
        request.session['safra_aviso'] = {
            'ok': not errores,
            'mensaje': 'Persiana eliminada.' if not errores else 'No se pudo eliminar la persiana:',
            'errores': [('Persiana %s: %s' % (e['line'], e['message'])) if e.get('line') else e['message']
                        for e in errores],
        }
        return request.redirect('/mis-cotizaciones/%d' % quote.id)

    @http.route('/mis-cotizaciones/<int:quote_id>/diseno/<int:line_id>/<string:cual>',
                type='http', auth='user', website=True)
    def quote_design_file(self, quote_id, line_id, cual, **kwargs):
        """Ajustes 20-oct (fila 79): el archivo del diseño (el del cliente o el
        aprobado por el diseñador) para verlo desde el portal."""
        line = request.env['safra.quote.line'].sudo().browse(line_id)
        if not line.exists() or line.quote_id.id != quote_id \
                or line.quote_id.partner_id != request.env.user.partner_id:
            return request.not_found()
        final = cual == 'final' and line.design_approved
        data = line.design_final_file if final else line.design_image
        nombre = (line.design_final_filename if final else line.design_filename) or 'diseno'
        if not data:
            return request.not_found()
        tipo = 'application/pdf' if nombre.lower().endswith('.pdf') else 'application/octet-stream'
        return request.make_response(base64.b64decode(data), headers=[
            ('Content-Type', tipo),
            ('Content-Disposition', 'inline; filename="%s"' % nombre.replace('"', '')),
        ])

    # Reunión 09-oct (fila 2): el distribuidor confirma SUS cotizaciones
    # desde el portal. Mientras el área de diseño no apruebe, la cotización
    # con diseño personalizado espera (no se ofrece el botón).
    PORTAL_CONFIRMABLES = ('draft', 'design_approved', 'production_approved')

    @http.route('/mis-cotizaciones/<int:quote_id>/confirmar', type='http', auth='user',
                website=True, methods=['POST'])
    def quote_confirm(self, quote_id, **kwargs):
        """Misma lógica que la confirmación del backoffice: se revalida la
        cotización y, si ya no cumple, se ANULA con el motivo en su
        historial; si cumple, queda confirmada."""
        quote = self._cotizacion_visible(quote_id)
        if not quote:
            return request.not_found()
        # Sprint 1.6 (fila 126): la exportación la confirma el área de
        # exportaciones en el backoffice. Fila 130: sin la verificación
        # aprobada (p. ej. rechazada) no se confirma.
        sin_verificar = quote.requiere_verificacion and not quote.verificacion_aprobada
        # Revisión 27-oct: el borrador sin finalizar no se confirma.
        if quote.state in self.PORTAL_CONFIRMABLES and not quote.borrador_portal \
                and not quote.es_exportacion and not sin_verificar:
            # Mejoras Sprint 1.1 (21-oct, fila 2): si ya no cumple queda
            # Bloqueada con el motivo y se puede editar.
            bloqueadas = quote._bloquear_si_invalida()
            if bloqueadas:
                request.session['safra_confirmacion'] = {
                    'ok': False,
                    'errores': [{'line': e['line'], 'message': e['message']}
                                for e in bloqueadas.get(quote, [])],
                }
            else:
                quote.write({'state': 'confirmed', 'bloqueo_motivos': False})
                quote.message_post(body='Cotización confirmada por el cliente desde el portal.')
                quote._generar_pedido_venta()
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
        # Ajustes Sprint 1.6 (26-oct, fila 160): U_Observación del producto
        # del color, que el portal muestra junto al corte atravesable.
        result = [{'id': c.id, 'name': c._portal_label(), 'code': c.code,
                   'available': c._is_available_for_portal(),
                   'obs': (c.product_tmpl_id.safra_u_observacion or '').strip()} for c in colors]
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
        # Sprint 1.2 (comentario del 15-oct): las asociaciones van en
        # Referencias. Los controles salen de la referencia de controles
        # (columna Motores de cada línea); ya no del «U_Controles
        # compatibles» del maestro. Sin referencia de controles el control
        # queda con sus opciones y las del kit motorizado.
        lineas = Color._lineas_control(product, system)
        controls = [{
            'value': l._valor_control(),
            'label': l._portal_label(),
            'canales': l._canales_portal(),
            # Acta del 30-oct (Tubo, punto 8): en gris si no hay existencias.
            'available': 1 if (not l.product_tmpl_id or l._is_available_for_portal()) else 0,
        } for l in lineas] if lineas is not None else []
        de_linea = color.fabric_id.es_motor
        return {
            'interruptor': bool(color.requiere_rf if de_linea else product.safra_u_requiere_interruptor_rf),
            'cargador': bool(color.requiere_cargador if de_linea else product.safra_u_requiere_cargador),
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

    @http.route('/cotizador/ajax/opciones_formula', type='jsonrpc', auth='user')
    def ajax_opciones_formula(self, system_id=None, campos=None):
        """Sprint 1.5 (fila 118): opciones que se ofrecen según su fórmula
        (p. ej. los dobladillos que caben en el rollo), con los valores que
        lleva la persiana en el formulario."""
        campos = dict(campos or {})

        def _num(raw):
            try:
                return float(str(raw or 0).replace(',', '.'))
            except (TypeError, ValueError):
                return 0.0

        def _id(raw):
            try:
                return int(raw or 0) or False
            except (TypeError, ValueError):
                return False
        try:
            system = int(system_id or 0)
        except (TypeError, ValueError):
            system = 0
        if not system:
            return {'opciones': {}, 'auto': {}, 'avisos': {}, 'maximos': {}}
        line = request.env['safra.quote.line'].sudo().new({
            'system_id': system, 'width': _num(campos.get('width')),
            'height': _num(campos.get('height')), 'quantity': _num(campos.get('quantity')) or 1,
            'fabric_id': _id(campos.get('fabric_id')), 'color_id': _id(campos.get('color_id')),
            'attribute_values': campos,
        })
        return line._formulas_opciones()

    @http.route('/cotizador/ajax/unificar', type='jsonrpc', auth='user')
    def ajax_unificar(self, lineas=None):
        """Revisión cálculo de tubo (27-oct, errores 2, 3 y 6): Unificación
        Mando de las persianas con Mismo cabezal, calculada como al guardar
        (tubo mayor de la secuencia, tramos con soportes dependientes como
        una sola persiana, tubo motorizado si hay motor). `lineas` =
        [{idx, system_id, campos, unificacion}]; devuelve {idx: {tubo, motor}}
        (motor = la mueve el motor de su tramo: tabla motorizada)."""
        def _num(raw):
            try:
                return float(str(raw or 0).replace(',', '.'))
            except (TypeError, ValueError):
                return 0.0

        def _id(raw):
            try:
                return int(raw or 0) or False
            except (TypeError, ValueError):
                return False

        soportes = ('MANDO', 'MOTOR', 'DEP', 'INDEP', 'TERMINAL')
        vals_list, idxs = [], []
        for item in lineas or []:
            campos = dict(item.get('campos') or {})
            vals_list.append({
                'system_id': _id(item.get('system_id')),
                'width': _num(campos.get('width')), 'height': _num(campos.get('height')),
                'quantity': 1, 'fabric_id': _id(campos.get('fabric_id')),
                'color_id': _id(campos.get('color_id')),
                'has_motor': str(campos.get('has_motor') or '') in ('1', 'True', 'true'),
                'motor': campos.get('motor') or False,
                'same_header': True, 'sequence_name': campos.get('sequence_name') or '',
                'soporte_izq': campos.get('soporte_izq') if campos.get('soporte_izq') in soportes else False,
                'soporte_der': campos.get('soporte_der') if campos.get('soporte_der') in soportes else False,
                'attribute_values': dict(campos, unificacion_mando=item.get('unificacion') or ''),
            })
            idxs.append(str(item.get('idx')))
        request.env['safra.quote.line'].sudo()._unificar_secuencias(vals_list)
        return {idx: {'tubo': vals['attribute_values'].get('unificacion_mando') or '',
                      'motor': bool(vals['attribute_values'].get('unificacion_motor'))}
                for idx, vals in zip(idxs, vals_list)}

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
                    motor=None, unificacion=None, motor_secuencia=False, **kwargs):
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
        cuadro = []
        if system_id:
            system = request.env['safra.system'].sudo().browse(int(system_id))
            system = system if system.exists() else None
            cab = (cabezal or '').lower()
            cab_type = 'redondo' if 'redondo' in cab else ('cuadrado' if 'cuadrado' in cab else None)
            Rule = request.env['safra.structure.rule'].sudo()
            # Sprint 1.3 (fila 73): con Unificación Mando la estructura y los
            # límites salen del tubo unificado (mayor al calculado).
            # Revisión cálculo de tubo (27-oct, error 6): si el alto no
            # alcanza, el tubo pasa solo al siguiente; «base» es el tubo que
            # la persiana necesita (por ancho y alto), sin unificar.
            Line = request.env['safra.quote.line'].sudo()
            fabric = request.env['safra.fabric'].sudo().browse(int(fabric_id)) if fabric_id else None
            fabric = fabric if fabric and fabric.exists() else None
            params = Line._params_estructura_de(system, fabric, perfil, motor if has_motor else '')
            # Revisión 27-oct (error 2): la persiana manual que mueve el motor
            # de su tramo (soportes dependientes) usa la tabla motorizada.
            tabla_motor = bool(has_motor or motor_secuencia)
            necesaria = Rule.elegir(system, w, h, motorized=tabla_motor, cabezal=cab_type,
                                    **params) if system else {'regla': Rule.browse()}
            elegida = Rule.elegir(system, w, h, motorized=tabla_motor, cabezal=cab_type,
                                  unificacion=unificacion or None, **params) if system else necesaria
            base_rule, rule = necesaria['regla'], elegida['regla']
            # Reunión 09-nov (fila 68, punto 3): si manual no se puede (ancho,
            # alto o peso), ¿con motor sí? Se le pide al cliente marcarlo.
            alternativa = None
            lim_elegida = elegida.get('limites') or {}
            if system and w and not tabla_motor and (
                    not rule or lim_elegida.get('alto_ok') is False or lim_elegida.get('peso_ok') is False):
                alternativa = Rule.alternativa_motor(
                    system, w, h, cabezal=cab_type, unificacion=unificacion or None,
                    motores=Line._motores_sistema(system), **params)
            if alternativa and not rule:
                limits = {'requiere_motor': True, 'tubo_motor': Rule.nombre_tubo(alternativa['tubo'])}
            if base_rule:
                tubos = Rule.tubos_ordenados(system, motorized=tabla_motor)
                pos = tubos.index(base_rule.tubo) if base_rule.tubo in tubos else len(tubos)
                # Reunión 15-oct (fila 68): los tubos sin insumos no se
                # ofrecen en la Unificación Mando y se avisan en la ficha.
                bloqueados = Rule.tubos_bloqueados(tubos)
                tubo_data = {
                    'base': base_rule.tubo,
                    'efectivo': rule.tubo,
                    'subio_de': necesaria.get('subio_de'),
                    'mayores': [t for t in tubos[pos + 1:] if t not in bloqueados],
                    'orden': tubos,
                    'bloqueados': bloqueados,
                    # Revisión 27-oct (error 2): orden de la secuencia
                    # (manual y motor) y los tubos de la tabla motorizada.
                    'secuencia': Rule.tubos_secuencia(system),
                    'motor': Rule.tubos_ordenados(system, motorized=True),
                    'con_motor': bool(has_motor),
                }
                # Cuadro de altos y pesos máximos de cada tubo (el «?»).
                cuadro = Rule.opciones(system, w, h, cabezal=cab_type, **params)
            if rule:
                mechanism = rule._mechanism_line(cabezal=cabezal or None)
                limits = elegida['limites']
                if alternativa:
                    limits['requiere_motor'] = True
                    limits['tubo_motor'] = Rule.nombre_tubo(alternativa['tubo'])
                # Con motor elegido, la carga es la de su maestro (fila 68).
                limits['motor_elegido'] = bool(params.get('motor_elegido'))
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
            'cuadro': cuadro,
            'kit': kit_data,
            'tubo': tubo_data,
        }

    def _puede_comentar(self):
        campo = request.env['safra.field'].sudo().search([('code', '=', 'description')], limit=1)
        return not campo.group_id or campo.group_id in request.env.user.all_group_ids

    def _parse_lines(self, post, sin_tela=False):
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
        # Ajustes 22-oct (fila 121): un campo con grupo solo lo guarda quien
        # pertenece a él (p. ej. Comentarios).
        user_groups = request.env.user.all_group_ids
        restringidos = {f.code for f in all_fields if f.group_id and f.group_id not in user_groups}

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
            # Sprint 1.7: las reglas «Al digitar un campo» se revisan aunque
            # todavía no se haya elegido la tela.
            if not fabric_id and not sin_tela:
                continue

            vals = {'sequence': (idx + 1) * 10}
            try:
                vals['system_id'] = int(system_raw) if system_raw else False
            except (TypeError, ValueError):
                vals['system_id'] = False

            extra = {}
            for code, ftype in field_types.items():
                if code in restringidos:
                    continue
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
            # Ajustes 22-oct (fila 121): con grupo en el campo Comentarios, solo
            # ese grupo lo diligencia.
            if ('description_%d' % idx) in post and self._puede_comentar():
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

            # Sprint 1.5 (fila 104): con motor no hay cadena ni cordón extra.
            motor = vals.get('motor')
            if 'extra_chain' in vals and (vals.get('has_motor') or (motor and motor not in ('0', 'sin'))):
                vals['extra_chain'] = 0.0

            # Reunión 09-oct (fila 13): con Mismo cabezal la persiana va
            # alineada aunque el formulario llegue sin la marca.
            if vals.get('same_header') and vals.get('system_id'):
                system = request.env['safra.system'].sudo().browse(vals['system_id'])
                if 'aligned' in system.mapping_ids.mapped('field_id.code'):
                    vals['aligned'] = True

            # Reunión 15-oct (fila 74): solo el grupo autorizado puede pedir
            # una persiana sin restricciones.
            if vals.get('sin_restricciones') and not request.env.user.has_group(
                    'website_quotes_safra.group_safra_sin_restricciones'):
                vals['sin_restricciones'] = False
            lines.append(vals)
        return lines
