/* Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>; ) */
/* See LICENSE file for full copyright and licensing details. */
/* License URL : <https://store.webkul.com/license.html/>; */
import { patch } from '@web/core/utils/patch';
import { PaymentForm } from '@payment/interactions/payment_form';

patch(PaymentForm.prototype, {
    _prepareTransactionRouteParams(providerId) {
        const transactionRouteParams = super._prepareTransactionRouteParams(...arguments);
        const searchParams = new URLSearchParams(window.location.search);
        let fee_slip_id = searchParams.has('fee_slip_id') ? parseInt(searchParams.get('fee_slip_id')) : 0
        return {
            ...transactionRouteParams,
            'fee_slip_id': fee_slip_id,
        };
    }
});