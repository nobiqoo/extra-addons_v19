/** @odoo-module */

import { SelectLotPopup } from "@point_of_sale/app/components/popups/select_lot_popup/select_lot_popup";
import { patch } from "@web/core/utils/patch";

patch(SelectLotPopup.prototype, {
    getSources() {
        const sources = super.getSources();
        for (const source of sources) {
            const baseOptions = source.options;
            source.optionSlot = "lotOptionSlot";
            source.options = (currentInput) => {
                return baseOptions(currentInput).map((result) => {
                    const lot = this.props.options.find((opt) => opt.name === result.label);
                    return { ...result, data: { notePlain: lot?.note_plain || "" } };
                });
            };
        }
        return sources;
    },
});
