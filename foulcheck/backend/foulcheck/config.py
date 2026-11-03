"""Pinned settings. Changing the Laws edition is a data swap, not a code change."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = BACKEND_DIR.parent
load_dotenv(REPO_DIR / ".env")

LOGS_DIR = Path(os.environ.get("FOULCHECK_LOGS_DIR", REPO_DIR / "logs"))
CACHE_DIR = Path(os.environ.get("FOULCHECK_CACHE_DIR", BACKEND_DIR / "data" / "cache"))

EDITIONS = {
    "2026-27": {
        "label": "Laws of the Game 2026/27",
        "pdf_url": "https://downloads.theifab.com/downloads/laws-of-the-game-202627-double-pages?l=en",
        "effective": "2026-07-01",
    },
}


@dataclass(frozen=True)
class LawsConfig:
    edition: str
    label: str
    pdf_url: str
    data_dir: Path

    @property
    def pdf_path(self) -> Path:
        return self.data_dir / "raw" / "laws.pdf"

    @property
    def chunks_path(self) -> Path:
        return self.data_dir / "chunks.jsonl"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "laws.sqlite"


def laws_config(edition: str | None = None) -> LawsConfig:
    edition = edition or os.environ.get("LAWS_EDITION", "2026-27")
    meta = EDITIONS[edition]
    return LawsConfig(
        edition=edition,
        label=meta["label"],
        pdf_url=meta["pdf_url"],
        data_dir=BACKEND_DIR / "data" / "laws" / edition,
    )


EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")

# Video analysis. See "Video understanding" in the build plan for why fps matters so much.
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-5-5")
LOCATE_FPS = 2
INSPECT_FPS = 12
INSPECT_HALF_WINDOW = 1.5  # seconds either side of the contact moment
MODEL_TIMEOUT_S = 180
MODEL_RETRIES = 5

# Decision engine (text only; never sees video).
DECISION_PROVIDER = os.environ.get("DECISION_PROVIDER", "gemini")  # "gemini" or "claude"
# gemini-3.6-flash: ~28 s per clip for two decision runs vs ~110 s on gemini-3.8-flash (Phase 3 run).
DECISION_MODEL = os.environ.get("DECISION_MODEL", "gemini-3.6-flash" if DECISION_PROVIDER == "gemini" else None)

# Web app
UPLOAD_DIR = Path(os.environ.get("FOULCHECK_UPLOAD_DIR", BACKEND_DIR / "data" / "uploads"))
FEEDBACK_PATH = Path(os.environ.get("FOULCHECK_FEEDBACK_PATH", BACKEND_DIR / "data" / "feedback" / "feedback.jsonl"))
RENDER_DIR = Path(os.environ.get("FOULCHECK_RENDER_DIR", BACKEND_DIR / "data" / "renders"))
RENDER_TTL_S = 2 * 60 * 60  # explained videos contain the clip, so they are deleted after this
MAX_UPLOAD_BYTES = 100 * 1024 * 1024
MAX_CLIP_SECONDS = 60
# Whether the web app may fall back to the server's own GEMINI_API_KEY when a visitor gives none.
# Off by default so a public deployment can't spend the owner's quota; set it in .env for local use.
ALLOW_SERVER_KEY = os.environ.get("FOULCHECK_ALLOW_SERVER_KEY", "").lower() in ("1", "true", "yes")
FRONTEND_ORIGINS = os.environ.get("FRONTEND_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
