# Claude Visual QA

A **Claude Code skill** that runs automated visual QA on any website — 63 checks across 7 Apple device viewports, per-section screenshots, CSS extraction, and a Word report.

## What It Does

| Layer | Tool | Capabilities |
|-------|------|-------------|
| **Playwright** | `scripts/automated.py` | 63 automated checks, `getComputedStyle()` CSS extraction at 7 viewports, per-section screenshots, interaction tests |
| **MCP Preview** | `preview_inspect` / `preview_snapshot` / `preview_eval` | Real-time CSS verification, accessibility tree, interactive element testing |
| **Report** | `scripts/report.py` | Word document with pass/fail summary, CSS comparison tables, screenshots |

## Quick Start

### 1. Install dependencies

```bash
pip3 install python-docx Pillow playwright
python3 -m playwright install chromium
```

### 2. Install the skill

Copy into any repo's `.claude/skills/` directory:

```bash
# Option A: Clone directly
git clone https://github.com/liuyixiaohu/claude-visual-qa.git .claude/skills/visual-qa

# Option B: Add as git submodule
git submodule add https://github.com/liuyixiaohu/claude-visual-qa.git .claude/skills/visual-qa
```

### 3. Run QA

Open Claude Code in your repo and type:

```
Run visual QA on https://your-website.com
```

Claude will automatically:
1. Run 63 automated checks (~2–3 min)
2. Capture per-section screenshots across 7 viewports
3. Extract computed CSS values
4. Generate a Word report on your Desktop

## Standalone Usage (without Claude Code)

```bash
# Run automated checks
python3 scripts/automated.py https://your-site.com /page-route

# Generate report
python3 scripts/report.py

# Start reverse proxy (for MCP Preview on external URLs)
node scripts/proxy.js https://your-site.com
```

## Device Viewports

| Device | Width | Height |
|--------|-------|--------|
| iPhone SE | 375 | 667 |
| iPhone 15 | 393 | 852 |
| iPhone 15 Pro Max | 430 | 932 |
| iPad Air | 820 | 1180 |
| iPad Pro 12.9" | 1024 | 1366 |
| MacBook Air 13" | 1440 | 900 |
| MacBook Pro 16" | 1728 | 1117 |

## Check Categories (63 total)

| Category | What It Checks |
|----------|----------------|
| Page Load & Layout | HTTP status, meta tags, OG tags, semantic structure |
| Typography & Colors | Font families, heading sizes, responsive scaling |
| Images & Media | Load status, alt text, image count |
| Responsiveness | Overflow, hamburger nav, layout stacking |
| Interactions | Modal dialogs, hamburger menu, nav indicators |
| Console & Network | JS errors, failed requests |

## Report Output

The report (`~/Desktop/Visual_QA_Report.docx`) includes:

- **Verdict**: Ready to Publish / Fix Before Publishing
- **Summary table**: Pass/fail by category
- **CSS comparison**: Typography at 3 viewports (mobile, tablet, desktop)
- **Section screenshots**: Desktop full-width + tablet/mobile side-by-side
- **Interaction screenshots**: Contact modal, hamburger menu
- **Critical issues & warnings**

## Files

```
├── SKILL.md              # Claude Code skill definition
├── GUIDE.md              # Non-technical user guide
├── CHANGELOG.md          # Version history
├── README.md             # This file
└── scripts/
    ├── automated.py      # Playwright checks + CSS extraction
    ├── report.py         # Word report generator
    └── proxy.js          # Reverse proxy for MCP Preview
```

## License

MIT
