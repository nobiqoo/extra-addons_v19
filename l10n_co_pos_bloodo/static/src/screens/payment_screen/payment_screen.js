/** @odoo-module */

import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";


patch(PaymentScreen.prototype, {
    toggleIsToEinvoice() {
        this.currentOrder.setToInvoice(false);
        this.currentOrder.set_to_einvoice(!this.currentOrder.is_to_einvoice());
    },
    toggleIsToInvoice() {
        this.currentOrder.set_to_einvoice(false);
        super.toggleIsToInvoice();
    },
    async _postPushOrderResolve(order, order_server_ids) {
        const invoice = await this.invoiceService.orm.call(
            "pos.order", 
            "get_invoice",
            [order_server_ids]
        );
        order.set_invoice(invoice);
        return super._postPushOrderResolve(...arguments);
    },
    async afterOrderValidation() {
        const invoice = await this.invoiceService.orm.call(
            "pos.order", 
            "get_invoice",
            [this.currentOrder.backendId ?? this.currentOrder.id]
        );
        if (Object.keys(invoice).length > 0) {
            this.currentOrder.set_invoice(invoice);
        }
        await super.afterOrderValidation(...arguments);
    },
});