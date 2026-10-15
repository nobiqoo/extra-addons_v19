/** @odoo-module **/

function setupLeaveFileToggle() {
    const leaveTypeSelect = document.getElementById("leave_type");
    const leaveFileContainer = document.getElementById("content-leave-file");

    if (!leaveTypeSelect || !leaveFileContainer) {
        return;
    }

    const toggleFileField = () => {
        const selectedOption = leaveTypeSelect.selectedOptions[0];
        const isFileRequired = selectedOption?.getAttribute("filerequired") === "True";
        leaveFileContainer.style.display = isFileRequired ? "block" : "none";
        const fileInput = leaveFileContainer.querySelector("input[type='file']");
        if (fileInput) {
            fileInput.required = isFileRequired;
        }
    };

    leaveTypeSelect.addEventListener("change", toggleFileField);
    toggleFileField();
}

// Este módulo va en web.assets_frontend, que el website carga de forma lazy
// cuando DOMContentLoaded ya disparó: hay que ejecutar directo si el DOM está listo.
if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", setupLeaveFileToggle);
} else {
    setupLeaveFileToggle();
}
