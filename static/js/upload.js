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
        const spinner = document.getElementById("upload-spinner-overlay");
        const form = document.querySelector("form[enctype='multipart/form-data']");
        const categorySelect = document.querySelector("select[name='category']");
        const seeingGroup = document.querySelector(".seeing-group");
        const bortleGroup = document.querySelector(".bortle-group");
        const planetaryGroup = document.querySelector(".planetary-group");
        const exposureGroup = document.querySelector(".exposure-group");

        updateVisibility(categorySelect, seeingGroup, planetaryGroup, bortleGroup, exposureGroup);
        categorySelect?.addEventListener("change", () =>
            updateVisibility(categorySelect, seeingGroup, planetaryGroup, bortleGroup, exposureGroup)
        );

        if (spinner && form) {
            form.addEventListener("submit", () => {
                spinner.classList.remove("d-none");
            });
        }
    });
})();
