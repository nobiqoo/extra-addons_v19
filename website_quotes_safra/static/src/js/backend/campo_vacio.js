/** Campos numéricos que admiten vacío (FloatVacio e IntegerVacio en
 * models/fields_vacio.py).
 *
 * Odoo convierte una casilla numérica vacía en 0 y, al confirmarla con Tab
 * o Enter, da por iguales el 0 y el vacío. En los campos marcados
 * `safra_vacio`: la casilla vacía queda vacía (false), un registro nuevo
 * arranca vacío y pasar de vacío a 0 (o de 0 a vacío) sí es un cambio.
 */
import { patch } from "@web/core/utils/patch";
import { useEffect, useState } from "@odoo/owl";
import { FloatField } from "@web/views/fields/float/float_field";
import { IntegerField } from "@web/views/fields/integer/integer_field";
import { parseInteger } from "@web/views/fields/parsers";
import { useInputField } from "@web/views/fields/input_field_hook";
import { useNumpadDecimal } from "@web/views/fields/numpad_decimal_hook";
import { Record } from "@web/model/relational_model/record";

function esVacio(component) {
    const field = component.props.record.fields[component.props.name];
    return Boolean(field && field.safra_vacio);
}

function sinTexto(value) {
    return !String(value ?? "").trim();
}

/** Odoo no registra el paso entre vacío y 0 (los da por iguales): se
 * registra aquí al salir de la casilla. */
function useCambioVacioCero(component) {
    useEffect(
        (el) => {
            if (!el) {
                return;
            }
            const sync = () => {
                let val;
                try {
                    val = component.parse(el.value);
                } catch {
                    return;
                }
                const actual = component.props.record.data[component.props.name];
                if ((val === 0 && actual === false) || (val === false && actual === 0)) {
                    component.props.record.update({ [component.props.name]: val });
                }
            };
            const onKeydown = (ev) => {
                if (ev.key === "Tab" || ev.key === "Enter") {
                    sync();
                }
            };
            el.addEventListener("change", sync, true);
            el.addEventListener("keydown", onKeydown, true);
            return () => {
                el.removeEventListener("change", sync, true);
                el.removeEventListener("keydown", onKeydown, true);
            };
        },
        () => [component.inputRef.el]
    );
}

patch(FloatField.prototype, {
    setup() {
        super.setup();
        if (esVacio(this)) {
            useCambioVacioCero(this);
        }
    },

    parse(value) {
        if (esVacio(this) && sinTexto(value)) {
            return false;
        }
        return super.parse(value);
    },
});

patch(IntegerField.prototype, {
    setup() {
        if (!esVacio(this)) {
            return super.setup();
        }
        // El mismo setup de Odoo, con un parse que deja la casilla vacía.
        this.state = useState({ hasFocus: false });
        this.inputRef = useInputField({
            getValue: () => this.formattedValue,
            refName: "numpadDecimal",
            parse: (v) => this.parse(v),
        });
        useNumpadDecimal();
        useCambioVacioCero(this);
    },

    parse(value) {
        if (sinTexto(value)) {
            return false;
        }
        return parseInteger(value, { allowOperation: true });
    },
});

patch(Record.prototype, {
    _getDefaultValues(fieldNames = this.fieldNames) {
        const values = super._getDefaultValues(fieldNames);
        for (const name of fieldNames) {
            if (this.fields[name] && this.fields[name].safra_vacio) {
                values[name] = false;
            }
        }
        return values;
    },
});
