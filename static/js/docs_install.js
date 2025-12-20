document.addEventListener("DOMContentLoaded", () => {
    const modal = document.getElementById("docsImageModal");
    if (!modal) return;
    const modalImg = modal.querySelector("[data-modal-image]");
    const modalCaption = modal.querySelector("[data-modal-caption]");
    const modalApi = window.bootstrap?.Modal;
    document.querySelectorAll("[data-docs-image]").forEach((btn) => {
        btn.addEventListener("click", (ev) => {
            ev.preventDefault();
            const img = btn.querySelector("img");
            const src = img ? img.src : "";
            const caption = btn.dataset.caption || (img ? img.alt : "");
            if (modalImg && src) {
                modalImg.src = src;
            }
            if (modalCaption) {
                modalCaption.textContent = caption;
            }
            if (modalApi) {
                modalApi.getOrCreateInstance(modal).show();
            }
        });
    });
});
