from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load_dotenv(path: Path | None = None) -> None:
    env_path = path or PROJECT_ROOT / ".env"
    if not env_path.is_file():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _path_from_env(name: str, default: str) -> Path:
    raw_value = os.getenv(name, default)
    candidate = Path(raw_value)
    if not candidate.is_absolute():
        candidate = PROJECT_ROOT / candidate
    return candidate


def _int_from_env(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None or raw_value.strip() == "":
        return default
    try:
        return int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer.") from exc


@dataclass(frozen=True)
class Settings:
    app_env: str
    storage_root: Path
    upload_root: Path
    asset_root: Path
    database_path: Path
    frontend_dist: Path
    max_upload_bytes: int
    openai_api_key: str
    openai_model: str


def get_settings() -> Settings:
    load_dotenv()
    storage_root = _path_from_env("MATH_EXAM_STORAGE_ROOT", "storage")
    database_path = _path_from_env("MATH_EXAM_DATABASE_PATH", "storage/math_exam.sqlite3")
    max_upload_mb = _int_from_env("MAX_UPLOAD_MB", 25)
    return Settings(
        app_env=os.getenv("APP_ENV", "local"),
        storage_root=storage_root,
        upload_root=storage_root / "uploads",
        asset_root=storage_root / "extracted-assets",
        database_path=database_path,
        frontend_dist=PROJECT_ROOT / "frontend" / "dist",
        max_upload_bytes=max_upload_mb * 1024 * 1024,
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-5-mini"),
    )
