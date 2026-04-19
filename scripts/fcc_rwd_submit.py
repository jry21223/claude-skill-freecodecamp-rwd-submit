#!/usr/bin/env python3
"""freeCodeCamp RWD submission helper - wraps brittle browser ops via tappi."""

import json
import subprocess
import sys
import time


def tappi_eval(js: str) -> dict | None:
    result = subprocess.run(["tappi", "eval", js], capture_output=True, text=True)
    if result.returncode != 0:
        return None
    out = result.stdout.strip()
    if not out:
        return None
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        try:
            return json.loads("[" + out + "]")[0] if out.startswith("{") else None
        except:
            return None


JS_GET_STATE = "(()=>{const h=document.querySelector('.monaco-editor')?.parentElement;if(!h)return null;const k=Object.keys(h).find(x=>x.startsWith('__reactFiber$'));if(!k)return null;let f=h[k];for(let d=0;f&&d<20;d++,f=f.return){const p=f.memoizedProps||{};if(p.editorRef||p.updateFile||p.challengeFiles)return{url:location.href,title:p.title,block:p.block,fileKey:p.fileKey,editorValue:p.editorRef?.current?.getValue?.()||null};}return null;})()"


JS_GET_BUTTON = "(()=>{const b=Array.from(document.querySelectorAll('button'));const c=b.find(e=>(e.innerText||'').includes('检查你的代码'));const s=b.find(e=>(e.innerText||'').includes('提交并继续'));if(s)return{text:'提交并继续',i:b.indexOf(s)};if(c)return{text:'检查你的代码',i:b.indexOf(c)};return null;})()"


def get_challenge_state() -> dict | None:
    return tappi_eval(JS_GET_STATE)


def get_primary_button() -> dict | None:
    return tappi_eval(JS_GET_BUTTON)


def click_button_by_text(text: str) -> bool:
    t = json.dumps(text)
    js = "(()=>{const b=Array.from(document.querySelectorAll('button'));const x=b.find(e=>(e.innerText||'').includes("+t+"));if(x){x.click();return true;}return false;})()"
    return tappi_eval(js) is True


def set_editor_value(code: str) -> bool:
    escaped = json.dumps(code)
    js = "(()=>{const h=document.querySelector('.monaco-editor')?.parentElement;if(!h)return false;const k=Object.keys(h).find(x=>x.startsWith('__reactFiber$'));if(!k)return false;let f=h[k];for(let d=0;f&&d<20;d++,f=f.return){const p=f.memoizedProps||{};if(p.editorRef?.current?.setValue){p.editorRef.current.setValue("+escaped+");return true;}}return false;})()"
    return tappi_eval(js) is True


def click_and_wait(btn_text: str, timeout_s: float = 6.0) -> dict:
    if not click_button_by_text(btn_text):
        return {"error": "Could not click '" + btn_text + "'"}
    start = time.time()
    while (time.time() - start) < timeout_s:
        time.sleep(0.6)
        new_btn = get_primary_button()
        if new_btn and new_btn.get("text") != btn_text:
            state = get_challenge_state()
            return {"clicked": btn_text, "newButton": new_btn.get("text"), "state": state}
    state = get_challenge_state()
    return {"clicked": btn_text, "timeout": True, "state": state}


def main(args: list[str] | None = None):
    args = args or sys.argv[1:]
    if not args:
        print("Usage: fcc_rwd_submit.py status | write <code> | click <btn> | run-step <code>")
        sys.exit(1)

    cmd = args[0]

    if cmd == "status":
        state = get_challenge_state()
        btn = get_primary_button()
        print(json.dumps({"state": state, "primaryButton": btn}, ensure_ascii=False, indent=2))

    elif cmd == "write":
        if len(args) < 2:
            print("Usage: fcc_rwd_submit.py write <code>")
            sys.exit(1)
        code = args[1]
        if code.startswith("@"):
            from pathlib import Path
            code = Path(code[1:]).read_text()
        ok = set_editor_value(code)
        print(json.dumps({"written": ok}))

    elif cmd == "click":
        if len(args) < 2:
            print("Usage: fcc_rwd_submit.py click <button-text>")
            sys.exit(1)
        btn = args[1]
        result = click_and_wait(btn)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif cmd == "run-step":
        if len(args) < 2:
            print("Usage: fcc_rwd_submit.py run-step <code>")
            sys.exit(1)
        code = args[1]
        if code.startswith("@"):
            from pathlib import Path
            code = Path(code[1:]).read_text()
        ok = set_editor_value(code)
        if not ok:
            print(json.dumps({"error": "Failed to write code"}))
            sys.exit(1)
        btn = get_primary_button()
        if not btn:
            print(json.dumps({"error": "No primary button"}))
            sys.exit(1)
        result = click_and_wait(btn.get("text"))
        print(json.dumps(result, ensure_ascii=False, indent=2))

    else:
        print("Unknown command: " + cmd)
        sys.exit(1)


if __name__ == "__main__":
    main()