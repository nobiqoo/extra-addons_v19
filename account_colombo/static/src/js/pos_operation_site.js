import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/services/pos_store";

/**
 * ReteICA por sede en el punto de venta (tarea 10340).
 *
 * Cada línea nueva nace con los impuestos del producto más el ReteICA de la
 * sede configurada en la caja. Se hace en el frontend a propósito: el ticket y
 * el pedido que se sincroniza deben calcular lo mismo, y si el impuesto se
 * agregara solo en el servidor los totales del navegador y los del asiento
 * contable quedarían descuadrados al cerrar la sesión.
 */
patch(PosStore.prototype, {
    async addLineToOrder(vals, order, opts = {}, configure = true) {
        const reteica = this.config.reteica_tax_id;
        // Si la llamada ya trae impuestos explícitos (devoluciones, combos,
        // líneas creadas por otros módulos) no se toca nada.
        if (reteica && !("tax_ids" in vals)) {
            let productTemplate = vals.product_tmpl_id;
            if (typeof productTemplate === "number") {
                productTemplate = this.data.models["product.template"].get(productTemplate);
            }
            const taxes = [...(productTemplate?.taxes_id || [])];
            if (!taxes.includes(reteica)) {
                taxes.push(reteica);
            }
            vals = { ...vals, tax_ids: taxes.map((tax) => ["link", tax]) };
        }
        return await super.addLineToOrder(vals, order, opts, configure);
    },
});
