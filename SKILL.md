---
name: freecodecamp-rwd-submit
description: Automate freeCodeCamp 2022 Responsive Web Design step-by-step submissions via tappi browser control. Reads challenge state, writes code to Monaco editor, clicks check/submit buttons, advances through exercises.
user-invocable: true
allowed-tools: Bash, Read
argument-hint: "[repo-root] [--max-steps N]"
---

# freeCodeCamp RWD Submission Skill

Automate legitimate step-by-step submissions for freeCodeCamp 2022 Responsive Web Design exercises.

## When to Use

- Submitting freeCodeCamp RWD exercises through the actual browser validation flow
- Continuing from a paused step in the curriculum
- Batch-advancing through multiple steps with proper validation

## Prerequisites

- `tappi` CLI installed and connected to Chrome (CDP)
- For parallel execution, each agent must use its own browser instance and its own `CDP_URL`
- freeCodeCamp challenge page already open and logged in on that browser instance
- Local repo with completed exercise files (index.html, styles.css)

## Usage

```bash
# Check current browser state
CDP_URL=http://127.0.0.1:9223 python3 scripts/fcc_rwd_submit.py status
python3 scripts/fcc_rwd_submit.py --cdp-url http://127.0.0.1:9223 status

# Write code to editor (inline or from file)
CDP_URL=http://127.0.0.1:9223 python3 scripts/fcc_rwd_submit.py write "<html>...</html>"
python3 scripts/fcc_rwd_submit.py --cdp-url http://127.0.0.1:9223 write @/path/to/index.html

# Click the current primary button
CDP_URL=http://127.0.0.1:9223 python3 scripts/fcc_rwd_submit.py click "Check Your Code"
CDP_URL=http://127.0.0.1:9223 python3 scripts/fcc_rwd_submit.py click "检查你的代码"

# Full step cycle: validate + write + verify + click + wait
python3 scripts/fcc_rwd_submit.py --cdp-url http://127.0.0.1:9223 run-step @/path/to/step-code.html
```

## Workflow

### Step 1: Read Current State

```bash
CDP_URL=http://127.0.0.1:9223 python3 scripts/fcc_rwd_submit.py status
```

Returns:
- `state.url` — current challenge URL when detectable
- `state.block` — challenge block name (e.g., `learn-html-by-building-a-cat-photo-app`)
- `state.title` — step title
- `state.fileKey` — active file key (e.g., `indexhtml`)
- `state.editorValue` — current editor content when the editor is present
- `state.hasEditor` — whether Monaco is writable
- `primaryButton.text` — canonical button name: `Check Your Code` or `Submit and go to next challenge`
- `primaryButton.rawText` — visible localized button text on the page
- `cdpUrl` — the browser endpoint bound to this invocation

### Step 2: Generate Step-Specific Code

Based on:
- The current challenge instructions visible in the bound browser instance
- The current editor contents from `status`
- The final local solution (adapted to step requirements)

**Critical:** Use step-specific intermediate code, not the final exercise solution. Early steps often require partial structures that later steps remove or modify.

### Step 3: Write and Submit

```bash
python3 scripts/fcc_rwd_submit.py --cdp-url http://127.0.0.1:9223 run-step @/path/to/step-code.html
```

Or manually:

```bash
python3 scripts/fcc_rwd_submit.py --cdp-url http://127.0.0.1:9223 write @/path/to/step-code.html
python3 scripts/fcc_rwd_submit.py --cdp-url http://127.0.0.1:9223 click "Check Your Code"
python3 scripts/fcc_rwd_submit.py --cdp-url http://127.0.0.1:9223 click "检查你的代码"
```

### Step 4: Handle Result

- If `newButton` becomes `Submit and go to next challenge`: step passed
- If result contains `timeout: true`: likely failed tests or the page did not transition yet
- If result contains `error`: inspect `phase` and `mutationAttempted` to see whether the helper failed before acting or during post-action validation
- Use the returned `before` / `after` payloads to inspect the latest challenge state before retrying

### Step 5: Advance to Next Step

```bash
python3 scripts/fcc_rwd_submit.py --cdp-url http://127.0.0.1:9223 click "Submit and go to next challenge"
```

Wait for URL to change, then repeat from Step 1.

## Guardrails

- **Only legitimate flow:** Write to editor → verify the editor value → click the current primary button → wait for the official state change
- **No bypass:** Never forge form submissions, skip validation, or modify hidden state
- **Fail closed per helper call:** Every mutating browser eval re-checks the live challenge target before acting and returns structured errors when the target is no longer valid
- **Bound browser only:** Every invocation must be tied to one browser instance via `CDP_URL` or `--cdp-url`
- **Shared-tab concurrency unsupported:** Do not run concurrent agents against different tabs in the same browser session

## Exercise-to-Repo Mapping

| Block | Local Directory |
|-------|-----------------|
| `learn-html-by-building-a-cat-photo-app` | `1. Cat Photo App/` |
| `learn-basic-css-by-building-a-cafe-menu` | `2. Cafe Menu/` |
| `learn-css-colors-by-building-a-set-of-colored-markers` | `3. Colored Markers/` |
| `learn-html-forms-by-building-a-registration-form` | `4. Registration Form/` |
| `learn-the-css-box-model-by-building-a-rothko-painting` | `6. Rothko Painting/` |
| `learn-css-flexbox-by-building-a-photo-gallery` | `7. Photo Gallery/` |
| `learn-typography-by-building-a-nutrition-label` | `8. Nutrition Label/` |
| `learn-more-about-css-pseudo-selectors-by-building-a-balance-sheet` | `11. Balance Sheet/` |
| `learn-intermediate-css-by-building-a-picasso-painting` | `12. Picasso Painting/` |
| `learn-responsive-web-design-by-building-a-piano` | `13. Piano/` |
| `learn-css-variables-by-building-a-city-skyline` | `15. City Skyline/` |
| `learn-css-grid-by-building-a-magazine` | `16. Magazine/` |
| `learn-css-animation-by-building-a-ferris-wheel` | `18. Ferris Wheel/` |
| `learn-css-transforms-by-building-a-penguin` | `19. Penguin/` |

## Browser Isolation and Parallelism

### Supported Parallel Mode

- Safe parallel execution means **one browser instance per agent**
- Each browser instance must expose a distinct `CDP_URL`
- Each agent must run every helper command with its own `CDP_URL`
- This keeps DOM reads, editor writes, and button clicks isolated per agent

### Unsupported Mode

The helper does **not** support safe concurrent automation across different tabs in the same browser session.

Do not rely on:
- `tappi tab <index>` as an isolation mechanism
- one shared Chrome instance with multiple agent-assigned tabs
- background agents switching tabs independently inside the same `CDP_URL`

## Implementation Notes

- Helper script wraps `tappi eval` for reliable browser ops
- React fiber traversal finds `editorRef.current.setValue()` path
- Each helper invocation binds to a browser instance through `CDP_URL`
- All mutating commands validate the live freeCodeCamp target before acting
- JSON output is structured for retries and debugging
