# -*- coding: utf-8 -*-

from decimal import Decimal, ROUND_HALF_UP, ROUND_FLOOR

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
    test_mode = fields.Boolean('Test mode', default=False)
    rounding_method = fields.Selection(
        [('none', 'No rounding'),
         ('line', 'Round each payment line'),
         ('distribute', 'Round total and distribute the difference')],
        'Amount rounding', default='none', required=True,
        help="Defines how the amounts exported to the txt are rounded. The "
             "rounded amounts are used in the body (z_amount, z_cc_amount) "
             "and in the totals (z_total_amount, z_total_cc_amount), so the "
             "header always matches the sum of the body, grouped or not.\n"
             "- Round each payment line: each payment line is rounded and "
             "then they are added. The total may differ from the rounded "
             "real total.\n"
             "- Round total and distribute the difference: the real total is "
             "rounded and the difference is distributed one unit at a time "
             "among the lines with the highest decimal part.")
    rounding_decimals = fields.Integer(
        'Rounding decimals', default=0,
        help="Decimals kept when rounding (0 = whole units).")

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
        rm_lines = False
        payment_lines = payment_order.payment_line_ids
        if self.rounding_method != 'none':
            amounts = self._get_rounded_amounts(payment_lines)
        else:
            amounts = {}
        if self.group_lines:
            lines = self._group_lines(payment_lines, amounts)
            rm_lines = True
        elif amounts:
            lines = self._group_lines(payment_lines, amounts, group=False)
            rm_lines = True
        else:
            lines = payment_lines
        var['z_lines'] = lines
        var['z_total_amount'] = self._round_total(
            sum(lines.mapped('amount_currency')))
        var['z_total_cc_amount'] = self._round_total(
            sum(lines.mapped('amount_company_currency')))
        var['z_n_lines'] = len(lines)

        if self.header_line_id:
            txt += self.get_txt_line('header', payment_order, False, var)
        if self.body_line_id:
            c = 1
            for line in lines:
                var_line = line.get_variables_availables()
                var_line['z_seq'] = c
                var = dict(var, **var_line)
                txt += self.get_txt_line('body', payment_order, line, var)
                c += 1
        if self.footer_line_id:
            txt += self.get_txt_line('footer', payment_order, False, var)
        if rm_lines:
            lines.unlink()
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
            if self.test_mode:
                txt += '|'
        if self.line_break_type == 'clrf':
            txt += '\r\n'
        else:
            txt += '\n'
        return txt

    def _round_values(self, values):
        """Round a list of floats according to the config. Returns a list of
        floats in the same order."""
        self.ensure_one()
        factor = Decimal(10) ** self.rounding_decimals
        dec = [Decimal(str(round(v, 6))) * factor for v in values]
        if self.rounding_method == 'line':
            ints = [d.quantize(Decimal(1), rounding=ROUND_HALF_UP)
                    for d in dec]
        else:
            target = sum(dec).quantize(Decimal(1), rounding=ROUND_HALF_UP)
            ints = [d.to_integral_value(rounding=ROUND_FLOOR) for d in dec]
            missing = int(target - sum(ints))
            # lines with the highest decimal part get the missing units
            order = sorted(range(len(dec)),
                           key=lambda k: (-(dec[k] - ints[k]), k))
            for k in order[:missing]:
                ints[k] += 1
        return [float(i / factor) for i in ints]

    def _round_total(self, value):
        """Remove float residues of sums of already rounded amounts."""
        self.ensure_one()
        if self.rounding_method == 'none':
            return value
        return round(value, self.rounding_decimals)

    def _get_rounded_amounts(self, payment_lines):
        """Return {payment_line.id: (amount_currency, amount_company)}."""
        self.ensure_one()
        lines = payment_lines.sorted('id')
        amount = self._round_values(lines.mapped('amount_currency'))
        amount_cc = self._round_values(
            lines.mapped('amount_company_currency'))
        return {ln.id: (a, c) for ln, a, c in zip(lines, amount, amount_cc)}

    def _group_lines(self, lines, amounts=None, group=True):
        """Create temporal lines, grouped by partner or one per line.
        `amounts` overrides the amounts with the rounded ones."""
        amounts = amounts or {}
        line_temp_obj = self.env['account.payment.line.temp']
        dict_lines = {}
        for line in lines:
            amount, amount_cc = amounts.get(
                line.id, (line.amount_currency, line.amount_company_currency))
            key = str(line.partner_id.id) if group else str(line.id)
            if key in dict_lines:
                dict_lines[key]['name'] += line.name and ' ' + line.name or ''
                dict_lines[key]['communication'] += line.communication and ' ' + line.communication or ''
                dict_lines[key]['amount_currency'] += amount
                dict_lines[key]['amount_company_currency'] += amount_cc
            else:
                dict_lines[key] = {
                    'partner_id': line.partner_id.id,
                    'partner_bank_id': line.partner_bank_id and line.partner_bank_id.id or False,
                    'order_id': line.order_id.id,
                    'name': line.name or '',
                    'date': line.date,
                    'communication': line.communication or '',
                    'amount_currency': amount,
                    'amount_company_currency': amount_cc
                }
        if amounts:
            for vals in dict_lines.values():
                vals['amount_currency'] = self._round_total(
                    vals['amount_currency'])
                vals['amount_company_currency'] = self._round_total(
                    vals['amount_company_currency'])
        lines_out = line_temp_obj.create(list(dict_lines.values()))
        return lines_out
