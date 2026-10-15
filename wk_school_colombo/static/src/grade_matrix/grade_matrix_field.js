import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { Component } from "@odoo/owl";

// Vista matricial de solo lectura del Consolidado de notas (subtarea 8,
// escenario #16 / criterios de aceptación: "las columnas de componentes
// del consolidado se generan dinámicamente según la estructura aplicada a
// la clase... sin requerir la creación de nuevos campos técnicos
// específicos para cada componente"). No registra ni modifica ninguna
// calificación -el Consolidado nunca lo hace-, solo pinta en pantalla el
// mismo detalle por componente que ya usan los reportes Midterm/Final
// (wk.school.colombo.grade.consolidated.line.components_json, calculado
// en models/grade_consolidated.py::_wk_calc_components).
//
// Todas las líneas de una misma clase comparten el mismo orden de
// componentes (se arman iterando class_assignment_type_ids.sorted(...)
// igual para cada estudiante), así que las columnas se derivan de la
// primera línea y las demás solo se recorren con el mismo filtro.

const RESULT_LABELS = {
    pass: "Pass",
    fail: "Fail",
    pending: "Pendiente",
};

export class GradeMatrixField extends Component {
    static template = "wk_school_colombo.GradeMatrixField";
    static props = { ...standardFieldProps };

    get lines() {
        return this.props.record.data[this.props.name].records;
    }

    get cutsCount() {
        return this.props.record.data.cuts_count;
    }

    _parseComponents(line) {
        try {
            return JSON.parse(line.data.components_json || "[]");
        } catch {
            return [];
        }
    }

    get midtermColumns() {
        const first = this.lines[0];
        return first
            ? this._parseComponents(first).filter((c) => (c.weight_midterm || 0) > 0)
            : [];
    }

    get finalColumns() {
        if (this.cutsCount !== "2") {
            return [];
        }
        const first = this.lines[0];
        return first
            ? this._parseComponents(first).filter((c) => (c.weight_final || 0) > 0)
            : [];
    }

    get rows() {
        return this.lines.map((line) => {
            const components = this._parseComponents(line);
            return {
                id: line.id,
                studentName: line.data.student_id ? line.data.student_id.display_name : "",
                midtermCells: components.filter((c) => (c.weight_midterm || 0) > 0),
                finalCells: this.cutsCount === "2"
                    ? components.filter((c) => (c.weight_final || 0) > 0)
                    : [],
                midtermGrade: line.data.midterm_grade,
                finalGrade: line.data.final_grade,
                absenceHours: line.data.absence_hours,
                rankingBadge: line.data.ranking_badge,
                performanceRangeCode: line.data.performance_range_code,
                resultLabel: RESULT_LABELS[line.data.result] || line.data.result || "",
                resultClass: line.data.result === "pass" ? "text-success fw-bold"
                    : line.data.result === "fail" ? "text-danger fw-bold" : "",
            };
        });
    }

    cellValue(cell) {
        return cell.grade === null || cell.grade === undefined ? "—" : cell.grade;
    }
}

registry.category("fields").add("wk_grade_matrix", {
    component: GradeMatrixField,
    supportedTypes: ["one2many"],
});
