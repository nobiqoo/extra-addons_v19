/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { ProductLabelSectionAndNoteField } from "@account/components/product_label_section_and_note_field/product_label_section_and_note_field";

// Core always rebuilds the invoice line label as
// `product.display_name + "\n" + whatever the user types`, so anything typed
// by hand ends up stored with the product's name (and internal code) glued
// in front of it, on the invoice print included. Anker wants the label to be
// exactly what the user types, falling back to the product name only when
// the label is left empty.
patch(ProductLabelSectionAndNoteField.prototype, {
    parseLabel(value) {
        return value || this.productName;
    },
});
