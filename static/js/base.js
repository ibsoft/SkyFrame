(function () {
    const pwaPromptBar = document.querySelector(".pwa-prompt");
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
    };

    window.addEventListener("beforeinstallprompt", (e) => {
        e.preventDefault();
        window.deferredPrompt = e;
        if (pwaPromptBar) {
            pwaPromptBar.classList.remove("d-none");
        }
    });

    document.addEventListener("click", (ev) => {
        if (ev.target.matches("[data-install-pwa]")) {
            installApp();
        }
    });

    if ("serviceWorker" in navigator && serviceWorkerUrl) {
        navigator.serviceWorker.register(serviceWorkerUrl).catch(() => {});
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
