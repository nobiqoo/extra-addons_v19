/* Ajuste y ampliación del Histórico Académico del Estudiante (tarea 12438):
 * la pantalla "Historial académico" (TranscriptPage, OWL puro de
 * wk_school_management, sin vista XML ni modelo transient detrás) se
 * amplía con la misma técnica de gradesheet_patch.js (tarea 12436): se
 * reemplaza por completo el método que arma los datos al pulsar "Consultar
 * historial académico", para traer TODA la trayectoria del estudiante
 * (student.student.wk_fetch_academic_history) en vez de una sola
 * Programación académica, y se agrega la descarga del PDF ampliado. El
 * método/reporte de Webkul (fetch_transcript_record, usado también por el
 * portal del estudiante) no se toca. */
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { TranscriptPage } from "@wk_school_management/js/transcript";

patch(TranscriptPage.prototype, {
    setup() {
        super.setup();
        this.action = useService("action");
        this.state.wk_header = {};
        this.state.wk_rows = [];
        this.state.wk_selected_index = -1;
        this.state.wk_error = "";
    },

    async _fetch_transcript_record() {
        const studentEl = document.querySelector('#wk_student_selection');
        const studentId = studentEl ? parseInt(studentEl.value) : -1;
        if (!studentId || studentId === -1) {
            this.state.wk_error = "Seleccione un estudiante para continuar.";
            this.state.wk_rows = [];
            this.state.wk_header = {};
            this.state.wk_selected_index = -1;
            return;
        }
        const result = await this.orm.call(
            "student.student", "wk_fetch_academic_history", [studentId]);
        this.state.wk_error = "";
        this.state.wk_header = result.header;
        this.state.wk_rows = result.rows;
        this.state.wk_selected_index = result.rows.length ? 0 : -1;
    },

    _wk_select_row(index) {
        this.state.wk_selected_index = index;
    },

    async _wk_download_pdf() {
        const studentEl = document.querySelector('#wk_student_selection');
        const studentId = studentEl ? parseInt(studentEl.value) : -1;
        if (!studentId || studentId === -1) {
            this.state.wk_error = "Seleccione un estudiante para continuar.";
            return;
        }
        await this.action.doAction(
            "wk_school_colombo.report_academic_history_action",
            { additionalContext: { active_ids: [studentId] } });
    },
});
