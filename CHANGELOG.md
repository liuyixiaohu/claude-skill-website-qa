# Changelog

All notable changes to this project are documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/).

---

## [1.0] — 2026-03-01

Initial public release as a standalone, website-agnostic Claude Code skill.

### Added
- **63 automated checks** across 6 categories (Page Load, Typography, Images, Responsiveness, Interactions, Console/Network)
- **CSS extraction** via `getComputedStyle()` at 7 Apple device viewports
- **Per-section screenshots** — each `<section>` captured individually at every viewport
- **Word report generator** with CSS comparison tables, screenshots, and pass/fail summary
- **Reverse proxy** for MCP Preview on external URLs
- **CLI arguments** — target URL, page route, and output directory are all configurable
- **SKILL.md** — Claude Code skill definition for automated triggering
- **GUIDE.md** — Non-technical user guide
- **README.md** — Installation and usage documentation

### Device Coverage
- iPhone SE (375x667)
- iPhone 15 (393x852)
- iPhone 15 Pro Max (430x932)
- iPad Air (820x1180)
- iPad Pro 12.9" (1024x1366)
- MacBook Air 13" (1440x900)
- MacBook Pro 16" (1728x1117)

### Origin
Extracted and generalized from the Zendar website QA system (v1.0–v3.0), where it was developed and battle-tested with 55+ PASS checks on a production Figma Make site.
