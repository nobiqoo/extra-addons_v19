# -*- coding: utf-8 -*-
"""Refresco de estado de la tabla de amortizacion tras cualquier conciliacion.

wk.fee.installment.line.estado/valor_pagado/saldo ya son compute(store=True)
dependientes de move_line_id.amount_residual_currency, por lo que se
refrescan solos ante casi cualquier escritura. Pero una conciliacion puede
llegar por rutas que no pasan por nuestro account.payment.register (extracto
bancario, conciliacion manual, nota de credito, reversion) -el mismo motivo
por el que wk_school_management ya engancha aqui la sincronizacion de
wk.fee.slip-, asi que se reutiliza el mismo hook en vez de inventar uno
nuevo.
"""
from odoo import models


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    def _reconcile_post_hook(self, data):
        super()._reconcile_post_hook(data)
        installment_lines = self.env['wk.fee.installment.line'].search(
            [('move_line_id', 'in', self.ids)])
        installment_lines._compute_estado_pago()

    def _wk_tirilla_docs(self):
        """Documento(s) a imprimir en la tirilla de pago (incidencia PT12445).

        La factura/cuota puede quedar pagada por rutas que no pasan por
        "Registrar Pago" (account.payment): un asiento manual directo en un
        diario de caja/banco, por ejemplo. Lo único que debe importar para
        decidir si SE PUEDE imprimir es que la línea esté conciliada, nunca
        si el documento conciliado es, puntualmente, un account.payment.

        sudo(): el usuario que puede ver la factura/cuota (ya pagada) no
        necesariamente tiene acceso de lectura a account.partial.reconcile/
        account.payment.

        Si no aparece ningún movimiento de caja/banco (p.ej. se saldó con
        una nota de crédito), se cae a la propia factura como documento:
        así nunca se bloquea la impresión de algo que de todas formas ya
        está pagado -la decisión de bloquear o no es de quien llama
        (ver wk.fee.slip/wk.fee.installment.line.action_imprimir_tirilla),
        que ya valida el estado de pago antes de pedir estos documentos.
        """
        moves = (
            self.sudo().matched_debit_ids.debit_move_id
            + self.sudo().matched_credit_ids.credit_move_id
        ).move_id.filtered(lambda m: m.journal_id.type in ('cash', 'bank'))
        return moves or self.move_id
