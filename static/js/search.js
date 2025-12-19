(() => {
    const grid = document.querySelector("[data-search-grid]");
    const sentinel = document.querySelector("[data-search-sentinel]");
    const modalEl = document.getElementById("searchImageModal");
    const modalTitle = document.getElementById("searchImageTitle");
    const modalImage = document.getElementById("searchImagePreview");
    const downloadBtn = document.getElementById("searchDownloadBtn");
    const shareBtn = document.getElementById("searchShareBtn");
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || "";

    if (!grid || !sentinel) {
        return;
    }

    let cursor = sentinel.dataset.nextCursor || "";
    let isFetching = false;
    const params = (() => {
        try {
            return JSON.parse(grid.dataset.searchParams || "{}");
        } catch {
            return {};
        }
    })();

    const metadataMedia = window.matchMedia("(min-width: 992px)");
    const syncMetadataSheet = (sheet) => {
        if (!sheet || sheet.dataset.userToggled === "true") return;
        if (metadataMedia.matches) {
            sheet.setAttribute("open", "");
        } else {
            sheet.removeAttribute("open");
        }
    };

    const syncMetadataSheets = (root = document) => {
        root.querySelectorAll(".metadata-sheet").forEach((sheet) => {
            if (!sheet.dataset.toggleBound) {
                sheet.addEventListener("toggle", () => {
                    sheet.dataset.userToggled = "true";
                });
                sheet.dataset.toggleBound = "true";
            }
            syncMetadataSheet(sheet);
        });
    };

    metadataMedia.addEventListener("change", () => syncMetadataSheets());
    syncMetadataSheets();

    const escapeHtml = (value = "") =>
        value
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");

    const formatDate = (value) => {
        if (!value) return "";
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) return "";
        return date.toLocaleDateString();
    };

    const buildCard = (image) => {
        const card = document.createElement("article");
        card.className = "search-card";
        const tags = Array.isArray(image.tags) && image.tags.length
            ? `<div class="metadata-tags small">${image.tags
                  .map((tag) => `<span class="tag-pill">#${escapeHtml(tag)}</span>`)
                  .join("")}</div>`
            : "";
        card.innerHTML = `
            <div class="search-thumb">
                <img class="search-image" src="${image.thumb_url}" alt="${escapeHtml(
            image.object_name
        )}" loading="lazy" data-image-id="${image.id}" data-download-url="${
            image.download_url
        }" data-download-name="${escapeHtml(image.download_name || "")}">
            </div>
            <details class="metadata-sheet search-meta">
                <summary>Metadata</summary>
                <div class="metadata-stack">
                    <div class="metadata-card px-3 py-3">
                        <div class="d-flex justify-content-between align-items-start">
                            <div>
                                <p class="small mb-1">${escapeHtml(image.category || "")} · ${escapeHtml(
            image.observer_name || ""
        )}</p>
                                <h5 class="mb-0">${escapeHtml(image.object_name || "")}</h5>
                            </div>
                            <span class="small">${formatDate(image.observed_at)}</span>
                        </div>
                        <p class="meta-info small mb-0">
                            ${escapeHtml(image.telescope || "Telescope TBD")} · ${escapeHtml(
            image.camera || "Camera TBD"
        )}<br>
                            Filter: ${escapeHtml(image.filter || "n/a")}<br>
                            Location: ${escapeHtml(image.location || "Unknown")}
                        </p>
                        <p class="meta-info small mb-0">
                            Seeing: ${escapeHtml(image.seeing_rating || "N/A")} · Transparency: ${escapeHtml(
            image.transparency_rating || "N/A"
        )}
                        </p>
                        ${
                            image.category === "Deep Sky" && image.bortle_rating
                                ? `<p class="meta-info small mb-0">Bortle scale: ${escapeHtml(
                                      image.bortle_rating
                                  )}</p>`
                                : ""
                        }
                        ${
                            image.notes
                                ? `<p class="meta-info small mb-0"><strong>Notes:</strong> ${escapeHtml(
                                      image.notes
                                  )}</p>`
                                : ""
                        }
                        ${tags}
                    </div>
                </div>
            </details>
        `;
        return card;
    };

    const buildQuery = () => {
        const search = new URLSearchParams();
        Object.entries(params).forEach(([key, value]) => {
            if (value) {
                search.set(key, value);
            }
        });
        if (cursor) {
            search.set("cursor", cursor);
        }
        return search.toString();
    };

    const fetchNext = async () => {
        if (isFetching || !cursor) return;
        isFetching = true;
        try {
            const resp = await fetch(`/api/search?${buildQuery()}`);
            if (!resp.ok) {
                cursor = "";
                return;
            }
            const data = await resp.json();
            if (Array.isArray(data.images)) {
                data.images.forEach((image) => {
                    const card = buildCard(image);
                    grid.appendChild(card);
                });
                syncMetadataSheets(grid);
            }
            cursor = data.next_cursor || "";
            sentinel.dataset.nextCursor = cursor;
            if (!cursor) {
                sentinel.textContent = "No more results.";
            }
        } catch (err) {
            console.warn(err);
        } finally {
            isFetching = false;
        }
    };

    const observer = new IntersectionObserver(
        (entries) => {
            if (entries[0].isIntersecting) {
                fetchNext();
            }
        },
        { threshold: 0.5 }
    );
    observer.observe(sentinel);

    const postAction = async (url) => {
        const resp = await fetch(url, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": csrfToken,
            },
            credentials: "include",
        });
        if (!resp.ok) {
            const payload = await resp.json().catch(() => ({}));
            throw new Error(payload.error || "Action failed");
        }
        return resp.json();
    };

    const shareImage = async (imageId) => {
        if (!imageId) return;
        try {
            const resp = await postAction(`/api/images/${imageId}/share`);
            if (!resp.share_url) {
                throw new Error("No share URL returned.");
            }
            const shareUrl = resp.share_url;
            if (navigator.share) {
                await navigator.share({
                    title: "SkyFrame",
                    text: "Check out this observation",
                    url: shareUrl,
                });
                return;
            }
            if (navigator.clipboard) {
                await navigator.clipboard.writeText(shareUrl);
                return;
            }
            window.prompt("Copy this share link", shareUrl);
        } catch (err) {
            console.warn(err);
        }
    };

    const openModal = (imgEl) => {
        if (!modalEl || !modalImage || !downloadBtn) return;
        const src = imgEl.getAttribute("src");
        const alt = imgEl.getAttribute("alt") || "Preview";
        const downloadUrl = imgEl.dataset.downloadUrl || "#";
        const downloadName = imgEl.dataset.downloadName || "";
        const imageId = imgEl.dataset.imageId;
        modalImage.src = src || "";
        modalImage.alt = alt;
        if (modalTitle) {
            modalTitle.textContent = alt;
        }
        downloadBtn.href = downloadUrl;
        downloadBtn.download = downloadName;
        if (shareBtn) {
            shareBtn.onclick = () => shareImage(imageId);
        }
        bootstrap.Modal.getOrCreateInstance(modalEl).show();
    };

    document.addEventListener("click", (event) => {
        const image = event.target.closest(".search-image");
        if (!image) return;
        openModal(image);
    });
})();
