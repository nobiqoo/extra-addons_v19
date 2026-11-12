"""Ejecutar con odoo-bin shell -d arthome < este_archivo.
Crea una compañía de demostración completa en una sola transacción.
No envía correos ni documentos electrónicos. Repetir no duplica los datos.
"""
from odoo import Command
import json

assert env.cr.dbname == 'arthome', 'Este ejemplo está preparado para la base local arthome.'
company_name = 'PRUEBA — Presupuestos Arthome'
company = env['res.company'].search([('name', '=', company_name)], limit=1)
if company:
    print('Los datos ya existen. Compañía:', company.id)
else:
    quiet = dict(tracking_disable=True, mail_create_nosubscribe=True, mail_notrack=True,
                 no_reset_password=True, mail_notify_force_send=False)
    company = env['res.company'].with_context(**quiet).create({
        'name': company_name, 'currency_id': env.ref('base.COP').id,
    })
    env.ref('base.user_admin').write({'company_ids': [Command.link(company.id)]})
    demo = env(context=dict(env.context, **quiet, allowed_company_ids=[company.id]), su=True)

    def account(code, name, kind, reconcile=False):
        return demo['account.account'].create({'code': code, 'name': 'PRUEBA ' + name,
            'account_type': kind, 'reconcile': reconcile, 'company_ids': [Command.set(company.ids)]})

    receivable = account('130505', 'Clientes', 'asset_receivable', True)
    payable = account('220505', 'Proveedores', 'liability_payable', True)
    income = account('413505', 'Ventas', 'income')
    cash = account('111005', 'Banco simulado', 'asset_cash')
    outstanding = account('111010', 'Recaudos pendientes', 'asset_current', True)
    sale_journal = demo['account.journal'].create({'name': 'PRUEBA Ventas', 'code': 'PVTA',
        'type': 'sale', 'company_id': company.id, 'default_account_id': income.id,
        'is_einvoicing': False})
    bank_journal = demo['account.journal'].create({'name': 'PRUEBA Banco simulado', 'code': 'PBAN',
        'type': 'bank', 'company_id': company.id, 'default_account_id': cash.id})
    for journal in sale_journal | bank_journal:
        journal.create_journal_sequence()
    bank_journal.inbound_payment_method_line_ids.write({'payment_account_id': outstanding.id})

    category_names = ['Colchón', 'Tapicería', 'Cama', 'Colchón Premium', 'Industrial', 'Cortinería']
    products = []
    for name in category_names:
        category = demo['product.category'].create({'name': 'PRUEBA ' + name,
            'property_account_income_categ_id': income.id})
        products.append(demo['product.product'].create({'name': 'PRUEBA ' + name,
            'type': 'service', 'categ_id': category.id, 'company_id': company.id,
            'list_price': 100000, 'taxes_id': [Command.clear()], 'supplier_taxes_id': [Command.clear()],
            'property_account_income_id': income.id}))
    north = demo['crm.team'].create({'name': 'PRUEBA Equipo Norte', 'company_id': company.id,
                                   'user_id': env.ref('base.user_admin').id})
    coast = demo['crm.team'].create({'name': 'PRUEBA Equipo Costa', 'company_id': company.id,
                                   'user_id': env.ref('base.user_admin').id})
    budgets = demo['sale.budget.monthly']
    cases = [
        ('Camila Restrepo', 'camila', north, 'Bogotá', 60800000, 8000000, 6300000, False,
         [20300000,12900000,7400000,9600000,4900000,3100000]),
        ('Andrés Pérez', 'andres', coast, 'Barranquilla', 80000000, 10000000, 10500000, False,
         [28000000,18000000,13000000,12000000,8000000,5000000]),
        ('Canal Institucional', 'institucional', north, 'Bogotá', 40000000, 5000000, 2500000, True,
         [28000000,0,0,0,0,0]),
    ]
    for name, login, team, city, target, collection_target, collection, unified, sales in cases:
        seller = demo['res.users'].create({'name': 'PRUEBA ' + name,
            'login': 'prueba_ppto_' + login, 'company_id': company.id,
            'company_ids': [Command.set(company.ids)],
            'group_ids': [Command.set([env.ref('sales_team.group_sale_salesman').id])]})
        demo['crm.team.member'].create({'crm_team_id': team.id, 'user_id': seller.id})
        partner = demo['res.partner'].create({'name': 'PRUEBA Cliente ' + name,
            'company_id': company.id, 'customer_rank': 1,
            'property_account_receivable_id': receivable.id, 'property_account_payable_id': payable.id})
        budget = demo['sale.budget.monthly'].create({'user_id': seller.id, 'company_id': company.id,
            'team_id': team.id, 'zone': city, 'city': city, 'date_start': '2026-09-01',
            'amount_total_budget': target, 'cartera_budget': collection_target,
            'allocation_mode': 'global' if unified else 'category',
            'notes': 'DATOS DE PRUEBA. Septiembre 2026. No representan operaciones reales.',
            'line_ids': [] if unified else [Command.create({'category_id': p.categ_id.id,
                'percent_allocation': percent, 'reference_unit_price': 100000,
                'uom_id': p.uom_id.id}) for p, percent in zip(products, [35,20,15,15,10,5])]})
        budget.action_generate_weeks()

        def invoice(date, amounts, ref, move_type='out_invoice', due=None):
            move = demo['account.move'].create({'company_id': company.id, 'journal_id': sale_journal.id,
                'move_type': move_type, 'partner_id': partner.id, 'invoice_user_id': seller.id,
                'team_id': team.id, 'invoice_date': date, 'date': date,
                'invoice_date_due': due or date, 'ref': 'PRUEBA PPTO ' + login + ' ' + ref,
                'invoice_line_ids': [Command.create({'product_id': p.id, 'name': p.name,
                    'account_id': income.id, 'quantity': 1, 'price_unit': amount,
                    'tax_ids': [Command.clear()]}) for p, amount in zip(products, amounts) if amount]})
            move.action_post()
            return move

        overdue = invoice('2026-08-20', [max(collection_target, collection) + 2000000],
                          'Cartera inicial', due='2026-08-30')
        for day, factor in [(7,0.3),(10,0.3),(13,0.4)]:
            invoice('2026-09-%02d' % day, [round(a*factor,2) for a in sales], 'Venta día %s' % day)
        if login == 'camila':
            invoice('2026-09-14', [500000], 'Nota crédito', move_type='out_refund')
        # Create a standalone payment, then reconcile it. The local sequence
        # addon rejects the wizard's second post of an already generated payment.
        payment = demo['account.payment'].create({
            'journal_id': bank_journal.id, 'company_id': company.id,
            'partner_id': partner.id, 'partner_type': 'customer', 'payment_type': 'inbound',
            'date': '2026-09-14', 'amount': collection, 'currency_id': company.currency_id.id,
            'payment_method_line_id': bank_journal.inbound_payment_method_line_ids[:1].id,
            'memo': 'PRUEBA Recaudo ' + name})
        payment.action_post()
        assert payment.move_id.state == 'posted'
        (overdue.line_ids | payment.move_id.line_ids).filtered(
            lambda line: line.account_id == receivable and not line.reconciled).reconcile()
        budget.action_confirm()
        budgets |= budget
    demo.flush_all()
    result = []
    for budget, case in zip(budgets, cases):
        expected = sum(case[-1]) - (500000 if case[1] == 'camila' else 0)
        assert abs(budget.amount_real_sales - expected) < .01
        assert abs(budget.cartera_real_collected - case[6]) < .01
        result.append({'id': budget.id, 'asesor': budget.user_id.name, 'meta': budget.amount_total_budget,
                       'venta': budget.amount_real_sales, 'recaudo': budget.cartera_real_collected})
    dashboard = demo['sale.budget.monthly'].get_dashboard('2026-09-01')
    assert dashboard['count'] == 3
    assert abs(dashboard['real'] - 169700000) < .01
    env.cr.commit()
    print(json.dumps({'company_id': company.id, 'budgets': result}, ensure_ascii=False, indent=2))
