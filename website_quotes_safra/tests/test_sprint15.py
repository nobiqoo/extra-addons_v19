# -*- coding: utf-8 -*-
from odoo.exceptions import ValidationError
from odoo.tests import HttpCase, new_test_user, tagged

from .common import SafraCommon

CAMPOS_CORTINA = [
    'width', 'height', 'quantity', 'location', 'fabric_id', 'color_id',
    'tipoplano_cortina', 'segmento_1', 'segmento_1_u', 'segmento_1_u_m',
    'segmento_2', 'segmento_3', 'segmento_3_m', 'curva_izquierda',
    'curva_derecha', 'bajofalso',
]


class Sprint15Common(SafraCommon):
    """Sprint 1.5 (filas 97-121 de la matriz): Riel, Cordón / Cadena /
    Bastón y Otras opciones. La función se vuelve a aplicar aquí, así el
    resultado no depende de lo que el funcional haya cambiado en la base."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Field = cls.env['safra.field'].with_context(active_test=False)
        cls.Field._apply_sprint15()
        Mapping = cls.env['safra.system.field']
        # Posición Telo Fijo en el panel de prueba y bolsillo en el enrollable.
        Mapping.create([
            {'system_id': cls.panel.id, 'field_id': cls._campo('posicion_telo').id, 'sequence': 200},
            {'system_id': cls.enrollable.id, 'field_id': cls._campo('bolsillo_size').id, 'sequence': 200},
        ])
        cls.cortina = cls._sistema('ZT49', 'PRUEBA CORTINA', CAMPOS_CORTINA,
                                   (0.30, 8.00, 0.30, 4.00))
        cls.tela.system_ids |= cls.cortina
        cls.tela_pesada.system_ids |= cls.cortina
        cls._rieles_referencia()
        cls._formulas_dobladillo()

    @classmethod
    def _formulas_dobladillo(cls):
        """Fila 118: las fórmulas iniciales del Dobladillo o Bajo falso
        (en la base pueden estar editadas)."""
        field = cls._campo('bajofalso')
        por_valor = {o.value: o for o in field.option_ids}
        for value, name, formula in cls.env['safra.field'].SPRINT15_DOBLADILLO:
            if value in por_valor:
                por_valor[value].formula = formula
            else:
                cls.env['safra.field.option'].create({
                    'field_id': field.id, 'value': value, 'name': name, 'formula': formula})
        field.option_ids.filtered(lambda o: o.value == 'BN_PANOS').write(
            {'solo_aviso': True, 'aviso': cls.env['safra.field'].AVISO_PANOS})

    @classmethod
    def _rieles_referencia(cls):
        """Referencia de rieles en la categoría «Riel» (marcada Rieles): 4 y
        5 vías y el Riel Velcrado."""
        categoria = cls._campo('riel_tipo').ref_category_id
        ref = cls.env['safra.fabric'].create({
            'code': 'ZT-RIEL', 'name': 'Rieles Prueba', 'category_id': categoria.id})
        Color = cls.env['safra.fabric.color']

        def linea(code, etiqueta, canales, velcrado=False):
            producto = cls.env['product.template'].create({
                'name': 'Riel %s' % etiqueta, 'safra_code': code, 'safra_is_color': True})
            return Color.create({'fabric_id': ref.id, 'product_tmpl_id': producto.id,
                                 'etiqueta': etiqueta, 'canales': canales, 'velcrado': velcrado})
        cls.riel4 = linea('ZTR4', '4 rieles', 4)
        cls.riel5 = linea('ZTR5', '5 rieles', 5)
        cls.rielv = linea('ZTRV', 'Velcro', 6, velcrado=True)

    def campo(self, code):
        return self.Field.search([('code', '=', code)], limit=1)

    def mapeo(self, code, sistema):
        return self.env['safra.system.field'].with_context(active_test=False).search([
            ('field_id.code', '=', code), ('system_id.code', '=', sistema)], limit=1)

    def opciones(self, mapping):
        return [(o.value, o.name) for o in (mapping.option_ids or mapping.field_id.option_ids)]

    def linea_cortina(self, ancho=1.5, **attrs):
        return self.linea(system_id=self.cortina.id, width=ancho, attribute_values=attrs)


@tagged('post_install', '-at_install', 'safra')
class TestSprint15(Sprint15Common):

    # --- Datos que deja la función ---------------------------------------

    def test_posicion_telo_fijo_segun_apertura(self):
        """Fila 97: Libre solo Ninguno; Centro con centro frente y atrás;
        las demás aperturas, Frente y Atrás. Panel Duo solo Frente."""
        telo = self.campo('posicion_telo')
        deps = {o.value: (o.depends_field_id.code, o.depends_value) for o in telo.option_ids}
        self.assertEqual(deps, {
            '1': ('apertura', '1,2,3,4'), '2': ('apertura', '1,2,3,4'),
            '3': ('apertura', '4'), '4': ('apertura', '4'), 'ninguno': ('apertura', '5')})
        duo = self.mapeo('posicion_telo', '54')
        if duo:
            self.assertEqual(self.opciones(duo), [('1', 'Frente')])

    def test_tipo_de_riel(self):
        """Fila 99: el Tipo de Riel sale de Referencias (categoría «Riel»)
        y, sin referencias, Panel Duo y Riel Armado traen los rieles de la
        matriz (Riel Armado mostraba solo «Velcrado»)."""
        riel = self.campo('riel_tipo')
        self.assertEqual(riel.field_type, 'ref_categoria')
        self.assertTrue(riel.ref_category_id.es_riel)
        self.assertEqual(riel.name, 'Tipo de Riel')
        for sistema in ('54', '15'):
            mapping = self.mapeo('riel_tipo', sistema)
            if mapping:
                with self.subTest(sistema=sistema):
                    self.assertEqual(self.opciones(mapping), self.Field.SPRINT15_RIELES)
                    self.assertFalse(mapping.label_override)

    def test_listas_desplegables(self):
        """Filas 100 y 115: Riel junto a y Distribución lamas combinadas."""
        for code, opciones in self.Field.SPRINT15_LISTAS.items():
            with self.subTest(campo=code):
                field = self.campo(code)
                self.assertEqual(field.field_type, 'selection')
                self.assertEqual([(o.value, o.name) for o in field.option_ids], opciones)

    def test_mando_y_longitud_baston(self):
        """Fila 106 (con la 77): el bastón depende del mando Bastón o Doble
        Bastón, que ahora está en los paneles y las cortinas."""
        for sistema, opciones in self.Field.SPRINT15_MANDOS.items():
            mapping = self.mapeo('mando_position', sistema)
            if mapping:
                with self.subTest(sistema=sistema):
                    self.assertTrue(mapping.active)
                    self.assertEqual(self.opciones(mapping), opciones)
        baston = self.campo('longitud_baston')
        self.assertEqual((baston.depends_field_id.code, baston.depends_value), ('mando_position', '4,5'))
        self.assertEqual(baston.ref_category_id.name, 'Bastón')

    def test_campos_desde_referencias(self):
        """Filas 110 y 119: Abrazadera y Gancho desde Referencias."""
        for code, nombre in self.Field.SPRINT15_CATEGORIAS.items():
            with self.subTest(campo=code):
                field = self.campo(code)
                self.assertEqual(field.field_type, 'ref_categoria')
                self.assertEqual(field.ref_category_id.name, nombre)

    def test_nombres_de_la_matriz(self):
        """Fila 104: un solo nombre para la cadena extra, sin las etiquetas
        «Cordón Extra» o «Altura Cadena» por sistema; fila 120: bastidor."""
        for code, nombre in self.Field.SPRINT15_NOMBRES.items():
            with self.subTest(campo=code):
                field = self.campo(code)
                self.assertEqual(field.name, nombre)
                self.assertFalse(field.mapping_ids.filtered('label_override'))

    def test_bolsillo_por_tela(self):
        self.assertEqual(self.campo('bolsillo_size').fabric_flag, 'bolsillo')

    def test_segmentos_de_las_cortinas(self):
        """Fila 112: en Onda Moderna y Pliegue Francés los segmentos salen
        del Riel curvo y el Segmento de los planos A-H se archiva."""
        for sistema in self.Field.SPRINT15_SIN_SEGMENTO:
            mapping = self.mapeo('num_segmento', sistema)
            if mapping:
                self.assertFalse(mapping.active)
            if self.mapeo('segmento_2', sistema):
                self.assertTrue(self.mapeo('curva_izquierda', sistema).active)
        # Reunión 22-oct: las curvas del Plano U son Segmento 1 y Segmento 3.
        self.assertFalse(self.campo('curva_izquierda').option_ids.filtered(lambda o: o.value == 'mas'))
        self.assertEqual(self.campo('curva_izquierda').depends_value, 'LI')
        self.assertEqual(self.campo('curva_derecha').depends_value, 'LD')
        for code in ('segmento_1_u', 'segmento_3'):
            campo = self.campo(code)
            self.assertEqual((campo.depends_field_id.code, campo.depends_value), ('tipoplano_cortina', 'U'))
            self.assertEqual(campo.option_ids.mapped('value'), ['0.30', '0.50', 'mas'])
            medida = self.campo(code + '_m')
            self.assertEqual((medida.depends_field_id.code, medida.depends_value), (code, 'mas'))

    def test_comentarios_en_todos_los_sistemas(self):
        """Fila 121: Comentarios es un campo del catálogo en cada sistema."""
        sistemas = self.env['safra.system'].with_context(active_test=False).search([])
        con_campo = self.env['safra.system.field'].with_context(active_test=False).search(
            [('field_id.code', '=', 'description')]).mapped('system_id')
        # Los sistemas de prueba se crean después de aplicar la función.
        self.assertFalse(sistemas - con_campo - self.enrollable - self.panel - self.cortina)

    def test_idempotente(self):
        antes = self.env['safra.field.option'].search_count([])
        antes_sis = self.env['safra.system.field.option'].search_count([])
        self.Field._apply_sprint15()
        self.assertEqual(self.env['safra.field.option'].search_count([]), antes)
        self.assertEqual(self.env['safra.system.field.option'].search_count([]), antes_sis)

    # --- Validaciones ----------------------------------------------------

    def test_e20033_opcion_que_no_aplica(self):
        """«Centro frente» solo con apertura Centro (4)."""
        con_derecha = self.linea_panel(6, '1', attribute_values={'posicion_telo': '3'})
        self.assertIn('V_OPCION_DEPENDENCIA', self.codigos([con_derecha], cross=False))
        con_centro = self.linea_panel(6, '4', attribute_values={'posicion_telo': '3'})
        self.assertNotIn('V_OPCION_DEPENDENCIA', self.codigos([con_centro], cross=False))
        libre = self.linea_panel(6, '5', attribute_values={'posicion_telo': '1'})
        self.assertIn('V_OPCION_DEPENDENCIA', self.codigos([libre], cross=False))

    def test_e20034_telo_fijo_con_7_o_12_telos(self):
        self.assertIn('V_TELO_FIJO', self.codigos([self.linea_panel(7, '1')], cross=False))
        con_telo = self.linea_panel(7, '1', attribute_values={'posicion_telo': '1'})
        self.assertNotIn('V_TELO_FIJO', self.codigos([con_telo], cross=False))
        self.assertNotIn('V_TELO_FIJO', self.codigos([self.linea_panel(6, '1')], cross=False))

    def test_e20035_bolsillo_solo_en_telas_que_lo_permiten(self):
        con_bolsillo = self.linea(bolsillo_size='5')
        self.assertIn('V_BOLSILLO_TELA', self.codigos([con_bolsillo], cross=False))
        self.tela.permite_bolsillo = True
        self.assertNotIn('V_BOLSILLO_TELA', self.codigos([con_bolsillo], cross=False))

    def test_e20036_segmentos_del_riel_curvo(self):
        casos = {
            'Plano L que suma el ancho': (self.linea_cortina(tipoplano_cortina='LID', segmento_1=1.0, segmento_2=0.5), False),
            'Plano L que no suma': (self.linea_cortina(tipoplano_cortina='LID', segmento_1=1.0, segmento_2=0.4), True),
            'Plano L incompleto': (self.linea_cortina(tipoplano_cortina='LID', segmento_1=1.5), True),
            'Plano U con curva digitada': (self.linea_cortina(tipoplano_cortina='U', segmento_1_u='0.30', segmento_2=0.9,
                                                              segmento_3='mas', segmento_3_m=0.3), False),
            'Plano U que no suma': (self.linea_cortina(tipoplano_cortina='U', segmento_1_u='0.50', segmento_2=0.9,
                                                       segmento_3='0.50'), True),
            'Plano U sin Segmento 3': (self.linea_cortina(tipoplano_cortina='U', segmento_1_u='0.60', segmento_2=0.9), True),
            'Curva izquierda elegida': (self.linea_cortina(tipoplano_cortina='LI', curva_izquierda='0.30'), False),
            'Curva izquierda sin elegir': (self.linea_cortina(tipoplano_cortina='LI'), True),
        }
        for nombre, (linea, error) in casos.items():
            with self.subTest(caso=nombre):
                codigos = self.codigos([linea], cross=False)
                if error:
                    self.assertIn('V_SEGMENTOS_CORTINA', codigos)
                else:
                    self.assertNotIn('V_SEGMENTOS_CORTINA', codigos)

    def test_segmento_3_solo_cuenta_en_plano_u(self):
        linea = self.linea_cortina(tipoplano_cortina='LI', curva_izquierda='0.30', segmento_3='mas', segmento_3_m=2)
        self.assertNotIn('V_SEGMENTOS_CORTINA', self.codigos([linea], cross=False))

    def test_aviso_de_corte_por_panos(self):
        linea = self.Line.new(self.linea(system_id=self.cortina.id, height=2.70))
        avisos = linea._formulas_opciones()['avisos'].get('bajofalso', [])
        self.assertIn(self.Field.AVISO_PANOS, avisos)
        linea = self.Line.new(self.linea(system_id=self.cortina.id, height=2.30))
        self.assertFalse(linea._formulas_opciones()['avisos'].get('bajofalso'))

    def test_riel_desde_referencias_contra_la_combinacion(self):
        """Fila 99: un riel de Referencias se cruza por sus canales (E20029);
        5 telos a la derecha llevan riel de 5 y 7 telos el Velcrado."""
        r4, r5, rv = (r._valor_control() for r in (self.riel4, self.riel5, self.rielv))
        self.assertIn('V_PANEL_RIEL', self.codigos([self.linea_panel(5, '1', r4)], cross=False))
        self.assertNotIn('V_PANEL_RIEL', self.codigos([self.linea_panel(5, '1', r5)], cross=False))
        self.assertIn('V_PANEL_RIEL', self.codigos([self.linea_panel(7, '1', r5)], cross=False))
        self.assertNotIn('V_PANEL_RIEL', self.codigos([self.linea_panel(7, '1', rv)], cross=False))
        linea = self.Line.new(self.linea_panel(5, '1', r4))
        self.assertEqual(linea._riel_tipo_label(r4), '4 rieles')

    def test_velcrado_y_riel_de_6_con_el_mismo_producto(self):
        """El Riel Velcrado puede ser el mismo producto del riel de 6: cada
        línea se distingue por su valor (ref-<id>)."""
        seis = self.env['safra.fabric.color'].create({
            'fabric_id': self.rielv.fabric_id.id, 'product_tmpl_id': self.rielv.product_tmpl_id.id,
            'etiqueta': '6 rieles', 'canales': 6})
        linea = self.Line.new(self.linea_panel(7, '1', seis._valor_control()))
        self.assertEqual(linea._riel_tipo_info(seis._valor_control()), 6)
        self.assertEqual(linea._riel_tipo_info(self.rielv._valor_control()), 'velcrado')

    def test_riel_auto_toma_el_de_la_combinacion(self):
        """Fila 99, obs. 2: «Auto» usa el riel de la combinación."""
        self.assertEqual(self.Line.new(self.linea_panel(7, '1', 'auto'))._riel_auto_resuelto(), 'Riel Velcrado')
        self.assertEqual(self.Line.new(self.linea_panel(5, '1', 'auto'))._riel_auto_resuelto(), 'riel de 5 vías')
        self.assertEqual(self.Line.new(self.linea_panel(5, '1', 'r5'))._riel_auto_resuelto(), '')

    # --- Fila 118: Dobladillo o Bajo falso por fórmula ---------------------

    def ofrecidas(self, alto, color=None):
        linea = self.Line.new(self.linea(system_id=self.cortina.id, height=alto,
                                         color_id=(color or self.blanco).id,
                                         fabric_id=(color or self.blanco).fabric_id.id))
        return set(linea._opciones_por_formula().get('bajofalso', []))

    def test_dobladillo_segun_alto_y_rollo(self):
        """Rollo de 2,50 m: cada dobladillo cabe si alto ≤ rollo − su
        constante; sin dobladillo posible, bajo falso hasta rollo + 12 cm, y
        más arriba se corta por paños y se elige el dobladillo (reunión
        22-oct: el corte por paños es un aviso, no una opción)."""
        casos = {
            2.20: {'BN_FLTE', 'BN_03', 'BN_10', 'BN_15'},
            2.30: {'BN_FLTE', 'BN_03', 'BN_10'},
            2.41: {'BN_FLTE'},
            2.45: {'BN_FALSO'},
            2.70: {'BN_FLTE', 'BN_03', 'BN_10', 'BN_15'},
        }
        for alto, esperadas in casos.items():
            with self.subTest(alto=alto):
                self.assertEqual(self.ofrecidas(alto), esperadas)

    def test_dobladillo_sin_ancho_de_rollo(self):
        """Sin U_Ancho en la tela se ofrecen los dobladillos como antes."""
        self.assertEqual(self.ofrecidas(3.5, self.pesada), {'BN_FLTE', 'BN_03', 'BN_10', 'BN_15'})

    def test_e20037_opcion_que_no_aplica_por_formula(self):
        no_cabe = self.linea(system_id=self.cortina.id, height=2.30,
                             attribute_values={'bajofalso': 'BN_15'})
        self.assertIn('V_OPCION_FORMULA', self.codigos([no_cabe], cross=False))
        cabe = self.linea(system_id=self.cortina.id, height=2.30,
                          attribute_values={'bajofalso': 'BN_10'})
        self.assertNotIn('V_OPCION_FORMULA', self.codigos([cabe], cross=False))

    def test_formula_editable_sin_desarrollo(self):
        """El funcional cambia la constante en el Catálogo de campos y el
        portal la respeta; una fórmula con error no se deja guardar."""
        quince = self._campo('bajofalso').option_ids.filtered(lambda o: o.value == 'BN_15')
        quince.formula = quince.formula.replace('dobladillo_inferior = 0.21', 'dobladillo_inferior = 0.15')
        self.assertIn('BN_15', self.ofrecidas(2.30))
        quince.formula = 'not ancho_rollo or alto <= ancho_rollo - 0.15'
        self.assertIn('BN_15', self.ofrecidas(2.30))
        with self.assertRaises(ValidationError):
            quince.formula = 'alto <= ancho_rollo -'

    def test_siembra_una_sola_vez(self):
        """Las fórmulas iniciales se siembran una vez: una actualización no
        pisa lo que el funcional edite."""
        Param = self.env['ir.config_parameter'].sudo()
        Param.set_param('website_quotes_safra.seed_formulas_dobladillo', False)
        self.Field._seed_formulas_dobladillo()
        quince = self._campo('bajofalso').option_ids.filtered(lambda o: o.value == 'BN_15')
        quince.formula = 'alto <= 9'
        self.Field._seed_formulas_dobladillo()
        self.assertEqual(quince.formula, 'alto <= 9')

    def test_formulas_de_la_primera_version_pasan_a_la_matriz(self):
        """Las fórmulas sembradas con constantes sueltas pasan a la forma de
        la matriz (dobladillo superior, inferior, riel); las editadas no."""
        opciones = {o.value: o for o in self._campo('bajofalso').option_ids}
        for value, formula in self.Field._S15_DOBLADILLO_ANTERIOR.items():
            opciones[value].formula = formula
        opciones['BN_PANOS'].formula = 'alto > 9'
        self.env['ir.config_parameter'].sudo().set_param(
            'website_quotes_safra.seed_formulas_dobladillo', '1')
        self.Field._seed_formulas_dobladillo()
        nuevas = {v: f for v, _n, f in self.Field.SPRINT15_DOBLADILLO}
        self.assertEqual(opciones['BN_15'].formula, nuevas['BN_15'])
        self.assertIn('dobladillo_inferior = 0.21', opciones['BN_15'].formula)
        self.assertEqual(opciones['BN_FALSO'].formula, nuevas['BN_FALSO'])
        self.assertEqual(opciones['BN_PANOS'].formula, 'alto > 9')

    def test_mando_y_escuadras_se_guardan(self):
        """Los valores por sistema (mando 4 = Bastón) y las escuadras desde
        Referencias ya no fallan al guardar."""
        quote = self.env['safra.quote'].create({
            'partner_id': self.env.user.partner_id.id,
            'line_ids': [(0, 0, self.linea(mando_position='4', escuadras='ZT-ESC'))]})
        self.assertEqual((quote.line_ids.mando_position, quote.line_ids.escuadras), ('4', 'ZT-ESC'))

    def test_opciones_del_campo_en_el_sistema(self):
        """La ficha «Opciones» muestra los valores propios del sistema (los
        que se escriben en «Solo con los valores»), no los del catálogo."""
        apertura = self.mapeo('apertura', '11')
        self.assertEqual(apertura.display_name, '%s · %s' % (apertura.system_id.name, apertura.field_id.name))
        self.assertEqual(apertura.option_count, len(apertura.option_ids))
        self.assertIn(('1', 'Derecha'), self.opciones(apertura))
        self.assertEqual(apertura.catalog_option_ids, apertura.field_id.option_ids)
        accion = apertura.action_open_opciones()
        self.assertEqual((accion['res_model'], accion['res_id']), ('safra.system.field', apertura.id))


@tagged('post_install', '-at_install', 'safra')
class TestPortalSprint15(HttpCase, Sprint15Common):
    """Lo que recibe el portal en el Sprint 1.5."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.usuario = new_test_user(cls.env, login='safra_portal_15', groups='base.group_portal')

    def setUp(self):
        super().setUp()
        self.authenticate('safra_portal_15', 'safra_portal_15')

    def campo_config(self, sistema, code):
        config = self.make_jsonrpc_request('/cotizador/ajax/config', {'system_id': sistema.id})
        return config, next(f for f in config['fields'] if f['code'] == code)

    def test_opciones_con_dependencia(self):
        _config, telo = self.campo_config(self.panel, 'posicion_telo')
        deps = {o['value']: (o['dep'], o['depv']) for o in telo['options']}
        self.assertEqual(deps['3'], ('apertura', '4'))
        self.assertEqual(deps['ninguno'], ('apertura', '5'))

    def test_rieles_con_canales_y_velcrado(self):
        _config, riel = self.campo_config(self.panel, 'riel_tipo')
        por_valor = {o['value']: o for o in riel['options']}
        self.assertEqual(por_valor[self.riel5._valor_control()]['canales'], 5)
        self.assertEqual(por_valor[self.rielv._valor_control()]['velcrado'], 1)

    def test_dobladillo_por_formula_en_el_portal(self):
        _config, bajo = self.campo_config(self.cortina, 'bajofalso')
        self.assertTrue(all(o['fml'] for o in bajo['options']))
        res = self.make_jsonrpc_request('/cotizador/ajax/opciones_formula', {
            'system_id': self.cortina.id,
            'campos': {'width': '1.5', 'height': '2.45', 'fabric_id': str(self.tela.id),
                       'color_id': str(self.blanco.id)}})
        self.assertEqual(res['opciones']['bajofalso'], ['BN_FALSO'])

    def test_tela_con_marca_de_bolsillo(self):
        self.tela.permite_bolsillo = True
        config, _campo = self.campo_config(self.enrollable, 'bolsillo_size')
        telas = {t['name']: t for t in config['fabrics']}
        self.assertTrue(telas['Tela Prueba']['bolsillo'])
        self.assertFalse(telas['Tela Pesada']['bolsillo'])
