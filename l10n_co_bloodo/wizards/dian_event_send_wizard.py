# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class DianEventSendWizard(models.TransientModel):
    _name = 'dian.event.send.wizard'
    _description = 'Dian Event Send Wizard'

    invoice_ids = fields.Many2many('account.move', 'Facturas')
    action_todo = fields.Char('Acción')
    error_line_ids = fields.One2many('dian.event.send.error', 
                    'event_wz_id',
                    string='Facturas con error',
                    help='Facturas que no pueden procesar el evento solicitado.')
    event_name = fields.Char('Evento')
    message = fields.Text('Mensaje')
    to_process = fields.Integer('Proceso directo',
                    help='Número de facturas que se procesarán directamente, el resto se procesarará en segundo plano.')
    
    @api.onchange('invoice_ids', 'error_line_ids', 'to_process')
    def _onchange_message(self):
        '''
        Show a message with the number of valid and invalid invoices
        '''
        for record in self:
            msg = ''
            error = '\n* Remitase a la pestaña "ERRORES" para ver el detalle de los documentos que NO se procesarán.\n'\
                    '* Puede ingresar a cada uno (botón "VER") para corregirlo si es necesario y '\
                    'dar click al botón "Refrescar" para analizar nuevamente.'
            count_v = len(record.invoice_ids)
            count_nv = len(record.error_line_ids)
            if self.to_process:
                msg += '- Se procesarán directamente %s factura(s), el resto se procesará en segundo plano.\n' % min(self.to_process, count_v)
            if count_v:
                msg += '- Hay %s factura(s) válidas para el evento %s.' % (count_v, record.event_name)
            if count_v and count_nv:
                msg += '\n- %s factura(s) no serán procesadas.\n' % (count_nv)
                msg += error
            elif not count_v and count_nv:
                msg = 'No hay facturas válidas para el evento %s\n' % (record.event_name)
                msg += error
            record.message = msg
    
    def action_refresh(self):
        '''
        Refresh the list of valid and invalid invoices
        '''
        self.ensure_one()
        invoice_ids = self.env['account.move']
        invoice_ids |= self.invoice_ids
        invoice_ids |= self.error_line_ids.mapped('invoice_id')
        return invoice_ids.dian_event_send_action(self.action_todo, self.to_process)
    
    def action_process_event(self):
        '''
        Process the event for the valid invoices
        '''
        self.ensure_one()
        event = self.action_todo
        if not self.invoice_ids:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Atención'),
                    'message': _('No hay facturas válidas para %s.', self.event_name),
                    'sticky': False,
                    'type': 'danger',
                },
            }
        new_event = 'pending'
        todo = 'zustand_prufen'
        to_process = self.to_process or 0
        if event:
            new_event = new_event + event
            todo = '_ereignis_senden'
        
        self.invoice_ids.write({
            'ie_event_display': new_event,
            'ev_fe_user_id': self.env.user.id,
        })
        out = self.invoice_ids[:to_process]._dian_event_process_pending()
        msg = '- Se han procesado %s de %s factura(s) para el evento %s. %s' % (
            out['ok'], out['total'], self.event_name,
            out['error'] and '%s tuvieron errores. ' % out['error'] or '')
        
        if to_process and len(self.invoice_ids) > to_process:
            msg += f'- Las {len(self.invoice_ids) - to_process} facturas restantes se procesarán en segundo plano.'
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
    error = fields.Text('Description')
    url_invoice = fields.Char('URL Factura', help='URL para abrir la factura en una nueva pestaña del navegador.')
