import { registry } from "@web/core/registry";
import { FloatField } from "@web/views/fields/float/float_field";
import { formatFloat } from "@web/views/fields/formatters";

// Requerimiento "Estructura de calificación avanzada" (2.9.1): "El sistema
// deberá aplicar la configuración definida para el manejo y visualización
// de decimales." wk.grade.scales.grade_decimals ya redondea el valor
// guardado (models/grade_consolidated.py::_wk_calc_components), pero el
// widget "float" estándar siempre muestra 2 decimales fijos sin importar
// esa configuración. Este widget lee la cantidad de decimales desde OTRO
// campo del mismo registro (pasado por options.decimals_field, igual que
// "monetary" resuelve sus decimales desde currency_field) y la usa para
// formatear -no para redondear el valor, que ya llega redondeado del
// servidor-.
export class GradeFloatField extends FloatField {
    get digits() {
        const decimals = this.props.record.data[this.props.decimalsField];
        return [16, typeof decimals === "number" ? decimals : 2];
    }

    get formattedValue() {
        if (
            !this.props.formatNumber ||
            (this.props.inputType === "number" && !this.props.readonly && this.value)
        ) {
            return this.value;
        }
        return formatFloat(this.value, {
            digits: this.digits,
            minDigits: this.props.minDigits,
            field: this.props.record.fields[this.props.name],
            trailingZeros: this.props.trailingZeros,
        });
    }
}
GradeFloatField.props = {
    ...FloatField.props,
    decimalsField: { type: String },
};

registry.category("fields").add("wk_grade_float", {
    component: GradeFloatField,
    extractProps: ({ options }) => ({
        decimalsField: options.decimals_field,
        formatNumber: true,
        trailingZeros: true,
    }),
    supportedTypes: ["float"],
});
