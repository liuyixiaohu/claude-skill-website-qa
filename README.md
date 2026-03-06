# Claude Visual QA

**One command to check if your website looks right on every device — from iPhone SE to MacBook Pro.**

Before publishing a website, you want to make sure it looks correct on phones, tablets, and desktops. This tool does that automatically: it runs visual checks across 7 screen sizes, captures screenshots of every section, and gives you a Word report with a clear pass/fail verdict.

It works on **any website** — the script auto-detects what your site has (nav bar, hamburger menu, contact modal, hero section, footer) and only runs relevant checks. No configuration needed, but you can customize everything via a simple config file.

> **New to this?** See the [User Guide](GUIDE.md) for a step-by-step walkthrough.

## How It Works

```
  ┌─────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
  │  You type:   │────▶│  Auto-detect  │────▶│  Run checks  │────▶│  Word report │
  │  "Run visual │     │  site features│     │  + screenshots│     │  on your     │
  │   QA on..."  │     │  (nav? modal?)│     │  at 7 sizes  │     │  Desktop     │
  └─────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
       ~10 sec              ~30 sec              ~2 min               Done!
```

This is a [Claude Code](https://docs.anthropic.com/en/docs/claude-code) skill — you install it into your project, then just ask Claude to run QA in natural language.

## What the Report Tells You

The generated report (`~/Desktop/Visual_QA_Report.docx`) includes:

- **Overall verdict** — "Ready to Publish" or "Fix Before Publishing"
- **Pass/fail summary** by category (layout, typography, images, responsiveness, interactions, errors)
- **Screenshots of every section** — desktop full-width, plus tablet and mobile side-by-side
- **CSS comparison table** — how fonts and sizes actually render at mobile, tablet, and desktop
- **Critical issues & warnings** — prioritized list of what to fix

Checks that don't apply to your site (e.g., hamburger menu on a site without one) are automatically skipped.

## What It Checks

The script auto-detects your site's features and runs relevant checks from these categories:

| Category | Examples |
|----------|---------|
| Page Load & Layout | Page loads, meta tags, OG tags, semantic HTML structure |
| Typography & Colors | Font consistency across headings, text hierarchy, no truncation |
| Images & Media | All images load, alt text present, no stretched images |
| Responsiveness | No overflow on mobile, touch targets large enough, content scales |
| Interactions | Nav links work, modals open/close, active page highlighted *(if applicable)* |
| Console & Network | No JavaScript errors, no failed network requests |

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

That's it. Claude will auto-detect your site's features, run all relevant checks, and generate the report.

## Customization (Optional)

Copy `qa-config.example.yaml` to `qa-config.yaml` and customize:

```yaml
# Check for specific fonts (default: just check consistency)
fonts:
  heading: "Inter"
  body: "Roboto"

# Turn off checks for features your site doesn't have
features:
  hamburger: false
  contact_modal: false

# Adjust thresholds
thresholds:
  h1_min_mobile: 24
  h1_min_desktop: 36
```

See [`qa-config.example.yaml`](qa-config.example.yaml) for all available options.

## Standalone Usage (Without Claude Code)

```bash
# Run automated checks on a specific page
python3 scripts/automated.py https://your-site.com /about

# Generate the Word report from results
python3 scripts/report.py
```

## Files

```
├── SKILL.md                  # Skill definition (how Claude uses this tool)
├── GUIDE.md                  # Step-by-step user guide
├── qa-config.example.yaml    # Configuration template
├── scripts/
│   ├── automated.py          # Runs checks + captures screenshots + extracts CSS
│   ├── report.py             # Generates the Word report
│   └── proxy.js              # Helper for testing external URLs via Claude's preview
├── CHANGELOG.md              # Version history
└── README.md                 # This file
```

## License

MIT
