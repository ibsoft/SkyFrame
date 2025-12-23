(() => {
    const input = document.getElementById("verify-input");
    const button = document.getElementById("verify-btn");
    const fileInput = document.getElementById("verify-file");
    const fileButton = document.getElementById("verify-file-btn");
    const result = document.getElementById("verify-result");

    if (!input || !button || !result || !fileInput || !fileButton) {
        return;
    }

    const setResult = (message, ok) => {
        result.textContent = message;
        result.classList.toggle("text-success", ok === true);
        result.classList.toggle("text-danger", ok === false);
        result.classList.toggle("text-white-50", ok === null);
    };

    const renderMetadata = (data) => {
        const lines = [
            `Uploader: ${data.uploader || "Unknown"}`,
            `Object: ${data.object_name || "Unknown"}`,
            `Category: ${data.category || "Unknown"}`,
            `Observed: ${data.observed_at || "Unknown"}`,
            `Telescope: ${data.telescope || "Unknown"}`,
            `Camera: ${data.camera || "Unknown"}`,
            `Filter: ${data.filter || "Unknown"}`,
            `Location: ${data.location || "Unknown"}`,
            `Scientific use: ${data.allow_scientific_use ? "Yes" : "No"}`,
        ];
        const filtered = lines.filter((line) => line);
        result.innerHTML = `Valid signature. SHA-256: ${data.computed_hash}<br>${filtered.join("<br>")}`;
        result.classList.add("text-success");
        result.classList.remove("text-danger", "text-white-50");
    };

    const extractToken = (value) => {
        const match = value.match(/\/share\/([^/?#]+)/);
        return match ? match[1] : null;
    };

    const verify = async () => {
        const raw = input.value.trim();
        if (!raw) {
            setResult("Enter a share URL or image ID.", null);
            return;
        }
        let url = "";
        const token = extractToken(raw);
        if (token) {
            url = `/share/${token}/verify`;
        } else if (/^\d+$/.test(raw)) {
            url = `/api/images/${raw}/verify`;
        } else {
            setResult("Invalid input. Use a share URL or numeric image ID.", false);
            return;
        }

        setResult("Checking signature…", null);
        try {
            const resp = await fetch(url);
            const data = await resp.json();
            if (!resp.ok) {
                setResult(data.error || "Verification failed.", false);
                return;
            }
            if (data.valid) {
                renderMetadata(data);
            } else if (data.reason === "missing_signature") {
                setResult("No stored signature found for this image.", false);
            } else {
                setResult(`Signature mismatch. SHA-256: ${data.computed_hash}`, false);
            }
        } catch (err) {
            setResult("Unable to verify right now.", false);
        }
    };

    const verifyFile = async () => {
        const file = fileInput.files[0];
        if (!file) {
            setResult("Choose a file to verify.", null);
            return;
        }
        setResult("Checking signature…", null);
        const formData = new FormData();
        formData.append("file", file);
        try {
            const resp = await fetch("/api/verify-file", { method: "POST", body: formData });
            const data = await resp.json();
            if (!resp.ok) {
                setResult(data.error || "Verification failed.", false);
                return;
            }
            if (data.valid) {
                renderMetadata(data);
            } else {
                setResult(`No match found. SHA-256: ${data.computed_hash}.`, false);
            }
        } catch (err) {
            setResult("Unable to verify right now.", false);
        }
    };

    button.addEventListener("click", verify);
    fileButton.addEventListener("click", verifyFile);
    input.addEventListener("keydown", (event) => {
        if (event.key === "Enter") {
            verify();
        }
    });
    fileInput.addEventListener("keydown", (event) => {
        if (event.key === "Enter") {
            verifyFile();
        }
    });
})();
