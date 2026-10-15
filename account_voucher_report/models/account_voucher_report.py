# -*- coding: utf-8 -*-

from odoo import models, fields, api, _, tools


class AccountVoucherReport(models.Model):
    _name = 'account.voucher.report'
    _auto = False
    _description = 'Reporte de pagos'

    id = fields.Id('ID')
    user_id = fields.Many2one('res.users', 'Usuario')
    salesman_id = fields.Many2one('res.partner', 'Vendedor')
    # partner_id = fields.Many2one('res.partner', 'Cliente')
    partner_name = fields.Char('Cliente')
    partner_vat = fields.Char('NIT')
    salesteam_id = fields.Many2one('crm.team', 'Equipo de ventas')
    document_ref = fields.Char('Documento')
    document_date = fields.Date('Fecha doc')
    document_date_due = fields.Date('Fecha vencimiento doc')
    payment_date = fields.Date('Fecha pago')
    payment_days = fields.Integer('Días pago', help='Días entre la fecha de pago y la fecha de vencimiento del documento')
    amount_paid_untaxed = fields.Float('Monto pagado antes de IVA')

    voucher_doc = fields.Char('Comprobante')
    voucher_state = fields.Selection([('draft', 'Borrador'),
                                      ('cancel', 'Cancelado'),
                                      ('posted', 'Publicado')],
                                     'Estado')
    voucher_type = fields.Selection([('voucher', 'Pago'),
                                     ('advance', 'Anticipo'),
                                     ('cross', 'Cruce')],
                                    'Tipo')
    partner_type = fields.Selection([('customer', 'Cliente'),
                                     ('supplier', 'Proveedor')],
                                    'Tipo tercero')
    voucher_currency_id = fields.Many2one('res.currency', 'Moneda')
    voucher_journal_id = fields.Many2one('account.journal', 'Diario')
    voucher_company_id = fields.Many2one('res.company', 'Compañía')

    def _auto_init(self):
        tools.drop_view_if_exists(self._cr, 'account_voucher_report')
        self._cr.execute('''
            CREATE OR REPLACE VIEW account_voucher_report AS
            SELECT
                avl.id AS id,
                {uid} AS user_id,
                ru.partner_id AS salesman_id,
                -- aml.partner_id AS partner_id,
                rp.name AS partner_name,
                rp.vat AS partner_vat,
                am.team_id AS salesteam_id,
                am.name AS document_ref,
                am.invoice_date AS document_date,
                am.invoice_date_due AS document_date_due,
                av.voucher_date AS payment_date,
                (av.voucher_date - am.invoice_date_due) AS payment_days,
                avl.amount AS amount_paid_untaxed,

                av.name AS voucher_doc,
                av.state AS voucher_state,
                av.voucher_type AS voucher_type,
                av.partner_type AS partner_type,
                av.currency_id AS voucher_currency_id,
                av.journal_id AS voucher_journal_id,
                avl.company_id AS voucher_company_id
            FROM account_voucher_line AS avl
            LEFT JOIN account_voucher AS av ON av.id = avl.voucher_passive_id
											OR av.id = avl.voucher_active_id
											OR av.id = avl.voucher_reconcile_id
            LEFT JOIN account_move_line AS aml ON aml.id = avl.move_line_id
            LEFT JOIN account_move AS am ON am.id = aml.move_id
            LEFT JOIN res_users AS ru ON ru.id = am.invoice_user_id
            LEFT JOIN res_partner AS rp ON rp.id = aml.partner_id OR rp.id = av.partner_id

        '''.format(uid=self.env.user.id))
        return super(AccountVoucherReport, self)._auto_init()
