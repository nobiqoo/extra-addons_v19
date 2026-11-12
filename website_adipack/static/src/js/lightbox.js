/** @odoo-module **/

// Visor de imágenes para las galerías del sitio Adipack (enlaces .o_adp_lightbox).

function openLightbox(links, index) {
    const overlay = document.createElement("div");
    overlay.className = "o_adp_lightbox_overlay";
    overlay.innerHTML = `
        <button type="button" class="o_adp_lb_close" aria-label="Cerrar">&times;</button>
        <button type="button" class="o_adp_lb_prev" aria-label="Anterior">&#8249;</button>
        <img alt=""/>
        <button type="button" class="o_adp_lb_next" aria-label="Siguiente">&#8250;</button>`;
    const img = overlay.querySelector("img");
    const show = (i) => {
        index = (i + links.length) % links.length;
        img.src = links[index].getAttribute("href");
    };
    const close = () => {
        overlay.remove();
        document.removeEventListener("keydown", onKey);
    };
    const onKey = (ev) => {
        if (ev.key === "Escape") {
            close();
        } else if (ev.key === "ArrowLeft") {
            show(index - 1);
        } else if (ev.key === "ArrowRight") {
            show(index + 1);
        }
    };
    if (links.length < 2) {
        overlay.querySelector(".o_adp_lb_prev").remove();
        overlay.querySelector(".o_adp_lb_next").remove();
    }
    overlay.addEventListener("click", (ev) => {
        if (ev.target.closest(".o_adp_lb_prev")) {
            show(index - 1);
        } else if (ev.target.closest(".o_adp_lb_next")) {
            show(index + 1);
        } else if (ev.target !== img) {
            close();
        }
    });
    document.addEventListener("keydown", onKey);
    show(index);
    document.body.appendChild(overlay);
}

document.addEventListener("click", (ev) => {
    const link = ev.target.closest && ev.target.closest("a.o_adp_lightbox");
    // En modo edición no se abre el visor
    if (!link || link.closest(".o_editable")) {
        return;
    }
    ev.preventDefault();
    const group = link.closest(".o_adp_gallery, .o_adp_carousel") || link.parentElement;
    const links = [...group.querySelectorAll("a.o_adp_lightbox")];
    openLightbox(links, Math.max(0, links.indexOf(link)));
});
