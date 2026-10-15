import { BarcodeScanner } from "@barcodes/components/barcode_scanner";
import { BarcodeDialog } from '@web/core/barcode/barcode_dialog';
import { isDisplayStandalone } from "@web/core/browser/feature_detection";

export class StudentKioskBarcodeScanner extends BarcodeScanner {
    static props = {
        ...BarcodeScanner.props,
        barcodeSource: String,
        token: String,
    };
    static template = "wk_school_management.BarcodeScanner";
    setup() {
        super.setup();
        this.isDisplayStandalone = isDisplayStandalone();
        this.scanBarcode = () => scanBarcode(this.env, this.facingMode, this.props.token);
    }

    get facingMode() {
        if (this.props.barcodeSource == "front") {
            return "user";
        }
        return super.facingMode;
    }

    get installURL() {
        const url = `student_attendance/${this.props.token}`;
        return `/scoped_app?app_id=wk_school_management&path=${encodeURIComponent(url)}`;
    }

    async openMobileScanner() {
        let error = null;
        let barcode = null;
        try {
            barcode = await this.scanBarcode();
        } catch (err) {
            error = err.message;
        }

        if (barcode) {
            this.props.onBarcodeScanned(barcode);
            if ("vibrate" in window.navigator) {
                window.navigator.vibrate(100);
            }
        } else {
            this.notification.add(error || _t("Please, Scan again!"), {
                type: "warning",
            });
        }
    }
}

/**
 * Opens the BarcodeScanning dialog and begins code detection using the device's camera.
 *
 * @returns {Promise<string>} resolves when a {qr,bar}code has been detected
 */
export async function scanBarcode(env, facingMode = "environment", token) {
    let res;
    let rej;
    const promise = new Promise((resolve, reject) => {
        res = resolve;
        rej = reject;
    });
    env.services.dialog.add(BarcodeDialog, {
        facingMode,
        token: token,
        onResult: (result) => res(result),
        onError: (error) => rej(error),
    });
    return promise;
}