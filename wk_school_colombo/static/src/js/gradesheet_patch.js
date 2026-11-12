/* Ajuste y ampliación de Reportes Académicos: agrega el botón "Generar
 * Class List" a la pantalla de Hoja de calificaciones (OWL puro de
 * wk_school_management, sin vista XML ni modelo transient detrás), que
 * abre el wizard wk.school.colombo.class.list.wizard con la Clase ofertada
 * ya seleccionada en esa misma pantalla. */
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { GradesheetPage } from "@wk_school_management/js/gradesheet";

patch(GradesheetPage.prototype, {
    setup() {
        super.setup();
        this.action = useService("action");
    },

    async _wk_generate_class_list() {
        const classDropdown = document.querySelector('#class_selection');
        const populateClassId = classDropdown ? parseInt(classDropdown.value) : -1;
        if (!populateClassId || populateClassId === -1) {
            const tableHeader = document.querySelector('.table_header');
            const errorMessage = document.querySelector('.error_message');
            this.state.error_message = "Seleccione primero una Clase ofertada";
            if (tableHeader) {
                tableHeader.classList.remove("d-none");
            }
            if (errorMessage) {
                errorMessage.classList.remove("d-none");
            }
            return;
        }
        await this.action.doAction("wk_school_colombo.class_list_wizard_action", {
            additionalContext: { default_populate_class_id: populateClassId },
        });
    },
});
