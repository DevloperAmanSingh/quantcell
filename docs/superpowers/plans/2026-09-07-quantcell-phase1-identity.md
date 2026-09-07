# QuantCell Phase 1: Repo Identity & Branding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Re-identify the repo as QuantCell: fresh git history, full `valuecell`→`quantcell` rename, frontend/Tauri rebrand, Apache 2.0 attribution, new English README.

**Architecture:** Pure mechanical rename + branding phase. No behavior change. The Python package moves from `python/valuecell/` to `python/quantcell/`; all string occurrences of `valuecell`/`ValueCell`/`VALUECELL` are rewritten except in LICENSE/NOTICE attribution.

**Tech Stack:** git, zsh/sed, uv + pytest (verification), bun (frontend typecheck).

**Spec:** `docs/superpowers/specs/2026-09-07-quantcell-rebuild-design.md`

## Global Constraints

- NOTICE file must credit ValueCell (Apache 2.0 requirement); this is the ONLY place upstream branding survives.
- App version resets to `0.1.0`.
- Excluded from all sed sweeps: `.git`, `python/.venv`, `frontend/node_modules`, `graphify-out`, `docs/superpowers` (spec/plan mention ValueCell intentionally), `LICENSE`, `NOTICE`.
- macOS sed syntax: `sed -i '' ...` with `LC_ALL=C`.

---

### Task 1: Fresh repo + attribution + docs

**Files:**
- Delete: `.git/` (approved by user; irreversible), `graphify-out/`
- Create: `NOTICE`
- Modify: `.gitignore` (add `graphify-out/`)

- [x] **Step 1:** `rm -rf .git graphify-out && git init -b main`
- [x] **Step 2:** Write `NOTICE`:

```
QuantCell
Copyright 2026 Aman Singh

This product includes software developed as part of the ValueCell project
(https://github.com/ValueCell-ai/valuecell), Copyright ValueCell team and
contributors, licensed under the Apache License, Version 2.0.
```

- [x] **Step 3:** Append `graphify-out/` to `.gitignore`.
- [x] **Step 4:** Commit: `git add LICENSE NOTICE .gitignore docs/superpowers && git commit -m "init: QuantCell licensing, notice, and rebuild docs"`

### Task 2: Python package rename

**Files:**
- Move: `python/valuecell/` → `python/quantcell/`
- Modify: every file under `python/` (incl. `pyproject.toml`, `configs/`, `scripts/`), `start.sh`, `start.ps1`, `Makefile`, `.env.example`, `docker/`, `.github/`
- Regenerate: `python/uv.lock`

**Interfaces:**
- Produces: importable package `quantcell` with identical module layout; `pyproject.toml` `name = "quantcell"`, `version = "0.1.0"`.

- [x] **Step 1:** `git mv`-equivalent move: `mv python/valuecell python/quantcell`
- [x] **Step 2:** Sweep (respecting Global Constraints exclusions), all three case variants, over `python/ start.sh start.ps1 Makefile .env.example docker/ .github/ project.code-workspace`:
  - `valuecell` → `quantcell`, `ValueCell` → `QuantCell`, `VALUECELL` → `QUANTCELL`
- [x] **Step 3:** Set `version = "0.1.0"` in `python/pyproject.toml`; run `cd python && uv lock` (regenerates lock under new name). If offline, sed the lock's own `name = "valuecell"` entry only.
- [x] **Step 4:** Verify: `cd python && uv run pytest` → expect same pass/fail set as pre-rename baseline (record baseline before Step 1).
- [x] **Step 5:** Verify no stragglers: `grep -rIl "valuecell\|ValueCell" python/ --exclude-dir=.venv` → empty.
- [x] **Step 6:** Commit: `git add -A && git commit -m "feat: quantcell python package"`

### Task 3: Frontend + Tauri rebrand

**Files:**
- Modify: `frontend/src-tauri/tauri.conf.json` (`productName: "QuantCell"`, `identifier: "com.quantcell.app"`, window `title`), `frontend/package.json` (`name: "quantcell-frontend"`), all `frontend/src/` + `frontend/public/locales/*.json` strings, `frontend/index.html` title if present.

- [x] **Step 1:** Same three-variant sed sweep over `frontend/` (excluding `node_modules`, `bun.lock`).
- [x] **Step 2:** Manually set `tauri.conf.json` identifier to `com.quantcell.app` (sed produces `com.quantcell.quantcellapp`; fix to the clean form).
- [x] **Step 3:** Verify: `cd frontend && bun run typecheck` → passes (or same errors as baseline).
- [x] **Step 4:** `grep -rIl "valuecell\|ValueCell" frontend/src frontend/public frontend/src-tauri` → empty.
- [x] **Step 5:** Commit: `git add -A && git commit -m "feat: rebrand frontend and desktop app to QuantCell"`

### Task 4: README and top-level docs

**Files:**
- Delete: `README.ja.md`, `README.zh.md`, `README.zh_Hant.md`, `assets/valuecell.png`
- Rewrite: `README.md` (QuantCell story: LangGraph agents behind A2A, async orchestrator with HITL, live/paper trading Binance+Coinbase, local-first data; quick start via start.sh; license section pointing at LICENSE+NOTICE)
- Modify: `SECURITY.md`, `.github/` templates (strip upstream links/Discord/social)

- [x] **Step 1:** Delete multilingual READMEs + logo asset; write new `README.md`.
- [x] **Step 2:** Sweep `SECURITY.md`, `.github/` for upstream links; replace with repo-relative text.
- [x] **Step 3:** Repo-wide final check: `grep -rIl "valuecell\|ValueCell" . --exclude-dir={.git,node_modules,.venv,graphify-out} --exclude=NOTICE --exclude=LICENSE --exclude-dir=superpowers` → empty.
- [x] **Step 4:** Commit: `git add -A && git commit -m "docs: QuantCell README and security docs"`

### Task 5: Runtime smoke check

- [x] **Step 1:** `cd python && uv run python -c "import quantcell.server.main"` → imports cleanly.
- [x] **Step 2:** `cd python && uv run pytest` full suite → matches baseline.
- [x] **Step 3:** Commit any fixes: `git commit -am "fix: post-rename import corrections"` (only if needed).

**Note:** App data dir changes from `~/Library/Application Support/ValueCell` to `.../QuantCell`; existing local DB/knowledge stores start fresh (acceptable, documented in README).
