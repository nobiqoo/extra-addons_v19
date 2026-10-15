/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";

/**
 * Tras guardar un product.template, se consulta al servidor si el producto está
 * vinculado a otras compañías y si algún campo maestro quedó divergente. En ese caso
 * el servidor devuelve la acción del asistente de sincronización.
 *
 * La comparación se hace en el servidor a propósito: así no dependemos de la API
 * interna de OWL para saber qué campos quedaron sucios, y solo se abre el asistente
 * cuando hay una diferencia real con las réplicas.
 */
patch(FormController.prototype, {
    async save(params) {
        const saved = await super.save(params);
        if (!saved || this.props.resModel !== "product.template") {
            return saved;
        }
        const resId = this.model.root.resId;
        if (!resId) {
            return saved;
        }
        try {
            const action = await this.orm.call(
                "product.template",
                "action_check_replica_sync",
                [[resId]]
            );
            if (action) {
                await this.action.doAction(action);
            }
        } catch {
            // Un fallo comprobando la sincronización no debe invalidar el guardado.
        }
        return saved;
    },
});
