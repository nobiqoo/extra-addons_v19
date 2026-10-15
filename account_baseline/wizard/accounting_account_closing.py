# -*- coding: utf-8 -*-

from odoo import _, fields, models
from odoo.exceptions import UserError


ACCOUNT_DOMAIN = "[('account_type', 'not in', ('asset_receivable','liability_payable','asset_cash','liability_credit_card','off_balance'))]"


class AccountingAccountClosing(models.TransientModel):
    _name = 'account.accounting.closing'
    _description = 'Accounting Closing'

    account_id = fields.Many2one(
        comodel_name='account.account',
        domain=ACCOUNT_DOMAIN
    )
    accounts_ids = fields.Many2many(
        comodel_name='account.account',
        domain=ACCOUNT_DOMAIN
    )

    company_id = fields.Many2one(
        comodel_name='res.company',
        default=lambda self: self.env.company
    )

    closing_type = fields.Selection(
        selection=[
            ('none', 'Only One'),
            ('account', 'By Account'),
            ('partner', 'By Partner'),
        ],
        required=True,
        default='none'
    )

    date = fields.Date(default=fields.Date.today())
    date_end = fields.Date()
    date_start = fields.Date()

    journal_id = fields.Many2one('account.journal')

    move_post = fields.Boolean()

    partner_id = fields.Many2one('res.partner')
    partners_ids = fields.Many2many('res.partner')

    def action_query(self, accounts, partners):
        query = """
            select
                account_id,
                partner_id,
                sum(debit) as debit,
                sum(credit) as credit
            from
                account_move_line
            where
                parent_state = 'posted'
                and company_id = %s
                and date between '%s' and '%s'
        """ % (
            self.company_id.id,
            fields.Date.to_string(self.date_start),
            fields.Date.to_string(self.date_end)
        )

        if accounts:
            query += """
                    and account_id in (%s)
            """ % ','.join(str(a.id) for a in accounts)

        if partners:
            query += """
                    and partner_id in (%s)
            """ % ','.join(str(p.id) for p in partners)

        query += """
            group by
                account_id,
                partner_id;
        """

        self._cr.execute(query)
        return self._cr.dictfetchall()

    def action_confirm(self):
        self.ensure_one()

        if not self.accounts_ids and not self.partners_ids:
            raise UserError(_('You must select account or partner'))

        lines = self.action_query(self.accounts_ids, self.partners_ids)
        lines = [l for l in lines if (l.get('debit') - l.get('credit')) != 0]

        move_ids = self.action_move(lines)

        return {
            'type': 'ir.actions.act_window',
            'name': _('Journal Entries'),
            'res_model': 'account.move',
            # 'view_type': 'form',
            'views': [[self.env.ref('account.view_move_tree').id, 'list'], [False, 'kanban'], [False, 'form']],
            'view_mode': 'list,kanban,form',
            'view_id': self.env.ref('account.view_move_tree').id,
            'search_view_id': self.env.ref('account.view_account_move_filter').id,
            'context': {'default_move_type': 'entry', 'search_default_misc_filter': 1, 'view_no_maturity': True},
            'domain': [('id', 'in', move_ids)],
            # 'target': 'new',
            # 'res_id': self.id,
        }

    def action_move(self, lines):
        Account = self.env['account.account']
        Move = self.env['account.move']
        Partner = self.env['res.partner']

        amoves = []
        if self.closing_type == 'account':
            account_ids = list(set([l.get('account_id') for l in lines]))
            for account_id in account_ids:
                account = Account.browse(account_id)
                alines = [
                    l for l in lines if l.get('account_id') == account_id
                ]
                amoves.append({
                    'name': account.display_name,
                    'lines': alines
                })
        elif self.closing_type == 'partner':
            partner_ids = list(set([l.get('partner_id') for l in lines]))
            for partner_id in partner_ids:
                partner = Partner.browse(partner_id)
                plines = [
                    l for l in lines if l.get('partner_id') == partner_id
                ]
                amoves.append({
                    'name': partner.display_name,
                    'lines': plines
                })
        else:
            amoves.append({'lines': lines})

        move_ids = []
        for amove in amoves:
            line_ids = []
            alines = amove.get('lines', [])
            for aline in alines:
                residual = aline.get('debit') - aline.get('credit')
                account = Account.browse(aline.get('account_id'))
                partner = Partner.browse(aline.get('partner_id'))
                name = _('Account: %s, Partner: %s')

                line_ids.append(
                    (0, 0, {
                        'account_id': aline.get('account_id'),
                        'partner_id': aline.get('partner_id'),
                        'name': name % (self.account_id.code, self.partner_id.name),
                        'debit': -residual if residual < 0 else 0,
                        'credit': residual if residual > 0 else 0,
                    })
                )
                line_ids.append(
                    (0, 0, {
                        'account_id': self.account_id.id,
                        'partner_id': self.partner_id.id,
                        'name': name % (account.code, partner.name),
                        'debit': residual if residual > 0 else 0,
                        'credit': -residual if residual < 0 else 0,
                    })
                )

            move_vals = {
                'move_type': 'entry',
                'ref': _('Accounting Closing %s') % amove.get('name', ''),
                'date': self.date,
                'journal_id': self.journal_id.id,
                'line_ids': line_ids
            }
            move = Move.create(move_vals)
            if self.move_post:
                move.action_post()
            move_ids.append(move.id)

        return move_ids
