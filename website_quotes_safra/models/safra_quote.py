# -*- coding: utf-8 -*-
import base64
import io
import logging
import math
import re
import unicodedata

from markupsafe import Markup, escape

from odoo import api, fields, models
from odoo.exceptions import UserError

from .fields_vacio import dato_sin_digitar, vacio_en
from .safra_formula_prueba import FORMULAS_TUBO
from .safra_panel import datos_usados, evaluar_formula, variables_formulario, vacio
from . import safra_reglas_17 as R17

_logger = logging.getLogger(__name__)


def _dato_de_ruta(record, attrs):
    """Sigue `tela.product_tmpl_id.safra_u_peso` desde el registro y
    devuelve el texto del dato si el último campo está sin digitar."""
    for attr in attrs:
        if attr.startswith('[') or not record:
            return None
        record = record[:1].sudo()
        field = record._fields.get(attr)
        if field is None:
            return None
        if field.relational:
            record = record[attr]
            continue
        return dato_sin_digitar(record, attr) if vacio_en(record, attr) else None
    return None


def datos_vacios(codigo, ctx):
    """Datos del maestro sin digitar que lee una fórmula con estas variables
    (texto de cada uno): las variables que llegan vacías (ancho_rollo,
    limites['wmax']…, en ctx['_sin_digitar']) y los campos numéricos que la
    fórmula lee de un registro (tela.peso_gm2, color.product_tmpl_id.…)."""
    variables = (ctx.get('_sin_digitar') or {}).get('variables') or {}
    out = []
    for ruta in sorted(datos_usados(codigo or '')):
        clave = ruta[0] + ''.join(p if p.startswith('[') else '.' + p for p in ruta[1:])
        dato = variables.get(clave)
        if dato is None and len(ruta) > 1 and isinstance(ctx.get(ruta[0]), models.BaseModel):
            dato = _dato_de_ruta(ctx[ruta[0]], ruta[1:])
        if dato and dato not in out:
            out.append(dato)
    return out


COORDINADO_SELECTION = [
    ('blanco', 'Blanco'),
    ('ivory', 'Ivory'),
    ('cafe', 'Café'),
    ('negro', 'Negro'),
    ('gris', 'Gris'),
]

ORIENTATION_SELECTION = [
    ('frente', 'Frente'),
    ('detras', 'Detrás'),
]

ATRAVESAR_SELECTION = [
    ('predeterminado', 'Predeterminado'),
    ('atravesar', 'Atravesar Tela'),
]


LATERALES_CENEFA_SELECTION = [
    ('sin', 'Sin Laterales'),
    ('izquierdo', 'Lateral Izquierdo'),
    ('derecho', 'Lateral Derecho'),
    ('ambos', 'Lateral Ambos Lados'),
]

CENEFA_TIPO_SELECTION = [
    ('sin', 'Sin Cenefa'),
    ('metalica', 'Cenefa Metálica'),
    ('tela', 'Cenefa en Tela'),
]

INTERRUPTOR_SELECTION = [
    ('sin', 'Sin Interruptor'),
    ('rf', 'Interruptor Receptor RF'),
]

BOLSILLO_SELECTION = [
    ('5', '5 cm'),
    ('8', '8 cm'),
    ('10', '10 cm'),
]


def _normaliza(texto):
    """Minúsculas y sin tildes, para comparar etiquetas."""
    texto = unicodedata.normalize('NFD', str(texto or '').strip().lower())
    return ''.join(c for c in texto if unicodedata.category(c) != 'Mn')


class SafraQuote(models.Model):
    _name = 'safra.quote'
    _description = 'Cotización Safra'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(
        string='Referencia', required=True, copy=False,
        readonly=True, default='Nueva Cotización',
    )
    partner_id = fields.Many2one('res.partner', string='Cliente', required=True, tracking=True)
    user_id = fields.Many2one(
        'res.users', string='Asesor',
        default=lambda self: self.env.user, tracking=True,
    )
    date = fields.Date(string='Fecha', default=fields.Date.today, required=True)
    # Fase 5.3 (obs f81): un pedido con diseño personalizado queda pendiente
    # de que el área de diseño lo revise (redimensión + m² de cobro) y lo
    # apruebe desde el ticket; solo entonces puede confirmarse.
    # Reunión 15-oct (fila 74): las persianas «sin restricciones» esperan a
    # que producción apruebe que se pueden fabricar.
    state = fields.Selection([
        ('draft', 'Borrador'),
        # Mejoras Sprint 1.1 (21-oct, fila 2): ya no cumple al confirmarla
        # (tela o referencia inactivada…); el cliente la corrige en el portal.
        ('blocked', 'Bloqueada'),
        ('pending_production', 'Pendiente aprobación producción'),
        ('pending_design', 'Pendiente aprobación diseño'),
        ('design_approved', 'Diseño aprobado'),
        ('production_approved', 'Aprobada por producción'),
        ('confirmed', 'Confirmada'),
        ('cancelled', 'Cancelada'),
    ], string='Estado', default='draft', tracking=True)
    line_ids = fields.One2many('safra.quote.line', 'quote_id', string='Líneas')
    bloqueo_motivos = fields.Text(string='Motivo del bloqueo', readonly=True, copy=False)
    note = fields.Text(string='Notas internas')
    # Revisión sprint 1 (f138): Safra Express aplica al PEDIDO completo,
    # no a cada persiana.
    safra_express = fields.Boolean(string='¿Solicita Safra Express?', tracking=True)
    # Sprint 1.6 (fila 126): el pedido de exportación no se confirma ni se
    # factura solo; el área de exportaciones lo agrupa según la negociación
    # y no lleva IVA.
    es_exportacion = fields.Boolean(string='¿Es una Exportación?', tracking=True)
    # Prueba 126.1 (26-oct): la cotización confirmada genera su pedido de
    # venta; así el área de exportaciones agrupa los pedidos de una
    # negociación con la factura consolidada nativa de Ventas.
    sale_order_id = fields.Many2one('sale.order', string='Pedido de venta',
                                    readonly=True, copy=False, index=True)
    # Sprint 1.6 (fila 128, reunión 21-oct): un usuario autorizado pide que
    # planta revise y ajuste la fabricación antes de seguir. Las
    # restricciones no bloquean (quedan para la revisión) y el pedido
    # espera la aprobación de producción desde su ticket.
    requiere_verificacion = fields.Boolean(
        string='Requiere verificación de fabricación', tracking=True)
    verificacion_observaciones = fields.Text(
        string='Cambios requeridos (verificación)',
        help='Observaciones del comercial para planta: qué se debe ajustar '
             'en la estructura o en las instrucciones de fabricación.')
    verificacion_detalle = fields.Text(
        string='Restricciones a revisar', readonly=True, copy=False)
    verificacion_aprobada = fields.Boolean(
        string='Verificación aprobada por producción', copy=False, tracking=True)
    verificacion_ticket_id = fields.Many2one(
        'helpdesk.ticket', string='Ticket de verificación', readonly=True, copy=False)
    # Ajustes Sprint 1.6 (26-oct, fila 130): planta puede rechazar la
    # verificación; el cliente edita la cotización (al guardarla sale un
    # ticket nuevo) o la elimina.
    verificacion_rechazada = fields.Boolean(
        string='Verificación rechazada por producción', readonly=True, copy=False, tracking=True)
    verificacion_rechazo_motivo = fields.Text(
        string='Motivo del rechazo (verificación)', readonly=True, copy=False)
    # Reunión 09-nov (fila 74): «Pedido sin restricciones» se unifica con la
    # verificación. El cliente acepta al cerrar la cotización que el pedido
    # se evalúa sin garantía; planta, al aprobar desde el ticket, dice si va
    # con garantía o sin garantía (y por qué), y el portal se lo muestra.
    # Se copia con el pedido duplicado: la copia lleva la misma verificación.
    verificacion_acepta_sin_garantia = fields.Boolean(
        string='Aceptó que se evalúa sin garantía', readonly=True, tracking=True)
    verificacion_garantia = fields.Selection(
        [('con', 'Con garantía'), ('sin', 'Sin garantía')],
        string='Garantía del pedido', readonly=True, copy=False, tracking=True,
        help='La indica planta al aprobar la verificación de fabricación.')
    verificacion_garantia_motivo = fields.Text(
        string='Motivo de la garantía', readonly=True, copy=False)
    # Ajustes Sprint 1.6 (26-oct, fila 128): pedidos de proyectos que se
    # facturan a mano al final (no al despachar), como la exportación.
    es_proyecto_especial = fields.Boolean(
        string='¿Requiere Facturación Proyectos Especiales?', tracking=True)
    # Ajustes Sprint 1.6 (26-oct, fila 127): embalaje de todo el pedido;
    # cada opción es una línea de una referencia de la categoría Embalaje
    # (con su producto del maestro, para la lista de materiales).
    embalaje_ids = fields.Many2many(
        'safra.fabric.color', 'safra_quote_embalaje_rel', 'quote_id', 'color_id',
        string='Embalaje')
    # Ajustes Sprint 1.6 (26-oct, fila 182): consecutivo propio del cliente.
    orden_compra = fields.Char(string='Orden de compra cliente', tracking=True)
    # Matriz, Datos de despacho (filas 184-188, reunión 26-oct): para todo el
    # pedido. Si recoge en fábrica no hay despacho: país, ciudad, dirección y
    # destinatario no se piden (la fecha sí). `despacho_registrado` marca
    # las cotizaciones guardadas con estos datos en el formulario: las de
    # antes no se revalidan contra V_DESPACHO_DATOS.
    recoge_fabrica = fields.Boolean(string='Recoge en fábrica', tracking=True)
    despacho_country_id = fields.Many2one('res.country', string='País de despacho', tracking=True)
    despacho_city_id = fields.Many2one(
        'res.city', string='Ciudad de despacho', tracking=True,
        domain="[('country_id', '=', despacho_country_id)]")
    despacho_direccion = fields.Char(string='Dirección de despacho', tracking=True)
    despacho_destinatario = fields.Char(string='Nombre del destinatario', tracking=True)
    despacho_fecha = fields.Date(string='Fecha tentativa de despacho', tracking=True)
    despacho_registrado = fields.Boolean(string='Con datos de despacho', readonly=True, copy=False)
    # Sprint 1.6 (fila 123): el cliente puede editar la cotización desde el
    # portal mientras no haya iniciado el flujo.
    editable_portal = fields.Boolean(compute='_compute_editable_portal')
    # Revisión 27-oct (pruebas de Safra): el cliente guarda el pedido como
    # borrador aunque tenga errores; no se finaliza ni se confirma hasta
    # corregirlos, y mientras tanto no arranca ningún flujo.
    borrador_portal = fields.Boolean(
        string='Sin finalizar', readonly=True, tracking=True,
        help='El cliente la guardó como borrador desde el portal y no ha pulsado '
             '«Finalizar pedido». No se confirma ni abre tickets (diseño, producción, '
             'verificación) ni avisa a exportaciones hasta que la finalice.')
    borrador_errores = fields.Text(string='Errores por corregir', readonly=True)

    currency_id = fields.Many2one(
        'res.currency', string='Moneda',
        related='partner_id.company_id.currency_id', store=True,
        default=lambda self: self.env.company.currency_id,
    )
    amount_total = fields.Float(string='Total', compute='_compute_amount_total', store=True)
    # Puntos 10-11 (OBS REU TELAS): cada diseño personalizado genera un
    # ticket de Helpdesk asociado a la cotización; reunión 15-oct (fila 74):
    # también el de producción de las persianas sin restricciones.
    design_ticket_count = fields.Integer(
        string='Tickets', compute='_compute_design_ticket_count')

    @api.depends('line_ids.price_total')
    def _compute_amount_total(self):
        for rec in self:
            rec.amount_total = sum(rec.line_ids.mapped('price_total'))

    @api.depends('state', 'line_ids.custom_design', 'line_ids.sin_restricciones',
                 'requiere_verificacion', 'verificacion_rechazada', 'borrador_portal')
    def _compute_editable_portal(self):
        # Con diseño, sin restricciones o verificación hay un ticket en
        # curso con las persianas tal como se enviaron: no se editan.
        for rec in self:
            # Ajustes Sprint 1.6 (26-oct, fila 130): rechazada la
            # verificación, el cliente la vuelve a editar.
            verificacion = rec.requiere_verificacion and not rec.verificacion_rechazada
            # Revisión 27-oct: el borrador sin finalizar no abrió tickets.
            rec.editable_portal = rec.state in ('draft', 'blocked') and (rec.borrador_portal or (
                not verificacion and not rec.line_ids.filtered(
                    lambda l: l.custom_design or l.sin_restricciones)))

    def _compute_design_ticket_count(self):
        Ticket = self.env['helpdesk.ticket'].sudo()
        for rec in self:
            rec.design_ticket_count = Ticket.search_count([
                ('safra_quote_id', '=', rec.id)]) if rec.id else 0

    def action_view_sale_order(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Pedido de venta',
            'res_model': 'sale.order',
            'view_mode': 'form',
            'res_id': self.sale_order_id.id,
        }

    def _descripcion_venta(self, line):
        """Texto de la línea del pedido de venta: la persiana como la ve el
        cliente en el portal."""
        partes = ['%s · %s × %s m' % (line.system_id.name or '', line.width or 0, line.height or 0)]
        if line.fabric_id:
            partes.append(' '.join(filter(None, [line.fabric_id.name, line.color_id.name])))
        if line.location:
            partes.append(line.location)
        return ' · '.join(partes)

    def _generar_pedido_venta(self):
        """Pedido de venta confirmado de cada cotización confirmada: una
        línea por persiana con el producto terminado del sistema, su
        cantidad y su precio. La exportación lleva la posición fiscal y el
        diario de exportación de Ajustes (sin posición fiscal configurada,
        las líneas van sin impuestos, como en el portal)."""
        Param = self.env['ir.config_parameter'].sudo()
        Order = self.env['sale.order'].sudo()
        posicion = self.env['account.fiscal.position'].sudo().browse(
            int(Param.get_param('safra.exportacion_posicion_fiscal') or 0)).exists()
        diario = self.env['account.journal'].sudo().browse(
            int(Param.get_param('safra.exportacion_diario') or 0)).exists()
        for quote in self.sudo().filtered(lambda q: q.state == 'confirmed' and not q.sale_order_id):
            quote.line_ids.system_id._ensure_products()
            lineas = []
            for line in quote.line_ids.sorted('sequence'):
                producto = line.system_id.product_tmpl_id.product_variant_id
                if not producto:
                    continue
                lineas.append((0, 0, {
                    'product_id': producto.id,
                    'name': quote._descripcion_venta(line),
                    'product_uom_qty': line.quantity or 1,
                    'price_unit': line.price_unit,
                }))
            if not lineas:
                continue
            vals = {
                'partner_id': quote.partner_id.id,
                'origin': quote.name,
                # Ajustes Sprint 1.6 (26-oct, fila 182): la orden de compra
                # del cliente es su referencia en el pedido de venta.
                'client_order_ref': quote.orden_compra or quote.name,
                'safra_quote_id': quote.id,
                'order_line': lineas,
            }
            if quote.user_id and not quote.user_id.share:
                vals['user_id'] = quote.user_id.id
            if quote.es_exportacion:
                if posicion:
                    vals['fiscal_position_id'] = posicion.id
                if diario:
                    vals['journal_id'] = diario.id
            order = Order.create(vals)
            if quote.es_exportacion and not posicion:
                order.order_line.tax_ids = False
            order.action_confirm()
            quote.sale_order_id = order
            quote.message_post(body=Markup('Pedido de venta <b>%s</b> creado.') % order.name)

    def action_view_design_tickets(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Tickets de la cotización',
            'res_model': 'helpdesk.ticket',
            'view_mode': 'list,form',
            'domain': [('safra_quote_id', '=', self.id)],
            'context': {'default_safra_quote_id': self.id},
        }

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nueva Cotización') == 'Nueva Cotización':
                vals['name'] = self.env['ir.sequence'].next_by_code('safra.quote') or 'Nueva Cotización'
        return super().create(vals_list)

    def _revalidate(self):
        """Reunión 28-sep (fila 2), regla general: una cotización guardada
        puede quedar inválida mientras espera (se inactiva una tela, se
        restringe un sistema a otros grupos, se suspende un diseño…). Antes
        de continuar el flujo se repiten TODAS las validaciones del pedido
        sobre las líneas guardadas, más la disponibilidad actual de lo que
        eligió el cliente. Devuelve [{line, code, severity, message}]."""
        self.ensure_one()
        lines = self.line_ids.sorted('sequence')
        Line = self.env['safra.quote.line'].sudo()
        issues = Line._validate_order([l.copy_data()[0] for l in lines], pedido=self._datos_pedido())
        cfg = self.env['safra.validation.rule'].sudo().get_config('V_REVALIDACION') or {}
        if cfg and not cfg.get('active', True):
            return issues
        user = self.user_id or self.env.user
        for n, line in enumerate(lines, start=1):
            # Reunión 09-nov (fila 2): cualquier ítem inactivado, no solo la tela.
            motivos = [d['motivo'] for d in line._items_no_disponibles(user)]
            for motivo in motivos:
                issues.append({
                    'line': n, 'code': 'V_REVALIDACION',
                    'severity': cfg.get('severity') or 'error',
                    'message': cfg.get('message') or
                    'E20025: No se puede continuar: %s.' % motivo,
                })
        return issues

    def _no_disponibles_portal(self):
        """Reunión 09-nov (fila 2): nota informativa del portal con lo que el
        cliente eligió y ya no está disponible, para que lo cambie antes de
        enviar o confirmar el pedido. ['Persiana N: motivo']."""
        self.ensure_one()
        if self.state not in self.SIN_CONFIRMAR:
            return []
        user = self.user_id or self.env.user
        return ['Persiana %d: %s' % (n, d['motivo'])
                for n, line in enumerate(self.sudo().line_ids.sorted('sequence'), start=1)
                for d in line._items_no_disponibles(user)]

    def _datos_pedido(self):
        """Lo que se marca para todo el pedido, como lo recibe el motor de
        validaciones."""
        self.ensure_one()
        return {'safra_express': self.safra_express, 'es_exportacion': self.es_exportacion,
                'requiere_verificacion': self.requiere_verificacion,
                'pide_despacho': self.despacho_registrado,
                'recoge_fabrica': self.recoge_fabrica,
                'despacho_country_id': self.despacho_country_id.id,
                'despacho_city_id': self.despacho_city_id.id,
                'despacho_direccion': self.despacho_direccion or '',
                'despacho_destinatario': self.despacho_destinatario or '',
                'despacho_fecha': self.despacho_fecha or False}

    @api.model
    def _hoy_colombia(self, ahora=None):
        """Fecha de hoy en Colombia (zona de la empresa o America/Bogota): el
        servidor trabaja en UTC, 5 horas adelante, y desde las 7 p. m. ya
        sería mañana. `ahora`: fecha y hora UTC (por defecto, la actual)."""
        tz = self.env.company.partner_id.tz or 'America/Bogota'
        return fields.Date.context_today(self.with_context(tz=tz), timestamp=ahora)

    # Estados de una cotización que todavía no inicia el flujo.
    SIN_CONFIRMAR = ('draft', 'pending_production', 'pending_design',
                     'design_approved', 'production_approved')

    def _anular_si_invalida(self):
        """Pendiente 4 (Safra, 5-oct): una cotización SIN CONFIRMAR que al
        revalidarse ya no cumple se ANULA, y el motivo queda en su
        historial. Devuelve {cotización: errores} de las anuladas."""
        anuladas = {}
        # Revisión 27-oct: el borrador sin finalizar puede tener errores; lo
        # corrige el cliente, no se anula.
        for quote in self.filtered(lambda q: q.state in self.SIN_CONFIRMAR and not q.borrador_portal):
            errores = [i for i in quote._revalidate() if i['severity'] == 'error']
            if not errores:
                continue
            quote.write({'state': 'cancelled'})
            quote.message_post(body=Markup(
                '<p>Cotización anulada: ya no cumple las condiciones para '
                'continuar.</p><ul>%s</ul>') % Markup('').join(
                    Markup('<li>Persiana %s: %s</li>') % (e['line'], e['message'])
                    for e in errores))
            anuladas[quote] = errores
        return anuladas

    def _bloquear_si_invalida(self):
        """Mejoras Sprint 1.1 (21-oct, fila 2): al confirmar, la cotización
        que ya no cumple (tela o referencia inactivada, sistema restringido…)
        queda BLOQUEADA con el motivo, en vez de anularse: el cliente entra
        desde el portal al mismo formulario, la corrige y la vuelve a
        confirmar. Devuelve {cotización: errores} de las bloqueadas."""
        bloqueadas = {}
        for quote in self.filtered(lambda q: q.state in self.SIN_CONFIRMAR + ('blocked',)):
            errores = [i for i in quote._revalidate() if i['severity'] == 'error']
            if not errores:
                continue
            motivos = '\n'.join('Persiana %s: %s' % (e['line'], e['message']) if e['line']
                                 else e['message'] for e in errores)
            nuevo = quote.state != 'blocked' or quote.bloqueo_motivos != motivos
            quote.write({'state': 'blocked', 'bloqueo_motivos': motivos})
            if nuevo:
                quote.message_post(body=Markup(
                    '<p>Cotización bloqueada: ya no cumple las condiciones para '
                    'continuar. El cliente puede editarla desde el portal.</p><ul>%s</ul>') % Markup('').join(
                        Markup('<li>%s</li>') % linea for linea in motivos.split('\n')))
            bloqueadas[quote] = errores
        return bloqueadas

    def _desbloquear(self):
        """La cotización bloqueada que se edita vuelve a Borrador; si sigue
        sin cumplir, se bloquea otra vez con el motivo actualizado."""
        bloqueadas = self.filtered(lambda q: q.state == 'blocked')
        bloqueadas.write({'state': 'draft', 'bloqueo_motivos': False})
        bloqueadas._bloquear_si_invalida()

    def action_confirm(self):
        sin_finalizar = self.filtered('borrador_portal')
        if sin_finalizar:
            raise UserError(
                'La cotización %s es un borrador que el cliente no ha finalizado: debe '
                'corregirla y pulsar «Finalizar pedido» en el portal.'
                % ', '.join(sin_finalizar.mapped('name')))
        # Reunión 15-oct (fila 74): sin la aprobación de producción una
        # persiana «sin restricciones» no avanza.
        pendientes = self.filtered(lambda q: q.line_ids.filtered(
            lambda l: l.sin_restricciones and not l.sin_restricciones_aprobado))
        if pendientes:
            raise UserError(
                'La cotización %s tiene persianas sin restricciones que '
                'producción no ha aprobado.' % ', '.join(pendientes.mapped('name')))
        # Sprint 1.6 (fila 128): sin la aprobación de planta no avanza.
        sin_verificar = self.filtered(lambda q: q.requiere_verificacion and not q.verificacion_aprobada)
        if sin_verificar:
            raise UserError(
                'La cotización %s requiere verificación de fabricación y '
                'producción no la ha aprobado.' % ', '.join(sin_verificar.mapped('name')))
        bloqueadas = self._bloquear_si_invalida()
        confirmadas = self - self.browse([q.id for q in bloqueadas])
        confirmadas.write({'state': 'confirmed', 'bloqueo_motivos': False})
        confirmadas._generar_pedido_venta()
        if bloqueadas:
            detalle = '\n'.join(
                '%s · Persiana %s: %s' % (q.name, e['line'], e['message'])
                for q, errores in bloqueadas.items() for e in errores)
            return {
                'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {
                    'type': 'danger', 'sticky': True,
                    'title': 'Cotización bloqueada: ya no cumple las condiciones',
                    'message': detalle,
                    'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'},
                },
            }

    def action_revisar_vigencia(self):
        """Acción del listado: revalida las cotizaciones elegidas sin
        confirmar y anula las que ya no cumplen."""
        anuladas = self._anular_si_invalida()
        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {
                'type': 'warning' if anuladas else 'success',
                'message': ('Se anularon %d cotizaciones que ya no cumplen: %s.'
                            % (len(anuladas), ', '.join(q.name for q in anuladas)))
                if anuladas else 'Todas las cotizaciones revisadas siguen vigentes.',
                'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'},
            },
        }

    @api.model
    def _cron_anular_invalidas(self):
        """Tarea programada: revisa todas las cotizaciones sin confirmar."""
        self.search([('state', 'in', self.SIN_CONFIRMAR)])._anular_si_invalida()

    def _sugerir_rollos(self):
        """Guarda en cada persiana el rollo (lote) del que saldría su tela."""
        Line = self.env['safra.quote.line'].sudo()
        for quote in self:
            lines = quote.line_ids.sorted('sequence')
            _issues, sugeridos = Line._asignar_rollos([l.copy_data()[0] for l in lines])
            for n, line in enumerate(lines, start=1):
                line.lote_sugerido_id = sugeridos.get(n, False)

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_draft(self):
        self.write({'state': 'draft', 'bloqueo_motivos': False})

    def _create_production_ticket(self):
        """Reunión 15-oct (fila 74): un ticket de Helpdesk por pedido para
        que producción revise las persianas «sin restricciones» (si se
        pueden fabricar) y las apruebe; mientras tanto el pedido no se
        confirma. Como el flujo del diseño personalizado."""
        self.ensure_one()
        lines = self.line_ids.filtered(
            lambda l: l.sin_restricciones and not l.production_ticket_id)
        if not lines:
            return self.env['helpdesk.ticket']
        Team = self.env['helpdesk.team'].sudo()
        team = Team.search([('name', 'ilike', 'produc')], limit=1) or Team.search([], limit=1)
        body = Markup('<h4>Pedido sin restricciones (sin garantía)</h4>'
                      '<p>Producción debe confirmar que estas persianas se '
                      'pueden fabricar y aprobarlas desde este ticket.</p>')
        for line in lines:
            body += Markup('<p><strong>Persiana %s</strong> · %s · %s · %.2f m × %.2f m</p>') % (
                line.sequence // 10, line.system_id.name or '', line.fabric_id.name or '',
                line.width or 0, line.height or 0)
            detalle = (line.sin_restricciones_detalle or 'Sin restricciones al cotizar.').split('\n')
            body += Markup('<ul>%s</ul>') % Markup('').join(
                Markup('<li>%s</li>') % d for d in detalle if d)
        ticket = self.env['helpdesk.ticket'].sudo().create({
            'name': 'Pedido sin restricciones - %s' % (self.name or ''),
            'team_id': team.id or False,
            'partner_id': self.partner_id.id,
            'description': body,
            'safra_quote_id': self.id,
            'safra_sin_restricciones': True,
        })
        lines.write({'production_ticket_id': ticket.id})
        return ticket

    def _equipo_produccion(self):
        Team = self.env['helpdesk.team'].sudo()
        return Team.search([('name', 'ilike', 'produc')], limit=1) or Team.search([], limit=1)

    def _create_verification_ticket(self):
        """Sprint 1.6 (fila 128): ticket para que planta revise las
        observaciones del comercial, ajuste la estructura o las
        instrucciones de fabricación y apruebe el pedido."""
        self.ensure_one()
        if not self.requiere_verificacion or self.verificacion_ticket_id:
            return self.env['helpdesk.ticket']
        body = Markup('<h4>Requiere verificación de fabricación</h4>'
                      '<p>Planta debe revisar los cambios pedidos, ajustar la '
                      'estructura o las instrucciones de fabricación y aprobar '
                      'el pedido desde este ticket.</p><p>El cliente aceptó que el '
                      'pedido se evalúa sin garantía: al aprobarlo, indique si va con '
                      'garantía o sin garantía (y el motivo); el cliente lo verá en el '
                      'portal.</p><p><strong>Cambios requeridos:</strong></p><p>%s</p>') % (
            self.verificacion_observaciones or 'Sin observaciones.')
        for line in self.line_ids.sorted('sequence'):
            body += Markup('<p><strong>Persiana %s</strong> · %s · %s · %.2f m × %.2f m</p>') % (
                line.sequence // 10, line.system_id.name or '', line.fabric_id.name or '',
                line.width or 0, line.height or 0)
        if self.verificacion_detalle:
            body += Markup('<p><strong>Restricciones que no se aplicaron:</strong></p><ul>%s</ul>') % (
                Markup('').join(Markup('<li>%s</li>') % d
                                for d in self.verificacion_detalle.split('\n') if d))
        ticket = self.env['helpdesk.ticket'].sudo().create({
            'name': 'Verificación de fabricación - %s' % (self.name or ''),
            'team_id': self._equipo_produccion().id or False,
            'partner_id': self.partner_id.id,
            'description': body,
            'safra_quote_id': self.id,
            'safra_verificacion': True,
        })
        self.verificacion_ticket_id = ticket
        return ticket

    def _rechazar_verificacion(self, motivo):
        """Ajustes Sprint 1.6 (26-oct, fila 130): planta rechaza la
        verificación de fabricación. La cotización vuelve a Borrador para
        que el cliente la corrija (al guardarla se abre un ticket nuevo) o
        la elimine."""
        for quote in self:
            quote.write({
                'state': 'draft',
                'verificacion_aprobada': False,
                'verificacion_rechazada': True,
                'verificacion_rechazo_motivo': motivo,
                'verificacion_ticket_id': False,
            })
            quote.message_post(body=Markup(
                '<p>Producción rechazó la verificación de fabricación.</p><p>%s</p>') % motivo)

    def _flujos_al_guardar(self):
        """Lo que arranca una cotización guardada: rollo sugerido, tickets
        de diseño, producción y verificación, y su estado."""
        for quote in self:
            for line in quote.line_ids.filtered(lambda l: l.custom_design and not l.design_ticket_id):
                line._create_design_ticket()
            quote._sugerir_rollos()
            quote._create_production_ticket()
            quote._create_verification_ticket()
            quote._update_design_state()

    def _duplicar_portal(self, user):
        """Ajustes Sprint 1.6 (26-oct, fila 123): copia del pedido completo
        (en cualquier estado) para quien la pide, en Borrador. Lo que el
        usuario no puede marcar no se copia; si ya no cumple las
        validaciones queda Bloqueada con el motivo."""
        self.ensure_one()
        vals = {'partner_id': user.partner_id.id, 'user_id': user.id,
                'state': 'draft', 'date': fields.Date.context_today(self)}
        for campo, grupo in (('es_exportacion', 'group_safra_exportacion'),
                             ('es_proyecto_especial', 'group_safra_proyectos_especiales'),
                             ('requiere_verificacion', 'group_safra_verificacion')):
            if not user.has_group('website_quotes_safra.%s' % grupo):
                vals[campo] = False
        # Reunión 09-nov (fila 74): sin la verificación no queda la aceptación.
        if vals.get('requiere_verificacion') is False:
            vals['verificacion_acepta_sin_garantia'] = False
        nueva = self.sudo().copy(vals)
        for line in self.line_ids.sorted('sequence'):
            line.sudo().copy({'quote_id': nueva.id})
        nueva.message_post(body='Copia del pedido %s.' % self.name)
        nueva._flujos_al_guardar()
        nueva._bloquear_si_invalida()
        nueva._avisar_exportacion()
        return nueva

    def _eliminar_linea_portal(self, line):
        """Ajustes Sprint 1.6 (26-oct, fila 124): desde el resumen del pedido
        en Borrador se elimina una persiana. El pedido que quedaría se valida
        completo antes; con errores no se cambia y se devuelven los errores.
        (Duplicar abre el formulario con la copia, para ajustarla.)"""
        self.ensure_one()
        lineas = self.line_ids.sorted('sequence')
        if len(lineas) == 1:
            return [{'line': 0, 'severity': 'error', 'message':
                     'El pedido debe tener al menos una persiana; para descartarlo, elimine el pedido.'}]
        datos = [l.copy_data()[0] for l in lineas if l != line]
        errores = [i for i in self.env['safra.quote.line'].sudo()._validate_order(
            datos, pedido=self._datos_pedido()) if i['severity'] == 'error']
        if errores:
            return errores
        self.message_post(body='Persiana %s eliminada por el cliente desde el portal.'
                          % (lineas.ids.index(line.id) + 1))
        line.sudo().unlink()
        for n, restante in enumerate(self.line_ids.sorted('sequence'), start=1):
            restante.sequence = n * 10
        self._sugerir_rollos()
        return []

    def _avisar_exportacion(self):
        """Sprint 1.6 (fila 126): actividad para el área de exportaciones
        (usuarios del grupo «Exportaciones»), que agrupa y factura el
        pedido según la negociación."""
        grupo = self.env.ref('website_quotes_safra.group_safra_exportacion', raise_if_not_found=False)
        usuarios = grupo.sudo().user_ids.filtered(lambda u: not u.share) if grupo else self.env['res.users']
        for quote in self.filtered('es_exportacion'):
            for usuario in usuarios:
                quote.sudo().activity_schedule(
                    'mail.mail_activity_data_todo', user_id=usuario.id,
                    summary='Pedido de exportación: agrupar y facturar',
                    note='El pedido %s es de exportación: no se confirma desde el portal '
                         'y no lleva IVA. Al confirmarlo se crea su pedido de venta; para '
                         'agrupar los pedidos de una negociación en una sola factura: '
                         'Ventas › Por facturar › Órdenes a facturar, filtro «Exportación '
                         '(cotizador)», seleccionarlos › Crear facturas › Facturación '
                         'consolidada.' % quote.name)

    def _update_design_state(self):
        """Estado según la aprobación del área de diseño: con diseños sin
        aprobar queda «Pendiente aprobación diseño»; cuando el diseñador
        aprueba todos desde sus tickets pasa a «Diseño aprobado».
        Reunión 15-oct (fila 74): antes que el diseño, las persianas «sin
        restricciones» esperan a producción («Pendiente aprobación
        producción»); aprobadas todas, sigue el diseño o queda «Aprobada
        por producción»."""
        for quote in self:
            # Fila 130: rechazada la verificación, espera a que el cliente
            # la corrija.
            if quote.state in ('confirmed', 'cancelled', 'blocked') or quote.verificacion_rechazada:
                continue
            design_lines = quote.line_ids.filtered('custom_design')
            sr_lines = quote.line_ids.filtered('sin_restricciones')
            # Sprint 1.6 (fila 128): la verificación de fabricación espera
            # a producción igual que las persianas sin restricciones.
            if sr_lines or quote.requiere_verificacion:
                if sr_lines.filtered(lambda l: not l.sin_restricciones_aprobado) or (
                        quote.requiere_verificacion and not quote.verificacion_aprobada):
                    nuevo = 'pending_production'
                elif design_lines.filtered(lambda l: not l.design_approved):
                    nuevo = 'pending_design'
                else:
                    nuevo = 'production_approved'
                if quote.state != nuevo:
                    antes = quote.state
                    quote.state = nuevo
                    if antes == 'pending_production':
                        quote.message_post(body=(
                            'Producción aprobó las persianas sin restricciones '
                            'del pedido (sin garantía).' if sr_lines else
                            'Producción aprobó la verificación de fabricación del pedido.'))
                continue
            if not design_lines:
                continue
            if all(l.design_approved for l in design_lines):
                if quote.state == 'pending_design':
                    quote.state = 'design_approved'
                    quote.message_post(body=(
                        'El área de diseño aprobó todos los diseños del '
                        'pedido; ya puede continuar con la confirmación.'))
            elif quote.state != 'pending_design':
                quote.state = 'pending_design'


class SafraQuoteLine(models.Model):
    _name = 'safra.quote.line'
    _description = 'Línea de Cotización Safra'
    _order = 'sequence, id'
    # Probar fórmulas (03-nov): la persiana se busca por cotización,
    # localización o sistema.
    _rec_names_search = ['quote_id.name', 'location', 'system_id.name']

    @api.depends('quote_id.name', 'sequence', 'location', 'system_id', 'width', 'height')
    def _compute_display_name(self):
        """«S00012 · Sala · ENROLLABLE · 2.1 × 3.58» para elegir la persiana."""
        for line in self:
            medidas = '%s × %s' % (line.width or 0, line.height or 0) if line.width else ''
            line.display_name = ' · '.join(p for p in (
                line.quote_id.name, line.location or 'Persiana %d' % (line.sequence // 10),
                line.system_id.name, medidas) if p)

    quote_id = fields.Many2one('safra.quote', string='Cotización', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)

    # Fase 5.4c (hoja «1» + programa HTML del cliente): piezas asignadas a
    # los dos soportes de la persiana en el configurador de secuencia.
    SOPORTE_SELECTION = [
        ('MANDO', 'Mando'),
        ('MOTOR', 'Motor'),
        ('DEP', 'Soporte dependiente'),
        ('INDEP', 'Soporte independiente'),
        ('TERMINAL', 'Terminal'),
    ]
    soporte_izq = fields.Selection(SOPORTE_SELECTION, string='Soporte izquierdo')
    soporte_der = fields.Selection(SOPORTE_SELECTION, string='Soporte derecho')

    # === DATOS BÁSICOS ===
    system_id = fields.Many2one(
        'safra.system', string='Sistema', required=True,
        default=lambda self: self.env.ref('website_quotes_safra.system_01', raise_if_not_found=False),
    )
    exhibition = fields.Boolean(string='Exhibición')
    same_header = fields.Boolean(string='Mismo Cabezal / Soporte Intermedio')
    sequence_name = fields.Char(string='Nombre secuencia')

    # === DIMENSIONES ===
    width = fields.Float(string='Ancho (m)', digits=(12, 3), required=True)
    height = fields.Float(string='Alto (m)', digits=(12, 3), required=True)
    quantity = fields.Integer(string='Cantidad', default=1, required=True)
    location = fields.Char(string='Localización / Ventana')
    aligned = fields.Boolean(string='Alineado')

    # === TELA ===
    fabric_id = fields.Many2one('safra.fabric', string='Referencia', required=True)
    color_id = fields.Many2one(
        'safra.fabric.color', string='Color', required=True,
        domain="[('fabric_id', '=', fabric_id)]",
    )
    # Telas combinadas (productos que mezclan varias telas en una persiana)
    fabric_id_2 = fields.Many2one('safra.fabric', string='Referencia 2')
    color_id_2 = fields.Many2one('safra.fabric.color', string='Color 2', domain="[('fabric_id', '=', fabric_id_2)]")
    fabric_id_3 = fields.Many2one('safra.fabric', string='Referencia 3')
    color_id_3 = fields.Many2one('safra.fabric.color', string='Color 3', domain="[('fabric_id', '=', fabric_id_3)]")
    fabric_id_4 = fields.Many2one('safra.fabric', string='Referencia 4')
    color_id_4 = fields.Many2one('safra.fabric.color', string='Color 4', domain="[('fabric_id', '=', fabric_id_4)]")
    fabric_id_5 = fields.Many2one('safra.fabric', string='Referencia 5')
    color_id_5 = fields.Many2one('safra.fabric.color', string='Color 5', domain="[('fabric_id', '=', fabric_id_5)]")
    tela_al_reves = fields.Boolean(string='¿Tela al revés? (Doblefaz)')
    atravesar_tela = fields.Selection(ATRAVESAR_SELECTION, string='Atravesar Tela', default='predeterminado')
    # Pendientes 24-sep (12.1): cuando el ancho supera el rollo de una tela
    # atravesable, el cliente acepta explícitamente el corte atravesado.
    acepta_atravesado = fields.Boolean(string='Acepta corte atravesado')
    # Pendiente 12.3: rollo (lote) del que saldría la tela de esta persiana,
    # elegido al guardar la cotización (el que mejor se ajusta). Es una
    # sugerencia: la optimización de corte puede cambiarlo.
    lote_sugerido_id = fields.Many2one(
        'stock.lot', string='Rollo sugerido', readonly=True, copy=False)

    # === ESTRUCTURA ===
    coordinado = fields.Selection(COORDINADO_SELECTION, string='Coordinado')

    # === ACCESORIOS ===
    orientation = fields.Selection(ORIENTATION_SELECTION, string='Orientación del enrollado', default='frente')
    # Sprint 1.5: texto y no lista fija — cada sistema tiene sus propias
    # opciones de mando (1 Derecho, 4 Bastón…) y una lista fija rechazaba
    # al guardar los valores de Panel Japonés y de las cortinas.
    mando_position = fields.Char(string='Posición del mando', default='derecha')

    # === MOTOR (solo si has_motor) ===
    has_motor = fields.Boolean(string='Con Motor')
    motor = fields.Char(string='Motor')
    # Reunión 13-oct: el Módulo de Control RF puede venir del menú
    # Referencias (códigos de sus líneas), no solo de la lista fija
    # sin/rf — se guarda como texto, igual que Motor y Control.
    interruptor_rf = fields.Char(string='Interruptor RF')
    motor_support_type = fields.Char(string='Tipo de Soporte Motor')
    control = fields.Char(string='Control Motor')
    control_channel = fields.Char(string='Canal del Control')
    requires_charger = fields.Boolean(string='¿Requiere Cargador?')

    # === DISEÑO DE IMPRESIÓN (solo si tela estampable) ===
    design_print = fields.Boolean(string='Diseño Impresión')
    custom_design = fields.Char(string='Diseño Personalizado')
    design_exterior = fields.Boolean(string='¿Diseño hacia el Exterior?')
    # Puntos 10-11 (OBS REU TELAS): el cliente sube su archivo de diseño con
    # un comentario; se analiza la resolución contra las medidas de la
    # persiana y se genera un ticket de Helpdesk ligado a la cotización.
    design_image = fields.Binary(string='Archivo del diseño', attachment=True)
    design_filename = fields.Char(string='Nombre del archivo')
    design_comment = fields.Text(string='Comentario del diseño')
    design_analysis = fields.Text(string='Análisis de dimensiones', readonly=True)
    design_ticket_id = fields.Many2one(
        'helpdesk.ticket', string='Ticket de diseño', readonly=True, copy=False)
    # Fase 5.3: el área de diseño hace la redimensión, asigna los m² para el
    # cobro (pueden diferir del ancho×alto) y aprueba desde el ticket.
    design_m2_cobro = fields.Float(
        string='M² de cobro (diseño)', digits=(12, 2),
        help='Metros cuadrados asignados por el área de diseño para el '
             'cobro; arrancan iguales al cálculo ancho × alto.')
    design_approved = fields.Boolean(string='Diseño aprobado', copy=False)
    # Ajustes 20-oct (fila 79): el diseñador adjunta el diseño final (imagen o
    # PDF para la planta); el portal muestra ese y no el del cliente.
    design_final_file = fields.Binary(
        string='Diseño aprobado (archivo del diseñador)', attachment=True, copy=False)
    design_final_filename = fields.Char(string='Nombre del diseño aprobado', copy=False)
    # Reunión 15-oct (fila 74): la persiana se salta las restricciones (se
    # muestran, no bloquean). No tiene garantía y producción debe aprobar
    # que se puede fabricar; solo el grupo «Pedidos sin restricciones» la
    # puede marcar en el portal.
    sin_restricciones = fields.Boolean(
        string='Pedido sin restricciones',
        help='Las restricciones se muestran pero no bloquean. La persiana no '
             'tiene garantía y producción debe aprobarla.')
    sin_restricciones_detalle = fields.Text(
        string='Restricciones que se saltó', readonly=True, copy=False)
    sin_restricciones_aprobado = fields.Boolean(
        string='Aprobada por producción', copy=False)
    production_ticket_id = fields.Many2one(
        'helpdesk.ticket', string='Ticket de producción', readonly=True, copy=False)
    # Punto 12 (OBS REU TELAS): los m² de impresión NO se digitan — se
    # calculan en el backend (ancho × alto real) porque el diseño se cobra
    # por m². El valor enviado por el cliente se ignora.
    print_m2 = fields.Float(
        string='Metros Cuadrados de Impresión', digits=(12, 2),
        compute='_compute_print_m2', store=True)

    @api.depends('design_print', 'width', 'height')
    def _compute_print_m2(self):
        for line in self:
            line.print_m2 = (line.width * line.height) if line.design_print else 0.0

    # Los archivos del diseño van a impresión: se guardan como se suben (Odoo
    # reduce las imágenes adjuntas a 1920 px).
    ARCHIVOS_DISENO = ('design_image', 'design_final_file')

    @api.model_create_multi
    def create(self, vals_list):
        if any(set(vals) & set(self.ARCHIVOS_DISENO) for vals in vals_list):
            self = self.with_context(image_no_postprocess=True)
        return super().create(vals_list)

    def write(self, vals):
        if set(vals) & set(self.ARCHIVOS_DISENO):
            self = self.with_context(image_no_postprocess=True)
        return super().write(vals)

    # Impresión de gran formato: por debajo de 40 DPI efectivos la imagen se
    # pixela a distancia normal de observación; 80+ es calidad óptima.
    DESIGN_DPI_MIN = 40
    DESIGN_DPI_GOOD = 80

    def _criterios_diseno(self):
        """Ajustes 20-oct (fila 79): DPI mínimo, óptimo y diferencia de
        proporción del sistema (con los valores de antes como respaldo)."""
        system = self.system_id
        return ((system.diseno_dpi_minimo or self.DESIGN_DPI_MIN),
                (system.diseno_dpi_optimo or self.DESIGN_DPI_GOOD),
                system.diseno_proporcion_max or 0.0)

    @api.model
    def _medidas_imagen(self, data):
        try:
            from PIL import Image
            return Image.open(io.BytesIO(data)).size
        except Exception:
            return None

    def _analyze_design(self, data, filename):
        """Análisis de dimensiones del archivo de diseño contra la persiana.

        Devuelve (texto, es_advertencia). Para imágenes compara la resolución
        en píxeles con el ancho×alto reales (DPI efectivo) y la proporción;
        para PDF solo deja constancia (lo revisa el área de diseño).
        """
        self.ensure_one()
        name = (filename or '').lower()
        if name.endswith('.pdf'):
            return ('Archivo PDF adjunto: la resolución y las medidas se '
                    'verificarán manualmente en el área de diseño.'), False
        medidas = self._medidas_imagen(data)
        if not medidas:
            return ('No fue posible leer la imagen para analizar sus '
                    'dimensiones; el área de diseño la validará '
                    'manualmente.'), True
        px_w, px_h = medidas
        dpi_min, dpi_opt, proporcion = self._criterios_diseno()
        w, h = self.width or 0.0, self.height or 0.0
        # Ajustes 20-oct (fila 80): el diseño propio no se restringe; el
        # análisis es una guía para el área de diseño.
        parts = ['El área de diseño revisará el archivo y lo ajustará a la '
                 'medida de la persiana.', 'Imagen de %d × %d px.' % (px_w, px_h)]
        warning = False
        if w and h:
            # DPI efectivo = píxeles / pulgadas impresas (1 m = 39.37 in)
            dpi = self._dpi_efectivo(px_w, px_h)
            parts.append('Resolución efectiva para %.2f × %.2f m: %.0f DPI.'
                         % (w, h, dpi))
            if dpi < dpi_min:
                warning = True
                parts.append('Resolución baja para el tamaño de la persiana '
                             '(mínimo recomendado %d DPI): la impresión puede '
                             'verse pixelada.' % dpi_min)
            elif dpi < dpi_opt:
                parts.append('Resolución aceptable (recomendado %d DPI o '
                             'más para calidad óptima).' % dpi_opt)
            else:
                parts.append('Resolución óptima para impresión.')
            ratio_img = px_w / px_h if px_h else 0
            ratio_blind = w / h
            if ratio_blind and abs(ratio_img - ratio_blind) / ratio_blind > (proporcion or 10) / 100.0:
                warning = True
                parts.append('La proporción de la imagen (%.2f) no coincide '
                             'con la de la persiana (%.2f): el diseño se '
                             'recortará o deformará al ajustarlo.' % (ratio_img, ratio_blind))
        return '\n'.join(parts), warning

    def _dpi_efectivo(self, px_w, px_h):
        w, h = self.width or 0.0, self.height or 0.0
        return min(px_w / (w * 39.3701), px_h / (h * 39.3701)) if w and h else 0.0

    def _validar_diseno_catalogo(self, add):
        """Ajustes 20-oct (filas 79 y 80): la restricción de resolución va en
        el diseño del catálogo (si su imagen no aguanta la medida, la persiana
        no se guarda y el cliente puede elegir «Diseño propio» para que el área
        de diseño lo revise); el diseño propio ya no se restringe."""
        codigo = self.custom_design
        if not (self.design_print and codigo and codigo != 'OTROS' and self.width and self.height):
            return
        diseno = self.env['safra.design'].sudo().with_context(active_test=False).search(
            [('code', '=', codigo)], limit=1)
        medidas = diseno.image_print and self._medidas_imagen(base64.b64decode(diseno.image_print))
        if not medidas:
            return
        px_w, px_h = medidas
        dpi_min, _opt, proporcion = self._criterios_diseno()
        dpi = self._dpi_efectivo(px_w, px_h)
        motivo = ''
        if dpi < dpi_min:
            motivo = 'la resolución a %.2f × %.2f m es de %.0f DPI (mínimo %.0f)' % (
                self.width, self.height, dpi, dpi_min)
        elif proporcion and px_h:
            ratio_img, ratio_blind = px_w / px_h, self.width / self.height
            if abs(ratio_img - ratio_blind) / ratio_blind * 100 > proporcion:
                motivo = 'la proporción de la imagen (%.2f) no coincide con la de la persiana (%.2f)' % (
                    ratio_img, ratio_blind)
        if motivo:
            add('V_DISENO_RESOLUCION', 'error',
                'E20043: El diseño {diseno} no se puede imprimir a esta medida: {motivo}. '
                'Elija otro diseño o marque «Diseño propio» para que el área de diseño lo revise.',
                diseno=diseno.name or codigo, motivo=motivo)

    def _design_display(self):
        """Nombre legible del diseño elegido (código del catálogo safra.design)."""
        self.ensure_one()
        if not self.custom_design:
            return ''
        design = self.env['safra.design'].sudo().search(
            [('code', '=', self.custom_design)], limit=1)
        if design and design.name != design.code:
            return '%s (%s)' % (design.name, design.code)
        return self.custom_design

    def _create_design_ticket(self):
        """Crea el ticket de Helpdesk del diseño personalizado de esta línea."""
        self.ensure_one()
        if self.design_ticket_id:
            return self.design_ticket_id
        Ticket = self.env['helpdesk.ticket'].sudo()
        Team = self.env['helpdesk.team'].sudo()
        team = Team.search([('name', 'ilike', 'dise')], limit=1) or Team.search([], limit=1)
        quote = self.quote_id
        rows = [
            ('Cotización', quote.name or ''),
            ('Cliente', quote.partner_id.display_name or ''),
            ('Sistema', self.system_id.name or ''),
            ('Referencia / Tela', self.fabric_id.name or ''),
            ('Color', self.color_id.name or ''),
            ('Ancho × Alto', '%.2f m × %.2f m' % (self.width or 0, self.height or 0)),
            ('Cantidad', '%d' % (self.quantity or 0)),
            ('M² de impresión', '%.2f m²' % (self.print_m2 or 0)),
            ('¿Diseño hacia el exterior?', 'Sí' if self.design_exterior else 'No'),
            ('Diseño seleccionado', self._design_display() or 'Sin diseño'),
            ('Archivo', self.design_filename or 'Sin archivo'),
        ]
        body = Markup('<h4>Diseño personalizado</h4><table class="table table-sm">')
        for label, value in rows:
            body += Markup('<tr><td><strong>%s</strong></td><td>%s</td></tr>') % (label, value)
        body += Markup('</table>')
        if self.design_analysis:
            body += Markup('<p><strong>Análisis de dimensiones:</strong><br/>%s</p>') % (
                Markup('<br/>').join(escape(p) for p in self.design_analysis.split('\n')))
        if self.design_comment:
            body += Markup('<p><strong>Comentario del cliente:</strong><br/>%s</p>') % (
                Markup('<br/>').join(escape(p) for p in self.design_comment.split('\n')))
        ticket = Ticket.create({
            'name': 'Diseño personalizado - %s - %s %s' % (
                quote.name or '', self.system_id.name or '',
                self.location or ('Persiana %d' % (self.sequence // 10))),
            'team_id': team.id or False,
            'partner_id': quote.partner_id.id,
            'description': body,
            'safra_quote_id': quote.id,
            'safra_quote_line_id': self.id,
        })
        if self.design_image:
            self.env['ir.attachment'].sudo().with_context(image_no_postprocess=True).create({
                'name': self.design_filename or 'diseno.png',
                'datas': self.design_image,
                'res_model': 'helpdesk.ticket',
                'res_id': ticket.id,
            })
        self.design_ticket_id = ticket
        # Los m² de cobro arrancan iguales al cálculo; el diseñador los
        # ajusta en el ticket al hacer la redimensión (fase 5.3).
        if not self.design_m2_cobro:
            self.design_m2_cobro = self.print_m2
        return ticket

    # Atributos del portal (JSON): campos configurables sin columna propia
    # (cantidad de lamas, apertura, ancho de telo, sesgo, riel, etc.).
    # Presentación legible para el backoffice: etiqueta del campo y, en las
    # listas, la etiqueta de la opción (respetando overrides por sistema).
    attributes_display = fields.Text(
        string='Atributos del portal', compute='_compute_attributes_display')

    @api.depends('attribute_values', 'system_id')
    def _compute_attributes_display(self):
        SField = self.env['safra.field'].sudo()
        Mapping = self.env['safra.system.field'].sudo()
        fields_by_code = {f.code: f for f in SField.search([])}
        for line in self:
            attrs = line.attribute_values or {}
            rows = []
            for code, value in attrs.items():
                field = fields_by_code.get(code)
                label = field.name if field else code
                display = value
                if isinstance(value, bool):
                    display = 'Sí' if value else 'No'
                elif field and field.field_type == 'ref_categoria':
                    # P16: el valor es el código del producto/color elegido.
                    color = self.env['safra.fabric.color'].sudo().search(
                        [('code', '=', str(value))], limit=1)
                    if color:
                        display = '%s (%s)' % (color._portal_label(), value)
                elif field and field.field_type == 'selection':
                    # Override del sistema primero; luego el catálogo global.
                    opts = field.option_ids
                    if line.system_id:
                        m = Mapping.search([
                            ('system_id', '=', line.system_id.id),
                            ('field_id', '=', field.id)], limit=1)
                        if m.option_ids:
                            opts = m.option_ids
                    match = opts.filtered(lambda o: str(o.value) == str(value))
                    if match:
                        display = match[0].name
                rows.append('%s: %s' % (label, display))
            line.attributes_display = '\n'.join(rows)

    # === CENEFA ===
    cenefa_type = fields.Selection(CENEFA_TIPO_SELECTION, string='Tipo de Cenefa', default='sin')
    cenefa_lateral = fields.Selection(LATERALES_CENEFA_SELECTION, string='Laterales Cenefa', default='sin')
    cenefa_lined = fields.Boolean(string='¿Cenefa forrada?')
    cenefa_tela = fields.Char(string='Tela de Cenefa')
    cenefa_corte = fields.Char(string='Tipo de corte Cenefa Tela')

    # === PERFIL COVER LIGHT ===
    # Ajustes 20-oct (filas 94 y 95): el perfil y la felpa salen de
    # Referencias; se guarda la línea elegida (código o «ref-<id>»).
    cover_light_profile = fields.Char(string='Perfil Cover Light')
    coverlight_felpa = fields.Char(string='¿Coverlight con Felpa?')
    coverlight_45 = fields.Boolean(string='¿Coverlight a 45°?')

    # === CORDÓN / CADENA ===
    extra_chain = fields.Float(string='Extra Cadena / Cordón (m)', digits=(12, 2))

    # === OTRAS OPCIONES ===
    enclosed = fields.Boolean(string='Persiana Encajonada')
    # Sprint 1.5: las escuadras salen de Referencias (código del producto).
    escuadras = fields.Char(string='Escuadras')
    bolsillo_size = fields.Selection(BOLSILLO_SELECTION, string='Tamaño del bolsillo')
    # Sprint 1.6 (fila 127): se marca en el pedido y cada persiana lo lleva
    # para el informe de productos que salieron con Safra Express.
    safra_express = fields.Boolean(
        string='Safra Express', related='quote_id.safra_express', store=True)
    quote_partner_id = fields.Many2one(
        related='quote_id.partner_id', string='Cliente', store=True)
    quote_date = fields.Date(related='quote_id.date', string='Fecha', store=True)
    quote_state = fields.Selection(related='quote_id.state', string='Estado del pedido')
    description = fields.Text(string='Comentarios')

    # === ATRIBUTOS DINÁMICOS ===
    # Almacena los valores de campos configurables que no tienen columna dedicada
    # (campos propios de otros sistemas: sesgo, apertura, cabezal, riel, etc.).
    attribute_values = fields.Json(string='Atributos dinámicos')

    # === PRECIOS ===
    price_unit = fields.Float(string='Precio unitario', digits=(12, 0))
    price_total = fields.Float(string='Total', compute='_compute_price_total', store=True)

    @api.depends('price_unit', 'quantity')
    def _compute_price_total(self):
        for line in self:
            line.price_total = line.price_unit * line.quantity

    # === MOTOR DE VALIDACIONES (archivo "Restricciones y Validaciones") ===
    # Cada validación tiene código, severidad y mensaje por defecto; el
    # registro homónimo en safra.validation.rule (menú Configuración >
    # Validaciones) permite desactivarla o cambiar severidad/mensaje.

    # Sistemas exentos de Localización (grupos de asociación del cliente).
    _LOCATION_EXEMPT = {'43', '33', '34', '52', '31', '56', '58', '59'}

    def _validations(self):
        """Hallazgos del cálculo interno de la línea: lista de dicts {code,
        severity, message, fmt}. Sprint 1.7: aquí no se aplica la
        configuración; cada hallazgo pasa por su regla en _aplicar_reglas
        (condición, momento, sistemas, severidad y mensaje)."""
        self.ensure_one()
        results = []

        def add(code, severity, message, **fmt):
            try:
                msg = message.format(**fmt)
            except (KeyError, IndexError):
                msg = message
            results.append({'code': code, 'severity': severity,
                            'message': msg, 'fmt': fmt})

        system = self.system_id
        sys_code = system.code or ''
        attrs = self.attribute_values or {}
        w, h = self.width or 0.0, self.height or 0.0

        # --- Rango de la ficha técnica (F63-F66 matriz; revisión sprint 1:
        # los U_AnchoMin/Max y U_AltoMin/Max del producto terminado mandan) ---
        # Reunión 28-sep (fila 3): con Exhibición rige la ficha de exhibición.
        if system:
            lim = system._tech_limits(exhibition=bool(self.exhibition))
            rango = 'de exhibición del sistema' if self.exhibition else 'del sistema'
            if w and ((lim['wmin'] and w < lim['wmin'])
                      or (lim['wmax'] and w > lim['wmax'])):
                add('V_RANGO_ANCHO', 'error',
                    'OB0005: El ancho {ancho} m está fuera del rango {rango} '
                    '({wmin} - {wmax} m).', ancho=w, rango=rango,
                    wmin=lim['wmin'], wmax=lim['wmax'])
            if h and ((lim['hmin'] and h < lim['hmin'])
                      or (lim['hmax'] and h > lim['hmax'])):
                add('V_RANGO_ALTO', 'error',
                    'OB0005: El alto {alto} m está fuera del rango {rango} '
                    '({hmin} - {hmax} m).', alto=h, rango=rango,
                    hmin=lim['hmin'], hmax=lim['hmax'])

        # --- Estructura por ancho + fórmulas de alto/peso máximo ---
        Rule = self.env['safra.structure.rule'].sudo()
        has_structure, rule, limits = self._estructura_linea()
        # Reunión 09-nov (fila 68, puntos 2 y 3): la persiana manual que no se
        # puede fabricar (sin tubo para el ancho, o alto o peso mayores a los
        # del mecanismo) se prueba con motor — con los motores del sistema y
        # su torque o carga del maestro —; si así sí se puede, se le pide al
        # cliente marcar el motor (no se marca solo).
        # Revisión 10-nov: «debe ir motorizada» (V_REQUIERE_MOTOR), «sin
        # componentes» (V_ESTRUCTURA), el alto máximo (V_ALTO_MAXIMO) y el
        # peso (V_PESO_MAXIMO, V_PESO_SIN_CARGA) son reglas de Validaciones
        # con su condición escrita allí (variables estructura[...]). Respaldo:
        # si una base todavía tiene alguna con la condición «hallazgo», el
        # cálculo interno lo sigue encontrando para que no deje de salir.
        self._hallazgos_tubo_respaldo(add, has_structure, rule, limits)
        if rule:
            # Revisión 10-nov: el peso contra la carga máxima (V_PESO_MAXIMO)
            # y el motor sin datos (V_PESO_SIN_CARGA) son reglas de
            # Validaciones con su condición escrita allí (variables
            # estructura[...]); el código solo calcula los datos.
            # Proporción alto vs ancho (solo sistemas con tabla: enrollables).
            if w and h and h > w * 3:
                add('V_ALTO_3X_ANCHO', 'warning',
                    'W10005: La persiana tiene un alto mayor a 3 veces su ancho.')

        # --- Reunión 15-oct (filas 50 y 68): tubo sin insumos y opciones que
        # solo sirven para ciertas telas o ciertos tubos.
        self._validaciones_15oct(add, rule)

        # --- Kit motorizado: control compatible y ancho mínimo motor ---
        # Sprint 1.7: también con el motor elegido por referencia (sin la
        # casilla Motorizado).
        if self._con_motor() and self.motor and self.motor != '7':
            # Cálculo interno (solo si la regla no tiene condición propia).
            minimo = self._motor_ancho_min() or 0.70
            if w and w < minimo:
                add('V_ANCHO_MIN_MOTOR', 'error',
                    'E13095: El ancho mínimo para una persiana motorizada es '
                    'de {minimo} m.', minimo=minimo)
            kit = rule._kit_for(self.motor) if rule else self.env['safra.motor.kit'].find_kit(self.motor, '')
            if self.control and self.control not in ('0', 'sin'):
                motor_ref = self._motor_con_controles_de_referencia()
                if motor_ref:
                    # Sprint 1.2: con referencia de controles manda su
                    # columna «Motores (solo estos)», no el kit.
                    lineas = self.env['safra.fabric.color']._lineas_control(motor_ref, self.system_id)
                    compatible = any(self.control in (l._valor_control(), l.code) for l in lineas)
                    motor_name = motor_ref.name
                elif kit:
                    allowed = [v.strip() for v in (kit.control_values or '').split(',') if v.strip()]
                    compatible = not allowed or self.control in allowed
                    motor_name = kit.motor_name
                else:
                    compatible = True
                if not compatible:
                    add('V_CONTROL_MOTOR', 'error',
                        'E13095: El control seleccionado no es compatible con '
                        'el motor «{motor}».', motor=motor_name)

        # --- Localización obligatoria (salvo sistemas exentos) ---
        if not self.location and sys_code not in self._LOCATION_EXEMPT:
            add('V_LOCALIZACION', 'error',
                "E13095: Por favor ingrese un valor en el campo 'Localización'.")

        # --- Revisión 27-oct (pruebas de Safra): con cenefa elegida, ¿Cenefa
        # dividida? debe decir Sí o No. Se revisa solo cuando el campo se ve
        # (su dependencia de Tipo de Cenefa, como en el portal). ---
        if system:
            maps = self.env['safra.system.field'].sudo().search([
                ('system_id', '=', system.id), ('active', '=', True),
                ('field_id.active', '=', True)])
            dividida = maps.filtered(lambda m: m.field_id.code == 'cenefa_dividida')[:1]
            if dividida and not self._valor_formulario('cenefa_dividida') \
                    and self._campo_visible(dividida, maps):
                add('V_CENEFA_DIVIDIDA', 'error',
                    'E13095: Indique si la cenefa va dividida (Sí o No).')

        # --- Segunda tela obligatoria en 2 en 1 / Sheer 2 en 1 ---
        if sys_code in ('32', '61') and not self.fabric_id_2:
            add('V_SEGUNDA_TELA', 'error',
                'E13022: Por favor seleccione la segunda tela de la persiana '
                '2 en 1.')

        # --- Orientación del enrollado en Sheer 2 en 1: solo hacia el frente ---
        if sys_code == '61' and self.orientation and self.orientation != 'frente':
            add('V_ENROLLE_SHEER', 'error',
                "E13095: En el sistema SHEER 2EN1 solo se permite 'Orientación "
                "del Enrollado' hacia el frente.")

        # --- Cadena/cordón extra en rango razonable ---
        if self.extra_chain and h:
            if self.extra_chain > h + 2.50 or self.extra_chain < (h * 1.50) / 2:
                add('V_CADENA_EXTRA', 'error',
                    'E13082: La cadena/cordón extra debe estar entre {minimo} y '
                    '{maximo} m para el alto digitado.',
                    minimo=round((h * 1.50) / 2, 2), maximo=round(h + 2.50, 2))

        # --- Atravesar tela solo si la tela lo permite ---
        if self.atravesar_tela == 'atravesar' and self.fabric_id and self.fabric_id.pierceable_type != 'si_cliente':
            add('V_ATRAVESADO', 'error',
                'E13026: La tela seleccionada no permite forzar el corte '
                'atravesado.')

        # --- Estampado: los m² de impresión deben cubrir la persiana ---
        if self.design_print and w and h:
            m2 = attrs.get('print_m2') or self.print_m2 or 0.0
            if m2 and m2 < w * h:
                add('V_ESTAMPADO_M2', 'error',
                    'E10027: Los m² de impresión ({m2imp}) son menores al área '
                    'de la persiana ({m2}).', m2imp=m2, m2=round(w * h, 2))

        # --- Cenefa en tela con corte «Entera»: si el ancho supera el rollo,
        # solo telas que lo permiten (revisión sprint 1 f94; ajustes 20-oct
        # fila 91: por debajo del rollo puede ir entera; reunión 28-oct: la
        # tela debe ser atravesable).
        if str(attrs.get('corte_cenefa') or '') == '2' \
                and self._corte_cenefa_tela()['tipo'] == 'anadida':
            add('V_CENEFA_ENTERA', 'error',
                'E20003: El ancho supera el ancho del rollo y la tela no se puede '
                'atravesar; elija «Cenefa añadida» u otra tela.')

        # --- Diseño Impresión activo: debe elegirse el diseño (catálogo u
        # OTROS); el archivo se exige aparte en el submit (va como adjunto).
        if self.design_print and not self.custom_design:
            add('V_DISENO_SELECCION', 'error',
                'E20002: Elija el diseño a imprimir en el catálogo con '
                'imágenes, o marque «Diseño propio» para subir su imagen.')
        self._validar_diseno_catalogo(add)

        # --- Panel Track (P19, fórmula Best Fit): la combinación de ancho,
        # traslape y cantidad de lamas/telos debe tener configuración
        # fabricable. Solo aplica a los sistemas con tabla de lamas (los que
        # tienen configurado el Tamaño del Traslape).
        try:
            lamas = int(attrs.get('quantity_lamas') or 0)
        except (TypeError, ValueError):
            lamas = 0
        if lamas and w and system and 'tamano_traslape' in self._system_field_codes():
            try:
                traslape = float(str(attrs.get('tamano_traslape') or 0.08).replace(',', '.'))
            except (TypeError, ValueError):
                traslape = 0.08
            Track = self.env['safra.panel.track']
            # Sprint 1.7: la Doble función de Panel Duo (6) tampoco sale de la
            # tabla de combinaciones (dos rieles); se revisa como la libre.
            ap_libre = {'libre': 'libre', '5': 'libre', '6': 'doble función'}
            es_libre = str(attrs.get('apertura') or '') in ap_libre
            configs = [] if es_libre else Track.compute_configs(
                w, traslape, lamas, campos=self._campos_formula(), system=system)
            if es_libre:
                # Correo de Safra (19-oct): la Apertura Libre la escoge el
                # cliente aunque no salga en las combinaciones; solo se
                # revisa el ancho de cada telo (sin tabla ni riel).
                falla = Track.revisar_libre(w, traslape, lamas,
                                            campos=self._campos_formula(), system=system)
                if falla:
                    add('V_PANEL_LAMAS', 'error',
                        'E20001: Con apertura {apertura}, {lamas} telos en {ancho} m dan '
                        'telos de {telo} cm; cada telo debe medir entre {minimo} '
                        'y {maximo} cm (hasta {telos_max} telos y {ancho_max} m de ancho).',
                        apertura=ap_libre[str(attrs.get('apertura'))],
                        lamas=lamas, ancho=w, telo=falla['telo_cm'],
                        minimo=falla['min_cm'], maximo=falla['max_cm'],
                        telos_max=falla['max_telos'], ancho_max=falla['ancho_max'])
                elif ap_libre[str(attrs.get('apertura'))] == 'libre' and attrs.get('riel_tipo'):
                    # Mejoras Sprint 1.1 (21-oct, fila 16): con Apertura Libre
                    # el riel sigue siendo uno de los de las combinaciones
                    # posibles para esos telos (si las hay).
                    permitidos = {self._riel_de_combinacion(c) for c in Track.compute_configs(
                        w, traslape, lamas, campos=self._campos_formula(), system=system)} - {None}
                    elegido = self._riel_tipo_info(attrs.get('riel_tipo'))
                    if permitidos and elegido is not None and elegido not in permitidos:
                        add('V_PANEL_RIEL', 'error',
                            'E20029: Con {lamas} telos en {ancho} m y apertura libre los rieles '
                            'posibles son: {rieles}; el Tipo de Riel elegido ({elegido}) no '
                            'corresponde.', lamas=lamas, ancho=w,
                            rieles=', '.join(sorted(self._riel_nombre(r) for r in permitidos)),
                            elegido=self._riel_tipo_label(attrs.get('riel_tipo')))
            elif not configs:
                add('V_PANEL_LAMAS', 'error',
                    'E20001: Con ancho {ancho} m y traslape {traslape} m no '
                    'existe una configuración válida de {lamas} telos '
                    '(revise la tabla de configuraciones posibles).',
                    ancho=w, traslape=traslape, lamas=lamas)
            elif attrs.get('apertura'):
                # Valores globales ('derecha'…) y numéricos del override de
                # Panel Japonés (1=Derecha, 2=Izquierda, 3=Extremos, 4=Centro,
                # 5=Libre). Reunión 28-sep (fila 16): la Apertura Libre ya no
                # pasa sin revisar — también debe salir en las combinaciones.
                ap_map = {'derecha': 'unilateral_derecha', '1': 'unilateral_derecha',
                          'izquierda': 'unilateral_izquierda', '2': 'unilateral_izquierda',
                          'extremos': 'extremos', '3': 'extremos',
                          'centro': 'centro', '4': 'centro',
                          'libre': 'libre', '5': 'libre'}
                valid_aps = {c['codigo_apertura'] for c in configs}
                elegida = [c for c in configs
                           if c['codigo_apertura'] == ap_map.get(str(attrs['apertura']))]
                if elegida and attrs.get('riel_tipo'):
                    # Reunión 09-oct (fila 16): el Tipo de Riel debe ser el
                    # de la combinación (N vías o Riel Velcrado). Revisión
                    # 10-nov: la misma apertura puede venir en varios rieles
                    # (7 telos en riel 6 velcrado o en riel 7): sirve cualquiera.
                    permitidos = [r for r in dict.fromkeys(
                        self._riel_de_combinacion(c) for c in elegida) if r]
                    elegido = self._riel_tipo_info(attrs.get('riel_tipo'))
                    if permitidos and elegido is not None and elegido not in permitidos:
                        add('V_PANEL_RIEL', 'error',
                            'E20029: Con {lamas} telos y apertura {apertura} la '
                            'combinación lleva {riel}; el Tipo de Riel elegido '
                            '({elegido}) no corresponde.',
                            lamas=lamas, apertura=elegida[0]['tipo_apertura'],
                            riel=' o '.join(self._riel_nombre(r) for r in permitidos),
                            elegido=self._riel_tipo_label(attrs.get('riel_tipo')))
                if ap_map.get(str(attrs['apertura'])) not in valid_aps:
                    # Pendientes 24-sep (7.2/8.1): fuera de las combinaciones
                    # posibles NO se puede fabricar — bloquea el pedido.
                    add('V_PANEL_APERTURA', 'error',
                        'E20014: Con {lamas} telos y ancho {ancho} m la '
                        'apertura seleccionada no se puede fabricar; las '
                        'combinaciones posibles son: {opciones}.',
                        lamas=lamas, ancho=w,
                        opciones=', '.join(sorted({c['tipo_apertura'] for c in configs})))

        # --- OBS REU GENERALES 11-sep: en paneles con varias telas, la suma
        # de lamas por tela no debe exceder la cantidad total de lamas (y
        # avisa cuando no la completa).
        def _int(v):
            try:
                return int(v or 0)
            except (TypeError, ValueError):
                return 0

        fabric_slots = [
            (1, bool(self.fabric_id)),
            (2, bool(self.fabric_id_2)),
            (3, bool(self.fabric_id_3)),
            (4, bool(attrs.get('fabric_id_4'))),
            (5, bool(attrs.get('fabric_id_5'))),
        ]
        lamas_tela = {n: _int(attrs.get('lamas_tela_%d' % n)) for n, _ in fabric_slots}
        # Pendientes 24-sep (11.1): con una sola tela no se piden lamas por
        # tela; con dos o más, cada tela debe traer su cantidad y la suma
        # debe ser EXACTAMENTE la cantidad total (bloqueante).
        telas_activas = [n for n, filled in fabric_slots if filled]
        if lamas and len(telas_activas) >= 2:
            sin_lamas = [n for n in telas_activas if not lamas_tela.get(n)]
            if sin_lamas:
                add('V_LAMAS_TELA_SUMA', 'error',
                    'E20018: Con varias telas debe indicar cuántas lamas '
                    'van en cada una (falta la tela {telas}).',
                    telas=', '.join(str(n) for n in sin_lamas))
            else:
                suma = sum(lamas_tela.get(n, 0) for n in telas_activas)
                if suma > lamas:
                    add('V_LAMAS_TELA', 'error',
                        'E20004: La suma de lamas por tela ({suma}) excede '
                        'la cantidad total de lamas ({total}).',
                        suma=suma, total=lamas)
                elif suma != lamas:
                    add('V_LAMAS_TELA_SUMA', 'error',
                        'E20018: La suma de lamas por tela ({suma}) debe '
                        'ser igual a la cantidad total de lamas ({total}).',
                        suma=suma, total=lamas)

        # --- OBS 11-sep, ajustada en la revisión del 17-sep: lo que no se
        # repite es la COMBINACIÓN referencia+color (la misma referencia con
        # colores distintos sí es válida — p. ej. un panel combinando dos
        # colores del mismo blackout).
        seen = {}
        for n, _filled in fabric_slots:
            if n == 1:
                fid, cid = self.fabric_id.id, self.color_id.id
            elif n == 2:
                fid, cid = self.fabric_id_2.id, self.color_id_2.id
            elif n == 3:
                fid, cid = self.fabric_id_3.id, self.color_id_3.id
            else:
                fid = _int(attrs.get('fabric_id_%d' % n))
                cid = attrs.get('color_id_%d' % n) or ''
            if not fid or not cid:
                continue
            key = (fid, str(cid))
            if key in seen:
                add('V_TELAS_REPETIDAS', 'error',
                    'E20005: La Referencia {b} repite la misma tela y color '
                    'de la Referencia {a}; elija un color distinto.',
                    a=seen[key], b=n)
            else:
                seen[key] = n

        # --- Revisión 17-sep (#19): máximo total de lamas/pantógrafos.
        # En los sistemas con fórmula (Vertical/Vintage), la cantidad de
        # lamas debe ser exactamente el máximo calculado para el ancho,
        # apertura y accionamiento — la suma por tela ya se valida aparte.
        if lamas and w and system:
            ap_map19 = {'1': 'derecha', '2': 'izquierda', '3': 'extremos', '4': 'centro'}
            ap_raw = str(attrs.get('apertura') or '')
            es_motor = bool(self.has_motor) or bool(
                self.motor and self.motor not in ('0', 'sin'))
            maximo = self.env['safra.lamas.rule'].sudo().compute_max(
                system, w, ap_map19.get(ap_raw, ap_raw),
                motorized=es_motor, campos=self._campos_formula())
            if maximo is not None and lamas != maximo:
                add('V_MAX_LAMAS', 'error',
                    'E20012: Para {ancho} m con esta apertura el total de '
                    'lamas debe ser {maximo} (digitó {lamas}).',
                    ancho=w, maximo=maximo, lamas=lamas)

        # --- Pendientes 24-sep (11.2/11.3): reglas de familia en los 2 en 1.
        # ENROLLABLE 2 EN 1 (32): una tela Blackout y una Sheer (cualquier
        # orden). SHEER 2 EN 1 (61): la Referencia 1 es Blackout y la
        # Referencia 2 es Sheer.
        if sys_code == '32' and self.fabric_id and self.fabric_id_2:
            familias = {self.fabric_id.is_blackout or self.fabric_id_2.is_blackout,
                        self.fabric_id.is_sheer or self.fabric_id_2.is_sheer}
            if familias != {True}:
                add('V_2EN1_FAMILIA', 'error',
                    'E20008: El Enrollable 2 en 1 requiere una tela de la '
                    'familia Blackout y una de la familia Sheer.')
        if sys_code == '61' and self.fabric_id and self.fabric_id_2 \
                and not (self.fabric_id.is_blackout and self.fabric_id_2.is_sheer):
            add('V_SHEER2EN1_REF', 'error',
                'E20009: En el Sheer 2 en 1 la Referencia 1 debe ser de la '
                'familia Blackout y la Referencia 2 de la familia Sheer.')

        # --- Revisión 17-sep: en telas NO atravesables, el ancho real no
        # puede superar el ancho del rollo (U_Ancho del artículo del color;
        # sin ese dato, el mayor de los rollos de la referencia). Con tela
        # atravesable la fábrica gira el corte y la regla no aplica.
        if self.fabric_id and self.fabric_id.pierceable_type == 'no' and w \
                and not self.fabric_id.is_anadido:
            rollo = self._ancho_rollo()
            if rollo and w > rollo:
                add('V_ANCHO_ROLLO', 'error',
                    'E20007: El ancho digitado ({ancho} m) supera el ancho '
                    'del rollo de {tela} ({rollo} m) y la tela no es '
                    'atravesable; no es posible fabricarla.',
                    ancho=w, rollo=rollo, tela=self.fabric_id.name)

        # --- Pendientes 24-sep (12.1/12.2): con tela ATRAVESABLE ('si' o
        # 'si/cliente') y el ancho por encima del rollo, la tela se corta
        # atravesada — se avisa y el cliente debe aceptarlo (sin obligarlo
        # a marcar «Atravesar Tela», que sigue siendo su opción).
        if self.fabric_id and w \
                and self.fabric_id.pierceable_type in ('si', 'si_cliente'):
            rollo_atr = self._ancho_rollo()
            if rollo_atr and w > rollo_atr and not self.acepta_atravesado:
                add('V_CORTE_ATRAVESADO', 'error',
                    'E20017: Con el ancho digitado ({ancho} m) la tela '
                    '{tela} se cortará atravesada (rollo de {rollo} m); '
                    'marque la aceptación del corte atravesado para '
                    'continuar.',
                    ancho=w, rollo=rollo_atr, tela=self.fabric_id.name)

        # --- Sprint 1.5 (filas 97-121): opciones por dependencia, telo fijo,
        # bolsillo y segmentos del riel curvo.
        self._validaciones_sprint15(add, attrs, w, lamas)

        # --- OBS 11-sep: Blackout Texturizado — con una tela texturizable
        # debe escogerse el diseño de textura del catálogo.
        if self.fabric_id and self.fabric_id.is_texturable \
                and 'textura_design' in self._system_field_codes() \
                and not attrs.get('textura_design'):
            add('V_TEXTURA_SELECCION', 'error',
                'E20006: La referencia {tela} es texturizada: elija el '
                'diseño de textura en el catálogo con imágenes.',
                tela=self.fabric_id.name)

        return results

    def _estructura_linea(self):
        """(tiene tabla, regla efectiva, límites) de la tabla de estructura
        para la línea. Sprint 1.3: la estructura considera el cabezal
        elegido (como el portal) y la Unificación Mando (tubo mayor al
        calculado). Revisión cálculo de tubo (27-oct, error 6): si el alto
        no alcanza con ese tubo, pasa al siguiente que sí alcance."""
        self.ensure_one()
        system = self.system_id
        attrs = self.attribute_values or {}
        w, h = self.width or 0.0, self.height or 0.0
        Rule = self.env['safra.structure.rule'].sudo()
        has_structure = bool(system) and bool(Rule.search_count([('system_ids', 'in', system.id)]))
        rule, limits = Rule.browse(), {}
        if has_structure:
            res = Rule.elegir(system, w, h,
                              motorized=bool(self.has_motor or attrs.get('unificacion_motor')),
                              cabezal=self._cabezal_elegido()[0],
                              unificacion=attrs.get('unificacion_mando') or None,
                              **self._params_estructura())
            rule, limits = res['regla'], res['limites']
        return has_structure, rule, limits

    REGLAS_TUBO_VISIBLES = ('V_REQUIERE_MOTOR', 'V_ESTRUCTURA', 'V_ALTO_MAXIMO',
                            'V_PESO_MAXIMO', 'V_PESO_SIN_CARGA')

    def _hallazgos_tubo_respaldo(self, add, has_structure, rule, limits):
        """Respaldo de las reglas del tubo que pasaron a tener la condición
        escrita en Validaciones (revisión 10-nov): solo para las que todavía
        tienen «hallazgo» en su condición (o no tienen condición), el
        cálculo interno deja el hallazgo como antes. Con la condición
        escrita, no se usa."""
        reglas = self.env['safra.validation.rule'].sudo()._por_clave(self.REGLAS_TUBO_VISIBLES)
        usan = {r._clave_programa() for r in reglas
                if 'hallazgo' in (r.condition_code or 'hallazgo')}
        if not usan:
            return
        w = self.width or 0.0
        alternativa = self._alternativa_motor(has_structure, rule, limits)
        nombre_tubo = self.env['safra.structure.rule'].nombre_tubo
        if alternativa and 'V_REQUIERE_MOTOR' in usan:
            add('V_REQUIERE_MOTOR', 'error', R17.MENSAJE_REQUIERE_MOTOR, ancho=w,
                tubo_motor=nombre_tubo(alternativa['tubo']))
        elif not alternativa and has_structure and w and not rule and 'V_ESTRUCTURA' in usan:
            add('V_ESTRUCTURA', 'error', R17.CAMBIOS['V_ESTRUCTURA']['message'], ancho=w)
        if not rule:
            return
        estructura = {'alto_maximo': limits.get('alto_maximo'), 'peso': limits.get('peso_total') or 0.0,
                      'carga': limits.get('carga_maxima'), 'carga_detalle': limits.get('carga_detalle') or ''}
        if limits.get('alto_ok') is False and 'V_ALTO_MAXIMO' in usan:
            add('V_ALTO_MAXIMO', 'error', R17.CAMBIOS['V_ALTO_MAXIMO']['message'],
                estructura=estructura, alto_maximo=limits.get('alto_maximo'))
        motor_elegido = self._params_estructura().get('motor_elegido')
        if alternativa:
            return
        if limits.get('peso_ok') is False and 'V_PESO_MAXIMO' in usan:
            add('V_PESO_MAXIMO', 'error', R17.PESO_MAXIMO_MENSAJE, estructura=estructura,
                quien='el motor elegido' if motor_elegido else 'el mecanismo')
        elif limits.get('carga_sin_dato') and motor_elegido and 'V_PESO_SIN_CARGA' in usan:
            add('V_PESO_SIN_CARGA', 'error', R17.PESO_SIN_CARGA['message'], estructura=estructura)

    def _alternativa_motor(self, has_structure=None, rule=None, limits=None):
        """Reunión 09-nov (fila 68, puntos 2 y 3): la persiana manual que no
        se puede fabricar (sin tubo para el ancho, o alto o peso mayores a los
        del mecanismo) se prueba con motor — con los motores del sistema y su
        torque o carga del maestro —. {'tubo', 'motor', 'limites'} si con
        motor sí se puede; None si no (o si ya va con motor)."""
        self.ensure_one()
        if has_structure is None:
            has_structure, rule, limits = self._estructura_linea()
        attrs = self.attribute_values or {}
        system, w, h = self.system_id, self.width or 0.0, self.height or 0.0
        if not has_structure or not w or self.has_motor or attrs.get('unificacion_motor'):
            return None
        limits = limits or {}
        if rule and limits.get('alto_ok') is not False and limits.get('peso_ok') is not False:
            return None
        Rule = self.env['safra.structure.rule'].sudo()
        alternativa = Rule.alternativa_motor(
            system, w, h, cabezal=self._cabezal_elegido()[0],
            unificacion=attrs.get('unificacion_mando') or None,
            motores=self._motores_sistema(), **self._params_estructura())
        # Matriz 1.7 ([24]): fuera de la tabla manual pero dentro de la
        # motorizada también va motorizada (no «sin componentes»).
        if not alternativa and not rule:
            regla_motor = Rule.find_rule(system, w, motorized=True)
            if regla_motor:
                alternativa = {'tubo': regla_motor.tubo, 'motor': None, 'limites': {}}
        return alternativa

    def _params_estructura(self):
        """Datos de la persiana para las fórmulas de alto y peso máximo."""
        self.ensure_one()
        attrs = self.attribute_values or {}
        return self._params_estructura_de(
            self.system_id, self.fabric_id,
            attrs.get('perfil') or attrs.get('perfil_sheer') or attrs.get('perfileria2'),
            self._valor_formulario('motor') if self.has_motor else '')

    @api.model
    def _params_estructura_de(self, system, fabric, perfil, motor):
        """Parámetros de compute_limits: peso y grosor de la tela, peso del
        perfil, factor del sistema y, con motor, su torque y su carga
        máxima del maestro (revisión cálculo de tubo, error 5 y hoja 4)."""
        producto = self._producto_motor(motor)
        # Un dato sin digitar llega vacío (False) a las fórmulas del tubo;
        # sin tela o sin motor, 0.
        return {'peso_tela': fabric.peso_gm2 if fabric else 0.0,
                'grosor_tela': fabric.grosor_mm if fabric else 0.0,
                'peso_perfil': self._peso_perfil(perfil),
                'factor': (system.weight_factor or 1.0) if system else 1.0,
                'torque': producto.safra_torque if producto else 0.0,
                'carga_motor': producto.safra_carga_maxima if producto else 0.0,
                # Reunión 09-nov (fila 68): con motor elegido la carga es solo
                # la de su maestro.
                'motor_elegido': bool(producto),
                'motor_nombre': producto.name if producto else ''}

    def _motores_sistema(self, system=None):
        """Reunión 09-nov (fila 68): productos de los motores que el portal
        ofrece en el sistema (líneas activas de la referencia del campo
        Motor), para probar si la persiana se puede fabricar motorizada."""
        system = system or self.system_id
        Product = self.env['product.template'].sudo()
        field = self.env['safra.field'].sudo().search([('code', '=', 'motor')], limit=1)
        if not system or not field.ref_category_id:
            return Product
        lineas = self.env['safra.fabric.color'].sudo().search([
            ('fabric_id.category_id', '=', field.ref_category_id.id), ('fabric_id.active', '=', True),
            ('product_tmpl_id', '!=', False)])
        lineas = lineas.filtered(
            lambda c: (not c.fabric_id.system_ids or system in c.fabric_id.system_ids)
            and (not c.system_ids or system in c.system_ids))
        return lineas.mapped('product_tmpl_id')

    @api.model
    def _producto_motor(self, valor):
        """Producto del maestro del motor elegido (línea de la referencia de
        motores); vacío si no hay motor o no tiene producto."""
        Product = self.env['product.template'].sudo()
        if not valor or str(valor) in ('0', 'sin'):
            return Product
        field = self.env['safra.field'].sudo().search([('code', '=', 'motor')], limit=1)
        return self._lineas_opcion(field, valor).mapped('product_tmpl_id')[:1] if field else Product

    @api.model
    def _peso_perfil(self, valor):
        """Peso lineal del perfil elegido (g/m): el de la opción del catálogo
        o, con el perfil de Referencias (Fase 5.1), el U_Peso del artículo
        de la línea. Sprint 1.7: el servidor valida con el mismo peso que
        muestra el portal."""
        if not valor:
            return 0.0
        opt = self.env['safra.field.option'].sudo().search([
            ('field_id.code', 'in', ['perfil', 'perfileria2', 'perfil_sheer']),
            ('value', '=', str(valor)), ('peso_gm', '>', 0)], limit=1)
        if opt:
            return opt.peso_gm
        color = self.env['safra.fabric.color'].sudo().search([('code', '=', str(valor))], limit=1)
        return color.product_tmpl_id.safra_u_peso if color.product_tmpl_id else 0.0

    # Revisión 30-oct: reglas de Validaciones del corte de la tela; el
    # portal las muestra junto a la tela mientras se digita.
    REGLAS_CORTE = ('V_ANCHO_ROLLO', 'V_SIN_ANCHO_ROLLO', 'V_ANADIDO', 'V_ANADIDO_MAXIMO',
                    'V_CORTE_ATRAVESADO', 'V_CORTE_PANOS')
    # Reunión 30-oct (fila 143): estas se resuelven marcando la aceptación del
    # corte; no bloquean el resto del formulario (sí guardar la línea).
    ACEPTACION_CORTE = ('V_CORTE_ATRAVESADO', 'V_CORTE_PANOS')
    # Acta del 30-oct (Tubo, punto 8): la disponibilidad del tubo se avisa en
    # la ficha técnica con el mensaje de su regla de Validaciones.
    REGLAS_FICHA = ('V_TUBO_SIN_INSUMO',
                    # Revisión 10-nov (fila 68): el alto y el peso contra los
                    # máximos y «debe ir motorizada».
                    'V_ALTO_MAXIMO', 'V_REQUIERE_MOTOR', 'V_PESO_MAXIMO', 'V_PESO_SIN_CARGA')

    def _constante_tubo(self, tubo, aumento):
        """Constante del tubo para el corte de persianas: la de Ajustes
        (Excel de Safra: R8 0,17 · R16 0,20 · R24 0,20) o, si el tubo no
        está, el «Aumento tela del tubo» de la tabla de estructura."""
        texto = self.env['ir.config_parameter'].sudo().get_param(
            'safra.corte.constante_tubo', 'R8:0.17, R16:0.20, R24:0.20')
        for par in (texto or '').split(','):
            nombre, _sep, valor = par.partition(':')
            if nombre.strip().lower() == (tubo or '').strip().lower():
                try:
                    return float(valor.replace(',', '.'))
                except ValueError:
                    break
        return aumento or 0.0

    def _corte_tela(self):
        """Tipo de corte de la tela según los archivos de Safra del 26-oct.

        Persianas (sistemas con Cálculo del corte de la tela = Persiana;
        hoy Enrollable, Premium, Romanas, 2 en 1, Sheer 2 en 1): corte
        normal si el ancho cabe en el rollo; si no, atravesado si la tela es
        atravesable y alto + constante del tubo cabe en el rollo; si no,
        añadido si la tela lo permite y los añadidos (piezas del rollo para
        alto + constante, menos una) no pasan del máximo de la referencia
        (1 si está en 0: alto ≤ 2 × rollo − constante); si no, no se puede
        fabricar.

        Cortinas (Cálculo = Cortina; hoy Onda Moderna y Pliegue Francés):
        corte normal si alto + dobladillo superior + inferior máximo − riel
        cabe en el rollo; si no, bajo falso si el alto ≤ rollo + 12 cm; si
        no, paños si la tela los permite (Añadido, o atravesable: en cortinas
        atravesar es cortar por paños) y el rollo más largo alcanza para
        todos (paños = ancho × factor ÷ rollo, hacia arriba); si no, no se
        puede fabricar. Reunión 30-oct (fila 143, punto 5): la tela
        atravesable sigue el mismo orden (antes no tenía bajo falso).

        Revisión 30-oct: si el color no tiene U_Ancho (0), «sin_ancho_rollo».

        Devuelve {tipo, motivo, anadidos, maximo_anadidos, constante,
        panos, ancho_tela}; tipo vacío si no aplica o faltan datos."""
        self.ensure_one()
        out = {'tipo': '', 'motivo': '', 'anadidos': 0, 'maximo_anadidos': 0,
               'constante': 0.0, 'panos': 0, 'ancho_tela': 0.0}
        tela, rollo = self.fabric_id, self._ancho_rollo()
        w, h = self.width or 0.0, self.height or 0.0
        if not tela or not self.color_id or not w or not self.system_id:
            return out
        # Revisión 30-oct: el sistema dice qué cálculo usa (Cálculo del corte
        # de la tela, en su producto terminado).
        persiana = self.system_id.calculo_corte == 'persiana'
        cortina = self.system_id.calculo_corte == 'cortina'
        if (persiana or cortina) and not rollo:
            out.update(tipo='sin_ancho_rollo', motivo=(
                ('el color %s no tiene digitado el ancho del rollo (U_Ancho) en el maestro de productos'
                 if vacio(rollo) else
                 'el color %s tiene el ancho del rollo (U_Ancho) en 0 en el maestro de productos')
                % self.color_id.name))
        elif persiana:
            _tabla, regla, _lim = self._estructura_linea()
            c = self._constante_tubo(regla.tubo if regla else '', regla._constantes()['aumento'] if regla else 0.0)
            out['constante'] = c
            if w <= rollo:
                out['tipo'] = 'normal'
            elif tela.pierceable_type not in ('si', 'si_cliente'):
                out.update(tipo='no_fabricable', motivo=(
                    'el ancho (%s m) supera el ancho del rollo (%s m) y la tela no es '
                    'atravesable' % (w, rollo)))
            elif h + c <= rollo:
                out['tipo'] = 'atravesado'
            elif not tela.is_anadido:
                out.update(tipo='no_fabricable', motivo=(
                    'para atravesarla, el alto (%s m) más %s m del tubo supera el ancho del '
                    'rollo (%s m) y la tela no permite añadido' % (h, c, rollo)))
            else:
                anadidos = math.ceil(round((h + c) / rollo, 6)) - 1
                maximo = tela.max_anadidos or 1
                out.update(anadidos=anadidos, maximo_anadidos=maximo,
                           tipo='anadido' if anadidos <= maximo else 'anadido_excede')
                if anadidos > maximo:
                    out['motivo'] = ('el alto (%s m) necesita %s añadidos y la tela permite '
                                     'máximo %s' % (h, anadidos, maximo))
        elif cortina:
            # Revisión 30-oct: corte normal y bajo falso con las fórmulas de
            # Ajustes › Corte de la tela. El alto máximo es el del dobladillo
            # que más alto permite entre las opciones del sistema (Consumo del
            # dobladillo); sin consumos, con el dobladillo inferior máximo.
            ctx = self._ctx_corte_cortina()
            permite_panos = ctx['tela_permite_panos']
            if self._formula_corte('safra.formula.cortina_normal', ctx):
                out['tipo'] = 'normal'
            elif self._formula_corte('safra.formula.cortina_bajo_falso', ctx):
                out['tipo'] = 'bajo_falso'
            elif not permite_panos:
                out.update(tipo='no_fabricable', motivo=(
                    'el alto (%s m) supera el ancho del rollo (%s m) más el bajo falso y la tela '
                    'no permite paños' % (h, rollo)))
            else:
                ancho_tela = w * (self.system_id.factor_confeccion or 1.0)
                panos = math.ceil(round(ancho_tela / rollo, 6))
                out.update(panos=panos, ancho_tela=round(ancho_tela, 3), tipo='panos')
                rollos = self.color_id._rollos_disponibles() if self.color_id else None
                if rollos is not None:
                    largo = max(rollos.values() or [0.0])
                    if largo < panos * h:
                        out.update(tipo='no_fabricable', motivo=(
                            'el corte por %s paños necesita %s m de un mismo rollo y el más '
                            'largo disponible tiene %s m' % (panos, round(panos * h, 2), round(largo, 2))))
        return out

    def _consumos_cortina(self):
        """Consumos del dobladillo de las opciones del sistema; sin consumos,
        el dobladillo inferior máximo de Ajustes."""
        self.ensure_one()
        consumos = [c for por_valor in self._consumos_dobladillo().values()
                    for c in por_valor.values()]
        return consumos or [self._parametro('safra.cortina.dobladillo_inferior_max', 0.21)]

    def _ctx_corte_cortina(self):
        """Variables de «Cortina con corte normal si…» y «Cortina con bajo
        falso si…»: el alto máximo es el del dobladillo que más alto permite."""
        self.ensure_one()
        tela = self.fabric_id
        return self._variables_corte_cortina(
            alto_maximo_dobladillo=max(self._alto_maximo_dobladillo(c) for c in self._consumos_cortina()),
            tela_con_diseno=tela.pierceable_type != 'no',
            tela_permite_panos=bool(tela.is_anadido) or tela.pierceable_type in ('si', 'si_cliente'))

    def _consumos_dobladillo(self, maps=None):
        """Revisión 30-oct: {código del campo: {valor: consumo}} de las
        opciones del sistema con «Consumo del dobladillo» (las del sistema o,
        si no tiene, las del catálogo)."""
        self.ensure_one()
        if maps is None:
            maps = self.env['safra.system.field'].sudo().search([
                ('system_id', '=', self.system_id.id), ('field_id.active', '=', True)]) \
                if self.system_id else self.env['safra.system.field']
        out = {}
        for m in maps:
            for opt in (m.option_ids or m.field_id.option_ids):
                if opt.consumo_dobladillo > 0:
                    out.setdefault(m.field_id.code, {})[opt.value] = opt.consumo_dobladillo
        return out

    def _variables_corte_cortina(self, **extra):
        """Variables de las fórmulas del corte de las cortinas (Ajustes ›
        Corte de la tela), más los campos del cotizador por su código."""
        p = self._parametro
        base = dict({
            'alto': self.height or 0.0, 'ancho': self.width or 0.0, 'ancho_rollo': self._ancho_rollo(),
            'riel': p('safra.cortina.riel', 0.035),
            'dobladillo_superior': p('safra.cortina.dobladillo_superior', 0.06),
            'dobladillo_inferior_max': p('safra.cortina.dobladillo_inferior_max', 0.21),
            'tolerancia_bajo_falso': p('safra.cortina.tolerancia_bajo_falso', 0.12),
            'consumo': 0.0, 'alto_maximo_dobladillo': 0.0,
            'tela_con_diseno': False, 'tela_permite_panos': False,
        }, **extra)
        return dict(base, **variables_formulario(self._campos_formula(), base))

    def _formula_corte(self, clave, ctx):
        """Resultado de una fórmula del corte de Ajustes (vacía = la del
        módulo). Una fórmula con error da False y queda en el log."""
        codigo = self.env['safra.structure.rule']._codigo_formula(
            self.env, clave, R17.FORMULAS_CORTE_CORTINA)
        try:
            return evaluar_formula(codigo, ctx)[0]
        except Exception as e:  # noqa: BLE001 — una fórmula mal escrita no rompe el portal
            _logger.warning('Fórmula %s con error: %s', clave, e)
            return False

    def _alto_maximo_dobladillo(self, consumo):
        """Alto máximo de la cortina con un dobladillo, con la fórmula de
        Ajustes › Corte de la tela (0 sin rollo o sin consumo)."""
        if not self._ancho_rollo() or not consumo:
            return 0.0
        valor = self._formula_corte('safra.formula.alto_maximo_dobladillo',
                                    self._variables_corte_cortina(consumo=consumo))
        try:
            return round(float(valor or 0.0), 3)
        except (TypeError, ValueError):
            return 0.0

    def _motor_ancho_min(self):
        """Matriz 1.7 ([44]): ancho mínimo de una persiana motorizada = el
        U_AnchoMin del producto del motor elegido. Revisión 28-oct: sin dato
        vale 0; el valor por defecto lo pone la condición de
        V_ANCHO_MIN_MOTOR en Validaciones (minimo = motor_ancho_min or 0.70)."""
        self.ensure_one()
        minimo = 0.0
        if self.motor:
            campo = self.env['safra.field'].sudo().search([('code', '=', 'motor')], limit=1)
            ref = self._lineas_opcion(campo, self.motor)[:1]
            minimo = ref.product_tmpl_id.safra_u_ancho_min if ref.product_tmpl_id else 0.0
        # Sin digitar llega vacío (False): en una cuenta vale 0.
        return minimo

    def _cenefa_en_tela(self, maps=None):
        """Tipo de Cenefa elegido es una cenefa en tela: la misma regla que
        muestra «Tipo de corte Cenefa Tela» (su dependencia en el Catálogo
        de campos)."""
        self.ensure_one()
        Field = self.env['safra.field'].sudo()
        corte = Field.search([('code', '=', 'corte_cenefa')], limit=1)
        padre = corte.depends_field_id or Field.search([('code', '=', 'cenefa_panel')], limit=1)
        actual = self._valor_formulario(padre.code) if padre else ''
        if not actual:
            return False
        dep = corte.depends_value or Field._S14_TELA
        if padre.field_type == 'ref_categoria' and not actual.startswith('ref-'):
            lineas = self._lineas_opcion(padre, actual)
            if len(lineas) > 1:
                return any(self._depende_ok(actual, dep, eti=l._portal_label(),
                                            ref=l.fabric_id.code or '') for l in lineas)
        if maps is None:
            maps = self.env['safra.system.field'].sudo().search([('system_id', '=', self.system_id.id)])
        eti, ref = self._etiqueta_y_ref(padre, actual, maps)
        return self._depende_ok(actual, dep, eti=eti, ref=ref)

    def _corte_cenefa_tela(self, maps=None):
        """Reunión 28-oct (filas 88 y 91): la cenefa en tela no tiene producto
        en el maestro; se hace con la tela de la persiana y sigue las reglas
        del atravesable (fila 46). El ancho de la cenefa (ancho + medida por
        lateral) se compara con el rollo: si cabe va entera; si no, con tela
        atravesable (Sí o Sí/Cliente) se puede cortar atravesada (entera, con
        costo adicional) o ir añadida; si no, va añadida.

        Devuelve {en_tela, tipo ('' | 'entera' | 'atravesada' | 'anadida'),
        ancho_cenefa}; tipo vacío si no es cenefa en tela o faltan datos."""
        self.ensure_one()
        out = {'en_tela': False, 'tipo': '', 'ancho_cenefa': 0.0}
        if not self.system_id or not self._cenefa_en_tela(maps):
            return out
        out['en_tela'] = True
        try:
            lateral = float(self.env['ir.config_parameter'].sudo().get_param('safra.cenefa.lateral') or 0.11)
        except ValueError:
            lateral = 0.11
        # El portal manda los campos en atributos al consultar las fórmulas
        # (la columna trae «sin» por defecto).
        lado = (self.attribute_values or {}).get('cenefa_lateral') or self.cenefa_lateral
        laterales = 2 if lado == 'ambos' else 1 if lado in ('izquierdo', 'derecho') else 0
        ancho = round((self.width or 0.0) + lateral * laterales, 3)
        out['ancho_cenefa'] = ancho
        tela, rollo = self.fabric_id, self._ancho_rollo()
        if not tela or not rollo or not self.width:
            return out
        if ancho <= rollo:
            out['tipo'] = 'entera'
        elif tela.pierceable_type in ('si', 'si_cliente'):
            out['tipo'] = 'atravesada'
        else:
            out['tipo'] = 'anadida'
        return out

    def _motor_con_controles_de_referencia(self):
        """Producto del motor elegido cuando hay referencia de controles
        (los controles salen de ella, como en el portal); vacío si no la
        hay o el motor no es una línea de referencia."""
        Color = self.env['safra.fabric.color']
        product = Color._linea_desde_valor(self.motor).product_tmpl_id
        if product and Color._lineas_control(product, self.system_id) is not None:
            return product
        return self.env['product.template']

    def _con_motor(self):
        """Motorizada: la casilla Motorizado o un motor elegido (los sistemas
        con motor por referencia no marcan la casilla)."""
        return bool(self.has_motor) or bool(self.motor and self.motor not in ('0', 'sin'))

    # Sprint 1.7: variables propias de las condiciones; un campo del
    # cotizador con el mismo código no las reemplaza.
    def _contexto_reglas(self, numero=0, lineas=None, pedido=None, solo_propias=False):
        """Variables de la «Condición (código)» de las validaciones (la
        ayuda del formulario de Validaciones las explica una a una). Con
        `solo_propias`, sin los campos del cotizador."""
        self.ensure_one()
        system = self.system_id
        sys_code = system.code or ''
        attrs = self.attribute_values or {}
        w, h = self.width or 0.0, self.height or 0.0

        def _int(v):
            try:
                return int(v or 0)
            except (TypeError, ValueError):
                return 0

        lamas = _int(attrs.get('quantity_lamas'))
        con_motor = self._con_motor()
        ap_raw = str(attrs.get('apertura') or '')
        maximo = self.env['safra.lamas.rule'].sudo().compute_max(
            system, w,
            {'1': 'derecha', '2': 'izquierda', '3': 'extremos',
             '4': 'centro'}.get(ap_raw, ap_raw),
            motorized=con_motor, campos=self._campos_formula()) if system else None
        telas = []
        slots = [(self.fabric_id.id, self.color_id.id), (self.fabric_id_2.id, self.color_id_2.id),
                 (self.fabric_id_3.id, self.color_id_3.id)]
        slots += [(_int(attrs.get('fabric_id_%d' % n)), attrs.get('color_id_%d' % n))
                  for n in (4, 5)]
        for fid, cid in slots:
            if fid and cid:
                telas.append((fid, str(cid)))
        _tabla, regla, limites_est = self._estructura_linea() if system else (False, None, {})
        Kit = self.env['safra.motor.kit'].sudo()
        kit = motor_kits = Kit
        motor_ref = self.env['safra.fabric.color']
        if con_motor and self.motor:
            kit = regla._kit_for(self.motor) if regla else Kit
            motor_kits = Kit.search(['|', ('motor_value', '=', self.motor),
                                     ('motor_ref_codes', 'ilike', self.motor)]).filtered(
                lambda k: k.motor_value == self.motor or self.motor in [
                    c.strip() for c in (k.motor_ref_codes or '').split(',')])
            campo_motor = self.env['safra.field'].sudo().search([('code', '=', 'motor')], limit=1)
            motor_ref = self._lineas_opcion(campo_motor, self.motor)[:1]
        try:
            traslape = float(str(attrs.get('tamano_traslape') or 0).replace(',', '.'))
        except ValueError:
            traslape = 0.0
        ancho_telo = 0.0
        if lamas and w and system:
            combo = self.env['safra.panel.combo.rule'].sudo()._regla(system)
            try:
                ancho_telo = (combo._ancho_telo(w, traslape, lamas, self._campos_formula())
                              if combo else (w + (lamas - 1) * traslape) / lamas) or 0.0
            except Exception:  # noqa: BLE001 — fórmula del funcional con error
                ancho_telo = 0.0
        estructura = {
            'tubo': regla.tubo if regla else '',
            'mecanismo': (regla.mecanismo or '') if regla else '',
            'cabezal': self._cabezal_elegido()[1] if system else '',
            # Sin digitar (ni en el producto del tubo ni en la fila) llega vacío.
            'aumento_tela': regla._constantes()['aumento'] if regla else 0.0,
            # Revisión 10-nov: vacío si no se pudo calcular (sin tabla, sin
            # peso ni grosor de la tela…); vacio(estructura['alto_maximo']).
            'alto_maximo': (limites_est['alto_maximo'] if limites_est.get('alto_maximo') is not None
                            else False),
            # El sistema tiene tabla de Estructura por Ancho y si se encontró
            # una fila para este ancho (tubo, mecanismo…).
            'tabla': bool(_tabla),
            'encontrada': bool(regla),
            'peso': limites_est.get('peso_total') or 0.0,
            # Revisión 10-nov: la carga sin digitar llega vacía (vacio() es
            # True), no 0; un 0 digitado es 0.
            'carga': (False if limites_est.get('carga_sin_dato') or (
                'carga_maxima' in limites_est and limites_est['carga_maxima'] is None)
                else (limites_est.get('carga_maxima') or 0.0)) if regla else 0.0,
            # True si la carga es la del motor elegido (su maestro).
            'motor_elegido': bool(regla) and bool(self._params_estructura().get('motor_elegido')),
            # De dónde sale la carga y cómo está cada dato (sin digitar,
            # digitado en 0 o su valor), para el mensaje.
            'carga_detalle': limites_est.get('carga_detalle') or '',
            # Fila 68 (punto 3): tubo con el que sí se fabrica motorizada
            # cuando manual no se puede ('' si no aplica).
            'tubo_motor': '',
        }
        if system and regla is not None:
            alternativa = self._alternativa_motor(_tabla, regla, limites_est)
            if alternativa:
                estructura['tubo_motor'] = self.env['safra.structure.rule'].nombre_tubo(
                    alternativa['tubo'])
        # Acta del 30-oct (Tubo, punto 8): los insumos del tubo sin
        # existencias, para que la regla V_TUBO_SIN_INSUMO tenga su condición
        # y su mensaje en Validaciones. Texto ('' si no falta ninguno).
        insumos_sin_stock = ', '.join(
            self.env['safra.structure.rule'].sudo()._insumos_sin_stock(estructura['tubo'])
            .mapped('display_name')) if estructura['tubo'] else ''
        pedido = pedido or {}
        lineas = lineas or []
        Fabric = self.env['safra.fabric'].sudo()
        Color = self.env['safra.fabric.color'].sudo()
        corte = self._corte_tela()
        cenefa = self._corte_cenefa_tela()
        ctx = {
            'numero': numero,
            # Revisión 28-oct: las persianas de su secuencia (Mismo cabezal y
            # mismo nombre), en orden; lo llena _preparar_reglas.
            'secuencia_lineas': [],
            # Revisión cálculo de tubo (27-oct, error 3): el tramo de soportes
            # dependientes de la persiana; lo llena _preparar_reglas.
            'tramo': {},
            'ancho': w, 'alto': h, 'cantidad': self.quantity or 0,
            'sistema': sys_code, 'sistema_nombre': system.name or '',
            'limites': dict(system._tech_limits(exhibition=bool(self.exhibition)), **dict.fromkeys(
                system._limites_sin_digitar(exhibition=bool(self.exhibition)), False)) if system else
                       {'wmin': 0, 'wmax': 0, 'hmin': 0, 'hmax': 0},
            # Revisión 28-oct: todos los campos de la persiana (también los
            # de columna, como same_header), por su código.
            'atributos': self._campos_formula(),
            'campos': set(self._system_field_codes()) if system else set(),
            'tela': self.fabric_id, 'color': self.color_id,
            'tela_2': self.fabric_id_2, 'color_2': self.color_id_2,
            'tela_3': self.fabric_id_3, 'color_3': self.color_id_3,
            'tela_4': Fabric.browse(_int(attrs.get('fabric_id_4'))).exists(),
            'color_4': Color.browse(_int(attrs.get('color_id_4'))).exists(),
            'tela_5': Fabric.browse(_int(attrs.get('fabric_id_5'))).exists(),
            'color_5': Color.browse(_int(attrs.get('color_id_5'))).exists(),
            'telas': telas,
            'linea': self,
            'con_motor': con_motor,
            'kit': kit,
            'motor_kits': motor_kits,
            'motor_ref': motor_ref,
            'motor_ancho_min': self._motor_ancho_min(),
            'traslape': traslape,
            'ancho_telo': round(ancho_telo, 4),
            'alineado': bool(self.aligned),
            'exhibicion': bool(self.exhibition),
            'localizacion': self.location or '',
            'ancho_rollo': self._ancho_rollo(),
            # Revisión 27-oct: valor que permite la impresora (Ajustes ›
            # Cotizador Safra › Estampación).
            'ancho_max_impresion': self.env['res.config.settings']._ancho_max_impresion(),
            # Archivos de Safra «Tipos de corte tela» (26-oct).
            'tipo_corte': corte['tipo'],
            'motivo_corte': corte['motivo'],
            'anadidos': corte['anadidos'],
            'maximo_anadidos': corte['maximo_anadidos'],
            'constante_tubo': corte['constante'],
            'panos': corte['panos'],
            'ancho_tela': corte['ancho_tela'],
            # Reunión 28-oct (filas 88 y 91): corte de la cenefa en tela.
            'cenefa_en_tela': cenefa['en_tela'],
            'tipo_corte_cenefa': cenefa['tipo'],
            'ancho_cenefa': cenefa['ancho_cenefa'],
            'maximo_lamas': maximo,
            'total_lamas': lamas,
            'suma_lamas': sum(_int(attrs.get('lamas_tela_%d' % n)) for n in range(1, 6)),
            'estructura': estructura,
            'insumos_sin_stock': insumos_sin_stock,
            # Revisión 10-nov: datos del maestro sin digitar que usan las
            # fórmulas y validaciones de la persiana: [{'dato', 'usos'}]
            # (lo completa _aplicar_reglas con las validaciones).
            'datos_sin_digitar': [],
            'lineas': lineas,
            'otras_lineas': [l for l in lineas if l['numero'] != numero],
            'pedido': {
                'express': bool(pedido.get('safra_express')),
                'exportacion': bool(pedido.get('es_exportacion')),
                'verificacion': bool(pedido.get('requiere_verificacion')),
                'unidades': sum(l['cantidad'] or 1 for l in lineas),
                'lineas': len(lineas),
                # Datos de despacho (filas 184-188). pide_despacho: el
                # formulario los trae (las cotizaciones de antes, no).
                'pide_despacho': bool(pedido.get('pide_despacho')),
                'recoge_fabrica': bool(pedido.get('recoge_fabrica')),
                'pais': self.env['res.country'].sudo().browse(
                    _int(pedido.get('despacho_country_id'))).exists().name or '',
                'ciudad': self.env['res.city'].sudo().browse(
                    _int(pedido.get('despacho_city_id'))).exists().name or '',
                'direccion': pedido.get('despacho_direccion') or '',
                'destinatario': pedido.get('despacho_destinatario') or '',
                'fecha_despacho': pedido.get('despacho_fecha') or False,
            },
            'hallazgo': False,
        }
        # Datos del maestro sin digitar (no es una variable de las fórmulas;
        # _aplicar_reglas avisa en cada validación que los usa).
        ctx['_sin_digitar'] = self._sin_digitar(
            regla=regla, con_motor=con_motor, motor_ref=motor_ref,
            apertura={'1': 'derecha', '2': 'izquierda', '3': 'extremos',
                      '4': 'centro'}.get(ap_raw, ap_raw))
        if not solo_propias:
            ctx.update(self._variables_campos(ctx))
        return ctx

    def _variables_campos(self, base):
        """Cada campo del cotizador por su código técnico: casillas
        True/False, números como número y lo demás como el texto del valor
        (el «Valor» de la opción en el Catálogo de Campos)."""
        out = {}
        Field = self.env['safra.field'].sudo().with_context(active_test=False)
        for field in Field.search([]):
            code = field.code or ''
            if not re.match(r'^[a-z_][a-z0-9_]*$', code) or code in base:
                continue
            valor = self._valor_formulario(code)
            if field.field_type == 'boolean':
                out[code] = valor not in ('', '0', 'False', 'false')
            elif field.field_type in ('float', 'integer'):
                try:
                    out[code] = float(str(valor).replace(',', '.') or 0)
                except ValueError:
                    out[code] = 0.0
            else:
                out[code] = valor
        return out

    def _resumen_regla(self, numero):
        """Una línea del pedido tal como la ven las condiciones en
        `lineas` / `otras_lineas`."""
        self.ensure_one()
        return {
            'numero': numero,
            'sistema': self.system_id.code or '',
            'ancho': self.width or 0.0, 'alto': self.height or 0.0,
            'cantidad': self.quantity or 0,
            'tela': self.fabric_id, 'color': self.color_id,
            'localizacion': self.location or '',
            'alineado': bool(self.aligned),
            'secuencia': self.sequence_name or '',
            'con_motor': self._con_motor(),
            'atributos': self._campos_formula(),
            'linea': self,
        }

    @api.model
    def _contexto_ejemplo(self):
        """Contexto de una línea vacía: con él se revisa al guardar que la
        condición solo use variables que existen."""
        return self.new({})._contexto_reglas(1, [], {})

    @api.model
    def _aplicar_reglas(self, hallazgos, contextos, momento, campo=None,
                        solo_regla=None, diagnostico=None):
        """Sprint 1.7: aplica la configuración de Validaciones a los
        hallazgos del cálculo interno y evalúa las condiciones.

        - `hallazgos`: [{line, code, severity, message, fmt}] en orden.
        - `contextos`: {n: variables de la línea n} (0 = el pedido).
        - `momento`: 'campo' / 'linea' / 'pedido'; con 'campo', `campo` es
          el código del campo que cambió.

        Regla sin condición: cada hallazgo de su código sale con la
        severidad y el mensaje de la regla. Regla con condición: la
        condición manda; se evalúa en cada línea con `hallazgo` = lo que
        encontró el cálculo interno (o False). Un hallazgo sin regla
        configurada sale tal cual. Con `solo_regla` se evalúa solo esa regla
        (aunque esté inactiva) y `diagnostico` recibe el detalle por línea."""
        Config = self.env['safra.validation.rule'].sudo().with_context(active_test=False)
        reglas = solo_regla or Config.search([])
        # Revisión 28-oct: el programa conoce cada regla por su clave interna
        # (no cambia); «codigo» es el Código visible, que Safra puede cambiar.
        por_codigo = {r._clave_programa(): r for r in reglas}
        issues = []
        vistos = set()

        def emitir(n, regla, message):
            clave = (n, regla._clave_programa(), message)
            if clave in vistos:
                return
            vistos.add(clave)
            issues.append({'line': n, 'code': regla._clave_programa(), 'codigo': regla.code,
                           'severity': regla.severity, 'message': message})

        # {(línea, dato sin digitar): validaciones que lo usan}.
        usan_vacio = {}
        propios = {}
        for h in hallazgos:
            regla = por_codigo.get(h['code'])
            if regla is None:
                if not solo_regla and momento not in ('campo', 'secuencia'):
                    clave = (h['line'], h['code'], h['message'])
                    if clave not in vistos:
                        vistos.add(clave)
                        issues.append({'line': h['line'], 'code': h['code'],
                                       'severity': h['severity'], 'message': h['message']})
                continue
            propios.setdefault((regla._clave_programa(), h['line']), []).append(h)

        # Revisión 10-nov: `datos_sin_digitar` = datos del maestro vacíos que
        # usan las fórmulas y las validaciones de la persiana. Las reglas que
        # lo usan (V_DATO_SIN_DIGITAR) se revisan al final, cuando ya se sabe
        # qué validaciones leyeron un dato vacío.
        def datos_sin_digitar(n, ctx):
            formulas = (ctx.get('_sin_digitar') or {}).get('formulas') or {}
            datos = set(formulas) | {d for (m, d) in usan_vacio if m == n}
            return [{'dato': d, 'usos': ', '.join(
                ['la validación «%s»' % nombre for nombre in usan_vacio.get((n, d), [])]
                + list(formulas.get(d) or []))} for d in sorted(datos)]

        for n, ctx in contextos.items():
            ctx['datos_sin_digitar'] = datos_sin_digitar(n, ctx)
        usa_datos = lambda r: 'datos_sin_digitar' in (r.condition_code or '')
        al_final = False
        for regla in sorted(reglas, key=usa_datos):
            if usa_datos(regla) and not al_final:
                al_final = True
                for n, ctx in contextos.items():
                    ctx['datos_sin_digitar'] = datos_sin_digitar(n, ctx)
            if not regla.active and not solo_regla:
                continue
            for n, ctx in contextos.items():
                encontrados = propios.get((regla._clave_programa(), n), [])
                # El contexto del pedido (0) solo sirve a lo que el cálculo
                # interno encontró a nivel de pedido (p. ej. Safra Express).
                if n == 0 and not encontrados:
                    continue
                fila = {'line': n, 'mensajes': [], 'severity': regla.severity}
                motivo = regla.aplica_en(momento, campo, ctx.get('sistema') if n else None)
                if motivo:
                    fila['motivo'] = motivo
                elif regla.condition_code:
                    datos = datos_vacios(regla.condition_code, ctx)
                    for dato in datos:
                        usan_vacio.setdefault((n, dato), []).append(regla.name or regla.code)
                    if datos:
                        fila['sin_digitar'] = datos
                    for h in encontrados or [None]:
                        local = dict(ctx)
                        if h:
                            local['hallazgo'] = dict(h.get('fmt') or {}, mensaje=h['message'])
                        try:
                            dispara, variables = regla._evaluar(local)
                        except Exception as e:  # noqa: BLE001 — una regla mal escrita no rompe el portal
                            _logger.warning('Validación %s: error evaluando la condición',
                                            regla.code, exc_info=True)
                            fila['error'] = str(e.args[0] if e.args else e).split(' while evaluating')[0]
                            regla._registrar_error(fila['error'])
                            break
                        if dispara:
                            msg = regla._mensaje(variables, h)
                            fila['mensajes'].append(msg)
                            emitir(n, regla, msg)
                else:
                    for h in encontrados:
                        msg = regla._mensaje(dict(ctx), h)
                        fila['mensajes'].append(msg)
                        emitir(n, regla, msg)
                if diagnostico is not None:
                    diagnostico.append(fila)

        # Reglas del pedido (se revisan al finalizar): un mismo mensaje en
        # varias líneas, o en la única línea del pedido, es del pedido
        # completo y sale una sola vez (p. ej. los datos de despacho).
        repetidos = {}
        for issue in issues:
            regla = por_codigo.get(issue['code'])
            if regla and regla.momento in ('pedido', 'secuencia') and issue['line']:
                repetidos.setdefault((issue['code'], issue['message']), []).append(issue)
        quitar = set()
        for grupo in repetidos.values():
            if len(grupo) > 1 or len([n for n in contextos if n]) == 1:
                grupo[0]['line'] = 0
                quitar.update(id(i) for i in grupo[1:])
        return [i for i in issues if id(i) not in quitar]

    @api.model
    def _probar_regla(self, regla, lines_vals, pedido=None, momento='pedido'):
        """«Probar» del formulario de Validaciones: resultado de una regla
        en cada línea de una cotización, sin guardar nada."""
        diagnostico = []
        lines, hallazgos, contextos = self._preparar_reglas(
            lines_vals, cross=momento in ('pedido', 'secuencia'), pedido=pedido)
        self._aplicar_reglas(hallazgos, contextos, momento, solo_regla=regla,
                             diagnostico=diagnostico)
        for fila in diagnostico:
            line = lines[fila['line'] - 1] if fila['line'] else None
            if line:
                fila['descripcion'] = '%s · %s × %s m%s' % (
                    line.system_id.name or '', line.width or 0, line.height or 0,
                    ' · %s' % line.fabric_id.name if line.fabric_id else '')
        return diagnostico

    @api.model
    def _preparar_reglas(self, lines_vals, cross=True, pedido=None):
        """(líneas, hallazgos, contextos) del pedido para _aplicar_reglas."""
        pedido = pedido or {}
        if cross:
            self._unificar_secuencias(lines_vals)
        lines = [self.new({k: v for k, v in vals.items() if k in self._fields})
                 for vals in lines_vals]
        hallazgos = []
        for n, line in enumerate(lines, start=1):
            for h in line._validations():
                h['line'] = n
                hallazgos.append(h)
        if cross:
            # Reglas cruzadas: secuencias (mismo cabezal), alineado, canal
            # compartido y segmentos de los planos.
            hallazgos.extend(self._validate_sequences(lines_vals))
            hallazgos.extend(self._validate_aligned(lines_vals))
            hallazgos.extend(self._validate_canal_compartido(lines_vals))
            hallazgos.extend(self._validate_controles(lines_vals))
            hallazgos.extend(self._validate_planos(lines_vals))
            hallazgos.extend(self._asignar_rollos(lines_vals)[0])
            hallazgos.extend(self._validate_express(lines_vals, pedido))
        resumen = [line._resumen_regla(n) for n, line in enumerate(lines, start=1)]
        contextos = {n: line._contexto_reglas(n, resumen, pedido)
                     for n, line in enumerate(lines, start=1)}
        contextos[0] = self.new({})._contexto_reglas(0, resumen, pedido)
        if cross:
            for numeros in self._grupos_secuencia(lines_vals).values():
                for n in numeros:
                    contextos[n]['secuencia_lineas'] = [resumen[i - 1] for i in numeros]
            for n, tramo in self._tramos_dependientes(lines_vals).items():
                contextos[n]['tramo'] = tramo
        return lines, hallazgos, contextos

    @api.model
    def _grupos_secuencia(self, lines_vals):
        """{nombre: [n, …]}: las persianas con «Mismo cabezal» de cada
        secuencia (mismo nombre, sin mayúsculas ni espacios), en orden."""
        grupos = {}
        for n, vals in enumerate(lines_vals, start=1):
            nombre = (vals.get('sequence_name') or '').strip().lower()
            if vals.get('same_header') and nombre:
                grupos.setdefault(nombre, []).append(n)
        return grupos

    @api.model
    def _validate_aligned(self, lines_vals):
        """Reglas del Alineado (revisión 17-sep, reunión 28-sep fila 13).
        Se evalúan todas y se devuelven todos los errores juntos —antes el
        primero tapaba a los demás y el cliente los descubría de a uno:

        - E20010: cada persiana alineada necesita otra alineada con la misma
          referencia y el mismo color.
        - E20026: cada persiana alineada necesita otra alineada en la misma
          localización (espacio); no se alinea una persiana sola.
        - Altura: las alineadas de la misma referencia deben tener la misma
          altura aunque difieran en color (así este error sale junto al de
          color). Con tela de franjas (familia Sheer) es bloqueante, sin
          franjas queda como advertencia."""
        Fabric = self.env['safra.fabric'].sudo()

        def make(n, code, default_msg, severity):
            return {'line': n, 'code': code, 'severity': severity, 'message': default_msg}

        def agrupar(lines, key_fn):
            grupos = {}
            for n, v in lines:
                grupos.setdefault(key_fn(v), []).append((n, v))
            return grupos

        issues = []
        alineadas = [(n, v) for n, v in enumerate(lines_vals, start=1)
                     if v.get('aligned')]

        for lines in agrupar(alineadas, lambda v: (v.get('fabric_id'), v.get('color_id'))).values():
            if len(lines) < 2:
                issue = make(lines[0][0], 'V_ALINEADO_MIN',
                             'E20010: El alineado requiere al menos dos líneas '
                             'con la misma referencia y color.', 'error')
                if issue:
                    issues.append(issue)

        for loc, lines in agrupar(alineadas, lambda v: (v.get('location') or '').strip().lower()).items():
            if len(lines) < 2:
                donde = lines[0][1].get('location')
                issue = make(lines[0][0], 'V_ALINEADO_LOCALIZACION',
                             'E20026: El alineado requiere al menos dos '
                             'persianas alineadas en la misma localización%s.'
                             % (' (%s)' % donde if donde else ''), 'error')
                if issue:
                    issues.append(issue)

        for fid, lines in agrupar(alineadas, lambda v: v.get('fabric_id')).items():
            alturas = {round(float(v.get('height') or 0), 3) for _, v in lines}
            if len(lines) < 2 or len(alturas) < 2:
                continue
            # La tela con franjas puede ir como principal o como tela
            # adicional (2 en 1, lamas): cualquiera escala a bloqueo.
            # Pendientes 24-sep (10.3): franjas == Familia Sheer.
            franjas = None
            for _, v in lines:
                for k in ('fabric_id', 'fabric_id_2', 'fabric_id_3',
                          'fabric_id_4', 'fabric_id_5'):
                    # Las telas 4 y 5 viajan en attribute_values.
                    raw = v.get(k) or (v.get('attribute_values') or {}).get(k)
                    try:
                        f = Fabric.browse(int(raw)) if raw else None
                    except (TypeError, ValueError):
                        f = None
                    if f and f.exists() and f.is_sheer:
                        franjas = f
                        break
                if franjas:
                    break
            if franjas:
                # Código propio con su propio registro configurable: la
                # severidad genérica de V_ALINEADO_ALTURA (advertencia) no
                # debe rebajar el bloqueo de las franjas.
                issue = make(lines[0][0], 'V_ALINEADO_FRANJAS',
                             'E20013: Las líneas alineadas con %s '
                             '(familia Sheer: franjas) deben tener '
                             'exactamente la misma altura.' % franjas.name,
                             'error')
            else:
                issue = make(lines[0][0], 'V_ALINEADO_ALTURA',
                             'Las líneas alineadas no tienen la misma '
                             'altura; revise antes de enviar el pedido.',
                             'warning')
            if issue:
                issues.append(issue)
        return issues

    @api.model
    def _validate_canal_compartido(self, lines_vals):
        """Pendientes 24-sep (16.2): una persiana motorizada puede ir SIN
        control propio y tomar un canal libre del control multicanal de
        otra persiana del pedido (mismo sistema). Reglas:
        - Solo se permite si otra línea del mismo sistema ya tiene control
          asignado.
        - El canal elegido debe existir en ese control (U_Cantidad de
          canales del maestro) y no estar tomado por otra línea."""

        def make(n, code, default_msg):
            return {'line': n, 'code': code, 'severity': 'error', 'message': default_msg}

        def _canales_de(control_val):
            # Reunión 13-oct: solo un control MULTICANAL presta canales.
            n = self._canales_control(control_val)
            return n if n > 1 else 0

        issues = []
        sin_control = ('', '0', 'sin', False, None)
        donors = {}      # system_id -> max canales entre los controles
        taken = {}       # system_id -> {canal: línea}
        for n, vals in enumerate(lines_vals, start=1):
            sysid = vals.get('system_id')
            ctrl = vals.get('control')
            canal = str(vals.get('control_channel') or '').strip()
            if ctrl not in sin_control:
                donors[sysid] = max(donors.get(sysid, 0), _canales_de(ctrl))
                if canal and canal != '0':
                    taken.setdefault(sysid, {}).setdefault(canal, n)
        for n, vals in enumerate(lines_vals, start=1):
            if not vals.get('has_motor') and not vals.get('motor'):
                continue
            ctrl = vals.get('control')
            canal = str(vals.get('control_channel') or '').strip()
            if ctrl not in sin_control or not canal or canal == '0':
                continue
            sysid = vals.get('system_id')
            if not donors.get(sysid):
                issue = make(n, 'V_CANAL_SIN_CONTROL',
                             'E20019: Para dejar la persiana sin control debe '
                             'existir otra persiana del mismo sistema en el '
                             'pedido con un control multicanal asignado.')
                if issue:
                    issues.append(issue)
                continue
            try:
                canal_n = int(canal)
            except ValueError:
                canal_n = 0
            if canal_n > donors[sysid]:
                issue = make(n, 'V_CANAL_FUERA_RANGO',
                             'E20020: El canal {canal} no existe en el control '
                             'compartido (tiene {max} canales).')
                if issue:
                    issue['message'] = issue['message'].format(
                        canal=canal, max=donors[sysid])
                    issues.append(issue)
            dueno = taken.get(sysid, {}).get(canal)
            if dueno and dueno != n:
                issue = make(n, 'V_CANAL_TOMADO',
                             'E20021: El canal {canal} ya está tomado por la '
                             'persiana {linea}.')
                if issue:
                    issue['message'] = issue['message'].format(
                        canal=canal, linea=dueno)
                    issues.append(issue)
            else:
                taken.setdefault(sysid, {}).setdefault(canal, n)
        return issues

    @api.model
    def _rf_sin_interruptor(self, value):
        """Reunión 13-oct: «Sin interruptor» es el valor 'sin' del catálogo
        o una línea de referencia sin producto."""
        value = str(value or '')
        if not value:
            return False
        if value == 'sin':
            return True
        line = self.env['safra.fabric.color']._linea_desde_valor(value)
        return bool(line) and not line.product_tmpl_id

    @api.model
    def _canales_control(self, value):
        """Canales del control elegido: los de su línea en Referencias (la
        línea manda) o, con controles del maestro, U_Cantidad de canales."""
        value = str(value or '')
        if not value or value in ('0', 'sin'):
            return 0
        line = self.env['safra.fabric.color']._linea_desde_valor(value)
        if line:
            return line._canales_portal()
        product = self.env['product.template'].sudo().search(
            ['|', ('safra_code', '=', value), ('default_code', '=', value)], limit=1)
        return product.safra_u_cantidad_canales or 0

    @api.model
    def _validate_controles(self, lines_vals):
        """Reunión 13-oct (filas 56-57):
        - Persiana con motor (y sin «Sin interruptor»): debe elegir control,
          aunque sea «Sin control» (E20030).
        - El pedido con persianas con motor debe llevar al menos un control
          real en alguna de ellas (E20031).
        - Con control multicanal o con «Sin control» el canal es obligatorio
          (E20032); con monocanal no se pide."""

        def make(n, code, default_msg):
            return {'line': n, 'code': code, 'severity': 'error', 'message': default_msg}

        issues, con_motor, con_control = [], [], False
        for n, vals in enumerate(lines_vals, start=1):
            if not vals.get('system_id'):
                continue
            line = self.new({'system_id': vals['system_id']})
            codes = line._system_field_codes()
            if 'control' not in codes:
                continue
            motor = str(vals.get('motor') or '')
            tiene_motor = (vals.get('has_motor') if 'has_motor' in codes else True) \
                and motor not in ('', '0', 'sin', 'False')
            if not tiene_motor or self._rf_sin_interruptor(vals.get('interruptor_rf')):
                continue
            con_motor.append(n)
            control = str(vals.get('control') or '')
            if not control or control == 'False':
                issue = make(n, 'V_CONTROL_REQUERIDO',
                             'E20030: La persiana lleva motor: elija el control '
                             '(o «Sin control» si usará un canal del control de '
                             'otra persiana).')
                if issue:
                    issues.append(issue)
                continue
            if control not in ('0', 'sin'):
                con_control = True
            canal = str(vals.get('control_channel') or '').strip()
            pide_canal = control in ('0', 'sin') or self._canales_control(control) > 1
            if pide_canal and 'control_channel' in codes and canal in ('', '0', 'False'):
                issue = make(n, 'V_CANAL_REQUERIDO',
                             'E20032: Elija el canal del control para esta '
                             'persiana.')
                if issue:
                    issues.append(issue)
        if con_motor and not con_control:
            issue = make(con_motor[0], 'V_CONTROL_PEDIDO',
                         'E20031: El pedido tiene persianas con motor pero '
                         'ninguna lleva control: al menos una debe pedir el '
                         'control.')
            if issue:
                issues.append(issue)
        return issues

    @api.model
    def _validate_sequences(self, lines_vals):
        """Fase 5.4c: reglas del configurador de secuencia (programa HTML del
        cliente) sobre las persianas con «Mismo cabezal», agrupadas por
        nombre de secuencia. Devuelve [{line, code, severity, message}]."""

        def make(n, code, default_msg):
            return {'line': n, 'code': code, 'severity': 'error', 'message': default_msg}

        issues = []
        traccion = ('MANDO', 'MOTOR')
        groups = {}
        for n, vals in enumerate(lines_vals, start=1):
            if not vals.get('same_header'):
                continue
            key = (vals.get('sequence_name') or '').strip().lower()
            # Pendientes 24-sep (4.2): con «Mismo cabezal» el nombre de la
            # secuencia es obligatorio.
            if not key:
                issue = make(n, 'V_SECUENCIA_NOMBRE',
                             'E20015: Con «Mismo cabezal o soporte intermedio» '
                             'debe diligenciar el Nombre de la secuencia.')
                if issue:
                    issues.append(issue)
            groups.setdefault(key, []).append((n, vals))

        Fabric = self.env['safra.fabric'].sudo()
        for key, lines in groups.items():
            # Reunión 28-sep (fila 4): dentro de una misma secuencia, las
            # persianas de la misma referencia de tela deben tener el mismo
            # alto (el cabezal es uno solo). Se evalúa aparte de la
            # configuración de soportes para mostrar todos los errores.
            por_tela = {}
            for n, l in lines:
                if l.get('fabric_id'):
                    por_tela.setdefault(l['fabric_id'], []).append((n, l))
            for fid, mismas in por_tela.items():
                altos = {round(float(l.get('height') or 0), 3) for _, l in mismas}
                if len(mismas) > 1 and len(altos) > 1:
                    issue = make(mismas[0][0], 'V_SECUENCIA_ALTO',
                                 'E20024: En la secuencia «%s» las persianas '
                                 'de la referencia %s deben tener el mismo '
                                 'alto.' % (lines[0][1].get('sequence_name') or key,
                                            Fabric.browse(fid).name))
                    if issue:
                        issues.append(issue)
            # Reunión 28-sep (fila 5): una secuencia es de dos o más
            # persianas; con una sola no hay nada que configurar. (Sin
            # nombre ya lo reporta E20015.)
            if key and len(lines) < 2:
                issue = make(lines[0][0], 'V_SECUENCIA_MIN',
                             'E20023: La secuencia «%s» tiene una sola '
                             'persiana; una secuencia necesita al menos dos '
                             '(agregue otra con el mismo nombre o desmarque '
                             '«Mismo cabezal»).'
                             % (lines[0][1].get('sequence_name') or key))
                if issue:
                    issues.append(issue)
                continue
            # Pendientes 24-sep (4.1) + reporte 28-sep: sin la secuencia
            # COMPLETA (todos los soportes izq/der de todas sus persianas,
            # incluso si el grupo es de una sola) el pedido NO se guarda —
            # antes un «Aplicar» vacío o parcial pasaba derecho.
            incompletas = [n for n, l in lines
                           if not (l.get('soporte_izq') and l.get('soporte_der'))]
            if incompletas:
                issue = make(incompletas[0], 'V_SECUENCIA_PENDIENTE',
                             'E20016: Las persianas con «Mismo cabezal» aún '
                             'no tienen configurada la secuencia completa '
                             '(botón Configurar Secuencia).')
                if issue:
                    issues.append(issue)
                continue

            sops = [(l.get('soporte_izq') or '', l.get('soporte_der') or '') for _, l in lines]
            first_n = lines[0][0]
            # Extremos: la secuencia no inicia ni termina con DEP/INDEP.
            if sops[0][0] in ('DEP', 'INDEP') or sops[-1][1] in ('DEP', 'INDEP'):
                issue = make(first_n, 'V_SECUENCIA',
                             'La secuencia no puede iniciar ni terminar con un '
                             'soporte dependiente/independiente.')
                if issue:
                    issues.append(issue)
            # Uniones entre persianas vecinas.
            for i in range(len(sops) - 1):
                der, izq = sops[i][1], sops[i + 1][0]
                if der and izq:
                    conector = der in ('DEP', 'INDEP') or izq in ('DEP', 'INDEP')
                    if conector and der != izq:
                        issue = make(lines[i][0], 'V_SECUENCIA',
                                     'Los soportes que se enfrentan entre las persianas '
                                     '%d y %d deben coincidir.' % (lines[i][0], lines[i + 1][0]))
                        if issue:
                            issues.append(issue)
                    if der in traccion and izq in traccion:
                        issue = make(lines[i][0], 'V_SECUENCIA',
                                     'No puede haber dos fuentes de tracción (mando/motor) '
                                     'enfrentadas entre las persianas %d y %d.'
                                     % (lines[i][0], lines[i + 1][0]))
                        if issue:
                            issues.append(issue)
            # Una persiana no puede tener dos fuentes de tracción propias.
            for n, l in lines:
                if (l.get('soporte_izq') in traccion and l.get('soporte_der') in traccion):
                    issue = make(n, 'V_SECUENCIA',
                                 'La persiana no puede tener dos fuentes de tracción '
                                 '(mando/motor) en sus dos soportes.')
                    if issue:
                        issues.append(issue)
            # Cadenas por uniones DEP-DEP (union-find) y su tracción.
            parent = list(range(len(sops)))

            def find(x):
                while parent[x] != x:
                    x = parent[x]
                return x

            for i in range(len(sops) - 1):
                if sops[i][1] == 'DEP' and sops[i + 1][0] == 'DEP':
                    ra, rb = find(i), find(i + 1)
                    if ra != rb:
                        parent[ra] = rb
            chains = {}
            for i in range(len(sops)):
                chains.setdefault(find(i), []).append(i)
            for members in chains.values():
                total = sum((1 if sops[i][0] in traccion else 0)
                            + (1 if sops[i][1] in traccion else 0) for i in members)
                nombres = ', '.join('persiana %d' % lines[i][0] for i in members)
                complete = all(sops[i][0] and sops[i][1] for i in members)
                if total > 1:
                    issue = make(lines[members[0]][0], 'V_SECUENCIA',
                                 'Conflicto de tracción: %s quedarían unidas por soportes '
                                 'dependientes y no pueden tener más de un mando/motor '
                                 'entre todas.' % nombres)
                    if issue:
                        issues.append(issue)
                elif total == 0 and complete:
                    issue = make(lines[members[0]][0], 'V_SECUENCIA',
                                 'Falta una fuente de tracción: %s quedarían sin mando ni '
                                 'motor.' % nombres)
                    if issue:
                        issues.append(issue)
        return issues

    @api.model
    def _tramos_dependientes(self, lines_vals):
        """Revisión cálculo de tubo (27-oct, error 3): variable «tramo» de las
        condiciones. Para cada persiana unida a otras por soportes
        dependientes, el tramo calculado como una sola persiana: {ancho,
        alto, numeros, persianas (texto), tabla (el sistema tiene estructura),
        tubo ('' si ninguno lo soporta), alto_maximo, alto_ok, peso, peso_ok,
        carga}. Las reglas V_SECUENCIA_DEP_* lo usan en su condición."""
        grupos = {}
        for n, vals in enumerate(lines_vals, start=1):
            nombre = (vals.get('sequence_name') or '').strip().lower()
            if vals.get('same_header') and nombre and vals.get('system_id'):
                grupos.setdefault(nombre, []).append((n, vals))
        tramos = {}
        for grupo in grupos.values():
            for cadena in self._cadenas_dependientes([v for _n, v in grupo]):
                numeros = [grupo[i][0] for i in cadena]
                tiene, res, ancho, alto = self._estructura_cadena([grupo[i][1] for i in cadena])
                lim = res['limites']
                tramo = {
                    'ancho': round(ancho, 3), 'alto': alto, 'numeros': numeros,
                    'persianas': ', '.join('persiana %d' % n for n in numeros),
                    'tabla': tiene, 'tubo': res['regla'].tubo or '' if res['regla'] else '',
                    'alto_maximo': lim.get('alto_maximo'), 'alto_ok': lim.get('alto_ok'),
                    'peso': lim.get('peso_total'), 'peso_ok': lim.get('peso_ok'),
                    'carga': lim.get('carga_maxima'),
                }
                for n in numeros:
                    tramos[n] = tramo
        return tramos

    @api.model
    def _asignar_rollos(self, lines_vals):
        """Pendiente 12.3 (rollos = lotes, confirmado por Safra el 5-oct):
        cada persiana necesita una pieza continua de tela de un solo rollo.
        Largo de la pieza = alto (o el ancho, si la tela se corta
        atravesada) + el aumento de tela del tubo de la estructura. Las
        piezas del pedido se reparten entre los rollos disponibles de cada
        color, de la más larga a la más corta, cada una en el rollo con
        MENOS metros que todavía la alcanza (el que mejor se ajusta).

        Devuelve (issues, {n: lote}):
        - E20027 (V_ROLLO_DISPONIBLE, advertencia): una pieza no cabe en
          ningún rollo. La matriz deja el bloqueo por rollos para la fase de
          fabricación: el portal avisa y deja finalizar.
        - E20028 (V_ROLLO_ALINEADO, advertencia): las persianas alineadas de
          una misma tela y color no alcanzan a salir de un mismo rollo
          (acuerdo 17-sep: se deja pasar avisando, la planta lo revisa).
        Los colores cuyo artículo no se controla por lotes se omiten."""
        Rule = self.env['safra.structure.rule'].sudo()

        def make(n, code, default_msg, severity):
            return {'line': n, 'code': code, 'severity': severity, 'message': default_msg}

        piezas = {}       # color -> [(n, largo)]
        alineadas = {}    # color -> [largo]
        for n, vals in enumerate(lines_vals, start=1):
            line = self.new({k: v for k, v in vals.items() if k in self._fields})
            color, fabric = line.color_id, line.fabric_id
            w, h = line.width or 0.0, line.height or 0.0
            if not color or not w or not h:
                continue
            ancho_rollo = color.product_tmpl_id.safra_u_ancho or 0.0
            atravesada = (fabric.pierceable_type in ('si', 'si_cliente')
                          and ancho_rollo and w > ancho_rollo)
            regla = Rule.find_rule(line.system_id, w, motorized=bool(line.has_motor))
            largo = (w if atravesada else h) + (regla._constantes()['aumento'] if regla else 0.0)
            for _i in range(max(int(line.quantity or 1), 1)):
                piezas.setdefault(color, []).append((n, largo))
                if line.aligned:
                    alineadas.setdefault(color, []).append(largo)

        issues, sugeridos = [], {}
        for color, lista in piezas.items():
            rollos = color._rollos_disponibles()
            if rollos is None:
                continue
            nombre = '%s %s' % (color.fabric_id.name, color._portal_label())
            mayor = max(rollos.values(), default=0.0)
            juntas = sum(alineadas.get(color, []))
            if len(alineadas.get(color, [])) > 1 and juntas > mayor:
                n0 = next(n for n, v in enumerate(lines_vals, start=1)
                          if v.get('aligned') and v.get('color_id') == color.id)
                issue = make(n0, 'V_ROLLO_ALINEADO',
                             'E20028: Las persianas alineadas de %s necesitan '
                             '%.2f m de un mismo rollo y el rollo más largo '
                             'disponible tiene %.2f m; la planta revisará '
                             'cómo alinearlas.' % (nombre, juntas, mayor),
                             'warning')
                if issue:
                    issues.append(issue)
            libres = dict(rollos)
            sin_rollo = {}
            for n, largo in sorted(lista, key=lambda p: -p[1]):
                aptos = [lote for lote, m in libres.items() if m + 1e-6 >= largo]
                if not aptos:
                    sin_rollo.setdefault(n, largo)
                    continue
                lote = min(aptos, key=lambda l: libres[l])
                libres[lote] -= largo
                sugeridos.setdefault(n, lote)
            for n, largo in sorted(sin_rollo.items()):
                if rollos:
                    msg = ('E20027: No hay un rollo de %s con %.2f m libres '
                           'para esta persiana (el rollo más largo que queda '
                           'tiene %.2f m); la planta revisará el corte.'
                           % (nombre, largo, max(libres.values(), default=0.0)))
                else:
                    msg = ('E20027: No hay rollos disponibles de %s; la planta '
                           'revisará el corte.' % nombre)
                issue = make(n, 'V_ROLLO_DISPONIBLE', msg, 'warning')
                if issue:
                    issues.append(issue)
        return issues, sugeridos

    @api.model
    def _cabezal_elegido(self):
        """Sprint 1.3: (tipo para la tabla de estructura, etiqueta) del
        cabezal elegido. El valor es el código de la línea de Referencias de
        la categoría del campo o, sin referencias, una opción de catálogo."""
        self.ensure_one()
        value = (self.attribute_values or {}).get('cabezal_tipo')
        if not value:
            return None, ''
        value = str(value)
        label = ''
        field = self.env['safra.field'].sudo().search([('code', '=', 'cabezal_tipo')], limit=1)
        if field.ref_category_id:
            Color = self.env['safra.fabric.color'].sudo().with_context(active_test=False)
            dom = [('fabric_id.category_id', '=', field.ref_category_id.id)]
            color = Color.search(dom + [('code', '=', value)], limit=1)
            if not color and value.isdigit():
                color = Color.search(dom + [('id', '=', int(value))], limit=1)
            label = color._portal_label() if color else ''
        if not label:
            opt = self.env['safra.system.field.option'].sudo().search([
                ('system_field_id.system_id', '=', self.system_id.id),
                ('system_field_id.field_id.code', '=', 'cabezal_tipo'),
                ('value', '=', value)], limit=1) or self.env['safra.field.option'].sudo().search([
                    ('field_id.code', '=', 'cabezal_tipo'), ('value', '=', value)], limit=1)
            label = opt.name or value
        low = label.lower()
        tipo = 'redondo' if 'redondo' in low else ('cuadrado' if 'cuadrado' in low else None)
        return tipo, label

    @api.model
    def _cadenas_dependientes(self, grupo):
        """Revisión cálculo de tubo (27-oct, error 3): tramos de una
        secuencia unidos por soportes dependientes (DEP enfrentado a DEP
        entre persianas vecinas), como posiciones dentro de `grupo` (dicts
        de las persianas en orden). Solo los de dos o más persianas."""
        cadenas, actual = [], [0] if grupo else []
        for i in range(1, len(grupo)):
            if grupo[i - 1].get('soporte_der') == 'DEP' and grupo[i].get('soporte_izq') == 'DEP':
                actual.append(i)
            else:
                cadenas.append(actual)
                actual = [i]
        if actual:
            cadenas.append(actual)
        return [c for c in cadenas if len(c) > 1]

    @api.model
    def _estructura_cadena(self, grupo):
        """El tramo de mando a terminal como una sola persiana (archivo de
        Safra, misma ventana): ancho sumado, el mayor alto, la tela y el
        perfil más pesados y motorizada si alguna lleva motor. Devuelve
        (tiene tabla, resultado de elegir(), ancho, alto)."""
        Rule = self.env['safra.structure.rule'].sudo()
        lines = [self.new({k: v for k, v in vals.items() if k in self._fields}) for vals in grupo]
        system = lines[0].system_id
        ancho = sum(l.width or 0.0 for l in lines)
        alto = max(l.height or 0.0 for l in lines)
        todos = [l._params_estructura() for l in lines]
        params = {k: max(p[k] for p in todos) for k in todos[0]}
        tiene = bool(system) and bool(Rule.search_count([('system_ids', 'in', system.id)]))
        res = Rule.elegir(system, ancho, alto, motorized=any(l.has_motor for l in lines),
                          cabezal=lines[0]._cabezal_elegido()[0], **params) if tiene \
            else {'base': Rule.browse(), 'regla': Rule.browse(), 'limites': {}, 'subio_de': None}
        return tiene, res, ancho, alto

    @api.model
    def _unificar_secuencias(self, lines_vals):
        """Sprint 1.3 (fila 73): en persianas con Mismo cabezal la
        Unificación Mando es obligatoria y automática: todas las de la
        secuencia van con el tubo MAYOR de la secuencia. Reunión 15-oct: si
        en alguna persiana se pidió un tubo aún mayor, ese manda en toda la
        secuencia (nunca uno menor al calculado). Ajusta
        attribute_values['unificacion_mando'] en los mismos dicts (así se
        valida y se guarda con el tubo unificado).
        Revisión 27-oct (error 2): manuales y motorizadas se comparan en un
        solo orden de tubos y, si la secuencia lleva motor, el tubo de todas
        es uno de la tabla motorizada."""
        Rule = self.env['safra.structure.rule'].sudo()
        grupos = {}
        for vals in lines_vals:
            nombre = (vals.get('sequence_name') or '').strip().lower()
            if vals.get('same_header') and nombre and vals.get('system_id'):
                grupos.setdefault(nombre, []).append(vals)
        for grupo in grupos.values():
            bases, pedidos, orden, motor = [], [], [], []
            for vals in grupo:
                line = self.new({k: v for k, v in vals.items() if k in self._fields})
                system = line.system_id
                tubos = Rule.tubos_secuencia(system)
                # Revisión 27-oct (error 6): el tubo que la persiana
                # necesita, también por su alto.
                base = Rule.elegir(system, line.width or 0.0, line.height or 0.0,
                                   motorized=line.has_motor, cabezal=line._cabezal_elegido()[0],
                                   **line._params_estructura())['regla']
                bases.append(base.tubo if base else None)
                pedidos.append((vals.get('attribute_values') or {}).get('unificacion_mando'))
                orden = tubos if len(tubos) > len(orden) else orden
                if line.has_motor and not motor:
                    motor = Rule.tubos_ordenados(system, motorized=True)
            # Revisión 27-oct (error 3): cada tramo unido por soportes
            # dependientes pide el tubo que necesita como una sola persiana.
            for cadena in self._cadenas_dependientes(grupo):
                res = self._estructura_cadena([grupo[i] for i in cadena])[1]
                if res['regla']:
                    pedidos.append(res['regla'].tubo)
            conocidos = [t for t in bases + pedidos if t in orden]
            if not conocidos:
                continue
            mayor = max(conocidos, key=orden.index)
            motorizados = [t for t in motor if t in orden and orden.index(t) >= orden.index(mayor)]
            if motorizados:
                mayor = motorizados[0]
            # Revisión 27-oct (error 2): las persianas manuales de un tramo
            # con soportes dependientes que lleva motor las mueve ese motor:
            # usan la tabla motorizada (mecanismo MOTOR) con el tubo unificado.
            del_motor = set()
            for cadena in self._cadenas_dependientes(grupo):
                if any(grupo[i].get('has_motor') for i in cadena):
                    del_motor.update(i for i in cadena if not grupo[i].get('has_motor'))
            for pos, (vals, base) in enumerate(zip(grupo, bases)):
                attrs = dict(vals.get('attribute_values') or {})
                if pos in del_motor:
                    attrs.update(unificacion_mando=mayor, unificacion_motor=True)
                elif base and base != mayor:
                    attrs['unificacion_mando'] = mayor
                    attrs.pop('unificacion_motor', None)
                else:
                    attrs.pop('unificacion_mando', None)
                    attrs.pop('unificacion_motor', None)
                vals['attribute_values'] = attrs
        return lines_vals

    def _validate_order(self, lines_vals, cross=True, pedido=None, campo=None, momento=None,
                        reglas=None):
        """Motor de validaciones del pedido sobre líneas sin guardar (portal)
        o reconstruidas desde una cotización guardada (revalidación al
        confirmar). Usa registros new() sin tocar la base. Con cross=False
        solo valida cada línea por sí sola («Guardar línea»); con `campo`
        además, solo las reglas «Al digitar» de ese campo. `pedido` trae
        lo que se marca para todo el pedido (Safra Express, verificación).
        Con `reglas`, solo esas reglas de Validaciones.
        Devuelve [{line: n, code, severity, message}]; line = 0 es el pedido."""
        pedido = pedido or {}
        # Revisión 28-oct: momento «secuencia» (configurador): reglas
        # cruzadas, pero solo las de ese momento.
        momento = momento or ('pedido' if cross else ('campo' if campo else 'linea'))
        _lines, hallazgos, contextos = self._preparar_reglas(lines_vals, cross=cross, pedido=pedido)
        issues = self._aplicar_reglas(hallazgos, contextos, momento, campo=campo, solo_regla=reglas)
        if momento == 'campo':
            # Revisión 30-oct: los avisos del corte salen junto a la tela
            # (_avisos_corte), no debajo del campo que cambió.
            issues = [i for i in issues if i.get('code') not in self.REGLAS_CORTE]
        # Reunión 15-oct (fila 74): en una persiana «sin restricciones» los
        # errores se muestran como advertencias y no bloquean; quedan
        # marcados para el ticket de producción.
        sin = {n for n, vals in enumerate(lines_vals, start=1) if vals.get('sin_restricciones')}
        for issue in issues:
            if issue.get('line') in sin and issue.get('severity') == 'error':
                issue['severity'] = 'warning'
                issue['saltada'] = True
                issue['message'] = 'Sin restricciones (sin garantía): %s' % issue['message']
        # Sprint 1.6 (fila 128, reunión 21-oct): con verificación de
        # fabricación las restricciones de las persianas no bloquean; planta
        # las revisa desde el ticket. Las del pedido (line 0) sí bloquean.
        if pedido.get('requiere_verificacion'):
            for issue in issues:
                if issue.get('line') and issue.get('severity') == 'error':
                    issue['severity'] = 'warning'
                    issue['saltada'] = True
                    issue['message'] = 'Verificación de fabricación: %s' % issue['message']
        return self._con_codigo_regla(issues)

    @api.model
    def _avisos_corte(self, vals, pedido=None):
        """Revisión 30-oct (tela atravesable y U_Añadido): tipo de corte de
        la tela de una persiana y los mensajes de las reglas activas del
        corte (REGLAS_CORTE) con su condición y mensaje de Validaciones; en
        «avisos_ficha», los de la ficha técnica (REGLAS_FICHA).
        `bloquea`: alguno es error (no se puede fabricar), y el portal no
        deja seguir configurando la persiana; los de ACEPTACION_CORTE no
        bloquean el formulario (se resuelven con el check de aceptación)."""
        reglas = self.env['safra.validation.rule']._por_clave(
            self.REGLAS_CORTE + self.REGLAS_FICHA).filtered('active')
        todos = self._validate_order([vals], cross=False, pedido=pedido, momento='linea',
                                     reglas=reglas) if reglas else []
        avisos = [a for a in todos if a.get('code') not in self.REGLAS_FICHA]
        tipo = self.new({k: v for k, v in vals.items() if k in self._fields})._corte_tela()['tipo']
        return {'tipo': tipo, 'avisos': avisos,
                # Acta del 30-oct (Tubo, punto 8): van en la ficha técnica y no
                # bloquean el formulario (sí guardar la línea si son error).
                'avisos_ficha': [a for a in todos if a.get('code') in self.REGLAS_FICHA],
                'bloquea': any(a['severity'] == 'error' and a.get('code') not in self.ACEPTACION_CORTE
                               for a in avisos)}

    @api.model
    def _con_codigo_regla(self, issues):
        """Revisión 28-oct: cada mensaje termina con el Código de su regla
        («[V_PLANO_SEGMENTOS]») para buscarla en Validaciones. Solo los
        códigos que existen allí; así sale en el portal, el cargue masivo,
        el motivo del bloqueo y el ticket. Si Safra cambió el Código, sale el
        nuevo (la regla se encuentra por su clave interna)."""
        claves = {i.get('code') for i in issues if i.get('code')}
        visibles = {r._clave_programa(): r.code for r in
                    self.env['safra.validation.rule']._por_clave(claves)} if claves else {}
        for issue in issues:
            codigo = issue.get('codigo') or visibles.get(issue.get('code'))
            sufijo = ' [%s]' % codigo
            if codigo and issue.get('code') in visibles and not issue['message'].endswith(sufijo):
                issue['message'] += sufijo
        return issues

    @api.model
    def _parametro(self, clave, defecto):
        try:
            return float(self.env['ir.config_parameter'].sudo().get_param(clave) or defecto)
        except ValueError:
            return defecto

    @api.model
    def _validate_express(self, lines_vals, pedido):
        """Sprint 1.6 (fila 127): Safra Express no se puede pedir cuando el
        pedido pasa de 10 unidades en total (parámetro
        safra.express_max_unidades)."""
        if not pedido.get('safra_express'):
            return []
        tope = int(self._parametro('safra.express_max_unidades', 10))
        total = sum(int(v.get('quantity') or 1) for v in lines_vals)
        if total <= tope:
            return []
        fmt = {'tope': tope, 'total': total}
        return [{'line': 0, 'code': 'V_EXPRESS_CANTIDAD', 'severity': 'error', 'fmt': fmt,
                 'message': 'E20041: Safra Express no se puede pedir en pedidos de más de '
                            '{tope} unidades; el pedido tiene {total}.'.format(**fmt)}]

    @api.model
    def _validate_planos(self, lines_vals):
        """Bloque 3 (acuerdos 17-sep y 28-sep): el Tipo de Plano une
        SEGMENTOS DE CABEZAL. Cada segmento es una secuencia («Mismo
        cabezal», agrupada por nombre: plano y segmento se eligen una sola
        vez para todas sus persianas) o una persiana individual con plano
        (plano y segmento en su propia línea). A nivel de pedido, cada plano
        usado debe traer todos sus segmentos (1..N según el catálogo), cada
        uno una sola vez; si falta alguno no se puede fabricar el cabezal."""

        def make(n, default_msg):
            return {'line': n, 'code': 'V_PLANO_SEGMENTOS', 'severity': 'error',
                    'message': default_msg}

        def attr(vals, key):
            return str((vals.get('attribute_values') or {}).get(key) or '').strip()

        requeridos = {}
        for opt in self.env['safra.field.option'].sudo().search(
                [('field_id.code', '=', 'tipo_plano')]):
            if opt.segmentos:
                requeridos[(opt.value or '').strip().upper()] = opt.segmentos

        # Segmentos de cabezal del pedido.
        segmentos = {}
        for n, vals in enumerate(lines_vals, start=1):
            if vals.get('same_header'):
                key = ('secuencia', (vals.get('sequence_name') or '').strip().lower())
            elif attr(vals, 'tipo_plano'):
                key = ('linea', n)
            else:
                continue
            segmentos.setdefault(key, []).append((n, vals))

        issues = []
        por_plano = {}
        for key, lines in segmentos.items():
            n0, v0 = lines[0]
            nombre = ('la secuencia «%s»' % (v0.get('sequence_name') or key[1])
                      if key[0] == 'secuencia' else 'la persiana %d' % n0)
            planos = {attr(v, 'tipo_plano').upper() for _, v in lines} - {''}
            segs = {attr(v, 'num_segmento') for _, v in lines} - {''}
            if not planos:
                continue
            if len(planos) > 1 or len(segs) > 1:
                issue = make(n0, 'E20022: Todas las persianas de %s van en el '
                                 'mismo cabezal: deben tener el mismo Tipo de '
                                 'Plano y el mismo Segmento.' % nombre)
                if issue:
                    issues.append(issue)
                continue
            plano = planos.pop()
            if plano not in requeridos:
                continue
            if not segs:
                issue = make(n0, 'E20022: Con Tipo de Plano %s falta elegir '
                                 'el Segmento de %s.' % (plano, nombre))
                if issue:
                    issues.append(issue)
                continue
            por_plano.setdefault(plano, []).append((n0, nombre, segs.pop()))

        for plano, units in por_plano.items():
            esperados = [str(i) for i in range(1, requeridos[plano] + 1)]
            usados = {}
            for n, nombre, seg in units:
                if seg not in esperados:
                    issue = make(n, 'E20022: El Plano %s tiene los segmentos '
                                    '%s; %s trae el segmento %s.'
                                 % (plano, ', '.join(esperados), nombre, seg))
                    if issue:
                        issues.append(issue)
                    continue
                if seg in usados:
                    issue = make(n, 'E20022: El segmento %s del Plano %s ya lo '
                                    'usa %s; %s debe ser otro segmento.'
                                 % (seg, plano, usados[seg], nombre))
                    if issue:
                        issues.append(issue)
                    continue
                usados[seg] = nombre
            faltan = [x for x in esperados if x not in usados]
            if faltan:
                issue = make(units[0][0],
                             'E20022: El Plano %s requiere en el pedido los '
                             'segmentos %s (uno por secuencia o persiana); '
                             'falta%s el %s.' % (
                                 plano, ', '.join(esperados),
                                 'n' if len(faltan) > 1 else '',
                                 ', '.join(faltan)))
                if issue:
                    issues.append(issue)
        return issues

    def _campos_formula(self):
        """Reunión 28-sep (fila 16): {código técnico: valor} de la línea para
        que las fórmulas (combinaciones, máximo de lamas) puedan usar
        cualquier campo del cotizador — los que van en columna y los que
        viajan en attribute_values."""
        self.ensure_one()
        campos = dict(self.attribute_values or {})
        for code in self.env['safra.field'].sudo().search([]).mapped('code'):
            if code in self._fields and code not in campos:
                val = self[code]
                campos[code] = val.id if isinstance(val, models.BaseModel) else val
        return campos

    # Reunión 09-oct (fila 16): el Tipo de Riel se identifica por la
    # etiqueta de su opción («4 Vías», «Riel Velcrado»…), que es lo que
    # comparten los sistemas; «Auto» y los rieles sin canales conocidos
    # (p. ej. Riel Suizo) no se restringen.
    def _riel_tipo_label(self, value):
        self.ensure_one()
        opt = self.env['safra.system.field.option'].sudo().search([
            ('system_field_id.system_id', '=', self.system_id.id),
            ('system_field_id.field_id.code', '=', 'riel_tipo'),
            ('value', '=', str(value))], limit=1)
        if opt:
            return opt.name
        linea = self._riel_linea_referencia(value)
        return linea._portal_label() if linea else str(value)

    @api.model
    def _riel_linea_referencia(self, value):
        """Sprint 1.5 (fila 99): línea de una referencia de rieles (categoría
        marcada «Rieles») cuyo código es el valor elegido."""
        linea = self.env['safra.fabric.color']._linea_desde_valor(value)
        return linea if linea.fabric_id.category_id.es_riel else self.env['safra.fabric.color']

    @api.model
    def _riel_info_desde_etiqueta(self, label):
        txt = (label or '').lower()
        if 'velcrado' in txt:
            return 'velcrado'
        m = re.search(r'(\d+)\s*v[ií]as', txt)
        return int(m.group(1)) if m else None

    def _riel_tipo_info(self, value):
        """Riel elegido: número de canales, 'velcrado' o None (Auto u
        otro riel que no se cruza con la combinación). Solo se cruza en
        los sistemas cuyo Tipo de Riel se expresa en vías."""
        self.ensure_one()
        linea = self._riel_linea_referencia(value)
        if linea:
            # Desde Referencias: la línea dice sus canales y si es Velcrado;
            # sin canales (p. ej. «Auto») no se cruza.
            if linea.velcrado:
                return 'velcrado'
            return linea.canales or self._riel_info_desde_etiqueta(linea._portal_label())
        opts = self.env['safra.system.field.option'].sudo().search([
            ('system_field_id.system_id', '=', self.system_id.id),
            ('system_field_id.field_id.code', '=', 'riel_tipo')])
        if not any(isinstance(self._riel_info_desde_etiqueta(o.name), int) for o in opts):
            return None
        return self._riel_info_desde_etiqueta(self._riel_tipo_label(value))

    def _riel_auto_resuelto(self):
        """Sprint 1.5 (fila 99, obs. 2): con Tipo de Riel «Auto» se usa el
        riel de la combinación de telos y apertura elegida. Devuelve su
        nombre («riel de 5 vías», «Riel Velcrado») o '' si no se puede
        resolver todavía."""
        self.ensure_one()
        attrs = self.attribute_values or {}
        valor = attrs.get('riel_tipo')
        if not valor or 'auto' not in (self._riel_tipo_label(valor) or '').lower():
            return ''
        try:
            lamas = int(attrs.get('quantity_lamas') or 0)
            traslape = float(str(attrs.get('tamano_traslape') or 0.08).replace(',', '.'))
        except (TypeError, ValueError):
            return ''
        if not (lamas and self.width and self.system_id and attrs.get('apertura')):
            return ''
        ap_map = {'1': 'unilateral_derecha', '2': 'unilateral_izquierda',
                  '3': 'extremos', '4': 'centro', '5': 'libre',
                  'derecha': 'unilateral_derecha', 'izquierda': 'unilateral_izquierda',
                  'extremos': 'extremos', 'centro': 'centro', 'libre': 'libre'}
        configs = self.env['safra.panel.track'].compute_configs(
            self.width, traslape, lamas, campos=self._campos_formula(), system=self.system_id)
        elegida = [c for c in configs
                   if c['codigo_apertura'] == ap_map.get(str(attrs['apertura']))]
        riel = elegida and self._riel_de_combinacion(elegida[0])
        return self._riel_nombre(riel) if riel else ''

    def _guardar_riel_auto(self):
        """Deja en la línea (attribute_values['riel_resuelto']) el riel que
        «Auto» toma de la combinación, para producción."""
        for line in self:
            resuelto = line._riel_auto_resuelto()
            if resuelto:
                line.attribute_values = dict(line.attribute_values or {}, riel_resuelto=resuelto)

    # --- Sprint 1.5 ------------------------------------------------------

    def _items_no_disponibles(self, user=None):
        """Reunión 28-sep (fila 2) y cierre del 09-nov: lo que eligió el
        cliente y ya no está disponible — no solo la tela: cualquier ítem con
        la casilla Activo (sistema, referencias y colores de todas las telas,
        y los productos de los campos de Referencias: perfil, motor, control,
        cenefa, riel…), el diseño y los servicios de la tela. Devuelve
        [{'campo', 'motivo', 'code', 'valor', 'nombre'}] para avisarle al
        cliente qué debe cambiar (code: campo del formulario; valor y nombre:
        lo que tenía elegido, para mostrarlo en gris junto al campo)."""
        self.ensure_one()
        user = user or self.quote_id.user_id or self.env.user
        out = []

        def falta(campo, motivo, code='', valor='', nombre=''):
            out.append({'campo': campo, 'motivo': motivo, 'code': code,
                        'valor': str(valor or ''), 'nombre': nombre or ''})

        system = self.system_id.sudo()
        if system and (not system.active or not system._visible_for_user(user)):
            falta('Sistema', 'el sistema %s ya no está disponible para %s' % (system.name, user.name),
                  'system_id', system.id, system.name)
        etiquetas = {m.field_id.code: (m.label_override or m.field_id.name)
                     for m in system.with_context(active_test=False).mapping_ids} if system else {}
        for n in ('', '_2', '_3', '_4', '_5'):
            fabric, color = self['fabric_id' + n].sudo(), self['color_id' + n].sudo()
            if fabric and not fabric.active:
                falta(etiquetas.get('fabric_id' + n, 'Referencia'),
                      'la referencia %s fue inactivada' % fabric.name,
                      'fabric_id' + n, fabric.id, fabric.name)
            if color and not color.active:
                falta(etiquetas.get('color_id' + n, 'Color'),
                      'el color %s fue inactivado' % color.name,
                      'color_id' + n, color.id, color._portal_label())
            elif color and not color._is_available_for_portal():
                falta(etiquetas.get('color_id' + n, 'Color'),
                      'el color %s ya no tiene existencias suficientes' % color.name,
                      'color_id' + n, color.id, color._portal_label())
        # Campos de Referencias (perfil, motor, control, cenefa, riel…): la
        # línea de la referencia, su referencia o su producto inactivados.
        Color = self.env['safra.fabric.color'].sudo()
        campos_ref = system.with_context(active_test=False).mapping_ids.mapped('field_id').filtered(
            lambda f: f.field_type == 'ref_categoria') if system else []
        for field in campos_ref:
            linea = Color._linea_desde_valor(self._valor_campo(field.code))
            if not linea:
                continue
            producto = linea.product_tmpl_id.with_context(active_test=False)
            if not linea.active or not linea.fabric_id.active or (producto and not producto.active):
                falta(etiquetas.get(field.code, field.name),
                      '«%s» (%s) fue inactivado' % (linea._portal_label(),
                                                    etiquetas.get(field.code, field.name)),
                      field.code, self._valor_campo(field.code), linea._portal_label())
        if self.custom_design and self.custom_design != 'OTROS':
            design = self.env['safra.design'].sudo().with_context(active_test=False).search(
                [('code', '=', self.custom_design)], limit=1)
            if design and not design.active:
                falta(etiquetas.get('custom_design', 'Diseño'),
                      'el diseño %s ya no está disponible' % design.code,
                      'custom_design', self.custom_design, design.code)
        # Revisión del 09-oct (fila 2): también los servicios de la tela.
        fabric = self.fabric_id.sudo()
        if fabric and (self.custom_design or self.design_print) and not fabric.is_printable:
            falta('Diseño de impresión', 'la referencia %s ya no permite estampación' % fabric.name,
                  'design_print')
        if fabric and (self.attribute_values or {}).get('textura_design') and not fabric.is_texturable:
            falta('Textura', 'la referencia %s ya no es texturizable' % fabric.name,
                  'textura_design')
        return out

    def _valor_campo(self, code):
        """Valor de un campo del cotizador en la línea, como texto (columna
        propia o attribute_values), con la convención del portal: casillas
        '1' o '' y referencias por su id."""
        self.ensure_one()
        if code in self._fields:
            valor = self[code]
            if isinstance(valor, models.BaseModel):
                return str(valor.id) if valor else ''
            if isinstance(valor, bool):
                return '1' if valor else ''
            return '' if valor in (None, False) else str(valor)
        valor = (self.attribute_values or {}).get(code)
        if isinstance(valor, bool):
            return '1' if valor else ''
        return '' if valor in (None, False) else str(valor)

    def _detalle_portal(self, resumen=False):
        """Ajustes Sprint 1.6 (26-oct, fila 124): lo elegido en la persiana,
        campo por campo y en el orden del formulario. [(etiqueta, valor)] de
        los campos visibles con valor. Con «resumen» (barrido de la matriz,
        fila 124), para las Características del resumen del pedido: sin lo
        que va en el Nombre (telas, medidas y cantidad) y primero los campos
        con «Orden en el resumen», como el portal actual de Safra."""
        self.ensure_one()
        maps = self.system_id.sudo().mapping_ids.filtered(lambda m: m.active and m.field_id.active)
        excluir = self._RESUMEN_EN_NOMBRE if resumen else ()

        def orden(m):
            if resumen and m.field_id.resumen_sequence:
                return (0, m.field_id.resumen_sequence, m.sequence, m.id)
            return (1, 0, m.sequence, m.id)

        # Como el formulario: un campo con «Requiere flag de tela» solo se ve
        # si la tela tiene esa marca (barrido de la matriz, fila 124).
        banderas = self.fabric_id.sudo()._banderas_portal() if self.fabric_id else {}
        filas = []
        for m in maps.sorted(orden):
            field = m.field_id
            if field.code == 'system_id' or field.code in excluir or not self._campo_visible(m, maps):
                continue
            if field.fabric_flag and not banderas.get(field.fabric_flag):
                continue
            valor = self._valor_campo(field.code)
            if not valor:
                continue
            columna = self._fields.get(field.code)
            if field.field_type == 'boolean':
                texto = 'Sí'
            elif columna is not None and columna.type == 'many2one':
                registro = self[field.code].sudo()
                texto = registro._portal_label() if hasattr(registro, '_portal_label') \
                    else registro.display_name
            elif field.field_type in ('selection', 'ref_categoria'):
                texto = self._etiqueta_y_ref(field, valor, maps)[0] or valor
            elif field.field_type == 'design':
                texto = self._design_display()
            else:
                texto = valor
            filas.append((m.label_override or field.name, texto))
        return filas

    # Barrido de la matriz (fila 124): lo que el resumen muestra en la
    # columna «Nombre» y no se repite en «Características».
    _RESUMEN_EN_NOMBRE = frozenset(
        ['width', 'height', 'quantity', 'fabric_id', 'color_id']
        + ['%s_%d' % (c, n) for c in ('fabric_id', 'color_id') for n in range(2, 6)])

    def _nombre_portal(self):
        """«Persiana ENROLLABLE Blackout Pinpoint Blanco + …»: el producto
        como lo arma el formulario del portal (sistema, referencias y
        colores)."""
        self.ensure_one()

        def tela(fabric, color):
            return ' '.join(p for p in (fabric.name, color._portal_label() if color else '') if p)

        nombre = ' '.join(p for p in (self.system_id.name, tela(self.fabric_id, self.color_id)) if p)
        for n in range(2, 6):
            if self['fabric_id_%d' % n]:
                nombre += ' + ' + tela(self['fabric_id_%d' % n], self['color_id_%d' % n])
        return ('Persiana ' + nombre).strip()

    def _resumen_portal(self):
        """Barrido de la matriz (fila 124): la persiana en el resumen del
        pedido, ordenada como el portal actual de Safra: nombre, medidas y
        cantidad; las características en el orden del formulario y, al
        final, el mecanismo de la tabla de estructura."""
        self.ensure_one()
        mecanismo = ''
        rule = self._estructura_linea()[1]
        if rule:
            mecanismo = rule._mechanism_line(cabezal=self._cabezal_elegido()[1] or None)
        return {
            'nombre': self._nombre_portal(),
            'ancho': self.width,
            'alto': self.height,
            'cantidad': self.quantity,
            'caracteristicas': self._detalle_portal(resumen=True),
            'mecanismo': mecanismo,
            'precio': self.price_total,
        }

    @api.model
    def _depende_ok(self, actual, depends_value, eti='', ref=''):
        """Misma regla que dependsMatch del portal: valores separados por
        coma, '!' adelante = ninguno de ellos, vacío = cualquier valor,
        'ref:CÓDIGO' = la referencia de la opción elegida y (ajustes del
        20-oct, fila 94) 'eti:Etiqueta' = la etiqueta de la opción elegida,
        sin mayúsculas ni tildes (para atributos que comparten producto)."""
        actual = actual or ''
        if not depends_value:
            return actual not in ('', '0')
        negado = depends_value.startswith('!')
        valores = [v.strip() for v in (depends_value[1:] if negado else depends_value).split(',')]

        def coincide(v):
            if v == 'not-selected':
                return actual == ''
            if v.startswith('ref:'):
                return bool(ref) and actual != '' and v[4:] == ref
            if v.startswith('eti:'):
                return bool(eti) and actual != '' and _normaliza(v[4:]) == _normaliza(eti)
            return v == actual
        hit = any(coincide(v) for v in valores)
        return not hit if negado else hit

    def _campo_visible(self, m, maps, vistos=None):
        """El campo del sistema se muestra con lo elegido (su dependencia
        y la de su padre, como el portal)."""
        if m.clear_depends:
            return True
        padre, valor = ((m.depends_field_id, m.depends_value) if m.depends_field_id
                        else (m.field_id.depends_field_id, m.field_id.depends_value))
        if not padre:
            return True
        vistos = (vistos or set()) | {m.field_id.id}
        padre_map = maps.filtered(lambda x: x.field_id == padre)[:1]
        if padre.id in vistos or (padre_map and not self._campo_visible(padre_map, maps, vistos)):
            return False
        actual = self._valor_campo(padre.code)
        # Revisión 27-oct: un código que comparten varias líneas del sistema
        # (p. ej. 054328 en «PVC CLASICA» y en «Sin cenefa») no dice cuál se
        # eligió; el campo se ve si alguna de ellas lo muestra.
        if padre.field_type == 'ref_categoria' and actual and not str(actual).startswith('ref-'):
            lineas = self._lineas_opcion(padre, actual)
            if len(lineas) > 1:
                return any(self._depende_ok(actual, valor, eti=l._portal_label(),
                                            ref=l.fabric_id.code or '') for l in lineas)
        eti, ref = self._etiqueta_y_ref(padre, actual, maps)
        return self._depende_ok(actual, valor, eti=eti, ref=ref)

    def _etiqueta_y_ref(self, field, valor, maps):
        """Etiqueta y código de referencia de lo elegido en un campo (para
        las dependencias eti:/ref:)."""
        if not valor:
            return '', ''
        if field.field_type == 'ref_categoria':
            linea = self._lineas_opcion(field, valor)[:1]
            return (linea._portal_label() if linea else ''), (linea.fabric_id.code or '' if linea else '')
        m = maps.filtered(lambda x: x.field_id == field)[:1]
        opt = (m.option_ids or field.option_ids).filtered(lambda o: o.value == valor)[:1]
        return opt.name or '', ''

    def _ancho_rollo(self):
        """Ancho del rollo de la tela elegida: U_Ancho del producto del color.
        Revisión 30-oct: sin dato vale 0 (ya no se toma el de otro color de
        la referencia) y el corte queda «sin_ancho_rollo»."""
        self.ensure_one()
        # U_Ancho sin digitar llega vacío (False) y un 0 digitado llega 0;
        # en una cuenta los dos valen 0.
        return self.color_id.product_tmpl_id.safra_u_ancho if self.color_id else 0.0

    def _sin_digitar(self, regla=None, con_motor=None, motor_ref=None, apertura=None):
        """Datos numéricos del maestro sin digitar que usan las fórmulas de
        esta persiana:
        - variables: {variable de las validaciones que llega vacía
          (ancho_rollo, motor_ancho_min, limites['wmax'],
          estructura['aumento_tela']…): dato};
        - formulas: {dato: [fórmulas de Ajustes y de opciones que lo usan]}.
        Los campos que una validación lee de un registro (tela.peso_gm2) se
        revisan al aplicarla (datos_vacios). Los parámetros son los que ya
        calculó _contexto_reglas (sin ellos se calculan aquí)."""
        self.ensure_one()
        variables, formulas = {}, {}
        system = self.system_id

        def usa(etiqueta, codigo, vacias):
            """Anota la fórmula en los datos de `vacias` ({variable: dato}) que lee."""
            nombres = {r[0] for r in datos_usados(codigo or '')}
            for var in sorted(nombres & set(vacias)):
                lista = formulas.setdefault(vacias[var], [])
                if etiqueta not in lista:
                    lista.append(etiqueta)

        producto_color = self.color_id.product_tmpl_id
        if producto_color and vacio_en(producto_color, 'safra_u_ancho'):
            variables['ancho_rollo'] = 'U_Ancho del color %s (%s)' % (
                self.color_id.name, self.fabric_id.name or self.color_id.fabric_id.name or '')
        if self.motor:
            if motor_ref is None:
                campo = self.env['safra.field'].sudo().search([('code', '=', 'motor')], limit=1)
                motor_ref = self._lineas_opcion(campo, self.motor)[:1]
            if vacio_en(motor_ref.product_tmpl_id, 'safra_u_ancho_min'):
                variables['motor_ancho_min'] = dato_sin_digitar(
                    motor_ref.product_tmpl_id, 'safra_u_ancho_min')
        if not system:
            return {'variables': variables, 'formulas': formulas}
        for clave, dato in system._limites_sin_digitar(exhibition=bool(self.exhibition)).items():
            variables['limites[%r]' % clave] = dato
        if regla is None:
            regla = self._estructura_linea()[1]
        if regla:
            tubo = regla.tubo_ref_id.product_tmpl_id
            if vacio_en(regla, 'aumento_tela') and (not tubo or vacio_en(tubo, 'safra_aumento_tela_tubo')):
                variables["estructura['aumento_tela']"] = dato_sin_digitar(regla, 'aumento_tela')
            if not system.tubo_solo_ancho:
                for etiqueta, codigo, vacias in self._formulas_tubo_sin_digitar(regla):
                    usa(etiqueta, codigo, vacias)
                # Revisión 10-nov: estructura['carga'] vacía (sin digitar).
                params = self._params_estructura()
                lim = regla.compute_limits(self.width or 0.0, self.height or 0.0, **params)
                if 'carga_maxima' in lim and lim['carga_maxima'] is None:
                    if params.get('motor_elegido'):
                        motor = self._producto_motor(self._valor_formulario('motor'))
                        variables["estructura['carga']"] = (
                            'Torque y Carga maxima del producto «%s»' % motor.display_name)
                    else:
                        variables["estructura['carga']"] = dato_sin_digitar(regla, 'carga_maxima')
        # Máximo de lamas: las constantes de su regla.
        if con_motor is None:
            con_motor = self._con_motor()
        if apertura is None:
            ap = str((self.attribute_values or {}).get('apertura') or '')
            apertura = {'1': 'derecha', '2': 'izquierda', '3': 'extremos', '4': 'centro'}.get(ap, ap)
        lamas = self.env['safra.lamas.rule'].sudo()._regla_max(system, apertura, con_motor)
        if lamas.formula_code:
            usa('la fórmula del máximo de lamas', lamas.formula_code,
                {c: dato_sin_digitar(lamas, c) for c in ('aux', 'divisor', 'adicional')
                 if vacio_en(lamas, c)})
        # Fórmulas de las opciones de los campos del sistema.
        vacias_opciones = dict(variables)
        maps = self.env['safra.system.field'].sudo().search([
            ('system_id', '=', system.id), ('active', '=', True)])
        for m in maps.filtered(lambda x: x.field_id.field_type == 'ref_categoria'):
            lineas = self._lineas_opcion(m.field_id, self._valor_formulario(m.field_id.code))
            productos = lineas.mapped('product_tmpl_id')
            if productos and all(vacio_en(p, 'safra_u_ancho_max') for p in productos):
                vacias_opciones['ancho_max_%s' % m.field_id.code] = dato_sin_digitar(
                    productos[:1], 'safra_u_ancho_max')
        if vacias_opciones:
            for m in maps:
                etiqueta = 'opciones de «%s»' % (m.label_override or m.field_id.name)
                for opt in (m.option_ids or m.field_id.option_ids):
                    usa(etiqueta, (opt.formula or '') + '\n' + (opt.auto_formula or ''), vacias_opciones)
        return {'variables': variables, 'formulas': formulas}

    def _formulas_tubo_sin_digitar(self, regla):
        """[(etiqueta, código, {variable vacía: dato})] de las fórmulas de
        Ajustes › Tubo: alto y peso máximo con los datos de esta persiana."""
        params = self._params_estructura()
        const_dato = {
            'espacio_eje_techo': ('espacio_eje_techo', [regla.cabezal_ref_id, regla.soporte_ref_id],
                                  'safra_espacio_eje_techo'),
            'diametro_tubo': ('diametro_tubo', [regla.tubo_ref_id], 'safra_diametro_tubo'),
            'carga_maxima': ('carga_maxima', [regla.mecanismo_ref_id], 'safra_carga_maxima'),
        }
        ctx = regla._ctx_limites(self.width or 0.0, self.height or 0.0, **params)
        vacias = {}
        for var, (campo, refs, campo_p) in const_dato.items():
            if ctx.get(var) is not False:
                continue
            dato = dato_sin_digitar(regla, campo)
            nombres = [r.product_tmpl_id._fields[campo_p].string for r in refs if r.product_tmpl_id]
            if nombres:
                dato += ' (ni el «%s» del producto)' % nombres[0]
            vacias[var] = dato
        if self.fabric_id:
            for var, campo in (('peso_tela', 'peso_gm2'), ('grosor_tela', 'grosor_mm')):
                if ctx.get(var) is False:
                    vacias[var] = dato_sin_digitar(self.fabric_id, campo)
        if ctx.get('peso_perfil') is False:
            attrs = self.attribute_values or {}
            perfil = attrs.get('perfil') or attrs.get('perfil_sheer') or attrs.get('perfileria2')
            color = self.env['safra.fabric.color'].sudo().search([('code', '=', str(perfil))], limit=1)
            vacias['peso_perfil'] = dato_sin_digitar(color.product_tmpl_id, 'safra_u_peso')
        # _params_estructura solo trae el motor si la persiana lo lleva.
        motor = self._producto_motor(self._valor_formulario('motor')) if self.has_motor \
            else self.env['product.template']
        if params.get('torque') is False and motor:
            vacias['torque'] = dato_sin_digitar(motor, 'safra_torque')
        if not vacias:
            return []
        Rule = self.env['safra.structure.rule']
        out = []
        for clave, nombre in FORMULAS_TUBO:
            if clave == 'safra.formula.tubo_carga_motor' and not motor:
                continue
            codigo = Rule._codigo_formula(self.env, clave, R17.FORMULAS_TUBO)
            out.append(('la fórmula «%s» de Ajustes › Tubo' % nombre, codigo, vacias))
        return out

    def _opciones_por_formula(self):
        """Sprint 1.5 (fila 118): {código del campo: valores ofrecidos}
        para los campos del sistema que tienen opciones con fórmula."""
        return self._formulas_opciones()['opciones']

    def _valor_formulario(self, code):
        """Valor de un campo tal como lo envió el formulario: la columna de
        la persiana o, si está vacía, el atributo (el portal manda todo en
        atributos al consultar las fórmulas)."""
        return self._valor_campo(code) or str((self.attribute_values or {}).get(code) or '')

    def _ctx_formulas_opciones(self, maps):
        """Variables de las fórmulas de las opciones (Sprint 1.5 y ajustes
        del 20 y 22-oct): medidas, rollo, motor, sistema, marcas de la tela
        y el ancho máximo (U_AnchoMax) del producto elegido en cada campo
        de Referencias (ancho_max_<código>)."""
        motor = self._valor_formulario('motor')
        base = {'alto': self.height or 0.0, 'ancho': self.width or 0.0,
                'ancho_rollo': self._ancho_rollo(), 'cantidad': self.quantity or 0,
                'motorizado': bool(self._valor_formulario('has_motor') not in ('', '0')
                                   or (motor and motor not in ('0', 'sin'))),
                'sistema': self.system_id.code or '',
                'tela_permite_cenefa_entera': bool(self.fabric_id.permite_cenefa_entera),
                'tela_atravesable': bool(self.fabric_id and self.fabric_id.pierceable_type != 'no'),
                # Archivos de Safra «Tipos de corte tela» (26-oct).
                'tipo_corte': self._corte_tela()['tipo']}
        cenefa = self._corte_cenefa_tela(maps)
        base.update(cenefa_en_tela=cenefa['en_tela'], tipo_corte_cenefa=cenefa['tipo'],
                    ancho_cenefa=cenefa['ancho_cenefa'])
        # Los campos de Referencias que el sistema no tiene valen 0 (la misma
        # fórmula sirve en todos los sistemas).
        for code in self.env['safra.field'].sudo().search(
                [('field_type', '=', 'ref_categoria')]).mapped('code'):
            base['ancho_max_%s' % code] = 0.0
        for m in maps.filtered(lambda x: x.field_id.field_type == 'ref_categoria'):
            lineas = self._lineas_opcion(m.field_id, self._valor_formulario(m.field_id.code))
            productos = lineas.mapped('product_tmpl_id')
            # Sin U_AnchoMax digitado en ninguno llega vacío (False).
            base['ancho_max_%s' % m.field_id.code] = False if productos and all(
                vacio_en(p, 'safra_u_ancho_max') for p in productos) else max(
                [p.safra_u_ancho_max or 0.0 for p in productos] or [0.0])
        return dict(base, **variables_formulario(self._campos_formula(), base))

    def _formulas_opciones(self):
        """Por campo del sistema con opciones que tienen fórmulas:
        - opciones: valores que se ofrecen («Se ofrece si…»; las de «Solo
          aviso» nunca);
        - auto: la opción que se elige sola («Se elige sola si…»);
        - avisos: los mensajes al cliente (de la opción que se eligió sola
          o de las de «Solo aviso» cuya fórmula da verdadero);
        - maximos: alto máximo de la cortina con cada opción que tiene
          Consumo del dobladillo (revisión 30-oct).
        Una fórmula que falla no oculta ni elige la opción (queda en el log)."""
        self.ensure_one()
        vacio = {'opciones': {}, 'auto': {}, 'avisos': {}, 'maximos': {}}
        if not self.system_id:
            return vacio
        maps = self.env['safra.system.field'].sudo().search([
            ('system_id', '=', self.system_id.id), ('field_id.active', '=', True)])
        ctx = None

        def evaluar(opt, campo, code):
            try:
                return bool(evaluar_formula(opt[campo], dict(
                    ctx, alto_maximo_opcion=self._alto_maximo_dobladillo(opt.consumo_dobladillo)))[0])
            except Exception as e:
                _logger.warning('Fórmula de la opción %s (%s) con error: %s', opt.name, code, e)
                return None

        for m in maps:
            opciones = m.option_ids or m.field_id.option_ids
            if not any(o.formula or o.auto_formula or o.solo_aviso for o in opciones):
                continue
            if ctx is None:
                ctx = self._ctx_formulas_opciones(maps)
            code = m.field_id.code
            ofrecidas, avisos = [], []
            for opt in opciones:
                ok = evaluar(opt, 'formula', code) if opt.formula else True
                if opt.solo_aviso:
                    if ok and opt.formula and opt.aviso:
                        avisos.append(opt.aviso)
                    continue
                if ok is not False:
                    ofrecidas.append(opt.value)
                if opt.auto_formula and code not in vacio['auto'] and evaluar(opt, 'auto_formula', code):
                    vacio['auto'][code] = opt.value
                    if opt.aviso:
                        avisos.insert(0, opt.aviso)
            vacio['opciones'][code] = ofrecidas
            # Revisión 30-oct: alto máximo de cada dobladillo, para la lista.
            maximos = {o.value: self._alto_maximo_dobladillo(o.consumo_dobladillo)
                       for o in opciones if o.consumo_dobladillo > 0}
            if maximos:
                vacio['maximos'][code] = maximos
            if avisos:
                vacio['avisos'][code] = avisos
        return vacio

    def _lineas_opcion(self, field, valor):
        """Líneas de referencia que corresponden al valor elegido en un
        campo «Referencia (categoría)» (código de la línea, su id o
        'ref-<id>'). Puede haber varias si comparten código."""
        Color = self.env['safra.fabric.color'].sudo()
        valor = str(valor or '')
        if not valor or not field.ref_category_id:
            return Color
        if valor.startswith('ref-') and valor[4:].isdigit():
            return Color.browse(int(valor[4:])).exists()
        dom = [('fabric_id.category_id', '=', field.ref_category_id.id)]
        lineas = Color.search(dom + [('code', '=', valor)])
        if not lineas and valor.isdigit():
            lineas = Color.search(dom + [('id', '=', int(valor))])
        # Revisión 27-oct: con el código repetido en referencias de otros
        # sistemas (p. ej. 054328 en «Cenefas» y en «Cenefas en Tela»),
        # primero las que aplican al sistema de la persiana, como el portal.
        sistema = self.system_id
        if len(lineas) > 1 and sistema:
            aplica = lineas.filtered(
                lambda c: (not c.fabric_id.system_ids or sistema in c.fabric_id.system_ids)
                and (not c.system_ids or sistema in c.system_ids))
            lineas = aplica | lineas
        return lineas

    def _validaciones_15oct(self, add, rule):
        """Reunión 15-oct. Fila 68: el tubo (calculado o unificado) se
        bloquea si a uno de sus insumos de estructura le falta stock, y una
        opción con tubos marcados en el maestro (p. ej. el cabezal cuadrado,
        solo R8 y R16) no se puede elegir con otro tubo. Fila 50: una opción
        de una referencia con «Solo con estas telas» solo sirve con ellas."""
        self.ensure_one()
        system = self.system_id
        if not system:
            return
        Rule = self.env['safra.structure.rule'].sudo()
        tubo = rule.tubo if rule else ''
        if tubo:
            faltan = Rule._insumos_sin_stock(tubo)
            if faltan:
                add('V_TUBO_SIN_INSUMO', 'error',
                    'E20038: El tubo {tubo} no está disponible: no hay '
                    'existencias de {insumos}.',
                    tubo=tubo, insumos=', '.join(faltan.mapped('display_name')))
        telas = self.fabric_id | self.fabric_id_2
        maps = self.env['safra.system.field'].sudo().search([
            ('system_id', '=', system.id), ('field_id.active', '=', True),
            ('field_id.field_type', '=', 'ref_categoria')])
        for m in maps:
            field = m.field_id
            lineas = self._lineas_opcion(field, self._valor_campo(field.code))
            if not lineas:
                continue
            campo = m.label_override or field.name
            opcion = lineas[0].etiqueta or lineas[0].name or lineas[0].code
            # Reunión 28-oct: las telas no compatibles de la línea y las de
            # su referencia.
            if not any(l._sirve_con_telas(telas) for l in lineas):
                add('V_OPCION_TELA', 'error',
                    'E20039: La opción «{opcion}» de {campo} no aplica con la '
                    'tela {tela}.', opcion=opcion, campo=campo,
                    tela=', '.join(telas.mapped('name')))
            nombre = (tubo or '').strip().lower()
            if nombre and all(
                    l.product_tmpl_id.safra_tubo_ids and nombre not in [
                        (t.name or '').strip().lower() for t in l.product_tmpl_id.safra_tubo_ids]
                    for l in lineas):
                add('V_OPCION_TUBO', 'error',
                    'E20040: La opción «{opcion}» de {campo} no se fabrica con '
                    'el tubo {tubo}.', opcion=opcion, campo=campo, tubo=tubo)

    def _validaciones_sprint15(self, add, attrs, w, lamas):
        self.ensure_one()
        system = self.system_id
        if not system:
            return
        maps = self.env['safra.system.field'].sudo().search([
            ('system_id', '=', system.id), ('field_id.active', '=', True)])
        codigos = set(maps.mapped('field_id.code'))

        # E20033 (filas 97 y 112): la opción elegida depende de otro campo
        # (p. ej. «Centro frente» solo con la apertura Centro).
        for m in maps:
            field = m.field_id
            if field.field_type not in ('selection', 'ref_categoria'):
                continue
            valor = self._valor_campo(field.code)
            if not valor:
                continue
            opt = (m.option_ids or field.option_ids).filtered(lambda o: o.value == valor)[:1]
            if not opt or not opt.depends_field_id:
                continue
            padre = opt.depends_field_id
            valor_padre = self._valor_campo(padre.code)
            eti, ref = self._etiqueta_y_ref(padre, valor_padre, maps)
            if not self._depende_ok(valor_padre, opt.depends_value, eti=eti, ref=ref):
                padre_map = maps.filtered(lambda x: x.field_id == padre)[:1]
                add('V_OPCION_DEPENDENCIA', 'error',
                    'E20033: La opción «{opcion}» de {campo} no aplica con lo '
                    'elegido en {padre}.',
                    opcion=opt.name, campo=m.label_override or field.name,
                    padre=padre_map.label_override or padre.name)

        # E20037 (fila 118): la opción elegida tiene fórmula y no aplica con
        # estas medidas (p. ej. un dobladillo que no cabe en el rollo).
        formulas = self._formulas_opciones()
        for code, ofrecidas in formulas['opciones'].items():
            valor = self._valor_campo(code)
            # Ajustes 20 y 22-oct: si una opción se elige sola (p. ej. riel o
            # cenefa dividida por el ancho), el campo debe llevarla.
            auto = formulas['auto'].get(code)
            m = maps.filtered(lambda x: x.field_id.code == code)[:1]
            if auto and valor != auto and self._campo_visible(m, maps):
                opt = (m.option_ids or m.field_id.option_ids).filtered(lambda o: o.value == auto)[:1]
                add('V_OPCION_AUTO', 'error',
                    'E20042: Con estas medidas {campo} debe ser «{opcion}». {aviso}',
                    campo=m.label_override or m.field_id.name, opcion=opt.name or auto,
                    aviso=opt.aviso or '')
                continue
            if valor and valor not in ofrecidas:
                opt = (m.option_ids or m.field_id.option_ids).filtered(lambda o: o.value == valor)[:1]
                add('V_OPCION_FORMULA', 'error',
                    'E20037: La opción «{opcion}» de {campo} no aplica con estas '
                    'medidas (alto {alto} m, ancho del rollo {rollo} m).',
                    opcion=opt.name or valor, campo=m.label_override or m.field_id.name,
                    alto=self.height or 0, rollo=round(self._ancho_rollo(), 3))

        # E20034 (fila 97): con 7 o 12 telos la Posición Telo Fijo es
        # obligatoria (cambia el alto de corte).
        if 'posicion_telo' in codigos and lamas in (7, 12) \
                and not self._valor_campo('posicion_telo'):
            add('V_TELO_FIJO', 'error',
                'E20034: Con {lamas} telos debe indicar la Posición Telo Fijo.',
                lamas=lamas)

        # E20035 (fila 109): el bolsillo solo en telas que lo permiten.
        if self.bolsillo_size and self.fabric_id and not self.fabric_id.permite_bolsillo:
            add('V_BOLSILLO_TELA', 'error',
                'E20035: La tela {tela} no permite bolsillo; quite el Tamaño '
                'del bolsillo o elija otra tela.', tela=self.fabric_id.name)

        # E20036 (fila 112): segmentos del Riel curvo de las cortinas.
        plano = attrs.get('tipoplano_cortina')
        if plano and 'segmento_2' in codigos:
            def num(code):
                try:
                    return float(str(attrs.get(code) or 0).replace(',', '.'))
                except (TypeError, ValueError):
                    return 0.0

            def curva(code):
                valor = attrs.get(code)
                return num(code + '_m') if valor == 'mas' else num(code)

            # Reunión 22-oct (fila 101): en el Plano U, Segmento 1 (curva
            # izquierda) + Segmento 2 (tramo) + Segmento 3 (curva derecha).
            partes = self._partes_riel_curvo(plano, num, curva)
            plano_opt = maps.filtered(lambda x: x.field_id.code == 'tipoplano_cortina')[:1]
            nombre_plano = ((plano_opt.option_ids or plano_opt.field_id.option_ids)
                            .filtered(lambda o: o.value == plano)[:1].name or plano)
            if partes is not None and not all(partes):
                add('V_SEGMENTOS_CORTINA', 'error',
                    'E20036: Complete los segmentos del Riel curvo ({plano}).',
                    plano=nombre_plano)
            elif partes and len(partes) > 1 and w and abs(sum(partes) - w) > 0.005:
                add('V_SEGMENTOS_CORTINA', 'error',
                    'E20036: Los segmentos del Riel curvo ({plano}) suman '
                    '{suma} m y el ancho es {ancho} m: deben sumar el ancho total.',
                    plano=nombre_plano, suma=round(sum(partes), 3), ancho=w)

    @api.model
    def _partes_riel_curvo(self, plano, num, curva):
        """Medidas que suman el ancho en cada plano del Riel curvo (el
        portal hace la misma cuenta mientras se digita)."""
        return {
            'LID': [num('segmento_1'), num('segmento_2')],
            'U': [curva('segmento_1_u'), num('segmento_2'), curva('segmento_3')],
            'LI': [curva('curva_izquierda')],
            'LD': [curva('curva_derecha')],
        }.get(plano)

    @api.model
    def _riel_de_combinacion(self, config):
        if config.get('codigo_condicion') == 'riel_velcrado':
            return 'velcrado'
        return config.get('canales') or None

    @api.model
    def _riel_nombre(self, info):
        return 'Riel Velcrado' if info == 'velcrado' else 'riel de %s vías' % info

    def _system_field_codes(self):
        """Códigos de campo configurados para el sistema de la línea."""
        self.ensure_one()
        if not self.system_id:
            return set()
        maps = self.env['safra.system.field'].sudo().search([
            ('system_id', '=', self.system_id.id)])
        return set(maps.mapped('field_id.code'))
