# -*- coding: utf-8 -*-
import base64

from odoo.tests import TransactionCase
from odoo.tools.misc import file_open


def excel_safra():
    """El Excel de combinaciones de Safra que trae el módulo."""
    with file_open('website_quotes_safra/data/panel_track_best_fit.xlsx', 'rb') as archivo:
        return archivo.read()


# Hoja «Matriz 2-12» del Excel de Safra (Panel_Track_Best_Fit_Odoo_CORREGIDO):
# (total telos, apertura, riel, Riel Velcrado). Es lo que da su fórmula.
COMBINACIONES_SAFRA = [
    (4, 'derecha', 4, False), (4, 'izquierda', 4, False), (4, 'centro', 4, False),
    (5, 'derecha', 5, False), (5, 'izquierda', 5, False),
    (6, 'extremos', 4, False), (6, 'derecha', 6, False), (6, 'izquierda', 6, False),
    (6, 'centro', 6, False),
    (7, 'derecha', 6, True), (7, 'izquierda', 6, True),
    (8, 'extremos', 5, False),
    (10, 'extremos', 6, False),
    (12, 'extremos', 6, True),
]

# Reglas que nacen como advertencia (las demás bloquean).
ADVERTENCIAS = {'V_ALTO_3X_ANCHO', 'V_ALINEADO_ALTURA', 'V_ROLLO_DISPONIBLE',
                'V_ROLLO_ALINEADO', 'V_DATO_SIN_DIGITAR'}

CAMPOS_ENROLLABLE = [
    'width', 'height', 'quantity', 'location', 'fabric_id', 'color_id',
    'aligned', 'same_header', 'sequence_name', 'has_motor', 'motor',
    'control', 'control_channel', 'interruptor_rf', 'unificacion_mando',
]
CAMPOS_PANEL = [
    'width', 'height', 'quantity', 'location', 'fabric_id', 'color_id',
    'aligned', 'quantity_lamas', 'tamano_traslape', 'apertura', 'riel_tipo',
]


class SafraCommon(TransactionCase):
    """Datos propios para probar el cotizador sin depender de lo que tenga
    cada base: sistemas, referencias, fórmulas, estructura y controles se
    crean aquí. De lo que siembra el módulo solo se usan los campos del
    catálogo (por su código técnico) y los registros de Validaciones, que
    se dejan como en una instalación nueva.

    Todo corre dentro de la transacción de la prueba: no queda nada
    escrito en la base."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.Line = cls.env['safra.quote.line'].sudo()
        cls._validaciones_de_fabrica()
        cls._parametros_panel()

        cls.enrollable = cls._sistema('ZT01', 'PRUEBA ENROLLABLE', CAMPOS_ENROLLABLE,
                                      (0.30, 3.00, 0.30, 4.00))
        cls.panel = cls._sistema('ZT11', 'PRUEBA PANEL', CAMPOS_PANEL,
                                 (0.60, 8.00, 0.30, 4.00))
        cls._rieles_panel()
        cls._formula_panel()
        cls._estructura()

        Fabric = cls.env['safra.fabric']
        sistemas = [(6, 0, (cls.enrollable | cls.panel).ids)]
        # Tela no atravesable con rollo de 2,50 m.
        # Peso y grosor digitados en 0 (sin digitar, las fórmulas del tubo
        # avisan «Falta digitar»; eso se prueba en test_sin_digitar).
        cls.tela = Fabric.create({'code': 'ZT-TELA', 'name': 'Tela Prueba',
                                  'system_ids': sistemas, 'pierceable_type': 'no',
                                  'peso_gm2': 0, 'grosor_mm': 0})
        cls.blanco = cls._color(cls.tela, 'ZTBLA', 'Blanco Prueba', ancho_rollo=2.5)
        cls.gris = cls._color(cls.tela, 'ZTGRI', 'Gris Prueba', ancho_rollo=2.5)
        # Tela pesada para las fórmulas de alto y peso máximo.
        cls.tela_pesada = Fabric.create({'code': 'ZT-PESADA', 'name': 'Tela Pesada',
                                         'system_ids': sistemas, 'peso_gm2': 300,
                                         'grosor_mm': 0.5, 'pierceable_type': 'si'})
        cls.pesada = cls._color(cls.tela_pesada, 'ZTPES', 'Pesada Prueba')
        # Tela de la familia Sheer (franjas).
        cls.tela_sheer = Fabric.create({'code': 'ZT-SHEER', 'name': 'Sheer Prueba',
                                        'system_ids': sistemas, 'is_sheer': True,
                                        'peso_gm2': 0, 'grosor_mm': 0})
        cls.sheer = cls._color(cls.tela_sheer, 'ZTSHE', 'Sheer Blanco')
        cls._controles()

    # --- Datos ---------------------------------------------------------

    @classmethod
    def _validaciones_de_fabrica(cls):
        """Las reglas pueden estar editadas en cada base (apagadas, otra
        severidad, otra condición). Se dejan como al instalar."""
        Rule = cls.env['safra.validation.rule'].sudo().with_context(active_test=False)
        for rule in Rule.search([]):
            clave = rule._clave_programa()
            if clave.startswith('V_'):
                # Sprint 1.7: sin sistemas (los de prueba son otros) y con el
                # momento en que la regla salía antes (línea o pedido).
                rule.write({
                    'active': True,
                    'condition_code': Rule.SEED_CONDITIONS.get(clave, False),
                    'message': Rule.SEED_MESSAGES.get(clave, False),
                    'severity': 'warning' if clave in ADVERTENCIAS else 'error',
                    'momento': 'pedido' if clave in Rule.REGLAS_PEDIDO else 'linea',
                    'trigger_field_id': False,
                    'system_ids': [(5, 0, 0)],
                })
            elif rule.condition_code:
                # Reglas creadas por el funcional: fuera de las pruebas.
                rule.active = False

    @classmethod
    def _parametros_panel(cls):
        Param = cls.env['ir.config_parameter'].sudo()
        Param.set_param('safra.panel.rieles', '4,5,6')
        Param.set_param('safra.panel.ancho_telo_min', '0.35')
        Param.set_param('safra.panel.ancho_telo_max', '0.95')
        Param.set_param('safra.panel.ancho_max', '8.0')

    @classmethod
    def _campo(cls, code):
        field = cls.env['safra.field'].sudo().with_context(active_test=False).search(
            [('code', '=', code)], limit=1)
        assert field, 'El catálogo no tiene el campo %s' % code
        return field

    @classmethod
    def _sistema(cls, code, name, campos, ficha):
        wmin, wmax, hmin, hmax = ficha
        system = cls.env['safra.system'].create({
            'code': code, 'name': name,
            'tech_width_min': wmin, 'tech_width_max': wmax,
            'tech_height_min': hmin, 'tech_height_max': hmax,
        })
        cls.env['safra.system.field'].create([
            {'system_id': system.id, 'field_id': cls._campo(c).id, 'sequence': (i + 1) * 10}
            for i, c in enumerate(campos)])
        return system

    @classmethod
    def _color(cls, tela, code, nombre, ancho_rollo=0.0, **producto):
        product = cls.env['product.template'].create(dict({
            'name': nombre, 'safra_code': code, 'safra_is_color': True,
            'safra_u_ancho': ancho_rollo}, **producto))
        return cls.env['safra.fabric.color'].create(
            {'fabric_id': tela.id, 'product_tmpl_id': product.id})

    @classmethod
    def _rieles_panel(cls):
        mapping = cls.env['safra.system.field'].search([
            ('system_id', '=', cls.panel.id), ('field_id.code', '=', 'riel_tipo')])
        opciones = [('auto', 'Auto'), ('r4', '4 Vías'), ('r5', '5 Vías'),
                    ('r6', '6 Vías'), ('rv', 'Riel Velcrado')]
        cls.env['safra.system.field.option'].create([
            {'system_field_id': mapping.id, 'value': v, 'name': n} for v, n in opciones])

    @classmethod
    def _formula_panel(cls):
        """La regla de combinaciones con el Excel de Safra
        (Panel_Track_Best_Fit_Odoo_CORREGIDO, el mismo de la carga inicial)."""
        cls.combo_rule = cls.env['safra.panel.combo.rule'].create({
            'system_ids': [(6, 0, cls.panel.ids)],
            'excel_archivo': base64.b64encode(excel_safra()),
            'excel_nombre': 'Panel_Track_Best_Fit_Odoo_CORREGIDO.xlsx',
        })

    # Constantes del tubo digitadas en 0 (sin digitar, las fórmulas del tubo
    # avisan «Falta digitar»; eso se prueba en test_sin_digitar).
    _SIN_CONSTANTES = {'espacio_eje_techo': 0, 'diametro_tubo': 0, 'carga_maxima': 0}

    @classmethod
    def _estructura(cls):
        """Tabla de estructura del enrollable de prueba: R8 manual y motor,
        R16 y R24 para ambos, y una regla R8 propia del cabezal redondo."""
        Rule = cls.env['safra.structure.rule']
        sistemas = [(6, 0, cls.enrollable.ids)]
        cls.r8_manual = Rule.create({
            'system_ids': sistemas, 'drive_type': 'manual', 'sequence': 1,
            'width_from': 0.30, 'width_to': 2.00, 'tubo': 'R8', 'mecanismo': 'R8SL',
            'soporte': 'S8', 'terminal': 'T8', 'aumento_tela': 0.25,
            'espacio_eje_techo': 60, 'diametro_tubo': 40, 'carga_maxima': 2000})
        cls.r8_motor = Rule.create({
            'system_ids': sistemas, 'drive_type': 'motor', 'sequence': 2,
            'width_from': 0.30, 'width_to': 2.00, 'tubo': 'R8', 'mecanismo': 'R8M',
            'aumento_tela': 0.25, 'espacio_eje_techo': 60, 'diametro_tubo': 40,
            'carga_maxima': 10000})
        cls.r8_redondo = Rule.create({
            'system_ids': sistemas, 'drive_type': 'manual', 'cabezal_type': 'redondo',
            'sequence': 3, 'width_from': 0.30, 'width_to': 2.00, 'tubo': 'R8',
            'mecanismo': 'R8SL-RED', **cls._SIN_CONSTANTES})
        cls.r16 = Rule.create({
            'system_ids': sistemas, 'drive_type': 'any', 'sequence': 4,
            'width_from': 2.001, 'width_to': 2.60, 'tubo': 'R16', 'mecanismo': 'R16SL',
            'aumento_tela': 0.30, **cls._SIN_CONSTANTES})
        cls.r24 = Rule.create({
            'system_ids': sistemas, 'drive_type': 'any', 'sequence': 5,
            'width_from': 2.601, 'width_to': 3.00, 'tubo': 'R24', 'mecanismo': 'R24SL',
            **cls._SIN_CONSTANTES})

    @classmethod
    def _controles(cls):
        """Referencia de controles (reunión 13-oct): el mismo control como
        monocanal y como multicanal de 5, más la línea «Sin control»."""
        categoria = cls.env['safra.product.option'].create({
            'name': 'Controles prueba', 'type': 'ref_categoria', 'es_control': True})
        ref = cls.env['safra.fabric'].create({
            'code': 'ZT-CTL', 'name': 'Controles Prueba', 'category_id': categoria.id})
        producto = cls.env['product.template'].create({
            'name': 'Control Prueba', 'safra_code': 'ZTCTL', 'safra_is_color': True})
        Color = cls.env['safra.fabric.color']
        cls.ctl_mono = Color.create({'fabric_id': ref.id, 'product_tmpl_id': producto.id,
                                     'canales': 1, 'etiqueta': 'Monocanal'})
        cls.ctl_multi = Color.create({'fabric_id': ref.id, 'product_tmpl_id': producto.id,
                                      'canales': 5, 'etiqueta': 'Multicanal 5'})
        cls.ctl_sin = Color.create({'fabric_id': ref.id, 'code': 'ZT-SIN',
                                    'name': 'Sin control'})

    # --- Ayudas para las pruebas ----------------------------------------

    def linea(self, **vals):
        """Persiana válida del enrollable de prueba; los argumentos cambian
        o agregan valores (mismos nombres de safra.quote.line)."""
        base = {'system_id': self.enrollable.id, 'fabric_id': self.tela.id,
                'color_id': self.blanco.id, 'width': 1.5, 'height': 1.8,
                'quantity': 1, 'location': 'Sala'}
        base.update(vals)
        return base

    def linea_panel(self, lamas, apertura=None, riel=None, ancho=2.4, **vals):
        attrs = {'quantity_lamas': lamas, 'tamano_traslape': 0.08}
        if apertura:
            attrs['apertura'] = apertura
        if riel:
            attrs['riel_tipo'] = riel
        attrs.update(vals.pop('attribute_values', {}))
        base = {'system_id': self.panel.id, 'fabric_id': self.tela.id,
                'color_id': self.blanco.id, 'width': ancho, 'height': 2.0,
                'quantity': 1, 'location': 'Sala', 'attribute_values': attrs}
        base.update(vals)
        return base

    def validar(self, lineas, cross=True):
        """Hallazgos del pedido, sin el código de la regla al final del
        mensaje (revisión 28-oct; se prueba aparte) para comparar textos."""
        issues = self.Line._validate_order(lineas, cross=cross)
        for i in issues:
            sufijo = ' [%s]' % (i.get('codigo') or i.get('code'))
            if i['message'].endswith(sufijo):
                i['message'] = i['message'][:-len(sufijo)]
        return issues

    def codigos(self, lineas, cross=True):
        return {i['code'] for i in self.validar(lineas, cross=cross)}

    def mensajes(self, lineas, code, cross=True):
        return [i for i in self.validar(lineas, cross=cross) if i['code'] == code]
