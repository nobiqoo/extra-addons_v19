# -*- coding: utf-8 -*-

from odoo import models, fields, tools


class PygPositionReport(models.Model):
    _name = 'pyg.position.report'
    _auto = False
    _description = 'P&G por posición'

    type_doc = fields.Selection([
        ('entry', 'Journal Entry'),
        ('out_invoice', 'Customer Invoice'),
        ('out_refund', 'Customer Credit Note'),
        ('in_invoice', 'Vendor Bill'),
        ('in_refund', 'Vendor Credit Note'),
        ('out_receipt', 'Sales Receipt'),
        ('in_receipt', 'Purchase Receipt'),
    ], 'Tipo')
    document_ref = fields.Char('Nombre documento')
    document_date = fields.Date('Fecha')
    partner_name = fields.Char('Tercero')
    profit = fields.Float('Ingresos')
    loss = fields.Float('Egresos')
    profitability_company = fields.Float('Rentabilidad')
    profitability_doc = fields.Float('Rentabilidad ($ Doc)')
    profit_usd = fields.Float('Ingresos (USD)')
    loss_usd = fields.Float('Egresos (USD)')
    profitability_usd = fields.Float('Rentabilidad (USD)')
    detail = fields.Char('Detalle')
    currency = fields.Char('Moneda')
    rate = fields.Float('TRM', group_operator='count_distinct')
    trm_usd = fields.Float('TRM USD', group_operator='count_distinct')

    account_id = fields.Many2one('account.account', 'Cuenta')
    analytic_account_id = fields.Many2one('account.analytic.account', 'Cuenta analítica')
    company_id = fields.Many2one('res.company', 'Compañía')

    state = fields.Selection([
        ('draft', 'Borrador'),
        ('cancel', 'Cancelado'),
        ('posted', 'Publicado'),
    ], 'Estado')
    doc_origin = fields.Char('Origen')
    doc_destination = fields.Char('Destino')
    doc_motor = fields.Char('Motonave')
    doc_weight = fields.Char('Peso')
    doc_position = fields.Char('Posición')
    doc_hbl = fields.Char('HBL')
    doc_volume = fields.Char('Volumen')
    doc_eta = fields.Char('ETA')
    doc_salesman = fields.Char('Comercial')

    account_root_id = fields.Char(string='Raíz Cuenta', readonly=True)

    doc_code_cw = fields.Char('Código CW')
    document_id = fields.Many2one('account.move', 'Documento')
    inv_date = fields.Date('Fecha factura/Recibo')
    inv_date_due = fields.Date('Fecha vencimiento')
    doc_embarque = fields.Char('N° Embarque')
    doc_department_code = fields.Char('Código departamento')
    doc_etd = fields.Char('ETD')
    doc_ref = fields.Char('Referencia')
    doc_user = fields.Char('Vendedor')
    doc_team_id = fields.Many2one('crm.team', 'Equipo de ventas')
    doc_payment_mode_id = fields.Many2one('account.payment.mode', 'Modo de pago')
    doc_to_check = fields.Boolean('Para revisar')
    doc_payment_state = fields.Selection([
        ('not_paid', 'No pagadas'),
        ('in_payment', 'En proceso de pago'),
        ('paid', 'Pagado'),
        ('partial', 'Pagado parcialmente'),
        ('reversed', 'Revertido'),
        ('invoicing_legacy', 'Factura sistema anterior'),
    ], 'Estado de pago')
    doc_inv_status_dian = fields.Selection([
        ('Exitoso', 'Exitoso'),
        ('Fallida', 'Fallida'),
    ], 'Estado factura DIAN')
    doc_edi_state = fields.Selection([
        ('to_send', 'Por enviar'),
        ('sent', 'Enviado'),
        ('to_cancel', 'Por cancelar'),
        ('cancelled', 'Cancelado'),
    ], 'Factura electrónica')
    partner_vat = fields.Char('NIT')
    doc_journal_id = fields.Many2one('account.journal', 'Diario')

    def _auto_init(self):
        tools.drop_view_if_exists(self._cr, 'pyg_position_report')
        self._cr.execute('''
            CREATE OR REPLACE VIEW pyg_position_report AS
            SELECT
                doc_code_cw,
                document_id,
                inv_date,
                inv_date_due,
                doc_embarque,
                doc_department_code,
                doc_etd,
                doc_ref,
                doc_user,
                doc_team_id,
                doc_payment_mode_id,
                doc_to_check,
                doc_payment_state,
                doc_inv_status_dian,
                doc_edi_state,
                partner_vat,
                doc_journal_id,
                id,
                type_doc,
                document_ref,
                document_date,
                partner_name,
                profit,
                loss,
                profitability_company,
                profitability_doc,
                CASE WHEN currency = \'USD\' AND rate > 0 THEN profit / rate
                     WHEN trm_usd IS NOT NULL THEN profit * trm_usd
                     ELSE NULL END AS profit_usd,
                CASE WHEN currency = \'USD\' AND rate > 0 THEN loss / rate
                     WHEN trm_usd IS NOT NULL THEN loss * trm_usd
                     ELSE NULL END AS loss_usd,
                CASE WHEN currency = \'USD\' AND rate > 0 THEN profitability_company / rate
                     WHEN trm_usd IS NOT NULL THEN profitability_company * trm_usd
                     ELSE NULL END AS profitability_usd,
                currency,
                rate,
                1 / NULLIF(trm_usd, 0) AS trm_usd,
                account_id,
                analytic_account_id,
                detail,
                company_id,
                state,
                doc_origin,
                doc_destination,
                doc_motor,
                doc_weight,
                doc_position,
                doc_hbl,
                doc_volume,
                doc_eta,
                doc_salesman,
                account_root_id
            FROM (
                SELECT
                    aml.id AS id,
                    am.move_type AS type_doc,
                    am.name AS document_ref,
                    aml.date AS document_date,
                    rp.name AS partner_name,
                    aml.credit AS profit,
                    aml.debit AS loss,
                    aml.credit - aml.debit AS profitability_company,
                    aml.amount_currency * -1 AS profitability_doc,
                    rcr.rate AS trm_usd,
                    rc.name AS currency,
                    am.current_exchange_rate AS rate,
                    aml.account_id AS account_id,
                    CASE
                        WHEN aml.analytic_distribution IS NOT NULL
                             AND aml.analytic_distribution != \'{}\'::jsonb
                        THEN (
                            SELECT SPLIT_PART(key, \',\', 1)::integer
                            FROM jsonb_each_text(aml.analytic_distribution)
                            LIMIT 1
                        )
                        ELSE NULL
                    END AS analytic_account_id,
                    aml.company_id AS company_id,
                    aml.name AS detail,
                    am.state AS state,
                    am.origin AS doc_origin,
                    am.destination AS doc_destination,
                    am.motor_ship AS doc_motor,
                    am.text_weight AS doc_weight,
                    am.position AS doc_position,
                    am.hbl AS doc_hbl,
                    am.volume AS doc_volume,
                    am.eta AS doc_eta,
                    rps.name AS doc_salesman,
                    LEFT(aa.code_store->>'1', 2) AS account_root_id,
                    am.code_cw AS doc_code_cw,
                    am.id AS document_id,
                    am.invoice_date AS inv_date,
                    am.invoice_date_due AS inv_date_due,
                    am.shipmentid AS doc_embarque,
                    am.department_code AS doc_department_code,
                    am.etd AS doc_etd,
                    am.ref AS doc_ref,
                    rpu.name AS doc_user,
                    am.team_id AS doc_team_id,
                    am.payment_mode_id AS doc_payment_mode_id,
                    am.checked AS doc_to_check,
                    am.payment_state AS doc_payment_state,
                    \'\' AS doc_inv_status_dian,
                    NULL::varchar AS doc_edi_state,
                    rp.vat AS partner_vat,
                    am.journal_id AS doc_journal_id
                FROM account_move_line AS aml
                LEFT JOIN account_move AS am ON am.id = aml.move_id
                LEFT JOIN res_partner AS rp ON rp.id = aml.partner_id
                LEFT JOIN res_currency AS rc ON rc.id = am.currency_id
                LEFT JOIN account_account AS aa ON aa.id = aml.account_id
                LEFT JOIN res_partner AS rps ON rps.id = am.salesman_cw_id
                LEFT JOIN res_users AS ru ON ru.id = am.invoice_user_id
                LEFT JOIN res_partner AS rpu ON rpu.id = ru.partner_id
                LEFT JOIN res_currency_rate AS rcr ON rcr.currency_id = (
                    SELECT id FROM res_currency WHERE name = \'USD\'
                )
                AND rcr.name = aml.date
                AND rcr.company_id = aml.company_id
            ) AS o
        ''')
        return super()._auto_init()

    def generate_xlsx(self):
        return self.generate_report_file('xlsx')

    def generate_pdf(self):
        return self.generate_report_file('pdf')

    def generate_report_file(self, report_type='xlsx'):
        data = {}
        if report_type == 'xlsx':
            data = self.prepare_data()
            report_name = 'account_pyg.pyg_position_report_xlsx'
        if report_type == 'pdf':
            report_name = 'account_pyg.pyg_position_report_pdf'
        report = self.env.ref(report_name)
        return report.report_action(self, data=data)

    def prepare_data(self):
        data = {}
        for line in self:
            if line.analytic_account_id.id not in data:
                data[line.analytic_account_id.id] = {
                    'id': line.analytic_account_id.id,
                    'name': line.analytic_account_id and
                            line.analytic_account_id.name or
                            'Sin cuenta analítica',
                    'aml_id': line.id,
                    'line_ids': [],
                }
            type_doc_dict = dict(line.fields_get()['type_doc']['selection'])
            data_line = {
                'id': line.id,
                'type_doc': type_doc_dict.get(line.type_doc) or '',
                'move': line.document_ref or '',
                'date': line.document_date or False,
                'partner': line.partner_name or False,
                'profit': line.profit or 0.0,
                'loss': line.loss or 0.0,
                'profitability': line.profitability_company,
                'profitability_usd': line.profitability_usd,
                'profitability_doc': line.profitability_doc,
                'currency': line.currency or '',
                'rate': line.rate or 0.0,
                'detail': line.detail or '',
                'origin': line.doc_origin or '',
                'destination': line.doc_destination or '',
                'motor': line.doc_motor or '',
                'weight': line.doc_weight or '',
                'position': line.doc_position or '',
                'hbl': line.doc_hbl or '',
                'volume': line.doc_volume or '',
                'eta': line.doc_eta or '',
                'salesman': line.doc_salesman or '',
                'currency_id': line.company_id.sudo().currency_id,
            }
            data[line.analytic_account_id.id]['line_ids'].append(data_line)
        return {'account_ids': list(data.values())}

    def function_test(self):
        for record in self:
            print(record)
