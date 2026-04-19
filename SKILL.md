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
- freeCodeCamp tab already open and logged in
- Local repo with completed exercise files (index.html, styles.css)

## Usage

```bash
# Check current browser state
python3 scripts/fcc_rwd_submit.py status

# Write code to editor (inline or from file)
python3 scripts/fcc_rwd_submit.py write "<html>...</html>"
python3 scripts/fcc_rwd_submit.py write @/path/to/index.html

# Click primary button (检查你的代码 / 提交并继续)
python3 scripts/fcc_rwd_submit.py click "检查你的代码"

# Full step cycle: write + click check + wait
python3 scripts/fcc_rwd_submit.py run-step "<html>...</html>"
```

## Workflow

### Step 1: Read Current State

```bash
python3 scripts/fcc_rwd_submit.py status
```

Returns:
- `state.url` — current challenge URL
- `state.block` — challenge block name (e.g., `learn-html-by-building-a-cat-photo-app`)
- `state.title` — step title (e.g., `第 17 步`)
- `state.fileKey` — active file key (e.g., `indexhtml`)
- `state.initialTests` — test specs for this step
- `state.editorValue` — current editor content
- `primaryButton` — "检查你的代码" or "提交并继续"

### Step 2: Generate Step-Specific Code

Based on:
- `initialTests` (what the step expects)
- Page instructions (visible text or fetched challenge markdown)
- Final local solution (adapted to step requirements)

**Critical:** Use step-specific intermediate code, not the final exercise solution. Early steps often require partial structures that later steps remove or modify.

### Step 3: Write and Submit

```bash
python3 scripts/fcc_rwd_submit.py run-step @/path/to/step-code.html
```

Or manually:

```bash
python3 scripts/fcc_rwd_submit.py write @/path/to/step-code.html
python3 scripts/fcc_rwd_submit.py click "检查你的代码"
```

### Step 4: Handle Result

- If `newButton` becomes "提交并继续": step passed
- If still "检查你的代码" with `timeout`: likely failed tests
- Read `state.initialTests` or visible error message to diagnose
- Adjust code and retry

### Step 5: Advance to Next Step

```bash
python3 scripts/fcc_rwd_submit.py click "提交并继续"
```

Wait for URL to change, then repeat from Step 1.

## Guardrails

- **Only legitimate flow:** Write to editor → click "检查你的代码" → wait → click "提交并继续"
- **No bypass:** Never forge form submissions, skip validation, or modify hidden state
- **Button-by-text:** Click by visible button text, not fragile element indices
- **Stay on target:** Only operate on freeCodeCamp challenge tabs
- **Stop on anomalies:** Login expiry, popups, URL outside curriculum → halt and report

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

## Implementation Notes

- Helper script wraps `tappi eval` for reliable browser ops
- React fiber traversal finds `editorRef.current.setValue()` path
- No hardcoded challenge data — reads from live page state
- JSON output for easy Claude integration