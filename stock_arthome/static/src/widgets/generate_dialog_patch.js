import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { x2ManyCommands } from "@web/core/orm_service";
import { getDataURLFromFile } from "@web/core/utils/urls";
import { getId } from "@web/model/relational_model/utils";
import { formatFloat } from "@web/views/fields/formatters";
import { GenerateDialog } from "@stock/widgets/generate_serial";
import { useRef, useState } from "@odoo/owl";

export const LOT_IMPORT_TEMPLATE_URL = "/stock_arthome/static/template/lot_import_template.xlsx";

patch(GenerateDialog.prototype, {
    setup() {
        super.setup();
        this.notification = useService("notification");
        this.lotImportTemplateUrl = LOT_IMPORT_TEMPLATE_URL;
        this.lotImportFile = useRef("lotImportFile");
        this.lotImport = useState({
            fileName: "",
            fileContent: false,
            preview: null,
            loading: false,
        });
        if (this.props.mode === "import") {
            this.size = "lg";
        }
    },

    formatLotImportQty(value) {
        return formatFloat(value, { digits: [16, 2] });
    },

    /** Contexto con los mismos valores por defecto que envía el asistente nativo. */
    _getLotImportContext() {
        const data = this.props.move.data;
        const context = this.props.move.context;
        return {
            ...context,
            default_product_id: data.product_id.id,
            default_location_dest_id: data.location_dest_id.id,
            default_location_id: data.location_id.id,
            default_tracking: data.has_tracking,
            default_uom_id: data.has_tracking === "lot" ? data.product_uom?.id : undefined,
            default_picking_type_id: context.default_picking_type_id || data.picking_type_id?.id,
            default_company_id: context.default_company_id || data.company_id?.id,
        };
    },

    /** Líneas que hoy tiene la ventana, incluidas las que aún no se han guardado. */
    _getLotImportCurrentLines() {
        return this.props.move.data.move_line_ids.records.map((record) => ({
            lot_name: record.data.lot_name || record.data.lot_id?.display_name || false,
            quantity: record.data.quantity || 0,
            product_uom_id: record.data.product_uom_id?.id || false,
        }));
    },

    async _fetchLotImport(apply) {
        const data = this.props.move.data;
        return this.orm.call("stock.move", "action_import_lot_line_vals_arthome", [
            this._getLotImportContext(),
            {
                lot_text: this.lotImport.fileContent ? "" : this.lots.el?.value || "",
                file_content: this.lotImport.fileContent,
                file_name: this.lotImport.fileName,
                keep_lines: this.keepLines.el.checked,
                current_lines: this._getLotImportCurrentLines(),
                demand: data.product_uom_qty,
                move_uom_id: data.product_uom?.id,
            },
            apply,
        ]);
    },

    _hasLotImportData() {
        return Boolean(this.lotImport.fileContent || (this.lots.el?.value || "").trim());
    },

    async onLotImportFileChange(ev) {
        const file = ev.target.files[0];
        this.lotImport.preview = null;
        if (!file) {
            this.onLotImportClearFile();
            return;
        }
        const dataUrl = await getDataURLFromFile(file);
        this.lotImport.fileContent = dataUrl.split(",")[1];
        this.lotImport.fileName = file.name;
    },

    onLotImportSelectFile() {
        this.lotImportFile.el.click();
    },

    onLotImportClearFile() {
        if (this.lotImportFile.el) {
            this.lotImportFile.el.value = "";
        }
        this.lotImport.fileContent = false;
        this.lotImport.fileName = "";
        this.lotImport.preview = null;
    },

    onLotImportInputChange() {
        this.lotImport.preview = null;
    },

    async onLotImportPreview() {
        if (!this._hasLotImportData()) {
            this.notification.add(_t("Upload a file or paste the lots and quantities to import."), {
                type: "warning",
            });
            return;
        }
        this.lotImport.loading = true;
        try {
            this.lotImport.preview = await this._fetchLotImport(false);
        } finally {
            this.lotImport.loading = false;
        }
    },

    async _onGenerate() {
        if (this.props.mode !== "import") {
            return super._onGenerate(...arguments);
        }
        if (!this.lotImport.preview) {
            return this.onLotImportPreview();
        }
        if (!this.lotImport.preview.valid_count) {
            this.notification.add(_t("There are no valid lines to import."), { type: "warning" });
            return;
        }
        this.lotImport.loading = true;
        try {
            // El servidor vuelve a validar y crea los lotes cuando la operación los muestra como registro.
            const result = await this._fetchLotImport(true);
            await this._applyLotImportLines(result.lines);
            if (result.error_count) {
                this.notification.add(
                    _t("%(valid)s lines imported, %(errors)s rows rejected.", {
                        valid: result.valid_count,
                        errors: result.error_count,
                    }),
                    { type: "warning" }
                );
            }
        } finally {
            this.lotImport.loading = false;
        }
        this.props.close();
    },

    async _applyLotImportLines(moveLineVals) {
        const lines = this.props.move.data.move_line_ids;
        const newLines = moveLineVals.map((values) =>
            lines._createRecordDatapoint(values, {
                mode: "readonly",
                virtualId: getId("virtual"),
                manuallyAdded: false,
            })
        );
        if (!this.keepLines.el.checked) {
            await lines._applyCommands(
                lines._currentIds.map((currentId) => [x2ManyCommands.DELETE, currentId])
            );
        }
        lines.records.push(...newLines);
        lines._commands.push(...newLines.map((record) => [x2ManyCommands.CREATE, record._virtualId]));
        lines._currentIds.push(...newLines.map((record) => record._virtualId));
        await lines._onUpdate();
    },
});
