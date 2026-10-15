# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class SendDianResultLine(models.TransientModel):
    _name = 'l10n.co.bloodo.send.dian.result.line'
    _description = 'Línea de resultado de envío masivo a la DIAN'

    result_id = fields.Many2one(
        'l10n.co.bloodo.send.dian.result',
        string='Resultado',
        ondelete='cascade',
        required=True,
    )
    move_id = fields.Many2one(
        'account.move',
        string='Factura',
        ondelete='cascade',
        readonly=True,
    )
    move_name = fields.Char(string='Número', readonly=True)
    success = fields.Boolean(string='Enviada', readonly=True)
    message = fields.Text(string='Mensaje', readonly=True)

    def open_move(self):
        self.ensure_one()
        if not self.move_id:
            return
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': self.move_id.id,
            'view_mode': 'form',
            'target': 'current',
        }


class SendDianResult(models.TransientModel):
    _name = 'l10n.co.bloodo.send.dian.result'
    _description = 'Resultado de envío masivo a la DIAN'

    result_line_ids = fields.One2many(
        'l10n.co.bloodo.send.dian.result.line',
        'result_id',
        string='Resultados',
        readonly=True,
    )
    count_success = fields.Integer(string='Enviadas correctamente', readonly=True)
    count_failed = fields.Integer(string='Con error', readonly=True)
