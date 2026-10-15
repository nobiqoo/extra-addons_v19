# -*- coding: utf-8 -*-
import io
import logging
import re

from markupsafe import Markup, escape

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


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

MANDO_SELECTION = [
    ('derecha', 'Derecha'),
    ('izquierda', 'Izquierda'),
]

ATRAVESAR_SELECTION = [
    ('predeterminado', 'Predeterminado'),
    ('atravesar', 'Atravesar Tela'),
]

COVER_LIGHT_SELECTION = [
    ('sin', 'Sin Cenefa'),
    ('un_lateral_5cm', 'Un Lateral 5cm'),
    ('dos_laterales_5cm', 'Dos Laterales 5cm'),
    ('tres_laterales_5cm', 'Tres Laterales 5cm'),
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

ESCUADRAS_SELECTION = [
    ('7_5', 'Escuadra 7.5 cm'),
    ('9', 'Escuadra 9 cm'),
    ('10_5', 'Escuadra 10.5 cm'),
    ('12', 'Escuadra 12 cm'),
    ('15', 'Escuadra 15 cm'),
]

BOLSILLO_SELECTION = [
    ('5', '5 cm'),
    ('8', '8 cm'),
    ('10', '10 cm'),
]


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
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('pending_design', 'Pendiente aprobación diseño'),
        ('design_approved', 'Diseño aprobado'),
        ('confirmed', 'Confirmada'),
        ('cancelled', 'Cancelada'),
    ], string='Estado', default='draft', tracking=True)
    line_ids = fields.One2many('safra.quote.line', 'quote_id', string='Líneas')
    note = fields.Text(string='Notas internas')
    # Revisión sprint 1 (f138): Safra Express aplica al PEDIDO completo,
    # no a cada persiana.
    safra_express = fields.Boolean(string='¿Solicita Safra Express?', tracking=True)

    currency_id = fields.Many2one(
        'res.currency', string='Moneda',
        related='partner_id.company_id.currency_id', store=True,
        default=lambda self: self.env.company.currency_id,
    )
    amount_total = fields.Float(string='Total', compute='_compute_amount_total', store=True)
    # Puntos 10-11 (OBS REU TELAS): cada diseño personalizado genera un
    # ticket de Helpdesk asociado a la cotización.
    design_ticket_count = fields.Integer(
        string='Tickets de diseño', compute='_compute_design_ticket_count')

    @api.depends('line_ids.price_total')
    def _compute_amount_total(self):
        for rec in self:
            rec.amount_total = sum(rec.line_ids.mapped('price_total'))

    def _compute_design_ticket_count(self):
        Ticket = self.env['helpdesk.ticket'].sudo()
        for rec in self:
            rec.design_ticket_count = Ticket.search_count([
                ('safra_quote_id', '=', rec.id)]) if rec.id else 0

    def action_view_design_tickets(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Tickets de diseño',
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
        issues = Line._validate_order([l.copy_data()[0] for l in lines])
        cfg = self.env['safra.validation.rule'].sudo().get_config('V_REVALIDACION') or {}
        if cfg and not cfg.get('active', True):
            return issues
        user = self.user_id or self.env.user
        Design = self.env['safra.design'].sudo().with_context(active_test=False)
        for n, line in enumerate(lines, start=1):
            motivos = []
            system = line.system_id.sudo()
            if system and (not system.active or not system._visible_for_user(user)):
                motivos.append('el sistema %s ya no está disponible para %s'
                               % (system.name, user.name))
            if line.fabric_id and not line.fabric_id.active:
                motivos.append('la referencia %s fue inactivada' % line.fabric_id.name)
            if line.color_id and not line.color_id.active:
                motivos.append('el color %s fue inactivado' % line.color_id.name)
            elif line.color_id and not line.color_id.sudo()._is_available_for_portal():
                motivos.append('el color %s ya no tiene existencias suficientes'
                               % line.color_id.name)
            if line.custom_design and line.custom_design != 'OTROS':
                design = Design.search([('code', '=', line.custom_design)], limit=1)
                if design and not design.active:
                    motivos.append('el diseño %s ya no está disponible' % design.code)
            for motivo in motivos:
                issues.append({
                    'line': n, 'code': 'V_REVALIDACION',
                    'severity': cfg.get('severity') or 'error',
                    'message': cfg.get('message') or
                    'E20025: No se puede continuar: %s.' % motivo,
                })
        return issues

    # Estados de una cotización que todavía no inicia el flujo.
    SIN_CONFIRMAR = ('draft', 'pending_design', 'design_approved')

    def _anular_si_invalida(self):
        """Pendiente 4 (Safra, 5-oct): una cotización SIN CONFIRMAR que al
        revalidarse ya no cumple se ANULA, y el motivo queda en su
        historial. Devuelve {cotización: errores} de las anuladas."""
        anuladas = {}
        for quote in self.filtered(lambda q: q.state in self.SIN_CONFIRMAR):
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

    def action_confirm(self):
        anuladas = self._anular_si_invalida()
        (self - self.browse([q.id for q in anuladas])).write({'state': 'confirmed'})
        if anuladas:
            detalle = '\n'.join(
                '%s · Persiana %s: %s' % (q.name, e['line'], e['message'])
                for q, errores in anuladas.items() for e in errores)
            return {
                'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {
                    'type': 'danger', 'sticky': True,
                    'title': 'Cotización anulada: ya no cumple las condiciones',
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
        self.write({'state': 'draft'})

    def _update_design_state(self):
        """Estado según la aprobación del área de diseño: con diseños sin
        aprobar queda «Pendiente aprobación diseño»; cuando el diseñador
        aprueba todos desde sus tickets pasa a «Diseño aprobado»."""
        for quote in self:
            design_lines = quote.line_ids.filtered('custom_design')
            if not design_lines or quote.state in ('confirmed', 'cancelled'):
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
    mando_position = fields.Selection(MANDO_SELECTION, string='Posición del mando', default='derecha')

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

    # Impresión de gran formato: por debajo de 40 DPI efectivos la imagen se
    # pixela a distancia normal de observación; 80+ es calidad óptima.
    DESIGN_DPI_MIN = 40
    DESIGN_DPI_GOOD = 80

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
        try:
            from PIL import Image
            img = Image.open(io.BytesIO(data))
            px_w, px_h = img.size
        except Exception:
            return ('No fue posible leer la imagen para analizar sus '
                    'dimensiones; el área de diseño la validará '
                    'manualmente.'), True
        w, h = self.width or 0.0, self.height or 0.0
        parts = ['Imagen de %d × %d px.' % (px_w, px_h)]
        warning = False
        if w and h:
            # DPI efectivo = píxeles / pulgadas impresas (1 m = 39.37 in)
            dpi = min(px_w / (w * 39.3701), px_h / (h * 39.3701))
            parts.append('Resolución efectiva para %.2f × %.2f m: %.0f DPI.'
                         % (w, h, dpi))
            if dpi < self.DESIGN_DPI_MIN:
                warning = True
                parts.append('ADVERTENCIA: resolución baja para el tamaño de '
                             'la persiana (mínimo recomendado %d DPI); la '
                             'impresión puede verse pixelada.'
                             % self.DESIGN_DPI_MIN)
            elif dpi < self.DESIGN_DPI_GOOD:
                parts.append('Resolución aceptable (recomendado %d DPI o '
                             'más para calidad óptima).' % self.DESIGN_DPI_GOOD)
            else:
                parts.append('Resolución óptima para impresión.')
            ratio_img = px_w / px_h if px_h else 0
            ratio_blind = w / h
            if ratio_blind and abs(ratio_img - ratio_blind) / ratio_blind > 0.10:
                warning = True
                parts.append('ADVERTENCIA: la proporción de la imagen '
                             '(%.2f) no coincide con la de la persiana '
                             '(%.2f); el diseño se recortará o deformará al '
                             'ajustarlo.' % (ratio_img, ratio_blind))
        return '\n'.join(parts), warning

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
            self.env['ir.attachment'].sudo().create({
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
    cover_light_profile = fields.Selection(COVER_LIGHT_SELECTION, string='Perfil Cover Light', default='sin')
    coverlight_felpa = fields.Boolean(string='¿Coverlight con Felpa?')
    coverlight_45 = fields.Boolean(string='¿Coverlight a 45°?')

    # === CORDÓN / CADENA ===
    extra_chain = fields.Float(string='Extra Cadena / Cordón (m)', digits=(12, 2))

    # === OTRAS OPCIONES ===
    enclosed = fields.Boolean(string='Persiana Encajonada')
    escuadras = fields.Selection(ESCUADRAS_SELECTION, string='Escuadras')
    bolsillo_size = fields.Selection(BOLSILLO_SELECTION, string='Tamaño del bolsillo')
    safra_express = fields.Boolean(string='Safra Express')
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
        """Valida la línea; lista de dicts {code, severity, message}."""
        self.ensure_one()
        Config = self.env['safra.validation.rule'].sudo()
        results = []

        def add(code, severity, message, **fmt):
            cfg = Config.get_config(code) or {}
            if cfg and not cfg.get('active', True):
                return
            # Apunte 23-sep: si la regla tiene «Condición (código)», esa
            # condición REEMPLAZA al chequeo interno del motor — se evalúa
            # en el bloque genérico y aquí no se emite nada.
            if cfg.get('has_code'):
                return
            msg = cfg.get('message') or message
            try:
                msg = msg.format(**fmt)
            except (KeyError, IndexError):
                pass
            results.append({
                'code': code,
                'severity': cfg.get('severity') or severity,
                'message': msg,
            })

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
        has_structure = system and bool(Rule.search_count([('system_ids', 'in', system.id)]))
        # Sprint 1.3: la estructura considera el cabezal elegido (como el
        # portal) y la Unificación Mando (tubo mayor al calculado).
        rule = Rule.browse()
        if has_structure:
            rule = Rule.resolve(system, w, motorized=self.has_motor,
                                cabezal=self._cabezal_elegido()[0],
                                unificacion=attrs.get('unificacion_mando') or None)[1]
        if has_structure and w and not rule:
            add('V_ESTRUCTURA', 'error',
                'E13095: No se han identificado los componentes (tubo/mecanismo) '
                'para el ancho {ancho} m: está fuera de la tabla de estructura.',
                ancho=w)
        if rule:
            fabric = self.fabric_id
            peso_perfil = 0.0
            perfil_val = attrs.get('perfil') or attrs.get('perfil_sheer') or attrs.get('perfileria2')
            if perfil_val:
                opt = self.env['safra.field.option'].sudo().search([
                    ('field_id.code', 'in', ['perfil', 'perfileria2', 'perfil_sheer']),
                    ('value', '=', str(perfil_val)), ('peso_gm', '>', 0)], limit=1)
                peso_perfil = opt.peso_gm
            limits = rule.compute_limits(
                w, h,
                peso_tela=fabric.peso_gm2 or 0.0,
                grosor_tela=fabric.grosor_mm or 0.0,
                peso_perfil=peso_perfil,
                factor=system.weight_factor or 1.0)
            if limits.get('alto_ok') is False:
                add('V_ALTO_MAXIMO', 'error',
                    'E10004: Alto fuera de rango para la fabricación. El alto '
                    'máximo calculado para esta configuración es {alto_maximo} m.',
                    alto_maximo=limits['alto_maximo'])
            if limits.get('peso_ok') is False:
                requiere_motor = False
                if not self.has_motor and limits.get('peso_total'):
                    rule_motor = Rule.find_rule(system, w, motorized=True)
                    requiere_motor = bool(
                        rule_motor and rule_motor.carga_maxima
                        and limits['peso_total'] <= rule_motor.carga_maxima)
                if requiere_motor:
                    add('V_REQUIERE_MOTOR', 'error',
                        'E13095: Por la medida de la persiana y el peso de la '
                        'tela ({peso} g), la persiana debe ir motorizada.',
                        peso=limits['peso_total'])
                else:
                    add('V_PESO_MAXIMO', 'error',
                        'E13095: El peso calculado ({peso} g) supera la carga '
                        'máxima del mecanismo ({carga} g).',
                        peso=limits['peso_total'], carga=limits['carga_maxima'])
            # Proporción alto vs ancho (solo sistemas con tabla: enrollables).
            if w and h and h > w * 3:
                add('V_ALTO_3X_ANCHO', 'warning',
                    'W10005: La persiana tiene un alto mayor a 3 veces su ancho.')

        # --- Kit motorizado: control compatible y ancho mínimo motor ---
        if self.has_motor and self.motor and self.motor != '7':
            if w and w < 0.80:
                add('V_ANCHO_MIN_MOTOR', 'error',
                    'E13095: El ancho mínimo para una persiana motorizada es '
                    'de 0.80 m.')
            kit = rule._kit_for(self.motor) if rule else self.env['safra.motor.kit'].find_kit(self.motor, '')
            if kit and self.control and self.control not in ('0', 'sin'):
                allowed = [v.strip() for v in (kit.control_values or '').split(',') if v.strip()]
                if allowed and self.control not in allowed:
                    add('V_CONTROL_MOTOR', 'error',
                        'E13095: El control seleccionado no es compatible con '
                        'el motor «{motor}».', motor=kit.motor_name)

        # --- Localización obligatoria (salvo sistemas exentos) ---
        if not self.location and sys_code not in self._LOCATION_EXEMPT:
            add('V_LOCALIZACION', 'error',
                "E13095: Por favor ingrese un valor en el campo 'Localización'.")

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

        # --- Cenefa en tela con corte «Entera»: solo telas que lo permiten
        # (revisión sprint 1 f94; parametrizado en la referencia).
        if str(attrs.get('corte_cenefa') or '') == '2' and self.fabric_id \
                and not self.fabric_id.permite_cenefa_entera:
            add('V_CENEFA_ENTERA', 'error',
                'E20003: La tela seleccionada no permite el corte de cenefa '
                'entera; elija «Cenefa añadida» u otra tela.')

        # --- Diseño Impresión activo: debe elegirse el diseño (catálogo u
        # OTROS); el archivo se exige aparte en el submit (va como adjunto).
        if self.design_print and not self.custom_design:
            add('V_DISENO_SELECCION', 'error',
                'E20002: Elija el diseño a imprimir en el catálogo con '
                'imágenes, o marque «Diseño propio» para subir su imagen.')

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
            configs = self.env['safra.panel.track'].compute_configs(
                w, traslape, lamas, campos=self._campos_formula(), system=system)
            if not configs:
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
                    # de la combinación (N vías o Riel Velcrado).
                    permitido = self._riel_de_combinacion(elegida[0])
                    elegido = self._riel_tipo_info(attrs.get('riel_tipo'))
                    if permitido and elegido is not None and elegido != permitido:
                        add('V_PANEL_RIEL', 'error',
                            'E20029: Con {lamas} telos y apertura {apertura} la '
                            'combinación lleva {riel}; el Tipo de Riel elegido '
                            '({elegido}) no corresponde.',
                            lamas=lamas, apertura=elegida[0]['tipo_apertura'],
                            riel=self._riel_nombre(permitido),
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
        if self.fabric_id and self.fabric_id.pierceable_type == 'no' and w:
            rollo = 0.0
            if self.color_id and self.color_id.product_tmpl_id:
                rollo = self.color_id.product_tmpl_id.safra_u_ancho or 0.0
            if not rollo:
                anchos = [c.product_tmpl_id.safra_u_ancho or 0.0
                          for c in self.fabric_id.color_ids if c.product_tmpl_id]
                rollo = max(anchos) if anchos else 0.0
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
            rollo_atr = 0.0
            if self.color_id and self.color_id.product_tmpl_id:
                rollo_atr = self.color_id.product_tmpl_id.safra_u_ancho or 0.0
            if not rollo_atr:
                anchos = [c.product_tmpl_id.safra_u_ancho or 0.0
                          for c in self.fabric_id.color_ids if c.product_tmpl_id]
                rollo_atr = max(anchos) if anchos else 0.0
            if rollo_atr and w > rollo_atr and not self.acepta_atravesado:
                add('V_CORTE_ATRAVESADO', 'error',
                    'E20017: Con el ancho digitado ({ancho} m) la tela '
                    '{tela} se cortará atravesada (rollo de {rollo} m); '
                    'marque la aceptación del corte atravesado para '
                    'continuar.',
                    ancho=w, rollo=rollo_atr, tela=self.fabric_id.name)

        # --- Apunte 23-sep: validaciones configuradas POR CÓDIGO (estilo
        # reglas de nómina) — el funcional crea reglas nuevas sin
        # desarrollo escribiendo la condición en Configuración >
        # Validaciones. Un error en la expresión no rompe el portal: la
        # regla se ignora y queda en el log.
        from odoo.tools.safe_eval import safe_eval
        # Precalculados pesados para que las condiciones queden legibles.
        campos = self._system_field_codes()
        rollo_ctx = 0.0
        if self.color_id and self.color_id.product_tmpl_id:
            rollo_ctx = self.color_id.product_tmpl_id.safra_u_ancho or 0.0
        if not rollo_ctx and self.fabric_id:
            anchos_ctx = [c.product_tmpl_id.safra_u_ancho or 0.0
                          for c in self.fabric_id.color_ids if c.product_tmpl_id]
            rollo_ctx = max(anchos_ctx) if anchos_ctx else 0.0
        ap_raw_ctx = str(attrs.get('apertura') or '')
        es_motor_ctx = bool(self.has_motor) or bool(
            self.motor and self.motor not in ('0', 'sin'))
        max_ctx = self.env['safra.lamas.rule'].sudo().compute_max(
            system, w,
            {'1': 'derecha', '2': 'izquierda', '3': 'extremos',
             '4': 'centro'}.get(ap_raw_ctx, ap_raw_ctx),
            motorized=es_motor_ctx, campos=self._campos_formula()) if system else None
        suma_ctx = sum(_int(attrs.get('lamas_tela_%d' % n)) for n in range(1, 6))
        telas_ctx = []
        for n, _f in fabric_slots:
            if n == 1:
                fid_c, cid_c = self.fabric_id.id, self.color_id.id
            elif n == 2:
                fid_c, cid_c = self.fabric_id_2.id, self.color_id_2.id
            elif n == 3:
                fid_c, cid_c = self.fabric_id_3.id, self.color_id_3.id
            else:
                fid_c = _int(attrs.get('fabric_id_%d' % n))
                cid_c = str(attrs.get('color_id_%d' % n) or '')
            if fid_c and cid_c:
                telas_ctx.append((fid_c, str(cid_c)))
        ctx_vars = {
            'ancho': w, 'alto': h, 'cantidad': self.quantity or 0,
            'limites': dict(system._tech_limits(exhibition=bool(self.exhibition))) if system else
                       {'wmin': 0, 'wmax': 0, 'hmin': 0, 'hmax': 0},
            'atributos': dict(attrs),
            'tela': self.fabric_id, 'color': self.color_id,
            'sistema': sys_code or '',
            'con_motor': bool(self.has_motor),
            'alineado': bool(self.aligned),
            'exhibicion': bool(self.exhibition),
            'linea': self,
            # precalculados
            'campos': set(campos),
            'ancho_rollo': rollo_ctx,
            'maximo_lamas': max_ctx,
            'total_lamas': lamas,
            'suma_lamas': suma_ctx,
            'telas': telas_ctx,
        }
        for regla in Config.search([('condition_code', '!=', False),
                                    ('active', '=', True)]):
            try:
                if safe_eval(regla.condition_code.strip(), dict(ctx_vars)):
                    msg = regla.message or ('%s: condición configurada' % regla.code)
                    try:
                        msg = msg.format(**ctx_vars)
                    except (KeyError, IndexError, ValueError):
                        pass
                    results.append({'code': regla.code,
                                    'severity': regla.severity or 'error',
                                    'message': msg})
            except Exception:
                _logger.warning('Validación %s: error evaluando la condición',
                                regla.code, exc_info=True)

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
        Config = self.env['safra.validation.rule'].sudo()
        Fabric = self.env['safra.fabric'].sudo()

        def make(n, code, default_msg, severity):
            cfg = Config.get_config(code) or {}
            if cfg and not cfg.get('active', True):
                return None
            return {'line': n, 'code': code,
                    'severity': cfg.get('severity') or severity,
                    'message': cfg.get('message') or default_msg}

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
        Config = self.env['safra.validation.rule'].sudo()

        def make(n, code, default_msg):
            cfg = Config.get_config(code) or {}
            if cfg and not cfg.get('active', True):
                return None
            return {'line': n, 'code': code,
                    'severity': cfg.get('severity') or 'error',
                    'message': cfg.get('message') or default_msg}

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
        Config = self.env['safra.validation.rule'].sudo()

        def make(n, code, default_msg):
            cfg = Config.get_config(code) or {}
            if cfg and not cfg.get('active', True):
                return None
            return {'line': n, 'code': code,
                    'severity': cfg.get('severity') or 'error',
                    'message': cfg.get('message') or default_msg}

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
        Config = self.env['safra.validation.rule'].sudo()

        def make(n, code, default_msg):
            cfg = Config.get_config(code) or {}
            if cfg and not cfg.get('active', True):
                return None
            return {'line': n, 'code': code,
                    'severity': cfg.get('severity') or 'error',
                    'message': cfg.get('message') or default_msg}

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
        Config = self.env['safra.validation.rule'].sudo()
        Rule = self.env['safra.structure.rule'].sudo()

        def make(n, code, default_msg, severity):
            cfg = Config.get_config(code) or {}
            if cfg and not cfg.get('active', True):
                return None
            return {'line': n, 'code': code,
                    'severity': cfg.get('severity') or severity,
                    'message': cfg.get('message') or default_msg}

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
            largo = (w if atravesada else h) + (regla.aumento_tela if regla else 0.0)
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
    def _unificar_secuencias(self, lines_vals):
        """Sprint 1.3 (fila 73): en persianas con Mismo cabezal la
        Unificación Mando es obligatoria y automática: todas las de la
        secuencia van con el tubo MAYOR de la secuencia. Ajusta
        attribute_values['unificacion_mando'] en los mismos dicts (así se
        valida y se guarda con el tubo unificado)."""
        Rule = self.env['safra.structure.rule'].sudo()
        grupos = {}
        for vals in lines_vals:
            nombre = (vals.get('sequence_name') or '').strip().lower()
            if vals.get('same_header') and nombre and vals.get('system_id'):
                grupos.setdefault(nombre, []).append(vals)
        for grupo in grupos.values():
            bases, orden = [], []
            for vals in grupo:
                line = self.new({k: v for k, v in vals.items() if k in self._fields})
                system = line.system_id
                tubos = Rule.tubos_ordenados(system, motorized=line.has_motor)
                base = Rule.find_rule(system, line.width, motorized=line.has_motor,
                                      cabezal=line._cabezal_elegido()[0])
                bases.append(base.tubo if base else None)
                orden = tubos if len(tubos) > len(orden) else orden
            conocidos = [t for t in bases if t in orden]
            if not conocidos:
                continue
            mayor = max(conocidos, key=orden.index)
            for vals, base in zip(grupo, bases):
                attrs = dict(vals.get('attribute_values') or {})
                if base and base != mayor:
                    attrs['unificacion_mando'] = mayor
                else:
                    attrs.pop('unificacion_mando', None)
                vals['attribute_values'] = attrs
        return lines_vals

    def _validate_order(self, lines_vals, cross=True):
        """Motor de validaciones del pedido sobre líneas sin guardar (portal)
        o reconstruidas desde una cotización guardada (revalidación al
        confirmar). Usa registros new() sin tocar la base. Con cross=False
        solo valida cada línea por sí sola («Guardar línea»).
        Devuelve [{line: n, code, severity, message}]."""
        issues = []
        if cross:
            self._unificar_secuencias(lines_vals)
        for n, vals in enumerate(lines_vals, start=1):
            line = self.new({k: v for k, v in vals.items() if k in self._fields})
            for issue in line._validations():
                issue['line'] = n
                issues.append(issue)
        if cross:
            # Reglas cruzadas: secuencias (mismo cabezal), alineado, canal
            # compartido y segmentos de los planos.
            issues.extend(self._validate_sequences(lines_vals))
            issues.extend(self._validate_aligned(lines_vals))
            issues.extend(self._validate_canal_compartido(lines_vals))
            issues.extend(self._validate_controles(lines_vals))
            issues.extend(self._validate_planos(lines_vals))
            issues.extend(self._asignar_rollos(lines_vals)[0])
        return issues

    @api.model
    def _validate_planos(self, lines_vals):
        """Bloque 3 (acuerdos 17-sep y 28-sep): el Tipo de Plano une
        SEGMENTOS DE CABEZAL. Cada segmento es una secuencia («Mismo
        cabezal», agrupada por nombre: plano y segmento se eligen una sola
        vez para todas sus persianas) o una persiana individual con plano
        (plano y segmento en su propia línea). A nivel de pedido, cada plano
        usado debe traer todos sus segmentos (1..N según el catálogo), cada
        uno una sola vez; si falta alguno no se puede fabricar el cabezal."""
        Config = self.env['safra.validation.rule'].sudo()

        def make(n, default_msg):
            cfg = Config.get_config('V_PLANO_SEGMENTOS') or {}
            if cfg and not cfg.get('active', True):
                return None
            return {'line': n, 'code': 'V_PLANO_SEGMENTOS',
                    'severity': cfg.get('severity') or 'error',
                    'message': cfg.get('message') or default_msg}

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
        return opt.name or str(value)

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
        opts = self.env['safra.system.field.option'].sudo().search([
            ('system_field_id.system_id', '=', self.system_id.id),
            ('system_field_id.field_id.code', '=', 'riel_tipo')])
        if not any(isinstance(self._riel_info_desde_etiqueta(o.name), int) for o in opts):
            return None
        return self._riel_info_desde_etiqueta(self._riel_tipo_label(value))

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
