# -*- coding: utf-8 -*-
"""Revisión 27-oct (video con la consultora): para que Safra escriba sus
validaciones sin saber el lenguaje de las condiciones, Odoo arma la
instrucción (prompt) que el funcional copia en la IA que use, y luego lee
la respuesta que pega. Odoo no llama a ninguna IA: solo junta lo que hay
en la base (variables con valores de una persiana real, campos de los
sistemas con sus valores, ejemplos que ya funcionan)."""
import re
import textwrap

from markupsafe import Markup, escape

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

from .fields_vacio import vacio_en

# Opciones por campo que se listan; el resto se resume («… y N más»).
MAX_OPCIONES = 30

# Variables propias del motor (safra.quote.line._contexto_reglas) que se
# explican en la instrucción, en este orden. Las telas, el pedido y el
# hallazgo van en su propia sección.
VARIABLES = [
    ('ancho', 'ancho digitado (m)'),
    ('alto', 'alto digitado (m)'),
    ('cantidad', 'unidades de la persiana'),
    ('sistema', 'CÓDIGO del sistema (no el nombre)'),
    ('sistema_nombre', 'nombre del sistema'),
    ('limites', "mínimos y máximos de la ficha (m): limites['wmin'], limites['wmax'], "
                "limites['hmin'], limites['hmax'] (vacío si no se digitaron ni en el producto "
                "terminado ni en el sistema)"),
    ('localizacion', 'localización digitada (texto)'),
    ('alineado', 'casilla Alineado'),
    ('exhibicion', 'casilla Exhibición'),
    ('con_motor', 'True si la persiana es motorizada (casilla o motor elegido)'),
    ('motor_ref', 'motor elegido (línea de Referencias; vacío si no hay motor o no viene de Referencias)'),
    ('kit', 'kit motorizado del motor y el tubo: kit.motor_name, kit.control_values (vacío si no hay)'),
    ('motor_kits', 'todos los kits del motor elegido (vacío si no tiene)'),
    ('motor_ancho_min', 'ancho mínimo del motor elegido: su U_AnchoMin (m); vacío si el motor no lo '
                        'tiene digitado, 0 si se digitó 0 (pon el valor por defecto en la condición: '
                        '0.70 if vacio(motor_ancho_min) else motor_ancho_min)'),
    ('ancho_rollo', 'ancho del rollo del color elegido (m; vacío si el color no tiene U_Ancho digitado; 0 si se digitó 0; vacio(ancho_rollo) dice si no se digitó)'),
    ('ancho_max_impresion', 'ancho máximo que permite la impresora para estampar (m)'),
    ('total_lamas', 'cantidad de lamas o telos (entero)'),
    ('suma_lamas', 'suma de las lamas por tela'),
    ('maximo_lamas', 'máximo de lamas/telos calculado (None si el sistema no lo calcula)'),
    ('traslape', 'paneles: tamaño del traslape (m)'),
    ('ancho_telo', 'paneles: ancho de cada telo (m)'),
    ('tipo_corte', "corte de la tela: 'normal', 'atravesado', 'anadido', 'anadido_excede', "
                   "'bajo_falso', 'panos', 'no_fabricable', 'sin_ancho_rollo' (el color no tiene U_Ancho) "
                   "o '' si el sistema no aplica"),
    ('motivo_corte', "por qué no se puede fabricar (texto), cuando tipo_corte es 'no_fabricable', "
                     "'anadido_excede' o 'sin_ancho_rollo'; '' en los demás"),
    ('anadidos', 'persianas: añadidos que necesita el alto'),
    ('constante_tubo', 'persianas: constante del tubo que se suma al alto para atravesar (m)'),
    ('maximo_anadidos', 'persianas: máximo de añadidos de la tela'),
    ('panos', 'cortinas: paños del corte por paños'),
    ('tipo_corte_cenefa', "cenefa en tela: 'entera' (cabe en el rollo), 'atravesada' (lo supera y la "
                          "tela es atravesable), 'anadida' (lo supera y la tela no es atravesable) "
                          "o '' si no es cenefa en tela"),
    ('ancho_cenefa', 'cenefa en tela: ancho de la cenefa con sus laterales (m)'),
    ('cenefa_en_tela', 'True si el Tipo de Cenefa es una cenefa en tela'),
    ('ancho_tela', 'cortinas: ancho de tela (ancho × factor de confección)'),
    ('estructura', "tabla de estructura: estructura['tubo'], ['mecanismo'], ['cabezal'] "
                   "(texto), ['alto_maximo'], ['aumento_tela'] (m), ['peso'], ['carga'] (g; la "
                   "carga vacía si no está digitada: vacio(estructura['carga'])), ['motor_elegido'] "
                   "(True si la carga es la del motor elegido), ['carga_detalle'] (texto: de dónde "
                   "sale la carga y cómo está cada dato), ['tubo_motor'] (tubo con el que sí se "
                   "fabrica motorizada cuando manual no se puede; '' si no aplica), ['tabla'] (True "
                   "si el sistema tiene Estructura por Ancho) y ['encontrada'] (True si hay fila "
                   "para este ancho); ['alto_maximo'] vacío si no se puede calcular "
                   "(vacio(estructura['alto_maximo']))"),
    ('datos_sin_digitar', "datos del maestro vacíos (sin digitar) que usan las fórmulas o las "
                          "validaciones de la persiana: lista de {'dato': qué falta y dónde, "
                          "'usos': qué validaciones o fórmulas lo usan}"),
    ('insumos_sin_stock', "insumos de estructura del tubo (estructura['tubo']) sin existencias: los "
                          "productos del maestro con ese tubo en «Tubos», separados por coma; '' si "
                          "no falta ninguno"),
    ('numero', 'número de la persiana en el pedido'),
    ('linea', "la persiana como se guarda: linea.acepta_atravesado (True si aceptó el corte "
              "atravesado o, en cortinas, por paños), linea.soporte_izq y linea.soporte_der "
              "('MANDO', 'MOTOR', 'DEP', 'INDEP', 'TERMINAL' o False), linea.has_motor, "
              "linea.same_header"),
    ('tramo', "solo «Al finalizar el pedido»: si la persiana está unida a otras por soportes "
              "dependientes, el tramo calculado como una sola persiana: tramo['ancho'] y "
              "tramo['alto'] (m), tramo['persianas'] (texto, p. ej. 'persiana 1, persiana 2'), "
              "tramo['numeros'], tramo['tubo'] ('' si ningún tubo lo soporta), "
              "tramo['alto_maximo'], tramo['alto_ok'], tramo['peso'] y tramo['carga'] (g), "
              "tramo['peso_ok']; vacío {} si no está en un tramo"),
]

DATOS_TELA = ('name', 'code', 'is_blackout', 'is_sheer', 'is_printable', 'has_franjas',
              'is_texturable', 'permite_cenefa_entera', 'pierceable_type', 'peso_gm2',
              'grosor_mm')

MOMENTO_TEXTO = {
    'campo': ('Se revisa apenas el cliente cambia el campo «%s»; también al guardar la '
              'persiana y al finalizar el pedido. En ese momento solo se conoce esta '
              'persiana.'),
    'linea': ('Se revisa al guardar la persiana y otra vez al finalizar el pedido. Para '
              'comparar persianas entre sí (lineas, otras_lineas, pedido) el momento debe '
              'ser «Al finalizar el pedido».'),
    'secuencia': ('Se revisa al pulsar «Aplicar» en el configurador de secuencia, con los '
                  'soportes que se acaban de armar, y otra vez al finalizar el pedido. Usa '
                  'secuencia_lineas (las persianas de la misma secuencia, en orden) y los '
                  'soportes: linea.soporte_izq, linea.soporte_der.'),
    'pedido': ('Se revisa al enviar el pedido: se pueden comparar las persianas entre sí '
               'con lineas, otras_lineas y pedido.'),
}

SEVERIDAD_TEXTO = {
    'error': 'Error (mensaje en rojo, no deja continuar)',
    'warning': 'Advertencia (mensaje en amarillo, deja continuar)',
    'info': 'Información (mensaje en azul, solo informa)',
}

EJEMPLO_BLOQUE = (
    'Área grande sin motor (bloque de varias líneas)',
    'area = ancho * alto\nresult = area > 12 and not con_motor',
    'El área ({area:.2f} m²) es grande para manual; considere motorizarla.',
)

# Encabezados de la respuesta de la IA («**CONDICIÓN:**», «Mensaje sugerido:»…).
_ENCABEZADO = re.compile(
    r'^[\s#>*_`]*(CONDICI[OÓ]N|MENSAJE(?: SUGERIDO)?|PRUEBAS|AVISOS?)[\s*_`]*:[\s*_`]*(.*)$',
    re.IGNORECASE)


class SafraValidationRulePrompt(models.TransientModel):
    _name = 'safra.validation.rule.prompt'
    _description = 'Instrucción para IA de una validación del cotizador'

    rule_id = fields.Many2one('safra.validation.rule', string='Validación', required=True,
                              ondelete='cascade')
    system_ids = fields.Many2many(
        'safra.system', 'safra_validation_prompt_system_rel', 'wizard_id', 'system_id',
        string='Sistemas',
        help='Sistemas en los que se revisa la validación. Sus campos y valores van en la '
             'instrucción. Al pasar la respuesta, la validación queda con estos sistemas.')
    solicitud = fields.Text(
        string='¿Qué quiere validar?',
        help='En palabras, como se lo explicaría a una persona: cuándo debe salir el '
             'mensaje y qué debe decir.')
    prompt = fields.Text(string='Instrucción para la IA', compute='_compute_prompt')
    # Revisión 28-oct: para escribir «¿Qué quiere validar?» con los valores
    # exactos (p. ej. «Tubo 40mm (Motorizado)», no «tubo de 40»).
    valores_html = fields.Html(string='Valores que puede usar', compute='_compute_valores',
                               sanitize=False)
    respuesta = fields.Text(
        string='Respuesta de la IA',
        help='Pegue aquí la respuesta completa; Odoo toma la CONDICIÓN y el MENSAJE.')

    @api.depends('rule_id', 'system_ids', 'solicitud')
    def _compute_prompt(self):
        for wiz in self:
            wiz.prompt = wiz._armar_prompt() if wiz.rule_id else ''

    # ------------------------------------------------------------------
    # Instrucción
    # ------------------------------------------------------------------

    def _armar_prompt(self):
        self.ensure_one()
        systems = self.system_ids.sorted('code')
        ctx, linea = self._contexto_muestra(systems)
        campos = self._campos_prompt(systems)
        partes = [
            'Eres un asistente que escribe condiciones para el motor de validaciones de un '
            'cotizador de persianas hecho en Odoo. Escribe la condición que se pide al final '
            'siguiendo TODAS las reglas. Si algo de lo pedido no se puede hacer con las '
            'variables y campos de abajo, dilo en AVISOS; no inventes nombres.',
            self._seccion('QUÉ ES UNA CONDICIÓN', [
                '- Se evalúa una vez por cada persiana del pedido.',
                '- Debe dar True cuando la regla SE INCUMPLE (cuando debe salir el mensaje). '
                'Si da False, no pasa nada.',
            ]),
            self._seccion_validacion(systems),
            self._seccion('REGLAS DEL CÓDIGO', [
                '- Python restringido: sin import, sin def, sin clases, sin archivos ni '
                'internet. Permitido: and, or, not, comparaciones, in, listas, len(), sum(), '
                'min(), max(), round(), abs(), any(), all(), int(), float(), str() y '
                'comprensiones de listas.',
                '- Forma 1: UNA expresión.   Ejemplo: ancho > 3',
                '- Forma 2: un bloque de varias líneas que termina en  result = <True/False>. '
                'Las variables del bloque se pueden usar en el mensaje como {variable}.',
                '- Usa SOLO las variables y los campos listados abajo.',
            ]),
            self._seccion_errores(systems, campos),
            self._seccion_variables(ctx, linea),
            self._seccion_telas(ctx),
            self._seccion_pedido(systems),
            self._seccion_campos(systems, campos),
            self._seccion_estructura(systems),
            self._seccion_ejemplos(systems),
            self._seccion('FORMATO DE RESPUESTA (obligatorio, sin texto adicional)', [
                'CONDICIÓN:',
                '<solo el código, sin ``` ni comentarios>',
                '',
                'MENSAJE:',
                '<texto para el cliente; puede usar {variable}. Si te dan un código de '
                'Safra (p. ej. E13095), empieza el mensaje con él: «E13095: …»>',
                '',
                'PRUEBAS:',
                '- Debe salir con: <una persiana de ejemplo, en palabras>',
                '- No debe salir con: <otra persiana de ejemplo, en palabras>',
                '',
                'AVISOS:',
                '<solo si algo no se puede o hay que cambiar los sistemas o el momento de la '
                'validación; si no, escribe «Ninguno»>',
            ]),
            # Revisión 28-oct: el usuario puede escribir códigos de variables
            # (same_header) o nombres de pantalla; cómo interpretarlos.
            self._seccion('CÓMO LEER LO QUE PIDE EL USUARIO', [
                '- Si nombra un CÓDIGO de las listas (p. ej. same_header, apertura, '
                "estructura['tubo']), es esa variable, exactamente: úsala tal cual, sin comillas "
                'y sin cambiarle el nombre.',
                '- Si nombra un campo como se ve en pantalla (p. ej. «Mismo cabezal», «Tipo de '
                'Apertura»), busca su código en la lista CAMPOS y usa ese código.',
                "- Casilla (True/False): la variable sola o con not, sin comillas: same_header, "
                "not same_header. Nunca same_header == 'True' ni == 'Sí'.",
                "- Valor de una lista u opción: la variable sin comillas y el valor entre "
                "comillas, exacto: apertura == '4', estructura['tubo'] == 'Tubo 40mm (Motorizado)'.",
                '- Número: sin comillas y con punto decimal: ancho > 2.5.',
                '- Si escribe un valor entre comillas, se copia exactamente así; si no está en las '
                'listas, usa el de la lista que corresponde y dilo en AVISOS.',
                '- Si nombra algo que no está en las variables ni en los campos, no lo inventes: '
                'dilo en AVISOS.',
            ]),
            self._seccion('LO QUE QUIERO VALIDAR', [
                (self.solicitud or '').strip()
                or '(escriba aquí, en palabras, lo que quiere validar)',
            ]),
        ]
        return '\n\n'.join(p for p in partes if p)

    @staticmethod
    def _seccion(titulo, lineas):
        return '== %s ==\n%s' % (titulo, '\n'.join(lineas))

    def _seccion_validacion(self, systems):
        rule = self.rule_id
        if systems:
            sistemas = ', '.join("%s (código '%s')" % (s.name, s.code) for s in systems)
            lineas = ['- Sistemas: %s. La validación SOLO se revisa en ellos.' % sistemas]
        else:
            lineas = ['- Sistemas: todos.']
        momento = MOMENTO_TEXTO[rule.momento]
        if rule.momento == 'campo':
            campo = rule.trigger_field_id
            momento %= ('%s (código %s)' % (campo.name, campo.code)) if campo else '…'
        lineas += [
            '- Momento: %s. %s' % (dict(rule._fields['momento'].selection)[rule.momento], momento),
            '- Severidad: %s.' % SEVERIDAD_TEXTO[rule.severity],
        ]
        if (rule.condition_code or '').strip():
            lineas += [
                '- Ya tiene esta condición. Si lo pedido es un cambio, modifícala; si es una '
                'regla distinta, reemplázala:',
                textwrap.indent(rule.condition_code.strip(), '    '),
            ]
            if rule.message:
                lineas.append('- Mensaje actual: %s' % rule.message)
            if 'hallazgo' in rule.condition_code:
                lineas.append(
                    '- «hallazgo» es lo que encontró el cálculo interno del sistema para esta '
                    'regla (False si no encontró nada). La condición «hallazgo» sola deja la '
                    'regla como la calcula el sistema; se puede combinar, p. ej. '
                    '«hallazgo and not exhibicion», o reemplazar por una condición propia.')
        return self._seccion('DATOS DE ESTA VALIDACIÓN', lineas)

    def _seccion_errores(self, systems, campos):
        if systems:
            s = systems[0]
            lineas = [
                '1. NO filtres por sistema en el código: la validación ya se revisa solo en '
                'los sistemas de arriba.',
                "2. «sistema» es el CÓDIGO ('%s'), no el nombre. El nombre es "
                "«sistema_nombre» ('%s')." % (s.code, s.name),
            ]
        else:
            lineas = [
                '1. La validación aplica a todos los sistemas. Si lo pedido es solo para '
                'algunos, filtra con sistema in (...) usando los CÓDIGOS de la lista de '
                'sistemas, y dilo en AVISOS para que se marquen esos sistemas.',
                "2. «sistema» es el CÓDIGO (p. ej. '01'), no el nombre. El nombre es "
                "«sistema_nombre».",
            ]
        lista = next((c for c in campos if c['opciones']), None)
        if lista:
            valor, etiqueta = lista['opciones'][0]
            lineas.append(
                "3. Los valores de las listas son TEXTO entre comillas: %s == '%s' (nunca "
                "%s == %s sin comillas ni %s == '%s', que es la etiqueta)."
                % (lista['code'], valor, lista['code'], valor, lista['code'], etiqueta))
        else:
            lineas.append('3. Los valores de las listas son TEXTO entre comillas, con el '
                          'valor (no la etiqueta).')
        lineas += [
            '4. Los números se comparan sin comillas: ancho > 2.5.',
            '5. Las medidas están en METROS y con punto decimal: 95 cm se escribe 0.95.',
            '6. Las referencias 2 a 5 pueden estar vacías: pregunta  tela_2 and ...  antes de '
            'usar tela_2.algo.',
            "7. Un campo que el cliente no llenó vale 0 si es número, '' si es texto o lista "
            "y False si es casilla. Un dato numérico del maestro sin digitar (ancho_rollo, "
            "motor_ancho_min, limites[...], estructura['aumento_tela'], tela.peso_gm2 y los demás "
            "números de productos, referencias y sistemas) llega vacío y no es lo mismo que 0: usa "
            "vacio(dato) para distinguirlos (p. ej. vacio(tela.peso_gm2)).",
            # Revisión 28-oct: la IA cambió «Tubo 40mm (Motorizado)» por
            # 'tubo_40_mm_(Motorizado)' y la condición nunca disparó.
            "8. Los valores de texto (opciones de los campos, nombres de tubo y mecanismo de "
            "la estructura, códigos de sistema) se copian EXACTAMENTE como están en las listas "
            "de esta instrucción, carácter por carácter: no los pases a minúsculas, no "
            "cambies espacios por guiones bajos, no quites paréntesis ni tildes.",
            "9. Si lo que te piden no coincide exactamente con un valor de las listas (p. ej. "
            "«tubo de 40»), usa el valor de la lista que corresponde (p. ej. 'Tubo 40mm "
            "(Motorizado)') y dilo en AVISOS. Nunca inventes un valor que no esté en las listas.",
            "10. En otras_lineas y lineas, los campos de cada persiana se leen por su código "
            "en l['atributos'], p. ej. l['atributos'].get('same_header'); usa .get() porque un "
            "campo puede no estar.",
        ]
        return self._seccion('ERRORES QUE NO DEBES COMETER', lineas)

    def _contexto_muestra(self, systems):
        """Variables de la última persiana cotizada en los sistemas (o en
        cualquiera), para mostrar valores reales; sin cotizaciones, las de
        una persiana vacía."""
        Line = self.env['safra.quote.line'].sudo()
        dominio = [('system_id', 'in', systems.ids)] if systems else [('system_id', '!=', False)]
        linea = Line.search(dominio, order='id desc', limit=1)
        if not linea:
            ctx = Line._contexto_ejemplo()
            if systems:
                ctx.update(sistema=systems[0].code or '', sistema_nombre=systems[0].name or '')
            return ctx, linea
        resumen = [linea._resumen_regla(1)]
        pedido = linea.quote_id._datos_pedido() if linea.quote_id else {}
        return linea._contexto_reglas(1, resumen, pedido), linea

    @staticmethod
    def _texto_valor(valor):
        if isinstance(valor, float):
            return repr(round(valor, 4))
        if isinstance(valor, dict):
            return '{%s}' % ', '.join('%r: %s' % (k, SafraValidationRulePrompt._texto_valor(v))
                                      for k, v in valor.items())
        if isinstance(valor, models.BaseModel):
            if not valor:
                return 'vacío'
            # Varios registros (p. ej. motor_kits: un motor con un kit por
            # tubo): se listan todos, como lista.
            if len(valor) > 1:
                return repr(valor.mapped('display_name'))
            return repr(valor.display_name)
        return repr(valor)

    def _seccion_variables(self, ctx, linea):
        titulo = 'VARIABLES (con el valor de %s)' % (
            'la última persiana cotizada en estos sistemas' if linea
            else 'una persiana vacía')
        lineas = ['%s = %s    # %s' % (nombre, self._texto_valor(ctx.get(nombre)), texto)
                  for nombre, texto in VARIABLES if nombre in ctx]
        return self._seccion(titulo, lineas)

    def _seccion_telas(self, ctx):
        tela, color = ctx.get('tela'), ctx.get('color')
        lineas = ['tela, color: referencia y color 1 (vacíos si no se eligieron). Datos:']
        for dato in DATOS_TELA:
            valor = ''
            if tela:
                valor = '    # %s' % ('vacío (sin digitar)' if vacio_en(tela, dato)
                                     else self._texto_valor(tela[dato]))
            lineas.append('  tela.%s%s' % (dato, valor))
        lineas += [
            "  (tela.pierceable_type es 'no', 'si' o 'si_cliente'; peso_gm2 en g/m²; "
            "grosor_mm en mm)",
            '  color.name, color.code%s' % (
                '    # %r, %r' % (color.name, color.code) if color else ''),
            'tela_2 … tela_5, color_2 … color_5: referencias y colores 2 a 5, con los mismos '
            'datos (vacíos si no se eligieron).',
            'telas: lista de las parejas (referencia, color) elegidas; len(telas) dice cuántas.',
        ]
        return self._seccion('TELAS', lineas)

    def _seccion_pedido(self, systems):
        codigo = systems[:1].code or '01'
        return self._seccion('OTRAS PERSIANAS Y PEDIDO (sobre todo «Al finalizar el pedido»)', [
            'lineas: todas las persianas del pedido; otras_lineas: las demás. Cada una es un '
            'diccionario:',
            "  {'numero': 2, 'sistema': '%s', 'ancho': 1.8, 'alto': 2.0, 'cantidad': 1, "
            "'tela': <referencia>, 'color': <color>, 'localizacion': 'Sala', "
            "'alineado': False, 'secuencia': '', 'con_motor': False, "
            "'atributos': {código de cualquier campo: valor}}" % codigo,
            "  Ejemplo: len([l for l in otras_lineas if l['localizacion'] == localizacion])",
            # Revisión 28-oct: secuencia y soportes del configurador.
            "secuencia_lineas: las persianas de la misma secuencia (Mismo cabezal y mismo "
            "Nombre de secuencia), en orden, incluida esta; cada una como las de lineas. "
            "Vacía si la persiana no va en secuencia.",
            "Soportes del configurador de secuencia: de esta persiana linea.soporte_izq y "
            "linea.soporte_der; de las demás l['linea'].soporte_izq y l['linea'].soporte_der. "
            "Valores: 'MANDO', 'MOTOR', 'DEP' (soporte central dependiente), 'INDEP' "
            "(independiente), 'TERMINAL' (False si no tiene).",
            "pedido = {'express': False, 'exportacion': False, 'verificacion': False, "
            "'unidades': 3, 'lineas': 2}   # unidades = suma de cantidades",
            # Datos de despacho (filas 184-188).
            "Datos de despacho del pedido: pedido['pide_despacho'] (el formulario trae el bloque; "
            "False en cotizaciones guardadas antes), pedido['recoge_fabrica'] (True/False), "
            "pedido['pais'], pedido['ciudad'], pedido['direccion'] y pedido['destinatario'] "
            "(texto, '' si está vacío) y pedido['fecha_despacho'] (fecha o False).",
        ])

    # ------------------------------------------------------------------
    # Campos de los sistemas
    # ------------------------------------------------------------------

    def _campos_prompt(self, systems):
        """[{code, label, tipo, opciones: [(valor, etiqueta)], mas, sistemas}]
        de los campos que una condición puede usar por su código."""
        # Un campo con el código de una variable propia (p. ej. ancho_telo)
        # no llega a la condición: manda la variable.
        base = set(self.env['safra.quote.line'].sudo().new({})._contexto_reglas(
            1, [], {}, solo_propias=True))
        Mapping = self.env['safra.system.field'].sudo()
        if systems:
            mapeos = Mapping.search([('system_id', 'in', systems.ids), ('active', '=', True),
                                     ('field_id.active', '=', True)])
            pares = [(m.field_id, m) for m in mapeos.sorted(lambda m: (m.sequence, m.id))]
        else:
            pares = [(f, None) for f in self.env['safra.field'].sudo().search([], order='code')]
        campos, por_codigo = [], {}
        for field, mapeo in pares:
            code = field.code or ''
            if (not re.match(r'^[a-z_][a-z0-9_]*$', code) or code in base
                    or field.field_type in ('fabric', 'color')):
                continue
            opciones = self._opciones_campo(field, mapeo)
            if code in por_codigo:
                campo = por_codigo[code]
                vistos = {v for v, _e in campo['opciones']}
                campo['opciones'] += [o for o in opciones if o[0] not in vistos]
                campo['sistemas'] |= mapeo.system_id
                continue
            campo = {'code': code, 'label': (mapeo and mapeo.label_override) or field.name,
                     'tipo': ('telas_' + field.opciones_telas) if field.opciones_telas else field.field_type,
                     'opciones': opciones,
                     'sistemas': mapeo.system_id if mapeo else self.env['safra.system']}
            por_codigo[code] = campo
            campos.append(campo)
        return campos

    def _opciones_campo(self, field, mapeo):
        """(valor, etiqueta) de las opciones del campo en el sistema, con el
        valor que guarda el portal."""
        system = mapeo.system_id if mapeo else self.env['safra.system']
        if field.field_type == 'ref_categoria' and field.ref_category_id:
            opciones = self._opciones_referencia(field.ref_category_id, system)
            if opciones is not None:
                return opciones
        if field.field_type in ('selection', 'ref_categoria'):
            recs = (mapeo and mapeo.option_ids) or field.option_ids
            if recs and recs._name == 'safra.field.option' and system:
                recs = recs.filtered(lambda o: not o.system_ids or system in o.system_ids)
            return [(str(o.value), o.name) for o in recs]
        return []

    def _opciones_referencia(self, category, system):
        """Como el portal (_ref_category_options): las líneas activas de las
        referencias de la categoría que aplican al sistema; None si la
        categoría no tiene referencias."""
        fabrics = self.env['safra.fabric'].sudo().search([('category_id', '=', category.id)])
        if not fabrics:
            return None
        if system:
            fabrics = fabrics.filtered(lambda f: not f.system_ids or system in f.system_ids)
        varias = len(fabrics) > 1
        opciones = []
        for fabric in fabrics:
            for color in fabric.color_ids.filtered(
                    lambda c: c.active and (not c.system_ids or not system
                                            or system in c.system_ids)):
                product = color.product_tmpl_id
                valor = color.code or str(color.id)
                # Como los guarda el portal: los rieles por su línea y los
                # controles (salen del motor elegido) por su línea, con «0»
                # para «Sin control» (la línea sin producto).
                if (category.es_riel and product) or category.es_control:
                    valor = color._valor_control()
                etiqueta = color._portal_label()
                if varias and product:
                    etiqueta = '%s %s' % (fabric.name, etiqueta)
                opciones.append([valor, etiqueta, color.id])
        repetidos = {}
        for o in opciones:
            repetidos[o[0]] = repetidos.get(o[0], 0) + 1
        vistos, salida = set(), []
        for valor, etiqueta, linea in sorted(opciones, key=lambda o: o[1]):
            if repetidos[valor] > 1 and not valor.startswith('ref-'):
                valor = 'ref-%d' % linea
            if valor not in vistos:
                vistos.add(valor)
                salida.append((valor, etiqueta))
        return salida

    def _seccion_campos(self, systems, campos):
        tipos = {'integer': 'número', 'float': 'número', 'boolean': 'casilla (True/False)',
                 'char': 'texto libre', 'design': 'texto: código del diseño elegido',
                 # Reunión 28-oct (fila 89): listas con las telas elegidas.
                 'telas_color': 'texto: una de las telas elegidas en el pedido («Referencia Color»)',
                 'telas_referencia': 'texto: una de las telas elegidas en el pedido (solo la referencia)'}
        ejemplo = next((c['code'] for c in campos if c['opciones']), 'perfil')
        lineas = ['(código: nombre en pantalla — tipo — valores). Se usan por su código, '
                  'p. ej. %s.' % ejemplo]
        for c in campos:
            if c['opciones']:
                mostradas = c['opciones'][:MAX_OPCIONES]
                tipo = 'texto, uno de: ' + ', '.join("'%s' %s" % o for o in mostradas)
                if len(c['opciones']) > MAX_OPCIONES:
                    tipo += ' … y %d más' % (len(c['opciones']) - MAX_OPCIONES)
            elif c['tipo'] in ('selection', 'ref_categoria'):
                tipo = 'texto (hoy sin opciones fijas en este sistema)'
            else:
                tipo = tipos.get(c['tipo'], 'texto')
            solo = ''
            if len(systems) > 1 and c['sistemas'] and c['sistemas'] != systems:
                solo = ' (solo en %s)' % ', '.join(c['sistemas'].sorted('code').mapped('name'))
            lineas.append('%s: %s — %s%s' % (c['code'], c['label'], tipo, solo))
        if systems:
            titulo = 'CAMPOS DE %s' % ', '.join(systems.mapped('name'))
        else:
            titulo = 'CAMPOS DEL COTIZADOR'
            lineas += ['', 'Sistemas (código: nombre):'] + [
                "'%s': %s" % (s.code, s.name)
                for s in self.env['safra.system'].sudo().search([], order='code')]
        return self._seccion(titulo, lineas)

    def _estructura_valores(self, systems):
        """{'tubo': [...], 'mecanismo': [...]}: los nombres exactos de la
        Estructura por Ancho de los sistemas (o de todos), que son los que
        trae estructura['tubo'] y estructura['mecanismo']."""
        dominio = [('system_ids', 'in', systems.ids)] if systems else []
        reglas = self.env['safra.structure.rule'].sudo().search(dominio, order='width_from, id')
        valores = {'tubo': [], 'mecanismo': []}
        for regla in reglas:
            for clave in valores:
                nombre = (regla[clave] or '').strip()
                if nombre and nombre not in valores[clave]:
                    valores[clave].append(nombre)
        return valores

    def _seccion_estructura(self, systems):
        valores = self._estructura_valores(systems)
        if not any(valores.values()):
            return ''
        lineas = ['Son TEXTO y se comparan con el nombre exacto (mayúsculas, espacios y '
                  'paréntesis), entre comillas:']
        for clave, nombres in valores.items():
            if nombres:
                lineas.append("estructura['%s'] es uno de: %s" % (
                    clave, ', '.join("'%s'" % n for n in nombres)))
        lineas.append("Ejemplo: estructura['tubo'] == '%s'" % valores['tubo'][0]
                      if valores['tubo'] else '')
        return self._seccion('VALORES DE LA ESTRUCTURA POR ANCHO', [l for l in lineas if l])

    @api.depends('system_ids')
    def _compute_valores(self):
        for wiz in self:
            wiz.valores_html = wiz._armar_valores() if wiz.rule_id else False

    def _armar_valores(self):
        """Tablas de la pestaña «Valores que puede usar»: tubos y mecanismos
        de la estructura y, por campo, el valor exacto de cada opción."""
        systems = self.system_ids.sorted('code')
        # Revisión 28-oct: se puede nombrar la variable (código) o el valor; en
        # la condición la variable va sin comillas y el valor de texto entre
        # comillas.
        partes = [Markup(
            '<p class="text-muted mb-1">En «¿Qué quiere validar?» puede nombrar la '
            '<b>variable</b> (columna Código o Variable) y el <b>valor</b> exacto de esta lista. '
            'En la condición se escriben distinto:</p>'
            '<ul class="text-muted mb-2">'
            '<li><b>Variable:</b> sin comillas, tal cual: <code>apertura</code>, '
            '<code>same_header</code>, <code>estructura[\'tubo\']</code>.</li>'
            '<li><b>Valor de texto</b> (opciones, nombres de tubo): entre comillas y exacto: '
            '<code>apertura == \'4\'</code>, <code>estructura[\'tubo\'] == \'Tubo 40mm '
            '(Motorizado)\'</code>.</li>'
            '<li><b>Casilla:</b> la variable sola o con <code>not</code>, sin comillas: '
            '<code>same_header</code>, <code>not same_header</code>.</li>'
            '<li><b>Número:</b> sin comillas y con punto decimal: <code>ancho &gt; 2.5</code>.</li>'
            '</ul>')]
        estructura = self._estructura_valores(systems)
        if any(estructura.values()):
            filas = Markup('').join(
                Markup('<tr><td><code>estructura[%s]</code></td><td>%s</td></tr>') % (
                    "'%s'" % clave,
                    Markup(', ').join(Markup('<code>%s</code>') % n for n in nombres))
                for clave, nombres in estructura.items() if nombres)
            partes.append(Markup('<h5 class="mt-2">Estructura por Ancho</h5><table class="table '
                                 'table-sm"><thead><tr><th>Variable</th><th>Valores</th></tr>'
                                 '</thead><tbody>%s</tbody></table>') % filas)
        filas = []
        for c in self._campos_prompt(systems):
            if c['opciones']:
                valores = Markup('<br/>').join(
                    Markup('<code>%s</code> = %s') % (valor, etiqueta)
                    for valor, etiqueta in c['opciones'])
            elif c['tipo'] == 'boolean':
                valores = Markup('casilla: <code>True</code> / <code>False</code>')
            elif c['tipo'] in ('integer', 'float'):
                valores = Markup('número')
            else:
                valores = Markup('texto')
            filas.append(Markup('<tr><td><code>%s</code></td><td>%s</td><td>%s</td></tr>') % (
                c['code'], c['label'], valores))
        if filas:
            partes.append(Markup('<h5 class="mt-3">Campos%s</h5><table class="table table-sm">'
                                 '<thead><tr><th>Código (variable)</th><th>En pantalla</th><th>Valor = '
                                 'opción</th></tr></thead><tbody>%s</tbody></table>') % (
                ' de %s' % ', '.join(systems.mapped('name')) if systems else '',
                Markup('').join(filas)))
        return Markup('').join(partes)

    def _seccion_ejemplos(self, systems):
        """Hasta tres reglas activas de estos sistemas con condición corta,
        más un bloque de varias líneas."""
        Rule = self.env['safra.validation.rule'].sudo()
        reglas = Rule.search([('estado', '=', 'portal'), ('condition_code', '!=', False),
                              ('id', '!=', self.rule_id.id)])
        reglas = reglas.filtered(
            lambda r: len(r.condition_code.strip()) <= 220 and 'hallazgo' not in r.condition_code
            and (not systems or not r.system_ids or r.system_ids & systems))
        reglas = reglas.sorted(lambda r: (not (r.system_ids & systems), len(r.condition_code),
                                          r.code))[:3]
        ejemplos = [(r.name, r.condition_code.strip(), r.message or '') for r in reglas]
        ejemplos.append(EJEMPLO_BLOQUE)
        lineas = []
        for i, (nombre, condicion, mensaje) in enumerate(ejemplos, 1):
            lineas += ['%d) %s' % (i, nombre), textwrap.indent(condicion, '   ')]
            if mensaje:
                lineas.append('   Mensaje: %s' % mensaje)
        return self._seccion('EJEMPLOS QUE YA FUNCIONAN', lineas)

    # ------------------------------------------------------------------
    # Respuesta
    # ------------------------------------------------------------------

    @api.model
    def _leer_respuesta(self, texto):
        """{'condicion', 'mensaje'} de la respuesta pegada: toma lo que hay
        debajo de cada encabezado, sin bloques ``` ni comillas de adorno."""
        partes, actual = {}, None
        for linea in (texto or '').splitlines():
            m = _ENCABEZADO.match(linea)
            if m:
                actual = m.group(1).upper().replace('Ó', 'O').split()[0]
                partes[actual] = [m.group(2)] if m.group(2).strip() else []
            elif actual:
                partes[actual].append(linea)

        def limpio(clave):
            lineas = [l for l in partes.get(clave, []) if not l.strip().startswith('```')]
            return textwrap.dedent('\n'.join(lineas)).strip()

        condicion = limpio('CONDICION').strip('`').strip()
        mensaje = ' '.join(limpio('MENSAJE').split())
        if len(mensaje) > 1 and mensaje[0] + mensaje[-1] in ('«»', '""', "''", '“”'):
            mensaje = mensaje[1:-1].strip()
        return {'condicion': condicion, 'mensaje': mensaje}

    def _guardar_solicitud(self):
        """Revisión 28-oct: lo escrito en «¿Qué quiere validar?» queda en la
        validación para la próxima instrucción."""
        for wiz in self:
            if (wiz.solicitud or False) != (wiz.rule_id.solicitud_ia or False):
                wiz.rule_id.solicitud_ia = wiz.solicitud or False

    def action_cerrar(self):
        self._guardar_solicitud()
        return {'type': 'ir.actions.act_window_close'}

    def action_aplicar(self):
        """Pasa la condición, el mensaje y los sistemas a la validación."""
        self.ensure_one()
        datos = self._leer_respuesta(self.respuesta)
        if not datos['condicion']:
            raise UserError(
                'No encontré la parte «CONDICIÓN:» en la respuesta. Pegue la respuesta '
                'completa de la IA, o pídale que respete el formato de respuesta.')
        vals = {'condition_code': datos['condicion'],
                'system_ids': [(6, 0, self.system_ids.ids)],
                'solicitud_ia': self.solicitud or False}
        if datos['mensaje']:
            vals['message'] = datos['mensaje']
        try:
            self.rule_id.write(vals)
        except ValidationError as e:
            raise UserError(
                'La condición que devolvió la IA tiene un problema:\n\n%s\n\nCopie este '
                'mensaje en la IA y pídale que la corrija.' % e.args[0]) from e
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'title': 'Condición aplicada',
                'message': 'Revise la validación y use «Probar con una cotización» con una '
                           'persiana que deba disparar y otra que no.',
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }
