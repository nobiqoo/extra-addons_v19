import { patch } from "@web/core/utils/patch";
import { PosPayment } from "@point_of_sale/app/models/pos_payment";

patch(PosPayment.prototype, {
    setAuthorizationNumber(value) {
        this.pos_order_id.assertEditable();
        this.authorization_number = value;
    },
});
