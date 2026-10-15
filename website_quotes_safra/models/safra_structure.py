# -*- coding: utf-8 -*-
import math

from odoo import api, fields, models


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
    desc_mando = fields.Float(string='Descuento mando (m)', digits=(6, 3))
    desc_terminal = fields.Float(string='Descuento terminal (m)', digits=(6, 3))
    desc_soporte = fields.Float(string='Descuento soporte (m)', digits=(6, 3))
    desc_corona = fields.Float(string='Descuento corona (m)', digits=(6, 3))
    aumento_tela = fields.Float(string='Aumento tela del tubo (m)', digits=(6, 3))
    aumento_perfil = fields.Float(string='Aumento/disminución tela perfil (m)', digits=(6, 3))

    # Constantes para las fórmulas de alto/peso máximo.
    espacio_eje_techo = fields.Float(
        string='Espacio eje central a techo (mm)', digits=(6, 2),
        help='Del soporte (hoja 3) o del cabezal (hoja 4) asociado al tubo.')
    diametro_tubo = fields.Float(string='Diámetro externo tubo (mm)', digits=(6, 2))
    carga_maxima = fields.Float(
        string='Carga máxima (g)', digits=(12, 2),
        help='Del mecanismo (manual) o del motor (motorizado).')

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
    def resolve(self, system, width, motorized=False, cabezal=None, unificacion=None):
        """Regla calculada por el ancho y regla efectiva tras la
        Unificación Mando: si el cliente (o la secuencia) pide un tubo mayor
        al calculado, la estructura y los límites salen de ese tubo.
        Devuelve (regla_calculada, regla_efectiva)."""
        base = self.find_rule(system, width, motorized=motorized, cabezal=cabezal)
        if not base or not unificacion or unificacion == base.tubo:
            return base, base
        tubos = self.tubos_ordenados(system, motorized=motorized)
        if (unificacion not in tubos or base.tubo not in tubos
                or tubos.index(unificacion) <= tubos.index(base.tubo)):
            return base, base
        rules = self.search([
            ('system_ids', 'in', system.id),
            ('drive_type', 'in', ['any', 'motor' if motorized else 'manual']),
            ('tubo', '=', unificacion),
        ], order='width_from, id')
        if cabezal:
            specific = rules.filtered(lambda r: r.cabezal_type == cabezal)
            if specific:
                return base, specific[0]
        return base, (rules.filtered(lambda r: r.cabezal_type == 'na') or rules)[:1] or base

    def compute_limits(self, width, height, peso_tela=0.0, grosor_tela=0.0,
                       peso_perfil=0.0, factor=1.0):
        """Fórmulas de alto/peso máximo de las hojas 3/4 del Excel.

        - Alto máx. por espacio: cuántas vueltas de tela caben entre el tubo y
          el techo: ((espacio − diámetro/2) / grosor) × (π × diámetro) / 1000.
        - Alto máx. por carga: (carga − ancho×peso_perfil) / (peso_tela×ancho).
        - Peso total: ancho×alto×peso_tela×factor + peso_perfil×ancho,
          comparado contra la carga máxima (factor 2 en Sheer: tela doblada).
        Devuelve None en los valores que no se pueden calcular por falta de
        parametrización (tela sin peso/grosor, regla sin constantes).
        """
        self.ensure_one()
        alto_espacio = alto_carga = None
        if grosor_tela and self.espacio_eje_techo and self.diametro_tubo:
            alto_espacio = (((self.espacio_eje_techo - self.diametro_tubo / 2.0)
                             / grosor_tela) * (math.pi * self.diametro_tubo)) / 1000.0
        if peso_tela and width and self.carga_maxima:
            alto_carga = ((self.carga_maxima - width * peso_perfil)
                          / (peso_tela * (factor or 1.0) * width))
        candidates = [v for v in (alto_espacio, alto_carga) if v is not None]
        alto_max = min(candidates) if candidates else None
        peso_total = None
        if peso_tela and width and height:
            peso_total = (width * height * peso_tela * (factor or 1.0)
                          + peso_perfil * width)
        return {
            'alto_maximo': round(alto_max, 2) if alto_max is not None else None,
            'alto_limitante': ('espacio' if alto_max == alto_espacio else 'carga')
                              if alto_max is not None else None,
            'peso_total': round(peso_total, 0) if peso_total is not None else None,
            'carga_maxima': self.carga_maxima or None,
            'alto_ok': (height <= alto_max) if (alto_max is not None and height) else None,
            'peso_ok': (peso_total <= self.carga_maxima)
                       if (peso_total is not None and self.carga_maxima) else None,
        }

    def _kit_for(self, motor_value):
        """Kit motorizado para el tubo de esta regla y el motor elegido."""
        self.ensure_one()
        return self.env['safra.motor.kit'].find_kit(motor_value, self.tubo)

    def _mechanism_line(self, cabezal=None):
        """Texto de la línea "Mecanismo" de la ficha técnica del portal.

        Sprint 1.3 (fila 71): el Cabezal es el que eligió el cliente; sin
        cabezal elegido, «No aplica» (antes salía el de la tabla)."""
        self.ensure_one()
        parts = [('Tubo', self.tubo), ('Mecanismo', self.mecanismo),
                 ('Soporte', self.soporte), ('Terminal', self.terminal),
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
        kits = self.search([('motor_value', '=', str(motor_value))])
        return kits.filtered(
            lambda k: t == k.tubo.strip().lower()
            or t.startswith(k.tubo.strip().lower())
            or k.tubo.strip().lower().startswith(t))[:1]


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
