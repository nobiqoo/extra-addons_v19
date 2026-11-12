# -*- coding: utf-8 -*-
from odoo.exceptions import ValidationError
from odoo.tests import tagged

from ..controllers.main import SafraQuoterController
from .common import CAMPOS_ENROLLABLE, SafraCommon
from ..models import safra_reglas_17 as R17


@tagged('post_install', '-at_install', 'safra')
class TestRevisionTubo(SafraCommon):
    """Revisión del cálculo de tubo de Safra (27-oct, archivo «Revision
    Calculo TUBO»): motor obligatorio, unificación entre persianas manuales
    y motorizadas, secuencia al editar y tabla del 2 en 1."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Las fórmulas del tubo como las deja el módulo.
        cls.env['ir.config_parameter'].sudo().search(
            [('key', 'in', list(R17.FORMULAS_TUBO))]).unlink()
        # Tabla como la del enrollable real: el Tubo 40mm solo existe
        # motorizado y tiene el mismo diámetro que el R16.
        cls.mixto = cls._sistema('ZT03', 'PRUEBA MIXTO', CAMPOS_ENROLLABLE,
                                 (0.30, 3.50, 0.30, 4.00))
        Rule = cls.env['safra.structure.rule']
        sistemas = [(6, 0, cls.mixto.ids)]
        cls.m_r8 = Rule.create({'system_ids': sistemas, 'drive_type': 'manual', 'width_from': 0.3,
                                'width_to': 2.0, 'tubo': 'R8', 'mecanismo': 'R8SL', 'diametro_tubo': 32})
        cls.m_r16 = Rule.create({'system_ids': sistemas, 'drive_type': 'manual', 'width_from': 2.01,
                                 'width_to': 3.3, 'tubo': 'R16', 'mecanismo': 'R16SL', 'diametro_tubo': 38})
        cls.m_r24 = Rule.create({'system_ids': sistemas, 'drive_type': 'manual', 'width_from': 3.301,
                                 'width_to': 3.5, 'tubo': 'R24', 'mecanismo': 'R24SL', 'diametro_tubo': 50})
        cls.m_t40 = Rule.create({'system_ids': sistemas, 'drive_type': 'motor', 'width_from': 0.7,
                                 'width_to': 2.5, 'tubo': 'T40', 'mecanismo': 'MOTOR', 'diametro_tubo': 38})
        cls.m_r24_motor = Rule.create({'system_ids': sistemas, 'drive_type': 'motor', 'width_from': 2.501,
                                       'width_to': 3.5, 'tubo': 'R24', 'mecanismo': 'MOTOR', 'diametro_tubo': 50})

    def secuencia(self, *anchos_motor, union='INDEP'):
        """Persianas de la secuencia S1 del sistema mixto: (ancho, con motor),
        unidas por soportes independientes (cada una se calcula sola) o
        dependientes."""
        ultima = len(anchos_motor) - 1
        return [self.linea(system_id=self.mixto.id, width=ancho, has_motor=motor,
                           same_header=True, sequence_name='S1',
                           soporte_izq='MOTOR' if motor else ('MANDO' if n == 0 else union),
                           soporte_der='TERMINAL' if n == ultima else union)
                for n, (ancho, motor) in enumerate(anchos_motor)]

    def unificados(self, lineas):
        self.validar(lineas)
        return [l['attribute_values'].get('unificacion_mando') for l in lineas]

    # --- Error 1: con motor hay que elegir el motor ----------------------

    def test_con_motor_hay_que_elegir_el_motor(self):
        msg = ['E13095: La persiana va con motor: seleccione el Motor.']
        avisos = lambda **v: [i['message'] for i in self.mensajes(
            [self.linea(**v)], 'V_MOTOR_OBLIGATORIO', cross=False)]
        self.assertEqual(avisos(has_motor=True), msg)
        self.assertEqual(avisos(has_motor=True, motor='sin'), msg)
        # «Sin motor» de las opciones propias de los sistemas (valor '0').
        self.assertEqual(avisos(has_motor=True, motor='0'), msg)
        self.assertFalse(avisos(has_motor=True, motor='M1'))
        self.assertFalse(avisos())

    def test_sin_campo_motor_no_se_revisa(self):
        self.assertFalse(self.mensajes([self.linea_panel(4, has_motor=True)], 'V_MOTOR_OBLIGATORIO'))

    # --- Error 2: unificación entre manuales y motorizadas ---------------

    def test_orden_de_la_secuencia(self):
        self.assertEqual(self.env['safra.structure.rule'].tubos_secuencia(self.mixto),
                         ['R8', 'R16', 'T40', 'R24'])

    def test_manual_toma_el_tubo_del_motor(self):
        """La persiana manual de una secuencia con motor queda con el tubo
        motorizado y su ficha sale de esa regla (mecanismo MOTOR)."""
        lineas = self.secuencia((1.5, True), (1.5, False))
        self.assertEqual(self.unificados(lineas), [None, 'T40'])
        manual = self.Line.new(lineas[1])
        self.assertEqual(manual._estructura_linea()[1], self.m_t40)
        self.assertEqual(manual._estructura_linea()[1]._mechanism_line(),
                         'Tubo: T40 - Mecanismo: MOTOR - Cabezal: No aplica')

    def test_mismo_diametro_va_el_motorizado(self):
        """Manual en R16 y motor en Tubo 40mm (mismo diámetro): el motor va
        dentro del tubo, así que la secuencia queda en el motorizado."""
        self.assertEqual(self.unificados(self.secuencia((1.5, True), (3.0, False))),
                         [None, 'T40'])

    def test_manual_mayor_pasa_al_motorizado_de_su_tamano(self):
        """Manual en R24 (más grande que el Tubo 40mm): el motor sube al R24
        de la tabla motorizada y la manual se queda en su R24."""
        lineas = self.secuencia((1.5, True), (3.4, False))
        self.assertEqual(self.unificados(lineas), ['R24', None])
        motor = self.Line.new(lineas[0])
        self.assertEqual(motor._estructura_linea()[1], self.m_r24_motor)

    def test_sin_motor_sigue_igual(self):
        self.assertEqual(self.unificados(self.secuencia((1.5, False), (3.0, False))),
                         ['R16', None])

    def test_persiana_sola_no_toma_tubos_del_motor(self):
        """Fuera de la secuencia, la Unificación Mando de una manual no
        acepta un tubo que solo es motorizado y más pequeño que el suyo."""
        Rule = self.env['safra.structure.rule']
        self.assertEqual(Rule.resolve(self.mixto, 3.4, unificacion='T40'),
                         (self.m_r24, self.m_r24))

    def test_tramo_dependiente_con_motor_usa_la_tabla_motorizada(self):
        """Motor de 1,00 m y manual de 1,60 m unidas por soportes
        dependientes: un tramo de 2,60 m que mueve el motor. Las dos van con
        el R24 de la tabla motorizada (mecanismo MOTOR), aunque el R24 también
        está en la tabla manual."""
        lineas = self.secuencia((1.0, True), (1.6, False), union='DEP')
        self.assertEqual(self.unificados(lineas), ['R24', 'R24'])
        self.assertTrue(lineas[1]['attribute_values'].get('unificacion_motor'))
        self.assertEqual(self.Line.new(lineas[1])._estructura_linea()[1], self.m_r24_motor)
        # Con soportes independientes la manual se queda con su tabla.
        sueltas = self.secuencia((1.0, True), (3.4, False))
        self.unificados(sueltas)
        self.assertFalse(sueltas[1]['attribute_values'].get('unificacion_motor'))
        self.assertEqual(self.Line.new(sueltas[1])._estructura_linea()[1], self.m_r24)

    # --- Error 4: la secuencia no se pierde al editar --------------------

    def test_editar_trae_los_soportes(self):
        quote = self.env['safra.quote'].create({
            'partner_id': self.env['res.partner'].create({'name': 'Secuencia'}).id,
            'line_ids': [(0, 0, dict(l, sequence=(n + 1) * 10))
                         for n, l in enumerate(self.secuencia((1.5, False), (1.5, False), union='DEP'))],
        })
        lineas = SafraQuoterController()._datos_edicion(quote)['lineas']
        self.assertEqual([(l.get('soporte_izq'), l.get('soporte_der')) for l in lineas],
                         [('MANDO', 'DEP'), ('DEP', 'TERMINAL')])

    # --- Hoja 5: 2 en 1 solo por ancho -----------------------------------

    def test_tabla_2en1(self):
        Param = self.env['ir.config_parameter'].sudo()
        Rule = self.env['safra.structure.rule']
        r16 = self.env.ref('website_quotes_safra.struct_2en1_r16')
        sistema = r16.system_ids[:1]
        # Como se sembró antes del ajuste, sin las otras reglas del 2 en 1.
        Rule.search([('system_ids', 'in', r16.system_ids.ids), ('id', '!=', r16.id)]).unlink()
        r16.write({'drive_type': 'any', 'width_from': 0.5, 'width_to': 2.5})
        Param.set_param('website_quotes_safra.ajuste_tubos_2en1', '')
        Rule._ajuste_tubos_2en1()
        self.assertEqual(Rule.find_rule(sistema, 1.0).tubo, 'R8')
        self.assertEqual(Rule.find_rule(sistema, 2.3), r16)
        self.assertEqual(Rule.find_rule(sistema, 1.0, motorized=True).tubo, 'Tubo 40mm (Motorizado)')
        self.assertFalse(Rule.find_rule(sistema, 0.6, motorized=True))
        # Sin alto ni peso máximo: las reglas no tienen constantes.
        self.assertIsNone(Rule.find_rule(sistema, 1.0).compute_limits(1.0, 2.0, 300, 0.5)['alto_maximo'])
        # Una sola vez: corrida de nuevo no crea más reglas.
        antes = Rule.search_count([('system_ids', 'in', sistema.ids)])
        Rule._ajuste_tubos_2en1()
        self.assertEqual(Rule.search_count([('system_ids', 'in', sistema.ids)]), antes)

    def test_2en1_solo_por_ancho(self):
        """Hoja 5: con «Tubo solo por ancho» no se calculan alto ni peso
        máximo aunque la fila tenga espacio, diámetro y carga (p. ej. desde
        las referencias) ni sale el cuadro del «?»."""
        Rule = self.env['safra.structure.rule']
        self.enrollable.tubo_solo_ancho = True
        params = {'peso_tela': 300, 'grosor_tela': 0.5}
        res = Rule.elegir(self.enrollable, 2.0, 3.8, **params)
        self.assertEqual((res['regla'], res['limites'], res['subio_de']), (self.r8_manual, {}, None))
        self.assertFalse(Rule.opciones(self.enrollable, 2.0, 3.8, **params))
        linea = self.linea(fabric_id=self.tela_pesada.id, color_id=self.pesada.id, width=2.0, height=3.8)
        self.assertFalse({'V_ALTO_MAXIMO', 'V_PESO_MAXIMO', 'V_REQUIERE_MOTOR'} & self.codigos([linea]))
        # Sin la marca vuelve el cálculo.
        self.enrollable.tubo_solo_ancho = False
        self.assertTrue(Rule.elegir(self.enrollable, 2.0, 3.8, **params)['limites'])

    def test_marca_solo_ancho_en_2en1(self):
        Param = self.env['ir.config_parameter'].sudo()
        sistemas = self.env['safra.system'].search([('code', 'in', ('32', '61'))])
        if not sistemas:
            self.skipTest('La base no tiene los sistemas 2 en 1')
        sistemas.tubo_solo_ancho = False
        Param.set_param('website_quotes_safra.tubo_solo_ancho', '')
        self.env['safra.structure.rule']._marcar_tubo_solo_ancho()
        self.assertTrue(all(sistemas.mapped('tubo_solo_ancho')))

    def test_tabla_2en1_editada_no_se_toca(self):
        Param = self.env['ir.config_parameter'].sudo()
        Rule = self.env['safra.structure.rule']
        r16 = self.env.ref('website_quotes_safra.struct_2en1_r16')
        r16.write({'drive_type': 'any', 'width_from': 0.5, 'width_to': 2.2})
        Param.set_param('website_quotes_safra.ajuste_tubos_2en1', '')
        antes = Rule.search_count([])
        Rule._ajuste_tubos_2en1()
        self.assertEqual(Rule.search_count([]), antes)
        self.assertEqual(r16.width_to, 2.2)


@tagged('post_install', '-at_install', 'safra')
class TestRevisionTuboFormulas(SafraCommon):
    """Revisión del cálculo de tubo (27-oct): siguiente tubo por alto
    (error 6), carga con torque (error 5), fórmulas editables (error 7),
    valores desde Referencias (punto 1.1) y soportes dependientes (error 3)."""

    def setUp(self):
        super().setUp()
        self.Rule = self.env['safra.structure.rule']

    def linea_pesada(self, **vals):
        return self.linea(fabric_id=self.tela_pesada.id, color_id=self.pesada.id, **vals)

    def secuencia(self, *anchos, **vals):
        ultima = len(anchos) - 1
        return [self.linea_pesada(width=a, same_header=True, sequence_name='S1',
                            soporte_izq='MANDO' if n == 0 else 'DEP',
                            soporte_der='TERMINAL' if n == ultima else 'DEP', **vals)
                for n, a in enumerate(anchos)]

    # --- Error 6: siguiente tubo por alto --------------------------------

    def test_sube_al_siguiente_tubo_por_alto(self):
        """R8 con 2 m de ancho y tela de 300 g/m² soporta 3,33 m de alto:
        con 3,50 m pasa al R16 y no sale el error de alto máximo."""
        res = self.Rule.elegir(self.enrollable, 2.0, 3.5, peso_tela=300, grosor_tela=0.5)
        self.assertEqual((res['regla'], res['subio_de']), (self.r16, 'R8'))
        linea = self.linea_pesada(width=2.0, height=3.5)
        self.assertEqual(self.Line.new(linea)._estructura_linea()[1], self.r16)
        self.assertFalse(self.mensajes([linea], 'V_ALTO_MAXIMO', cross=False))
        # Con el alto que sí alcanza se queda en el R8.
        self.assertEqual(self.Rule.elegir(self.enrollable, 2.0, 3.0, peso_tela=300,
                                          grosor_tela=0.5)['subio_de'], None)

    def test_cuadro_de_opciones(self):
        filas = self.Rule.opciones(self.enrollable, 2.0, 3.5, peso_tela=300, grosor_tela=0.5)
        r8 = [f for f in filas if f['tubo'] == 'R8' and f['accionamiento'] == 'Manual'][0]
        self.assertEqual((r8['alto_maximo'], r8['carga_maxima'], r8['cumple']), (3.33, 2000, False))
        self.assertEqual({(f['accionamiento'], f['tubo']) for f in filas},
                         {('Manual', 'R8'), ('Manual', 'R16'), ('Manual', 'R24'),
                          ('Motor', 'R8'), ('Motor', 'R16'), ('Motor', 'R24')})
        self.assertFalse(self.Rule.opciones(self.enrollable, 2.0, 3.5))  # tela sin parámetros

    # --- Error 5: carga con el torque del motor --------------------------

    def test_carga_con_torque(self):
        """Reunión 30-oct (fila 168): 3 N·m sobre el tubo de 40 mm: 3 × 100 ÷
        40 × 1000 (como el Excel: 6 N·m en 38 mm = 15.789 g)."""
        self.assertEqual(self.r8_motor.carga_motor(3), 7500)
        lim = self.r8_motor.compute_limits(2.0, 2.0, peso_tela=300, torque=3, motor_elegido=True)
        self.assertEqual(lim['carga_maxima'], 7500)
        # La fórmula se cambia en Ajustes › Tubo: alto y peso máximo.
        self.env['ir.config_parameter'].sudo().set_param(
            'safra.formula.tubo_carga_motor', 'result = torque * 1000')
        self.assertEqual(self.r8_motor.carga_motor(3), 3000)
        # Sin torque, la carga máxima del producto del motor. Reunión 09-nov
        # (fila 68): con motor elegido ya no se toma la de la fila; sin motor
        # elegido, la de la fila.
        self.assertEqual(self.r8_motor.compute_limits(2.0, 2.0, peso_tela=300, carga_motor=12000,
                                                      motor_elegido=True)['carga_maxima'], 12000)
        self.assertIsNone(self.r8_motor.compute_limits(2.0, 2.0, peso_tela=300, torque=False,
                                                       carga_motor=False,
                                                       motor_elegido=True)['carga_maxima'])
        self.assertEqual(self.r8_motor.compute_limits(2.0, 2.0, peso_tela=300)['carga_maxima'], 10000)

    def test_torque_del_motor_elegido(self):
        campo = self._campo('motor')
        categoria = campo.ref_category_id or self.env['safra.product.option'].create(
            {'name': 'Motores prueba', 'type': 'ref_categoria'})
        campo.ref_category_id = categoria
        ref = self.env['safra.fabric'].create({'code': 'ZT-MOT', 'name': 'Motores Prueba',
                                               'category_id': categoria.id})
        self._color(ref, 'ZTMOT', 'Motor Prueba', safra_torque=3.0)
        params = self.Line.new(self.linea(has_motor=True, motor='ZTMOT'))._params_estructura()
        self.assertEqual(params['torque'], 3.0)
        self.assertFalse(self.Line.new(self.linea(motor='ZTMOT'))._params_estructura()['torque'])

    # --- Error 7: fórmulas editables -------------------------------------

    def test_formula_editable(self):
        Param = self.env['ir.config_parameter'].sudo()
        Param.set_param('safra.formula.tubo_peso_total', 'result = ancho * alto * peso_tela * factor')
        self.assertEqual(self.r8_manual.compute_limits(2.0, 2.0, peso_tela=300,
                                                       peso_perfil=100)['peso_total'], 1200)
        Param.set_param('safra.formula.tubo_peso_total', False)
        self.assertEqual(self.r8_manual.compute_limits(2.0, 2.0, peso_tela=300,
                                                       peso_perfil=100)['peso_total'], 1400)

    def test_formula_con_error_no_se_guarda(self):
        with self.assertRaises(ValidationError):
            self.env['res.config.settings'].create(
                {'safra_formula_tubo_carga_motor': 'result = torque * (diametro_tubo'}).execute()

    def test_formulas_del_excel(self):
        """Ejemplo del Excel (hoja 3): R16 manual, 2,10 × 3,58 m, tela de
        520 g/m² y 0,74 de densidad, perfil de 136 g/m: 3,39 m por espacio,
        4.194,96 g de peso."""
        regla = self.Rule.create({'system_ids': [(6, 0, self.enrollable.ids)], 'drive_type': 'manual',
                                  'width_from': 9, 'width_to': 9.5, 'tubo': 'RX',
                                  'espacio_eje_techo': 40, 'diametro_tubo': 38, 'carga_maxima': 8000})
        lim = regla.compute_limits(2.1, 3.58, peso_tela=520, grosor_tela=0.74, peso_perfil=136)
        self.assertEqual((lim['alto_maximo'], lim['alto_limitante'], lim['peso_total']),
                         (3.39, 'espacio', 4195))

    # --- Punto 1.1: piezas desde Referencias -----------------------------

    def test_valores_desde_referencias(self):
        Option = self.env['safra.product.option']
        tubo_cat = Option.search([('type', '=', 'ref_categoria'), ('name', '=ilike', 'tubo')], limit=1) \
            or Option.create({'name': 'Tubo', 'type': 'ref_categoria'})
        cab_cat = Option.search([('type', '=', 'ref_categoria'), ('name', '=ilike', 'cabezal')], limit=1) \
            or Option.create({'name': 'Cabezal', 'type': 'ref_categoria'})
        tubos = self.env['safra.fabric'].create({'code': 'ZT-TUB', 'name': 'Tubos', 'category_id': tubo_cat.id})
        cabezales = self.env['safra.fabric'].create({'code': 'ZT-CAB', 'name': 'Cabezales',
                                                     'category_id': cab_cat.id})
        tubo = self._color(tubos, 'ZTR8', 'R8 Prueba', safra_diametro_tubo=50.0,
                           safra_aumento_tela_tubo=0.4)
        cab = self._color(cabezales, 'ZTCABR', 'Cabezal Redondo Prueba', safra_espacio_eje_techo=70.0)
        regla = self.r8_manual
        self.assertEqual(regla._constantes(), {'espacio': 60, 'diametro': 40, 'carga': 2000,
                                               'aumento': 0.25})
        regla.write({'tubo_ref_id': tubo.id, 'cabezal_ref_id': cab.id})
        self.assertEqual(regla._constantes(), {'espacio': 70, 'diametro': 50, 'carga': 2000,
                                               'aumento': 0.4})
        # El tipo del cabezal sale de su referencia al guardar.
        self.assertEqual(regla.cabezal_type, 'redondo')
        # Al elegir la referencia en la pantalla se llena el nombre vacío.
        nueva = self.Rule.new({'cabezal_ref_id': cab.id, 'tubo_ref_id': tubo.id})
        nueva._onchange_referencias()
        self.assertEqual((nueva.cabezal, nueva.tubo), (cab._portal_label(), tubo._portal_label()))
        # Revisión 03-nov: el nombre ya escrito no cambia (con él se
        # emparejan la unificación, los kits y la constante por tubo).
        escrita = self.Rule.new({'tubo': 'R8', 'cabezal': 'Redondo R8',
                                 'cabezal_ref_id': cab.id, 'tubo_ref_id': tubo.id})
        escrita._onchange_referencias()
        self.assertEqual((escrita.cabezal, escrita.tubo), ('Redondo R8', 'R8'))

    # --- Error 3 y hoja 4: soportes dependientes y cabezal ---------------

    def test_tramo_dependiente_como_una_persiana(self):
        """Dos persianas de 1,50 m unidas por DEP son una de 3,00 m: las dos
        van con el tubo de 3,00 m (R24), no con el R8 de cada una."""
        lineas = self.secuencia(1.5, 1.5, height=2.0)
        self.validar(lineas)
        self.assertEqual([l['attribute_values'].get('unificacion_mando') for l in lineas],
                         ['R24', 'R24'])

    def test_tope_entre_dependientes(self):
        avisos = self.mensajes(self.secuencia(1.5, 1.5, 1.5, height=2.0), 'V_SECUENCIA_DEP_ANCHO')
        self.assertEqual([a['message'] for a in avisos],
                         ['E13095: Entre soportes dependientes (persiana 1, persiana 2, persiana 3) '
                          'el ancho suma 4.50 m y el máximo es 4.00 m.'])
        self.assertFalse(self.mensajes(self.secuencia(1.5, 1.5, height=2.0), 'V_SECUENCIA_DEP_ANCHO'))

    def test_reglas_editables_en_validaciones(self):
        """Las reglas nuevas tienen su condición en Validaciones: cambiar el
        tope en la condición cambia la validación, sin código."""
        Rule = self.env['safra.validation.rule']
        for code in ('V_MOTOR_OBLIGATORIO', 'V_SECUENCIA_DEP_ANCHO', 'V_SECUENCIA_DEP_TUBO'):
            self.assertNotIn((Rule.search([('code', '=', code)]).condition_code or 'hallazgo').strip(),
                             ('', 'hallazgo'), code)
        regla = Rule.search([('code', '=', 'V_SECUENCIA_DEP_ANCHO')])
        regla.condition_code = "maximo = 5.0\nresult = bool(tramo) and tramo['ancho'] > maximo"
        self.assertFalse(self.mensajes(self.secuencia(1.5, 1.5, 1.5, height=2.0), 'V_SECUENCIA_DEP_ANCHO'))

    def test_tramo_sin_tubo(self):
        avisos = self.mensajes(self.secuencia(1.8, 1.8, height=2.0), 'V_SECUENCIA_DEP_TUBO')
        self.assertTrue(avisos and 'No hay tubo' in avisos[0]['message'])

    def test_independiente_no_suma(self):
        """Con soporte independiente cada persiana va por su cuenta."""
        lineas = self.secuencia(1.8, 1.8, height=2.0)
        lineas[0]['soporte_der'] = lineas[1]['soporte_izq'] = 'INDEP'
        lineas[1]['soporte_der'] = 'MANDO'
        lineas[1]['soporte_der'], lineas[1]['soporte_izq'] = 'TERMINAL', 'INDEP'
        self.assertFalse(self.mensajes(lineas, 'V_SECUENCIA_DEP_TUBO'))


    # --- Ajuste de la base -----------------------------------------------

    def test_ajuste_revision_tubo(self):
        Param = self.env['ir.config_parameter'].sudo()
        System = self.env['safra.system']
        venecian = System.search([('code', '=', '04')], limit=1)
        premium = System.search([('code', '=', '06')], limit=1)
        if not (venecian and premium):
            self.skipTest('La base no tiene Venecian y Enrollable Premium')
        self.Rule.search([('system_ids', 'in', venecian.id)]).write({'system_ids': [(3, venecian.id)]})
        regla = self.env['safra.validation.rule'].search([('code', '=', 'V_SECUENCIA_ANCHO')])
        regla.system_ids = [(6, 0, premium.ids)]
        Param.set_param('website_quotes_safra.ajuste_revision_tubo', '')
        self.Rule._ajuste_revision_tubo()
        self.assertTrue(self.Rule.search_count([('system_ids', 'in', venecian.id),
                                                ('cabezal_type', '!=', 'na')]))
        self.assertIn(venecian, regla.system_ids)
        nombres = self.env['safra.product.option'].search(
            [('type', '=', 'ref_categoria')]).mapped(lambda o: o.name.lower())
        for nombre in ('tubo', 'mecanismo', 'soporte', 'terminal', 'cabezal'):
            self.assertIn(nombre, nombres)
