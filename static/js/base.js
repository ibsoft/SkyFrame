(function () {
    const pwaPromptBar = document.querySelector(".pwa-prompt");
    const pwaPromptCenter = document.getElementById("pwa-prompt-center");
    const pwaCloseBtn = pwaPromptCenter?.querySelector("[data-dismiss-pwa]");
    const serviceWorkerUrl = document.body?.dataset?.serviceWorker;

    const installApp = async () => {
        const promptEvent = window.deferredPrompt;
        if (!promptEvent) return;
        promptEvent.prompt();
        await promptEvent.userChoice;
        window.deferredPrompt = null;
        if (pwaPromptBar) {
            pwaPromptBar.classList.add("d-none");
        }
        if (pwaPromptCenter) {
            pwaPromptCenter.classList.add("d-none");
        }
        localStorage.setItem("pwaPrompted", "1");
    };

    window.addEventListener("beforeinstallprompt", (e) => {
        e.preventDefault();
        window.deferredPrompt = e;
        if (pwaPromptBar) {
            pwaPromptBar.classList.remove("d-none");
        }
        if (pwaPromptCenter) {
            pwaPromptCenter.classList.remove("d-none");
        }
    });

    document.addEventListener("click", (ev) => {
        if (ev.target.matches("[data-install-pwa]")) {
            installApp();
        }
        if (ev.target.matches("[data-dismiss-pwa]")) {
            pwaPromptCenter?.classList.add("d-none");
            localStorage.setItem("pwaPrompted", "1");
        }
    });

    if ("serviceWorker" in navigator && serviceWorkerUrl) {
        navigator.serviceWorker.register(serviceWorkerUrl).catch(() => {});
    }

    const shouldShowPwaPrompt = () => {
        const isStandalone =
            window.matchMedia("(display-mode: standalone)").matches || window.navigator.standalone;
        if (isStandalone) return false;
        if (localStorage.getItem("pwaPrompted")) return false;
        const isMobile = /Mobi|Android|iPhone|iPad|iPod/i.test(navigator.userAgent || "");
        return isMobile;
    };

    if (shouldShowPwaPrompt() && pwaPromptCenter) {
        pwaPromptCenter.classList.remove("d-none");
    }

    document.addEventListener("DOMContentLoaded", () => {
        const toasts = document.querySelectorAll(".toast");
        toasts.forEach((toastEl) => {
            const delay = Number(toastEl.dataset.bsDelay) || 4000;
            const toast = new bootstrap.Toast(toastEl, {
                autohide: true,
                delay,
            });
            const progress = toastEl.querySelector(".toast-progress");
            if (progress) {
                requestAnimationFrame(() => {
                    progress.style.width = "0%";
                    progress.style.transition = `width ${delay}ms linear`;
                });
            }
            toast.show();
        });

        const motdModal = document.getElementById("motd-modal");
        if (motdModal) {
            const motdId = motdModal.dataset.motdId;
            const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;
            const modal = new bootstrap.Modal(motdModal);
            let acked = false;
            motdModal.addEventListener("hidden.bs.modal", () => {
                if (acked || !motdId || !csrfToken) return;
                acked = true;
                fetch("/api/motd/ack", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "X-CSRFToken": csrfToken,
                    },
                    body: JSON.stringify({ motd_id: Number(motdId) }),
                }).catch(() => {});
            });
            modal.show();
        }
    });
})();
