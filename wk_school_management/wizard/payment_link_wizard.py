# -*- coding: utf-8 -*-
#################################################################################
#
# Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>; )
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>;
#
#################################################################################

from odoo import models


class PaymentLinkWizard(models.TransientModel):
    _inherit = 'payment.link.wizard'
    _description = 'Generate Fee Slip Payment Link'

    def _prepare_query_params(self, *args):
        res = super()._prepare_query_params(*args)
        if self.res_model != 'wk.fee.slip':
            return res

        return {
            'amount': self.amount,
            'access_token': self._prepare_access_token(),
            'fee_slip_id': self.res_id,
        }
