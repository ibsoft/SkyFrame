from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func, or_

from .extensions import db
from .models import FeedSeen, Image


@dataclass
class FeedCursor:
    prioritized: str | None = None
    global_new: str | None = None


@dataclass
class FeedSelection:
    images: list[Image]
    next_cursor: str
    seen_ids: set[int]
    has_more: bool


def parse_feed_cursor(cursor: str | None) -> FeedCursor:
    if not cursor:
        return FeedCursor()
    if "|" in cursor and ("p=" in cursor or "g=" in cursor):
        parts = cursor.split("|")
        parsed = FeedCursor()
        for part in parts:
            if part.startswith("p="):
                parsed.prioritized = part[2:] or None
            elif part.startswith("g="):
                parsed.global_new = part[2:] or None
        return parsed
    if cursor == "random":
        return FeedCursor()
    return FeedCursor(global_new=cursor)


def format_feed_cursor(prioritized: str | None, global_new: str | None) -> str:
    if not prioritized and not global_new:
        return ""
    return f"p={prioritized or ''}|g={global_new or ''}"


def _parse_cursor_point(cursor_value: str | None):
    if not cursor_value:
        return None, None
    try:
        timestamp, image_id = cursor_value.split("_")
        return datetime.fromisoformat(timestamp), int(image_id)
    except ValueError:
        return None, None


def _apply_cursor(query, cursor_value: str | None):
    cursor_point, cursor_image_id = _parse_cursor_point(cursor_value)
    if cursor_point is None:
        return query
    return query.filter(
        (Image.observed_at < cursor_point)
        | ((Image.observed_at == cursor_point) & (Image.id < cursor_image_id))
    )


def _prioritized_filter(liked_ids: set[int], following_ids: set[int]):
    conditions = []
    if liked_ids:
        conditions.append(Image.id.in_(liked_ids))
    if following_ids:
        conditions.append(Image.user_id.in_(following_ids))
    if not conditions:
        return None
    return or_(*conditions)


def _pop_next_valid(
    pool: list[Image],
    per_uploader_counts: dict[int, int],
    last_uploader: int | None,
    consecutive: int,
    max_per_uploader: int,
    max_consecutive: int,
):
    for idx, image in enumerate(pool):
        uploader_id = image.user_id
        if max_per_uploader > 0 and per_uploader_counts[uploader_id] >= max_per_uploader:
            continue
        if max_consecutive > 0 and last_uploader == uploader_id and consecutive >= max_consecutive:
            continue
        return pool.pop(idx), uploader_id
    return None, last_uploader


def _blend_feed(
    prioritized: list[Image],
    global_new: list[Image],
    per_page: int,
    prioritized_target: int,
    max_per_uploader: int,
    max_consecutive: int,
):
    output: list[Image] = []
    per_uploader_counts: dict[int, int] = defaultdict(int)
    last_uploader = None
    consecutive = 0
    prioritized_taken = 0

    last_prioritized = None
    last_global = None

    while len(output) < per_page and (prioritized or global_new):
        take_prioritized = prioritized_taken < prioritized_target
        selected = None
        selected_uploader = None
        picked_from_prioritized = False
        if take_prioritized:
            selected, selected_uploader = _pop_next_valid(
                prioritized,
                per_uploader_counts,
                last_uploader,
                consecutive,
                max_per_uploader,
                max_consecutive,
            )
            if selected is None:
                selected, selected_uploader = _pop_next_valid(
                    global_new,
                    per_uploader_counts,
                    last_uploader,
                    consecutive,
                    max_per_uploader,
                    max_consecutive,
                )
            else:
                picked_from_prioritized = True
        else:
            selected, selected_uploader = _pop_next_valid(
                global_new,
                per_uploader_counts,
                last_uploader,
                consecutive,
                max_per_uploader,
                max_consecutive,
            )
            if selected is None:
                selected, selected_uploader = _pop_next_valid(
                    prioritized,
                    per_uploader_counts,
                    last_uploader,
                    consecutive,
                    max_per_uploader,
                    max_consecutive,
                )
                if selected is not None:
                    picked_from_prioritized = True

        if selected is None:
            break

        output.append(selected)
        per_uploader_counts[selected_uploader] += 1
        if last_uploader == selected_uploader:
            consecutive += 1
        else:
            last_uploader = selected_uploader
            consecutive = 1
        if picked_from_prioritized:
            prioritized_taken += 1
            last_prioritized = selected
        else:
            last_global = selected

    return output, last_prioritized, last_global


def _fresh_cutoff(days: int | None):
    if not days or days <= 0:
        return None
    return datetime.utcnow() - timedelta(days=days)


def _load_seen_ids(user_id: int, retention_days: int, max_ids: int):
    cutoff = _fresh_cutoff(retention_days)
    query = FeedSeen.query.filter_by(user_id=user_id)
    if cutoff:
        query = query.filter(FeedSeen.seen_at >= cutoff)
    rows = query.order_by(FeedSeen.seen_at.desc()).limit(max_ids).all()
    return {row.image_id for row in rows}


def _persist_seen_ids(user_id: int, image_ids: list[int], retention_days: int):
    if not image_ids:
        return
    now = datetime.utcnow()
    existing = {
        row.image_id
        for row in FeedSeen.query.filter(
            FeedSeen.user_id == user_id, FeedSeen.image_id.in_(image_ids)
        ).all()
    }
    new_rows = [
        FeedSeen(user_id=user_id, image_id=image_id, seen_at=now)
        for image_id in image_ids
        if image_id not in existing
    ]
    changed = False
    if new_rows:
        db.session.bulk_save_objects(new_rows)
        changed = True
    if retention_days > 0:
        cutoff = datetime.utcnow() - timedelta(days=retention_days)
        removed = FeedSeen.query.filter(
            FeedSeen.user_id == user_id, FeedSeen.seen_at < cutoff
        ).delete()
        if removed:
            changed = True
    if changed:
        db.session.commit()


def build_feed_selection(
    *,
    liked_ids: set[int],
    following_ids: set[int],
    per_page: int,
    cursor: str | None,
    fresh_days: int,
    prioritized_pct: int,
    candidate_multiplier: int,
    max_per_uploader: int,
    max_consecutive: int,
    seen_enabled: bool,
    seen_user_id: int | None,
    seen_retention_days: int,
    seen_max_ids: int,
) -> FeedSelection:
    prioritized_pct = max(0, min(prioritized_pct, 100))
    use_seen = seen_enabled and seen_user_id is not None
    prioritized_target = int(round(per_page * (prioritized_pct / 100.0)))
    candidate_limit = max(per_page * candidate_multiplier, per_page)

    cursor_state = parse_feed_cursor(cursor)
    cutoff = _fresh_cutoff(fresh_days)

    seen_ids: set[int] = set()
    if use_seen:
        seen_ids = _load_seen_ids(seen_user_id, seen_retention_days, seen_max_ids)

    prioritized_filter = _prioritized_filter(liked_ids, following_ids)
    prioritized_candidates: list[Image] = []
    if prioritized_filter is not None:
        query = Image.query.filter(prioritized_filter)
        if cutoff:
            query = query.filter(Image.observed_at >= cutoff)
        if seen_ids:
            query = query.filter(~Image.id.in_(seen_ids))
        if not use_seen:
            query = _apply_cursor(query, cursor_state.prioritized)
        prioritized_candidates = (
            query.order_by(Image.observed_at.desc(), Image.id.desc())
            .limit(candidate_limit)
            .all()
        )

    prioritized_ids = {img.id for img in prioritized_candidates}

    random_query = Image.query
    if seen_ids:
        random_query = random_query.filter(~Image.id.in_(seen_ids))
    if prioritized_ids:
        random_query = random_query.filter(~Image.id.in_(prioritized_ids))
    random_candidates = (
        random_query.order_by(func.random())
        .limit(candidate_limit)
        .all()
    )
    images, last_prioritized, last_global = _blend_feed(
        prioritized_candidates,
        random_candidates,
        per_page,
        prioritized_target,
        max_per_uploader,
        max_consecutive,
    )

    has_more = len(prioritized_candidates) + len(random_candidates) > len(images)
    if use_seen:
        next_cursor = "seen" if has_more else ""
    else:
        prioritized_cursor = (
            f"{last_prioritized.observed_at.isoformat()}_{last_prioritized.id}"
            if last_prioritized and prioritized_filter is not None
            else cursor_state.prioritized
        )
        global_cursor = "random" if random_candidates else cursor_state.global_new
        next_cursor = format_feed_cursor(prioritized_cursor, global_cursor)
        if not images:
            next_cursor = ""

    if not images:
        fallback_images = Image.query.order_by(func.random()).limit(per_page).all()
        images = fallback_images
        next_cursor = "random" if images else ""
        has_more = bool(images)

    return FeedSelection(images=images, next_cursor=next_cursor, seen_ids=seen_ids, has_more=has_more)


def persist_seen_for_feed(
    *,
    user_id: int | None,
    images: list[Image],
    retention_days: int,
):
    if user_id is None:
        return
    image_ids = [image.id for image in images]
    _persist_seen_ids(user_id, image_ids, retention_days)
