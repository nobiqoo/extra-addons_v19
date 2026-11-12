# -*- coding: utf-8 -*-
from odoo.tests import HttpCase, new_test_user, tagged

from .common import SafraCommon


@tagged('post_install', '-at_install', 'safra')
class TestPortal(HttpCase, SafraCommon):
    """Rutas del portal con un usuario de portal: lo que recibe el JS."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.usuario = new_test_user(cls.env, login='safra_portal_prueba',
                                    groups='base.group_portal')

    def setUp(self):
        super().setUp()
        self.authenticate('safra_portal_prueba', 'safra_portal_prueba')

    def rpc(self, ruta, **params):
        return self.make_jsonrpc_request(ruta, params)

    def test_configuracion_del_formulario(self):
        # Las opciones de respaldo del riel salen mientras la categoría no
        # tenga referencias (las de la base pueden ser de otros sistemas).
        self.env['safra.fabric'].search(
            [('category_id', '=', self._campo('riel_tipo').ref_category_id.id)]).active = False
        config = self.rpc('/cotizador/ajax/config', system_id=self.panel.id)
        codigos = [f['code'] for f in config['fields']]
        self.assertTrue(set(codigos) >= {'width', 'quantity_lamas', 'tamano_traslape', 'riel_tipo'})
        # Ordenados por sección y luego por orden dentro del sistema.
        orden = [(f['section_seq'], f['seq']) for f in config['fields']]
        self.assertEqual(orden, sorted(orden))
        riel = next(f for f in config['fields'] if f['code'] == 'riel_tipo')
        self.assertIn('Riel Velcrado', [o['label'] for o in riel['options']])
        self.assertIn('Tela Prueba', [t['name'] for t in config['fabrics']])
        self.assertEqual(set(config['aperturas_formula']),
                         {'unilateral_derecha', 'unilateral_izquierda', 'centro', 'extremos'})

    def test_sistema_restringido_a_otro_grupo(self):
        self.panel.group_ids = self.env.ref('base.group_system')
        self.assertEqual(self.rpc('/cotizador/ajax/config', system_id=self.panel.id),
                         {'fields': []})

    def test_tabla_de_combinaciones(self):
        res = self.rpc('/cotizador/ajax/panel_lamas', width=2.4, traslape=0.08,
                       system_id=self.panel.id, campos={'height': 2.0})
        self.assertEqual(len(res['rows']), 12)
        self.assertIsNone(res['rango'])
        vacio = self.rpc('/cotizador/ajax/panel_lamas', width=0.9, traslape=0.08,
                         system_id=self.panel.id)
        self.assertEqual(vacio['rows'], [])
        self.assertEqual(vacio['rango']['wmin'], 1.16)

    def test_validar_como_el_formulario(self):
        """Los nombres del formulario llevan el índice de la persiana."""
        form = {'system_id_0': self.enrollable.id, 'fabric_id_0': self.tela.id,
                'color_id_0': self.blanco.id, 'width_0': '3,5', 'height_0': '1.8',
                'quantity_0': '1', 'location_0': 'Sala', 'aligned_0': 'on'}
        codigos = {i['code'] for i in self.rpc('/cotizador/ajax/validar', **form)}
        self.assertIn('V_RANGO_ANCHO', codigos)
        self.assertIn('V_ALINEADO_MIN', codigos)
        # «Guardar persiana» manda single y no corre las reglas del pedido.
        codigos = {i['code'] for i in self.rpc('/cotizador/ajax/validar', single=1, **form)}
        self.assertIn('V_RANGO_ANCHO', codigos)
        self.assertNotIn('V_ALINEADO_MIN', codigos)

    def test_lineas_despues_de_un_hueco(self):
        """Borrar una persiana deja huecos en los índices (arreglo 28-sep)."""
        form = {}
        for idx in (0, 2):
            form.update({'system_id_%d' % idx: self.enrollable.id,
                         'fabric_id_%d' % idx: self.tela.id,
                         'color_id_%d' % idx: self.blanco.id,
                         'width_%d' % idx: '1.5', 'height_%d' % idx: '1.8',
                         'quantity_%d' % idx: '1', 'location_%d' % idx: ''})
        issues = self.rpc('/cotizador/ajax/validar', **form)
        self.assertEqual(sorted(i['line'] for i in issues if i['code'] == 'V_LOCALIZACION'), [1, 2])

    def test_opciones_por_referencia(self):
        """Sprint 1.4: cada opción lleva el código de su referencia (para
        las dependencias «ref:CÓDIGO»); la línea «Sin …» va sin prefijo."""
        categoria = self.env['safra.product.option'].create(
            {'name': 'Cenefa prueba', 'type': 'ref_categoria'})
        campo = self.env['safra.field'].create({
            'code': 'zt_cenefa', 'name': 'Cenefa prueba', 'field_type': 'ref_categoria',
            'ref_category_id': categoria.id, 'section_id': self._campo('cenefa_panel').section_id.id})
        campo.option_ids = [(0, 0, {'value': '1', 'name': 'Opción de catálogo'})]
        self.env['safra.system.field'].create(
            {'system_id': self.enrollable.id, 'field_id': campo.id, 'sequence': 999})

        def opciones():
            config = self.rpc('/cotizador/ajax/config', system_id=self.enrollable.id)
            return next(f['options'] for f in config['fields'] if f['code'] == 'zt_cenefa')

        # Sin referencias en la categoría: respaldo en las opciones del campo.
        self.assertEqual([o['label'] for o in opciones()], ['Opción de catálogo'])
        Fabric, Color = self.env['safra.fabric'], self.env['safra.fabric.color']
        sin = Fabric.create({'code': 'ZT-CSIN', 'name': 'Sin cenefa', 'category_id': categoria.id})
        Color.create({'fabric_id': sin.id, 'code': 'ZT-CSIN-0', 'name': 'Sin cenefa'})
        pvc = Fabric.create({'code': 'ZT-CPVC', 'name': 'Cenefa PVC', 'category_id': categoria.id})
        producto = self.env['product.template'].create(
            {'name': 'Cenefa PVC Clásica', 'safra_code': 'ZTCPVC', 'safra_is_color': True,
             'safra_u_forrado': True})
        Color.create({'fabric_id': pvc.id, 'product_tmpl_id': producto.id, 'etiqueta': 'Clásica'})
        por_etiqueta = {o['label']: o for o in opciones()}
        self.assertEqual(set(por_etiqueta), {'Sin cenefa', 'Cenefa PVC Clásica'})
        self.assertEqual(por_etiqueta['Cenefa PVC Clásica']['ref'], 'ZT-CPVC')
        self.assertEqual(por_etiqueta['Cenefa PVC Clásica']['forrado'], 1)
        self.assertEqual((por_etiqueta['Sin cenefa']['ref'], por_etiqueta['Sin cenefa']['sin']),
                         ('ZT-CSIN', 1))

    def test_pagina_del_cotizador(self):
        res = self.url_open('/cotizador')
        self.assertEqual(res.status_code, 200)
        self.assertIn('PRUEBA ENROLLABLE', res.text)
