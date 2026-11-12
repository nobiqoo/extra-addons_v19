# -*- coding: utf-8 -*-
"""Pago por cuotas (tarea 11856): extiende el wizard "Generar recibos de
tarifas" existente (wk.fee.generate.wizard, wk_school_management).

Con "Pago por cuotas" activo se fuerza Plazo de pago = Personalizado y
Entrega = 1 (tal como pide el requerimiento), lo que hace que
generate_now() original genere un único wk.fee.slip con el valor total -sin
tocar esa lógica-. Encima de ese único recibo se construye la tabla de
amortización: un account.payment.term a medida (una línea fija por cuota,
la última como "percent"/100 para absorber el residual) que Odoo convierte
automáticamente en líneas contables ('display_type'='payment_term') por
fecha de vencimiento, todas dentro del mismo asiento de la única factura.
"""
import math

from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, _
from odoo.exceptions import UserError

PERIODICIDAD_DELTA = {
    'semanal': relativedelta(weeks=1),
    'quincenal': relativedelta(days=15),
    'mensual': relativedelta(months=1),
}


class FeeInstallmentPreviewLine(models.TransientModel):
    _name = 'wk.fee.installment.preview.line'
    _description = 'Línea de vista previa del acuerdo de pago por cuotas'
    _order = 'sequence'

    wizard_id = fields.Many2one(
        'wk.fee.generate.wizard', string='Asistente', ondelete='cascade')
    sequence = fields.Integer(string='#', default=10)
    name = fields.Char(string='Cuota', required=True)
    fecha_vencimiento = fields.Date(string='Fecha de vencimiento', required=True)
    valor = fields.Monetary(string='Valor', required=True, currency_field='currency_id')
    currency_id = fields.Many2one(related='wizard_id.currency_id', string='Moneda')


class FeeSlipGenerateWizard(models.TransientModel):
    _inherit = 'wk.fee.generate.wizard'

    # Incidencia PT11849 (1): "Plazo de pago" no traía ningún valor por
    # defecto -el requerimiento (2.1) pide que arranque en Personalizado/1,
    # que es justamente lo que ya fuerza _onchange_pago_por_cuotas cuando el
    # check está activo (wk.fee.generate.wizard.get_total_periods trata
    # 'custom' + installment=1 como "un único período", es decir, un único
    # recibo). El usuario sigue pudiendo cambiarlo a Mensual/Trimestral/
    # Anual si lo necesita.
    payment_term = fields.Selection(default='custom')
    installment = fields.Integer(default=1)

    currency_id = fields.Many2one(
        'res.currency', string='Moneda',
        default=lambda self: self.env.company.currency_id)
    pago_por_cuotas = fields.Boolean(string='Pago por cuotas')
    monto_inicial = fields.Monetary(string='Monto inicial', currency_field='currency_id')
    descuento_beneficio = fields.Monetary(
        string='Descuento por cupón', compute='_compute_beneficio',
        currency_field='currency_id',
        help="Descuento que dará el código de cupón/beneficio dejado "
             "pendiente en la inscripción. Se resta del monto a pagar antes "
             "de armar la tabla de cuotas, para que la suma de las cuotas "
             "coincida con lo que realmente se factura.")
    aviso_beneficio = fields.Char(
        string='Aviso del cupón', compute='_compute_beneficio')
    monto_neto = fields.Monetary(
        string='Total a financiar', compute='_compute_beneficio',
        currency_field='currency_id')
    valor_pendiente = fields.Monetary(
        string='Valor pendiente', compute='_compute_valor_pendiente',
        currency_field='currency_id')
    numero_abonos = fields.Integer(string='Número de abonos', default=1)
    fecha_primer_abono = fields.Date(string='Fecha primer abono')
    periodicidad = fields.Selection([
        ('semanal', 'Semanal'),
        ('quincenal', 'Quincenal'),
        ('mensual', 'Mensual'),
    ], string='Periodicidad', default='mensual')
    preview_line_ids = fields.One2many(
        'wk.fee.installment.preview.line', 'wizard_id', string='Vista previa de cuotas')

    def _get_simulated_slip_lines(self):
        """Líneas ``(producto, tarifa)`` del único recibo que generará
        generate_now() con Pago por cuotas (Personalizado/1): los conceptos
        únicos aún no pagados más los recurrentes completos."""
        self.ensure_one()
        enrollment = self.enrollment_id
        paid_products = enrollment.fee_slip_ids.filtered(
            lambda s: s.state == 'paid').mapped('fee_slip_line_ids.product_id')
        lines = []
        for summary in enrollment.fee_summary_ids:
            if summary.frequency == 'one':
                if summary.product_id in paid_products:
                    continue
                fee = math.ceil(summary.fee)
            else:
                fee = summary.fee
            if fee > 0:
                lines.append((summary.product_id, fee))
        return lines

    @api.depends(
        'pago_por_cuotas', 'amount_to_pay', 'enrollment_id',
        'enrollment_id.codigo_beneficio_pendiente')
    def _compute_beneficio(self):
        for wizard in self:
            descuento = 0.0
            aviso = False
            codigo = wizard.enrollment_id.codigo_beneficio_pendiente
            if wizard.pago_por_cuotas and codigo:
                lines = wizard._get_simulated_slip_lines()
                try:
                    result = self.env['wk.fee.benefit']._compute_benefit(
                        codigo, lines, sum(fee for _p, fee in lines))
                    descuento = result['amount']
                except UserError as e:
                    aviso = str(e)
            wizard.descuento_beneficio = descuento
            wizard.aviso_beneficio = aviso
            wizard.monto_neto = (wizard.amount_to_pay or 0.0) - descuento

    @api.depends('amount_to_pay', 'monto_inicial', 'descuento_beneficio')
    def _compute_valor_pendiente(self):
        for wizard in self:
            wizard.valor_pendiente = (
                (wizard.amount_to_pay or 0.0) - (wizard.descuento_beneficio or 0.0)
                - (wizard.monto_inicial or 0.0))

    @api.onchange('pago_por_cuotas')
    def _onchange_pago_por_cuotas(self):
        if self.pago_por_cuotas:
            self.payment_term = 'custom'
            self.installment = 1
            if not self.fecha_primer_abono:
                self.fecha_primer_abono = fields.Date.context_today(self)

    @api.onchange(
        'monto_inicial', 'numero_abonos', 'fecha_primer_abono', 'periodicidad',
        'amount_to_pay', 'descuento_beneficio')
    def _onchange_recalcular_preview(self):
        if self.pago_por_cuotas:
            self._rebuild_preview_lines()

    def _rebuild_preview_lines(self):
        self.ensure_one()
        self.preview_line_ids = [(5, 0, 0)]
        lines = []
        currency = self.currency_id
        if self.monto_inicial and not (currency and currency.is_zero(self.monto_inicial)):
            # Sin monto inicial no hay "Cuota inicial" que mostrar: una línea
            # de vencimiento en $0 es una fila sin sentido contable, y Odoo la
            # descarta en silencio al publicar la factura (deja de generar
            # esa línea de vencimiento), lo que desalinearía el emparejamiento
            # posicional con las demás cuotas en _create_installment_plan.
            lines.append((0, 0, {
                'sequence': 0,
                'name': _('Cuota inicial'),
                'fecha_vencimiento': fields.Date.context_today(self),
                'valor': self.monto_inicial,
            }))
        n = self.numero_abonos or 0
        if n > 0 and self.fecha_primer_abono:
            pendiente = self.valor_pendiente
            raw = pendiente / n
            delta = PERIODICIDAD_DELTA.get(self.periodicidad, relativedelta(months=1))
            amounts = [math.ceil(raw)] * (n - 1)
            amounts.append(pendiente - sum(amounts))
            for i, amount in enumerate(amounts):
                lines.append((0, 0, {
                    'sequence': i + 1,
                    'name': _('Abono %s', i + 1),
                    'fecha_vencimiento': self.fecha_primer_abono + delta * i,
                    'valor': amount,
                }))
        self.preview_line_ids = lines

    def _check_installment_plan(self):
        self.ensure_one()
        if self.monto_inicial > self.monto_neto:
            raise UserError(_(
                'El monto inicial no puede ser superior al monto total a pagar.'))
        if self.numero_abonos <= 0:
            raise UserError(_('El número de abonos debe ser mayor a cero.'))
        if not self.preview_line_ids:
            raise UserError(_('No hay cuotas generadas para el acuerdo de pago.'))

        # Comparar contra el orden de secuencia (Cuota inicial=0, Abono 1=1,
        # ...) y no solo "distintas entre sí": si el usuario elige una fecha
        # de primer abono anterior a hoy, las fechas podrían ser todas
        # distintas y aun así quedar en un orden distinto al de las cuotas
        # -la Cuota inicial (fecha de hoy) dejaría de ser la primera-, y dos
        # cuotas en la misma fecha colapsan en una sola línea contable sin
        # aviso (Odoo indexa las líneas de vencimiento solo por fecha).
        lines_by_seq = self.preview_line_ids.sorted('sequence')
        fechas = lines_by_seq.mapped('fecha_vencimiento')
        if len(set(fechas)) != len(fechas) or fechas != sorted(fechas):
            raise UserError(_(
                'Las fechas de las cuotas deben ser estrictamente crecientes, '
                'distintas entre sí, y la Cuota inicial debe ser la fecha más '
                'temprana (no se admite una fecha de primer abono anterior a '
                'hoy).'))

        currency = self.currency_id
        # preview_line_ids ya incluye la "Cuota inicial" como su primera fila
        # (valor = monto_inicial): no sumarlo aparte.
        suma = sum(self.preview_line_ids.mapped('valor'))
        if not currency.is_zero(suma - self.monto_neto):
            raise UserError(_(
                'La suma del monto inicial y los abonos (%(suma)s) debe ser '
                'exactamente igual al monto total a pagar (%(total)s).',
                suma=suma, total=self.monto_neto))

    def _build_payment_term(self, fee_slip):
        self.ensure_one()
        lines = self.preview_line_ids.sorted('fecha_vencimiento')
        line_vals = []
        today = fields.Date.context_today(self)
        for index, line in enumerate(lines):
            is_last = index == len(lines) - 1
            nb_days = (line.fecha_vencimiento - today).days
            if is_last:
                line_vals.append((0, 0, {
                    'value': 'percent',
                    'value_amount': 100.0,
                    'nb_days': max(nb_days, 0),
                    'delay_type': 'days_after',
                }))
            else:
                line_vals.append((0, 0, {
                    'value': 'fixed',
                    'value_amount': line.valor,
                    'nb_days': max(nb_days, 0),
                    'delay_type': 'days_after',
                }))
        term = self.env['account.payment.term'].create({
            'name': _('Cuotas - %s', fee_slip.name),
            'line_ids': line_vals,
        })
        return term

    def _create_installment_plan(self, fee_slip, invoice):
        self.ensure_one()
        lines = self.preview_line_ids.sorted('fecha_vencimiento')
        term_lines = invoice.line_ids.filtered(
            lambda l: l.display_type == 'payment_term').sorted('date_maturity')
        if len(term_lines) != len(lines):
            raise UserError(_(
                'No fue posible emparejar las cuotas con las líneas contables '
                'de vencimiento de la factura (%(cuotas)s cuotas, %(lineas)s '
                'líneas contables). Revise que las fechas de las cuotas sean '
                'todas distintas.', cuotas=len(lines), lineas=len(term_lines)))

        plan = self.env['wk.fee.installment.plan'].create({
            'enrollment_id': self.enrollment_id.id,
            'fee_slip_id': fee_slip.id,
            'monto_inicial': self.monto_inicial,
            'numero_abonos': self.numero_abonos,
            'periodicidad': self.periodicidad,
        })
        for preview_line, move_line in zip(lines, term_lines):
            self.env['wk.fee.installment.line'].create({
                'plan_id': plan.id,
                'sequence': preview_line.sequence,
                'name': preview_line.name,
                'fecha_vencimiento': preview_line.fecha_vencimiento,
                # 'valor_programado' debe ser el monto REAL de la línea
                # contable de vencimiento (move_line.amount_currency), no lo
                # que el usuario tecleó en la vista previa (preview_line.
                # valor): si entre armar la vista previa y facturar se aplicó
                # un Beneficio/cupón pendiente (_apply_pending_benefit_code,
                # ANTES de _create_invoices en este mismo método), la última
                # cuota (value='percent'/100, absorbe el residual) factura
                # por menos de lo tecleado -usar el valor tecleado mostraría
                # una cuota que nunca se cobrará-.
                'valor_programado': move_line.amount_currency,
                'move_line_id': move_line.id,
            })
        return plan

    def _apply_pending_benefit_code(self, fee_slip):
        """Código de beneficio/cupón dejado pendiente por el botón "Código de
        cupón" de la Inscripción (fee_benefit_wizard.py) antes de que
        existiera ningún recibo sobre el cual aplicarlo."""
        codigo = self.enrollment_id.codigo_beneficio_pendiente
        if codigo and fee_slip:
            self.env['wk.fee.benefit'].apply_benefit(fee_slip, codigo)
            self.enrollment_id.codigo_beneficio_pendiente = False

    def _check_no_pending_benefit_loss(self):
        """Antes de (re)generar recibos: wk.fee.generate.wizard.generate_now()
        (Webkul, wk_school_management/wizard/fee_slip_wizard.py:128) borra
        TODOS los recibos sin pagar del alumno (``unpaid_slips.unlink()``)
        sin revisar si alguno ya tiene un Beneficio/cupón aplicado
        (wk.fee.discount.log, ``ondelete='cascade'``) -el recibo y su
        beneficio desaparecen juntos, en silencio, sin ningún aviso-.

        Bloquea la generación en ese caso para que el usuario decida
        (facturar ese recibo primero, o quitar el beneficio a propósito) en
        vez de perder el descuento sin darse cuenta (hallazgo real: al
        aplicar un código de cupón sobre un recibo sin facturar y luego
        generar un nuevo acuerdo de pago por cuotas, el recibo con el
        beneficio se borraba y el nuevo se creaba a precio completo).
        """
        unpaid_slips = self.enrollment_id.fee_slip_ids.filtered(lambda s: s.state != 'paid')
        con_beneficio = unpaid_slips.filtered(
            lambda s: self.env['wk.fee.discount.log'].search_count([('fee_slip_id', '=', s.id)]))
        if con_beneficio:
            raise UserError(_(
                'El recibo %(recibo)s ya tiene un Beneficio/cupón aplicado y '
                'todavía no tiene factura. Generar nuevos recibos de tarifa '
                'eliminaría ese recibo junto con el beneficio ya aplicado. '
                'Facture ese recibo primero, o quite el beneficio antes de '
                'continuar.', recibo=', '.join(con_beneficio.mapped('name'))))

    def generate_now(self):
        self._check_no_pending_benefit_loss()
        if not self.pago_por_cuotas:
            res = super().generate_now()
            fee_slip = self.enrollment_id.fee_slip_ids.sorted('id', reverse=True)[:1]
            self._apply_pending_benefit_code(fee_slip)
            return res

        self.payment_term = 'custom'
        self.installment = 1
        self._check_installment_plan()

        super().generate_now()
        fee_slip = self.enrollment_id.fee_slip_ids.sorted('id', reverse=True)[:1]
        if not fee_slip:
            raise UserError(_('No se generó ningún recibo de tarifa para el acuerdo de pago.'))

        # Numeracion del recibo (2.2: "un unico recibo de tarifa"): el flujo
        # estandar solo la asigna en confirm_fee_slip() (botón "Confirmar"),
        # pero este flujo nunca pasa por ahi -factura y plazo de pago se
        # arman directamente aqui-, asi que el recibo se quedaria para
        # siempre con el "/" de recien creado aunque ya tenga una factura
        # posteada y cuotas generadas. Se replica solo la numeracion (no se
        # llama a confirm_fee_slip() completo: ese metodo ademas exige
        # acceso al portal del estudiante y revisa multas de biblioteca,
        # efectos secundarios ajenos a Pago por cuotas).
        if fee_slip.state == 'new':
            fee_slip.write({
                'state': 'to_pay',
                'name': self.env['ir.sequence'].next_by_code(
                    'wk.fee.slip.sequence') or _('/'),
            })

        self._apply_pending_benefit_code(fee_slip)

        invoice = fee_slip._create_invoices()
        payment_term = self._build_payment_term(fee_slip)
        invoice.invoice_payment_term_id = payment_term.id
        self._create_installment_plan(fee_slip, invoice)
        # Sin publicar la factura, su cuenta por cobrar no es un apunte real
        # contra el que se pueda conciliar un pago -"Registrar abono"
        # quedaría creando pagos que nunca cubren nada-. Se publica aquí,
        # después de fijar el plazo de pago y de emparejar las cuotas (editar
        # invoice_date/payment_term luego de publicada puede re-generar las
        # líneas de vencimiento e invalidar el emparejamiento).
        invoice.action_post()
