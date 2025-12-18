(() => {
    const feedContainer = document.querySelector(".feed-stack");
    const sentinel = document.querySelector("[data-feed-sentinel]");
    const commentsSheet = document.getElementById("comments-sheet");
    const commentsList = document.getElementById("comments-list");
    const commentsTarget = document.getElementById("comments-target");
    const commentForm = document.getElementById("comment-form");
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || "";
    let cursor = sentinel?.dataset.nextCursor || null;
    let isFetching = false;
    let activeImage = null;

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

    const fetchFeed = async () => {
        if (isFetching || !sentinel) {
            return;
        }
        isFetching = true;
        showSpinner();
        try {
            const params = new URLSearchParams();
            if (cursor) {
                params.set("cursor", cursor);
            }
            const resp = await fetch(`/api/feed?${params.toString()}`);
            const data = await resp.json();
            if (data.images?.length && feedContainer) {
                data.images.forEach((entry) => {
                    const card = buildCard(entry);
                    feedContainer.appendChild(card);
                });
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

    const isAuthenticated = document.body?.dataset?.authenticated === "true";
    const observer = sentinel
        ? new IntersectionObserver(
              (entries) => {
                  if (entries[0].isIntersecting) {
                      fetchFeed();
                  }
              },
              { threshold: 0.5 }
          )
        : null;

    if (observer && sentinel) {
        observer.observe(sentinel);
    }

    const buildCard = (image) => {
        const card = document.createElement("article");
        card.className = "feed-card";
        card.dataset.imageId = image.id;
        const actionButtons = isAuthenticated
            ? `
                <button type="button" class="toggle-actions-btn" data-action="toggle-buttons">
                    <span class="toggle-text">Hide controls</span>
                </button>
                <div class="action-column" data-image-id="${image.id}">
                    <button class="action-icon ${image.liked ? "active" : ""}" data-action="like" data-image-id="${image.id}">
                        <span>Like</span>
                        <span class="action-count">${image.like_count}</span>
                    </button>
                    <button class="action-icon ${image.favorited ? "active" : ""}" data-action="favorite" data-image-id="${image.id}">
                        <span>Save</span>
                        <span class="action-count">${image.favorite_count}</span>
                    </button>
                    <button class="action-icon" data-action="download" data-image-id="${image.id}" data-download-url="${image.download_url}" data-download-name="${image.download_name}">
                        <span>Download</span>
                    </button>
                    <button class="action-icon ${image.following_uploader ? "active" : ""}" data-action="follow" data-target-id="${image.uploader_id}">
                        <span>${image.following_uploader ? "Following" : "Follow"}</span>
                    </button>
                    <button class="action-icon" data-action="comment" data-image-id="${image.id}">
                        <span>Comment</span>
                        <span class="action-count">${image.comment_count}</span>
                    </button>
                    <button type="button" class="action-icon share" data-action="share" data-image-id="${image.id}">
                        <span>Share</span>
                    </button>
                    ${
                        image.owned_by_current_user
                            ? `<a class="action-icon" href="/images/${image.id}/edit"><span>Edit</span></a>`
                            : ""
                    }
                </div>
            `
            : "";
        card.innerHTML = `
            <div class="image-wrap">
                <img class="feed-image" src="${image.thumb_url}" alt="${image.object_name}" loading="lazy" data-image-id="${image.id}">
                ${actionButtons}
            </div>
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
            </div>
        `;
        return card;
    };

    const toggleControls = (button) => {
        const card = button.closest(".feed-card");
        if (!card) return;
        const hidden = card.classList.toggle("feed-card--hide-controls");
        const label = button.querySelector(".toggle-text");
        if (label) {
            label.textContent = hidden ? "Show controls" : "Hide controls";
        }
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
        if (!action || (!imageId && action !== "follow")) return;
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
        } else if (action === "share") {
            shareImage(imageId);
        } else if (action === "comment") {
            const imageEl = element.closest("[data-image-id]");
            if (!imageEl) return;
            const heading = imageEl.querySelector(".metadata-card h5");
            openComments(imageId, heading ? heading.textContent : "Comments");
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
            const action = actionTarget.dataset.action;
            if (action === "close-comments") {
                closeComments();
                return;
            }
            if (action === "toggle-buttons") {
                toggleControls(actionTarget);
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

})();
