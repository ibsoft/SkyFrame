(() => {
    const planetaryValues = ["Planets", "Sun", "Moon"];
    const deepTargets = ["Deep Sky", "Comets"];

    const updateVisibility = (categorySelect, seeingGroup, planetaryGroup, bortleGroup, exposureGroup) => {
        const value = categorySelect?.value;
        if (!value) return;
        const isPlanetary = planetaryValues.includes(value);
        const isDeepOrComet = deepTargets.includes(value);
        seeingGroup?.classList.toggle("d-none", !isPlanetary);
        planetaryGroup?.classList.toggle("d-none", !isPlanetary);
        bortleGroup?.classList.toggle("d-none", !isDeepOrComet);
        exposureGroup?.classList.toggle("d-none", !isDeepOrComet);
    };

    document.addEventListener("DOMContentLoaded", () => {
        const categorySelect = document.querySelector("select[name='category']");
        const seeingGroup = document.querySelector(".seeing-group");
        const bortleGroup = document.querySelector(".bortle-group");
        const planetaryGroup = document.querySelector(".planetary-group");
        const exposureGroup = document.querySelector(".exposure-group");
        const confirmBtn = document.getElementById("confirm-delete");
        const errorMsg = document.getElementById("delete-error");
        const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || "";

        updateVisibility(categorySelect, seeingGroup, planetaryGroup, bortleGroup, exposureGroup);
        categorySelect?.addEventListener("change", () =>
            updateVisibility(categorySelect, seeingGroup, planetaryGroup, bortleGroup, exposureGroup)
        );

        if (confirmBtn) {
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
        }
    });
})();
