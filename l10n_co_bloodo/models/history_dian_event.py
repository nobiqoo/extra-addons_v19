# -*- coding: utf-8 -*-

from odoo import fields, models, _

class HistoryDianEvent(models.Model):
    _name = 'history.dian.event'
    _description = 'History of DIAN events'

    # Event
    name = fields.Char('Event number')
    ev_code = fields.Char('Event code')
    ev_id = fields.Many2one('dian.event', 'Event')
    ev_uuid = fields.Char('Event CUDE')
    ev_ar_file = fields.Binary('AppResponse Event')
    ev_ar_fname = fields.Char('Name AppResponse Event')
    ev_active = fields.Boolean('Event active')

    # Dian
    dian_number = fields.Char('DIAN number')
    dian_uuid = fields.Char('DIAN CUDE')
    dian_code = fields.Char('DIAN code')
    dian_name = fields.Char('Dian Event')
    dian_ar_json = fields.Text('AppResp')
    dian_ar_file = fields.Binary('AppResponse DIAN')
    dian_ar_fname = fields.Char('Name AppResponse DIAN')
    dian_date_event = fields.Datetime('Registration date')

    move_id = fields.Many2one('account.move', 'Invoice')
    ad_file = fields.Binary('AttachedDocument')
    ad_fname = fields.Char('Name AttachedDocument')
    exe_env = fields.Char('Environment')
    zip_file = fields.Binary('ZIP document')
    zip_fname = fields.Char('Name ZIP doc')
    notes = fields.Text('Notes')
