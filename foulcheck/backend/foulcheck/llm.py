"""The one place model calls go through: retries, timeouts, structured parsing, and logging.

Every call writes a JSON record (request summary, raw response, error, latency) to logs/<date>/.
Media bytes are never logged; callers pass a summary describing what was sent.
"""

import json
import random
import re
import time
import uuid
from collections.abc import Callable
from datetime import datetime
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from foulcheck import config

T = TypeVar("T")
M = TypeVar("M", bound=BaseModel)

TRANSIENT_STATUS = {408, 409, 429, 500, 502, 503, 504, 529}
# On the free tier every request, failed or not, counts toward the daily quota, so server-side
# failures (overload, timeouts) get few attempts and long gaps.
SERVER_ERROR_ATTEMPTS = 3
SERVER_ERROR_BACKOFF = (5, 15)  # multiples of base_delay: 20 s then 60 s at the default 4 s
MAX_SERVER_HINT_S = 120.0
RETRY_HINT = re.compile(r"retryDelay'?\s*:\s*'?(\d+(?:\.\d+)?)s")


class ModelCallError(RuntimeError):
    pass


class ModelOutputError(RuntimeError):
    """The model answered, but its output never passed validation."""


def is_transient(exc: Exception) -> bool:
    if "PerDay" in str(exc) or "per day" in str(exc).lower():
        return False  # a daily quota will not recover within any sensible retry window
    for attr in ("code", "status_code", "status"):
        status = getattr(exc, attr, None)
        if isinstance(status, int):
            return status in TRANSIENT_STATUS
    name = type(exc).__name__.lower()
    return "timeout" in name or "connection" in name or isinstance(exc, (TimeoutError, ConnectionError))


def _status(exc: Exception) -> int | None:
    for attr in ("code", "status_code", "status"):
        status = getattr(exc, attr, None)
        if isinstance(status, int):
            return status
    return None


def _retry_plan(exc: Exception, attempt: int, retries: int, base_delay: float) -> float | None:
    """Seconds to wait before the next attempt, or None to give up."""
    if not is_transient(exc):
        return None
    hint = RETRY_HINT.search(str(exc))
    if _status(exc) == 429 and hint:
        # Per-minute rate limit: the server says when a slot frees up.
        return None if attempt >= retries else min(float(hint.group(1)), MAX_SERVER_HINT_S) + random.uniform(1, 3)
    if (_status(exc) or 0) >= 500:
        if attempt >= min(retries, SERVER_ERROR_ATTEMPTS):
            return None
        return base_delay * SERVER_ERROR_BACKOFF[min(attempt - 1, len(SERVER_ERROR_BACKOFF) - 1)]
    return None if attempt >= retries else base_delay * 2 ** (attempt - 1) + random.uniform(0, 1)


def _log(record: dict) -> None:
    now = datetime.now()
    day = config.LOGS_DIR / now.strftime("%Y-%m-%d")
    day.mkdir(parents=True, exist_ok=True)
    path = day / f"{now.strftime('%H%M%S')}-{record['label']}-{uuid.uuid4().hex[:6]}.json"
    path.write_text(json.dumps(record, indent=2, default=str))


def call(label: str, fn: Callable[[], T], *, request: dict,
         retries: int = config.MODEL_RETRIES, base_delay: float = 4.0) -> T:
    """Run fn with retries on transient errors. fn returns the model's raw text."""
    for attempt in range(1, retries + 1):
        start = time.monotonic()
        record = {"label": label, "attempt": attempt, "request": request}
        try:
            result = fn()
            record.update(latency_s=round(time.monotonic() - start, 2), response=result)
            _log(record)
            return result
        except Exception as exc:
            record.update(latency_s=round(time.monotonic() - start, 2), error=f"{type(exc).__name__}: {exc}")
            _log(record)
            wait = _retry_plan(exc, attempt, retries, base_delay)
            if wait is None:
                raise ModelCallError(f"{label} failed after {attempt} attempt(s): {exc}") from exc
            time.sleep(wait)
    raise AssertionError("unreachable")


def generate_json(label: str, schema: type[M], run: Callable[[str | None], str], *, request: dict,
                  check: Callable[[M], None] | None = None) -> M:
    """Call a model that returns JSON and parse it into `schema`.

    `run(repair)` performs one model call; `repair` is None first, then the validation error
    text, so the caller can show the model what was wrong. `check` adds rules beyond the schema
    and raises ValueError to trigger the same single repair retry.
    """
    repair: str | None = None
    for attempt in (1, 2):
        text = call(f"{label}-try{attempt}", lambda: run(repair), request={**request, "repair": repair})
        try:
            parsed = schema.model_validate_json(text or "")
            if check:
                check(parsed)
            return parsed
        except (ValidationError, ValueError) as exc:
            repair = str(exc)
    raise ModelOutputError(f"{label}: output invalid after repair retry: {repair}")
