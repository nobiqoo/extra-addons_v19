# -*- coding: utf-8 -*-
import base64
import io
import zipfile

from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import SafraCommon, excel_safra
from ..models import safra_reglas_17 as R17


@tagged('post_install', '-at_install', 'safra')
class TestCierre0911(SafraCommon):
    """Reunión del 09-nov (cierre de los pendientes del Sprint 1): ítems
    inactivados (fila 2), tubo y motor (fila 68) y verificación de
    fabricación unificada con «Pedido sin restricciones» (fila 74)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['ir.config_parameter'].sudo().search(
            [('key', 'in', list(R17.FORMULAS_TUBO))]).unlink()
        # Motores de prueba en la referencia del campo Motor, solo para el
        # enrollable de prueba (los de la base no aplican).
        campo_motor = cls._campo('motor')
        categoria = campo_motor.ref_category_id or cls.env['safra.product.option'].create(
            {'name': 'Motores prueba 0911', 'type': 'ref_categoria', 'es_motor': True})
        campo_motor.ref_category_id = categoria
        Color = cls.env['safra.fabric.color'].sudo().with_context(active_test=False)
        Color.search([('fabric_id.category_id', '=', categoria.id)]).write(
            {'system_ids': [(6, 0, cls.panel.ids)]})
        cls.ref_motores = cls.env['safra.fabric'].create({
            'code': 'ZT-MOT0911', 'name': 'Motores 0911', 'category_id': categoria.id,
            'system_ids': [(6, 0, cls.enrollable.ids)]})
        Product = cls.env['product.template']
        cls.prod_sin_datos = Product.create({'name': 'Motor Sin Datos', 'safra_code': 'ZTM0',
                                             'safra_is_color': True})
        cls.motor_sin_datos = cls.env['safra.fabric.color'].create(
            {'fabric_id': cls.ref_motores.id, 'product_tmpl_id': cls.prod_sin_datos.id,
             'code': 'ZTM0'})

    def linea_pesada(self, **vals):
        return self.linea(fabric_id=self.tela_pesada.id, color_id=self.pesada.id, **vals)

    def cotizacion(self, **vals):
        return self.env['safra.quote'].create({
            'partner_id': self.env.user.partner_id.id, 'user_id': self.env.user.id,
            'line_ids': [(0, 0, self.linea(**vals))]})

    # --- Fila 68: carga máxima del mecanismo y del motor -------------------

    def limites(self, regla, **params):
        base = dict(peso_tela=300.0, grosor_tela=0.5, peso_perfil=0.0, factor=1.0)
        base.update(params)
        return regla.compute_limits(1.5, 1.8, **base)

    def test_carga_en_cero_no_deja_pasar_el_peso(self):
        """Una carga máxima digitada en 0 dice que el mecanismo no soporta
        peso: antes no se comparaba y la persiana pasaba."""
        self.r8_manual.carga_maxima = 0
        lim = self.limites(self.r8_manual)
        self.assertIs(lim['peso_ok'], False)
        self.assertEqual(lim['carga_maxima'], 0)
        # Sin digitar no hay con qué comparar (lo avisa «Falta digitar»).
        self.r8_manual.carga_maxima = False
        lim = self.limites(self.r8_manual)
        self.assertIsNone(lim['peso_ok'])
        self.assertTrue(lim['carga_sin_dato'])

    def test_con_motor_la_carga_sale_solo_del_maestro(self):
        r8 = self.r8_motor  # fila con carga 10.000 g y tubo de 40 mm
        # Sin motor elegido: la de la fila.
        self.assertEqual(self.limites(r8)['carga_maxima'], 10000)
        # Motor sin torque ni carga en el maestro: ya no toma la de la fila.
        lim = self.limites(r8, torque=False, carga_motor=False, motor_elegido=True)
        self.assertIsNone(lim['carga_maxima'])
        self.assertTrue(lim['carga_sin_dato'])
        # Con la Carga máxima del producto del motor.
        lim = self.limites(r8, torque=False, carga_motor=500.0, motor_elegido=True)
        self.assertEqual((lim['carga_maxima'], lim['peso_ok']), (500, False))
        # Con torque: 6 N·m × 100 ÷ 40 mm × 1000 = 15.000 g.
        lim = self.limites(r8, torque=6.0, carga_motor=500.0, motor_elegido=True)
        self.assertEqual((lim['carga_maxima'], lim['peso_ok']), (15000, True))

    def test_motor_sin_datos_en_el_maestro_es_error(self):
        linea = self.linea_pesada(has_motor=True, motor=self.motor_sin_datos.code, control='0',
                            control_channel='1')
        mensajes = [i['message'] for i in self.mensajes([linea], 'V_PESO_SIN_CARGA', cross=False)]
        self.assertEqual(len(mensajes), 1)
        self.assertIn('El motor elegido no tiene Torque ni Carga máxima', mensajes[0])
        self.assertFalse(self.mensajes([linea], 'V_PESO_MAXIMO', cross=False))
        # La carga vacía también se avisa como dato sin digitar.
        avisos = [i['message'] for i in self.mensajes([linea], 'V_DATO_SIN_DIGITAR', cross=False)]
        self.assertTrue([a for a in avisos if 'Torque y Carga maxima del producto' in a])
        # Con la carga en su maestro ya se compara.
        self.prod_sin_datos.safra_carga_maxima = 9000
        self.assertFalse(self.mensajes([linea], 'V_PESO_MAXIMO', cross=False))
        self.prod_sin_datos.safra_carga_maxima = 100
        mensajes = [i['message'] for i in self.mensajes([linea], 'V_PESO_MAXIMO', cross=False)]
        self.assertIn('La persiana no se puede fabricar: el motor elegido no soporta el peso '
                      'de la persiana (peso calculado 810 g; carga máxima 100 g).', mensajes[0])

    def test_manual_por_peso_sugiere_motor(self):
        """Tela de 300 g/m² en 1,9 × 3,5 m: pesa 1.995 g; con el mecanismo
        manual en 1.500 g no se puede, con motor (10.000 g) sí."""
        self.r8_manual.carga_maxima = 1500
        Rule = self.env['safra.structure.rule']
        params = dict(peso_tela=300.0, grosor_tela=0.5, peso_perfil=0.0, factor=1.0)
        self.assertIs(Rule.elegir(self.enrollable, 1.9, 3.5, **params)['limites']['peso_ok'], False)
        alternativa = Rule.alternativa_motor(self.enrollable, 1.9, 3.5, **params)
        self.assertEqual(alternativa['tubo'], 'R8')
        issues = self.mensajes([self.linea_pesada(width=1.9, height=3.5)], 'V_REQUIERE_MOTOR', cross=False)
        self.assertEqual(len(issues), 1)
        self.assertIn('tubo R8', issues[0]['message'])
        self.assertIn('Con motor', issues[0]['message'])
        self.assertNotIn('V_PESO_MAXIMO', self.codigos([self.linea_pesada(width=1.9, height=3.5)], cross=False))
        # Con el motor marcado ya no se pide.
        self.assertNotIn('V_REQUIERE_MOTOR', self.codigos(
            [self.linea_pesada(width=1.9, height=3.5, has_motor=True, motor='M1', control='0',
                         control_channel='1')], cross=False))

    def test_sugiere_el_motor_que_soporta_el_peso(self):
        """Los motores del sistema con datos en el maestro: si ninguno
        soporta el peso, no se sugiere motorizar."""
        self.r8_manual.carga_maxima = 1500
        self.prod_sin_datos.safra_carga_maxima = 1000
        params = dict(peso_tela=300.0, grosor_tela=0.5, peso_perfil=0.0, factor=1.0)
        Rule = self.env['safra.structure.rule']
        motores = self.Line._motores_sistema(self.enrollable)
        self.assertEqual(motores, self.prod_sin_datos)
        self.assertIsNone(Rule.alternativa_motor(self.enrollable, 1.9, 3.5, motores=motores, **params))
        self.prod_sin_datos.safra_carga_maxima = 3000
        alternativa = Rule.alternativa_motor(self.enrollable, 1.9, 3.5, motores=motores, **params)
        self.assertEqual(alternativa['motor'], self.prod_sin_datos)

    def test_mensaje_de_requiere_motor_una_vez(self):
        Rule = self.env['safra.validation.rule'].with_context(active_test=False)
        regla = Rule.search([('code', '=', 'V_REQUIERE_MOTOR')], limit=1)
        regla.message = R17.MENSAJE_REQUIERE_MOTOR_ANTERIOR
        Rule._ajuste_mensaje_requiere_motor()
        self.assertEqual(regla.message, R17.MENSAJE_REQUIERE_MOTOR)
        # Si Safra lo editó, se respeta.
        regla.message = 'Mensaje de Safra'
        Rule._ajuste_mensaje_requiere_motor()
        self.assertEqual(regla.message, 'Mensaje de Safra')

    # --- Fila 2: ítems inactivados -----------------------------------------

    def test_motor_inactivado_se_avisa(self):
        quote = self.cotizacion(has_motor=True, motor='ref-%d' % self.motor_sin_datos.id)
        self.assertFalse(quote._no_disponibles_portal())
        self.motor_sin_datos.active = False
        avisos = quote._no_disponibles_portal()
        self.assertEqual(len(avisos), 1)
        self.assertIn('Persiana 1: «', avisos[0])
        self.assertIn('fue inactivado', avisos[0])
        self.assertIn('V_REVALIDACION', [i['code'] for i in quote._revalidate()])
        # Al editar, el portal lo deja elegido en gris junto a su campo.
        item = quote.line_ids._items_no_disponibles()[0]
        self.assertEqual((item['code'], item['valor'], item['nombre']),
                         ('motor', 'ref-%d' % self.motor_sin_datos.id,
                          self.motor_sin_datos._portal_label()))
        # El producto archivado en el maestro también (archiva su línea).
        self.motor_sin_datos.active = True
        self.prod_sin_datos.active = False
        self.assertTrue(quote._no_disponibles_portal())

    def test_todas_las_telas_se_revisan(self):
        quote = self.cotizacion(fabric_id_2=self.tela_sheer.id, color_id_2=self.sheer.id)
        self.assertFalse(quote._no_disponibles_portal())
        self.sheer.active = False
        self.assertEqual(quote._no_disponibles_portal(),
                         ['Persiana 1: el color %s fue inactivado' % self.sheer.name])
        self.tela_sheer.active = False
        self.assertIn('Persiana 1: la referencia Sheer Prueba fue inactivada',
                      quote._no_disponibles_portal())

    def test_confirmada_no_avisa(self):
        quote = self.cotizacion(has_motor=True, motor='ref-%d' % self.motor_sin_datos.id)
        self.motor_sin_datos.active = False
        quote.state = 'confirmed'
        self.assertFalse(quote._no_disponibles_portal())

    # --- Fila 74: verificación de fabricación con garantía -----------------

    def test_sin_restricciones_se_unifica_en_la_verificacion(self):
        campo = self._campo('sin_restricciones')
        campo.active = True
        viejo = self.env.ref('website_quotes_safra.group_safra_sin_restricciones')
        nuevo = self.env.ref('website_quotes_safra.group_safra_verificacion')
        usuario = self.env['res.users'].create({
            'name': 'Comercial 0911', 'login': 'comercial0911', 'group_ids': [(4, viejo.id)]})
        self.assertNotIn(nuevo, usuario.group_ids)
        self.env['safra.field']._ajuste_unificar_verificacion()
        self.assertFalse(campo.active)
        self.assertIn(nuevo, usuario.group_ids)

    def verificacion(self):
        quote = self.cotizacion()
        quote.write({'requiere_verificacion': True, 'verificacion_observaciones': 'Cambiar perfil',
                     'verificacion_acepta_sin_garantia': True})
        ticket = quote._create_verification_ticket()
        self.assertIn('indique si va con garantía o sin garantía', str(ticket.description))
        return quote, ticket

    def test_planta_aprueba_con_garantia(self):
        quote, ticket = self.verificacion()
        ticket.safra_garantia_motivo = 'Cumple las especificaciones; se reservó por capacidad.'
        ticket.action_safra_aprobar_con_garantia()
        self.assertTrue(quote.verificacion_aprobada)
        self.assertEqual(quote.verificacion_garantia, 'con')
        self.assertEqual(quote.verificacion_garantia_motivo,
                         'Cumple las especificaciones; se reservó por capacidad.')
        self.assertEqual(ticket.safra_garantia, 'con')
        self.assertTrue(ticket.safra_produccion_aprobada)

    def test_planta_aprueba_sin_garantia(self):
        quote, ticket = self.verificacion()
        ticket.safra_garantia_motivo = 'Medidas fuera de la ficha técnica.'
        ticket.action_safra_aprobar_sin_garantia()
        self.assertEqual((quote.verificacion_aprobada, quote.verificacion_garantia,
                          quote.verificacion_garantia_motivo),
                         (True, 'sin', 'Medidas fuera de la ficha técnica.'))

    def test_motivo_obligatorio_para_aprobar(self):
        """El Motivo (garantía) es obligatorio con o sin garantía."""
        quote, ticket = self.verificacion()
        for aprobar in (ticket.action_safra_aprobar_con_garantia,
                        ticket.action_safra_aprobar_sin_garantia):
            with self.assertRaisesRegex(UserError, 'Motivo'):
                aprobar()
        ticket.safra_garantia_motivo = '   '
        with self.assertRaises(UserError):
            ticket.action_safra_aprobar_con_garantia()
        self.assertFalse(quote.verificacion_aprobada)

    def test_la_copia_conserva_la_aceptacion(self):
        quote, _ticket = self.verificacion()
        copia = quote._duplicar_portal(self.env.user)
        self.assertEqual(copia.verificacion_acepta_sin_garantia,
                         copia.requiere_verificacion)
        self.assertFalse(copia.verificacion_garantia)

    # --- Revisión 10-nov: la misma apertura en dos rieles ------------------

    def test_misma_apertura_en_dos_rieles(self):
        """Con la fórmula del Excel en 4 rieles, 7 telos a la derecha salen en
        riel 6 velcrado y en riel 7: el Tipo de Riel puede ser cualquiera de
        los dos (antes solo se aceptaba el primero)."""
        entrada, salida = zipfile.ZipFile(io.BytesIO(excel_safra())), io.BytesIO()
        with zipfile.ZipFile(salida, 'w', zipfile.ZIP_DEFLATED) as nuevo:
            for info in entrada.infolist():
                data = entrada.read(info.filename)
                if info.filename == 'xl/worksheets/sheet1.xml':
                    data = data.replace(b'_xlpm.cantidadRieles,3', b'_xlpm.cantidadRieles,4')
                nuevo.writestr(info, data)
        self.combo_rule.excel_archivo = base64.b64encode(salida.getvalue())
        ancho = round(0.65 * 7 - 6 * 0.08, 2)
        rieles = {f['riel'] for f in self.combo_rule._filas(ancho, 0.08, 7)
                  if f['apertura'] == 'derecha'}
        self.assertEqual(rieles, {6, 7})
        linea = lambda riel: self.linea_panel(7, apertura='derecha', riel=riel, ancho=ancho)
        self.assertFalse(self.mensajes([linea('rv')], 'V_PANEL_RIEL', cross=False))
        mensaje = self.mensajes([linea('r4')], 'V_PANEL_RIEL', cross=False)[0]['message']
        self.assertIn('Riel Velcrado o riel de 7 vías', mensaje)

    # --- Revisión 10-nov: 0 o vacío en los datos de la carga ---------------

    def test_dato_vacio_o_en_cero(self):
        Rule = self.env['safra.structure.rule']
        self.assertEqual(Rule._dato(False, ' N·m'), 'sin digitar')
        self.assertEqual(Rule._dato(0.0, ' g', femenino=True), 'digitada en 0')
        self.assertEqual(Rule._dato(6.0, ' N·m'), '6 N·m')
        self.assertEqual(Rule._dato(15789.47, ' g'), '15.789 g')

    def test_motor_dice_que_dato_falta(self):
        """Torque sin digitar y Carga maxima en 0: el mensaje lo dice, no
        solo «(0 g)»."""
        self.prod_sin_datos.write({'safra_torque': False, 'safra_carga_maxima': 0})
        linea = self.linea_pesada(has_motor=True, motor=self.motor_sin_datos.code, control='0',
                                  control_channel='1')
        mensaje = self.mensajes([linea], 'V_PESO_MAXIMO', cross=False)[0]['message']
        self.assertIn('el motor elegido no soporta el peso', mensaje)
        self.assertIn('Maestro del motor «Motor Sin Datos»: Torque sin digitar, '
                      'Carga maxima digitada en 0.', mensaje)
        # Torque digitado en 0 y Carga maxima vacía: es 0, no «sin dato».
        self.prod_sin_datos.write({'safra_torque': 0, 'safra_carga_maxima': False})
        mensaje = self.mensajes([linea], 'V_PESO_MAXIMO', cross=False)[0]['message']
        self.assertIn('Torque digitado en 0, Carga maxima sin digitar.', mensaje)
        self.assertNotIn('no hay con qué comparar', mensaje)
        # Las dos vacías: no hay con qué comparar.
        self.prod_sin_datos.write({'safra_torque': False})
        mensaje = self.mensajes([linea], 'V_PESO_SIN_CARGA', cross=False)[0]['message']
        self.assertIn('no hay con qué comparar', mensaje)
        self.assertIn('Torque sin digitar, Carga maxima sin digitar.', mensaje)

    def test_fila_en_cero_lo_dice(self):
        self.r8_manual.carga_maxima = 0
        lim = self.limites(self.r8_manual)
        self.assertEqual(lim['carga_detalle'],
                         'Carga máxima de la fila «R8» en Estructura por Ancho: digitada en 0.')

    def test_peso_con_la_condicion_en_validaciones(self):
        """Revisión 10-nov: V_PESO_MAXIMO y V_PESO_SIN_CARGA tienen la
        condición escrita en Validaciones (no «hallazgo»); Safra la cambia."""
        Rule = self.env['safra.validation.rule'].with_context(active_test=False)
        regla = Rule.search([('code', '=', 'V_PESO_MAXIMO')], limit=1)
        self.assertEqual(regla.condition_code, R17.PESO_MAXIMO_CONDICION)
        self.assertNotIn('hallazgo', regla.condition_code)
        self.prod_sin_datos.safra_carga_maxima = 100
        linea = self.linea_pesada(has_motor=True, motor=self.motor_sin_datos.code, control='0',
                                  control_channel='1')
        self.assertTrue(self.mensajes([linea], 'V_PESO_MAXIMO', cross=False))
        # Safra le da un margen del 10 %: 810 g no pasan de 100 g × 1,1.
        regla.condition_code = (
            "quien = 'el motor'\n"
            "result = not vacio(estructura['carga']) and estructura['peso'] > estructura['carga'] * 10")
        self.assertFalse(self.mensajes([linea], 'V_PESO_MAXIMO', cross=False))
        regla.write({'condition_code': R17.PESO_MAXIMO_CONDICION, 'message': 'Pesa {estructura[peso]:.0f} g.'})
        self.assertEqual(self.mensajes([linea], 'V_PESO_MAXIMO', cross=False)[0]['message'], 'Pesa 810 g.')

    def test_ajuste_reglas_visibles(self):
        """Una base con las reglas como estaban (condición «hallazgo»)."""
        Rule = self.env['safra.validation.rule'].with_context(active_test=False)
        peso = Rule.search([('code', '=', 'V_PESO_MAXIMO')], limit=1)
        peso.write({'condition_code': 'hallazgo', 'message': False})
        Rule.search([('code', 'in', ('V_DATO_SIN_DIGITAR', 'V_PESO_SIN_CARGA'))]).unlink()
        Rule._ajuste_reglas_visibles_1011()
        self.assertEqual((peso.condition_code, peso.message),
                         (R17.PESO_MAXIMO_CONDICION, R17.PESO_MAXIMO_MENSAJE))
        dato = Rule.search([('code', '=', 'V_DATO_SIN_DIGITAR')])
        self.assertEqual((dato.severity, dato.condition_code),
                         ('warning', R17.DATO_SIN_DIGITAR['condition']))
        self.assertTrue(Rule.search([('code', '=', 'V_PESO_SIN_CARGA')]))
        # Lo que Safra escribió se respeta.
        peso.write({'condition_code': 'estructura[\'peso\'] > 5000', 'message': 'Pesa mucho.'})
        Rule._ajuste_reglas_visibles_1011()
        self.assertEqual(peso.condition_code, "estructura['peso'] > 5000")

    def test_reglas_del_tubo_con_condicion_escrita(self):
        """Revisión 10-nov: V_REQUIERE_MOTOR, V_ALTO_MAXIMO y V_ESTRUCTURA
        tienen su condición escrita (estructura[...]) y salen igual que antes;
        si una base conserva «hallazgo», el respaldo del cálculo interno las
        sigue sacando."""
        Rule = self.env['safra.validation.rule'].with_context(active_test=False)
        reglas = {}
        for code, condicion in (('V_REQUIERE_MOTOR', R17.REQUIERE_MOTOR_CONDICION),
                                ('V_ALTO_MAXIMO', R17.ALTO_MAXIMO_CONDICION),
                                ('V_ESTRUCTURA', R17.ESTRUCTURA_CONDICION)):
            reglas[code] = Rule.search([('code', '=', code)], limit=1)
            self.assertEqual(reglas[code].condition_code, condicion)

        def sale(code, linea):
            """Con la condición escrita y con «hallazgo», igual."""
            escrita = code in self.codigos([linea], cross=False)
            original = reglas[code].condition_code
            reglas[code].condition_code = 'hallazgo'
            con_hallazgo = code in self.codigos([linea], cross=False)
            reglas[code].condition_code = original
            self.assertEqual(escrita, con_hallazgo, code)
            return escrita

        self.r8_manual.carga_maxima = 1500
        self.assertTrue(sale('V_REQUIERE_MOTOR', self.linea_pesada(width=1.9, height=3.5)))
        self.assertFalse(sale('V_REQUIERE_MOTOR', self.linea_pesada(width=1.5, height=1.8)))
        self.enrollable.tech_width_max = 4.0
        self.assertTrue(sale('V_ESTRUCTURA', self.linea(width=3.5)))
        self.assertFalse(sale('V_ESTRUCTURA', self.linea(width=1.5)))
        (self.r16 | self.r24).write({'espacio_eje_techo': 60, 'diametro_tubo': 40, 'carga_maxima': 2000})
        self.assertTrue(sale('V_ALTO_MAXIMO', self.linea_pesada(width=2.0, height=3.8)))
        self.assertFalse(sale('V_ALTO_MAXIMO', self.linea_pesada(width=2.0, height=1.8)))
        # El peso también, con «hallazgo» y sin mensaje.
        peso = Rule.search([('code', '=', 'V_PESO_MAXIMO')], limit=1)
        peso.write({'condition_code': 'hallazgo', 'message': False})
        self.prod_sin_datos.safra_carga_maxima = 100
        con_motor = self.linea_pesada(has_motor=True, motor=self.motor_sin_datos.code, control='0',
                                      control_channel='1')
        self.assertIn('no soporta el peso', self.mensajes([con_motor], 'V_PESO_MAXIMO', cross=False)[0]['message'])
