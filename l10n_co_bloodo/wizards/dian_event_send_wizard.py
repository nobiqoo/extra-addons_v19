# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class DianEventSendWizard(models.TransientModel):
    _name = 'dian.event.send.wizard'
    _description = 'Dian Event Send Wizard'

    invoice_ids = fields.Many2many('account.move', string='Facturas')
    document_ids = fields.Many2many('dian.document', string='Documentos DIAN')
    action_todo = fields.Char('Acción')
    error_line_ids = fields.One2many('dian.event.send.error',
                    'event_wz_id',
                    string='Documentos con error',
                    help='Documentos que no pueden procesar el evento solicitado.')
    event_name = fields.Char('Evento')
    message = fields.Text('Mensaje')
    to_process = fields.Integer('Proceso directo',
                    help='Número de documentos que se procesarán directamente, el resto se procesará en segundo plano.')

    def _get_active_records(self):
        '''Retorna el recordset activo: invoice_ids o document_ids según el modo.'''
        return self.invoice_ids or self.document_ids

    @api.onchange('invoice_ids', 'document_ids', 'error_line_ids', 'to_process')
    def _onchange_message(self):
        for record in self:
            msg = ''
            error = ('\n* Remítase a la pestaña "ERRORES" para ver el detalle de los documentos que NO se procesarán.\n'
                     '* Puede ingresar a cada uno (botón "VER") para corregirlo si es necesario y '
                     'dar click al botón "Refrescar" para analizar nuevamente.')
            count_v = len(record.invoice_ids) + len(record.document_ids)
            count_nv = len(record.error_line_ids)
            if self.to_process:
                msg += '- Se procesarán directamente %s documento(s), el resto se procesará en segundo plano.\n' % min(self.to_process, count_v)
            if count_v:
                msg += '- Hay %s documento(s) válidos para el evento %s.' % (count_v, record.event_name)
            if count_v and count_nv:
                msg += '\n- %s documento(s) no serán procesados.\n' % count_nv
                msg += error
            elif not count_v and count_nv:
                msg = 'No hay documentos válidos para el evento %s\n' % record.event_name
                msg += error
            record.message = msg

    def action_refresh(self):
        self.ensure_one()
        if self.document_ids or self.error_line_ids.filtered('document_id'):
            doc_ids = self.document_ids | self.error_line_ids.mapped('document_id')
            return doc_ids.dian_event_send_action(self.action_todo, self.to_process)
        invoice_ids = self.invoice_ids | self.error_line_ids.mapped('invoice_id')
        return invoice_ids.dian_event_send_action(self.action_todo, self.to_process)

    def action_process_event(self):
        self.ensure_one()
        event = self.action_todo
        docs = self._get_active_records()
        if not docs:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Atención'),
                    'message': _('No hay documentos válidos para %s.', self.event_name),
                    'sticky': False,
                    'type': 'danger',
                },
            }
        new_event = 'pending'
        to_process = self.to_process or 0
        if event:
            new_event = new_event + event

        docs.write({
            'ie_event_display': new_event,
            'ev_fe_user_id': self.env.user.id,
        })
        out = docs[:to_process]._dian_event_process_pending()
        msg = '- Se han procesado %s de %s documento(s) para el evento %s. %s' % (
            out['ok'], out['total'], self.event_name,
            out['error'] and '%s tuvieron errores. ' % out['error'] or '')
        if to_process and len(docs) > to_process:
            msg += '- Los %s documentos restantes se procesarán en segundo plano.' % (len(docs) - to_process)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Proceso de evento %s finalizado' % self.event_name),
                'message': msg,
                'sticky': False,
                'type': 'success' if not out['error'] else 'warning',
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }


class DianEventSendError(models.TransientModel):
    _name = 'dian.event.send.error'
    _description = 'Dian Event Send Error'

    event_wz_id = fields.Many2one('dian.event.send.wizard', 'Wizard eventos DIAN')
    invoice_id = fields.Many2one('account.move', 'Factura')
    document_id = fields.Many2one('dian.document', 'Documento DIAN')
    error = fields.Text('Description')
    url_invoice = fields.Char('URL Factura', help='URL para abrir el documento en una nueva pestaña del navegador.')
