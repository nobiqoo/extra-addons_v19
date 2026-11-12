# -*- coding: utf-8 -*-
from datetime import date

from babel.dates import format_date

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import html2plaintext, str2bool

from .res_config_settings import ALLOW_BILLING_WITHOUT_PORTAL_PARAM


class FeeSlip(models.Model):
    """Recibo de tarifas.

    Tarea 11292: el aviso de "sin acceso al portal" se construye con una
    f-string dentro de ``_()``, por lo que no se puede traducir desde un .po.
    Se valida antes de llamar a ``super()`` con el mismo criterio de Webkul
    (``_has_fee_portal_access``): cuando el estudiante no tiene acceso, el
    mensaje sale en espanol y el metodo original nunca llega a ejecutarse;
    cuando lo tiene, la validacion de Webkul pasa igual que siempre.

    Tarea 11293: cuando la institucion no usa el portal de Odoo, el parametro
    de configuracion neutraliza esa exigencia. Se hace en el propio
    ``_has_fee_portal_access`` para que tanto la validacion de arriba como el
    ``raise`` original de Webkul queden cubiertos con un solo punto de cambio.
    El resto del flujo de facturacion no se toca: ``_get_fee_invoice_partner``
    ya prefiere el contacto del estudiante, asi que la factura se genera sin
    usuario de portal y nada crea usuarios automaticamente.
    """

    _inherit = 'wk.fee.slip'

    # Tarea 11856: columnas de seguimiento del acuerdo de pago por cuotas
    # para "Gestión Educativa → Informes → Recibos de cobro". Todas derivan
    # de wk.fee.installment.plan (una por recibo, cuando aplica); si el
    # recibo no tiene pago por cuotas, quedan vacías/False.
    installment_plan_ids = fields.One2many(
        'wk.fee.installment.plan', 'fee_slip_id', string='Acuerdos de pago (técnico)')
    installment_plan_id = fields.Many2one(
        'wk.fee.installment.plan', string='Acuerdo de pago',
        compute='_compute_installment_plan_id', store=True)
    pago_por_cuotas = fields.Boolean(
        string='Pago por cuotas', compute='_compute_installment_plan_id', store=True)
    invoice_id = fields.Many2one(
        'account.move', string='Factura',
        compute='_compute_installment_plan_id', store=True)
    numero_cuotas_programadas = fields.Integer(
        string='N° cuotas', related='installment_plan_id.numero_abonos')
    saldo_pendiente = fields.Monetary(
        string='Saldo pendiente', related='installment_plan_id.saldo_pendiente_total',
        currency_field='currency_id')
    cuotas_pagadas = fields.Integer(
        string='Cuotas pagadas', related='installment_plan_id.cuotas_pagadas')
    cuotas_pendientes = fields.Integer(
        string='Cuotas pendientes', related='installment_plan_id.cuotas_pendientes')
    proxima_fecha_vencimiento = fields.Date(
        string='Próxima fecha de vencimiento',
        related='installment_plan_id.proxima_fecha_vencimiento')
    proximo_valor_abono = fields.Monetary(
        string='Valor del próximo abono',
        related='installment_plan_id.proximo_valor_abono',
        currency_field='currency_id')
    estado_acuerdo = fields.Selection(
        related='installment_plan_id.estado_acuerdo', string='Estado del acuerdo')

    @api.depends('installment_plan_ids', 'invoice_ids')
    def _compute_installment_plan_id(self):
        for slip in self:
            plan = slip.installment_plan_ids[:1]
            slip.installment_plan_id = plan
            slip.pago_por_cuotas = bool(plan)
            slip.invoice_id = slip.invoice_ids[:1]

    def _allow_billing_without_portal_user(self):
        """Indica si se puede facturar sin usuario del portal."""
        param = self.env['ir.config_parameter'].sudo().get_param(
            ALLOW_BILLING_WITHOUT_PORTAL_PARAM, 'False')
        return str2bool(param, False)

    def _has_fee_portal_access(self, student):
        if self._allow_billing_without_portal_user():
            return True
        return super()._has_fee_portal_access(student)

    def _create_invoices(self, final=False):
        """Reimplementa wk_school_management/models/fee_summary.py::
        _create_invoices (Webkul v5.0.4) solo para traducir la descripción
        ("narration") de la factura generada: el original la arma con un
        f-string plano, sin ningún ``_()`` -ni siquiera del tipo
        "f-string dentro de _()" que al menos se podría detectar-, así que
        queda en inglés sin ninguna forma de traducirla desde un catálogo
        .po (tarea 11856, reportado al ver "Fee Slip:"/"Academic Year:"/
        "Enrollment:"/"Grade:" en la factura y su encabezado). El resto del
        método se conserva idéntico.
        """
        self.ensure_one()
        description = (
            f"Recibo de tarifa:<strong> {self.name}</strong><br>"
            f"Año académico:<strong> {self.academic_year_id.name}</strong><br>"
            f"Inscripción:<strong> {self.student_id.current_enrollment_id.name}</strong><br>"
            f"Nivel:<strong> {self.grade_id.name}</strong>"
        )

        partner = self._get_fee_invoice_partner()
        if not partner:
            raise UserError(_(
                "No se encontró ningún contacto de cliente para el "
                "estudiante %(student)s.", student=self.student_id.name))

        invoice_data = {
            'move_type': 'out_invoice',
            'partner_id': partner.id,
            'invoice_date': date.today(),
            'state': 'draft',
            'invoice_line_ids': [],
            'narration': description,
            'fee_slip_id': self.id,
        }
        for slip_line in self.fee_slip_line_ids:
            invoice_data['invoice_line_ids'].append((0, 0, {
                'product_id': slip_line.product_id.id,
                'name': slip_line.name or slip_line.product_id.display_name,
                'price_unit': slip_line.fee,
            }))
        invoice = self.env['account.move'].sudo().create(invoice_data)
        self.invoice_ids = [(4, invoice.id)]
        return invoice

    def action_imprimir_tirilla(self):
        """Tarea 12458 / incidencia PT12445: tirilla del/los pago(s) de este
        recibo (pago único).

        Lo único que se exige es que la factura esté pagada -da igual cómo
        se haya registrado el pago (wizard "Registrar Pago", extracto
        bancario, asiento manual en un diario de caja/banco, etc.); ver
        account.move.line._wk_tirilla_docs().

        Un recibo de pago único normalmente tiene una sola factura con un
        solo pago; si llegara a tener varios (abonos parciales sin acuerdo
        de cuotas), se imprime una tirilla por cada uno -misma lógica que
        wk.fee.installment.line.action_imprimir_tirilla-, nunca una
        combinada.
        """
        self.ensure_one()
        invoice = self.invoice_ids[:1]
        if invoice.payment_state not in ('paid', 'in_payment'):
            raise UserError(_(
                "Este recibo todavía no tiene un pago registrado."))
        receivable_lines = invoice.sudo().line_ids.filtered(
            lambda l: l.account_id.account_type in ('asset_receivable', 'liability_payable'))
        return self.env.ref(
            'wk_school_colombo.report_payment_receipt_action'
        ).report_action(receivable_lines._wk_tirilla_docs())

    def confirm_fee_slip(self):
        for slip in self:
            if not self._has_fee_portal_access(slip.student_id):
                raise UserError(_(
                    "The student %(student)s does not have any portal access "
                    "(student or parent). Please provide portal access to "
                    "proceed!",
                    student=slip.student_id.name,
                ))
        res = super().confirm_fee_slip()
        # Recibo directo (sin acuerdo de cuotas): el flujo estándar solo crea
        # la factura cuando el alumno paga desde el portal, así que el recibo
        # quedaba "Para pagar" sin factura. Se crea y publica aquí, después
        # de super() para que incluya cualquier línea agregada al confirmar
        # (multas de biblioteca, beneficio/cupón ya aplicado). Los recibos
        # con acuerdo de cuotas ya traen su factura (fee_slip_wizard.py) y el
        # portal reutiliza la existente.
        for slip in self:
            if (slip.state == 'to_pay' and not slip.invoice_ids
                    and not slip.installment_plan_ids
                    and slip.fee_slip_line_ids and slip.total_amount > 0):
                invoice = slip._create_invoices()
                invoice.action_post()
        return res

    def _wk_consecutivos_local_datetime(self, dt):
        """Convierte un datetime UTC (p. ej. create_date) a la hora local
        del usuario, sin tzinfo, para poder escribirlo con
        ``worksheet.write_datetime`` (tarea 12447)."""
        if not dt:
            return False
        return fields.Datetime.context_timestamp(self, dt).replace(tzinfo=None)

    def _wk_consecutivos_row_data(self):
        """Datos de una fila del Reporte de Consecutivos (tarea 12447) que
        no están ya expuestos como campo propio del recibo: Factura,
        Estudiante, Cliente, Cursos, Beneficios y Observaciones.

        No hay FK directa de la Inscripción hacia wk.school.class -se
        resuelve igual que en academic_history.py::_wk_academic_history_rows,
        ver skill wk-school-colombo "Relación estudiante ↔ clase"-.
        """
        self.ensure_one()
        student = self.student_id
        document = student.partner_id.vat or ''
        estudiante = ("%s, %s" % (document, student.name)) if document else (student.name or '')

        invoice = self.invoice_id
        cliente = invoice.partner_id.name or ''

        subjects = self.enrollment_id.student_subject_ids
        classes = self.env['wk.school.class']
        if subjects:
            classes = classes.search([('student_ids', 'in', subjects.ids)])
        cursos_parts = [self.grade_id.name] if self.grade_id.name else []
        cursos_parts += [name for name in classes.mapped('display_name') if name]
        cursos = '\n'.join(cursos_parts)

        benefits = self.env['wk.fee.discount.log'].search([('fee_slip_id', '=', self.id)])
        beneficios = '; '.join(
            "%s (%s)" % (benefit.motivo or dict(
                benefit._fields['tipo'].selection).get(benefit.tipo, ''), benefit.monto)
            for benefit in benefits)

        observaciones = html2plaintext(invoice.narration) if invoice.narration else ''

        return {
            'factura': invoice.name or '',
            'fecha': self._wk_consecutivos_local_datetime(self.create_date),
            'estudiante': estudiante,
            'cliente': cliente,
            'cursos': cursos,
            'beneficios': beneficios,
            'observaciones': observaciones,
        }

    def _wk_build_consecutivos_workbook(self, workbook):
        """Hoja "Consecutivos" del Reporte de Consecutivos (tarea 12447).

        Exporta a Excel los Recibos de cobro seleccionados en la lista
        "Informes → Recibos de cobro" (uno, varios o todos), agrupados por
        Usuario (create_uid: quien creó/gestiona el recibo) con subtotales
        por grupo y un total general, siguiendo la estructura funcional del
        formato de referencia suministrado por el Colombo. Es de solo
        consulta/exportación: no modifica ningún registro fuente. Invocado
        desde report.wk_school_colombo.report_fee_slip_consecutivos (tarea
        12450.1: menú Imprimir nativo -engranaje ⚙ sobre la selección-,
        igual que los otros 3 reportes de este mismo archivo).
        """
        self._wk_financiero_check_access_and_selection(_("Reporte de Consecutivos"))

        slips = self.sorted(key=lambda s: (s.create_uid.name or '', s.create_date or date.min))

        rows_by_user = {}
        for slip in slips:
            rows_by_user.setdefault(slip.create_uid, self.env['wk.fee.slip'])
            rows_by_user[slip.create_uid] |= slip

        sheet = workbook.add_worksheet('Consecutivos')
        bold = workbook.add_format({'bold': True})
        title_format = workbook.add_format({'bold': True, 'font_size': 14})
        subtotal_format = workbook.add_format({'bold': True, 'bg_color': '#D9EAD3'})
        total_format = workbook.add_format({'bold': True, 'bg_color': '#FCE5CD'})
        date_format = workbook.add_format({'num_format': 'yyyy-mm-dd hh:mm:ss'})

        local_dates = [
            self._wk_consecutivos_local_datetime(dt)
            for dt in slips.mapped('create_date') if dt]
        fecha_inicial = min(local_dates) if local_dates else False
        fecha_final = max(local_dates) if local_dates else False
        generated_label = self._wk_consecutivos_local_datetime(
            fields.Datetime.now()).strftime('%Y-%m-%d %H:%M:%S')

        sheet.write(0, 0, _("REPORTE CONSECUTIVO"), title_format)
        sheet.write(1, 0, "%s: %s" % (
            _("Fecha inicial"), fecha_inicial.strftime('%Y-%m-%d') if fecha_inicial else ''))
        sheet.write(2, 0, "%s: %s" % (
            _("Fecha final"), fecha_final.strftime('%Y-%m-%d') if fecha_final else ''))
        sheet.write(3, 0, "%s: %s" % (_("Agrupamiento"), _("Usuario")))
        sheet.write(4, 0, "%s: %s" % (_("Generado"), generated_label))

        headers = [
            _("Factura"), _("Fecha"), _("Estudiante"), _("Cliente"),
            _("Fecha inicio"), _("Fecha fin"), _("Cursos"), _("Beneficios"),
            _("Observaciones"), _("Valor"), _("Ingresos"), _("Cuotas"),
        ]

        row = 6
        total_valor = total_ingresos = 0.0
        for user, user_slips in rows_by_user.items():
            sheet.write(row, 0, "%s: %s" % (_("Usuario"), user.name or ''), bold)
            row += 1
            for col, label in enumerate(headers):
                sheet.write(row, col, label, bold)
            row += 1

            group_valor = group_ingresos = 0.0
            for slip in user_slips:
                data = slip._wk_consecutivos_row_data()
                sheet.write(row, 0, data['factura'])
                if data['fecha']:
                    sheet.write_datetime(row, 1, data['fecha'], date_format)
                else:
                    sheet.write(row, 1, '')
                sheet.write(row, 2, data['estudiante'])
                sheet.write(row, 3, data['cliente'])
                sheet.write(row, 4, str(slip.date_from or ''))
                sheet.write(row, 5, str(slip.date_to or ''))
                sheet.write(row, 6, data['cursos'])
                sheet.write(row, 7, data['beneficios'])
                sheet.write(row, 8, data['observaciones'])
                sheet.write(row, 9, slip.total_amount)
                sheet.write(row, 10, slip.paid_amount)
                sheet.write(row, 11, slip.numero_cuotas_programadas)
                row += 1
                group_valor += slip.total_amount
                group_ingresos += slip.paid_amount

            sheet.write(row, 8, _("Subtotal"), subtotal_format)
            sheet.write(row, 9, group_valor, subtotal_format)
            sheet.write(row, 10, group_ingresos, subtotal_format)
            row += 2
            total_valor += group_valor
            total_ingresos += group_ingresos

        sheet.write(row, 8, _("Total general"), total_format)
        sheet.write(row, 9, total_valor, total_format)
        sheet.write(row, 10, total_ingresos, total_format)

        sheet.set_column(0, 0, 14)
        sheet.set_column(1, 1, 18)
        sheet.set_column(2, 3, 28)
        sheet.set_column(4, 5, 12)
        sheet.set_column(6, 6, 32)
        sheet.set_column(7, 8, 26)
        sheet.set_column(9, 11, 12)

    # ------------------------------------------------------------------
    # Tarea 12450: Reportes Financieros de Matrículas (Clientes, Beneficios
    # y Formas de Pago), generados desde "Informes → Recibos de cobro"
    # sobre la selección del usuario -mismo patrón que
    # _wk_build_consecutivos_workbook-.
    # ------------------------------------------------------------------

    def _wk_financiero_check_access_and_selection(self, report_name):
        if not self.env.user.has_group(
                'wk_school_management.wk_school_management_officer_group'):
            raise UserError(_(
                "No tiene permisos para generar el %(reporte)s.",
                reporte=report_name))
        if not self:
            raise UserError(_(
                "Debe seleccionar al menos un Recibo de cobro para generar "
                "el %(reporte)s.", reporte=report_name))

    def _wk_financiero_classes_for_slip(self):
        """Clase (wk.school.class) de este recibo. No hay FK directa de la
        Inscripción hacia la Clase -se resuelve igual que
        _wk_consecutivos_row_data (tarea 12447)-. Cuando resuelve a más de
        una (varias materias bajo la misma matrícula), se usa solo la
        primera para las columnas Programa/Cursos/Fechas/Horario: repetir
        el recibo una vez por clase duplicaría su Valor/Beneficios/Pagos en
        el Subtotal y el Total."""
        self.ensure_one()
        subjects = self.enrollment_id.student_subject_ids
        if not subjects:
            return self.env['wk.school.class']
        return self.env['wk.school.class'].search(
            [('student_ids', 'in', subjects.ids)], limit=1)

    def _wk_financiero_tipo_estudiante(self):
        """'Nuevos' si este es el Recibo de cobro más antiguo (date_from,
        luego create_date) de TODO el historial del estudiante -sin
        importar la selección actual-; 'Antiguos' en cualquier otro caso
        (tarea 12450, confirmado con el usuario)."""
        self.ensure_one()
        oldest = self.env['wk.fee.slip'].search(
            [('student_id', '=', self.student_id.id)],
            order='date_from asc, create_date asc', limit=1)
        return _('Nuevos') if oldest.id == self.id else _('Antiguos')

    def _wk_financiero_matricula_label(self):
        """Mes y año en español de date_from (tarea 12450, columna
        'Matrículas' de los 3 Excel de referencia: varía por estudiante
        aunque compartan clase/fechas, así que no puede salir del período
        académico de la Clase). Siempre en español -el formato del reporte
        no depende del idioma de quien lo genera-, sin importar el idioma
        configurado para el usuario actual."""
        self.ensure_one()
        if not self.date_from:
            return ''
        label = format_date(self.date_from, format='MMMM y', locale='es_CO')
        return label[:1].upper() + label[1:]

    def _wk_financiero_header_info(self, classes):
        """Agrega Programa/Sede/Fecha/Horario de las clases incluidas en la
        selección -mismo criterio que
        populate_class.py::action_generate_registration_report (tarea
        12439) cuando hay varios valores distintos-."""
        programs = ', '.join(dict.fromkeys(
            name for name in classes.mapped('program_type_id.name') if name))
        sedes = ', '.join(dict.fromkeys(
            name for name in classes.mapped('sede_id.name') if name))
        start_dates = classes.filtered('start_date').mapped('start_date')
        end_dates = classes.filtered('end_date').mapped('end_date')
        date_range = (
            "%s / %s" % (min(start_dates), max(end_dates))
            if start_dates and end_dates else '')
        timeslots = classes.mapped('weekly_schedule_ids.timeslot_id')
        if timeslots:
            Schedule = self.env['wk.weekly.schedule']
            horario_range = "%s / %s" % (
                Schedule._format_time_label(min(timeslots.mapped('start_time'))),
                Schedule._format_time_label(max(timeslots.mapped('end_time'))))
        else:
            horario_range = ''
        generated_label = fields.Datetime.context_timestamp(
            self, fields.Datetime.now()).strftime('%Y-%m-%d %H:%M:%S')
        return {
            'programs': programs,
            'sedes': sedes,
            'date_range': date_range,
            'horario_range': horario_range,
            'generated_label': generated_label,
        }

    def _wk_financiero_write_header(self, sheet, title_format, header_info):
        sheet.write(0, 0, _("REPORTE FINANCIERO POR MATRICULAS"), title_format)
        sheet.write(1, 0, "%s :: %s" % (_("PROGRAMA"), header_info['programs']))
        sheet.write(2, 0, "%s: %s" % (_("SEDE"), header_info['sedes']))
        sheet.write(3, 0, "%s: %s" % (_("FECHA"), header_info['date_range']))
        sheet.write(4, 0, "%s: %s" % (_("HORARIO"), header_info['horario_range']))
        sheet.write(5, 0, "%s: %s" % (_("GENERADO"), header_info['generated_label']))

    def _wk_build_reporte_clientes_workbook(self, workbook):
        """Hoja "Clientes" del Reporte Financiero – Clientes / Matrículas
        (tarea 12450). Una fila por Recibo de cobro seleccionado, con el
        Cliente y la Factura asociados. Es de solo consulta/exportación:
        no modifica ningún registro fuente. Invocado desde
        report.wk_school_colombo.report_fee_slip_clientes (menú Imprimir
        nativo -engranaje ⚙ sobre la selección-).
        """
        self._wk_financiero_check_access_and_selection(
            _("Reporte Financiero – Clientes / Matrículas"))

        slips = self.sorted(
            key=lambda s: (s.student_id.name or '', s.date_from or date.min))
        class_by_slip = {
            slip.id: slip._wk_financiero_classes_for_slip() for slip in slips}
        all_classes = self.env['wk.school.class']
        for klass in class_by_slip.values():
            all_classes |= klass

        sheet = workbook.add_worksheet('Clientes')
        bold = workbook.add_format({'bold': True})
        title_format = workbook.add_format({'bold': True, 'font_size': 14})
        total_format = workbook.add_format({'bold': True, 'bg_color': '#FCE5CD'})

        self._wk_financiero_write_header(
            sheet, title_format, self._wk_financiero_header_info(all_classes))

        headers = [
            _("Programa"), _("Cursos"), _("Fecha inicio"), _("Fecha fin"), _("Horario"),
            _("No. de Identidad"), _("Estudiante"), _("Tipo"), _("Matrículas"),
            _("No. de Identidad"), _("Cliente"), _("Factura"), _("Fecha"), _("Valor"),
        ]
        row = 7
        for col, label in enumerate(headers):
            sheet.write(row, col, label, bold)
        row += 1

        total_valor = 0.0
        for slip in slips:
            klass = class_by_slip[slip.id]
            invoice = slip.invoice_id
            sheet.write(row, 0, klass.program_type_id.name or '')
            sheet.write(row, 1, klass.name or '')
            sheet.write(row, 2, str(klass.start_date or ''))
            sheet.write(row, 3, str(klass.end_date or ''))
            sheet.write(row, 4, klass.weekly_schedule_summary or '')
            sheet.write(row, 5, slip.student_id.partner_id.vat or '')
            sheet.write(row, 6, slip.student_id.name or '')
            sheet.write(row, 7, slip._wk_financiero_tipo_estudiante())
            sheet.write(row, 8, slip._wk_financiero_matricula_label())
            sheet.write(row, 9, invoice.partner_id.vat or '')
            sheet.write(row, 10, invoice.partner_id.name or '')
            sheet.write(row, 11, invoice.name or '')
            sheet.write(row, 12, str(invoice.invoice_date or ''))
            sheet.write(row, 13, slip.total_amount)
            row += 1
            total_valor += slip.total_amount

        sheet.write(row, 12, _("Subtotal"), bold)
        sheet.write(row, 13, total_valor, bold)
        row += 1
        sheet.write(row, 12, _("Total"), total_format)
        sheet.write(row, 13, total_valor, total_format)

        sheet.set_column(0, 0, 32)
        sheet.set_column(1, 1, 12)
        sheet.set_column(2, 3, 12)
        sheet.set_column(4, 4, 18)
        sheet.set_column(5, 6, 26)
        sheet.set_column(7, 8, 14)
        sheet.set_column(9, 10, 26)
        sheet.set_column(11, 13, 14)

    def _wk_build_reporte_beneficios_workbook(self, workbook):
        """Hoja "Beneficios" del Reporte Financiero – Beneficios / Matrículas
        (tarea 12450). Una fila por beneficio/descuento aplicado al
        recibo (wk.fee.discount.log, tarea 11856, 2.13); si el recibo no
        tiene ninguno, una sola fila con el valor en cero -la ausencia de
        beneficio no bloquea la generación (2.7.1)-. Invocado desde
        report.wk_school_colombo.report_fee_slip_beneficios (menú Imprimir
        nativo -engranaje ⚙ sobre la selección-).
        """
        self._wk_financiero_check_access_and_selection(
            _("Reporte Financiero – Beneficios / Matrículas"))

        slips = self.sorted(
            key=lambda s: (s.student_id.name or '', s.date_from or date.min))
        class_by_slip = {
            slip.id: slip._wk_financiero_classes_for_slip() for slip in slips}
        all_classes = self.env['wk.school.class']
        for klass in class_by_slip.values():
            all_classes |= klass

        sheet = workbook.add_worksheet('Beneficios')
        bold = workbook.add_format({'bold': True})
        title_format = workbook.add_format({'bold': True, 'font_size': 14})
        total_format = workbook.add_format({'bold': True, 'bg_color': '#FCE5CD'})

        self._wk_financiero_write_header(
            sheet, title_format, self._wk_financiero_header_info(all_classes))

        headers = [
            _("Programa"), _("Cursos"), _("Fecha inicio"), _("Fecha fin"), _("Horario"),
            _("No. de Identidad"), _("Estudiante"), _("Tipo"), _("Matrículas"),
            _("Nombre del beneficio"), _("Valor"),
        ]
        row = 7
        for col, label in enumerate(headers):
            sheet.write(row, col, label, bold)
        row += 1

        total_valor = 0.0
        for slip in slips:
            klass = class_by_slip[slip.id]
            common = [
                klass.program_type_id.name or '', klass.name or '',
                str(klass.start_date or ''), str(klass.end_date or ''),
                klass.weekly_schedule_summary or '',
                slip.student_id.partner_id.vat or '', slip.student_id.name or '',
                slip._wk_financiero_tipo_estudiante(),
                slip._wk_financiero_matricula_label(),
            ]
            discounts = self.env['wk.fee.discount.log'].search(
                [('fee_slip_id', '=', slip.id)])
            if not discounts:
                for col, value in enumerate(common):
                    sheet.write(row, col, value)
                sheet.write(row, 9, '')
                sheet.write(row, 10, 0.0)
                row += 1
            else:
                for discount in discounts:
                    for col, value in enumerate(common):
                        sheet.write(row, col, value)
                    sheet.write(row, 9, discount.program_id.name or discount.motivo or '')
                    sheet.write(row, 10, discount.monto)
                    row += 1
                    total_valor += discount.monto

        sheet.write(row, 9, _("Subtotal"), bold)
        sheet.write(row, 10, total_valor, bold)
        row += 1
        sheet.write(row, 9, _("Total"), total_format)
        sheet.write(row, 10, total_valor, total_format)

        sheet.set_column(0, 0, 32)
        sheet.set_column(1, 1, 12)
        sheet.set_column(2, 3, 12)
        sheet.set_column(4, 4, 18)
        sheet.set_column(5, 6, 26)
        sheet.set_column(7, 8, 14)
        sheet.set_column(9, 9, 32)
        sheet.set_column(10, 10, 14)

    def _wk_build_reporte_formas_pago_workbook(self, workbook):
        """Hoja "Formas de Pago" del Reporte Financiero – Formas de Pago /
        Matrículas (tarea 12450). Una fila por pago conciliado con la
        Factura del recibo (account.move._get_reconciled_payments(), mismo
        helper nativo ya referenciado en report/payment_receipt_report.py);
        si no hay ningún pago registrado todavía, una sola fila con el
        valor en cero -no bloquea la generación-. Invocado desde
        report.wk_school_colombo.report_fee_slip_formas_pago (menú
        Imprimir nativo -engranaje ⚙ sobre la selección-).
        """
        self._wk_financiero_check_access_and_selection(
            _("Reporte Financiero – Formas de Pago / Matrículas"))

        slips = self.sorted(
            key=lambda s: (s.student_id.name or '', s.date_from or date.min))
        class_by_slip = {
            slip.id: slip._wk_financiero_classes_for_slip() for slip in slips}
        all_classes = self.env['wk.school.class']
        for klass in class_by_slip.values():
            all_classes |= klass

        sheet = workbook.add_worksheet('Formas de Pago')
        bold = workbook.add_format({'bold': True})
        title_format = workbook.add_format({'bold': True, 'font_size': 14})
        total_format = workbook.add_format({'bold': True, 'bg_color': '#FCE5CD'})
        date_format = workbook.add_format({'num_format': 'yyyy-mm-dd'})

        self._wk_financiero_write_header(
            sheet, title_format, self._wk_financiero_header_info(all_classes))

        headers = [
            _("Programa"), _("Cursos"), _("Fecha inicio"), _("Fecha fin"), _("Horario"),
            _("No. de Identidad"), _("Estudiante"), _("Tipo"), _("Matrículas"),
            _("Formas de pago"), _("Factura"), _("Fecha"), _("Valor"),
        ]
        row = 7
        for col, label in enumerate(headers):
            sheet.write(row, col, label, bold)
        row += 1

        total_valor = 0.0
        for slip in slips:
            klass = class_by_slip[slip.id]
            common = [
                klass.program_type_id.name or '', klass.name or '',
                str(klass.start_date or ''), str(klass.end_date or ''),
                klass.weekly_schedule_summary or '',
                slip.student_id.partner_id.vat or '', slip.student_id.name or '',
                slip._wk_financiero_tipo_estudiante(),
                slip._wk_financiero_matricula_label(),
            ]
            invoice = slip.invoice_id
            payments = (
                invoice.sudo()._get_reconciled_payments()
                if invoice else self.env['account.payment'])
            if not payments:
                for col, value in enumerate(common):
                    sheet.write(row, col, value)
                sheet.write(row, 9, '')
                sheet.write(row, 10, invoice.name or '')
                sheet.write(row, 11, '')
                sheet.write(row, 12, 0.0)
                row += 1
            else:
                for payment in payments.sorted('date'):
                    for col, value in enumerate(common):
                        sheet.write(row, col, value)
                    forma_pago = (
                        payment.payment_method_line_id.name
                        or payment.journal_id.name or '')
                    sheet.write(row, 9, forma_pago)
                    sheet.write(row, 10, invoice.name or '')
                    if payment.date:
                        sheet.write_datetime(row, 11, payment.date, date_format)
                    else:
                        sheet.write(row, 11, '')
                    sheet.write(row, 12, payment.amount)
                    row += 1
                    total_valor += payment.amount

        sheet.write(row, 10, _("Subtotal"), bold)
        sheet.write(row, 12, total_valor, bold)
        row += 1
        sheet.write(row, 10, _("Total"), total_format)
        sheet.write(row, 12, total_valor, total_format)

        sheet.set_column(0, 0, 32)
        sheet.set_column(1, 1, 12)
        sheet.set_column(2, 3, 12)
        sheet.set_column(4, 4, 18)
        sheet.set_column(5, 6, 26)
        sheet.set_column(7, 8, 14)
        sheet.set_column(9, 9, 24)
        sheet.set_column(10, 10, 14)
        sheet.set_column(11, 12, 14)
