# -*- coding: utf-8 -*-
import logging
import re
from string import Formatter

from markupsafe import Markup

from odoo import SUPERUSER_ID, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.safe_eval import test_python_expr

from . import safra_reglas_17 as R17
from .safra_panel import evaluar_formula, _mensaje_amigable, _ASIGNA_RESULT

_logger = logging.getLogger(__name__)

# Sprint 1.7: momento en que se revisa la regla, del más temprano al último.
# Cada regla sale desde su momento y se vuelve a revisar en los siguientes
# (una regla «al digitar» también se revisa al guardar la línea y al
# finalizar el pedido).
MOMENTOS = [
    ('campo', 'Al digitar un campo'),
    ('linea', 'Al guardar la línea'),
    # Revisión 28-oct: al pulsar «Aplicar» en el configurador de secuencia.
    ('secuencia', 'Al aplicar la secuencia'),
    ('pedido', 'Al finalizar el pedido'),
]
NIVEL_MOMENTO = {'campo': 0, 'linea': 1, 'secuencia': 2, 'pedido': 3}



class SinDigitar(str):
    """En un mensaje, el dato sin digitar se lee «sin digitar» con cualquier
    formato ({limites[wmax]:.2f})."""

    def __new__(cls):
        return super().__new__(cls, 'sin digitar')

    def __format__(self, spec):
        return str(self)

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

    code = fields.Char(
        string='Código', required=True, index=True,
        help='Código de la regla, único (p. ej. R_ANCHO_MOTOR). Sale al final del mensaje '
             'entre corchetes para buscar la regla. Se puede cambiar: el programa la '
             'encuentra por la Clave interna. No es el código de Safra: E13095 y los demás '
             'se repiten en muchas validaciones y van al inicio del Mensaje.')
    # Revisión 28-oct: Safra cambia el Código de las reglas; el programa
    # (cálculos con «hallazgo», Ajustes, portal) las busca por esta clave,
    # que no cambia.
    clave = fields.Char(
        string='Clave interna', readonly=True, copy=False, index=True,
        help='Con esta clave el programa encuentra la regla (es el código con el que se '
             'creó). No cambia aunque se cambie el Código. Las reglas que crea el '
             'funcional no la necesitan: se manejan solo con su condición.')
    name = fields.Char(string='Nombre', required=True)
    severity = fields.Selection([
        ('error', 'Error (bloquea)'),
        ('warning', 'Advertencia (deja continuar)'),
        ('info', 'Información'),
    ], string='Severidad', required=True, default='error',
        help='Error: el mensaje sale en rojo y no deja guardar la línea ni '
             'finalizar el pedido.\nAdvertencia: sale en amarillo y deja '
             'continuar.\nInformación: sale en azul, solo informa.')
    # Sprint 1.7 (video 23-oct): un solo momento de disparo por regla y los
    # sistemas en los que aplica.
    momento = fields.Selection(
        MOMENTOS, string='Momento de disparo', required=True, default='linea',
        help='Cuándo se revisa la regla por primera vez:\n'
             '- Al digitar un campo: apenas el cliente cambia el campo '
             'elegido; el mensaje sale debajo de ese campo.\n'
             '- Al guardar la línea: al pulsar «Guardar línea».\n'
             '- Al finalizar el pedido: al enviar el pedido; aquí se pueden '
             'comparar las líneas entre sí.\n'
             'En los momentos siguientes la regla se vuelve a revisar.\n'
             'Las reglas del corte de la tela (V_ANCHO_ROLLO, V_SIN_ANCHO_ROLLO, V_ANADIDO, '
             'V_ANADIDO_MAXIMO, V_CORTE_ATRAVESADO y V_CORTE_PANOS, por su Clave interna) salen '
             'además junto a la tela mientras se digita, sea cual sea su momento; si una es '
             'Error, el portal no deja seguir configurando la persiana, salvo V_CORTE_ATRAVESADO '
             'y V_CORTE_PANOS, que se resuelven marcando la aceptación del corte (sí frenan al '
             'guardar la línea y al finalizar).')
    trigger_field_id = fields.Many2one(
        'safra.field', string='Campo que la dispara', ondelete='set null',
        help='Con el momento «Al digitar un campo»: el campo del formulario '
             'que, al cambiar, revisa la regla.')
    system_ids = fields.Many2many(
        'safra.system', 'safra_validation_rule_system_rel', 'rule_id', 'system_id',
        string='Sistemas',
        help='Sistemas en los que aplica la regla. Vacío = todos.')
    active = fields.Boolean(string='Activa', default=True)
    # Revisión 17-sep: el catálogo completo del archivo «Restricciones y
    # Validaciones de Productos» vive aquí — las reglas ya cableadas al
    # motor del portal y las que siguen pendientes (roadmap visible y
    # mensajes administrables desde ya).
    # Sprint 1.7: un solo catálogo. Cada función del archivo de Safra dice
    # con qué reglas del portal quedó cubierta, o por qué no aplica.
    estado = fields.Selection([
        ('portal', 'Activa en el portal'),
        ('cubierta', 'Cubierta por reglas del portal'),
        ('pendiente', 'Pendiente de implementación'),
        ('pendiente_safra', 'Pendiente información de Safra'),
        ('inactivada', 'Inactivada o eliminada por Safra'),
    ], string='Estado', required=True, default='portal')
    seccion = fields.Char(
        string='Sección (archivo Safra)',
        help='Capítulo del archivo «Restricciones y Validaciones de Productos» al que '
             'pertenece (Comunes, Enrollables, Paneles, Cortinas…). Solo informativo: '
             'sirve para agrupar y filtrar la lista.')
    funcion_safra = fields.Char(
        string='Función Safra',
        help='Nombre de la validación en el archivo «Restricciones y Validaciones '
             'de Productos» (p. ej. ValidaAlto). Une la regla del portal con su registro '
             'del catálogo: buscando por este nombre salen juntas. Solo informativo.')
    regla_ids = fields.Many2many(
        'safra.validation.rule', 'safra_validation_rule_cubre_rel', 'catalogo_id', 'regla_id',
        string='Reglas del portal que la cubren',
        help='Reglas del portal que implementan esta función del archivo de Safra.')
    # Revisión 3-nov: las reglas que trae el módulo no se borran (sin ellas se
    # pierde la validación y al actualizar no vuelven); se desactivan.
    del_modulo = fields.Boolean(
        string='Regla del módulo', readonly=True, copy=False,
        help='La creó el módulo al instalarse o actualizarse. No se puede borrar: para que '
             'no se revise, desmarque Activa (o Acción › Archivar). Las reglas creadas en '
             'esta pantalla sí se pueden borrar.')
    # Revisión 3-nov: una condición que falla con los datos de una persiana no
    # dispara; el error queda en la regla para que no pase en silencio.
    ultimo_error = fields.Char(
        string='Error de la condición', readonly=True, copy=False,
        help='Último error al revisar la condición en el portal: mientras falle, la regla no '
             'dispara. Se borra al cambiar la condición o con «Quitar aviso de error».')
    ultimo_error_fecha = fields.Datetime(string='Con error desde', readonly=True, copy=False)
    # Apunte 23-sep (estilo reglas salariales de nómina): condición en
    # Python para crear validaciones NUEVAS sin desarrollo. Si la
    # expresión es verdadera para una línea, la validación dispara con la
    # severidad y el mensaje de este registro.
    condition_code = fields.Text(
        string='Condición (código)',
        help="Se revisa por cada línea del pedido; si da verdadero, la regla "
             "dispara con la severidad y el mensaje de este registro.\n"
             "En una línea: la condición (ej. sistema == '01' and ancho > 3).\n"
             "En varias líneas: la última debe ser result = <condición>.\n"
             "«hallazgo» trae lo que encontró el cálculo interno del sistema "
             "para esta regla. Vacía = la regla usa solo el cálculo interno.\n"
             "Vea la ayuda del formulario para las variables y ejemplos.")
    message = fields.Char(
        string='Mensaje',
        help='Texto que ve el cliente. Entre llaves se reemplaza por el valor '
             'de una variable de la condición, p. ej. {ancho}, {tela.name}, '
             '{limites[wmax]}, o un dato del hallazgo como {alto_maximo}. '
             'Vacío = el mensaje del cálculo interno.')
    description = fields.Text(string='Descripción')
    # Revisión 28-oct: lo que se escribió en «¿Qué quiere validar?» del
    # asistente para IA; al volver a abrirlo no hay que escribirlo otra vez.
    solicitud_ia = fields.Text(
        string='Última solicitud a la IA', copy=False,
        help='Lo último que se escribió en «¿Qué quiere validar?» al generar la instrucción '
             'para IA. Sale escrito la próxima vez que se abre el asistente.')


    # Reglas del motor cuya condición SÍ es expresable línea a línea: se
    # siembran en el campo «Condición (código)» para que el funcional las
    # vea y las pueda ajustar (código presente = el código manda).
    SEED_CONDITIONS = {
        # Barrido de la matriz (03-nov): las reglas nuevas (R17.REGLAS_BARRIDO).
        **{r['code']: r['condition'] for r in R17.REGLAS_BARRIDO},
        'V_RANGO_ANCHO': ("ancho and limites['wmax'] and "
                          "(ancho < limites['wmin'] or ancho > limites['wmax'])"),
        'V_RANGO_ALTO': ("alto and limites['hmax'] and "
                         "(alto < limites['hmin'] or alto > limites['hmax'])"),
        # Ajustes 20-oct (fila 91): por debajo del ancho del rollo la cenefa
        # puede ir entera; si lo supera, solo con telas que lo permiten.
        # Reunión 28-oct: la cenefa en tela sigue el atravesable de la tela.
        'V_CENEFA_ENTERA': "corte_cenefa == '2' and tipo_corte_cenefa == 'anadida'",
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
        # Revisión cálculo de tubo (27-oct): reglas con su condición en
        # Validaciones; el código solo calcula «campos» y «tramo».
        'V_MOTOR_OBLIGATORIO': "has_motor and 'motor' in campos and (motor or '') in ('', '0', 'sin')",
        # Acta del 30-oct (Tubo, punto 8): la disponibilidad del tubo, en el menú.
        'V_TUBO_SIN_INSUMO': "bool(insumos_sin_stock)",
        'V_SECUENCIA_DEP_ANCHO': ("maximo = 4.0\n"
                                  "result = bool(tramo) and tramo['ancho'] > maximo"),
        'V_SECUENCIA_DEP_TUBO': (
            "sin_tubo = bool(tramo) and tramo['tabla'] and not tramo['tubo']\n"
            "alto = bool(tramo) and not sin_tubo and tramo['alto_ok'] is False\n"
            "peso = bool(tramo) and not sin_tubo and not alto and tramo['peso_ok'] is False\n"
            "mensaje = ('No hay tubo en la tabla de estructura para %s, unidas por soportes '\n"
            "           'dependientes (%.2f m de ancho en total).' % (tramo['persianas'], tramo['ancho']) if sin_tubo\n"
            "           else 'E10004: %s, unidas por soportes dependientes (%.2f m de ancho), superan el '\n"
            "                'alto máximo de %.2f m con el tubo %s.' % (tramo['persianas'], tramo['ancho'],\n"
            "                                                          tramo['alto_maximo'], tramo['tubo']) if alto\n"
            "           else 'E13095: %s, unidas por soportes dependientes, pesan %d g y la carga máxima '\n"
            "                'del tubo %s es %d g: debe motorizarse o dividirse.' % (\n"
            "                    tramo['persianas'], tramo['peso'], tramo['tubo'], tramo['carga']) if peso\n"
            "           else '')\n"
            "result = sin_tubo or alto or peso"),
    }

    # Mensajes por defecto de esas reglas (mismos del motor, con los
    # comodines del contexto: {ancho}, {limites[wmax]}, {tela.name}…).
    # Ajustes 20-oct: semillas anteriores que se actualizan si nadie las editó.
    SEED_ANTERIORES = {
        'V_CENEFA_ENTERA': (
            "atributos.get('corte_cenefa') == '2' and tela and not tela.permite_cenefa_entera",
            'E20003: La tela seleccionada no permite el corte de cenefa entera; '
            'elija «Cenefa añadida» u otra tela.'),
    }

    SEED_MESSAGES = {
        **{r['code']: r['message'] for r in R17.REGLAS_BARRIDO},
        'V_RANGO_ANCHO': ('OB0005: El ancho {ancho} m está fuera del rango '
                          'del sistema ({limites[wmin]} - {limites[wmax]} m).'),
        'V_RANGO_ALTO': ('OB0005: El alto {alto} m está fuera del rango '
                         'del sistema ({limites[hmin]} - {limites[hmax]} m).'),
        'V_CENEFA_ENTERA': ('E20003: El ancho supera el ancho del rollo y la tela '
                            'no se puede atravesar; elija «Cenefa añadida» u otra tela.'),
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
        'V_MOTOR_OBLIGATORIO': 'E13095: La persiana va con motor: seleccione el Motor.',
        'V_TUBO_SIN_INSUMO': ('E20038: El tubo {estructura[tubo]} no está disponible: no hay '
                              'existencias de {insumos_sin_stock}.'),
        'V_SECUENCIA_DEP_ANCHO': ('E13095: Entre soportes dependientes ({tramo[persianas]}) el ancho '
                                  'suma {tramo[ancho]:.2f} m y el máximo es {maximo:.2f} m.'),
        'V_SECUENCIA_DEP_TUBO': '{mensaje}',
    }

    @api.model
    def _seed_condition_codes(self, _ids=None):
        """Llena la condición de las reglas expresables que estén vacías.
        Sprint 1.7: una sola vez por base — si el funcional la edita o la
        borra, se respeta (borrarla devuelve la regla al cálculo interno)."""
        Param = self.env['ir.config_parameter'].sudo()
        marca = 'website_quotes_safra.seed_condiciones'
        if Param.get_param(marca):
            return
        Param.set_param(marca, '1')
        for code, cond in self.SEED_CONDITIONS.items():
            rule = self.with_context(active_test=False).search(
                [('code', '=', code), ('condition_code', '=', False)], limit=1)
            if rule:
                vals = {'condition_code': cond}
                if not rule.message and code in self.SEED_MESSAGES:
                    vals['message'] = self.SEED_MESSAGES[code]
                rule.write(vals)

    # Revisión 10-nov (fila 68): el peso máximo con su condición escrita en
    # Validaciones (antes era del cálculo interno).
    SEED_CONDITIONS = dict(SEED_CONDITIONS, V_PESO_MAXIMO=R17.PESO_MAXIMO_CONDICION,
                           V_REQUIERE_MOTOR=R17.REQUIERE_MOTOR_CONDICION,
                           V_ALTO_MAXIMO=R17.ALTO_MAXIMO_CONDICION,
                           V_ESTRUCTURA=R17.ESTRUCTURA_CONDICION)
    SEED_MESSAGES = dict(SEED_MESSAGES, V_PESO_MAXIMO=R17.PESO_MAXIMO_MENSAJE,
                         V_REQUIERE_MOTOR=R17.MENSAJE_REQUIERE_MOTOR,
                         V_ALTO_MAXIMO=R17.CAMBIOS['V_ALTO_MAXIMO']['message'],
                         V_ESTRUCTURA=R17.CAMBIOS['V_ESTRUCTURA']['message'])

    # Revisión cálculo de tubo (27-oct): reglas nuevas con su condición
    # escrita aquí (no en el código) y sus sistemas.
    REGLAS_TUBO = {'V_MOTOR_OBLIGATORIO': (), 'V_SECUENCIA_DEP_ANCHO': ('01', '06', '02', '04'),
                   'V_SECUENCIA_DEP_TUBO': ()}

    @api.model
    def _seed_condiciones_tubo(self, _ids=None):
        """Una sola vez por base: condición, mensaje y sistemas de las reglas
        de la revisión del cálculo de tubo (si siguen sin condición)."""
        Param = self.env['ir.config_parameter'].sudo()
        marca = 'website_quotes_safra.seed_condiciones_tubo'
        if Param.get_param(marca):
            return
        Param.set_param(marca, '1')
        Rule = self.sudo().with_context(active_test=False)
        System = self.env['safra.system'].sudo()
        for code, sistemas in self.REGLAS_TUBO.items():
            rule = Rule.search([('code', '=', code)], limit=1)
            if not rule or (rule.condition_code or '').strip() not in ('', 'hallazgo'):
                continue
            vals = {'condition_code': self.SEED_CONDITIONS[code], 'message': self.SEED_MESSAGES[code]}
            if sistemas and not rule.system_ids:
                vals['system_ids'] = [(6, 0, System.search([('code', 'in', sistemas)]).ids)]
            rule.write(vals)

    @api.model
    def _ajuste_tubo_sin_insumo(self, _ids=None):
        """Acta del 30-oct (Tubo, punto 8: «la alerta de disponibilidad debe
        quedar por el menú de restricciones»), una sola vez por base: la
        regla del tubo sin existencias de sus insumos pasa de «hallazgo» (lo
        decidía el código) a su condición y su mensaje escritos en
        Validaciones. Si Safra ya la editó, se respeta."""
        Param = self.env['ir.config_parameter'].sudo()
        marca = 'website_quotes_safra.ajuste_tubo_sin_insumo'
        if Param.get_param(marca):
            return
        Param.set_param(marca, '1')
        code = 'V_TUBO_SIN_INSUMO'
        rule = self._por_clave([code])[:1]
        if not rule or (rule.condition_code or '').strip() not in ('', 'hallazgo'):
            return
        vals = {'condition_code': self.SEED_CONDITIONS[code]}
        if not rule.message:
            vals['message'] = self.SEED_MESSAGES[code]
        if not rule.description:
            vals['description'] = (
                'Acta del 30-oct (Tubo, punto 8): el tubo de la persiana (estructura[\'tubo\']) '
                'no se puede fabricar si a uno de sus insumos de estructura le faltan existencias '
                '(insumos_sin_stock: los productos del maestro con ese tubo en «Tubos», separados '
                'por coma). El portal muestra este mensaje en la ficha técnica mientras se digita.')
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
    def _ajuste_mensaje_requiere_motor(self):
        """Reunión 09-nov (fila 68): V_REQUIERE_MOTOR ahora también sale por
        el alto y pide marcar el motor. Se cambia el mensaje solo si sigue el
        que sembró el módulo (si Safra lo editó, se respeta). Una vez."""
        self.with_context(active_test=False).search([
            ('code', '=', 'V_REQUIERE_MOTOR'), ('message', '=', R17.MENSAJE_REQUIERE_MOTOR_ANTERIOR),
        ]).write({'message': R17.MENSAJE_REQUIERE_MOTOR})
        return True

    @api.model
    def _reseed_2en1_family_rules(self, _ids=None):
        """Pendientes 24-sep: reglas cuya definición cambió por decisión del
        cliente — se reescriben condición y mensaje aunque ya existan
        (11.2/11.3 familias de los 2 en 1; 11.1 suma exacta de lamas).
        Sprint 1.7: una sola vez por base, para respetar lo que el
        funcional edite después."""
        Param = self.env['ir.config_parameter'].sudo()
        marca = 'website_quotes_safra.reseed_2en1'
        if Param.get_param(marca):
            return
        Param.set_param(marca, '1')
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
    def _por_clave(self, claves):
        """Reglas que el programa conoce por estas claves (la Clave interna
        o, en una regla sin clave, su Código)."""
        claves = list(claves)
        return self.sudo().with_context(active_test=False).search(
            ['|', ('clave', 'in', claves), '&', ('clave', '=', False), ('code', 'in', claves)])

    def _clave_programa(self):
        self.ensure_one()
        return self.clave or self.code

    @api.model
    def _ajuste_motor_ancho_min(self, _ids=None):
        """Revisión 28-oct, una sola vez por base: motor_ancho_min ya no trae
        0,80 cuando el motor no tiene U_AnchoMin (vale 0); el valor por
        defecto (0,70 m) queda en la condición de V_ANCHO_MIN_MOTOR, donde
        Safra lo cambia. Solo si la condición sigue como la dejó el módulo."""
        Param = self.env['ir.config_parameter'].sudo()
        marca = 'website_quotes_safra.ajuste_motor_ancho_min'
        if Param.get_param(marca):
            return
        Param.set_param(marca, '1')
        regla = self._por_clave(['V_ANCHO_MIN_MOTOR'])[:1]
        if regla and (regla.condition_code or '').strip() == 'con_motor and ancho and ancho < motor_ancho_min':
            vals = {'condition_code': 'minimo = motor_ancho_min or 0.70\n'
                                      'result = con_motor and ancho and ancho < minimo'}
            if (regla.message or '').strip() == ('E13095: El ancho mínimo para el motor seleccionado '
                                                 'es de {motor_ancho_min} metros.'):
                vals['message'] = ('E13095: El ancho mínimo para el motor seleccionado es de '
                                   '{minimo} metros.')
            regla.write(vals)

    @api.model
    def _ajuste_dobladillo_consumo(self, _ids=None):
        """Revisión 30-oct (Dobladillo o Bajo falso), una sola vez por base:
        cada dobladillo lleva su consumo (R17.DOBLADILLO_CONSUMO) y se ofrece
        si el alto cabe con él. Solo las opciones sin consumo y las fórmulas
        que siguen como las dejó el módulo."""
        Param = self.env['ir.config_parameter'].sudo()
        marca = 'website_quotes_safra.ajuste_dobladillo_consumo'
        if Param.get_param(marca):
            return
        Param.set_param(marca, '1')
        campo = self.env['safra.field'].sudo().with_context(active_test=False).search(
            [('code', '=', 'bajofalso')], limit=1)
        if not campo:
            return
        opciones = list(campo.option_ids) + list(self.env['safra.system.field.option'].sudo().search(
            [('system_field_id.field_id', '=', campo.id)]))
        anterior = R17.DOBLADILLO_CORTE['BN_FLTE'][0].strip()
        for opt in opciones:
            consumo = R17.DOBLADILLO_CONSUMO.get(opt.value)
            if not consumo:
                continue
            vals = {}
            if not opt.consumo_dobladillo:
                vals['consumo_dobladillo'] = consumo
            if (opt.formula or '').strip() in ('', anterior):
                vals['formula'] = R17.DOBLADILLO_30OCT
            if vals:
                opt.write(vals)

    @api.model
    def _ajuste_sin_ancho_rollo(self, _ids=None):
        """Revisión 30-oct (U_Ancho), una sola vez por base: la regla del
        color sin ancho del rollo (ver R17.SIN_ANCHO_ROLLO)."""
        Param = self.env['ir.config_parameter'].sudo()
        marca = 'website_quotes_safra.ajuste_sin_ancho_rollo'
        if Param.get_param(marca):
            return
        Param.set_param(marca, '1')
        r = R17.SIN_ANCHO_ROLLO
        if self._por_clave([r['code']]):
            return
        systems = self.env['safra.system'].sudo().with_context(active_test=False).search(
            [('code', 'in', list(r['systems']))])
        self.sudo().create({
            'code': r['code'], 'name': r['name'], 'funcion_safra': r['funcion_safra'],
            'severity': r['severity'], 'momento': r['momento'],
            'system_ids': [(6, 0, systems.ids)], 'condition_code': r['condition'],
            'message': r['message'], 'description': r['description'], 'estado': 'portal',
        })

    @api.model
    def _ajuste_corte_panos(self, _ids=None):
        """Reunión 30-oct (fila 143, puntos 4 a 6), una sola vez por base: la
        regla de la aceptación del corte por paños en cortinas, la etiqueta
        «Acepto que la tela se corte por paños» del check en las cortinas (si no tiene una
        propia) y la fórmula del bajo falso sin «tela sin diseño» si quedó
        guardada como la dejó el módulo."""
        Param = self.env['ir.config_parameter'].sudo()
        marca = 'website_quotes_safra.ajuste_corte_panos'
        if Param.get_param(marca):
            return
        Param.set_param(marca, '1')
        clave = 'safra.formula.cortina_bajo_falso'
        if (Param.get_param(clave) or '').strip() == R17.CORTINA_BAJO_FALSO_ANTERIOR:
            Param.set_param(clave, R17.FORMULAS_CORTE_CORTINA[clave])
        r = R17.CORTE_PANOS
        systems = self.env['safra.system'].sudo().with_context(active_test=False).search(
            [('code', 'in', list(r['systems']))])
        self.env['safra.system.field'].sudo().search([
            ('system_id', 'in', systems.ids), ('field_id.code', '=', 'acepta_atravesado'),
            ('label_override', 'in', (False, ''))]).write({'label_override': R17.CORTE_PANOS_ETIQUETA,
                                                          'help_override': R17.CORTE_PANOS_AYUDA})
        if self._por_clave([r['code']]):
            return
        self.sudo().create({
            'code': r['code'], 'name': r['name'], 'funcion_safra': r['funcion_safra'],
            'severity': r['severity'], 'momento': r['momento'],
            'system_ids': [(6, 0, systems.ids)], 'condition_code': r['condition'],
            'message': r['message'], 'description': r['description'], 'estado': 'portal',
        })

    @api.model
    def _ajuste_barrido_matriz(self, _ids=None):
        """Barrido de la matriz (03-nov), una sola vez por base: crea las
        reglas nuevas (Posición del mando y Datos de despacho) con su
        condición y su mensaje si no existen."""
        Param = self.env['ir.config_parameter'].sudo()
        marca = 'website_quotes_safra.ajuste_barrido_matriz'
        if Param.get_param(marca):
            return
        Param.set_param(marca, '1')
        self._crear_reglas_barrido([r for r in R17.REGLAS_BARRIDO
                                    if r is not R17.CENEFA_EN_TELA_TELA])

    @api.model
    def _ajuste_reglas_visibles_1011(self):
        """Revisión 10-nov, una vez por base: reglas con la condición escrita
        en Validaciones en vez del cálculo interno («hallazgo»):
        V_DATO_SIN_DIGITAR (advertencia) y V_PESO_SIN_CARGA se crean, y
        V_PESO_MAXIMO recibe su condición (y su mensaje si está vacío). Lo
        que Safra ya haya escrito se respeta."""
        Rule = self.with_context(active_test=False)
        self._crear_reglas_barrido([R17.DATO_SIN_DIGITAR, R17.PESO_SIN_CARGA])
        nuevas = {'V_DATO_SIN_DIGITAR': (R17.DATO_SIN_DIGITAR['condition'], R17.DATO_SIN_DIGITAR['message']),
                  'V_PESO_MAXIMO': (R17.PESO_MAXIMO_CONDICION, R17.PESO_MAXIMO_MENSAJE),
                  'V_REQUIERE_MOTOR': (R17.REQUIERE_MOTOR_CONDICION, R17.MENSAJE_REQUIERE_MOTOR),
                  'V_ALTO_MAXIMO': (R17.ALTO_MAXIMO_CONDICION, R17.CAMBIOS['V_ALTO_MAXIMO']['message']),
                  'V_ESTRUCTURA': (R17.ESTRUCTURA_CONDICION, R17.CAMBIOS['V_ESTRUCTURA']['message'])}
        # Las condiciones que dejó el módulo (Safra no las cambió).
        del_modulo = {'', 'hallazgo', R17.CAMBIOS['V_ESTRUCTURA']['condition'].strip()}
        for code, (condicion, mensaje) in nuevas.items():
            for regla in Rule.search([('code', '=', code)]):
                if (regla.condition_code or '').strip() not in del_modulo:
                    continue
                vals = {'condition_code': condicion}
                if not regla.message or code == 'V_DATO_SIN_DIGITAR':
                    vals['message'] = mensaje
                try:
                    with self.env.cr.savepoint():
                        regla.write(vals)
                except ValidationError:
                    # El mensaje de Safra usaba datos del cálculo interno que
                    # la condición escrita no tiene: queda el del módulo.
                    regla.write(dict(vals, message=mensaje))
        return True

    @api.model
    def _crear_reglas_barrido(self, reglas):
        System = self.env['safra.system'].sudo().with_context(active_test=False)
        for r in reglas:
            if self._por_clave([r['code']]):
                continue
            systems = System.search([('code', 'in', list(r['systems']))]) if r['systems'] else System
            self.sudo().create({
                'code': r['code'], 'name': r['name'], 'funcion_safra': r['funcion_safra'],
                'severity': r['severity'], 'momento': r['momento'],
                'system_ids': [(6, 0, systems.ids)], 'condition_code': r['condition'],
                'message': r['message'], 'description': r['description'], 'estado': 'portal',
            })

    @api.model
    def _ajuste_tela_cenefa_en_tela(self, _ids=None):
        """Reunión 28-oct (fila 89), una sola vez por base: «Tela de Cenefa» y
        «Tela Cabezal Forrado» pasan a decir en el Catálogo de campos que
        listan las telas elegidas (antes lo hacía el código por su nombre
        técnico), y se crea «Tela de la cenefa en tela», que se activa con
        Cenefa en tela en los sistemas de varias telas, con su regla. Lo que
        Safra ya haya configurado se conserva."""
        Param = self.env['ir.config_parameter'].sudo()
        marca = 'website_quotes_safra.ajuste_tela_cenefa_en_tela'
        if Param.get_param(marca):
            return
        Param.set_param(marca, '1')
        self._crear_reglas_barrido([R17.CENEFA_EN_TELA_TELA])
        Field = self.env['safra.field'].sudo().with_context(active_test=False)
        Mapping = self.env['safra.system.field'].sudo().with_context(active_test=False)

        def campo(code):
            return Field.search([('code', '=', code)], limit=1)

        for code, modo in (('cenefa_tela', 'color'), ('cabezal_tela', 'referencia')):
            f = campo(code)
            if f and not f.opciones_telas:
                f.opciones_telas = modo
        datos = R17.CENEFA_EN_TELA_CAMPO
        tela, panel = campo('cenefa_tela'), campo('cenefa_panel')
        existente = campo(datos['code'])
        if existente:
            # Si el campo ya estaba (p. ej. la columna se perdió al actualizar
            # sin este código), se le devuelve la lista de telas elegidas.
            if not existente.opciones_telas:
                existente.opciones_telas = 'color'
            return
        if not tela:
            return
        nuevo = Field.create({
            'code': datos['code'], 'name': datos['name'], 'field_type': 'char',
            'opciones_telas': 'color', 'help_text': datos['help'],
            'section_id': tela.section_id.id, 'col_size': tela.col_size or 6,
            'sequence': (tela.sequence or 0) + 1,
            'depends_field_id': panel.id if panel else False,
            'depends_value': Field._S14_TELA if panel else False,
        })
        for m in Mapping.search([('field_id', '=', tela.id),
                                 ('system_id.code', 'in', list(datos['systems']))]):
            Mapping.create({'system_id': m.system_id.id, 'field_id': nuevo.id,
                            'sequence': (m.sequence or 0) + 1, 'active': m.active})

    @api.model
    def _ajuste_orden_resumen(self, _ids=None):
        """Barrido de la matriz (fila 124), una sola vez por base: el orden
        de las características del resumen del pedido, como el portal actual
        de Safra. Solo en los campos sin orden propio."""
        Param = self.env['ir.config_parameter'].sudo()
        marca = 'website_quotes_safra.ajuste_orden_resumen'
        if Param.get_param(marca):
            return
        Param.set_param(marca, '1')
        Field = self.env['safra.field'].sudo().with_context(active_test=False)
        for pos, grupo in enumerate(R17.ORDEN_RESUMEN, start=1):
            for sub, code in enumerate(grupo):
                f = Field.search([('code', '=', code), ('resumen_sequence', '=', 0)], limit=1)
                if f:
                    f.resumen_sequence = pos * 10 + sub

    @api.model
    def _ajuste_etiqueta_panos(self, _ids=None):
        """Reunión 3-nov, una sola vez por base: el check de las cortinas pasa
        de «Acepta corte por paños» a «Acepto que la tela se corte por paños»,
        con una ayuda que dice que es el cliente quien lo acepta. Solo si la
        etiqueta sigue como la dejó el módulo (o vacía) y no tiene ayuda propia."""
        Param = self.env['ir.config_parameter'].sudo()
        marca = 'website_quotes_safra.ajuste_etiqueta_panos'
        if Param.get_param(marca):
            return
        Param.set_param(marca, '1')
        mappings = self.env['safra.system.field'].sudo().search([
            ('system_id.code', 'in', list(R17.CORTE_PANOS['systems'])),
            ('field_id.code', '=', 'acepta_atravesado')])
        for m in mappings:
            vals = {}
            if (m.label_override or '') in ('', R17.CORTE_PANOS_ETIQUETA_ANTERIOR):
                vals['label_override'] = R17.CORTE_PANOS_ETIQUETA
            if not m.help_override:
                vals['help_override'] = R17.CORTE_PANOS_AYUDA
            if vals:
                m.write(vals)

    @api.model
    def _ajuste_cenefa_tela(self, _ids=None):
        """Reunión 28-oct (fila 91), una sola vez por base: «Tipo de corte
        Cenefa Tela» sigue las reglas del atravesable (tipo_corte_cenefa)
        en vez del ancho del rollo y U_CenefaEntera. Solo se cambian las
        fórmulas, el aviso y la condición que siguen como las dejó el módulo."""
        Param = self.env['ir.config_parameter'].sudo()
        marca = 'website_quotes_safra.ajuste_cenefa_tela'
        if Param.get_param(marca):
            return
        Param.set_param(marca, '1')
        campo = self.env['safra.field'].sudo().with_context(active_test=False).search(
            [('code', '=', 'corte_cenefa')], limit=1)
        anteriores = {(c, v, 'auto_formula' if t == 'auto' else 'formula'): f
                      for c, v, t, f in R17.FORMULAS_OPCION if c == 'corte_cenefa'}
        aviso_anterior = self.env['safra.field'].AJUSTES_1415_AUTO[('corte_cenefa', '1')][1]
        for (code, valor, nombre), formula in R17.CORTE_CENEFA_TELA.items():
            opt = campo.option_ids.filtered(lambda o: o.value == valor)[:1] if campo else False
            if not opt or (opt[nombre] or '').strip() not in ('', anteriores.get((code, valor, nombre), '').strip()):
                continue
            vals = {nombre: formula}
            if valor == '1' and nombre == 'auto_formula' and (opt.aviso or '') in ('', aviso_anterior):
                vals['aviso'] = R17.CORTE_CENEFA_AVISO
            opt.write(vals)
        regla = self._por_clave(['V_CENEFA_ENTERA'])[:1]
        cond, msg = R17.CENEFA_ENTERA_28OCT
        if regla and (regla.condition_code or '').strip() == R17.CAMBIOS['V_CENEFA_ENTERA']['condition'].strip():
            vals = {'condition_code': cond}
            if (regla.message or '').strip() == R17.CAMBIOS['V_CENEFA_ENTERA']['message'].strip():
                vals['message'] = msg
            regla.write(vals)

    @api.model
    def _llenar_clave_interna(self, _ids=None):
        """Una sola vez por base: cada regla existente guarda su código como
        Clave interna, antes de que Safra empiece a cambiar códigos."""
        Param = self.env['ir.config_parameter'].sudo()
        marca = 'website_quotes_safra.clave_interna'
        if Param.get_param(marca):
            return
        Param.set_param(marca, '1')
        self.env.cr.execute("UPDATE safra_validation_rule SET clave = code WHERE clave IS NULL")
        self.invalidate_model(['clave'])

    @api.model
    def get_config(self, code):
        """(activa, severidad, mensaje) para un código; None si no hay registro."""
        rule = self._por_clave([code])[:1]
        if not rule:
            return None
        return {'active': rule.active, 'severity': rule.severity,
                'message': rule.message,
                'has_code': bool(rule.condition_code)}

    # ------------------------------------------------------------------
    # Sprint 1.7: reglas parametrizables por código
    # ------------------------------------------------------------------
    # Reglas que se comparan entre líneas: solo al finalizar el pedido.
    REGLAS_PEDIDO = (
        'V_ALINEADO_ALTURA', 'V_ALINEADO_FRANJAS', 'V_ALINEADO_LOCALIZACION', 'V_ALINEADO_MIN',
        'V_CANAL_FUERA_RANGO', 'V_CANAL_SIN_CONTROL', 'V_CANAL_TOMADO',
        'V_CANAL_REQUERIDO', 'V_CONTROL_PEDIDO', 'V_CONTROL_REQUERIDO',
        'V_SECUENCIA', 'V_SECUENCIA_ALTO', 'V_SECUENCIA_MIN', 'V_SECUENCIA_NOMBRE',
        'V_SECUENCIA_PENDIENTE', 'V_SECUENCIA_DEP_ANCHO', 'V_SECUENCIA_DEP_TUBO',
        # Barrido de la matriz (03-nov): datos de despacho del pedido.
        'V_DESPACHO_DATOS',
        'V_ROLLO_ALINEADO', 'V_ROLLO_DISPONIBLE',
        'V_EXPRESS_CANTIDAD', 'V_PLANO_SEGMENTOS', 'V_REVALIDACION',
    )
    # Reglas que se revisan apenas se digita el campo.
    REGLAS_CAMPO = {
        'V_RANGO_ANCHO': 'width', 'V_RANGO_ALTO': 'height',
        'V_ANCHO_ROLLO': 'width', 'V_ANCHO_MIN_MOTOR': 'width',
    }
    # Sistemas en los que aplica la regla; la condición deja de preguntar
    # por el sistema (código: (sistemas, condición anterior, condición nueva)).
    SEED_SISTEMAS = {
        'V_2EN1_FAMILIA': (('32',), SEED_CONDITIONS['V_2EN1_FAMILIA'],
                           "tela and tela_2 and not ((tela.is_blackout or tela_2.is_blackout) "
                           "and (tela.is_sheer or tela_2.is_sheer))"),
        'V_SHEER2EN1_REF': (('61',), SEED_CONDITIONS['V_SHEER2EN1_REF'],
                            "tela and tela_2 and not (tela.is_blackout and tela_2.is_sheer)"),
        'V_SEGUNDA_TELA': (('32', '61'), SEED_CONDITIONS['V_SEGUNDA_TELA'], "not tela_2"),
        'V_ENROLLE_SHEER': (('61',), SEED_CONDITIONS['V_ENROLLE_SHEER'],
                            "orientation and orientation != 'frente'"),
        # Matriz 1.7: la restricción del ancho del rollo es de los enrollables.
        'V_ANCHO_ROLLO': (('01', '02', '06', '32', '61'), SEED_CONDITIONS['V_ANCHO_ROLLO'],
                          SEED_CONDITIONS['V_ANCHO_ROLLO']),
    }
    # Reglas del cálculo interno que se pueden escribir completas.
    SEED_17 = {
        'V_ALTO_3X_ANCHO': ("ancho and alto > ancho * 3 and estructura['tubo']",
                            'W10005: La persiana tiene un alto mayor a 3 veces su ancho.'),
        'V_CORTE_ATRAVESADO': (
            "tela and tela.pierceable_type in ('si', 'si_cliente') and ancho_rollo "
            "and ancho > ancho_rollo and not linea.acepta_atravesado",
            'E20017: Con el ancho digitado ({ancho} m) la tela {tela.name} se cortará '
            'atravesada (rollo de {ancho_rollo} m); marque la aceptación del corte '
            'atravesado para continuar.'),
    }

    @api.model
    def _seed_sprint17(self, _ids=None):
        """Sprint 1.7, una sola vez por base: cada validación del portal queda
        con su momento, sus sistemas y su condición escrita. Las de cálculo
        del sistema (secuencias, combinaciones, rollos…) quedan con la
        condición «hallazgo»: dispara cuando el cálculo interno lo encuentra,
        y el funcional puede agregarle condiciones. Lo editado se respeta."""
        Param = self.env['ir.config_parameter'].sudo()
        marca = 'website_quotes_safra.seed_sprint17'
        if Param.get_param(marca):
            return
        Param.set_param(marca, '1')
        rules = self.with_context(active_test=False).search([('code', 'like', 'V_%')])
        Field = self.env['safra.field'].sudo().with_context(active_test=False)
        System = self.env['safra.system'].sudo().with_context(active_test=False)
        for rule in rules:
            vals = {}
            if rule.code in self.REGLAS_PEDIDO:
                vals['momento'] = 'pedido'
            elif rule.code in self.REGLAS_CAMPO:
                field = Field.search([('code', '=', self.REGLAS_CAMPO[rule.code])], limit=1)
                if field:
                    vals.update(momento='campo', trigger_field_id=field.id)
            if rule.code in self.SEED_SISTEMAS:
                codigos, anterior, nueva = self.SEED_SISTEMAS[rule.code]
                systems = System.search([('code', 'in', codigos)])
                if len(systems) == len(codigos) and not rule.system_ids:
                    vals['system_ids'] = [(6, 0, systems.ids)]
                    if (rule.condition_code or '').strip() in ('', anterior):
                        vals['condition_code'] = nueva
            elif not rule.condition_code and rule.code != 'V_REVALIDACION':
                cond, msg = self.SEED_17.get(rule.code, ('hallazgo', None))
                vals['condition_code'] = cond
                if msg and not rule.message:
                    vals['message'] = msg
            if vals:
                rule.write(vals)
    @api.model
    def _seed_sprint17_safra(self, _ids=None):
        """Sprint 1.7, una sola vez por base: las validaciones del archivo de
        Safra como reglas del portal (safra_reglas_17), los cambios a las que
        ya existían, los campos obligatorios y las dependencias de opciones.
        Lo que el funcional ya haya editado se respeta."""
        Param = self.env['ir.config_parameter'].sudo()
        marca = 'website_quotes_safra.seed_sprint17_safra'
        if Param.get_param(marca):
            return
        Param.set_param(marca, '1')
        Rule = self.sudo().with_context(active_test=False)
        Field = self.env['safra.field'].sudo().with_context(active_test=False)
        System = self.env['safra.system'].sudo().with_context(active_test=False)
        Mapping = self.env['safra.system.field'].sudo().with_context(active_test=False)

        def sistemas(codigos):
            """Ids de los sistemas, o None si falta alguno (sin todos los
            sistemas la regla quedaría para todos)."""
            found = System.search([('code', 'in', list(codigos))])
            return found.ids if len(found) == len(set(codigos)) else None

        def campo(code):
            return Field.search([('code', '=', code)], limit=1)

        # 1. Reglas nuevas.
        for r in R17.REGLAS:
            if Rule.search_count([('code', '=', r['code'])]):
                continue
            ids = sistemas(r['systems']) if r['systems'] else []
            trigger = campo(r['trigger_field']) if r['trigger_field'] else Field
            if ids is None or (r['momento'] == 'campo' and not trigger):
                _logger.warning('Sprint 1.7: la regla %s no se creó (faltan sistemas o el campo).',
                                r['code'])
                continue
            Rule.create({
                'code': r['code'], 'name': r['name'], 'funcion_safra': r['funcion_safra'],
                'severity': r['severity'], 'momento': r['momento'],
                'trigger_field_id': trigger.id or False, 'system_ids': [(6, 0, ids)],
                'condition_code': r['condition'], 'message': r['message'],
                'description': r['description'], 'active': r['active'], 'estado': 'portal',
            })

        # 2. Cambios a las reglas que ya existían.
        for code, cambios in R17.CAMBIOS.items():
            rule = Rule.search([('code', '=', code)], limit=1)
            if not rule:
                continue
            del_modulo_cond = {False, '', 'hallazgo', self.SEED_CONDITIONS.get(code)}
            del_modulo_cond |= {v[2] for k, v in self.SEED_SISTEMAS.items() if k == code}
            del_modulo_cond |= {v[0] for k, v in self.SEED_17.items() if k == code}
            del_modulo_msg = {False, '', self.SEED_MESSAGES.get(code)}
            del_modulo_msg |= {v[1] for k, v in self.SEED_17.items() if k == code}
            vals = {}
            for clave, valor in cambios.items():
                if clave == 'condition':
                    if (rule.condition_code or '').strip() in del_modulo_cond:
                        vals['condition_code'] = valor
                elif clave == 'message':
                    if (rule.message or '') in del_modulo_msg:
                        vals['message'] = valor
                elif clave == 'systems':
                    ids = sistemas(valor)
                    if ids is not None:
                        vals['system_ids'] = [(6, 0, ids)]
                else:
                    vals[clave] = valor
            if vals:
                rule.write(vals)

        # 3. Campos obligatorios por sistema.
        for sistema, code in R17.OBLIGATORIOS:
            mapping = Mapping.search([('system_id.code', '=', sistema),
                                      ('field_id.code', '=', code)], limit=1)
            if mapping:
                mapping.write({'required': True, 'active': True})

        # 4. Opciones que dependen de otro campo (si no tienen ya una).
        SysOption = self.env['safra.system.field.option'].sudo()
        for sistema, code, valor, padre, dep in R17.DEPENDENCIAS_OPCION:
            parent = campo(padre)
            if not parent:
                continue
            if sistema:
                opts = SysOption.search([('system_field_id.system_id.code', '=', sistema),
                                         ('system_field_id.field_id.code', '=', code),
                                         ('value', '=', valor)])
            else:
                field = campo(code)
                opts = field.option_ids.filtered(lambda o: o.value == valor) if field else []
            for opt in opts:
                if not opt.depends_field_id and not opt.depends_value:
                    opt.write({'depends_field_id': parent.id, 'depends_value': dep})

        # 5. Fórmulas de opciones que siguen como las dejó el Sprint 1.4/1.5.
        anteriores = dict(Field.AJUSTES_1415_AUTO)
        for code, valor, tipo, formula in R17.FORMULAS_OPCION:
            field = campo(code)
            opt = field.option_ids.filtered(lambda o: o.value == valor)[:1] if field else False
            if not opt:
                continue
            if tipo == 'auto':
                if (opt.auto_formula or '') in ('', (anteriores.get((code, valor)) or ('',))[0]):
                    opt.auto_formula = formula
            elif (opt.formula or '') in ('', Field.AJUSTES_1415_FORMULA.get((code, valor), '')):
                opt.formula = formula

        # 6. Vintage motorizada: el mando derecho se elige solo.
        codigos, valor, formula, aviso = R17.MANDO_VINTAGE
        for opt in SysOption.search([('system_field_id.system_id.code', 'in', list(codigos)),
                                     ('system_field_id.field_id.code', '=', 'mando_position'),
                                     ('value', '=', valor)]):
            if not opt.auto_formula:
                opt.write({'auto_formula': formula, 'aviso': opt.aviso or aviso})

        # 7. Hanas: solo coordinado Blanco (si el sistema no tiene opciones propias).
        sistema, valor, nombre = R17.COORDINADO_HANAS
        mapping = Mapping.search([('system_id.code', '=', sistema),
                                  ('field_id.code', '=', 'coordinado')], limit=1)
        if mapping and not SysOption.search_count([('system_field_id', '=', mapping.id)]):
            SysOption.create({'system_field_id': mapping.id, 'value': valor, 'name': nombre})

        # 8. Panel Duo: ancho propio de cada telo.
        sistema, minimo, maximo = R17.TELO_PANEL_DUO
        duo = System.search([('code', '=', sistema)], limit=1)
        if duo and not duo.panel_telo_min and not duo.panel_telo_max:
            duo.write({'panel_telo_min': minimo, 'panel_telo_max': maximo})

    @api.model
    def _ajuste_anadidos_17(self, _ids=None):
        """Fila 142 (reunión 17-09), una sola vez por base: la tela marcada
        «Añadido» se fabrica añadida (alerta OB0003) en vez de bloquear por
        el ancho del rollo, y no puede pasar del máximo de añadidos. Solo se
        cambian las condiciones que siguen como las dejó el módulo."""
        Param = self.env['ir.config_parameter'].sudo()
        marca = 'website_quotes_safra.ajuste_anadidos_17'
        if Param.get_param(marca):
            return
        Param.set_param(marca, '1')
        Rule = self.sudo().with_context(active_test=False)
        for code, (anteriores, nueva, mensaje) in R17.ANADIDOS.items():
            rule = Rule.search([('code', '=', code)], limit=1)
            if rule and (rule.condition_code or '').strip() in anteriores + ('',):
                vals = {'condition_code': nueva}
                if mensaje:
                    vals['message'] = mensaje
                rule.write(vals)
        r = R17.ANADIDO_MAXIMO
        if not Rule.search_count([('code', '=', r['code'])]):
            systems = self.env['safra.system'].sudo().with_context(active_test=False).search(
                [('code', 'in', list(r['systems']))])
            Rule.create({
                'code': r['code'], 'name': r['name'], 'funcion_safra': r['funcion_safra'],
                'severity': r['severity'], 'momento': r['momento'],
                'system_ids': [(6, 0, systems.ids)], 'condition_code': r['condition'],
                'message': r['message'], 'description': r['description'],
                'active': r['active'], 'estado': 'portal',
            })

    @api.model
    def _ajuste_corte_tela(self, _ids=None):
        """Archivos de Safra «Tipos de corte tela» (26-oct), una sola vez por
        base: las reglas del corte de la tela y las opciones del Dobladillo
        o Bajo falso pasan a usar el tipo de corte de la línea (tipo_corte),
        y Onda Moderna y Pliegue Francés toman el factor de confección del
        Excel. Solo se cambia lo que sigue como lo dejó el módulo."""
        Param = self.env['ir.config_parameter'].sudo()
        marca = 'website_quotes_safra.ajuste_corte_tela'
        if Param.get_param(marca):
            return
        Param.set_param(marca, '1')
        Rule = self.sudo().with_context(active_test=False)
        System = self.env['safra.system'].sudo().with_context(active_test=False)
        for code, (nombre, conds, cond, msgs, msg, sis_ant, sis) in R17.CORTE_TELA.items():
            rule = Rule.search([('code', '=', code)], limit=1)
            if not rule or (rule.condition_code or '').strip() not in conds + ('',):
                continue
            vals = {'condition_code': cond, 'name': nombre}
            if (rule.message or '') in msgs + ('',):
                vals['message'] = msg
            if set(rule.system_ids.mapped('code')) in (set(sis_ant), set()):
                vals['system_ids'] = [(6, 0, System.search([('code', 'in', list(sis))]).ids)]
            rule.write(vals)
        Field = self.env['safra.field'].sudo().with_context(active_test=False)
        campo = Field.search([('code', '=', 'bajofalso')], limit=1)
        anteriores = {v: {f.strip()} for v, _n, f in Field.SPRINT15_DOBLADILLO}
        for valor, (formula, auto, aviso) in R17.DOBLADILLO_CORTE.items():
            opt = campo.option_ids.filtered(lambda o: o.value == valor)[:1] if campo else False
            if not opt or (opt.formula or '').strip() not in anteriores.get(valor, set()) | {''}:
                continue
            vals = {'formula': formula}
            if auto and not opt.auto_formula:
                vals['auto_formula'] = auto
            if aviso and (not opt.aviso or opt.aviso == Field.AVISO_PANOS):
                vals['aviso'] = aviso
            opt.write(vals)
        for code, factor in R17.FACTOR_CONFECCION.items():
            System.search([('code', '=', code), ('factor_confeccion', 'in', [False, 0])]).factor_confeccion = factor

    @api.model
    def _seed_catalogo_17(self, _ids=None):
        """Sprint 1.7, una sola vez por base: un solo catálogo. Cada función
        del archivo de Safra queda con su estado (cubierta, pendiente,
        pendiente de Safra o inactivada), las reglas del portal que la
        cubren y una nota; cada regla del portal, con su función."""
        Param = self.env['ir.config_parameter'].sudo()
        marca = 'website_quotes_safra.seed_catalogo_17'
        if Param.get_param(marca):
            return
        Param.set_param(marca, '1')
        Rule = self.sudo().with_context(active_test=False)

        def reglas(codigos):
            return [(6, 0, Rule.search([('code', 'in', list(codigos))]).ids)]

        for code, (nombre, funcion, estado, codigos, nota) in R17.CATALOGO.items():
            rec = Rule.search([('code', '=', code)], limit=1)
            if not rec:
                continue
            rec.write({
                'name': nombre, 'funcion_safra': funcion, 'estado': estado,
                'regla_ids': reglas(codigos), 'active': False,
                'description': '%s\n%s' % (rec.description, nota) if rec.description else nota,
            })
        for code, nombre, funcion, seccion, estado, codigos, nota in R17.CATALOGO_NUEVOS:
            if not Rule.search_count([('code', '=', code)]):
                Rule.create({'code': code, 'name': nombre, 'funcion_safra': funcion,
                             'seccion': seccion, 'estado': estado, 'severity': 'error',
                             'active': False, 'regla_ids': reglas(codigos), 'description': nota})
        for code, funcion in R17.FUNCION_REGLA.items():
            Rule.search([('code', '=', code), ('funcion_safra', '=', False)]).funcion_safra = funcion

    # Revisión 27-oct: reglas que el archivo de Safra marca «Mantener» o
    # «Actualizar» y estaban apagadas. Cadena extra (no debe avisar) y
    # Estampado fuera de servicio (interruptor) siguen apagadas.
    ACTIVAR_SEGUN_ARCHIVO = {
        'V_TELAS_REPETIDAS': (
            'E13095-65',
            'La regla existe pero está inactiva porque en la reunión del 24-sep Safra '
            'pidió quitarla. Safra debe confirmar si se reactiva.',
            'Activa desde el 27-oct: el archivo de Safra la marca «Mantener» (en la '
            'reunión del 24-sep se había pedido quitarla).'),
    }

    @api.model
    def _ajuste_ancho_impresion(self, _ids=None):
        """Revisión 27-oct, una sola vez por base: el ancho máximo de Sheer
        Elegance sale de Ajustes (ancho_max_impresion) en vez de estar
        escrito en la condición. Solo si la condición sigue como se sembró."""
        Param = self.env['ir.config_parameter'].sudo()
        marca = 'website_quotes_safra.ajuste_ancho_impresion'
        if Param.get_param(marca):
            return
        Param.set_param(marca, '1')
        regla = self.sudo().with_context(active_test=False).search(
            [('code', '=', 'V_ESTAMPADO_SHEER_ELEGANCE')], limit=1)
        if regla and (regla.condition_code or '').strip() == 'maximo = 2.5\nresult = design_print and ancho > maximo':
            regla.condition_code = 'maximo = ancho_max_impresion\nresult = design_print and ancho > maximo'

    @api.model
    def _activar_segun_archivo_safra(self, _ids=None):
        """Una sola vez por base: activa esas reglas y deja su función del
        catálogo como cubierta. Las funciones del catálogo que quedaron como
        «Activa en el portal» sin condición (no revisan nada) vuelven al
        catálogo con su estado."""
        Param = self.env['ir.config_parameter'].sudo()
        marca = 'website_quotes_safra.activar_segun_archivo_27oct'
        if Param.get_param(marca):
            return
        Param.set_param(marca, '1')
        Rule = self.sudo().with_context(active_test=False)
        for code, (ficha_code, nota_vieja, nota_nueva) in self.ACTIVAR_SEGUN_ARCHIVO.items():
            Rule.search([('code', '=', code)]).active = True
            ficha = Rule.search([('code', '=', ficha_code), ('estado', '=', 'pendiente_safra')])
            if ficha:
                ficha.write({'estado': 'cubierta',
                             'description': (ficha.description or '').replace(nota_vieja, nota_nueva)})
        for ficha in Rule.search([('code', 'in', list(R17.CATALOGO)), ('estado', '=', 'portal'),
                                  ('condition_code', '=', False)]):
            ficha.write({'estado': R17.CATALOGO[ficha.code][2], 'active': False})

    # Revisión 27-oct: el código repetido decía solo «debe ser único»; con
    # el catálogo en su propio menú, la otra regla ni se veía al buscarla.
    @api.model_create_multi
    def create(self, vals_list):
        self._revisar_codigo_repetido([vals.get('code') for vals in vals_list])
        # Las reglas del programa (V_…) nacen con su clave interna.
        for vals in vals_list:
            code = vals.get('code') or ''
            if not vals.get('clave') and code.startswith('V_') and not self._por_clave([code]):
                vals['clave'] = code
            # Revisión 3-nov: las crea el módulo al instalarse o actualizarse
            # (usuario del sistema); las de pantalla o del asistente de IA
            # quedan con el usuario que las crea, aunque sea con sudo.
            vals.setdefault('del_modulo', self.env.uid == SUPERUSER_ID)
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('code'):
            self._revisar_codigo_repetido([vals['code']])
        if 'condition_code' in vals:
            vals = dict(vals, ultimo_error=False, ultimo_error_fecha=False)
        return super().write(vals)

    def unlink(self):
        """Revisión 3-nov: las reglas del módulo no se borran desde la
        pantalla (sí el programa, con sudo)."""
        if not self.env.su:
            del_modulo = self.filtered('del_modulo')
            if del_modulo:
                raise UserError(
                    'No se pueden borrar reglas del módulo (%s): el cotizador las usa y al '
                    'actualizar no se vuelven a crear. Para que no se revisen, desmarque Activa '
                    '(o Acción › Archivar).' % ', '.join(del_modulo.mapped('code')))
        return super().unlink()

    @api.model
    def _ajuste_reglas_del_modulo(self, _ids=None):
        """Revisión 3-nov: marca como «Regla del módulo» las que creó el
        módulo antes de existir la marca (usuario del sistema o con XML id)."""
        Rule = self.sudo().with_context(active_test=False)
        ids = set(Rule.search([('create_uid', '=', SUPERUSER_ID), ('del_modulo', '=', False)]).ids)
        ids |= set(self.env['ir.model.data'].sudo().search(
            [('model', '=', self._name), ('module', '=', 'website_quotes_safra')]).mapped('res_id'))
        Rule.browse(ids).exists().filtered(lambda r: not r.del_modulo).write({'del_modulo': True})

    def _registrar_error(self, error):
        """Revisión 3-nov: guarda el error de la condición. Solo escribe si
        cambió (el portal revisa las reglas en cada cambio de campo)."""
        self.ensure_one()
        error = (error or '')[:500]
        if not error or self.ultimo_error == error:
            return
        try:
            with self.env.cr.savepoint():
                self.sudo().write({'ultimo_error': error, 'ultimo_error_fecha': fields.Datetime.now()})
        except Exception:  # noqa: BLE001 — no registrar el error no debe romper el portal
            _logger.warning('Validación %s: no se pudo guardar el error de la condición', self.code,
                            exc_info=True)

    def action_limpiar_error(self):
        self.sudo().write({'ultimo_error': False, 'ultimo_error_fecha': False})

    def _revisar_codigo_repetido(self, codigos):
        Rule = self.sudo().with_context(active_test=False)
        for code in filter(None, codigos):
            otra = Rule.search([('code', '=', code), ('id', 'not in', self.ids)], limit=1)
            if not otra:
                continue
            donde = ('en Validaciones' if otra.estado == 'portal'
                     else 'en el menú Catálogo archivo Safra')
            raise ValidationError(
                'El código «%s» ya lo tiene «%s» (%s%s). El código es el identificador '
                'interno de la regla y no se repite: use uno propio, por ejemplo '
                'R_ANCHO_MOTOR. Si es un código de Safra (como E13095), póngalo al inicio '
                'del Mensaje.' % (code, otra.name, donde, '' if otra.active else ', inactiva'))

    @api.constrains('momento', 'trigger_field_id')
    def _check_momento(self):
        for rule in self:
            if rule.momento == 'campo' and not rule.trigger_field_id:
                raise ValidationError(
                    'La regla %s se revisa «Al digitar un campo»: elija el campo '
                    'que la dispara.' % rule.code)

    @api.constrains('condition_code', 'message')
    def _check_condition_code(self):
        for rule in self:
            error = rule._revisar_condicion()
            if error:
                raise ValidationError('Regla %s: %s' % (rule.code, error))

    def _revisar_condicion(self):
        """Revisión al guardar: escritura de la condición, variables que no
        existen y comodines del mensaje que la condición no conoce. Se
        prueba con una línea vacía (todo en 0 / vacío); los demás errores
        dependen de los datos y se ven con «Probar»."""
        self.ensure_one()
        codigo = (self.condition_code or '').strip()
        if not codigo:
            return False
        if test_python_expr(codigo, mode='eval'):
            error = test_python_expr(codigo, mode='exec')
            if error:
                return _mensaje_amigable(error)
            if not _ASIGNA_RESULT.search(codigo):
                return ('Una condición de varias líneas debe terminar asignando '
                        '«result» (p. ej. result = ancho > 3).')
        ctx = self.env['safra.quote.line'].sudo()._contexto_ejemplo()
        try:
            _valor, variables = evaluar_formula(codigo, ctx)
        except Exception as e:  # noqa: BLE001 — se traduce para el funcional
            texto = str(e.args[0] if e.args else e)
            if re.search(r"name '\w+' is not defined", texto) or 'SyntaxError' in texto:
                return _mensaje_amigable(texto.split(' while evaluating')[0])
            variables = ctx
        if self.message and 'hallazgo' not in codigo:
            for _txt, nombre, _spec, _conv in Formatter().parse(self.message):
                raiz = re.split(r'[.\[]', nombre or '', maxsplit=1)[0]
                if raiz and not raiz.isdigit() and raiz not in variables:
                    return ('El mensaje usa {%s}, pero «%s» no es una variable de la '
                            'condición. Revise la lista de variables de la ayuda.'
                            % (nombre, raiz))
        return False

    def _evaluar(self, ctx):
        """(dispara, variables) de la condición con el contexto de una línea."""
        self.ensure_one()
        valor, variables = evaluar_formula(self.condition_code, ctx)
        return bool(valor), variables

    def _mensaje(self, variables, hallazgo=None):
        """Mensaje de la regla con los comodines reemplazados. Sin mensaje
        propio se usa el del cálculo interno (ya armado) o el nombre."""
        self.ensure_one()
        if not self.message:
            if hallazgo:
                return hallazgo['message']
            return '%s: %s' % (self.code, self.name)
        # Los datos del hallazgo completan las variables sin reemplazarlas
        # (p. ej. el hallazgo trae «tela» como texto y la condición como registro).
        fmt = dict((hallazgo or {}).get('fmt') or {})
        fmt.update(variables)
        # Un dato del maestro sin digitar sale como «sin digitar», no «False».
        for clave in ((variables.get('_sin_digitar') or {}).get('variables') or {}):
            nombre, _sep, llave = clave.partition('[')
            if not llave and nombre in fmt:
                fmt[nombre] = SinDigitar()
            elif llave and isinstance(fmt.get(nombre), dict):
                fmt[nombre] = dict(fmt[nombre], **{llave[1:-2]: SinDigitar()})
        try:
            return self.message.format(**fmt)
        except (KeyError, IndexError, ValueError, AttributeError, TypeError):
            return self.message

    def aplica_en(self, momento, campo=None, sistema=None):
        """Motivo por el que la regla NO se revisa en este momento/sistema
        (o False si sí aplica)."""
        self.ensure_one()
        if momento == 'campo':
            if self.momento != 'campo' or (self.trigger_field_id.code or '') != campo:
                return 'momento'
        elif momento == 'secuencia':
            # En el configurador solo las reglas de ese momento (las demás
            # salen al guardar la línea o al finalizar).
            if self.momento != 'secuencia':
                return 'momento'
        elif NIVEL_MOMENTO[self.momento] > NIVEL_MOMENTO[momento]:
            return 'momento'
        if self.system_ids and sistema is not None \
                and sistema not in self.system_ids.mapped('code'):
            return 'sistema'
        return False

    @api.model
    def _campos_disparo(self, system):
        """Códigos de los campos con reglas activas «Al digitar un campo»
        que aplican al sistema."""
        reglas = self.search([('momento', '=', 'campo'), ('trigger_field_id', '!=', False)])
        return sorted({r.trigger_field_id.code for r in reglas
                       if not r.system_ids or system in r.system_ids})

    def action_probar(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Probar regla %s' % self.code,
            'res_model': 'safra.validation.rule.test',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_rule_id': self.id},
        }

    def action_prompt_ia(self):
        """Revisión 27-oct: instrucción para escribir la condición con la IA
        que use Safra (ver safra.validation.rule.prompt)."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Instrucción para IA · %s' % self.code,
            'res_model': 'safra.validation.rule.prompt',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_rule_id': self.id,
                        'default_system_ids': [(6, 0, self.system_ids.ids)],
                        'default_solicitud': self.solicitud_ia or False},
        }


class SafraValidationRuleTest(models.TransientModel):
    """Sprint 1.7: prueba una regla contra una cotización guardada, línea
    por línea, sin cambiar nada (también una regla inactiva, antes de
    activarla)."""
    _name = 'safra.validation.rule.test'
    _description = 'Probar validación del cotizador'

    rule_id = fields.Many2one('safra.validation.rule', string='Regla', required=True,
                              ondelete='cascade')
    quote_id = fields.Many2one('safra.quote', string='Cotización', required=True,
                               ondelete='cascade')
    momento = fields.Selection(MOMENTOS, string='Probar como', default='pedido', required=True,
                               help='«Al finalizar el pedido» revisa todas las reglas; '
                                    'los momentos anteriores dejan por fuera las que '
                                    'se revisan después.')
    resultado = fields.Html(string='Resultado', readonly=True, sanitize=False)

    def action_probar(self):
        self.ensure_one()
        Line = self.env['safra.quote.line'].sudo()
        lines = self.quote_id.line_ids.sorted('sequence')
        filas = Line._probar_regla(
            self.rule_id, [l.copy_data()[0] for l in lines],
            pedido=self.quote_id._datos_pedido(), momento=self.momento)
        colores = {'error': 'danger', 'warning': 'warning', 'info': 'info'}
        cuerpo = Markup()
        for fila in filas:
            if fila.get('error'):
                estado = Markup('<span class="text-danger">Error en la condición: %s</span>') % fila['error']
            elif fila.get('motivo') == 'sistema':
                estado = Markup('<span class="text-muted">No aplica: el sistema no está en la regla</span>')
            elif fila.get('motivo') == 'momento':
                estado = Markup('<span class="text-muted">No se revisa en este momento</span>')
            elif fila.get('mensajes'):
                estado = Markup('<br/>').join(
                    Markup('<span class="badge text-bg-%s">Dispara</span> %s')
                    % (colores.get(fila['severity'], 'secondary'), m) for m in fila['mensajes'])
            else:
                estado = Markup('<span class="text-success">No dispara</span>')
            if fila.get('sin_digitar'):
                # La condición usó un dato del maestro vacío.
                estado += Markup('<br/><span class="text-warning">Usa datos sin digitar: %s. '
                                 'El resultado no es confiable hasta que se llenen.</span>') % (
                    ', '.join(fila['sin_digitar']))
            cuerpo += Markup('<tr><td>%s</td><td>%s</td><td>%s</td></tr>') % (
                fila['line'] or 'Pedido', fila.get('descripcion') or '', estado)
        if not filas:
            cuerpo = Markup('<tr><td colspan="3">La cotización no tiene líneas.</td></tr>')
        self.resultado = Markup(
            '<table class="table table-sm table-bordered"><thead><tr><th>Línea</th>'
            '<th>Persiana</th><th>Resultado</th></tr></thead><tbody>%s</tbody></table>') % cuerpo
        return {
            'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': self.id,
            'view_mode': 'form', 'target': 'new', 'name': 'Probar regla %s' % self.rule_id.code,
        }
