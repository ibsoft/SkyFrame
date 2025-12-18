(() => {
    const confirmBtn = document.getElementById("confirm-delete");
    const errorMsg = document.getElementById("delete-error");
    if (!confirmBtn) return;
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || "";
    confirmBtn.addEventListener("click", async () => {
        confirmBtn.disabled = true;
        errorMsg.textContent = "";
        const imageId = confirmBtn.dataset.imageId;
        try {
            const resp = await fetch(`/api/images/${imageId}`, {
                method: "DELETE",
                headers: {
                    "X-CSRFToken": csrfToken,
                },
            });
            if (resp.ok) {
                const redirectUrl = confirmBtn.dataset.redirectUrl || "/";
                window.location.href = redirectUrl;
                return;
            }
            const payload = await resp.json().catch(() => ({}));
            errorMsg.textContent = payload.error || "Unable to delete frame.";
        } catch (err) {
            errorMsg.textContent = "Unable to delete frame.";
        } finally {
            confirmBtn.disabled = false;
        }
    });
})();
