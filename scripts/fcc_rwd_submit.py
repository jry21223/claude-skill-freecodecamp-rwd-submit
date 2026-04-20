#!/usr/bin/env python3
"""freeCodeCamp RWD submission helper - wraps brittle browser ops via tappi."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


BUTTON_ALIASES = {
    "Check Your Code": ["Check Your Code", "检查你的代码"],
    "Submit and go to next challenge": ["Submit and go to next challenge", "提交并继续"],
}
BUTTON_TEXT_TO_CANONICAL = {
    alias: canonical
    for canonical, aliases in BUTTON_ALIASES.items()
    for alias in aliases
}
ALLOWED_BUTTON_TEXTS = set(BUTTON_TEXT_TO_CANONICAL)
CHALLENGE_URL_PREFIX = "https://www.freecodecamp.org/learn/2022/responsive-web-design/"
USAGE = "Usage: fcc_rwd_submit.py [--cdp-url URL] status | write <code> | click <btn> | run-step <code>"

JS_GET_STATE = "(()=>{const h=document.querySelector('.monaco-editor')?.parentElement;if(!h)return null;const k=Object.keys(h).find(x=>x.startsWith('__reactFiber$'));if(!k)return null;let f=h[k];for(let d=0;f&&d<20;d++,f=f.return){const p=f.memoizedProps||{};if(p.editorRef||p.updateFile||p.challengeFiles)return{url:location.href,title:p.title||document.title,block:p.block||null,fileKey:p.fileKey||null,editorValue:p.editorRef?.current?.getValue?.()||null,hasEditor:Boolean(p.editorRef?.current?.setValue),isFreeCodeCampChallenge:location.href.startsWith('https://www.freecodecamp.org/learn/2022/responsive-web-design/')};}return null;})()"

JS_GET_BUTTON = "(()=>{const b=Array.from(document.querySelectorAll('button'));const labels={check:['检查你的代码','Check Your Code'],submit:['提交并继续','Submit and go to next challenge']};const c=b.find(e=>labels.check.some(t=>(e.innerText||'').includes(t)));const s=b.find(e=>labels.submit.some(t=>(e.innerText||'').includes(t)));if(s)return{text:'Submit and go to next challenge',rawText:s.innerText||'',i:b.indexOf(s)};if(c)return{text:'Check Your Code',rawText:c.innerText||'',i:b.indexOf(c)};return null;})()"


def normalize_tappi_value(value: Any) -> Any:
    if isinstance(value, list):
        return [normalize_tappi_value(item) for item in value]
    if isinstance(value, dict):
        if value.get("subtype") == "null" and value.get("value") is None:
            return None
        return {key: normalize_tappi_value(item) for key, item in value.items()}
    return value


def canonicalize_button_text(text: str | None) -> str | None:
    if not isinstance(text, str):
        return None
    return BUTTON_TEXT_TO_CANONICAL.get(text)


def get_allowed_button_labels(text: str | None) -> list[str]:
    canonical = canonicalize_button_text(text)
    if canonical is None:
        return []
    return BUTTON_ALIASES[canonical]


def get_visible_button_text(button: dict[str, Any] | None) -> str | None:
    if not isinstance(button, dict):
        return None
    raw_text = button.get("rawText")
    if isinstance(raw_text, str) and raw_text:
        return raw_text
    text = button.get("text")
    return text if isinstance(text, str) and text else None


@dataclass(frozen=True)
class RuntimeConfig:
    cdp_url: str


def print_json(payload: dict[str, Any], *, exit_code: int = 0) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if exit_code:
        sys.exit(exit_code)


def make_error(message: str, **extra: Any) -> dict[str, Any]:
    return {"error": message, **extra}


def parse_args(args: list[str]) -> tuple[RuntimeConfig, str, list[str]]:
    remaining = list(args)
    cli_cdp_url: str | None = None

    while remaining and remaining[0].startswith("--"):
        flag = remaining.pop(0)
        if flag == "--cdp-url":
            if not remaining:
                print_json(make_error("Missing value for --cdp-url", usage=USAGE), exit_code=1)
            cli_cdp_url = remaining.pop(0)
        else:
            print_json(make_error(f"Unknown option: {flag}", usage=USAGE), exit_code=1)

    if not remaining:
        print_json(make_error("Missing command", usage=USAGE), exit_code=1)

    cdp_url = cli_cdp_url or os.environ.get("CDP_URL")
    if not cdp_url:
        print_json(
            make_error(
                "Missing browser binding. Provide --cdp-url or set CDP_URL.",
                usage=USAGE,
            ),
            exit_code=1,
        )

    return RuntimeConfig(cdp_url=cdp_url), remaining[0], remaining[1:]


def run_tappi_eval(js: str, config: RuntimeConfig) -> tuple[int, str, str]:
    env = {**os.environ, "CDP_URL": config.cdp_url}
    result = subprocess.run(
        ["tappi", "eval", js],
        capture_output=True,
        text=True,
        env=env,
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def tappi_eval(js: str, config: RuntimeConfig) -> Any | None:
    code, stdout, _stderr = run_tappi_eval(js, config)
    if code != 0 or not stdout:
        return None
    try:
        return normalize_tappi_value(json.loads(stdout))
    except json.JSONDecodeError:
        try:
            parsed = json.loads("[" + stdout + "]")[0] if stdout.startswith("{") else None
            return normalize_tappi_value(parsed)
        except json.JSONDecodeError:
            return None


def get_challenge_state(config: RuntimeConfig) -> dict[str, Any] | None:
    state = tappi_eval(JS_GET_STATE, config)
    return state if isinstance(state, dict) else None


def get_primary_button(config: RuntimeConfig) -> dict[str, Any] | None:
    button = tappi_eval(JS_GET_BUTTON, config)
    return button if isinstance(button, dict) else None


def build_status_payload(config: RuntimeConfig) -> dict[str, Any]:
    state = get_challenge_state(config)
    button = get_primary_button(config)
    return {"state": state, "primaryButton": button, "cdpUrl": config.cdp_url}


def validate_primary_button(button: dict[str, Any] | None, payload: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    if button is None:
        return False, make_error(
            "No supported primary button is visible on the bound browser target.",
            **payload,
        )

    if canonicalize_button_text(button.get("text")) is None:
        return False, make_error(
            "Detected primary button is outside the allowed action set.",
            **payload,
        )

    return True, payload


def extract_atomic_before(payload: dict[str, Any], config: RuntimeConfig) -> dict[str, Any]:
    before = payload.get("before")
    if isinstance(before, dict):
        return {**before, "cdpUrl": config.cdp_url}
    return build_status_payload(config)


def build_mutation_error(
    message: str,
    *,
    phase: str,
    mutation_attempted: bool,
    before: dict[str, Any],
    after: dict[str, Any] | None = None,
    **extra: Any,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "error": message,
        "phase": phase,
        "mutationAttempted": mutation_attempted,
        "before": before,
        **extra,
    }
    if after is not None:
        payload["after"] = after
    return payload


def run_atomic_write(code: str, config: RuntimeConfig) -> dict[str, Any]:
    escaped = json.dumps(code)
    js = """(()=>{const isStep=url=>typeof url==='string'&&url.startsWith(""" + json.dumps(CHALLENGE_URL_PREFIX) + """)&&url.includes('/step-');const getState=()=>{const h=document.querySelector('.monaco-editor')?.parentElement;if(!h)return null;const k=Object.keys(h).find(x=>x.startsWith('__reactFiber$'));if(!k)return null;let f=h[k];for(let d=0;f&&d<20;d++,f=f.return){const p=f.memoizedProps||{};if(p.editorRef||p.updateFile||p.challengeFiles)return{url:location.href,title:p.title||document.title,block:p.block||null,fileKey:p.fileKey||null,editorValue:p.editorRef?.current?.getValue?.()||null,hasEditor:Boolean(p.editorRef?.current?.setValue),isFreeCodeCampChallenge:location.href.startsWith(""" + json.dumps(CHALLENGE_URL_PREFIX) + """)};}return null;};const getButton=()=>{const b=Array.from(document.querySelectorAll('button'));const labels={check:['检查你的代码','Check Your Code'],submit:['提交并继续','Submit and go to next challenge']};const c=b.find(e=>labels.check.some(t=>(e.innerText||'').includes(t)));const s=b.find(e=>labels.submit.some(t=>(e.innerText||'').includes(t)));if(s)return{text:'Submit and go to next challenge',rawText:s.innerText||'',i:b.indexOf(s)};if(c)return{text:'Check Your Code',rawText:c.innerText||'',i:b.indexOf(c)};return null;};const before={state:getState(),primaryButton:getButton()};const state=before.state;if(!state)return{ok:false,error:'No freeCodeCamp challenge state detected on the bound browser instance.',before,mutationAttempted:false};if(!isStep(state.url))return{ok:false,error:'Bound browser target is not a freeCodeCamp challenge step.',before,mutationAttempted:false};if(state.isFreeCodeCampChallenge!==true)return{ok:false,error:'Bound browser target is outside the supported freeCodeCamp course.',before,mutationAttempted:false};if(!state.hasEditor)return{ok:false,error:'Challenge editor is not available on the bound browser target.',before,mutationAttempted:false};const button=before.primaryButton;if(!button)return{ok:false,error:'No supported primary button is visible on the bound browser target.',before,mutationAttempted:false};const h=document.querySelector('.monaco-editor')?.parentElement;if(!h)return{ok:false,error:'Challenge editor is not available on the bound browser target.',before,mutationAttempted:false};const k=Object.keys(h).find(x=>x.startsWith('__reactFiber$'));if(!k)return{ok:false,error:'Challenge editor is not available on the bound browser target.',before,mutationAttempted:false};let f=h[k];for(let d=0;f&&d<20;d++,f=f.return){const p=f.memoizedProps||{};if(p.editorRef?.current?.setValue){p.editorRef.current.setValue(""" + escaped + """);return{ok:true,before,mutationAttempted:true,actualCode:p.editorRef.current.getValue?.()||null};}}return{ok:false,error:'Failed to write code to the challenge editor.',before,mutationAttempted:false};})()"""
    result = tappi_eval(js, config)
    return result if isinstance(result, dict) else make_error("Failed to evaluate write operation in the bound browser instance.")


def run_atomic_click(btn_text: str, config: RuntimeConfig) -> dict[str, Any]:
    labels = get_allowed_button_labels(btn_text)
    if not labels:
        return make_error("Requested button text is not allowed.", allowedButtons=sorted(ALLOWED_BUTTON_TEXTS))
    escaped = json.dumps(labels)
    js = """(()=>{const isStep=url=>typeof url==='string'&&url.startsWith(""" + json.dumps(CHALLENGE_URL_PREFIX) + """)&&url.includes('/step-');const getState=()=>{const h=document.querySelector('.monaco-editor')?.parentElement;if(!h)return null;const k=Object.keys(h).find(x=>x.startsWith('__reactFiber$'));if(!k)return null;let f=h[k];for(let d=0;f&&d<20;d++,f=f.return){const p=f.memoizedProps||{};if(p.editorRef||p.updateFile||p.challengeFiles)return{url:location.href,title:p.title||document.title,block:p.block||null,fileKey:p.fileKey||null,editorValue:p.editorRef?.current?.getValue?.()||null,hasEditor:Boolean(p.editorRef?.current?.setValue),isFreeCodeCampChallenge:location.href.startsWith(""" + json.dumps(CHALLENGE_URL_PREFIX) + """)};}return null;};const getButton=()=>{const b=Array.from(document.querySelectorAll('button'));const labels={check:['检查你的代码','Check Your Code'],submit:['提交并继续','Submit and go to next challenge']};const c=b.find(e=>labels.check.some(t=>(e.innerText||'').includes(t)));const s=b.find(e=>labels.submit.some(t=>(e.innerText||'').includes(t)));if(s)return{text:'Submit and go to next challenge',rawText:s.innerText||'',i:b.indexOf(s)};if(c)return{text:'Check Your Code',rawText:c.innerText||'',i:b.indexOf(c)};return null;};const before={state:getState(),primaryButton:getButton()};const state=before.state;if(!state)return{ok:false,error:'No freeCodeCamp challenge state detected on the bound browser instance.',before,mutationAttempted:false};if(!isStep(state.url))return{ok:false,error:'Bound browser target is not a freeCodeCamp challenge step.',before,mutationAttempted:false};if(state.isFreeCodeCampChallenge!==true)return{ok:false,error:'Bound browser target is outside the supported freeCodeCamp course.',before,mutationAttempted:false};const button=before.primaryButton;if(!button)return{ok:false,error:'No supported primary button is visible on the bound browser target.',before,mutationAttempted:false};const candidates=""" + escaped + """;const buttons=Array.from(document.querySelectorAll('button'));const target=buttons.find(e=>candidates.some(t=>(e.innerText||'').includes(t)));if(!target)return{ok:false,error:'Requested button is not the current primary button.',before,requested:""" + json.dumps(btn_text) + """,mutationAttempted:false};target.click();return{ok:true,before,requested:""" + json.dumps(btn_text) + """,mutationAttempted:true};})()"""
    result = tappi_eval(js, config)
    return result if isinstance(result, dict) else make_error("Failed to evaluate click operation in the bound browser instance.")
    return isinstance(url, str) and url.startswith(CHALLENGE_URL_PREFIX) and "/step-" in url


def validate_target(config: RuntimeConfig, *, require_editor: bool = False) -> tuple[bool, dict[str, Any]]:
    payload = build_status_payload(config)
    state = payload.get("state")

    if not state:
        return False, make_error(
            "No freeCodeCamp challenge state detected on the bound browser instance.",
            **payload,
        )

    url = state.get("url")
    if not is_valid_challenge_url(url):
        return False, make_error(
            "Bound browser target is not a freeCodeCamp challenge step.",
            **payload,
        )

    if state.get("isFreeCodeCampChallenge") is not True:
        return False, make_error(
            "Bound browser target is outside the supported freeCodeCamp course.",
            **payload,
        )

    if require_editor and not state.get("hasEditor"):
        return False, make_error(
            "Challenge editor is not available on the bound browser target.",
            **payload,
        )

    button_ok, button_payload = validate_primary_button(payload.get("primaryButton"), payload)
    if not button_ok:
        return False, button_payload

    return True, payload


def verify_editor_value(expected_code: str, payload: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    state = payload.get("state")
    actual_code = state.get("editorValue") if isinstance(state, dict) else None
    if actual_code != expected_code:
        return False, make_error(
            "Editor value does not match the requested code after write.",
            expectedCode=expected_code,
            actualCode=actual_code,
            **payload,
        )
    return True, payload


def write_and_verify(code: str, config: RuntimeConfig) -> tuple[bool, dict[str, Any]]:
    write_result = run_atomic_write(code, config)
    if write_result.get("ok") is not True:
        before = extract_atomic_before(write_result, config)
        return False, build_mutation_error(
            write_result.get("error", "Failed to write code to the challenge editor."),
            phase="write_preflight",
            mutation_attempted=bool(write_result.get("mutationAttempted")),
            before=before,
            requestedCode=code,
        )

    before = extract_atomic_before(write_result, config)
    revalidated_ok, after = validate_target(config, require_editor=True)
    if not revalidated_ok:
        return False, build_mutation_error(
            "Post-write validation failed.",
            phase="post_write_validation",
            mutation_attempted=True,
            before=before,
            after=after,
            requestedCode=code,
        )

    verified_ok, verified_payload = verify_editor_value(code, after)
    if not verified_ok:
        return False, build_mutation_error(
            verified_payload["error"],
            phase="post_write_verification",
            mutation_attempted=True,
            before=before,
            after=verified_payload,
            requestedCode=code,
        )

    return True, {"before": before, "after": after}


def click_and_wait(btn_text: str, config: RuntimeConfig, timeout_s: float = 6.0) -> dict[str, Any]:
    click_result = run_atomic_click(btn_text, config)
    if click_result.get("ok") is not True:
        before = extract_atomic_before(click_result, config)
        return build_mutation_error(
            click_result.get("error", "Could not click the requested button."),
            phase="click_preflight",
            mutation_attempted=bool(click_result.get("mutationAttempted")),
            before=before,
            requested=btn_text,
            allowedButtons=sorted(ALLOWED_BUTTON_TEXTS),
        )

    before = extract_atomic_before(click_result, config)
    current = before.get("primaryButton") or {}
    current_text = current.get("text")

    start = time.time()
    while (time.time() - start) < timeout_s:
        time.sleep(0.6)
        after = build_status_payload(config)
        next_button = after.get("primaryButton")
        next_text = next_button.get("text") if isinstance(next_button, dict) else None
        if next_text and next_text != current_text:
            valid, checked_after = validate_target(config, require_editor=False)
            if not valid:
                return build_mutation_error(
                    "Post-click validation failed after button transition.",
                    phase="post_click_validation",
                    mutation_attempted=True,
                    before=before,
                    after=checked_after,
                    clicked=btn_text,
                )
            return {
                "clicked": btn_text,
                "before": before,
                "after": checked_after,
                "newButton": next_text,
                "mutationAttempted": True,
            }

    valid, checked_after = validate_target(config, require_editor=False)
    if not valid:
        return build_mutation_error(
            "Post-click validation failed after timeout.",
            phase="post_click_validation",
            mutation_attempted=True,
            before=before,
            after=checked_after,
            clicked=btn_text,
        )
    return {
        "clicked": btn_text,
        "before": before,
        "after": checked_after,
        "timeout": True,
        "mutationAttempted": True,
    }


def read_code_arg(raw: str) -> str:
    return Path(raw[1:]).read_text() if raw.startswith("@") else raw


def main(args: list[str] | None = None) -> None:
    config, cmd, cmd_args = parse_args(args or sys.argv[1:])

    if cmd == "status":
        print_json(build_status_payload(config))
        return

    if cmd == "write":
        if len(cmd_args) < 1:
            print_json(make_error("Usage: fcc_rwd_submit.py [--cdp-url URL] write <code>"), exit_code=1)
        code = read_code_arg(cmd_args[0])
        write_ok, result_payload = write_and_verify(code, config)
        if not write_ok:
            print_json(result_payload, exit_code=1)
        print_json({"written": True, **result_payload})
        return

    if cmd == "click":
        if len(cmd_args) < 1:
            print_json(make_error("Usage: fcc_rwd_submit.py [--cdp-url URL] click <button-text>"), exit_code=1)
        result = click_and_wait(cmd_args[0], config)
        if "error" in result:
            print_json(result, exit_code=1)
        print_json(result)
        return

    if cmd == "run-step":
        if len(cmd_args) < 1:
            print_json(make_error("Usage: fcc_rwd_submit.py [--cdp-url URL] run-step <code>"), exit_code=1)
        code = read_code_arg(cmd_args[0])
        write_ok, write_payload = write_and_verify(code, config)
        if not write_ok:
            print_json(write_payload, exit_code=1)
        primary_button = write_payload["after"].get("primaryButton") or {}
        requested = get_visible_button_text(primary_button) or primary_button.get("text")
        result = click_and_wait(requested, config)
        if "error" in result:
            print_json(result, exit_code=1)
        print_json({"written": True, **write_payload, "result": result})
        return

    print_json(make_error(f"Unknown command: {cmd}", usage=USAGE), exit_code=1)


if __name__ == "__main__":
    main()
