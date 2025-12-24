(() => {
    const feedContainer = document.querySelector(".feed-stack");
    const feedShell = document.querySelector(".feed-shell");
    const sentinel = document.querySelector("[data-feed-sentinel]");
    const feedEndpoint = feedShell?.dataset?.feedEndpoint || "/api/feed";
    const scrollContainer = document.querySelector(".app-shell main");
    const totalFeeds = feedShell?.dataset?.totalFeeds || "0";
    const commentsSheet = document.getElementById("comments-sheet");
    const commentsList = document.getElementById("comments-list");
    const commentsTarget = document.getElementById("comments-target");
    const commentForm = document.getElementById("comment-form");
    const likesModal = document.getElementById("likesModal");
    const likesList = likesModal?.querySelector("[data-likes-list]");
    const likesCount = likesModal?.querySelector("[data-likes-count]");
    const fullscreenModal = document.getElementById("fullscreenModal");
    const fullscreenImage = document.getElementById("fullscreenImage");
    const zoomInButton = fullscreenModal?.querySelector("[data-zoom-in]");
    const zoomOutButton = fullscreenModal?.querySelector("[data-zoom-out]");
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || "";
    const isAuthenticated = document.body?.dataset?.authenticated === "true";
    let cursor = sentinel?.dataset.nextCursor || null;
    let isFetching = false;
    let activeImage = null;
    let zoomLevel = 1;

    const postAction = async (url) => {
        const resp = await fetch(url, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": csrfToken,
            },
        });
        if (!resp.ok) {
            const payload = await resp.json().catch(() => ({}));
            throw new Error(payload.error || "Action failed");
        }
        return resp.json();
    };

    const toastContainer = document.querySelector(".toast-container");
    const observerInput = document.querySelector(".observer-input");
    const observerList = document.querySelector("[data-observer-list]");
    let observerDebounce;

    const showToast = (message) => {
        if (!toastContainer) return;
        const toastEl = document.createElement("div");
        toastEl.className = "toast toast-blue align-items-center";
        toastEl.setAttribute("role", "alert");
        toastEl.setAttribute("aria-live", "assertive");
        toastEl.setAttribute("aria-atomic", "true");
        toastEl.dataset.bsDelay = 4000;
        toastEl.innerHTML = `
            <div class="toast-progress" aria-hidden="true"></div>
            <div class="d-flex">
                <div class="toast-body"></div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        `;
        const body = toastEl.querySelector(".toast-body");
        if (body) {
            body.textContent = message;
        }
        toastContainer.appendChild(toastEl);
        const toast = new bootstrap.Toast(toastEl, {
            autohide: true,
            delay: 4000,
        });
        toastEl.addEventListener("hidden.bs.toast", () => toastEl.remove());
        toast.show();
    };

    const metadataMedia = window.matchMedia("(min-width: 992px)");

    const openLikesModal = async (imageId) => {
        if (!likesModal || !likesList) return;
        likesList.innerHTML = `<div class="likes-empty">Loading likes...</div>`;
        if (likesCount) {
            likesCount.textContent = "";
        }
        const modalApi = window.bootstrap?.Modal;
        if (modalApi) {
            modalApi.getOrCreateInstance(likesModal).show();
        }
        try {
            const resp = await fetch(`/api/images/${imageId}/likes`);
            if (!resp.ok) {
                throw new Error("Failed to load likes");
            }
            const data = await resp.json();
            const items = data.likes || [];
            if (!items.length) {
                likesList.innerHTML = `<div class="likes-empty">No likes yet.</div>`;
                return;
            }
            if (likesCount) {
                likesCount.textContent = `${data.count || items.length} likes`;
            }
            likesList.innerHTML = items
                .map(
                    (user) => `
                    <div class="likes-item">
                        <img class="likes-avatar" src="${user.avatar_url}" alt="${escapeHtml(
                        user.username
                    )} avatar">
                        <div class="likes-username">${escapeHtml(user.username)}</div>
                    </div>
                `
                )
                .join("");
        } catch (error) {
            likesList.innerHTML = `<div class="likes-empty">Unable to load likes.</div>`;
        }
    };
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
                showToast("Share dialog opened");
                return;
            }
            if (navigator.clipboard) {
                await navigator.clipboard.writeText(shareUrl);
                showToast("Share link copied to clipboard");
                return;
            }
            window.prompt("Copy this share link", shareUrl);
            showToast("Share link ready to copy");
        } catch (err) {
            console.warn(err);
            showToast("Unable to create share link");
        }
    };

    const escapeHtml = (value = "") =>
        value
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");

    const linkifyText = (value = "") => {
        const urlRegex = /((https?:\/\/|www\.)[^\s<]+[^<.,:;"')\]\s])/gi;
        const escaped = escapeHtml(value);
        return escaped.replace(urlRegex, (match) => {
            const url = match.startsWith("www.") ? `https://${match}` : match;
            return `<a href="${url}" target="_blank" rel="noopener noreferrer">${match}</a>`;
        });
    };

    const spinner = document.getElementById("feed-loading-overlay");
    const showSpinner = () => {
        spinner?.classList.remove("d-none");
    };
    const hideSpinner = () => {
        spinner?.classList.add("d-none");
    };

    const updateFeedCounts = () => {
        if (!feedContainer) return;
        const ids = new Set();
        feedContainer.querySelectorAll(".feed-card").forEach((card) => {
            const id = card.dataset.imageId;
            if (id) ids.add(id);
        });
        const loaded = ids.size;
        const rangeLabel = loaded > 0 ? `1-${loaded}` : "0";
        document.querySelectorAll("[data-loaded-feeds-range]").forEach((el) => {
            el.textContent = rangeLabel;
        });
    };

    function buildCard(image) {
        const card = document.createElement("article");
        card.className = "feed-card";
        card.dataset.imageId = image.id;
        const actionButtons = isAuthenticated
            ? `
                <div class="action-column" data-image-id="${image.id}">
                <button class="action-icon action-like ${image.liked ? "active" : ""}" data-action="like" data-image-id="${image.id}">
                        <i class="fa-solid fa-heart"></i>
                        <span>Like</span>
                        <span class="action-count">${image.like_count}</span>
                    </button>
                    <button class="action-icon action-save ${image.favorited ? "active" : ""}" data-action="favorite" data-image-id="${image.id}">
                        <i class="fa-solid fa-bookmark"></i>
                        <span>Save</span>
                        <span class="action-count">${image.favorite_count}</span>
                    </button>
                    <button class="action-icon action-download" data-action="download" data-image-id="${image.id}" data-download-url="${image.download_url}" data-download-name="${image.download_name}">
                        <i class="fa-solid fa-download"></i>
                        <span>Download</span>
                    </button>
                    ${
                        image.owned_by_current_user
                            ? ""
                            : `<button class="action-icon action-follow ${image.following_uploader ? "active" : ""}" data-action="follow" data-target-id="${image.uploader_id}">
                                   <i class="fa-solid fa-user-plus"></i>
                                   <span>${image.following_uploader ? "Following" : "Follow"}</span>
                               </button>`
                    }
                    <button class="action-icon action-comment" data-action="comment" data-image-id="${image.id}">
                        <i class="fa-solid fa-comment"></i>
                        <span>Comment</span>
                        <span class="action-count">${image.comment_count}</span>
                    </button>
                    <button type="button" class="action-icon share" data-action="share" data-image-id="${image.id}">
                        <i class="fa-solid fa-share-nodes"></i>
                        <span>Share</span>
                    </button>
                    ${
                        image.owned_by_current_user
                            ? `<a class="action-icon" href="/images/${image.id}/edit"><i class="fa-solid fa-pen-to-square"></i><span>Edit</span></a>`
                            : ""
                    }
                    <button type="button" class="action-icon action-view" data-action="view-fullscreen" data-full-url="${image.download_url}">
                        <i class="fa-solid fa-up-right-and-down-left-from-center"></i>
                        <span>View</span>
                    </button>
                    <button type="button" class="action-icon action-reload" data-action="feed-load">
                        <i class="fa-solid fa-arrows-rotate"></i>
                        <span>Load</span>
                    </button>
                    <button type="button" class="action-icon action-toggle" data-action="toggle-buttons">
                        <i class="fa-solid fa-eye-slash"></i>
                        <span>Hide</span>
                    </button>
                </div>
            `
            : "";
        const planetary = image.planetary_data;
        let planetaryContent = "";
        if (planetary) {
            planetaryContent = `
            <div class="post-metadata px-3 py-3">
                <p class="meta-info small mb-0">
                    RA: ${planetary.ra}° · Dec: ${planetary.dec}°
                </p>
                <p class="meta-info small mb-0">Distance: ${planetary.distance_au} AU</p>
                ${
                    planetary.altitude !== undefined && planetary.azimuth !== undefined
                        ? `<p class="meta-info small mb-0">
                             Altitude: ${planetary.altitude}° · Azimuth: ${planetary.azimuth}°
                           </p>`
                        : ""
                }
                ${
                    !planetary.has_location
                        ? `<p class="meta-info small mb-0 fst-italic text-white">
                             Alt/Az unavailable – uploader has not provided observatory coordinates.
                           </p>`
                        : ""
                }
                ${
                    planetary.jupiter_systems
                        ? `<p class="meta-info small mb-0 mt-1">
                             <strong>Jupiter System</strong>
                             I: ${planetary.jupiter_systems.system_i}° ·
                             II: ${planetary.jupiter_systems.system_ii}° ·
                             III: ${planetary.jupiter_systems.system_iii}°
                           </p>`
                        : ""
                }
            </div>`;
        }
        const showExposureDetails =
            ["Deep Sky", "Comets"].includes(image.category) && image.max_exposure_time;
        card.innerHTML = `
            <div class="image-wrap">
                <img class="feed-image" src="${image.thumb_url}" alt="${image.object_name}" loading="lazy" data-image-id="${image.id}">
            </div>
            ${actionButtons}
            <details class="metadata-sheet">
                <summary>Metadata</summary>
                <div class="metadata-stack">
                    <div class="metadata-card px-3 py-3">
                        <div class="d-flex justify-content-between align-items-start">
                            <div>
                                <p class="small mb-1">${image.category} · ${image.observer_name}</p>
                                <h5 class="mb-0">${image.object_name}</h5>
                            </div>
                            <span class="small">${new Date(image.observed_at).toLocaleString()}</span>
                        </div>
                        <p class="meta-info small mb-0">${image.telescope || "Telescope TBD"} · ${image.camera || "Camera TBD"}<br>Filter: ${
            image.filter || "n/a"
        }<br>Location: ${image.location || "Unknown"}</p>
                        <p class="meta-info small mb-0">
                            Seeing: ${image.seeing_rating || "N/A"} · Transparency: ${image.transparency_rating || "N/A"}
                        </p>
                        ${
                            image.category === "Deep Sky" && image.bortle_rating
                                ? `<p class="meta-info small mb-0">Bortle scale: ${image.bortle_rating}</p>`
                                : ""
                        }
                        ${
                            image.notes
                                ? `<p class="meta-info small mb-0"><strong>Notes:</strong> ${escapeHtml(
                                      image.notes
                                  )}</p>`
                                : ""
                        }
                        ${
                            image.tags?.length
                                ? `<div class="metadata-tags small">${image.tags
                                      .map((tag) => `<span class="tag-pill">#${escapeHtml(tag)}</span>`)
                                      .join("")}</div>`
                            : ""
                        }
                        ${
                            image.derotation_time
                                ? `<p class="meta-info small mb-0">Derotation time: ${parseFloat(
                                      image.derotation_time
                                  ).toFixed(1)} min</p>`
                                : ""
                        }
                        ${
                            showExposureDetails
                                ? `<p class="meta-info small mb-0">Max exposure: ${parseFloat(
                                      image.max_exposure_time
                                  ).toFixed(1)} s</p>`
                                : ""
                        }
                    </div>
                    ${planetaryContent}
                </div>
            </details>
        `;
        return card;
    }

    const fetchFeed = async () => {
        if (isFetching || !sentinel || !cursor) {
            return;
        }
        isFetching = true;
        showSpinner();
        try {
            const params = new URLSearchParams();
            if (cursor) {
                params.set("cursor", cursor);
            }
            const resp = await fetch(`${feedEndpoint}?${params.toString()}`);
            const data = await resp.json();
            if (data.images?.length && feedContainer) {
                const existingIds = new Set(
                    Array.from(feedContainer.querySelectorAll(".feed-card")).map(
                        (card) => card.dataset.imageId
                    )
                );
                const seenBatch = new Set();
                data.images.forEach((entry) => {
                    const entryId = String(entry.id);
                    if (!entryId || existingIds.has(entryId) || seenBatch.has(entryId)) {
                        return;
                    }
                    const card = buildCard(entry);
                    feedContainer.appendChild(card);
                    syncMetadataSheets(card);
                    existingIds.add(entryId);
                    seenBatch.add(entryId);
                });
                updateFeedCounts();
            }
            cursor = data.next_cursor;
            if (sentinel) {
                sentinel.dataset.nextCursor = data.next_cursor || "";
            }
            if (!cursor) {
                sentinel.textContent = "You're caught up for now.";
                observer?.disconnect();
            }
        } finally {
            isFetching = false;
            hideSpinner();
        }
    };

    const replaceFeed = (entries = []) => {
        if (!feedContainer) return;
        feedContainer.innerHTML = "";
        const seenBatch = new Set();
        entries.forEach((entry) => {
            const entryId = String(entry.id);
            if (seenBatch.has(entryId)) {
                return;
            }
            const card = buildCard(entry);
            feedContainer.appendChild(card);
            syncMetadataSheets(card);
            seenBatch.add(entryId);
        });
        updateFeedCounts();
    };

    const loadNextBatch = async () => {
        await fetchFeed();
    };

    const renderObserverSuggestions = (items = []) => {
        if (!observerList) return;
        if (!items.length) {
            observerList.classList.add("d-none");
            observerList.innerHTML = "";
            return;
        }
        observerList.innerHTML = items
            .map(
                (name) => `
                <button type="button" data-observer-suggestion>${name}</button>
            `
            )
            .join("");
        observerList.classList.remove("d-none");
    };

    const fetchObservers = async (query) => {
        if (!query) {
            renderObserverSuggestions([]);
            return;
        }
        try {
            const resp = await fetch(`/api/observers?q=${encodeURIComponent(query)}`);
            if (!resp.ok) {
                throw new Error("Observer lookup failed");
            }
            const data = await resp.json();
            renderObserverSuggestions(data.observers || []);
        } catch (error) {
            console.warn(error);
            renderObserverSuggestions([]);
        }
    };

    const openCommentFromQuery = () => {
        if (!commentsSheet) return;
        const params = new URLSearchParams(window.location.search);
        const imageId = params.get("open_comment");
        if (!imageId) return;
        openComments(imageId, "Comments");
        params.delete("open_comment");
        const next = `${window.location.pathname}${params.toString() ? `?${params}` : ""}`;
        window.history.replaceState({}, "", next);
    };

    const focusImageFromQuery = () => {
        const params = new URLSearchParams(window.location.search);
        const imageId = params.get("focus_image");
        if (!imageId || !feedContainer) return;
        const card = feedContainer.querySelector(`[data-image-id="${imageId}"]`);
        if (!card) return;
        card.scrollIntoView({ behavior: "smooth", block: "center" });
        card.classList.add("feed-highlight");
        setTimeout(() => card.classList.remove("feed-highlight"), 1600);
        params.delete("focus_image");
        const next = `${window.location.pathname}${params.toString() ? `?${params}` : ""}`;
        window.history.replaceState({}, "", next);
    };

    const initDeepLink = () => {
        openCommentFromQuery();
        focusImageFromQuery();
    };

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initDeepLink);
    } else {
        initDeepLink();
    }

    observerInput?.addEventListener("input", (ev) => {
        const text = ev.target.value.trim();
        clearTimeout(observerDebounce);
        observerDebounce = setTimeout(() => {
            fetchObservers(text);
        }, 350);
    });

    document.addEventListener("click", (ev) => {
        if (observerList && !observerList.contains(ev.target) && ev.target !== observerInput) {
            observerList.classList.add("d-none");
        }
        if (observerList?.contains(ev.target) && ev.target.matches("[data-observer-suggestion]")) {
            observerInput.value = ev.target.textContent.trim();
            observerList.classList.add("d-none");
        }
    });

    const observer = null;

    const updateZoom = () => {
        if (!fullscreenImage) return;
        fullscreenImage.style.transform = `scale(${zoomLevel})`;
    };

    const openFullscreen = (url) => {
        if (!fullscreenModal || !fullscreenImage) return;
        zoomLevel = 1;
        updateZoom();
        fullscreenImage.src = url;
        const modalApi = window.bootstrap?.Modal;
        if (modalApi) {
            modalApi.getOrCreateInstance(fullscreenModal).show();
        }
    };

    zoomInButton?.addEventListener("click", () => {
        zoomLevel = Math.min(4, zoomLevel + 0.25);
        updateZoom();
    });

    zoomOutButton?.addEventListener("click", () => {
        zoomLevel = Math.max(1, zoomLevel - 0.25);
        updateZoom();
    });

    fullscreenModal?.addEventListener("hidden.bs.modal", () => {
        if (!fullscreenImage) return;
        fullscreenImage.src = "";
        zoomLevel = 1;
        updateZoom();
    });


    const updateToggleIcon = (button, isHidden) => {
        const icon = button.querySelector("i");
        if (icon) {
            icon.className = isHidden ? "fa-solid fa-eye" : "fa-solid fa-eye-slash";
        }
        const label = button.querySelector("span");
        if (label) {
            label.textContent = isHidden ? "Show" : "Hide";
        }
    };

    const toggleControls = () => {
        if (!document.body) return;
        const toggles = document.querySelectorAll('[data-action="toggle-buttons"]');
        const shouldHide = !document.body.classList.contains("controls-hidden");
        document.body.classList.toggle("controls-hidden", shouldHide);
        toggles.forEach((btn) => {
            btn.classList.toggle("controls-active", shouldHide);
            updateToggleIcon(btn, shouldHide);
        });
    };

    const initToggleIcons = () => {
        const isHidden = document.body.classList.contains("controls-hidden");
        document.querySelectorAll('[data-action="toggle-buttons"]').forEach((btn) => {
            updateToggleIcon(btn, isHidden);
        });
    };

    const animateHeart = (container) => {
        if (!container) return;
        const heart = document.createElement("span");
        heart.textContent = "❤";
        heart.className = "floating-heart";
        container.appendChild(heart);
        requestAnimationFrame(() => heart.classList.add("visible"));
        heart.addEventListener("animationend", () => heart.remove());
    };

    const likeImage = async (imageId, card) => {
        if (!card) return;
        const likeButton = card.querySelector('[data-action="like"]');
        if (!likeButton) return;
        const isActive = likeButton.classList.contains("active");
        const verb = isActive ? "unlike" : "like";
        try {
            const resp = await postAction(`/api/images/${imageId}/${verb}`);
            const countEl = likeButton.querySelector(".action-count");
            if ("like_count" in resp && countEl) {
                countEl.textContent = resp.like_count;
            }
            likeButton.classList.toggle("active", !isActive);
        } catch (err) {
            console.warn(err);
        }
    };

    const handleAction = async (element) => {
        const action = element.dataset.action;
        const imageId = element.dataset.imageId;
        if (!action) return;
        if (!imageId && !["follow", "feed-load", "view-fullscreen"].includes(action)) {
            return;
        }
        if (action === "like" || action === "favorite") {
            const isActive = element.classList.contains("active");
            const verb = isActive ? "un" : "";
            const resp = await postAction(`/api/images/${imageId}/${verb}${action}`);
            if ("like_count" in resp) {
                element.querySelector(".action-count").textContent = resp.like_count;
            }
            if ("favorite_count" in resp) {
                element.querySelector(".action-count").textContent = resp.favorite_count;
            }
            element.classList.toggle("active", !isActive);
        } else if (action === "follow") {
            const targetId = element.dataset.targetId;
            const isActive = element.classList.contains("active");
            const verb = isActive ? "unfollow" : "follow";
            await postAction(`/api/users/${targetId}/${verb}`);
            element.classList.toggle("active", !isActive);
        } else if (action === "download") {
            const url = element.dataset.downloadUrl;
            const downloadName = element.dataset.downloadName;
            if (!url) return;
            try {
                const resp = await fetch(url, { credentials: "include" });
                if (!resp.ok) {
                    throw new Error("Unable to download image.");
                }
                const blob = await resp.blob();
                const link = document.createElement("a");
                link.href = URL.createObjectURL(blob);
                link.download = downloadName || "";
                document.body.appendChild(link);
                link.click();
                window.setTimeout(() => {
                    URL.revokeObjectURL(link.href);
                    link.remove();
                }, 1000);
            } catch (err) {
                console.error(err);
            }
        } else if (action === "verify") {
            const watermark = element.dataset.watermark;
            const owner = element.dataset.uploader || "SkyFrame";
            if (!watermark) return;
            const modal = document.getElementById("signatureModal");
            if (!modal) return;
            const idElement = modal.querySelector(".signature-id");
            const ownerElement = modal.querySelector(".signature-owner");
            if (idElement) {
                idElement.textContent = watermark;
            }
            if (ownerElement) {
                ownerElement.textContent = owner;
            }
            bootstrap.Modal.getOrCreateInstance(modal).show();
        } else if (action === "share") {
            shareImage(imageId);
        } else if (action === "comment") {
            const imageEl = element.closest("[data-image-id]");
            if (!imageEl) return;
            const heading = imageEl.querySelector(".metadata-card h5");
            openComments(imageId, heading ? heading.textContent : "Comments");
        } else if (action === "feed-load") {
            loadNextBatch();
        } else if (action === "view-fullscreen") {
            const fullUrl = element.dataset.fullUrl;
            if (!fullUrl) return;
            openFullscreen(fullUrl);
        }
    };

    const closeComments = () => {
        commentsSheet?.classList.add("d-none");
        activeImage = null;
        if (commentsList) {
            commentsList.innerHTML = "";
        }
    };

    const openComments = async (imageId, label) => {
        activeImage = imageId;
        if (commentsTarget) {
            commentsTarget.textContent = label;
        }
        commentsSheet?.classList.remove("d-none");
        const resp = await fetch(`/api/images/${imageId}/comments`);
        const data = await resp.json();
        if (!commentsList) {
            return;
        }
        commentsList.innerHTML = "";
        data.forEach((comment) => {
            const row = document.createElement("div");
            row.className = "comment-row";
            row.innerHTML = `<strong>${escapeHtml(comment.user)}</strong><p class="mb-0 text-muted">${linkifyText(
                comment.body
            )}</p>`;
            commentsList.appendChild(row);
        });
    };

    document.addEventListener("click", (event) => {
        const actionTarget = event.target.closest("[data-action]");
        if (actionTarget) {
            if (actionTarget.dataset.longPress === "true") {
                actionTarget.dataset.longPress = "false";
                return;
            }
            const action = actionTarget.dataset.action;
            if (action === "close-comments") {
                closeComments();
                return;
            }
            if (action === "toggle-buttons") {
                toggleControls();
                return;
            }
            handleAction(actionTarget);
            return;
        }
        const imageTarget = event.target.closest(".feed-image");
        if (!imageTarget) {
            return;
        }
        const card = imageTarget.closest(".feed-card");
        if (!card) return;
        const imageId = card.dataset.imageId;
        animateHeart(card.querySelector(".image-wrap"));
        likeImage(imageId, card);
    });

    if (window.matchMedia("(pointer: coarse)").matches) {
        let longPressTimer = null;
        let longPressTarget = null;
        document.addEventListener("pointerdown", (event) => {
            const button = event.target.closest('[data-action="like"]');
            if (!button || event.pointerType !== "touch") return;
            const imageId = button.dataset.imageId;
            longPressTarget = button;
            longPressTimer = window.setTimeout(() => {
                if (longPressTarget) {
                    longPressTarget.dataset.longPress = "true";
                }
                openLikesModal(imageId);
            }, 550);
        });

        const clearLongPress = () => {
            if (longPressTimer) {
                window.clearTimeout(longPressTimer);
                longPressTimer = null;
            }
            longPressTarget = null;
        };

        document.addEventListener("pointerup", clearLongPress);
        document.addEventListener("pointercancel", clearLongPress);
        document.addEventListener("pointermove", (event) => {
            if (event.pointerType !== "touch") return;
            if (longPressTimer) {
                window.clearTimeout(longPressTimer);
                longPressTimer = null;
            }
        });
    }

    commentForm?.addEventListener("submit", async (event) => {
        event.preventDefault();
        const textarea = commentForm.querySelector("textarea");
        const body = textarea.value.trim();
        if (!activeImage || !body) return;
        const resp = await fetch(`/api/images/${activeImage}/comments`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": csrfToken,
            },
            body: JSON.stringify({ body }),
        });
        if (!resp.ok) return;
        const data = await resp.json();
        const row = document.createElement("div");
        row.className = "comment-row";
        row.innerHTML = `<strong>${escapeHtml(data.user)}</strong><p class="mb-0 text-muted">${linkifyText(
            data.body
        )}</p>`;
        if (commentsList) {
            commentsList.prepend(row);
        }
        textarea.value = "";
    });

    updateFeedCounts();

    syncMetadataSheets();
    initToggleIcons();

})();
