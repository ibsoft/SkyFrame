(() => {
    const spinner = document.getElementById("upload-spinner-overlay");
    const form = document.querySelector("form[enctype='multipart/form-data']");
    if (!spinner || !form) {
        return;
    }
    form.addEventListener("submit", () => {
        spinner.classList.remove("d-none");
    });
})();
