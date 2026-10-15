
from odoo import api, models, fields


class AccountGroup(models.Model):
    _inherit = 'account.group'

    code = fields.Char(required=False)
    child_ids = fields.One2many('account.group', 'parent_id')

    def update_compute_accounts_ids(self):
        for record in self:
            record._compute_group_accounts()

    @api.depends(
        "code_prefix_start",
        "code_prefix_end",
        "account_ids",
        "account_ids.code",
        "group_child_ids",
        "group_child_ids.account_ids.code",
    )
    def _compute_group_accounts(self):
        account_obj = self.env["account.account"]
        for record in self:
            prefix_start = record.code_prefix_start
            prefix_end = record.code_prefix_end
            if prefix_end and prefix_start:
                accounts = account_obj.with_company(record.company_id.id).search(
                    [('company_id', '=', record.company_id.id)]).filtered(lambda x: x.code != False)
                codes_accounts = [x.with_company(record.company_id.id).code for x in accounts]
                order_accounts = sorted(codes_accounts)
                len_prefix = len(prefix_start) > len(prefix_end) and \
                    len(prefix_start) or \
                    len(prefix_end)
                prefix_start = (prefix_start + ('0'*len_prefix))[:len_prefix]
                prefix_end = (prefix_end + ('9'*len_prefix))[:len_prefix]
                acc_start = []
                while not acc_start:
                    acc_start = list(filter(
                        lambda x: x.startswith(prefix_start),
                        order_accounts
                    ))
                    if not acc_start:
                        prefix_start = str(int(prefix_start) + 1)
                    if int(prefix_start) > int(prefix_end):
                        break
                acc_end = []
                while not acc_end:
                    acc_end = list(filter(
                        lambda x: x.startswith(prefix_end),
                        order_accounts
                    ))
                    if not acc_end:
                        prefix_end = int(prefix_end) - 1
                        prefix_end = (
                            '{:0%sd}' % len_prefix).format(prefix_end)
                    if int(prefix_start) > int(prefix_end):
                        break
                if acc_start and acc_end:
                    index_start = order_accounts.index(acc_start[0])
                    index_end = order_accounts.index(acc_end[-1])
                    acc_to_add = order_accounts[index_start:index_end+1]
                    acc_to_add_ids = accounts.filtered(
                        lambda x: x.code in acc_to_add)
                    record.compute_account_ids = [(6, 0, acc_to_add_ids.ids)]
                else:
                    record.compute_account_ids = [(6, 0, [])]
            else:
                record.compute_account_ids = [(6, 0, [])]
