# Visual QA — User Guide

A quick-start guide for running Visual QA on any website before publishing.

---

## What This Does

This tool automatically checks **any website** for visual issues — broken images, layout problems, missing text, interaction bugs — across **7 different screen sizes** (from iPhone SE to MacBook Pro 16"). It auto-detects what your site has (navigation bar, hamburger menu, contact form, hero section, footer) and only runs relevant checks. It produces a **Word report** on your Desktop with screenshots and a pass/fail summary.

---

## What You'll Get

After running QA, you'll find a file on your Desktop:

**`Visual_QA_Report.docx`** (~2 MB)

The report includes:
- A **verdict** (Ready to Publish / Fix Before Publishing)
- Pass/fail results for 63 automated checks
- Screenshots of every section at desktop, tablet, and mobile sizes
- Screenshots of interactive elements (modals, menus)
- A list of critical issues (if any) and recommended improvements

---

## Prerequisites (One-Time Setup)

You only need to do this once.

### 1. Install Python packages

Open your Terminal and paste:

```bash
pip3 install python-docx Pillow playwright
```

### 2. Install the browser engine

```bash
python3 -m playwright install chromium
```

### 3. Install this skill into your project

```bash
cd ~/Documents/GitHub/YourProject
git clone https://github.com/liuyixiaohu/claude-visual-qa.git .claude/skills/visual-qa
```

That's it! You're ready to run QA.

---

## How to Run QA

### Step 1 — Open Claude Code

Open Claude Code in the project that has this skill installed:

```bash
cd ~/Documents/GitHub/YourProject
claude
```

### Step 2 — Ask Claude to run QA

Type a prompt like:

> Run visual QA on https://your-website.com

or for a specific page:

> Run visual QA on https://your-website.com/about

Claude will automatically:
1. Run the automated checks (~2–3 minutes)
2. Inspect the site with browser tools
3. Generate the Word report

### Step 3 — Open the report

When Claude says it's done, open the report:

```bash
open ~/Desktop/Visual_QA_Report.docx
```

Or just find **Visual_QA_Report.docx** on your Desktop.

---

## Understanding the Report

### Verdict

The first thing you'll see is the overall verdict:

| Verdict | What It Means |
|---------|---------------|
| **READY TO PUBLISH** | All checks passed. Safe to publish. |
| **READY TO PUBLISH (with warnings)** | Minor issues found (1–3 failures). Review the warnings but publishing is OK. |
| **FIX BEFORE PUBLISHING** | Multiple issues found. Review the "Critical Issues" section before publishing. |

### Summary Table

Shows pass/fail counts for each category:

| Category | What It Checks |
|----------|----------------|
| Page Load & Layout | Page loads correctly, has proper titles and meta tags |
| Typography & Colors | Fonts look correct, sizes are right |
| Images & Media | All images load, all images have descriptions |
| Responsiveness | Site looks good on phones, tablets, and desktops |
| Interactions | Forms open, menus work, navigation highlights current page |
| Console & Network | No broken scripts or failed downloads |

### Screenshots

The report includes side-by-side screenshots at:
- **Desktop** — MacBook Air 13" (1440px wide)
- **Tablet** — iPad Air (820px wide)
- **Mobile** — iPhone 15 (393px wide)

### Critical Issues & Warnings

- **Critical Issues** — Must be fixed before publishing
- **Warnings** — Recommended improvements but not blocking

---

## FAQ

### How long does it take?

About **2–3 minutes** for the automated checks, plus another minute for report generation.

### Can I test different pages?

Yes! Just tell Claude which URL and page to test:

> Run visual QA on https://my-site.com/pricing

### What if some checks fail?

Not all failures are critical. Read the "Details" column in the report. Some common expected failures:

- **CORS font errors** — Known limitation with CDN-hosted fonts, fonts still render correctly
- **Console errors about third-party scripts** — Usually harmless (analytics, chat widgets, etc.)

### What if the setup doesn't work?

Make sure you have:
1. **Python 3** installed — check with `python3 --version`
2. **pip** available — check with `pip3 --version`
3. All packages installed (see Prerequisites above)

### Where are the raw screenshots?

All screenshots are saved in `/tmp/visual-qa/`. They're named by device and section.
