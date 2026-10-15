/** @odoo-module */

// import { BarcodeDialog } from '@web/core/barcode/barcode_dialog';
import { Component, onMounted, useRef, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { Dialog } from "@web/core/dialog/dialog";
import { BarcodeVideoScanner, isBarcodeScannerSupported } from '@web/core/barcode/barcode_video_scanner';

import { rpc } from "@web/core/network/rpc";

export class BarcodeInput extends Component {
    static template = "wk_school_management.BarcodeInput";
    static props = {
        onSubmit: Function,
        // dialogState: Object,
    };

    setup() {
        this.state = useState({
            barcode: false,
        });	
        this.barcodeManual = useRef('manualBarcode');
        // Autofocus processing was blocked because a document already has a focused element.
        onMounted(() => {
            this.barcodeManual.el.focus();
        });
        console.log("Dialog state in BarcodeInput:", this.props.dialogState);
    }

    /**
     * Called when press Enter after filling barcode input manually.
     *
     * @private
     * @param {KeyboardEvent} ev
     */
    _onKeydown(ev) {
        if (ev.key === "Enter" && this.state.barcode) {
            this.props.onSubmit(this.state.barcode);
            this.state.barcode = '';  // Clear input

        }
    }
    setResultData(data) {
        this.state.issued_books = data;
    }

    get issuedBooks() {
        return this.props.dialogState?.resultData?.issued_books || [];
    }
}


export class ManualBarcodeScanner extends Component {
    static template = "wk_school_management.ManualBarcodeScanner22";
    static components = {
        BarcodeVideoScanner,
        Dialog,BarcodeInput
    };
    static props = ["facingMode", "close", "onResult", "onError"];

    setup() {
        this.state = useState({
            barcodeScannerSupported: isBarcodeScannerSupported(),
            errorMessage: _t("Check your browser permissions"),
        });
        console.log('dfssdfsdxf', this.props)
        this.action = useService('action');
        this.specification = useState({
            issued_books : [],
            return_books : [],
            student_record : false,
            error : false,
        });
        console.log('--barcodeScannerSupported-',this.state.barcodeScannerSupported)
        this.onResult = this.onResult.bind(this);
    }

    /**
     * Detection success handler
     *
     * @param {string} result found code
     */

    async onResult(result) {
        console.log('rrrr', result)
        var barcode = result
        if (! this.specification.student_record){
            const res = await rpc('/student_transaction/scan_from_main_menu', { barcode });
            console.log('---res22',res)
            if (res && res.name){
                this.specification.student_record = res
                this.specification.error = false
            }
            else{
                this.specification.error = "Student record not found. Please check the barcode and try again"
                setTimeout(() => {
                    this.specification.error = false;
                }, 5000);
                // return false;
            }
        }
        else{
            var student = this.specification.student_record.id
            var issue_book = this.specification.issued_books
            const res = await rpc('/book_transaction/scan_from_main_menu', { barcode , student, issue_book});
            console.log('---res',res)
            const isAlreadyIssued = this.specification.issued_books.some(book => book.id === res.id);
            const isAlreadyReturned = this.specification.return_books.some(book => book.id === res.id);
    
            if (res && res.error_max_book){
                this.specification.error =  'Students are not allowed to take more than ' + res.max_book + ' books'
                setTimeout(() => {
                    this.specification.error = false;
                }, 5000);
            }
            if (res && res.other_user_book){
                this.specification.error =  'As this book is not assigned to ' + res.current_student +', therefore you are not authorised to return this book.'
                setTimeout(() => {
                    this.specification.error = false;
                }, 5000);
            }
            if (res && res.issued && !isAlreadyIssued) {
                this.specification.issued_books.push(res); 
                this.specification.error = false
            }
            if (res && res.return && !isAlreadyReturned) {
                this.specification.return_books.push(res); 
                this.specification.error = false
            }
            if (!res){
                this.specification.error = "No Book Found, Please Check"
            }
            if ((res.issued && isAlreadyIssued) || (res.return && isAlreadyReturned)) {
                return false;
            }
    
        }
        
    }  

     async submitData()
    {
        var issue_books = this.specification.issued_books
        var return_books = this.specification.return_books
        var student = this.specification.student_record.id
        console.log('issue book', issue_books)
        console.log('return_books book', return_books)
        const record = await rpc('/create/issue/return', { issue_books, return_books, student});
        console.log('record==',record)
        this.props.close();
        this.action.doAction(record);

    }

    onCloseModal()
    {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: 'wk.book.history',
            name: 'Book Requests',
            views: [[false, 'list'],[false, 'form']],
            domain: [["state", "=", 'issued']],
        });
        console.log('-')
        this.props.close()
    }

    removeButton(ev){
        const bookId = ev.target.dataset.bookId;
        this.specification.issued_books = this.specification.issued_books.filter(
        (book) => book.id !== parseInt(bookId)
    );  
    }

    removeRequest(ev){
        const bookId = ev.target.dataset.bookId;
        this.specification.return_books = this.specification.return_books.filter(
        (book) => book.id !== parseInt(bookId)
    );  
    }


    /**
     * Detection error handler
     *
     * @param {Error} error
     */
    onError(error) {
        this.state.barcodeScannerSupported = false;
        this.state.errorMessage = error.message;
    }
}

/**
 * Opens the BarcodeScanning dialog and begins code detection using the device's camera.
 *
 * @returns {Promise<string>} resolves when a {qr,bar}code has been detected
 */
export async function scanBarcode(env, facingMode = "environment") {
    let res;
    let rej;
    const promise = new Promise((resolve, reject) => {
        res = resolve;
        rej = reject;
    });
    env.services.dialog.add(ManualBarcodeScanner, {
        facingMode,
        onResult: (result) => res(result),
        onError: (error) => rej(error),
    });
    return promise;
}

