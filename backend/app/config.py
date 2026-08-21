from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ADMIN_PASSWORD_HASH = (
    "pbkdf2_sha256$310000$3VvI_J65X3m6DqA_w_g77w==$"
    "BaKp_Bv0HdF3dbfrhZTiz3fCIM0Dd5GmUeyyZZLU5lM="
)


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


def _bool_from_env(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None or raw_value.strip() == "":
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    app_env: str
    ai_provider: str
    ai_provider_chain: tuple[str, ...]
    chat_provider_chain: tuple[str, ...]
    auto_ocr_on_import: bool
    auto_ocr_max_workers: int
    auto_ocr_batch_size: int
    storage_root: Path
    upload_root: Path
    asset_root: Path
    database_path: Path
    frontend_dist: Path
    max_upload_bytes: int
    public_base_url: str
    openai_api_key: str
    openai_model: str
    gemini_api_key: str
    gemini_api_keys: tuple[str, ...]
    gemini_model: str
    gemini_chat_models: tuple[str, ...]
    openrouter_api_key: str
    openrouter_ocr_model: str
    openrouter_chat_model: str
    tokenrouter_api_key: str
    tokenrouter_base_url: str
    tokenrouter_chat_model: str
    nvidia_api_key: str
    nvidia_ocr_model: str
    nvidia_ocr_base_url: str
    nvidia_chat_model: str
    admin_username: str
    admin_password: str
    admin_password_hash: str
    admin_session_days: int


def _list_from_env(name: str) -> tuple[str, ...]:
    raw_value = os.getenv(name, "")
    values = [item.strip() for item in raw_value.replace("\n", ",").split(",")]
    return tuple(item for item in values if item)


def _provider_chain_from_env(name: str, fallback_provider: str) -> tuple[str, ...]:
    providers = _list_from_env(name)
    if not providers:
        providers = (fallback_provider,)
    cleaned: list[str] = []
    for provider in providers:
        value = provider.strip().lower()
        if value and value not in cleaned:
            cleaned.append(value)
    return tuple(cleaned)


def _model_chain_from_env(name: str, defaults: tuple[str, ...]) -> tuple[str, ...]:
    models = _list_from_env(name) or defaults
    cleaned: list[str] = []
    for model in models:
        value = model.strip()
        if value and value not in cleaned:
            cleaned.append(value)
    return tuple(cleaned)


def get_settings() -> Settings:
    load_dotenv()
    storage_root = _path_from_env("MATH_EXAM_STORAGE_ROOT", "storage")
    database_path = _path_from_env("MATH_EXAM_DATABASE_PATH", "storage/math_exam.sqlite3")
    max_upload_mb = _int_from_env("MAX_UPLOAD_MB", 25)
    gemini_api_key = os.getenv("GEMINI_API_KEY", "").strip()
    gemini_model = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite").strip()
    gemini_api_keys = []
    if gemini_api_key:
        gemini_api_keys.append(gemini_api_key)
    for key in _list_from_env("GEMINI_API_KEYS"):
        if key not in gemini_api_keys:
            gemini_api_keys.append(key)
    return Settings(
        app_env=os.getenv("APP_ENV", "local"),
        ai_provider=os.getenv("AI_PROVIDER", "openai").strip().lower(),
        ai_provider_chain=_provider_chain_from_env("AI_PROVIDER_CHAIN", os.getenv("AI_PROVIDER", "openai").strip().lower()),
        chat_provider_chain=_provider_chain_from_env("CHAT_PROVIDER_CHAIN", os.getenv("AI_PROVIDER", "openai").strip().lower()),
        auto_ocr_on_import=_bool_from_env("AUTO_OCR_ON_IMPORT", False),
        auto_ocr_max_workers=max(1, _int_from_env("AUTO_OCR_MAX_WORKERS", 6)),
        auto_ocr_batch_size=max(1, _int_from_env("AUTO_OCR_BATCH_SIZE", 20)),
        storage_root=storage_root,
        upload_root=storage_root / "uploads",
        asset_root=storage_root / "extracted-assets",
        database_path=database_path,
        frontend_dist=PROJECT_ROOT / "frontend" / "dist",
        max_upload_bytes=max_upload_mb * 1024 * 1024,
        public_base_url=os.getenv("PUBLIC_BASE_URL", "").strip().rstrip("/"),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-5-mini"),
        gemini_api_key=gemini_api_key,
        gemini_api_keys=tuple(gemini_api_keys),
        gemini_model=gemini_model,
        gemini_chat_models=_model_chain_from_env(
            "GEMINI_CHAT_MODEL_CHAIN",
            (gemini_model, "gemini-3.5-flash-lite"),
        ),
        openrouter_api_key=os.getenv("OPENROUTER_API_KEY", "").strip(),
        openrouter_ocr_model=os.getenv("OPENROUTER_OCR_MODEL", "nvidia/nemotron-nano-12b-v2-vl:free"),
        openrouter_chat_model=os.getenv("OPENROUTER_CHAT_MODEL", "nvidia/nemotron-nano-12b-v2-vl:free"),
        tokenrouter_api_key=os.getenv("TOKENROUTER_API_KEY", "").strip(),
        tokenrouter_base_url=os.getenv("TOKENROUTER_BASE_URL", "https://api.tokenrouter.com/v1").strip().rstrip("/"),
        tokenrouter_chat_model=os.getenv("TOKENROUTER_CHAT_MODEL", "deepseek/deepseek-v4-flash").strip(),
        nvidia_api_key=os.getenv("NVIDIA_API_KEY", "").strip(),
        nvidia_ocr_model=os.getenv("NVIDIA_OCR_MODEL", "nvidia/nemotron-ocr-v2"),
        nvidia_ocr_base_url=os.getenv("NVIDIA_OCR_BASE_URL", "").strip().rstrip("/"),
        nvidia_chat_model=os.getenv("NVIDIA_CHAT_MODEL", "nvidia/nemotron-3-nano-30b-a3b"),
        admin_username=os.getenv("ADMIN_USERNAME", "0912311121").strip(),
        admin_password=os.getenv("ADMIN_PASSWORD", ""),
        admin_password_hash=os.getenv("ADMIN_PASSWORD_HASH", DEFAULT_ADMIN_PASSWORD_HASH),
        admin_session_days=max(1, _int_from_env("ADMIN_SESSION_DAYS", 7)),
    )
