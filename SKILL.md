---
name: visual-qa
description: "Visual QA for any website. Combines Playwright automated checks + CSS extraction with MCP Preview real-time browser inspection. Captures computed CSS at all 7 viewports, verifies interactions, and generates an English Word report with CSS comparison tables and per-section screenshots."
allowed-tools: Read, Glob, Write, Bash, mcp__Claude_Preview__preview_start, mcp__Claude_Preview__preview_stop, mcp__Claude_Preview__preview_snapshot, mcp__Claude_Preview__preview_inspect, mcp__Claude_Preview__preview_eval, mcp__Claude_Preview__preview_click, mcp__Claude_Preview__preview_resize, mcp__Claude_Preview__preview_screenshot, mcp__Claude_Preview__preview_fill, mcp__Claude_Preview__preview_console_logs, mcp__Claude_Preview__preview_network
---

# Visual QA Skill

This skill runs a **hybrid visual QA** on any website, combining two complementary approaches:

| Layer | Tool | What It Does |
|-------|------|-------------|
| **Playwright** | `scripts/automated.py` | 7 viewports x per-section screenshots, 63 automated checks, `getComputedStyle()` CSS extraction on 30+ elements per viewport, interaction tests |
| **MCP Preview** | `preview_inspect` / `preview_snapshot` / `preview_eval` / `preview_click` | Real-time CSS verification, accessibility tree, interactive element testing |

All output and the final Word report must be in **English**.

---

## Setup

### 0.1 Install dependencies

```bash
pip3 install python-docx Pillow playwright 2>/dev/null
python3 -m playwright install chromium 2>/dev/null
mkdir -p /tmp/visual-qa
```

### 0.2 Determine target URL

Ask the user which URL to test. Examples:
- `https://example.com` (production)
- `https://staging.example.com` (staging)
- A Figma Make preview URL

### 0.3 Set up reverse proxy (for MCP Preview on external URLs)

MCP Preview tools only work on localhost. For external URLs, use the included reverse proxy:

Update `.claude/launch.json` to add the qa-proxy entry:
```json
{
  "name": "qa-proxy",
  "runtimeExecutable": "node",
  "runtimeArgs": ["<SKILL_PATH>/scripts/proxy.js", "TARGET_URL"],
  "port": 8765
}
```

**Note:** Replace `<SKILL_PATH>` with the actual path to this skill directory, and `TARGET_URL` with the site to test. Find the correct node path with: `which node`

---

## Device Viewports

| # | Device | Width | Height | Category |
|---|--------|-------|--------|----------|
| 1 | iPhone SE | 375 | 667 | Mobile |
| 2 | iPhone 15 | 393 | 852 | Mobile |
| 3 | iPhone 15 Pro Max | 430 | 932 | Mobile |
| 4 | iPad Air | 820 | 1180 | Tablet |
| 5 | iPad Pro 12.9" | 1024 | 1366 | Tablet |
| 6 | MacBook Air 13" | 1440 | 900 | Desktop |
| 7 | MacBook Pro 16" | 1728 | 1117 | Desktop |

---

# Phase 1 — Playwright Automated Checks + CSS Extraction

The script is at `scripts/automated.py`. It accepts the target URL as a CLI argument:

```bash
python3 <SKILL_PATH>/scripts/automated.py <BASE_URL> [PAGE_ROUTE] [--out DIR]
```

Examples:
```bash
python3 scripts/automated.py https://example.com
python3 scripts/automated.py https://example.com /about
python3 scripts/automated.py https://example.com /pricing --out /tmp/my-qa
```

Default output directory: `/tmp/visual-qa`

## 1.1 Automated Checks (63 checks across 6 categories)

| Category | Check IDs | Examples |
|----------|-----------|---------|
| Page Load & Layout | 1.x - 5.x | HTTP 200, title, meta tags, OG tags, canonical, console errors, network failures, font loading, section structure |
| Typography & Colors | 6.x - 8.x | Font families, heading sizes scale responsively, button styles consistent |
| Images & Media | 9.x - 10.x | All images loaded, alt text present, hero image renders, reasonable image count |
| Responsiveness | 11.x - 14.x | No horizontal overflow, hamburger visible on mobile, nav links hidden on mobile, hero text scales, sections stack vertically |
| Interactions | 15.x - 16.x | Contact modal opens (desktop + mobile), hamburger menu opens, active nav indicator, modal has form fields |
| Console & Network | 17.x - 18.x | No JS errors (excluding known CORS), no failed network requests |

## 1.2 CSS Extraction via `getComputedStyle()`

For **each of the 7 viewports**, the script extracts computed CSS on:

| Element | Properties Extracted |
|---------|---------------------|
| `nav` | font-family, font-size, height, background-color, padding |
| Nav links | font-family, font-size, font-weight, color, opacity, text-decoration |
| `h1` (hero heading) | font-family, font-size, font-weight, line-height, letter-spacing, color |
| All `h2` headings | same as h1 |
| Body paragraphs | same as h1 |
| All `<button>` elements | font-family, font-size, color, bg-color, border-radius, padding |
| Section backgrounds | background-color, background-image, padding, height |
| Footer | standard CSS extraction |

## 1.3 Per-Section Screenshots

For each viewport, the script captures each `<section>` and `<footer>` individually via `element.screenshot()`.

## 1.4 Output

All data saved to `<OUT_DIR>/hybrid_automated_results.json`.

---

# Phase 2 — MCP Preview Deep Inspection

**Prerequisite:** Reverse proxy must be running (`preview_start` the `qa-proxy` server).

## 2.1 Start the Preview Server

```
preview_start(name: "qa-proxy")
```

## 2.2 Desktop Inspection

Use `preview_resize(preset: "desktop")` or `preview_resize(width: 1440, height: 900)`.

- `preview_snapshot` — full accessibility tree
- `preview_inspect(selector: "h1")` — exact computed CSS
- `preview_eval(expression: "...")` — bulk JS extraction (wrap in IIFE)

## 2.3 Tablet & Mobile Inspection

```
preview_resize(preset: "tablet")   // 768x1024
preview_resize(preset: "mobile")   // 375x812
```

Test hamburger menu, responsive layouts, font scaling.

## 2.4 Output

Save MCP findings to `<OUT_DIR>/hybrid_mcp_results.json`.

---

# Phase 3 — Report Generation

```bash
python3 <SKILL_PATH>/scripts/report.py [--out DIR] [--report PATH]
```

Default output: `~/Desktop/Visual_QA_Report.docx`

The report includes:
- Executive Summary with verdict
- All check results table
- CSS typography scale comparison (3 viewports)
- Section background inspection
- MCP findings (if available)
- Per-section screenshots (desktop + responsive side-by-side)
- Interaction screenshots
- Critical issues & warnings

---

# Known Limitations

## MCP Preview

| Issue | Workaround |
|-------|------------|
| `preview_screenshot` fails on macOS | Playwright handles all screenshots |
| MCP only works on localhost | Reverse proxy maps external → localhost |
| `preview_eval` variables persist | Use IIFE with unique variable names |

## Playwright

| Issue | Workaround |
|-------|------------|
| CORS errors on CDN fonts | Known limitation, mark as expected |
| Strict mode multiple matches | Use more specific selectors |

---

# Reference Files

| File | Purpose |
|------|---------|
| `scripts/automated.py` | Playwright script with 63 checks + CSS extraction |
| `scripts/report.py` | Word report generator |
| `scripts/proxy.js` | Reverse proxy for MCP Preview |
| `/tmp/visual-qa/hybrid_automated_results.json` | Runtime output |
| `/tmp/visual-qa/hybrid_mcp_results.json` | Runtime output |
| `~/Desktop/Visual_QA_Report.docx` | Final report |
