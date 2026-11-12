# -*- coding: utf-8 -*-
import logging
import math

from odoo import api, fields, models

from .fields_vacio import FloatVacio
from . import safra_reglas_17 as R17
from .safra_panel import evaluar_formula

_logger = logging.getLogger(__name__)


def _num(valor):
    """Variable numérica de una fórmula: False si el dato del maestro está
    sin digitar (las fórmulas lo distinguen con vacio()); si no, el número
    (0 cuando no aplica)."""
    return False if valor is False else (valor or 0.0)


class SafraStructureRule(models.Model):
    """Tabla de selección de estructura por rango de ancho.

    Réplica configurable de las hojas 3/4/5 del Excel
    "matriz_unificada_variables": para un sistema, tipo de accionamiento y
    (opcionalmente) tipo de cabezal, el rango de ancho determina el tubo,
    mecanismo, soporte, terminal y cabezal, junto con las constantes que
    alimentan las fórmulas de alto/peso máximo y los consumos.
    """
    _name = 'safra.structure.rule'
    _description = 'Estructura por rango de ancho'
    _order = 'sequence, width_from, id'

    name = fields.Char(string='Nombre', compute='_compute_name', store=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    system_ids = fields.Many2many(
        'safra.system', 'safra_structure_rule_system_rel', 'rule_id', 'system_id',
        string='Sistemas', required=True,
    )
    drive_type = fields.Selection([
        ('any', 'Ambos'),
        ('manual', 'Manual'),
        ('motor', 'Motor'),
    ], string='Tipo accionamiento', required=True, default='any',
        help='Manual aplica cuando el cliente marca "Con Motor = No"; '
             'Motor cuando marca "Con Motor = Sí"; Ambos aplica siempre.')
    cabezal_type = fields.Selection([
        ('na', 'No aplica'),
        ('cuadrado', 'Cuadrado'),
        ('redondo', 'Redondo'),
    ], string='Tipo cabezal', required=True, default='na',
        help='Para sistemas con cabezal (hoja 4 del Excel) la tabla se '
             'diferencia por el tipo de cabezal escogido por el cliente.')

    width_from = fields.Float(string='Ancho desde (m)', digits=(6, 3), required=True)
    width_to = fields.Float(string='Ancho hasta (m)', digits=(6, 3), required=True)

    # Estructura resultante. Hoy texto (nombres del portal del cliente); cuando
    # exista la parametrización del maestro de referencias pasarán a ser
    # desplegables por categoría (TUBO, MECANISMO, SOPORTE, TERMINAL, CABEZAL).
    tubo = fields.Char(string='Tubo', required=True)
    mecanismo = fields.Char(string='Mecanismo')
    soporte = fields.Char(string='Soporte')
    terminal = fields.Char(string='Terminal')
    cabezal = fields.Char(string='Cabezal')
    perfil = fields.Char(string='Perfiles permitidos')

    # Constantes de consumo (metros; negativos = descuento sobre el ancho).
    desc_mando = FloatVacio(string='Descuento mando (m)', digits=(6, 3))
    desc_terminal = FloatVacio(string='Descuento terminal (m)', digits=(6, 3))
    desc_soporte = FloatVacio(string='Descuento soporte (m)', digits=(6, 3))
    desc_corona = FloatVacio(string='Descuento corona (m)', digits=(6, 3))
    aumento_tela = FloatVacio(string='Aumento tela del tubo (m)', digits=(6, 3))
    aumento_perfil = FloatVacio(string='Aumento/disminución tela perfil (m)', digits=(6, 3))

    # Constantes para las fórmulas de alto/peso máximo.
    espacio_eje_techo = FloatVacio(
        string='Espacio eje central a techo (mm)', digits=(6, 2),
        help='Del soporte (hoja 3) o del cabezal (hoja 4) asociado al tubo.')
    diametro_tubo = FloatVacio(string='Diámetro externo tubo (mm)', digits=(6, 2))
    carga_maxima = FloatVacio(
        string='Carga máxima (g)', digits=(12, 2),
        help='Del mecanismo (manual) o del motor (motorizado).')

    # Revisión cálculo de tubo (27-oct, punto 1.1): cada pieza se elige de
    # Referencias por categoría y los valores de las fórmulas salen del
    # producto de esa referencia (espacio al techo del cabezal o, sin
    # cabezal, del soporte; diámetro y aumento de tela del tubo; carga del
    # mecanismo). Si la referencia no tiene el valor, se usa el de la fila.
    # El nombre (texto) se conserva: los kits de motor y la unificación
    # buscan el tubo por nombre.
    tubo_ref_id = fields.Many2one(
        'safra.fabric.color', string='Tubo (referencia)',
        domain="[('fabric_id.category_id.name', '=ilike', 'tubo')]")
    mecanismo_ref_id = fields.Many2one(
        'safra.fabric.color', string='Mecanismo (referencia)',
        domain="[('fabric_id.category_id.name', '=ilike', 'mecanismo')]")
    soporte_ref_id = fields.Many2one(
        'safra.fabric.color', string='Soporte (referencia)',
        domain="[('fabric_id.category_id.name', '=ilike', 'soporte')]")
    terminal_ref_id = fields.Many2one(
        'safra.fabric.color', string='Terminal (referencia)',
        domain="[('fabric_id.category_id.name', '=ilike', 'terminal')]")
    cabezal_ref_id = fields.Many2one(
        'safra.fabric.color', string='Cabezal (referencia)',
        domain="[('fabric_id.category_id.name', '=ilike', 'cabezal')]",
        help='Su tipo (redondo o cuadrado) es el que se compara con el Tipo de cabezal '
             'que elige el cliente en el portal.')
    espacio_usado = fields.Float(string='Espacio eje a techo usado (mm)',
                                 compute='_compute_valores_usados', digits=(6, 2))
    diametro_usado = fields.Float(string='Diámetro del tubo usado (mm)',
                                  compute='_compute_valores_usados', digits=(6, 2))
    carga_usada = fields.Float(string='Carga máxima usada (g)',
                               compute='_compute_valores_usados', digits=(12, 2))
    aumento_usado = fields.Float(string='Aumento tela del tubo usado (m)',
                                 compute='_compute_valores_usados', digits=(6, 3))

    def _constantes(self):
        """Valores de las fórmulas de esta fila: los del producto de cada
        referencia y, si no los tiene, los digitados en la fila."""
        self.ensure_one()
        cab = self.cabezal_ref_id.product_tmpl_id
        sop = self.soporte_ref_id.product_tmpl_id
        tubo = self.tubo_ref_id.product_tmpl_id
        mec = self.mecanismo_ref_id.product_tmpl_id
        return {
            'espacio': cab.safra_espacio_eje_techo or sop.safra_espacio_eje_techo or self.espacio_eje_techo,
            'diametro': tubo.safra_diametro_tubo or self.diametro_tubo,
            'carga': mec.safra_carga_maxima or self.carga_maxima,
            'aumento': tubo.safra_aumento_tela_tubo or self.aumento_tela,
        }

    @api.depends('espacio_eje_techo', 'diametro_tubo', 'carga_maxima', 'aumento_tela',
                 'tubo_ref_id', 'mecanismo_ref_id', 'soporte_ref_id', 'cabezal_ref_id')
    def _compute_valores_usados(self):
        for rec in self:
            c = rec._constantes()
            rec.espacio_usado, rec.diametro_usado = c['espacio'], c['diametro']
            rec.carga_usada, rec.aumento_usado = c['carga'], c['aumento']

    @api.onchange('tubo_ref_id', 'mecanismo_ref_id', 'soporte_ref_id', 'terminal_ref_id', 'cabezal_ref_id')
    def _onchange_referencias(self):
        """Al elegir la referencia se llena el nombre de la pieza solo si
        está vacío. Revisión 03-nov: el nombre ya escrito no se cambia,
        porque con él se emparejan la Unificación Mando, los kits de motor,
        la constante por tubo y las secuencias (al elegir la referencia del
        R16, «R16» pasaba a «TUBO 1 1/2' (R16)»). El tipo del cabezal se toma
        al guardar (_tipo_cabezal)."""
        for campo in ('tubo', 'mecanismo', 'soporte', 'terminal', 'cabezal'):
            ref = self['%s_ref_id' % campo]
            if ref and not (self[campo] or '').strip():
                self[campo] = ref._portal_label() or ref.product_tmpl_id.name

    @api.depends('tubo', 'drive_type', 'cabezal_type', 'width_from', 'width_to')
    def _compute_name(self):
        for rec in self:
            parts = [rec.tubo or '?']
            if rec.drive_type and rec.drive_type != 'any':
                parts.append(dict(rec._fields['drive_type'].selection).get(rec.drive_type))
            if rec.cabezal_type and rec.cabezal_type != 'na':
                parts.append(dict(rec._fields['cabezal_type'].selection).get(rec.cabezal_type))
            rec.name = '%s (%s - %s m)' % (' / '.join(parts), rec.width_from, rec.width_to)

    @api.model
    def find_rule(self, system, width, motorized=False, cabezal=None):
        """Regla aplicable para un sistema, ancho y accionamiento dados.

        `cabezal` ('cuadrado'/'redondo') filtra cuando el sistema diferencia
        por tipo de cabezal; si no hay regla específica se cae a las 'na'.
        """
        if not system or not width:
            return self.browse()
        domain = [
            ('system_ids', 'in', system.id),
            ('drive_type', 'in', ['any', 'motor' if motorized else 'manual']),
            ('width_from', '<=', width),
            ('width_to', '>=', width),
        ]
        rules = self.search(domain)
        if cabezal:
            specific = rules.filtered(lambda r: r.cabezal_type == cabezal)
            if specific:
                return specific[0]
        return (rules.filtered(lambda r: r.cabezal_type == 'na') or rules)[:1]

    @api.model
    def tubos_ordenados(self, system, motorized=False):
        """Sprint 1.3 (fila 73): tubos del sistema de menor a mayor, en el
        orden en que aparecen en la tabla de estructura al crecer el ancho
        (para el accionamiento dado). Es el orden de la Unificación Mando."""
        if not system:
            return []
        rules = self.search([
            ('system_ids', 'in', system.id),
            ('drive_type', 'in', ['any', 'motor' if motorized else 'manual']),
        ], order='width_from, id')
        tubos = []
        for rule in rules:
            if rule.tubo and rule.tubo not in tubos:
                tubos.append(rule.tubo)
        return tubos

    @api.model
    def tubos_secuencia(self, system):
        """Revisión cálculo de tubo (27-oct, error 2): orden de los tubos de
        una secuencia que mezcla persianas manuales y motorizadas. Va por
        diámetro cuando la tabla lo tiene en todos los tubos (si no, por el
        ancho desde el que se usan); a igual diámetro, primero el manual
        (R16 antes que Tubo 40mm)."""
        if not system:
            return []
        datos = {}
        for rule in self.search([('system_ids', 'in', system.id)], order='width_from, id'):
            if not rule.tubo:
                continue
            d = datos.setdefault(rule.tubo, {'diam': 0.0, 'desde': rule.width_from,
                                             'solo_motor': True, 'pos': len(datos)})
            d['diam'] = max(d['diam'], rule.diametro_tubo or 0.0)
            d['solo_motor'] = d['solo_motor'] and rule.drive_type == 'motor'
        con_diametro = all(d['diam'] for d in datos.values())
        return sorted(datos, key=lambda t: (
            datos[t]['diam'] if con_diametro else datos[t]['desde'],
            datos[t]['solo_motor'], datos[t]['pos']))

    @api.model_create_multi
    def create(self, vals_list):
        rules = super().create(vals_list)
        rules._seed_opciones_tubo()
        rules.filtered('cabezal_ref_id')._tipo_cabezal()
        return rules

    def write(self, vals):
        res = super().write(vals)
        if 'tubo' in vals:
            self._seed_opciones_tubo()
        if 'cabezal_ref_id' in vals:
            self.filtered('cabezal_ref_id')._tipo_cabezal()
        return res

    def _tipo_cabezal(self):
        """Revisión cálculo de tubo (punto 1.1): el Tipo cabezal de la fila
        (que se compara con el que elige el cliente) sale del nombre del
        cabezal de Referencias: redondo o cuadrado."""
        for rec in self:
            nombre = (rec.cabezal_ref_id._portal_label() or rec.cabezal or '').lower()
            tipo = 'redondo' if 'redondo' in nombre else 'cuadrado' if 'cuadrado' in nombre else None
            if tipo and rec.cabezal_type != tipo:
                super(SafraStructureRule, rec).write({'cabezal_type': tipo})

    @api.model
    def _seed_opciones_tubo(self, _ids=None):
        """Reunión 15-oct (fila 68): cada tubo de la tabla existe como
        opción «Tubo» para marcarlo en los insumos del maestro (campo
        Tubos). Idempotente; corre en cada actualización y al crear o
        cambiar una regla."""
        Option = self.env['safra.product.option'].sudo().with_context(active_test=False)
        existentes = {(o.name or '').strip().lower() for o in Option.search([('type', '=', 'tubo')])}
        orden = 10
        for tubo in self.sudo().with_context(active_test=False).search(
                [], order='width_from, id').mapped('tubo'):
            nombre = (tubo or '').strip()
            if nombre and nombre.lower() not in existentes:
                Option.create({'type': 'tubo', 'name': nombre, 'sequence': orden})
                existentes.add(nombre.lower())
            orden += 10
        return True

    @api.model
    def _ajuste_tubos_2en1(self, _ids=None):
        """Revisión cálculo de tubo (27-oct, hoja 5), una sola vez por base:
        Enrollable 2 en 1 y Sheer 2 en 1 eligen el tubo solo por ancho (sin
        alto ni peso máximo): R8 manual 0,50-2,00 m, R16 manual 2,01-2,50 m
        y Tubo 40mm motorizado 0,70-2,50 m. Solo si la regla R16 sigue como
        se sembró (0,50-2,50 m para ambos accionamientos)."""
        Param = self.env['ir.config_parameter'].sudo()
        marca = 'website_quotes_safra.ajuste_tubos_2en1'
        if Param.get_param(marca):
            return
        Param.set_param(marca, '1')
        r16 = self.env.ref('website_quotes_safra.struct_2en1_r16', raise_if_not_found=False)
        if not r16 or (r16.drive_type, r16.width_from, r16.width_to) != ('any', 0.5, 2.5):
            return
        r16.write({'drive_type': 'manual', 'width_from': 2.01})
        comun = {'system_ids': [(6, 0, r16.system_ids.ids)], 'cabezal_type': 'na',
                 'soporte': r16.soporte, 'cabezal': r16.cabezal, 'perfil': r16.perfil}
        self.sudo().create([
            dict(comun, drive_type='manual', width_from=0.5, width_to=2.0, tubo='R8',
                 mecanismo='R8SL', terminal='Terminal R8SL'),
            dict(comun, drive_type='motor', width_from=0.7, width_to=2.5,
                 tubo='Tubo 40mm (Motorizado)', mecanismo='MOTOR', terminal=r16.terminal),
        ])

    @api.model
    def _marcar_tubo_solo_ancho(self, _ids=None):
        """Revisión cálculo de tubo (hoja 5), una sola vez por base: Enrollable
        2 en 1 y Sheer 2 en 1 quedan con «Tubo solo por ancho» (sin alto ni
        peso máximo)."""
        Param = self.env['ir.config_parameter'].sudo()
        marca = 'website_quotes_safra.tubo_solo_ancho'
        if Param.get_param(marca):
            return
        Param.set_param(marca, '1')
        self.env['safra.system'].sudo().with_context(active_test=False).search(
            [('code', 'in', ('32', '61'))]).write({'tubo_solo_ancho': True})

    # Revisión cálculo de tubo (27-oct): categorías de Referencias de la
    # estructura (punto 1.1).
    CATEGORIAS_ESTRUCTURA = ('Tubo', 'Mecanismo', 'Soporte', 'Terminal', 'Cabezal')

    @api.model
    def _ajuste_revision_tubo(self, _ids=None):
        """Categorías de la estructura en Referencias (idempotente, como la
        de Embalaje) y, una sola vez por base: Venecian con las filas por
        cabezal de Enrollable Premium y Sheer Elegance (hoja 4: «ENROLLABLE
        PREMIUM, SHEER ELEGANCE, VENECIAS»), si aún no tiene filas, y en el
        tope de 5,80 m del cabezal (V_SECUENCIA_ANCHO, si la regla tiene
        sistemas)."""
        Option = self.env['safra.product.option'].sudo().with_context(active_test=False)
        for nombre in self.CATEGORIAS_ESTRUCTURA:
            if not Option.search_count([('type', '=', 'ref_categoria'), ('name', '=ilike', nombre)]):
                Option.create({'type': 'ref_categoria', 'name': nombre, 'sequence': 100})
        Param = self.env['ir.config_parameter'].sudo()
        marca = 'website_quotes_safra.ajuste_revision_tubo'
        if Param.get_param(marca):
            return
        Param.set_param(marca, '1')
        System = self.env['safra.system'].sudo().with_context(active_test=False)
        venecian = System.search([('code', '=', '04')], limit=1)
        premium = System.search([('code', '=', '06')], limit=1)
        Rule = self.sudo().with_context(active_test=False)
        if venecian and premium and not Rule.search_count([('system_ids', 'in', venecian.id)]):
            Rule.search([('system_ids', 'in', premium.id), ('cabezal_type', '!=', 'na')]).write(
                {'system_ids': [(4, venecian.id)]})
        regla = self.env['safra.validation.rule'].sudo().with_context(active_test=False).search(
            [('code', '=', 'V_SECUENCIA_ANCHO')], limit=1)
        if venecian and regla.system_ids and venecian not in regla.system_ids:
            regla.system_ids = [(4, venecian.id)]

    @api.model
    def _insumos_sin_stock(self, tubo):
        """Reunión 15-oct (fila 68): insumos de estructura del tubo que no
        tienen stock. Son los productos del maestro con ese tubo en «Tubos»
        que no son opciones del portal (las líneas de las referencias, como
        los cabezales, se filtran aparte). Solo cuentan los productos con
        inventario (almacenables)."""
        Product = self.env['product.template'].sudo()
        nombre = (tubo or '').strip().lower()
        if not nombre:
            return Product
        opciones = self.env['safra.product.option'].sudo().search([('type', '=', 'tubo')])
        opt = opciones.filtered(lambda o: (o.name or '').strip().lower() == nombre)
        if not opt:
            return Product
        productos = Product.search([('safra_tubo_ids', 'in', opt.ids)])
        de_portal = self.env['safra.fabric.color'].sudo().with_context(active_test=False).search(
            [('product_tmpl_id', 'in', productos.ids)]).mapped('product_tmpl_id')
        return (productos - de_portal).filtered(
            lambda p: p.is_storable and p.qty_available <= 0)

    @api.model
    def tubos_bloqueados(self, tubos):
        """{tubo: [insumos sin stock]} de los tubos dados que están
        bloqueados por falta de insumos."""
        bloqueados = {}
        for tubo in tubos or []:
            faltan = self._insumos_sin_stock(tubo)
            if faltan:
                bloqueados[tubo] = faltan.mapped('display_name')
        return bloqueados

    @api.model
    def _regla_tubo(self, system, tubo, motorized=False, cabezal=None):
        """Regla de un tubo del sistema para el accionamiento (o, si el tubo
        no está en esa tabla, la del otro) y el cabezal (o la general)."""
        dom = [('system_ids', 'in', system.id), ('tubo', '=', tubo)]
        rules = self.search(dom + [('drive_type', 'in', ['any', 'motor' if motorized else 'manual'])],
                            order='width_from, id') or self.search(dom, order='width_from, id')
        if cabezal:
            specific = rules.filtered(lambda r: r.cabezal_type == cabezal)
            if specific:
                return specific[0]
        return (rules.filtered(lambda r: r.cabezal_type == 'na') or rules)[:1]

    @api.model
    def resolve(self, system, width, motorized=False, cabezal=None, unificacion=None):
        """Regla calculada por el ancho y regla efectiva tras la
        Unificación Mando: si el cliente (o la secuencia) pide un tubo mayor
        al calculado, la estructura y los límites salen de ese tubo.
        Revisión 27-oct (error 2): en una secuencia con motor, la persiana
        manual toma el tubo motorizado de la secuencia; si el tubo no está
        en la tabla de su accionamiento, se usa la regla del otro (Tubo
        40mm con mecanismo MOTOR).
        Devuelve (regla_calculada, regla_efectiva)."""
        base = self.find_rule(system, width, motorized=motorized, cabezal=cabezal)
        if not base or not unificacion or unificacion == base.tubo:
            return base, base
        tubos = self.tubos_secuencia(system)
        if (unificacion not in tubos or base.tubo not in tubos
                or tubos.index(unificacion) <= tubos.index(base.tubo)):
            return base, base
        return base, self._regla_tubo(system, unificacion, motorized, cabezal) or base

    @api.model
    def elegir(self, system, width, height, motorized=False, cabezal=None,
               unificacion=None, **params):
        """Revisión cálculo de tubo (27-oct, error 6): la regla de resolve()
        y, si el alto digitado supera el alto máximo de su tubo, el siguiente
        tubo del accionamiento (de menor a mayor, sin mirar el rango de
        ancho, como el cuadro del Excel) con el que sí alcanza. Si ninguno
        alcanza, queda el de resolve() y su alto máximo da el error.
        `params` va a compute_limits. Devuelve {'base', 'regla', 'limites',
        'subio_de'} (subio_de = tubo que no alcanzaba, o None)."""
        base, regla = self.resolve(system, width, motorized=motorized, cabezal=cabezal,
                                   unificacion=unificacion)
        if not regla:
            return {'base': base, 'regla': regla, 'limites': {}, 'subio_de': None}
        # Hoja 5: en los sistemas «Tubo solo por ancho» no hay alto ni peso
        # máximo; queda el tubo del ancho.
        if system.tubo_solo_ancho:
            return {'base': base, 'regla': regla, 'limites': {}, 'subio_de': None}
        limites = regla.compute_limits(width, height, **params)
        elegida = regla
        if limites.get('alto_ok') is False:
            tubos = self.tubos_ordenados(system, motorized=motorized)
            siguientes = tubos[tubos.index(regla.tubo) + 1:] if regla.tubo in tubos else []
            for tubo in siguientes:
                otra = self._regla_tubo(system, tubo, motorized, cabezal)
                lim = otra.compute_limits(width, height, **params) if otra else {}
                if otra and lim.get('alto_ok') is not False:
                    elegida, limites = otra, lim
                    break
        return {'base': base, 'regla': elegida, 'limites': limites,
                'subio_de': regla.tubo if elegida != regla else None}

    @api.model
    def opciones(self, system, width, height, cabezal=None, torque=0.0, carga_motor=0.0,
                 motor_elegido=False, **params):
        """Revisión cálculo de tubo (27-oct, error 6): cuadro de altos y
        pesos máximos de cada tubo del sistema, manual y motorizado, para
        las medidas digitadas (cuadro resumen del Excel). Vacío si la tela no
        tiene peso ni grosor (no hay nada que calcular)."""
        if not system or system.tubo_solo_ancho or not (
                params.get('peso_tela') or params.get('grosor_tela')):
            return []
        filas = []
        for motor in (False, True):
            for tubo in self.tubos_ordenados(system, motorized=motor):
                regla = self._regla_tubo(system, tubo, motor, cabezal)
                if not regla or regla.drive_type not in ('any', 'motor' if motor else 'manual'):
                    continue
                lim = regla.compute_limits(width, height, torque=torque if motor else 0.0,
                                           carga_motor=carga_motor if motor else 0.0,
                                           motor_elegido=motor_elegido if motor else False,
                                           **dict(params, motor_nombre=params.get('motor_nombre') if motor else ''))
                filas.append({
                    'accionamiento': 'Motor' if motor else 'Manual', 'tubo': tubo,
                    'alto_maximo': lim.get('alto_maximo'), 'peso_total': lim.get('peso_total'),
                    'carga_maxima': lim.get('carga_maxima'),
                    'aplica_ancho': regla.width_from <= width <= regla.width_to,
                    'cumple': lim.get('alto_ok') is not False and lim.get('peso_ok') is not False,
                })
        return filas

    @staticmethod
    def nombre_tubo(tubo):
        """«tubo R24» o «Tubo 2 1/2» (sin repetir la palabra) para los mensajes."""
        tubo = tubo or ''
        return tubo if tubo.lower().startswith('tubo') else ('tubo %s' % tubo).strip()

    @api.model
    def alternativa_motor(self, system, width, height, cabezal=None, unificacion=None,
                          motores=None, **params):
        """Reunión 09-nov (fila 68, punto 3): la persiana que no se puede
        fabricar manual (sin tubo para el ancho, alto o peso mayores a los
        del mecanismo) se prueba motorizada: con cada motor del sistema que
        tenga Torque o Carga máxima en el maestro y, si ninguno lo tiene,
        con la carga de la tabla motorizada. Devuelve {'tubo', 'motor',
        'limites'} de la primera combinación que cumple, o None."""
        if not system or not width:
            return None
        base = {k: v for k, v in params.items()
                if k not in ('torque', 'carga_motor', 'motor_elegido', 'motor_nombre')}
        candidatos = [(m, dict(base, torque=m.safra_torque, carga_motor=m.safra_carga_maxima,
                               motor_elegido=True, motor_nombre=m.name))
                      for m in (motores or []) if m.safra_torque or m.safra_carga_maxima]
        if not candidatos:
            candidatos = [(None, dict(base, torque=0.0, carga_motor=0.0, motor_elegido=False))]
        for motor, p in candidatos:
            res = self.elegir(system, width, height, motorized=True, cabezal=cabezal,
                              unificacion=unificacion, **p)
            lim = res['limites']
            if res['regla'] and lim.get('alto_ok') is not False and lim.get('peso_ok') is not False:
                return {'tubo': res['regla'].tubo, 'motor': motor, 'limites': lim}
        return None

    def carga_motor(self, torque):
        """Revisión cálculo de tubo (27-oct, error 5) y reunión 30-oct (fila
        168): carga máxima (g) de un motor sobre el tubo de esta regla, con la
        fórmula de Ajustes › Tubo: alto y peso máximo (por defecto torque ×
        100 ÷ diámetro externo del tubo × 1000, como el Excel: 6 N·m en el
        tubo de 38 mm = 15.789 g)."""
        self.ensure_one()
        return self._formula_tubo('safra.formula.tubo_carga_motor', self._ctx_carga_motor(torque)) or 0.0

    def _ctx_carga_motor(self, torque):
        """Variables de la fórmula «Carga máxima del motor» en esta fila."""
        self.ensure_one()
        return {'torque': _num(torque), 'diametro_tubo': _num(self._constantes()['diametro']),
                'pi': math.pi}

    @staticmethod
    def _dato(valor, unidad, femenino=False):
        """Un dato del maestro como lo debe leer la persona: «sin digitar»
        (vacío), «digitado en 0» o el número."""
        if valor is False or valor is None:
            return 'sin digitar'
        if not valor:
            return 'digitada en 0' if femenino else 'digitado en 0'
        return ('{:,.0f}'.format(valor) if valor >= 100 else '{:g}'.format(valor)).replace(',', '.') + unidad

    def _carga_y_origen(self, torque=0.0, carga_motor=0.0, motor_elegido=False, motor_nombre=''):
        """(carga máxima, de dónde sale en palabras). Reunión 09-nov (fila
        68): con motor elegido, la de su torque (fórmula de Ajustes) o, sin
        torque, su Carga maxima; un Torque digitado en 0 es 0. Sin motor, la
        del producto del mecanismo o la de la fila. Vacío (False) si no hay
        dato con qué comparar. El texto dice cómo está cada dato (sin
        digitar, digitado en 0 o su valor) para que se sepa qué corregir."""
        self.ensure_one()
        if motor_elegido:
            por_torque = self.carga_motor(torque) if torque else 0.0
            if por_torque:
                carga = por_torque
            elif carga_motor is not False and carga_motor is not None:
                carga = carga_motor or 0.0
            elif torque is not False and torque is not None and not torque:
                carga = 0.0
            else:
                carga = False
            texto = 'Maestro del motor «%s»: Torque %s, Carga maxima %s.' % (
                motor_nombre or 'elegido', self._dato(torque, ' N·m'),
                self._dato(carga_motor, ' g', femenino=True))
            return carga, texto
        const = self._constantes()
        mec = self.mecanismo_ref_id.product_tmpl_id
        if mec and mec.safra_carga_maxima:
            return const['carga'], 'Carga maxima del mecanismo «%s» en el maestro: %s.' % (
                mec.name, self._dato(mec.safra_carga_maxima, ' g', femenino=True))
        texto = 'Carga máxima de la fila «%s» en Estructura por Ancho: %s' % (
            self.tubo or '', self._dato(self.carga_maxima, ' g', femenino=True))
        if mec:
            texto += ' (el mecanismo «%s» la tiene %s en el maestro)' % (
                mec.name, self._dato(mec.safra_carga_maxima, '', femenino=True))
        return const['carga'], texto + '.'

    def _ctx_limites(self, width, height, peso_tela=0.0, grosor_tela=0.0,
                     peso_perfil=0.0, factor=1.0, torque=0.0, carga_motor=0.0,
                     motor_elegido=False, motor_nombre=''):
        """Variables de las fórmulas de alto y peso máximo en esta fila (las
        de la tabla de Ajustes › Tubo: alto y peso máximo). Un dato del
        maestro sin digitar llega vacío (False), no 0.
        Reunión 09-nov (fila 68): con un motor elegido la carga sale SOLO del
        maestro de ese motor (por su torque o, sin torque, su Carga máxima);
        ya no se toma la de la fila como valor por defecto. Sin motor
        elegido, la del mecanismo o la de la fila."""
        self.ensure_one()
        const = self._constantes()
        carga = self._carga_y_origen(torque, carga_motor, motor_elegido, motor_nombre)[0]
        return {'ancho': width or 0.0, 'alto': height or 0.0, 'peso_tela': _num(peso_tela),
                'grosor_tela': _num(grosor_tela), 'peso_perfil': _num(peso_perfil),
                'factor': factor or 1.0, 'espacio_eje_techo': _num(const['espacio']),
                'diametro_tubo': _num(const['diametro']), 'carga_maxima': _num(carga),
                'pi': math.pi}

    def compute_limits(self, width, height, peso_tela=0.0, grosor_tela=0.0,
                       peso_perfil=0.0, factor=1.0, torque=0.0, carga_motor=0.0,
                       motor_elegido=False, motor_nombre=''):
        """Fórmulas de alto/peso máximo de las hojas 3/4 del Excel.

        Revisión 30-oct: las fórmulas (alto máximo por espacio, por carga,
        peso total y carga del motor por su torque) se ven y se cambian en
        Ajustes › Tubo: alto y peso máximo (R17.FORMULAS_TUBO). El alto
        máximo es el menor de los dos y el peso total se compara contra la
        carga máxima. Con motor, la carga sale del torque del motor elegido
        o, sin torque, de la Carga máxima de su producto (`carga_motor`,
        hoja 4); si no, la de la fila. Espacio, diámetro y carga salen de
        las referencias de la fila (_constantes). Devuelve None en los
        valores que no se pueden calcular por falta de parametrización (tela
        sin peso/grosor, regla sin constantes).
        """
        self.ensure_one()
        ctx = self._ctx_limites(width, height, peso_tela, grosor_tela, peso_perfil, factor,
                                torque, carga_motor, motor_elegido, motor_nombre)
        carga = ctx['carga_maxima']
        origen = self._carga_y_origen(torque, carga_motor, motor_elegido, motor_nombre)[1]
        alto_espacio = self._formula_tubo('safra.formula.tubo_alto_espacio', ctx)
        alto_carga = self._formula_tubo('safra.formula.tubo_alto_carga', ctx)
        candidates = [v for v in (alto_espacio, alto_carga) if v is not None]
        alto_max = min(candidates) if candidates else None
        peso_total = self._formula_tubo('safra.formula.tubo_peso_total', ctx)
        return {
            'alto_maximo': round(alto_max, 2) if alto_max is not None else None,
            'alto_limitante': ('espacio' if alto_max == alto_espacio else 'carga')
                              if alto_max is not None else None,
            'peso_total': round(peso_total, 0) if peso_total is not None else None,
            'carga_maxima': round(carga, 0) if carga is not False else None,
            'alto_ok': (height <= alto_max) if (alto_max is not None and height) else None,
            # Reunión 09-nov (fila 68): una carga digitada en 0 sí se compara
            # (la persiana no se puede fabricar por peso); sin digitar no hay
            # con qué comparar (`carga_sin_dato`).
            'peso_ok': (peso_total <= carga)
                       if (peso_total is not None and carga is not False) else None,
            'carga_sin_dato': peso_total is not None and carga is False,
            # De dónde sale la carga y cómo está cada dato en el maestro.
            'carga_detalle': origen,
        }

    @staticmethod
    def _codigo_formula(env, clave, defectos):
        """Código de una fórmula de Ajustes (vacía = la del módulo). Con
        «Probar fórmulas» (contexto safra_formulas_prueba) manda lo escrito
        en la pantalla de Ajustes, aunque no se haya guardado."""
        prueba = env.context.get('safra_formulas_prueba') or {}
        if clave in prueba:
            return (prueba[clave] or '').strip() or defectos[clave]
        return env['ir.config_parameter'].sudo().get_param(clave) or defectos[clave]

    @api.model
    def _formula_tubo(self, clave, ctx):
        """Valor de una fórmula del tubo de Ajustes (vacía = la del módulo);
        None si no se puede calcular o la fórmula tiene un error (queda en el
        log)."""
        codigo = self._codigo_formula(self.env, clave, R17.FORMULAS_TUBO)
        try:
            valor = evaluar_formula(codigo, dict(ctx))[0]
            return float(valor) if valor is not None else None
        except Exception as e:  # noqa: BLE001 — una fórmula mal escrita no rompe el portal
            _logger.warning('Fórmula %s con error: %s', clave, e)
            return None

    def _kit_for(self, motor_value):
        """Kit motorizado para el tubo de esta regla y el motor elegido."""
        self.ensure_one()
        return self.env['safra.motor.kit'].find_kit(motor_value, self.tubo)

    def _mechanism_line(self, cabezal=None):
        """Texto de la línea "Mecanismo" de la ficha técnica del portal.

        Sprint 1.3 (fila 71): el Cabezal es el que eligió el cliente; sin
        cabezal elegido, «No aplica» (antes salía el de la tabla).
        Reunión 15-oct (fila 69): Soporte y Terminal no se muestran al
        cliente; siguen en la tabla porque producción los descarga."""
        self.ensure_one()
        parts = [('Tubo', self.tubo), ('Mecanismo', self.mecanismo),
                 ('Cabezal', cabezal or 'No aplica')]
        return ' - '.join('%s: %s' % (k, v) for k, v in parts if v)


class SafraMotorKit(models.Model):
    """Kit motorizado (hoja 2 del Excel de la matriz).

    Por cada motor x tubo define los componentes que arma producción (corona,
    adaptador, soportes, interruptor) y los controles compatibles que el
    portal debe ofrecer. El cliente ya no escoge soporte de motor: lo da el
    kit (por eso motor_support_type se eliminó del formulario).
    """
    _name = 'safra.motor.kit'
    _description = 'Kit Motorizado'
    _order = 'sequence, motor_name, id'

    name = fields.Char(string='Nombre', compute='_compute_name', store=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    motor_value = fields.Char(
        string='Valor opción motor', required=True, index=True,
        help='Valor de la opción del campo "motor" del catálogo (p. ej. 26 = '
             'Motor Tubular Wifi 6/28 RF).')
    motor_name = fields.Char(string='Motor', required=True)
    # Sprint 1.7: el portal guarda el motor elegido como el código de su
    # línea de Referencias (categoría Motor), no como el valor de opción
    # anterior; sin este dato el kit no se encontraba.
    motor_ref_codes = fields.Char(
        string='Código del motor (Referencias)',
        help='Código de la línea de Referencias del motor que usa este kit '
             '(categoría Motor), p. ej. I100002874. Varios separados por coma.')
    tubo = fields.Char(
        string='Tubo', required=True,
        help='Debe corresponder al tubo de la tabla Estructura por Ancho.')

    corona = fields.Char(string='Corona')
    adaptador = fields.Char(string='Adaptador')
    soportes = fields.Char(string='Soportes')
    interruptor = fields.Char(
        string='Interruptor',
        help='Si se define, el campo Interruptor se habilita en el portal '
             'para este motor (p. ej. Receptor Rf 433MHz del SA35Q).')
    control_names = fields.Char(string='Controles (texto hoja 2)')
    control_values = fields.Char(
        string='Valores de control compatibles',
        help='Valores (separados por coma) de las opciones del campo '
             '"control" que el portal ofrece con este motor.')

    aplica_cargador = fields.Boolean(
        string='Aplica cargador',
        help='La pregunta "¿Requiere Cargador?" solo se muestra para los '
             'motores con este check (motores de batería).')
    compra_completa = fields.Boolean(
        string='Se compra completo',
        help='Motores Somfy: se compran con todos los accesorios; el pedido '
             'debe dejarse pasar a compra.')
    nota = fields.Char(string='Nota para el portal')

    # OBS REU GENERALES 11-sep: los componentes se amarran al maestro de
    # productos con cantidades (los Char de arriba quedan como referencia
    # de la hoja 2 mientras se completa la parametrización).
    component_ids = fields.One2many(
        'safra.motor.kit.component', 'kit_id', string='Componentes (maestro)')

    @api.depends('motor_name', 'tubo')
    def _compute_name(self):
        for rec in self:
            rec.name = '%s × %s' % (rec.motor_name or '?', rec.tubo or '?')

    @api.model
    def find_kit(self, motor_value, tubo):
        """Kit para un motor (valor de opción) y un tubo de la estructura.

        El nombre del tubo en la hoja 2 puede ser un prefijo del de la tabla
        de estructura ("Tubo 3" vs "Tubo 3 (Galvanizado)").
        """
        if not motor_value or not tubo:
            return self.browse()
        t = tubo.strip().lower()
        valor = str(motor_value).strip()
        kits = self.search(['|', ('motor_value', '=', valor),
                            ('motor_ref_codes', 'ilike', valor)])
        kits = kits.filtered(lambda k: k.motor_value == valor or valor in [
            c.strip() for c in (k.motor_ref_codes or '').split(',')])
        return kits.filtered(
            lambda k: t == k.tubo.strip().lower()
            or t.startswith(k.tubo.strip().lower())
            or k.tubo.strip().lower().startswith(t))[:1]


    @api.model
    def _seed_motor_ref_codes(self, _ids=None):
        """Sprint 1.7, una sola vez por base: amarra cada kit con la línea de
        Referencias del motor cuyo producto tiene el mismo nombre del motor
        del kit. Los que no coinciden los completa Safra en el kit."""
        Param = self.env['ir.config_parameter'].sudo()
        marca = 'website_quotes_safra.seed_motor_ref_codes'
        if Param.get_param(marca):
            return
        Param.set_param(marca, '1')
        field = self.env['safra.field'].sudo().search([('code', '=', 'motor')], limit=1)
        if not field.ref_category_id:
            return

        def norm(texto):
            return ' '.join((texto or '').lower().split())

        refs = self.env['safra.fabric.color'].sudo().with_context(active_test=False).search(
            [('fabric_id.category_id', '=', field.ref_category_id.id)])
        por_nombre = {}
        for ref in refs:
            for nombre in (ref.product_tmpl_id.name, ref.etiqueta):
                if nombre:
                    por_nombre.setdefault(norm(nombre), ref.code)
        for kit in self.with_context(active_test=False).search([('motor_ref_codes', '=', False)]):
            code = por_nombre.get(norm(kit.motor_name))
            if code:
                kit.motor_ref_codes = code


class SafraMotorKitComponent(models.Model):
    """Componente de un kit motorizado amarrado al maestro de productos.

    OBS REU GENERALES 11-sep: corona, adaptador, soportes, interruptor y
    demás («otros», ej. tornillos) deben ser productos reales con cantidad,
    para que al consumirse el kit producción sepa qué descargar.
    """
    _name = 'safra.motor.kit.component'
    _description = 'Componente de Kit Motorizado'
    _order = 'sequence, id'

    kit_id = fields.Many2one(
        'safra.motor.kit', string='Kit', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    role = fields.Selection([
        ('corona', 'Corona'),
        ('adaptador', 'Adaptador'),
        ('soporte', 'Soporte'),
        ('interruptor', 'Interruptor'),
        ('otro', 'Otro'),
    ], string='Rol', required=True, default='otro')
    product_id = fields.Many2one(
        'product.product', string='Producto', required=True,
        ondelete='restrict')
    quantity = fields.Float(
        string='Cantidad', required=True, default=1.0,
        help='Unidades del producto que consume el kit (ej. 2 coronas).')
    note = fields.Char(string='Nota')
