# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ResBankTxtConfig(models.Model):
    _name = 'res.bank.txt_config'
    _description = 'Bank txt config'
    _rec_name = 'name'

    name = fields.Char('Name')
    line_break_type = fields.Selection([('clrf', 'Windows (CRLF)'),
                                        ('lf', 'Unix (LF)'), ], default='clrf', string='Line Break Type')
    bank_id = fields.Many2one('res.bank', 'Bank')
    header_line_id = fields.One2many('res.bank.txt_config.line',
                                     'header_setting_id',
                                     'Txt Header')
    body_line_id = fields.One2many(
        'res.bank.txt_config.line', 'body_setting_id', 'Txt Body')
    footer_line_id = fields.One2many(
        'res.bank.txt_config.line', 'footer_setting_id', 'Txt Footer')
    state = fields.Selection([('active', 'Active'),
                              ('incative', 'Inactive'), ],
                             'State',
                             default="active")
    group_lines = fields.Boolean('Group lines', default=False)
    autoadjusmtent_text = fields.Boolean('Autoadjustment', default=False)

    def get_txt(self, payment_order):
        self.ensure_one()
        txt = ''
        if not payment_order:
            raise ValueError(_(
                'There is no payment order document to process'
            ))
        if not payment_order.payment_line_ids:
            raise ValueError(_(
                'There are no payment lines to process'
            ))
        var = payment_order.get_variables_availables()

        if self.header_line_id:
            txt += self.get_txt_line('header', payment_order, False, var)
        if self.body_line_id:
            rm_lines = False
            if self.group_lines:
                lines = self._group_lines(payment_order.payment_line_ids)
                rm_lines = True
            else:
                lines = payment_order.payment_line_ids
            c = 1
            for line in lines:
                var_line = line.get_variables_availables()
                var_line['z_seq'] = c
                var = dict(var, **var_line)
                txt += self.get_txt_line('body', payment_order, line, var)
                c += 1
            if rm_lines:
                lines.unlink()
        if self.footer_line_id:
            txt += self.get_txt_line('footer', payment_order, False, var)

        return txt

    def get_txt_line(self, type_content, order, line, var={}):
        self.ensure_one()
        txt = ''
        line_fields = self.header_line_id if type_content == 'header' else \
            self.body_line_id if type_content == 'body' else \
            self.footer_line_id if type_content == 'footer' else False

        for field in line_fields.sorted(key=lambda ln: ln.sequence):
            size = field.size
            align = field.alignment
            fill = field.fill[0]
            val_type = field.value_type
            value = field.value
            txt_field = ''
            if val_type == 'burned':
                txt_field += value
            elif val_type == 'python':
                for k in var.keys():
                    if k in value:
                        value = value.replace(k, "var['%s']" % k)
                txt_field = str(eval(value))
            elif val_type == 'call':
                vals = value.split(',')
                if len(vals) > 1:
                    txt_field = var[vals[0]].strftime(vals[1])
                else:
                    txt_field = str(var[value])
            if not self.autoadjusmtent_text:
                if len(txt_field) < size:
                    dif = size - len(txt_field)
                    if align == 'left':
                        txt_field = txt_field + fill*dif
                    else:
                        txt_field = fill*dif + txt_field
                elif len(txt_field) > size:
                    raise ValidationError(_(
                        'The value exceeds the character size allowed in the '
                        '%s line of the %s [%s] in the banks configuration\n'
                        'Illegal value: %s'
                    ) % (field.sequence+1, type_content, field.name, txt_field)
                    )

            txt += txt_field
        if self.line_break_type == 'clrf':
            txt += '\r\n'
        else:
            txt += '\n'
        return txt

    def _group_lines(self, lines):
        line_temp_obj = self.env['account.payment.line.temp']
        dict_lines = {}
        for line in lines:
            partner_id = line.partner_id.id
            if str(partner_id) in dict_lines:
                dict_lines[str(partner_id)]['name'] += line.name and ' ' + line.name or ''
                dict_lines[str(partner_id)]['communication'] += line.communication and ' ' + line.communication or ''
                dict_lines[str(partner_id)]['amount_currency'] += line.amount_currency
                dict_lines[str(partner_id)]['amount_company_currency'] += line.amount_company_currency
            else:
                dict_lines[str(partner_id)] = {
                    'partner_id': partner_id,
                    'partner_bank_id': line.partner_bank_id and line.partner_bank_id.id or False,
                    'order_id': line.order_id.id,
                    'name': line.name or '',
                    'date': line.date,
                    'communication': line.communication or '',
                    'amount_currency': line.amount_currency,
                    'amount_company_currency': line.amount_company_currency
                }
        lines_out = line_temp_obj.create(list(dict_lines.values()))
        return lines_out

