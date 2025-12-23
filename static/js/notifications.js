(() => {
    const notifyButton = document.getElementById("notify-btn");
    if (!notifyButton) return;

    const likeBadge = notifyButton.querySelector("[data-like-badge]");
    const commentBadge = notifyButton.querySelector("[data-comment-badge]");
    const modalEl = document.getElementById("notificationsModal");
    const likeList = modalEl?.querySelector("[data-like-list]");
    const commentList = modalEl?.querySelector("[data-comment-list]");
    const likeCount = modalEl?.querySelector("[data-like-count]");
    const commentCount = modalEl?.querySelector("[data-comment-count]");

    const escapeHtml = (value = "") =>
        value
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");

    const setBadge = (el, value) => {
        if (!el) return;
        const count = Number(value) || 0;
        el.textContent = count > 99 ? "99+" : String(count);
        el.style.display = count > 0 ? "inline-flex" : "none";
    };

    const renderEmpty = (target, message) => {
        if (!target) return;
        target.innerHTML = `<div class="notify-empty">${message}</div>`;
    };

    const renderLikes = (items = []) => {
        if (!likeList) return;
        if (!items.length) {
            renderEmpty(likeList, "No likes yet.");
            return;
        }
        likeList.innerHTML = items
            .map(
                (item) => `
                <div class="notify-item">
                    <img class="notify-thumb" src="${item.thumb_url}" alt="${escapeHtml(
                    item.image_name
                )}">
                    <div class="notify-meta">
                        <div class="notify-title">${escapeHtml(item.actor)} liked</div>
                        <div class="notify-sub">${escapeHtml(item.image_name)}</div>
                        <a class="notify-link" href="${item.link}" data-notify-link data-event-type="like" data-image-id="${item.image_id}" data-actor-id="${item.actor_id}" data-created-at="${item.created_at}">View image</a>
                    </div>
                </div>
            `
            )
            .join("");
    };

    const renderComments = (items = []) => {
        if (!commentList) return;
        if (!items.length) {
            renderEmpty(commentList, "No comments yet.");
            return;
        }
        commentList.innerHTML = items
            .map(
                (item) => `
                <div class="notify-item">
                    <img class="notify-thumb" src="${item.thumb_url}" alt="${escapeHtml(
                    item.image_name
                )}">
                    <div class="notify-meta">
                        <div class="notify-title">${escapeHtml(item.actor)} commented</div>
                        <div class="notify-sub">${escapeHtml(item.body).slice(0, 80)}</div>
                        <a class="notify-link" href="${item.link}" data-notify-link data-event-type="comment" data-image-id="${item.image_id}" data-actor-id="${item.actor_id}" data-created-at="${item.created_at}">View image</a>
                    </div>
                </div>
            `
            )
            .join("");
    };

    const markAllRead = async () => {
        try {
            const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || "";
            const resp = await fetch("/api/notifications/read", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrfToken,
                },
                credentials: "same-origin",
                body: JSON.stringify({}),
            });
            if (!resp.ok) return;
            setBadge(likeBadge, 0);
            setBadge(commentBadge, 0);
            if (likeCount) likeCount.textContent = "0 total";
            if (commentCount) commentCount.textContent = "0 total";
            renderEmpty(likeList, "All caught up.");
            renderEmpty(commentList, "All caught up.");
        } catch (err) {
            // ignore
        }
    };

    const markItemRead = async (payload) => {
        if (!payload) return;
        try {
            const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || "";
            await fetch("/api/notifications/read-item", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrfToken,
                },
                credentials: "same-origin",
                body: JSON.stringify(payload),
            });
        } catch (err) {
            // ignore
        }
    };

    const loadCounts = async () => {
        try {
            const resp = await fetch("/api/notifications");
            if (!resp.ok) return;
            const data = await resp.json();
            setBadge(likeBadge, data.like_unread ?? data.like_total);
            setBadge(commentBadge, data.comment_unread ?? data.comment_total);
        } catch (err) {
            // ignore
        }
    };

    const loadDetails = async () => {
        if (!modalEl) return;
        renderEmpty(likeList, "Loading likes...");
        renderEmpty(commentList, "Loading comments...");
        try {
            const resp = await fetch("/api/notifications");
            if (!resp.ok) throw new Error("Failed");
            const data = await resp.json();
            setBadge(likeBadge, data.like_unread ?? data.like_total);
            setBadge(commentBadge, data.comment_unread ?? data.comment_total);
            if (likeCount) {
                likeCount.textContent = `${data.like_unread ?? 0} unread`;
            }
            if (commentCount) {
                commentCount.textContent = `${data.comment_unread ?? 0} unread`;
            }
            renderLikes(data.likes || []);
            renderComments(data.comments || []);
        } catch (err) {
            renderEmpty(likeList, "Unable to load likes.");
            renderEmpty(commentList, "Unable to load comments.");
        }
    };

    notifyButton.addEventListener("click", () => {
        if (!modalEl) return;
        const modalApi = window.bootstrap?.Modal;
        if (modalApi) {
            modalApi.getOrCreateInstance(modalEl).show();
            loadDetails();
        }
    });

    modalEl?.querySelector("[data-mark-read]")?.addEventListener("click", markAllRead);

    modalEl?.addEventListener("click", (event) => {
        const link = event.target.closest("[data-notify-link]");
        if (!link) return;
        const createdAt = link.dataset.createdAt;
        event.preventDefault();
        const target = link.href;
        markItemRead({
            event_type: link.dataset.eventType,
            image_id: link.dataset.imageId,
            actor_id: link.dataset.actorId,
            event_created_at: createdAt,
        }).finally(() => {
            window.location.assign(target);
        });
    });

    document.addEventListener("DOMContentLoaded", () => {
        loadCounts();
        setInterval(loadCounts, 60000);
    });
})();
