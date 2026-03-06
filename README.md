# Claude Visual QA

**One command to check if your website looks right on every device — from iPhone SE to MacBook Pro.**

Before publishing a website, you want to make sure it looks correct on phones, tablets, and desktops. This tool does that automatically: it runs 63 visual checks across 7 screen sizes, captures screenshots of every section, and gives you a Word report with a clear pass/fail verdict.

> **New to this?** See the [User Guide](GUIDE.md) for a step-by-step walkthrough with screenshots.

## How It Works

```
  ┌─────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
  │  You type:   │────▶│  Automated   │────▶│  Screenshots │────▶│  Word report │
  │  "Run visual │     │  checks run  │     │  captured at │     │  on your     │
  │   QA on..."  │     │  (63 checks) │     │  7 viewports │     │  Desktop     │
  └─────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
       ~10 sec              ~2 min              ~1 min               Done!
```

This is a [Claude Code](https://docs.anthropic.com/en/docs/claude-code) skill — you install it into your project, then just ask Claude to run QA in natural language.

## What the Report Tells You

The generated report (`~/Desktop/Visual_QA_Report.docx`) includes:

- **Overall verdict** — "Ready to Publish" or "Fix Before Publishing"
- **Pass/fail summary** by category (layout, typography, images, responsiveness, interactions, errors)
- **Screenshots of every section** — desktop full-width, plus tablet and mobile side-by-side
- **Interaction screenshots** — modals, hamburger menus, navigation states
- **CSS comparison table** — how fonts and sizes actually render at mobile, tablet, and desktop
- **Critical issues & warnings** — prioritized list of what to fix

## What It Checks (63 Checks)

| Category | Examples |
|----------|---------|
| Page Load & Layout | Does the page load? Are meta tags and social share (OG) tags present? Is the HTML structure semantic? |
| Typography & Colors | Are the right fonts loading? Do headings scale properly on smaller screens? |
| Images & Media | Do all images load? Do they have alt text for accessibility? |
| Responsiveness | Does anything overflow on mobile? Does the hamburger menu appear? Do sections stack correctly? |
| Interactions | Does the contact modal open? Does the hamburger menu work? Is the current nav item highlighted? |
| Console & Network | Any JavaScript errors? Any failed network requests? |

## Device Viewports Tested

| Device | Screen Size |
|--------|------------|
| iPhone SE | 375 x 667 |
| iPhone 15 | 393 x 852 |
| iPhone 15 Pro Max | 430 x 932 |
| iPad Air | 820 x 1180 |
| iPad Pro 12.9" | 1024 x 1366 |
| MacBook Air 13" | 1440 x 900 |
| MacBook Pro 16" | 1728 x 1117 |

## Quick Start

### 1. Install dependencies

```bash
pip3 install python-docx Pillow playwright
python3 -m playwright install chromium
```

### 2. Install the skill into your project

```bash
cd ~/Documents/GitHub/YourProject
git clone https://github.com/liuyixiaohu/claude-skill-website-qa.git .claude/skills/visual-qa
```

### 3. Run QA

Open Claude Code in your project and type:

```
Run visual QA on https://your-website.com
```

That's it. Claude will run all 63 checks, capture screenshots, and generate the report on your Desktop.

## Standalone Usage (Without Claude Code)

You can also run the scripts directly from the command line:

```bash
# Run automated checks on a specific page
python3 scripts/automated.py https://your-site.com /about

# Generate the Word report from results
python3 scripts/report.py
```

## Files

```
├── SKILL.md              # Skill definition (how Claude uses this tool)
├── GUIDE.md              # Step-by-step user guide for non-technical users
├── scripts/
│   ├── automated.py      # Runs 63 checks + captures screenshots + extracts CSS
│   ├── report.py         # Generates the Word report
│   └── proxy.js          # Helper for testing external URLs via Claude's preview
├── CHANGELOG.md          # Version history
└── README.md             # This file
```

## License

MIT
