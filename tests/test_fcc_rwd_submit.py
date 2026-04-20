from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "fcc_rwd_submit.py"
SPEC = importlib.util.spec_from_file_location("fcc_rwd_submit", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
fcc = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = fcc
SPEC.loader.exec_module(fcc)


def test_run_atomic_write_uses_single_eval(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, fcc.RuntimeConfig]] = []

    def fake_run_tappi_eval(js: str, config: fcc.RuntimeConfig) -> tuple[int, str, str]:
        calls.append((js, config))
        return 0, '{"ok": true, "before": {"state": {"url": "https://www.freecodecamp.org/learn/2022/responsive-web-design/test/step-1", "isFreeCodeCampChallenge": true, "hasEditor": true}, "primaryButton": {"text": "Check Your Code", "rawText": "Check Your Code"}}, "mutationAttempted": true, "actualCode": "<h1>Hello</h1>"}', ""

    monkeypatch.setattr(fcc, "run_tappi_eval", fake_run_tappi_eval)

    result = fcc.run_atomic_write("<h1>Hello</h1>", fcc.RuntimeConfig(cdp_url="http://127.0.0.1:9223"))

    assert result["ok"] is True
    assert result["mutationAttempted"] is True
    assert len(calls) == 1
    assert "setValue" in calls[0][0]


@pytest.mark.parametrize(
    ("requested", "expected_aliases"),
    [
        ("Check Your Code", ["Check Your Code", "检查你的代码"]),
        ("检查你的代码", ["Check Your Code", "检查你的代码"]),
        ("Submit and go to next challenge", ["Submit and go to next challenge", "提交并继续"]),
        ("提交并继续", ["Submit and go to next challenge", "提交并继续"]),
    ],
)
def test_run_atomic_click_accepts_any_supported_alias(
    monkeypatch: pytest.MonkeyPatch,
    requested: str,
    expected_aliases: list[str],
) -> None:
    calls: list[str] = []

    def fake_run_tappi_eval(js: str, config: fcc.RuntimeConfig) -> tuple[int, str, str]:
        del config
        calls.append(js)
        return 0, '{"ok": true, "before": {"state": {"url": "https://www.freecodecamp.org/learn/2022/responsive-web-design/test/step-1", "isFreeCodeCampChallenge": true}, "primaryButton": {"text": "Check Your Code", "rawText": "Check Your Code", "i": 0}}, "mutationAttempted": true}', ""

    monkeypatch.setattr(fcc, "run_tappi_eval", fake_run_tappi_eval)

    result = fcc.run_atomic_click(requested, fcc.RuntimeConfig(cdp_url="http://127.0.0.1:9223"))

    assert result["ok"] is True
    assert result["mutationAttempted"] is True
    assert len(calls) == 1
    assert ".click()" in calls[0]
    for alias in expected_aliases:
        assert alias in calls[0]


def test_write_and_verify_marks_post_validation_failure_as_mutated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        fcc,
        "run_atomic_write",
        lambda code, config: {
            "ok": True,
            "before": {
                "state": {
                    "url": "https://www.freecodecamp.org/learn/2022/responsive-web-design/test/step-1"
                },
                "primaryButton": {"text": "Check Your Code", "rawText": "Check Your Code"},
                "cdpUrl": config.cdp_url,
            },
            "actualCode": code,
            "mutationAttempted": True,
        },
    )
    monkeypatch.setattr(
        fcc,
        "validate_target",
        lambda config, require_editor=False: (
            False,
            {
                "error": "Challenge editor disappeared.",
                "state": None,
                "primaryButton": None,
                "cdpUrl": config.cdp_url,
            },
        ),
    )

    ok, payload = fcc.write_and_verify("<main></main>", fcc.RuntimeConfig(cdp_url="http://127.0.0.1:9223"))

    assert ok is False
    assert payload["phase"] == "post_write_validation"
    assert payload["mutationAttempted"] is True
    assert payload["before"]["state"]["url"].endswith("/step-1")
    assert payload["after"]["error"] == "Challenge editor disappeared."


def test_click_and_wait_marks_post_validation_failure_as_mutated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        fcc,
        "run_atomic_click",
        lambda btn_text, config: {
            "ok": True,
            "before": {
                "state": {
                    "url": "https://www.freecodecamp.org/learn/2022/responsive-web-design/test/step-1"
                },
                "primaryButton": {"text": "Check Your Code", "rawText": "Check Your Code"},
                "cdpUrl": config.cdp_url,
            },
            "requested": btn_text,
            "mutationAttempted": True,
        },
    )
    monkeypatch.setattr(fcc.time, "sleep", lambda _: None)
    times = iter([0.0, 0.0, 0.1, 0.2, 0.3])
    monkeypatch.setattr(fcc.time, "time", lambda: next(times))
    monkeypatch.setattr(
        fcc,
        "build_status_payload",
        lambda config: {
            "state": {
                "url": "https://www.freecodecamp.org/learn/2022/responsive-web-design/test/step-2"
            },
            "primaryButton": {
                "text": "Submit and go to next challenge",
                "rawText": "Submit and go to next challenge",
            },
            "cdpUrl": config.cdp_url,
        },
    )
    monkeypatch.setattr(
        fcc,
        "validate_target",
        lambda config, require_editor=False: (
            False,
            {
                "error": "Bound browser target drifted.",
                "state": None,
                "primaryButton": None,
                "cdpUrl": config.cdp_url,
            },
        ),
    )

    payload = fcc.click_and_wait("检查你的代码", fcc.RuntimeConfig(cdp_url="http://127.0.0.1:9223"))

    assert payload["phase"] == "post_click_validation"
    assert payload["mutationAttempted"] is True
    assert payload["clicked"] == "检查你的代码"
    assert payload["after"]["error"] == "Bound browser target drifted."
