# -*- coding: utf-8 -*-
from odoo.tests import tagged

from .common import SafraCommon


@tagged('post_install', '-at_install', 'safra')
class TestCampoVacio(SafraCommon):
    """9-nov: los números del maestro distinguen «sin digitar» de «digitado en 0»."""

    def producto(self, **vals):
        return self.env['product.template'].create(dict({'name': 'Color Vacío Prueba'}, **vals))

    def test_vacio_y_cero_son_distintos(self):
        Product = self.env['product.template']
        vacio, cero, lleno = self.producto(), self.producto(safra_u_ancho=0), self.producto(safra_u_ancho=2.5)
        self.assertEqual([vacio.safra_u_ancho, cero.safra_u_ancho, lleno.safra_u_ancho], [False, 0.0, 2.5])
        self.assertEqual(vacio.read(['safra_u_ancho'])[0]['safra_u_ancho'], False)
        self.assertEqual(cero.read(['safra_u_ancho'])[0]['safra_u_ancho'], 0.0)
        ids = (vacio | cero | lleno).ids
        self.assertEqual(Product.search([('id', 'in', ids), ('safra_u_ancho', '=', False)]), vacio)
        self.assertEqual(Product.search([('id', 'in', ids), ('safra_u_ancho', '=', 0)]), cero)
        # En la base el vacío es NULL y el 0 es 0.
        self.env.flush_all()
        self.env.cr.execute('SELECT id, safra_u_ancho FROM product_template WHERE id IN %s', [tuple(ids)])
        self.assertEqual(dict(self.env.cr.fetchall()), {vacio.id: None, cero.id: 0.0, lleno.id: 2.5})

    def test_digitar_cero_y_borrar(self):
        prod = self.producto()
        prod.safra_u_ancho = 0
        self.assertEqual(prod.read(['safra_u_ancho'])[0]['safra_u_ancho'], 0.0)
        prod.safra_u_ancho = False
        self.assertIs(prod.read(['safra_u_ancho'])[0]['safra_u_ancho'], False)

    def test_pantalla_y_exportacion(self):
        self.assertTrue(self.env['product.template'].fields_get(['safra_u_ancho'])['safra_u_ancho'].get('safra_vacio'))
        self.assertFalse(self.env['product.template'].fields_get(['list_price'])['list_price'].get('safra_vacio'))
        # La vista del producto lo recibe (el backoffice deja la casilla vacía).
        vistas = self.env['product.template'].get_views([(False, 'form')])
        self.assertTrue(vistas['models']['product.template']['fields']['safra_u_ancho'].get('safra_vacio'))
        datos = (self.producto() | self.producto(safra_u_ancho=0)).export_data(['safra_u_ancho'])['datas']
        self.assertEqual([d[0] for d in datos], ['', 0.0])

    def test_calculos_sin_cambio(self):
        # El corte de la tela trata el vacío como hoy el 0: «sin ancho del rollo».
        color = self.env['safra.fabric.color'].create({
            'fabric_id': self.tela.id, 'product_tmpl_id': self.producto().id})
        linea = self.env['safra.quote.line'].new({'fabric_id': self.tela.id, 'color_id': color.id})
        self.assertFalse(linea._ancho_rollo())
        self.assertEqual(linea._ancho_rollo() * 2, 0)

    def test_todos_los_numeros_del_maestro(self):
        campos = {
            'product.template': ['safra_u_peso', 'safra_u_ancho_min', 'safra_torque', 'safra_carga_maxima',
                                 'safra_u_cantidad_canales', 'safra_u_cantidad_paquete'],
            'safra.fabric': ['peso_gm2', 'grosor_mm', 'max_anadidos', 'cant_min_stock'],
            'safra.fabric.color': ['canales'],
            'safra.system': ['tech_width_max', 'exh_height_min', 'factor_confeccion', 'weight_factor'],
            'safra.structure.rule': ['espacio_eje_techo', 'diametro_tubo', 'carga_maxima'],
            'safra.lamas.rule': ['aux', 'adicional'],
            'safra.field.option': ['consumo_dobladillo', 'peso_gm', 'segmentos'],
        }
        for modelo, nombres in campos.items():
            info = self.env[modelo].fields_get(nombres)
            for nombre in nombres:
                self.assertTrue(info[nombre].get('safra_vacio'), '%s.%s' % (modelo, nombre))
        # Lo que no es un dato del maestro sigue igual.
        self.assertFalse(self.env['safra.quote.line'].fields_get(['width'])['width'].get('safra_vacio'))

    def test_entero_vacio_y_cero(self):
        Fabric = self.env['safra.fabric']
        vacia = Fabric.create({'code': 'ZT-VAC', 'name': 'Vacía'})
        cero = Fabric.create({'code': 'ZT-CER', 'name': 'Cero', 'max_anadidos': 0})
        self.assertEqual([vacia.max_anadidos, cero.max_anadidos], [False, 0])
        self.assertEqual(Fabric.search([('id', 'in', (vacia | cero).ids), ('max_anadidos', '=', False)]), vacia)
        # Con un valor por defecto, el registro nuevo lo trae (no queda vacío).
        self.assertEqual(self.env['safra.system'].create({'code': 'ZTV', 'name': 'V'}).weight_factor, 1.0)
