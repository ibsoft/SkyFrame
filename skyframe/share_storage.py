import json
import secrets
from datetime import datetime
from pathlib import Path

from .config import Config
from .models import Image


def _share_root() -> Path:
    root = Path(Config.SHARE_PATH)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _share_path(token: str) -> Path:
    return _share_root() / f"{token}.json"


def create_share_token(image: Image) -> str:
    token = secrets.token_urlsafe(36)
    payload = {
        "token": token,
        "image_id": image.id,
        "user_id": image.user_id,
        "created_at": datetime.utcnow().isoformat(),
    }
    _share_path(token).write_text(json.dumps(payload))
    return token


def read_share_token(token: str) -> dict:
    path = _share_path(token)
    if not path.exists():
        raise FileNotFoundError("Share token missing")
    return json.loads(path.read_text())
