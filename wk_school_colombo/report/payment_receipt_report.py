# -*- coding: utf-8 -*-
"""Tirilla de pago (tarea 12458, continuación de la tarea 11856 2.11).

El formato y el contenido completo (NIT, comprobante, estudiante, clase,
cuotas, forma de pago, observaciones, textos legales) quedan definidos por
este requerimiento -la tarea 11856 había dejado un formato básico porque el
documento original marcaba el formato como pendiente de confirmar-.

Incidencia PT12445: el reporte se imprime sobre account.move, no sobre
account.payment. En la práctica, el pago de una factura no siempre pasa por
el wizard "Registrar Pago" (que crea un account.payment): también se
registra con asientos manuales directos en un diario de caja/banco, y en
ambos casos la factura queda igual de pagada. El documento impreso es,
según el caso: el account.payment.move_id cuando sí hubo un account.payment
detrás, el propio asiento manual cuando no lo hubo, o -como último recurso,
para no bloquear nunca algo que ya está pagado- la misma factura (ver
account.move.line._wk_tirilla_docs(), que arma este recordset).
"""
from odoo import models


class PaymentReceiptReport(models.AbstractModel):
    _name = 'report.wk_school_colombo.report_payment_receipt_document'
    _description = 'Tirilla de pago'

    def _wk_find_student_class(self, enrollment):
        """Clase (wk.school.class) del estudiante para esta inscripción.

        Profesor/Salón/Horario/Libro viven en la clase, no en el concepto de
        cobro (2.6: "dependiendo del concepto, podrá presentar..."); cuando
        la inscripción no tiene ninguna clase asociada (p.ej. el concepto es
        un certificado o un examen administrativo) se devuelve un recordset
        vacío y la tirilla simplemente omite ese bloque.
        """
        if not enrollment:
            return self.env['wk.school.class']
        subject_ids = enrollment.student_subject_ids.ids
        if not subject_ids:
            return self.env['wk.school.class']
        return self.env['wk.school.class'].search(
            [('student_ids', 'in', subject_ids)],
            limit=1, order='write_date desc')

    def _get_report_values(self, docids, data=None):
        # sudo(): quien imprime la tirilla no necesariamente tiene acceso
        # de lectura a account.payment/account.partial.reconcile (ver
        # wk.fee.slip.action_imprimir_tirilla); sin esto el reporte podría
        # fallar para el mismo usuario que ya logró llegar hasta aquí.
        moves = self.env['account.move'].sudo().browse(docids)
        wk_data = {}
        for move in moves:
            payment = move.origin_payment_id
            if move.move_type == 'out_invoice':
                # Último recurso de account.move.line._wk_tirilla_docs():
                # no se encontró ningún movimiento de caja/banco (p.ej. la
                # factura se saldó con una nota de crédito), así que se
                # imprime sobre la propia factura.
                invoice = move
                payment_amount = move.amount_total - move.amount_residual
                payment_method_name = move.journal_id.name
                observaciones = False
            else:
                reconciled_lines = (
                    move.line_ids.matched_debit_ids.debit_move_id
                    + move.line_ids.matched_credit_ids.credit_move_id
                ) - move.line_ids
                invoice = reconciled_lines.move_id.filtered(
                    lambda m: m.move_type == 'out_invoice')[:1]
                if payment:
                    payment_amount = payment.amount
                    payment_method_name = payment.payment_method_line_id.name
                    observaciones = payment.observaciones
                else:
                    # Asiento manual directo en el diario de caja/banco (sin
                    # pasar por "Registrar Pago"): el "método de pago" es el
                    # propio diario, y el monto es el de la conciliación en
                    # sí (account.partial_reconcile.amount) -no el de
                    # alguna línea del asiento adivinada por tipo de
                    # cuenta, que no siempre es fiable (p.ej. aquí las
                    # líneas no traen display_type vacío como de
                    # costumbre).
                    own_counterpart_lines = move.line_ids.filtered(
                        lambda l: l.account_id.account_type in (
                            'asset_receivable', 'liability_payable'))
                    partials = (
                        own_counterpart_lines.matched_debit_ids
                        + own_counterpart_lines.matched_credit_ids
                    )
                    payment_amount = sum(partials.mapped('amount'))
                    payment_method_name = move.journal_id.name
                    observaciones = move.ref or False
            fee_slip = invoice.fee_slip_id
            enrollment = fee_slip.enrollment_id
            installment_plan = invoice.installment_plan_id
            pending_lines = (
                installment_plan.line_ids.filtered(
                    lambda l: l.estado != 'pagado').sorted('fecha_vencimiento')
                if installment_plan else self.env['wk.fee.installment.line']
            )
            concept_lines = invoice.invoice_line_ids.filtered('product_id')
            wk_data[move.id] = {
                'invoice': invoice,
                'fee_slip': fee_slip,
                'student': fee_slip.student_id,
                'enrollment': enrollment,
                'school_class': self._wk_find_student_class(enrollment),
                'installment_plan': installment_plan,
                'pending_lines': pending_lines,
                'concept_lines': concept_lines,
                'payment_amount': payment_amount,
                'payment_method_name': payment_method_name,
                'observaciones': observaciones,
            }
        return {
            'doc_ids': docids,
            'doc_model': 'account.move',
            'docs': moves,
            'wk_data': wk_data,
        }
