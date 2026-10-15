# -*- coding: utf-8 -*-
from odoo import api, fields, models


class SafraValidationRule(models.Model):
    """Configuración de las validaciones de negocio del cotizador.

    Réplica configurable del archivo "Restricciones y Validaciones de
    Productos": cada validación implementada en el motor
    (safra.quote.line._validations) tiene aquí su severidad y mensaje,
    editables sin tocar código. Si el registro no existe, el motor usa los
    valores por defecto definidos en código.
    """
    _name = 'safra.validation.rule'
    _description = 'Validación del Cotizador'
    _order = 'code'

    _code_uniq = models.Constraint('UNIQUE(code)', 'El código de la validación debe ser único.')

    code = fields.Char(string='Código', required=True, index=True)
    name = fields.Char(string='Nombre', required=True)
    severity = fields.Selection([
        ('error', 'Error (bloquea)'),
        ('warning', 'Advertencia'),
        ('info', 'Información'),
    ], string='Severidad', required=True, default='error')
    active = fields.Boolean(default=True)
    # Revisión 17-sep: el catálogo completo del archivo «Restricciones y
    # Validaciones de Productos» vive aquí — las reglas ya cableadas al
    # motor del portal y las que siguen pendientes (roadmap visible y
    # mensajes administrables desde ya).
    estado = fields.Selection([
        ('portal', 'Activa en el portal'),
        ('pendiente', 'Pendiente de implementación'),
    ], string='Estado', required=True, default='portal')
    seccion = fields.Char(string='Sección (archivo Safra)')
    # Apunte 23-sep (estilo reglas salariales de nómina): condición en
    # Python para crear validaciones NUEVAS sin desarrollo. Si la
    # expresión es verdadera para una línea, la validación dispara con la
    # severidad y el mensaje de este registro.
    condition_code = fields.Text(
        string='Condición (código)',
        help="Expresión Python evaluada por cada línea del pedido; si es\n"
             "verdadera, dispara esta validación (el mensaje admite\n"
             "comodines de las mismas variables, ej. {ancho}).\n"
             "Variables disponibles:\n"
             "  ancho, alto, cantidad → dimensiones digitadas\n"
             "  atributos  → dict con todos los campos del formulario\n"
             "               (ej. atributos.get('quantity_lamas'))\n"
             "  tela, color → registros de la referencia y el color\n"
             "               (ej. tela.is_sheer, tela.peso_gm2)\n"
             "  sistema    → código del sistema (ej. '01')\n"
             "  con_motor, alineado, exhibicion → True/False\n"
             "Ejemplo: sistema == '01' and ancho > 3 and not con_motor")
    message = fields.Char(
        string='Mensaje',
        help='Plantilla del mensaje. Placeholders entre llaves según la '
             'validación (p. ej. {alto_maximo}, {carga}, {peso}).')
    description = fields.Text(string='Descripción')


    # Reglas del motor cuya condición SÍ es expresable línea a línea: se
    # siembran en el campo «Condición (código)» para que el funcional las
    # vea y las pueda ajustar (código presente = el código manda).
    SEED_CONDITIONS = {
        'V_RANGO_ANCHO': ("ancho and limites['wmax'] and "
                          "(ancho < limites['wmin'] or ancho > limites['wmax'])"),
        'V_RANGO_ALTO': ("alto and limites['hmax'] and "
                         "(alto < limites['hmin'] or alto > limites['hmax'])"),
        'V_CENEFA_ENTERA': ("atributos.get('corte_cenefa') == '2' and tela "
                            "and not tela.permite_cenefa_entera"),
        # Pendientes 24-sep (11.2/11.3): 2en1 = una Blackout + una Sheer;
        # Sheer 2en1 = Referencia 1 Blackout y Referencia 2 Sheer.
        'V_2EN1_FAMILIA': ("sistema == '32' and tela and linea.fabric_id_2 "
                           "and not ((tela.is_blackout or linea.fabric_id_2.is_blackout) "
                           "and (tela.is_sheer or linea.fabric_id_2.is_sheer))"),
        'V_SHEER2EN1_REF': ("sistema == '61' and tela and linea.fabric_id_2 "
                            "and not (tela.is_blackout and linea.fabric_id_2.is_sheer)"),
        'V_DISENO_SELECCION': "linea.design_print and not linea.custom_design",
        'V_LOCALIZACION': ("not linea.location and sistema not in "
                           "('43', '33', '34', '52', '31', '56', '58', '59')"),
        'V_SEGUNDA_TELA': "sistema in ('32', '61') and not linea.fabric_id_2",
        'V_ENROLLE_SHEER': ("sistema == '61' and linea.orientation "
                            "and linea.orientation != 'frente'"),
        'V_ATRAVESADO': ("linea.atravesar_tela == 'atravesar' and tela "
                         "and tela.pierceable_type != 'si_cliente'"),
        'V_ANCHO_MIN_MOTOR': ("con_motor and linea.motor and linea.motor != '7' "
                              "and ancho and ancho < 0.80"),
        'V_CADENA_EXTRA': ("linea.extra_chain and alto and "
                           "(linea.extra_chain > alto + 2.50 "
                           "or linea.extra_chain < alto * 0.75)"),
        'V_ESTAMPADO_M2': ("linea.design_print and ancho and alto and "
                           "float(atributos.get('print_m2') or linea.print_m2 or 0) "
                           "and float(atributos.get('print_m2') or linea.print_m2) "
                           "< ancho * alto"),
        'V_TELAS_REPETIDAS': "len(telas) != len(set(telas))",
        'V_ANCHO_ROLLO': ("tela and tela.pierceable_type == 'no' "
                          "and ancho_rollo and ancho > ancho_rollo"),
        'V_TEXTURA_SELECCION': ("tela and tela.is_texturable "
                                "and 'textura_design' in campos "
                                "and not atributos.get('textura_design')"),
        'V_MAX_LAMAS': ("maximo_lamas is not None and total_lamas "
                        "and total_lamas != maximo_lamas"),
        'V_LAMAS_TELA': "total_lamas and suma_lamas > total_lamas",
        # Pendientes 24-sep (11.1): con 2+ telas la suma de lamas por tela
        # debe ser EXACTA (una tela sin diligenciar cuenta como 0 y también
        # dispara la regla); con una sola tela no aplica.
        'V_LAMAS_TELA_SUMA': ("len(telas) >= 2 and total_lamas "
                              "and suma_lamas != total_lamas"),
    }

    # Mensajes por defecto de esas reglas (mismos del motor, con los
    # comodines del contexto: {ancho}, {limites[wmax]}, {tela.name}…).
    SEED_MESSAGES = {
        'V_RANGO_ANCHO': ('OB0005: El ancho {ancho} m está fuera del rango '
                          'del sistema ({limites[wmin]} - {limites[wmax]} m).'),
        'V_RANGO_ALTO': ('OB0005: El alto {alto} m está fuera del rango '
                         'del sistema ({limites[hmin]} - {limites[hmax]} m).'),
        'V_CENEFA_ENTERA': ('E20003: La tela seleccionada no permite el '
                            'corte de cenefa entera; elija «Cenefa añadida» '
                            'u otra tela.'),
        'V_2EN1_FAMILIA': ('E20008: El Enrollable 2 en 1 requiere una tela '
                           'de la familia Blackout y una de la familia '
                           'Sheer.'),
        'V_SHEER2EN1_REF': ('E20009: En el Sheer 2 en 1 la Referencia 1 '
                            'debe ser de la familia Blackout y la '
                            'Referencia 2 de la familia Sheer.'),
        'V_DISENO_SELECCION': ('E20002: Elija el diseño a imprimir en el '
                               'catálogo con imágenes, o marque «Diseño '
                               'propio» para subir su imagen.'),
        'V_LOCALIZACION': ("E13095: Por favor ingrese un valor en el campo "
                           "'Localización'."),
        'V_SEGUNDA_TELA': ('E13022: Por favor seleccione la segunda tela de '
                           'la persiana 2 en 1.'),
        'V_ENROLLE_SHEER': ("E13095: En el sistema SHEER 2EN1 solo se permite "
                            "'Orientación del Enrollado' hacia el frente."),
        'V_ATRAVESADO': ('E13026: La tela seleccionada no permite forzar el '
                         'corte atravesado.'),
        'V_ANCHO_MIN_MOTOR': ('E13095: El ancho mínimo para una persiana '
                              'motorizada es de 0.80 m.'),
        'V_CADENA_EXTRA': ('E13082: La cadena/cordón extra está fuera del '
                           'rango permitido para el alto digitado.'),
        'V_ESTAMPADO_M2': ('E10027: Los m² de impresión son menores al área '
                           'de la persiana ({ancho} × {alto} m).'),
        'V_TELAS_REPETIDAS': ('E20005: Hay telas repetidas con el mismo color '
                              'en la persiana; elija colores distintos.'),
        'V_ANCHO_ROLLO': ('E20007: El ancho digitado ({ancho} m) supera el '
                          'ancho del rollo ({ancho_rollo} m) y la tela no es '
                          'atravesable; no es posible fabricarla.'),
        'V_TEXTURA_SELECCION': ('E20006: La referencia {tela.name} es '
                                'texturizada: elija el diseño de textura en '
                                'el catálogo con imágenes.'),
        'V_MAX_LAMAS': ('E20012: Para {ancho} m con esta apertura el total de '
                        'lamas debe ser {maximo_lamas} (digitó {total_lamas}).'),
        'V_LAMAS_TELA': ('E20004: La suma de lamas por tela ({suma_lamas}) '
                         'excede la cantidad total de lamas ({total_lamas}).'),
        'V_LAMAS_TELA_SUMA': ('E20018: La suma de lamas por tela '
                              '({suma_lamas}) debe ser igual a la cantidad '
                              'total de lamas ({total_lamas}).'),
    }

    @api.model
    def _seed_condition_codes(self, _ids=None):
        """Llena la condición de las reglas expresables que estén vacías
        (idempotente; si el funcional la edita o la borra, se respeta —
        borrarla devuelve la regla al motor interno)."""
        for code, cond in self.SEED_CONDITIONS.items():
            rule = self.with_context(active_test=False).search(
                [('code', '=', code), ('condition_code', '=', False)], limit=1)
            if rule:
                vals = {'condition_code': cond}
                if not rule.message and code in self.SEED_MESSAGES:
                    vals['message'] = self.SEED_MESSAGES[code]
                rule.write(vals)

    @api.model
    def _fix_panel_apertura_error(self, _ids=None):
        """Reunión 28-sep (fila 16): la apertura fuera de las combinaciones
        posibles debe BLOQUEAR. En bases antiguas el registro quedó como
        advertencia (es noupdate) y el pedido se guardaba. Se corrige una
        sola vez; si después el funcional la vuelve a poner como
        advertencia, se respeta."""
        Param = self.env['ir.config_parameter'].sudo()
        marca = 'website_quotes_safra.fix_panel_apertura_error'
        if Param.get_param(marca):
            return
        self.with_context(active_test=False).search([
            ('code', '=', 'V_PANEL_APERTURA'), ('severity', '!=', 'error'),
        ]).write({'severity': 'error'})
        Param.set_param(marca, '1')

    @api.model
    def _fix_rollo_disponible_warning(self, _ids=None):
        """Pruebas 09-oct: la falta de rollo (E20027) no debe impedir
        finalizar el pedido; la matriz deja ese bloqueo para la fase de
        fabricación. El registro es noupdate: se pasa a advertencia una sola
        vez y, si después el funcional lo vuelve a poner como error, se
        respeta."""
        Param = self.env['ir.config_parameter'].sudo()
        marca = 'website_quotes_safra.fix_rollo_disponible_warning'
        if Param.get_param(marca):
            return
        self.with_context(active_test=False).search([
            ('code', '=', 'V_ROLLO_DISPONIBLE'), ('severity', '=', 'error'),
        ]).write({'severity': 'warning'})
        Param.set_param(marca, '1')

    @api.model
    def _reseed_2en1_family_rules(self, _ids=None):
        """Pendientes 24-sep: reglas cuya definición cambió por decisión del
        cliente — se reescriben condición y mensaje aunque ya existan
        (11.2/11.3 familias de los 2 en 1; 11.1 suma exacta de lamas)."""
        updates = {
            'V_2EN1_FAMILIA': {},
            'V_SHEER2EN1_REF': {},
            'V_LAMAS_TELA_SUMA': {'severity': 'error'},
        }
        for code, extra in updates.items():
            rule = self.with_context(active_test=False).search(
                [('code', '=', code)], limit=1)
            if rule:
                vals = dict(extra,
                            condition_code=self.SEED_CONDITIONS[code],
                            message=self.SEED_MESSAGES[code])
                rule.write(vals)

    @api.model
    def get_config(self, code):
        """(activa, severidad, mensaje) para un código; None si no hay registro."""
        rule = self.search([('code', '=', code), ('active', 'in', [True, False])], limit=1)
        if not rule:
            return None
        return {'active': rule.active, 'severity': rule.severity,
                'message': rule.message,
                'has_code': bool(rule.condition_code)}
