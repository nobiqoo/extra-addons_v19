/** @odoo-module */

import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { useService } from "@web/core/utils/hooks";
import { qrCodeSrc } from "@point_of_sale/utils";
import { patch } from "@web/core/utils/patch";
import { markup } from "@odoo/owl";


patch(PosOrder.prototype, {
    setup(vals) {
        super.setup(...arguments);

        this.to_einvoice = vals.to_einvoice || false;
        this.invoice = {};

        if ( this.config.default_check_invoice === 'invoice') {
            this.to_invoice = true;
            this.to_einvoice = false;
        }
        else if ( this.config.default_check_invoice === 'einvoice') {
            this.to_einvoice = true;
            this.to_invoice = false;
        }
    },
 
    /* --- e-Invoice --- */
    set_to_einvoice(to_einvoice) {
        this.assertEditable();
        this.to_einvoice = to_einvoice;
    },
    is_to_einvoice() {
        return this.to_einvoice;
    },
    // TODO: Esta funcion ya no existe 
    // export_as_JSON() {
    //     const json = super.export_as_JSON(...arguments);
    //     json.to_einvoice = this.to_einvoice ? this.to_einvoice : false;
    //     return json;
    // },
    // TODO: Esta funcion ya no existe 
    // init_from_JSON(json) {
    //     super.init_from_JSON(...arguments);
    //     this.to_einvoice = json.to_einvoice;
    //     this.invoice = json.invoice;
    // },
    set_invoice(invoice) {
        if (invoice && invoice.fe_url) {
            invoice.fe_qr_data = qrCodeSrc(String(invoice.fe_url));
            invoice.fe_notes_mk = markup(invoice.fe_notes);
        }
        this.invoice = invoice;
    },
    async get_invoice() {
        const response = await useService("orm").call(
            "pos.order", 
            "get_invoice",
            [this.backendId ?? this.id]
        );
        if ( response ) {
            return response;
        } else {
            return {};
        }
    },
});