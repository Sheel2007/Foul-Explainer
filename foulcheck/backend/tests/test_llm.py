import json

import pytest
from pydantic import BaseModel

from foulcheck import config, llm


class Out(BaseModel):
    x: int


class Busy(Exception):
    code = 503


class BadRequest(Exception):
    code = 400


@pytest.fixture(autouse=True)
def tmp_logs(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "LOGS_DIR", tmp_path / "logs")
    return tmp_path / "logs"


def test_is_transient():
    assert llm.is_transient(Busy())
    assert not llm.is_transient(BadRequest())
    assert llm.is_transient(TimeoutError())
    assert not llm.is_transient(Busy("429 RESOURCE_EXHAUSTED quotaId GenerateRequestsPerDayPerProjectPerModel-FreeTier"))


def test_retries_transient_then_succeeds_and_logs(tmp_logs):
    calls = iter([Busy(), Busy(), '{"x": 1}'])

    def fn():
        v = next(calls)
        if isinstance(v, Exception):
            raise v
        return v

    assert llm.call("t", fn, request={"q": 1}, base_delay=0) == '{"x": 1}'
    records = [json.loads(p.read_text()) for p in tmp_logs.rglob("*.json")]
    assert len(records) == 3
    assert sum("error" in r for r in records) == 2
    assert all(r["request"] == {"q": 1} for r in records)


def test_non_transient_fails_fast():
    n = 0

    def fn():
        nonlocal n
        n += 1
        raise BadRequest("nope")

    with pytest.raises(llm.ModelCallError):
        llm.call("t", fn, request={}, base_delay=0)
    assert n == 1


def test_generate_json_repairs_once_with_error_text():
    seen = []

    def run(repair):
        seen.append(repair)
        return '{"x": "not a number"}' if repair is None else '{"x": 2}'

    assert llm.generate_json("t", Out, run, request={}).x == 2
    assert seen[0] is None and "x" in seen[1]


def test_generate_json_check_hook_and_give_up():
    def check(o: Out):
        raise ValueError("always wrong")

    with pytest.raises(llm.ModelOutputError, match="always wrong"):
        llm.generate_json("t", Out, lambda r: '{"x": 1}', request={}, check=check)


class RateLimited(Exception):
    code = 429


def _count_calls(exc_factory, monkeypatch, n_fail=99):
    sleeps, calls = [], []
    monkeypatch.setattr(llm.time, "sleep", sleeps.append)

    def fn():
        calls.append(1)
        if len(calls) <= n_fail:
            raise exc_factory()
        return "ok"
    return fn, sleeps, calls


def test_server_errors_capped_at_three_attempts(monkeypatch):
    fn, sleeps, calls = _count_calls(lambda: Busy("503 UNAVAILABLE"), monkeypatch)
    with pytest.raises(llm.ModelCallError, match="after 3 attempt"):
        llm.call("t", fn, request={}, retries=5)
    assert len(calls) == 3 and sleeps == [20.0, 60.0]


def test_per_minute_limit_waits_for_server_hint(monkeypatch):
    msg = "429 RESOURCE_EXHAUSTED quotaId': 'GenerateRequestsPerMinutePerProjectPerModel-FreeTier' 'retryDelay': '52s'"
    fn, sleeps, calls = _count_calls(lambda: RateLimited(msg), monkeypatch, n_fail=2)
    assert llm.call("t", fn, request={}, retries=5) == "ok"
    assert len(calls) == 3 and all(53 <= s <= 55 for s in sleeps)


def test_daily_quota_not_retried(monkeypatch):
    msg = "429 quotaId': 'GenerateRequestsPerDayPerProjectPerModel-FreeTier' 'retryDelay': '22155s'"
    fn, sleeps, calls = _count_calls(lambda: RateLimited(msg), monkeypatch)
    with pytest.raises(llm.ModelCallError, match="after 1 attempt"):
        llm.call("t", fn, request={})
    assert sleeps == []
