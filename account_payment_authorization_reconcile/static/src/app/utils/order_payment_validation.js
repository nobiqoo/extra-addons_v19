import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import OrderPaymentValidation from "@point_of_sale/app/utils/order_payment_validation";

patch(OrderPaymentValidation.prototype, {
    async isOrderValid(isForceValidate) {
        const missingAuthorizationNumber = this.order.payment_ids.find(
            (payment) => !payment.payment_method_id.is_cash_count && !payment.authorization_number
        );
        if (missingAuthorizationNumber) {
            this.pos.dialog.add(AlertDialog, {
                title: _t("Authorization Number required"),
                body: _t(
                    "Please enter the Authorization Number for the %s payment before validating the order.",
                    missingAuthorizationNumber.payment_method_id.name
                ),
            });
            return false;
        }
        return super.isOrderValid(...arguments);
    },
});
