/** @odoo-module */
import { registry } from "@web/core/registry";
import { Component} from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { ManualBarcodeScanner } from "../manual_barcode/manual_barcode";

export class BarcodeScan1 extends Component {
    static components = {
    ...Component.components,
    ManualBarcodeScanner,
};

	setup() {
        this.orm = useService("orm");
		this.action = useService("action");
        this.dialogService = useService("dialog");
        this.notificationService = useService("notification");
        this.actionService = useService('action');
	}

    onClickBackToDashboard() {
        this.actionService.doAction('wk_school_management.wk_action_dashboard');
    }

    openManualBarcodeDialog() {
        let res;
        let rej;
        const promise = new Promise((resolve, reject) => {
            res = resolve;
            rej = reject;
        });
        this.dialogService.add(ManualBarcodeScanner, {
            facingMode: "environment",
            onResult: (barcode) => {
                this._onBarcodeScanned(barcode);
                res(barcode);
            },
            onError: (error) => rej(error),
        });
        promise.catch(error => console.log(error))
        return promise;
    }

    async _onBarcodeScanned(barcode) {
    }

}

BarcodeScan1.template = 'wk_school_management.BarcodeScan'
registry.category("actions").add('action_lib_barcode', BarcodeScan1)

