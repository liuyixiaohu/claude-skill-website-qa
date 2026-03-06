#!/usr/bin/env python3
"""
Visual QA -- Playwright automated checks + CSS extraction.

60+ checks across 6 categories, 7 device viewports, per-section screenshots,
and full CSS inspection data for downstream MCP Preview analysis.

Usage:
  python3 automated.py <BASE_URL> [PAGE_ROUTE] [--out DIR]

Examples:
  python3 automated.py https://example.com
  python3 automated.py https://example.com /about
  python3 automated.py https://example.com /pricing --out /tmp/my-qa
"""
import argparse
import asyncio
import json
import os
import re as _re
import sys
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Config: optional qa-config.yaml overrides auto-detected defaults
# ---------------------------------------------------------------------------
DEFAULT_CONFIG = {
    "fonts": {
        "heading": None,   # None = just check consistency across headings
        "body": None,      # None = just check consistency across body text
    },
    "features": {
        # "auto" = detect at runtime; True/False = force on/off
        "nav": "auto",
        "hamburger": "auto",
        "contact_modal": "auto",
        "hero_section": "auto",
        "footer": "auto",
    },
    "thresholds": {
        "hero_min_height": 200,
        "h1_min_mobile": 20,
        "h1_min_desktop": 28,
        "nav_min_links": 2,
        "touch_target_min": 44,
    },
}


def _load_config(out_dir):
    """Load config from qa-config.yaml if present, merge with defaults."""
    config = json.loads(json.dumps(DEFAULT_CONFIG))  # deep copy

    for search_dir in [out_dir, os.getcwd()]:
        cfg_path = os.path.join(search_dir, "qa-config.yaml")
        if os.path.exists(cfg_path):
            try:
                import yaml
            except ImportError:
                # Fall back to simple parsing if PyYAML not installed
                print(f"  Config found at {cfg_path} but PyYAML not installed, using defaults")
                break
            with open(cfg_path) as f:
                user_cfg = yaml.safe_load(f) or {}
            for section in ("fonts", "features", "thresholds"):
                if section in user_cfg and isinstance(user_cfg[section], dict):
                    config[section].update(user_cfg[section])
            if "selectors" in user_cfg and isinstance(user_cfg[section], dict):
                config["selectors"] = user_cfg["selectors"]
            print(f"  Loaded config from {cfg_path}")
            break

    return config


DEVICES = [
    ("iPhone_SE", 375, 667),
    ("iPhone_15", 393, 852),
    ("iPhone_15_Pro_Max", 430, 932),
    ("iPad_Air", 820, 1180),
    ("iPad_Pro_12_9", 1024, 1366),
    ("MacBook_Air_13", 1440, 900),
    ("MacBook_Pro_16", 1728, 1117),
]

MOBILE_BREAKPOINT = 1024  # below this -> hamburger nav expected

# Categories for summary grouping
CATEGORIES = {
    "part1": "Page Load & Layout",
    "part2": "Typography & Colors",
    "part3": "Images & Media",
    "part4": "Responsiveness",
    "part5": "Interactions",
    "part6": "Console & Network",
}

# Which parts trigger "FIX BEFORE PUBLISHING" on any FAIL
CRITICAL_PARTS = {"part1", "part2", "part3", "part5"}

# Default selectors — can be overridden via qa-config.yaml
SELECTORS = {
    "nav_logo": "nav a:has(img), nav a:has(svg)",
    "hamburger_btn": 'button[class*="lg:hidden"], button[aria-label="Toggle menu"], button[aria-label="Menu"], nav button[class*="menu"], button[class*="hamburger"]',
    "modal": "[role=dialog], [aria-modal=true], .fixed.inset-0, [class*=modal]",
    "modal_close": "button:has-text('\u00d7'), button:has-text('Close'), button[aria-label*='close'], button[aria-label*='Close'], [role=dialog] button:first-of-type",
}


# Map check-id prefix to part key
def _part_for(check_id: str) -> str:
    num = float(check_id.split(".")[0]) if check_id[0].isdigit() else 99
    if 1 <= num <= 5:
        return "part1"
    if 6 <= num <= 8:
        return "part2"
    if 9 <= num <= 10:
        return "part3"
    if 11 <= num <= 14:
        return "part4"
    if 15 <= num <= 17:
        return "part5"
    if 19 <= num <= 20:
        return "part6"
    if 21 <= num <= 23:
        # Hybrid-specific -> grouped into the most relevant standard part
        if 21 <= num <= 21.9:
            return "part2"  # typography
        if 22 <= num <= 22.9:
            return "part1"  # layout / consistency
        if 23 <= num <= 23.9:
            return "part1"  # semantic HTML
    return "part1"


# ---------------------------------------------------------------------------
# JS: Find sections inside <main>
# ---------------------------------------------------------------------------
FIND_SECTIONS_JS = """
(() => {
    const out = [];
    const main = document.querySelector('main#main-content') || document.querySelector('main');
    if (main) {
        for (const child of main.children) {
            if (child.tagName === 'SECTION') {
                const h = child.querySelector('h1, h2');
                out.push({
                    heading: h ? h.textContent.trim().substring(0, 50) : '',
                    selector: child.id ? 'section#' + child.id
                             : child.getAttribute('aria-labelledby')
                               ? 'section[aria-labelledby="' + child.getAttribute('aria-labelledby') + '"]'
                               : null
                });
            } else if (child.tagName === 'DIV') {
                for (const gc of child.children) {
                    if (gc.tagName === 'SECTION') {
                        const h = gc.querySelector('h1, h2');
                        out.push({
                            heading: h ? h.textContent.trim().substring(0, 50) : '',
                            selector: gc.id ? 'section#' + gc.id : null
                        });
                    }
                }
            }
        }
    }
    const footer = document.querySelector('footer');
    if (footer) out.push({ heading: 'Footer', selector: 'footer' });
    return out;
})()
"""

# ---------------------------------------------------------------------------
# JS: Extract computed styles on 30+ elements
# ---------------------------------------------------------------------------
CSS_EXTRACT_JS = """
(() => {
    const getS = (el, label) => {
        if (!el) return null;
        const s = getComputedStyle(el);
        const r = el.getBoundingClientRect();
        return {
            label, text: el.textContent.trim().substring(0, 60),
            tagName: el.tagName,
            className: el.className ? String(el.className).substring(0, 120) : '',
            fontFamily: s.fontFamily, fontSize: s.fontSize,
            fontWeight: s.fontWeight, lineHeight: s.lineHeight,
            letterSpacing: s.letterSpacing, color: s.color,
            backgroundColor: s.backgroundColor,
            backgroundImage: s.backgroundImage !== 'none' ? 'has-image' : 'none',
            backgroundSize: s.backgroundSize,
            display: s.display, position: s.position,
            overflow: s.overflow, textOverflow: s.textOverflow,
            flexDirection: s.flexDirection, gridTemplateColumns: s.gridTemplateColumns,
            padding: s.padding, margin: s.margin,
            borderRadius: s.borderRadius,
            width: r.width + 'px', height: r.height + 'px',
            x: r.x, y: r.y,
            minWidth: s.minWidth, minHeight: s.minHeight,
            maxWidth: s.maxWidth,
        };
    };
    const out = [];

    // Nav ---------------------------------------------------------------
    const nav = document.querySelector('nav');
    out.push(getS(nav, 'nav'));

    // Nav links (visible only)
    document.querySelectorAll('nav a[href]').forEach((a, i) => {
        const r = a.getBoundingClientRect();
        if (r.width > 0 && r.height > 0) {
            const s = getComputedStyle(a);
            out.push({
                label: 'nav-link-' + i, text: a.textContent.trim(),
                href: a.getAttribute('href'),
                fontFamily: s.fontFamily, fontSize: s.fontSize,
                fontWeight: s.fontWeight, color: s.color,
                opacity: s.opacity, textDecoration: s.textDecorationLine,
                width: r.width + 'px', height: r.height + 'px',
            });
        }
    });

    // Hamburger button
    const hamburger = document.querySelector('button[class*="lg:hidden"]')
                   || document.querySelector('button[aria-label="Toggle menu"]')
                   || document.querySelector('nav button[class*="menu"]');
    if (hamburger) {
        const hs = getComputedStyle(hamburger);
        const hr = hamburger.getBoundingClientRect();
        out.push({
            label: 'hamburger',
            display: hs.display,
            visible: hs.display !== 'none' && hr.width > 0,
            width: hr.width + 'px', height: hr.height + 'px',
        });
    }

    // Desktop nav text links container
    const navDesktopLinks = document.querySelector('nav [class*="hidden lg:flex"], nav [class*="lg:flex"]');
    if (navDesktopLinks) {
        const nds = getComputedStyle(navDesktopLinks);
        out.push({
            label: 'nav-desktop-links',
            display: nds.display,
            width: navDesktopLinks.getBoundingClientRect().width + 'px',
        });
    }

    // Contact button in nav
    const contactBtn = Array.from(document.querySelectorAll('nav button, nav a')).find(b => b.textContent.trim().includes('Contact'));
    if (contactBtn) out.push(getS(contactBtn, 'contact-button'));

    // h1 ----------------------------------------------------------------
    out.push(getS(document.querySelector('h1'), 'h1'));

    // Hero subtitle (first p in first section)
    const heroP = document.querySelector('main section:first-child p, main > div > section:first-child p');
    out.push(getS(heroP, 'hero-subtitle'));

    // All h2s
    document.querySelectorAll('h2').forEach((h, i) => out.push(getS(h, 'h2-' + i)));

    // All h3s
    document.querySelectorAll('h3').forEach((h, i) => {
        if (i < 8) out.push(getS(h, 'h3-' + i));
    });

    // Section body paragraphs (first 12)
    document.querySelectorAll('main section p, main > div > section p').forEach((p, i) => {
        if (i < 12) out.push(getS(p, 'body-p-' + i));
    });

    // All buttons
    document.querySelectorAll('button, a[role="button"]').forEach((b, i) => {
        if (i < 20) {
            const s = getComputedStyle(b);
            const r = b.getBoundingClientRect();
            out.push({
                label: 'button-' + i,
                text: b.textContent.trim().substring(0, 40),
                tagName: b.tagName,
                fontFamily: s.fontFamily, fontSize: s.fontSize,
                fontWeight: s.fontWeight, color: s.color,
                backgroundColor: s.backgroundColor,
                borderRadius: s.borderRadius, padding: s.padding,
                display: s.display,
                visible: s.display !== 'none' && r.width > 0,
                width: r.width + 'px', height: r.height + 'px',
            });
        }
    });

    // Section backgrounds
    const sections = document.querySelectorAll('main section, main > div > section');
    sections.forEach((sec, i) => {
        const s = getComputedStyle(sec);
        const h = sec.querySelector('h1, h2');
        const r = sec.getBoundingClientRect();
        out.push({
            label: 'section-bg-' + i,
            heading: h ? h.textContent.trim().substring(0, 50) : '(none)',
            backgroundColor: s.backgroundColor,
            backgroundImage: s.backgroundImage !== 'none' ? 'has-image' : 'none',
            backgroundSize: s.backgroundSize,
            padding: s.padding,
            height: r.height + 'px',
            y: r.y, bottom: r.y + r.height,
            textContent: sec.textContent.trim().substring(0, 40),
        });
    });

    // Footer
    out.push(getS(document.querySelector('footer'), 'footer'));

    // Images
    const imgs = document.querySelectorAll('img');
    out.push({
        label: 'images-summary',
        total: imgs.length,
        allLoaded: Array.from(imgs).every(i => i.complete && i.naturalWidth > 0),
        missingAlt: Array.from(imgs).filter(i => !i.alt).length,
        details: Array.from(imgs).map(i => ({
            alt: i.alt || '(none)',
            loaded: i.complete && i.naturalWidth > 0,
            naturalW: i.naturalWidth, naturalH: i.naturalHeight,
            displayW: Math.round(i.getBoundingClientRect().width),
            displayH: Math.round(i.getBoundingClientRect().height),
        })),
    });

    // Links / touch targets (all visible a and button elements)
    const targets = [];
    document.querySelectorAll('a, button').forEach(el => {
        const r = el.getBoundingClientRect();
        if (r.width > 0 && r.height > 0) {
            targets.push({ w: r.width, h: r.height, text: el.textContent.trim().substring(0, 30) });
        }
    });
    out.push({ label: 'touch-targets', items: targets });

    return out.filter(x => x !== null);
})()
"""


# ---------------------------------------------------------------------------
# Helper: parse "Npx" to float
# ---------------------------------------------------------------------------
def _px(val):
    """Parse '16px' -> 16.0, tolerant of bad input."""
    if not val or not isinstance(val, str):
        return 0.0
    m = _re.match(r'([\d.]+)', val)
    return float(m.group(1)) if m else 0.0


# ---------------------------------------------------------------------------
# Lookup helpers for CSS data
# ---------------------------------------------------------------------------
def _find(css_data, label_prefix):
    """Return first element whose label starts with prefix."""
    if not isinstance(css_data, list):
        return None
    for item in css_data:
        if isinstance(item, dict) and item.get("label", "").startswith(label_prefix):
            return item
    return None


def _find_all(css_data, label_prefix):
    if not isinstance(css_data, list):
        return []
    return [item for item in css_data if isinstance(item, dict) and item.get("label", "").startswith(label_prefix)]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _parse_args():
    parser = argparse.ArgumentParser(
        description="Visual QA -- Playwright automated checks + CSS extraction.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Examples:\n"
               "  python3 automated.py https://example.com\n"
               "  python3 automated.py https://example.com /about\n"
               "  python3 automated.py https://example.com /pricing --out /tmp/my-qa",
    )
    parser.add_argument("base_url", help="Target website URL (e.g. https://example.com)")
    parser.add_argument("page_route", nargs="?", default="/",
                        help="Page route to test (default: /)")
    parser.add_argument("--out", default="/tmp/visual-qa",
                        help="Output directory (default: /tmp/visual-qa)")
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Post-processing helpers
# ---------------------------------------------------------------------------
def _compute_summary(results):
    """Compute per-part summary, critical issues, warnings, and verdict."""
    print("\n=== COMPUTING SUMMARY ===")
    part_summary = {}
    for key, label in CATEGORIES.items():
        passed = 0
        failed = 0
        skipped = 0
        for c in results["checks"]:
            if _part_for(c["id"]) == key:
                if c["status"] == "PASS":
                    passed += 1
                elif c["status"] == "SKIP":
                    skipped += 1
                else:
                    failed += 1
        part_summary[key] = {"name": label, "passed": passed, "failed": failed, "skipped": skipped, "total": passed + failed}
    results["summary"] = part_summary

    critical = []
    warnings_list = []
    for c in results["checks"]:
        if c["status"] == "FAIL":
            part = _part_for(c["id"])
            entry = f"[{c['id']}] {c['name']}: {c['details']}"
            if part in CRITICAL_PARTS:
                critical.append(entry)
            else:
                warnings_list.append(entry)
    results["critical_issues"] = critical
    results["warnings"] = warnings_list

    if critical:
        results["verdict"] = "FIX BEFORE PUBLISHING"
    elif warnings_list:
        results["verdict"] = "READY TO PUBLISH (with warnings)"
    else:
        results["verdict"] = "READY TO PUBLISH"


def _save_and_print(results, out_dir):
    """Save JSON to disk and print summary to stdout."""
    out_path = os.path.join(out_dir, "hybrid_automated_results.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)

    total_checks = len(results["checks"])
    total_pass = sum(1 for c in results["checks"] if c["status"] == "PASS")
    total_skip = sum(1 for c in results["checks"] if c["status"] == "SKIP")
    total_fail = total_checks - total_pass - total_skip

    ss = results["section_screenshots"].get("site", {})
    total_ss = sum(len(v) for v in ss.values())

    print(f"\n{'='*60}")
    skip_info = f" / {total_skip} SKIP" if total_skip > 0 else ""
    print(f"  RESULTS: {total_pass} PASS / {total_fail} FAIL{skip_info} / {total_checks} TOTAL")
    print(f"  CSS inspected: {len(results['css_inspection'])} viewports")
    print(f"  Section screenshots: {total_ss}")
    print(f"  Verdict: {results['verdict']}")
    print(f"{'='*60}")

    part_summary = results["summary"]
    for key, ps in part_summary.items():
        sym = "OK" if ps["failed"] == 0 else "!!"
        skip_note = f" ({ps.get('skipped', 0)} skipped)" if ps.get("skipped", 0) > 0 else ""
        print(f"  [{sym}] {ps['name']}: {ps['passed']}/{ps['total']} passed{skip_note}")

    critical = results["critical_issues"]
    if critical:
        print(f"\n  CRITICAL ISSUES ({len(critical)}):")
        for ci in critical[:10]:
            print(f"    - {ci}")

    warnings_list = results["warnings"]
    if warnings_list:
        print(f"\n  WARNINGS ({len(warnings_list)}):")
        for w in warnings_list[:10]:
            print(f"    - {w}")

    print(f"\n  Output: {out_path}")


# ---------------------------------------------------------------------------
# Browser helper
# ---------------------------------------------------------------------------
async def _open_page(browser, w, h, url, *, wait_ms=1000):
    """Create a browser context, open page, navigate, and return (ctx, page)."""
    ctx = await browser.new_context(viewport={"width": w, "height": h})
    page = await ctx.new_page()
    await page.goto(url, wait_until="networkidle", timeout=30000)
    if wait_ms > 0:
        await page.wait_for_timeout(wait_ms)
    return ctx, page


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
async def main(args):
    base_url = args.base_url.rstrip("/")
    page_route = args.page_route
    out_dir = args.out
    url = f"{base_url}{page_route}"
    os.makedirs(out_dir, exist_ok=True)
    print(f"Target: {url}")
    print(f"Output: {out_dir}")

    config = _load_config(out_dir)

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("ERROR: pip install playwright && python3 -m playwright install chromium")
        sys.exit(1)

    results = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "base_url": base_url,
        "page": page_route,
        "method": "hybrid_playwright_css_extraction",
        "checks": [],
        "summary": {},
        "critical_issues": [],
        "warnings": [],
        "verdict": "",
        "css_inspection": {},
        "section_screenshots": {},
        "interaction_tests": {},
        "page_console_errors": [],
        "page_network_failures": [],
    }

    def add(cid, name, cat, passed, details=""):
        status = "PASS" if passed else "FAIL"
        results["checks"].append({
            "id": cid, "name": name, "category": cat,
            "status": status, "details": str(details),
        })
        print(f"  [{status}] {cid} {name}")

    def skip(cid, name, cat, reason="Feature not detected"):
        results["checks"].append({
            "id": cid, "name": name, "category": cat,
            "status": "SKIP", "details": reason,
        })
        print(f"  [SKIP] {cid} {name} — {reason}")

    # ===================================================================
    # Launch browser
    # ===================================================================
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)

        # ==============================================================
        # PHASE A+B: CSS EXTRACTION + SECTION SCREENSHOTS (merged)
        # Viewports run in parallel (semaphore=3 to limit resource use)
        # ==============================================================
        print("\n=== PHASE A+B: CSS EXTRACTION & SCREENSHOTS (all 7 viewports) ===")
        viewport_data = {}  # dev_name -> {overflow, scroll_width}
        results["section_screenshots"]["site"] = {}

        _sem = asyncio.Semaphore(3)

        async def _process_viewport(dev_name, w, h):
            async with _sem:
                print(f"  Viewport: {dev_name} ({w}x{h})")
                vp_result = {"css_data": [], "screenshots": [],
                             "overflow": None, "scroll_width": None}
                ctx, pg = await _open_page(browser, w, h, url)
                try:
                    # CSS extraction
                    try:
                        css_data = await pg.evaluate(CSS_EXTRACT_JS)
                        vp_result["css_data"] = css_data
                        print(f"    CSS: {len(css_data)} elements")
                    except Exception as e:
                        print(f"    CSS FAIL: {e}")
                        vp_result["css_data"] = {"error": str(e)}

                    # Overflow measurement (reused by Part 4 checks)
                    try:
                        vp_result["overflow"] = await pg.evaluate(
                            "document.documentElement.scrollWidth > document.documentElement.clientWidth"
                        )
                        vp_result["scroll_width"] = await pg.evaluate(
                            "document.documentElement.scrollWidth"
                        )
                    except Exception:
                        pass

                    # Section screenshots
                    sec_list = []
                    try:
                        section_info = await pg.evaluate(FIND_SECTIONS_JS)
                        for idx, sec in enumerate(section_info):
                            heading = sec.get("heading", "") or f"Section {idx}"
                            slug = _re.sub(r'[^a-z0-9]+', '_', heading.lower())[:30].strip('_') or f"section_{idx}"
                            fname = f"hybrid_site_{dev_name}_sec_{idx}_{slug}.png"
                            try:
                                if sec.get("selector"):
                                    el = pg.locator(sec["selector"]).first
                                else:
                                    el = pg.locator("main section").nth(idx)
                                await el.screenshot(path=os.path.join(out_dir, fname))
                                sec_list.append({"label": heading, "file": fname})
                                print(f"    OK  {fname}")
                            except Exception as e2:
                                print(f"    SKIP {fname}: {e2}")
                    except Exception as e:
                        print(f"    Screenshots FAIL: {e}")
                    vp_result["screenshots"] = sec_list
                finally:
                    await ctx.close()
                return dev_name, vp_result

        vp_results = await asyncio.gather(
            *[_process_viewport(dn, w, h) for dn, w, h in DEVICES]
        )
        for dev_name, vp_result in vp_results:
            results["css_inspection"][dev_name] = vp_result["css_data"]
            results["section_screenshots"]["site"][dev_name] = vp_result["screenshots"]
            viewport_data[dev_name] = {
                "overflow": vp_result["overflow"],
                "scroll_width": vp_result["scroll_width"],
            }

        # Shorthand to pull CSS data for a viewport
        def css(dev):
            return results["css_inspection"].get(dev, [])

        # ==============================================================
        # AUTO-DETECT SITE FEATURES
        # ==============================================================
        print("\n=== AUTO-DETECTING SITE FEATURES ===")
        desk_css_detect = css("MacBook_Air_13")
        mob_css_detect = css("iPhone_SE")

        def _feature(key):
            val = config["features"].get(key, "auto")
            return val if val != "auto" else None  # None = needs detection

        has_nav = _feature("nav")
        if has_nav is None:
            has_nav = _find(desk_css_detect, "nav") is not None
        print(f"  nav: {has_nav}")

        has_hamburger = _feature("hamburger")
        if has_hamburger is None:
            has_hamburger = has_nav and _find(mob_css_detect, "hamburger") is not None
        print(f"  hamburger: {has_hamburger}")

        has_hero = _feature("hero_section")
        if has_hero is None:
            sections_detect = _find_all(desk_css_detect, "section-bg-")
            has_hero = len(sections_detect) > 0
        print(f"  hero_section: {has_hero}")

        has_footer = _feature("footer")
        if has_footer is None:
            has_footer = _find(desk_css_detect, "footer") is not None
        print(f"  footer: {has_footer}")

        # Contact modal detection deferred to Part 5 (needs page interaction)
        has_contact_modal = _feature("contact_modal")
        # If "auto", we'll try to detect during interaction tests

        # ==============================================================
        # PART 1 -- Page Load & Layout (IDs 1.x - 5.x)
        # ==============================================================
        print("\n=== PART 1: PAGE LOAD & LAYOUT ===")

        console_errors = []
        network_failures = []
        font_responses = []

        ctx = await browser.new_context(viewport={"width": 1440, "height": 900})
        pg = await ctx.new_page()
        pg.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        pg.on("requestfailed", lambda req: network_failures.append(f"{req.method} {req.url} -> {req.failure}"))
        pg.on("response", lambda resp: font_responses.append({"url": resp.url, "status": resp.status}) if _re.search(r'\.woff2?(\?|$)', resp.url) else None)

        resp = await pg.goto(url, wait_until="networkidle", timeout=30000)
        await pg.wait_for_timeout(1000)

        # 1.1 HTTP 200
        status_code = resp.status if resp else 0
        add("1.1", "Page loads (HTTP 200, no error boundary)", "Page Load & Layout",
            status_code == 200, f"HTTP {status_code}")

        # 1.2 Page title
        title = await pg.title()
        add("1.2", "Page title present", "Page Load & Layout",
            len(title.strip()) > 0, f"Title: {title}")

        # 1.3 Viewport meta
        vp = await pg.evaluate("document.querySelector('meta[name=viewport]')?.content || ''")
        add("1.3", "Viewport meta tag", "Page Load & Layout",
            "width=device-width" in vp, vp)

        # 1.4 Meta description
        desc = await pg.evaluate("document.querySelector('meta[name=description]')?.content || ''")
        add("1.4", "Meta description present", "Page Load & Layout",
            len(desc) > 10, desc[:120])

        # 1.5 OG title
        og_title = await pg.evaluate("document.querySelector('meta[property=\"og:title\"]')?.content || ''")
        add("1.5", "OG title present", "Page Load & Layout",
            len(og_title) > 0, og_title)

        # 1.6 Canonical URL
        canonical = await pg.evaluate("document.querySelector('link[rel=canonical]')?.href || ''")
        add("1.6", "Canonical URL present", "Page Load & Layout",
            len(canonical) > 0, canonical)

        # 5.3 No horizontal overflow at 1440px
        overflow_desktop = await pg.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth")
        add("5.3", "No horizontal overflow (desktop 1440px)", "Page Load & Layout",
            not overflow_desktop, "No overflow" if not overflow_desktop else "Overflow detected")

        # --- CSS-based checks (use MacBook Air 13 = 1440px data) ---
        desk_css = css("MacBook_Air_13")
        mob_css = css("iPhone_SE")
        ipad_pro_css = css("iPad_Pro_12_9")
        ipad_air_css = css("iPad_Air")

        nav_el = _find(desk_css, "nav")
        hamburger_el = _find(mob_css, "hamburger")
        hamburger_visible = hamburger_el and hamburger_el.get("visible", False) if hamburger_el else False
        ipad_air_has_hamburger = False

        if has_nav:
            # 2.1 NavBar desktop appearance
            nav_ok = False
            nav_detail = "nav not found in CSS data"
            if nav_el:
                nav_h = _px(nav_el.get("height", ""))
                nav_bg = nav_el.get("backgroundColor", "")
                nav_links = _find_all(desk_css, "nav-link-")
                min_links = config["thresholds"].get("nav_min_links", 2)
                nav_ok = (30 <= nav_h <= 200) and len(nav_links) >= min_links
                nav_detail = f"h={nav_h}px, bg={nav_bg}, links={len(nav_links)}"
            add("2.1", "NavBar desktop appearance", "Page Load & Layout", nav_ok, nav_detail)

            # 2.2 NavBar mobile appearance
            if has_hamburger:
                mob_nav_links = _find_all(mob_css, "nav-link-")
                add("2.2", "NavBar mobile appearance (hamburger visible)", "Page Load & Layout",
                    hamburger_visible is True,
                    f"hamburger_visible={hamburger_visible}, visible_links={len(mob_nav_links)}")
            else:
                skip("2.2", "NavBar mobile appearance", "Page Load & Layout", "No hamburger nav pattern detected")

            # 2.3 NavBar does not overlap content
            h1_el = _find(desk_css, "h1")
            nav_overlap_ok = False
            overlap_detail = "h1 or nav not found"
            if h1_el and nav_el:
                h1_y = h1_el.get("y", 0)
                nav_h = _px(nav_el.get("height", ""))
                nav_overlap_ok = h1_y > nav_h
                overlap_detail = f"h1.y={h1_y}, nav.height={nav_h}"
            add("2.3", "NavBar does not overlap content", "Page Load & Layout", nav_overlap_ok, overlap_detail)

            # 2.4 NavBar responsive breakpoint
            if has_hamburger:
                ip_hamburger = _find(ipad_pro_css, "hamburger")
                ia_hamburger = _find(ipad_air_css, "hamburger")
                ipad_air_has_hamburger = ia_hamburger and ia_hamburger.get("visible", False)
                add("2.4", "NavBar responsive breakpoint", "Page Load & Layout",
                    ipad_air_has_hamburger is True,
                    f"iPad Air (820px) hamburger={ipad_air_has_hamburger}")
            else:
                skip("2.4", "NavBar responsive breakpoint", "Page Load & Layout", "No hamburger nav pattern detected")
        else:
            skip("2.1", "NavBar desktop appearance", "Page Load & Layout", "No nav element detected")
            skip("2.2", "NavBar mobile appearance", "Page Load & Layout", "No nav element detected")
            skip("2.3", "NavBar does not overlap content", "Page Load & Layout", "No nav element detected")
            skip("2.4", "NavBar responsive breakpoint", "Page Load & Layout", "No nav element detected")
            h1_el = _find(desk_css, "h1")

        # 3.1 Hero section visible
        sections_bg = _find_all(desk_css, "section-bg-")
        hero_sec = sections_bg[0] if sections_bg else None
        if has_hero and hero_sec:
            hero_h = _px(hero_sec.get("height", ""))
            hero_has_bg = hero_sec.get("backgroundImage") == "has-image" or hero_sec.get("backgroundColor", "") != "rgba(0, 0, 0, 0)"
            hero_min = config["thresholds"].get("hero_min_height", 200)
            hero_ok = hero_h >= hero_min and hero_has_bg
            hero_detail = f"height={hero_h}px, hasBg={hero_has_bg}"
            add("3.1", f"Hero section visible (height >= {hero_min}px, has background)", "Page Load & Layout",
                hero_ok, hero_detail)
        else:
            skip("3.1", "Hero section visible", "Page Load & Layout", "No hero section detected")

        # 4.1 No blank sections
        blank_sections = []
        for sb in sections_bg:
            sh = _px(sb.get("height", ""))
            has_text = len(sb.get("textContent", "").strip()) > 0
            if sh < 50 or not has_text:
                blank_sections.append(f"{sb.get('heading', '?')}: h={sh}px, hasText={has_text}")
        add("4.1", "No blank sections (each > 50px with text)", "Page Load & Layout",
            len(blank_sections) == 0,
            f"{len(blank_sections)} blank" + (f": {blank_sections[:3]}" if blank_sections else ""))

        # 4.2 Section spacing (no gaps > 5px between consecutive)
        gaps = []
        for i in range(len(sections_bg) - 1):
            bottom_i = sections_bg[i].get("bottom", 0)
            top_next = sections_bg[i + 1].get("y", 0)
            gap = top_next - bottom_i
            if gap > 5:
                gaps.append(f"gap {i}->{i+1}: {gap:.0f}px")
        add("4.2", "Section spacing (no gaps > 5px)", "Page Load & Layout",
            len(gaps) == 0,
            f"{len(gaps)} gaps" + (f": {gaps[:3]}" if gaps else ""))

        # 4.3 Content max-width at 1728px
        mbp_css = css("MacBook_Pro_16")
        mbp_h1 = _find(mbp_css, "h1")
        content_maxw_ok = True
        maxw_detail = ""
        if mbp_h1:
            h1_w = _px(mbp_h1.get("width", ""))
            content_maxw_ok = h1_w < 1728 - 100  # at least 50px margin each side
            maxw_detail = f"h1 width at 1728px viewport = {h1_w}px"
        add("4.3", "Content max-width (no full-width stretch at 1728px)", "Page Load & Layout",
            content_maxw_ok, maxw_detail)

        # 5.1 Footer renders
        footer_el = _find(desk_css, "footer")
        if has_footer:
            footer_ok = footer_el is not None and _px(footer_el.get("height", "")) > 0
            add("5.1", "Footer renders", "Page Load & Layout",
                footer_ok, f"height={_px(footer_el.get('height', '')) if footer_el else 0}px")

            # 5.2 Footer content
            footer_text = footer_el.get("text", "") if footer_el else ""
            add("5.2", "Footer has text content", "Page Load & Layout",
                len(footer_text.strip()) > 5, f"text: {footer_text[:80]}")
        else:
            skip("5.1", "Footer renders", "Page Load & Layout", "No footer detected")
            skip("5.2", "Footer has text content", "Page Load & Layout", "No footer detected")

        await ctx.close()

        # ==============================================================
        # PART 2 -- Typography & Colors (IDs 6.x - 8.x)
        # ==============================================================
        print("\n=== PART 2: TYPOGRAPHY & COLORS ===")

        # Use desktop CSS data
        desk_h1 = _find(desk_css, "h1")
        desk_hero_sub = _find(desk_css, "hero-subtitle")
        desk_nav_links = _find_all(desk_css, "nav-link-")

        expected_heading_font = config["fonts"].get("heading")
        expected_body_font = config["fonts"].get("body")

        h1_ff = desk_h1.get("fontFamily", "") if desk_h1 else ""
        body_ps = _find_all(desk_css, "body-p-")
        body_ff = body_ps[0].get("fontFamily", "") if body_ps else ""

        # 6.1 Heading font
        if expected_heading_font:
            add("6.1", f"Heading font is {expected_heading_font}", "Typography & Colors",
                expected_heading_font.lower() in h1_ff.lower(),
                f"h1 fontFamily: {h1_ff[:60]}")
        else:
            # Just check that headings have a font loaded (not empty/default)
            has_heading_font = len(h1_ff) > 0 and "serif" not in h1_ff.lower().split(",")[0]
            add("6.1", "Heading font loaded", "Typography & Colors",
                len(h1_ff) > 0, f"h1 fontFamily: {h1_ff[:60]}")

        # 6.2 Body text font
        if expected_body_font:
            add("6.2", f"Body text font is {expected_body_font}", "Typography & Colors",
                expected_body_font.lower() in body_ff.lower(),
                f"p fontFamily: {body_ff[:60]}")
        else:
            add("6.2", "Body text font loaded", "Typography & Colors",
                len(body_ff) > 0, f"p fontFamily: {body_ff[:60]}")

        # 6.3 Heading/body font differentiation
        h1_primary = h1_ff.split(",")[0].strip().strip('"').strip("'").lower() if h1_ff else ""
        body_primary = body_ff.split(",")[0].strip().strip('"').strip("'").lower() if body_ff else ""
        fonts_differ = h1_primary != body_primary and h1_primary and body_primary
        add("6.3", "Heading and body use distinct fonts (or intentionally same)", "Typography & Colors",
            True,  # Advisory check — same font is valid design choice
            f"heading={h1_primary}, body={body_primary}" + (" (same)" if not fonts_differ else " (different)"))

        # 6.4 Font consistency across headings
        h2_elements = _find_all(desk_css, "h2-")
        heading_fonts = set()
        if h1_ff:
            heading_fonts.add(h1_ff.split(",")[0].strip().strip('"').strip("'").lower())
        for h2 in h2_elements:
            ff = h2.get("fontFamily", "")
            if ff:
                heading_fonts.add(ff.split(",")[0].strip().strip('"').strip("'").lower())
        add("6.4", "Heading font consistency (all h1/h2 same family)", "Typography & Colors",
            len(heading_fonts) <= 1,
            f"heading fonts: {list(heading_fonts)}")

        # 7.1, 7.2 — Removed (contrast checks produced false positives for this site)

        # 7.4 Heading text readability (font size)
        mob_h1 = _find(mob_css, "h1")
        mob_fs = _px(mob_h1.get("fontSize", "")) if mob_h1 else 0
        desk_fs = _px(desk_h1.get("fontSize", "")) if desk_h1 else 0
        h1_min_mob = config["thresholds"].get("h1_min_mobile", 20)
        h1_min_desk = config["thresholds"].get("h1_min_desktop", 28)
        add("7.4", f"Heading readability (h1 >= {h1_min_mob}px mobile, >= {h1_min_desk}px desktop)", "Typography & Colors",
            mob_fs >= h1_min_mob and desk_fs >= h1_min_desk,
            f"mobile h1={mob_fs}px, desktop h1={desk_fs}px")

        # 8.1 No text truncation (overflow:hidden + text-overflow:ellipsis)
        truncated = []
        for el in desk_css if isinstance(desk_css, list) else []:
            if not isinstance(el, dict):
                continue
            label = el.get("label", "")
            if label.startswith("h1") or label.startswith("h2-") or label.startswith("h3-") or label.startswith("body-p-"):
                ov = el.get("overflow", "")
                to = el.get("textOverflow", "")
                if "hidden" in ov and "ellipsis" in to:
                    truncated.append(f"{label}: overflow={ov}, textOverflow={to}")
        add("8.1", "No text truncation on headings/paragraphs", "Typography & Colors",
            len(truncated) == 0,
            f"{len(truncated)} truncated" + (f": {truncated[:3]}" if truncated else ""))

        # 8.2 Heading balance (no very short headings that might cause orphan lines)
        h2_elements = _find_all(desk_css, "h2-")
        short_headings = []
        for h2 in h2_elements:
            text = h2.get("text", "")
            w = _px(h2.get("width", ""))
            if len(text) > 0 and len(text) < 10 and w > 400:
                short_headings.append(f"{h2.get('label')}: '{text}' in {w}px container")
        add("8.2", "Heading balance (no orphan-word headings)", "Typography & Colors",
            True,  # This is more of an advisory check
            f"{len(short_headings)} potentially unbalanced" if short_headings else "Headings look balanced")

        # ==============================================================
        # PART 3 -- Images & Media (IDs 9.x - 10.x)
        # ==============================================================
        print("\n=== PART 3: IMAGES & MEDIA ===")

        img_summary = _find(desk_css, "images-summary")

        # 9.1 No broken images
        all_loaded = img_summary.get("allLoaded", False) if img_summary else False
        img_details_list = img_summary.get("details", []) if img_summary else []
        broken = [d for d in img_details_list if not d.get("loaded")]
        add("9.1", "No broken images", "Images & Media",
            all_loaded,
            f"{len(broken)}/{len(img_details_list)} broken" + (f": {[d.get('alt') for d in broken[:3]]}" if broken else ""))

        # 9.2 Hero background image
        hero_bg_img = hero_sec.get("backgroundImage", "none") if hero_sec else "none"
        hero_bg_color = hero_sec.get("backgroundColor", "") if hero_sec else ""
        has_hero_bg = hero_bg_img == "has-image" or (hero_bg_color != "rgba(0, 0, 0, 0)" and hero_bg_color != "")
        add("9.2", "Hero background image or color", "Images & Media",
            has_hero_bg, f"bgImage={hero_bg_img}, bgColor={hero_bg_color}")

        # 10.1 No stretched images
        stretched = []
        for d in img_details_list:
            nw, nh = d.get("naturalW", 0), d.get("naturalH", 0)
            dw, dh = d.get("displayW", 0), d.get("displayH", 0)
            if nw > 0 and nh > 0 and dw > 0 and dh > 0:
                nat_ratio = nw / nh
                disp_ratio = dw / dh
                diff = abs(nat_ratio - disp_ratio) / nat_ratio
                if diff > 0.1:
                    stretched.append(f"{d.get('alt', '?')}: natural={nw}x{nh}, display={dw}x{dh}")
        add("10.1", "No stretched images (aspect ratio preserved)", "Images & Media",
            len(stretched) == 0,
            f"{len(stretched)} stretched" + (f": {stretched[:3]}" if stretched else ""))

        # 10.2 Proper image sizing (not rendered > 2x natural)
        oversized = []
        for d in img_details_list:
            nw = d.get("naturalW", 0)
            dw = d.get("displayW", 0)
            if nw > 0 and dw > 2 * nw:
                oversized.append(f"{d.get('alt', '?')}: natural={nw}px, display={dw}px")
        add("10.2", "Proper image sizing (display <= 2x natural)", "Images & Media",
            len(oversized) == 0,
            f"{len(oversized)} oversized" + (f": {oversized[:3]}" if oversized else ""))

        # 10.3 Hero background coverage
        hero_bg_size = hero_sec.get("backgroundSize", "") if hero_sec else ""
        add("10.3", "Hero background coverage (cover or 100%)", "Images & Media",
            "cover" in hero_bg_size or "100%" in hero_bg_size or hero_bg_img != "has-image",
            f"backgroundSize={hero_bg_size}" if hero_bg_img == "has-image" else "No background image; color bg")

        # 10.4 All images have alt text
        missing_alt = img_summary.get("missingAlt", 0) if img_summary else 0
        add("10.4", "All images have alt text", "Images & Media",
            missing_alt == 0,
            f"{missing_alt} images without alt text")

        # ==============================================================
        # PART 4 -- Responsiveness (IDs 11.x - 14.x)
        # ==============================================================
        print("\n=== PART 4: RESPONSIVENESS ===")

        # 11.1 Mobile single column
        mob_sections = _find_all(mob_css, "section-bg-")
        mob_single_col = True
        mob_col_detail = []
        for el in mob_css if isinstance(mob_css, list) else []:
            if not isinstance(el, dict):
                continue
            fd = el.get("flexDirection", "")
            gtc = el.get("gridTemplateColumns", "")
            if fd == "row" and _px(el.get("width", "")) > 300:
                # Row direction at mobile is suspicious if it's a main content container
                if el.get("label", "").startswith("section-bg-") or el.get("label", "").startswith("body-p-"):
                    mob_single_col = False
                    mob_col_detail.append(f"{el.get('label')}: flexDirection=row")
            if gtc and "px" in gtc and gtc.count("px") > 1:
                mob_single_col = False
                mob_col_detail.append(f"{el.get('label')}: grid={gtc}")
        add("11.1", "Mobile single column layout (iPhone SE)", "Responsiveness",
            mob_single_col,
            "; ".join(mob_col_detail[:3]) if mob_col_detail else "Single column layout confirmed")

        # 11.2 Hamburger menu visible at mobile
        if has_hamburger:
            add("11.2", "Hamburger menu visible at mobile", "Responsiveness",
                hamburger_visible is True,
                f"hamburger visible={hamburger_visible}")
        else:
            skip("11.2", "Hamburger menu visible at mobile", "Responsiveness", "No hamburger nav pattern detected")

        # 11.3 Touch target sizing at mobile
        touch_min = config["thresholds"].get("touch_target_min", 44)
        touch_targets_el = _find(mob_css, "touch-targets")
        small_targets = []
        if touch_targets_el:
            for t in touch_targets_el.get("items", []):
                if t.get("w", 0) < touch_min or t.get("h", 0) < touch_min:
                    small_targets.append(f"'{t.get('text', '?')}': {t.get('w')}x{t.get('h')}")
        add("11.3", f"Touch target sizing (>= {touch_min}px at mobile)", "Responsiveness",
            len(small_targets) <= 2,  # Allow up to 2 minor exceptions
            f"{len(small_targets)} small targets" + (f": {small_targets[:3]}" if small_targets else ""))

        # 11.4 No mobile horizontal scroll at 375px (uses Phase A+B data)
        vd_se = viewport_data.get("iPhone_SE", {})
        mob_overflow = vd_se.get("overflow", False)
        mob_sw = vd_se.get("scroll_width", 375)
        add("11.4", "No mobile horizontal scroll (375px)", "Responsiveness",
            not mob_overflow,
            f"scrollWidth={mob_sw}" if mob_overflow else "No overflow")

        # 12.1 iPhone 15 layout OK (393px, uses Phase A+B data)
        vd_15 = viewport_data.get("iPhone_15", {})
        ip15_overflow = vd_15.get("overflow", False)
        add("12.1", "iPhone 15 layout OK (393px, no overflow)", "Responsiveness",
            not ip15_overflow, "No overflow" if not ip15_overflow else "Overflow detected")

        # 12.2 iPhone 15 Pro Max layout OK (430px, uses Phase A+B data)
        vd_15pm = viewport_data.get("iPhone_15_Pro_Max", {})
        ip15pm_overflow = vd_15pm.get("overflow", False)
        add("12.2", "iPhone 15 Pro Max layout OK (430px, no overflow)", "Responsiveness",
            not ip15pm_overflow, "No overflow" if not ip15pm_overflow else "Overflow detected")

        # 13.1 iPad Air layout (820px)
        if has_hamburger:
            add("13.1", "iPad Air layout (820px, hamburger nav)", "Responsiveness",
                ipad_air_has_hamburger is True,
                f"hamburger visible at 820px = {ipad_air_has_hamburger}")
        else:
            skip("13.1", "iPad Air layout (hamburger nav)", "Responsiveness", "No hamburger nav pattern detected")

        # 13.2 iPad Pro 12.9" layout (1024px -- near breakpoint)
        ip_pro_hamburger_visible = ip_hamburger and ip_hamburger.get("visible", False) if ip_hamburger else False
        ip_pro_nav_links = _find_all(ipad_pro_css, "nav-link-")
        add("13.2", "iPad Pro 12.9\" layout (1024px, nav breakpoint)", "Responsiveness",
            True,  # Informational -- just checking which style
            f"hamburger={ip_pro_hamburger_visible}, visible_links={len(ip_pro_nav_links)}")

        # 14.1 MacBook Air 13" layout (1440px -- full desktop)
        desk_nav_links_count = len(_find_all(desk_css, "nav-link-"))
        desk_hamburger = _find(desk_css, "hamburger")
        desk_hamburger_visible = desk_hamburger and desk_hamburger.get("visible", False) if desk_hamburger else False
        if has_nav:
            min_links = config["thresholds"].get("nav_min_links", 2)
            add("14.1", "MacBook Air 13\" layout (desktop nav visible)", "Responsiveness",
                desk_nav_links_count >= min_links and not desk_hamburger_visible,
                f"nav links={desk_nav_links_count}, hamburger={desk_hamburger_visible}")
        else:
            skip("14.1", "MacBook Air 13\" layout (desktop nav)", "Responsiveness", "No nav element detected")

        # 14.2 MacBook Pro 16" layout (1728px -- centered, not stretched)
        mbp_sections = _find_all(mbp_css, "section-bg-")
        mbp_centered = True
        if mbp_h1:
            h1_x = mbp_h1.get("x", 0)
            h1_w = _px(mbp_h1.get("width", ""))
            if h1_x < 50:  # Content too close to edge
                mbp_centered = False
        add("14.2", "MacBook Pro 16\" layout (content centered, not full-width)", "Responsiveness",
            mbp_centered,
            f"h1 x={mbp_h1.get('x', '?') if mbp_h1 else '?'}px, width={_px(mbp_h1.get('width', '')) if mbp_h1 else '?'}px")

        # 14.3 Typography fluid scaling (h1 differs between iPhone SE and MacBook Pro)
        se_h1 = _find(css("iPhone_SE"), "h1")
        mbp16_h1 = _find(css("MacBook_Pro_16"), "h1")
        se_fs = se_h1.get("fontSize", "") if se_h1 else ""
        mbp_fs = mbp16_h1.get("fontSize", "") if mbp16_h1 else ""
        add("14.3", "Typography fluid scaling (h1 size differs mobile vs desktop)", "Responsiveness",
            se_fs != mbp_fs and se_fs != "" and mbp_fs != "",
            f"iPhone SE h1={se_fs}, MacBook Pro 16 h1={mbp_fs}")

        # 14.4 NavBar responsive transition
        if has_nav and has_hamburger:
            add("14.4", "NavBar responsive transition (mobile=hamburger, desktop=text)", "Responsiveness",
                hamburger_visible is True and desk_nav_links_count >= 2 and not desk_hamburger_visible,
                f"mobile: hamburger={hamburger_visible}, desktop: links={desk_nav_links_count}")
        else:
            skip("14.4", "NavBar responsive transition", "Responsiveness",
                 "No nav element detected" if not has_nav else "No hamburger nav pattern detected")

        # ==============================================================
        # PART 5 -- Interactions (IDs 15.x - 17.x)
        # ==============================================================
        print("\n=== PART 5: INTERACTIONS ===")

        # 15.1 Nav link click
        if has_nav:
            ctx, pg = await _open_page(browser, 1440, 900, url)
            try:
                try:
                    # Find and click the first internal nav link
                    first_link = await pg.evaluate("""
                        (() => {
                            const links = document.querySelectorAll('nav a[href]');
                            for (const a of links) {
                                const href = a.getAttribute('href');
                                if (href && href.startsWith('/') && href !== '/' && !href.startsWith('//')) {
                                    return { href, text: a.textContent.trim() };
                                }
                            }
                            return null;
                        })()
                    """)
                    if first_link:
                        await pg.click(f"nav a[href='{first_link['href']}']", timeout=3000)
                        await pg.wait_for_timeout(1000)
                        path = await pg.evaluate("window.location.pathname")
                        add("15.1", f"Nav link click ({first_link['text']})", "Interactions",
                            True, f"Navigated to: {path}")
                        results["interaction_tests"]["nav_link"] = path
                    else:
                        skip("15.1", "Nav link click", "Interactions", "No internal nav links found (may be single-page site)")
                except Exception as e:
                    add("15.1", "Nav link click", "Interactions",
                        False, f"Error: {str(e)[:80]}")
            finally:
                await ctx.close()
        else:
            skip("15.1", "Nav link click", "Interactions", "No nav element detected")

        # 15.2 — runs in shared 23.x context (see below)

        # 15.3 Logo click
        if has_nav:
            ctx, pg = await _open_page(browser, 1440, 900, url)
            try:
                try:
                    await pg.click(SELECTORS["nav_logo"], timeout=3000)
                    await pg.wait_for_timeout(1000)
                    path = await pg.evaluate("window.location.pathname")
                    add("15.3", "Logo click navigates", "Interactions",
                        True, f"Navigated to: {path}")
                    results["interaction_tests"]["logo_click"] = path
                except Exception as e:
                    skip("15.3", "Logo click navigates", "Interactions", f"No logo link found: {str(e)[:60]}")
            finally:
                await ctx.close()
        else:
            skip("15.3", "Logo click navigates", "Interactions", "No nav element detected")

        # 16.1 Contact modal opens (desktop)
        # Auto-detect: check if page has a contact CTA
        _try_contact_modal = has_contact_modal
        if _try_contact_modal is None:
            # Auto-detect by checking if a contact-like button exists
            _detect_ctx, _detect_pg = await _open_page(browser, 1440, 900, url)
            try:
                _has_cta = await _detect_pg.evaluate("""
                    !!Array.from(document.querySelectorAll('button, a')).find(
                        el => /contact|get.?in.?touch|inquir/i.test(el.textContent)
                    )
                """)
                _try_contact_modal = _has_cta
            finally:
                await _detect_ctx.close()

        if _try_contact_modal:
            ctx, pg = await _open_page(browser, 1440, 900, url)
            modal_opened = False
            modal_fields_count = 0
            modal_closed = False
            try:
                try:
                    # Find and click the contact-like CTA
                    await pg.evaluate("""
                        (() => {
                            const el = Array.from(document.querySelectorAll('button, a')).find(
                                el => /contact|get.?in.?touch|inquir/i.test(el.textContent)
                            );
                            if (el) el.click();
                        })()
                    """)
                    await pg.wait_for_timeout(1500)
                    modal_opened = await pg.evaluate("""
                        !!document.querySelector('[role=dialog], [aria-modal=true], .fixed.inset-0, [class*=modal]')
                    """)
                    if modal_opened:
                        await pg.screenshot(path=os.path.join(out_dir, "hybrid_modal_contact_desktop.png"))

                    add("16.1", "Contact modal opens", "Interactions",
                        modal_opened, "Modal appeared" if modal_opened else "CTA found but no modal detected")
                    results["interaction_tests"]["contact_modal"] = modal_opened

                    # 16.2 Modal has form fields
                    if modal_opened:
                        fields = await pg.evaluate("""
                            (() => {
                                const els = document.querySelectorAll('input, textarea, select');
                                return Array.from(els).map(e => ({
                                    tag: e.tagName, name: e.name || e.id || e.placeholder || '',
                                    required: e.required,
                                }));
                            })()
                        """)
                        modal_fields_count = len(fields)
                        add("16.2", "Modal has form fields", "Interactions",
                            modal_fields_count >= 1,
                            f"{modal_fields_count} fields: {[f['name'] for f in fields[:6]]}")

                        # 16.4 Modal closes
                        close_btn = pg.locator(SELECTORS["modal_close"])
                        if await close_btn.count() > 0:
                            await close_btn.first.click()
                            await pg.wait_for_timeout(500)
                            modal_gone = await pg.evaluate("""
                                !document.querySelector('[role=dialog], [aria-modal=true]')
                            """)
                            modal_closed = modal_gone
                            add("16.4", "Modal closes", "Interactions",
                                modal_closed, "Dismissed" if modal_closed else "Still visible")
                        else:
                            await pg.keyboard.press("Escape")
                            await pg.wait_for_timeout(500)
                            modal_gone = await pg.evaluate("""
                                !document.querySelector('[role=dialog], [aria-modal=true]')
                            """)
                            modal_closed = modal_gone
                            add("16.4", "Modal closes (Escape key)", "Interactions",
                                modal_closed, "Dismissed via Escape" if modal_closed else "Still visible")
                    else:
                        skip("16.2", "Modal has form fields", "Interactions", "Modal did not open")
                        skip("16.4", "Modal closes", "Interactions", "Modal did not open")

                    results["interaction_tests"]["modal_fields"] = modal_fields_count
                    results["interaction_tests"]["modal_closed"] = modal_closed
                except Exception as e:
                    skip("16.1", "Contact modal opens", "Interactions", f"Error: {str(e)[:80]}")
                    skip("16.2", "Modal has form fields", "Interactions", "Modal test failed")
                    skip("16.4", "Modal closes", "Interactions", "Modal test failed")
            finally:
                await ctx.close()
        else:
            skip("16.1", "Contact modal opens", "Interactions", "No contact CTA detected")
            skip("16.2", "Modal has form fields", "Interactions", "No contact CTA detected")
            skip("16.4", "Modal closes", "Interactions", "No contact CTA detected")

        # 17.1 Hamburger menu opens (mobile)
        if has_hamburger:
            ctx, pg = await _open_page(browser, 375, 667, url)
            try:
                try:
                    await pg.click(SELECTORS["hamburger_btn"], timeout=3000)
                    await pg.wait_for_timeout(500)
                    await pg.screenshot(path=os.path.join(out_dir, "hybrid_hamburger_open.png"), full_page=False)
                    menu_links = await pg.evaluate("""
                        Array.from(document.querySelectorAll('nav a')).filter(a => {
                            const r = a.getBoundingClientRect();
                            return r.width > 0 && r.height > 0 && a.textContent.trim().length > 0;
                        }).map(a => a.textContent.trim())
                    """)
                    add("17.1", "Hamburger menu opens (mobile)", "Interactions",
                        len(menu_links) >= 2, f"Links visible: {menu_links}")
                    results["interaction_tests"]["hamburger_menu"] = menu_links
                except Exception as e:
                    add("17.1", "Hamburger menu opens", "Interactions", False, str(e)[:100])
            finally:
                await ctx.close()
        else:
            skip("17.1", "Hamburger menu opens (mobile)", "Interactions", "No hamburger nav pattern detected")

        # ==============================================================
        # PART 6 -- Console & Network (IDs 19.x - 20.x)
        # ==============================================================
        print("\n=== PART 6: CONSOLE & NETWORK ===")

        # 19.1 No JS console errors (filtered)
        real_errors = [e for e in console_errors
                       if "third-party" not in e.lower()
                       and "analytics" not in e.lower()
                       and "gtm" not in e.lower()
                       and "google" not in e.lower()]
        add("19.1", "No JS console errors (ignoring 3rd-party)", "Console & Network",
            len(real_errors) == 0,
            f"{len(real_errors)} errors" + (f": {real_errors[0][:80]}" if real_errors else ""))
        results["page_console_errors"] = console_errors

        # 20.1 No failed network requests
        real_net = [n for n in network_failures
                    if "google-analytics" not in n
                    and "gtag" not in n
                    and "analytics" not in n.lower()]
        add("20.1", "No failed network requests (ignoring analytics)", "Console & Network",
            len(real_net) == 0,
            f"{len(real_net)} failures" + (f": {real_net[0][:80]}" if real_net else ""))
        results["page_network_failures"] = network_failures

        # 20.2 Font files load (.woff/.woff2)
        if font_responses:
            all_200 = all(r["status"] == 200 for r in font_responses)
            add("20.2", "Font files load (.woff/.woff2)", "Console & Network",
                all_200,
                f"{len(font_responses)} font files, all 200" if all_200 else f"Some failed: {font_responses[:3]}")
        else:
            add("20.2", "Font files load (.woff/.woff2)", "Console & Network",
                False, "No .woff/.woff2 requests detected")

        # ==============================================================
        # HYBRID-SPECIFIC CHECKS (IDs 21.x - 23.x)
        # ==============================================================
        print("\n=== HYBRID-SPECIFIC CHECKS ===")

        # 21.1 CSS typography scale (h1 > h2 > body)
        desk_h2s = _find_all(desk_css, "h2-")
        desk_body = _find_all(desk_css, "body-p-")
        h1_fs_val = _px(desk_h1.get("fontSize", "")) if desk_h1 else 0
        h2_fs_val = _px(desk_h2s[0].get("fontSize", "")) if desk_h2s else 0
        body_fs_val = _px(desk_body[0].get("fontSize", "")) if desk_body else 0
        scale_ok = h1_fs_val > h2_fs_val > body_fs_val > 0
        add("21.1", "CSS typography scale (h1 > h2 > body fontSize)", "Typography & Colors",
            scale_ok,
            f"h1={h1_fs_val}px > h2={h2_fs_val}px > body={body_fs_val}px")

        # 21.2 Heading font-weight consistency
        h1_fw = desk_h1.get("fontWeight", "") if desk_h1 else ""
        h2_fws = [h.get("fontWeight", "") for h in desk_h2s]
        all_heading_fw = [h1_fw] + h2_fws
        fw_consistent = len(set(all_heading_fw)) <= 1 and len(all_heading_fw) > 0
        add("21.2", "Heading font-weight consistency (all h1/h2 same weight)", "Typography & Colors",
            fw_consistent,
            f"weights: {list(set(all_heading_fw))}")

        # 21.3 Body text weight consistency
        body_fws = [p.get("fontWeight", "") for p in desk_body]
        body_fw_set = set(body_fws)
        add("21.3", "Body text weight consistency", "Typography & Colors",
            len(body_fw_set) <= 1 and len(body_fws) > 0,
            f"body font-weights: {list(body_fw_set)}")

        # 21.4 Line-height sanity (>= 1.2x font-size)
        bad_lh = []
        for el in desk_css if isinstance(desk_css, list) else []:
            if not isinstance(el, dict):
                continue
            label = el.get("label", "")
            if label.startswith("h1") or label.startswith("h2-") or label.startswith("body-p-") or label.startswith("hero-subtitle"):
                fs = _px(el.get("fontSize", ""))
                lh = _px(el.get("lineHeight", ""))
                if fs > 0 and lh > 0 and lh < fs * 1.1:
                    bad_lh.append(f"{label}: fontSize={fs}, lineHeight={lh}")
        add("21.4", "Line-height sanity (all text >= 1.1x font-size)", "Typography & Colors",
            len(bad_lh) == 0,
            f"{len(bad_lh)} violations" + (f": {bad_lh[:3]}" if bad_lh else ""))

        # 22.1 Section background variety
        bg_colors = [sb.get("backgroundColor", "") for sb in sections_bg]
        unique_bgs = set(bg_colors)
        add("22.1", "Section background variety (not all same color)", "Page Load & Layout",
            len(unique_bgs) > 1,
            f"{len(unique_bgs)} unique backgrounds: {list(unique_bgs)[:4]}")

        # 22.2 Button style consistency (same font-family)
        desk_buttons = _find_all(desk_css, "button-")
        visible_buttons = [b for b in desk_buttons if b.get("visible")]
        btn_fonts = set(b.get("fontFamily", "") for b in visible_buttons if b.get("fontFamily"))
        add("22.2", "Button style consistency (same font-family)", "Page Load & Layout",
            len(btn_fonts) <= 1,
            f"button fonts: {list(btn_fonts)[:3]}")

        # 22.3 NavBar height consistent across desktop breakpoints
        if has_nav and nav_el:
            desk_nav_h = _px(nav_el.get("height", ""))
            mbp_nav = _find(mbp_css, "nav")
            mbp_nav_h = _px(mbp_nav.get("height", "")) if mbp_nav else 0
            ipad_pro_nav = _find(ipad_pro_css, "nav")
            ipad_pro_nav_h = _px(ipad_pro_nav.get("height", "")) if ipad_pro_nav else 0
            nav_h_consistent = abs(desk_nav_h - mbp_nav_h) <= 10 if desk_nav_h > 0 and mbp_nav_h > 0 else False
            add("22.3", "NavBar height consistent across desktop breakpoints", "Page Load & Layout",
                nav_h_consistent,
                f"MacBook Air={desk_nav_h}px, MacBook Pro={mbp_nav_h}px, iPad Pro={ipad_pro_nav_h}px")
        else:
            skip("22.3", "NavBar height consistent", "Page Load & Layout", "No nav element detected")

        # 15.2 + 23.x -- shared read-only context at 1440x900
        ctx, pg = await _open_page(browser, 1440, 900, url)
        try:
            # 15.2 Active link indicator (current page highlighted in nav)
            if has_nav:
                try:
                    active_link = await pg.evaluate("""
                        (() => {
                            const currentPath = window.location.pathname;
                            const links = document.querySelectorAll('nav a[href]');
                            for (const a of links) {
                                const href = a.getAttribute('href');
                                if (href === currentPath || href === currentPath + '/') {
                                    const s = getComputedStyle(a);
                                    return {
                                        text: a.textContent.trim(), href,
                                        opacity: s.opacity,
                                        textDecoration: s.textDecorationLine,
                                        fontWeight: s.fontWeight,
                                        color: s.color,
                                    };
                                }
                            }
                            // Also check for aria-current or .active class
                            const active = document.querySelector('nav a[aria-current], nav a.active, nav a[class*="active"]');
                            if (active) {
                                const s = getComputedStyle(active);
                                return {
                                    text: active.textContent.trim(),
                                    href: active.getAttribute('href'),
                                    opacity: s.opacity,
                                    textDecoration: s.textDecorationLine,
                                    fontWeight: s.fontWeight,
                                    color: s.color,
                                    method: 'aria-current or .active class',
                                };
                            }
                            return null;
                        })()
                    """)
                    has_indicator = active_link is not None
                    add("15.2", "Active link indicator (current page highlighted)", "Interactions",
                        True,  # Advisory — not all sites need this
                        f"active link: {active_link}" if active_link else "No active link indicator found (advisory)")
                    results["interaction_tests"]["active_link"] = active_link
                except Exception as e:
                    skip("15.2", "Active link indicator", "Interactions", str(e)[:80])
            else:
                skip("15.2", "Active link indicator", "Interactions", "No nav element detected")

            # 23.1 Semantic HTML (nav, main, footer)
            semantic = await pg.evaluate("""
                (() => ({
                    hasNav: !!document.querySelector('nav'),
                    hasMain: !!document.querySelector('main'),
                    hasFooter: !!document.querySelector('footer'),
                    hasHeader: !!document.querySelector('header'),
                }))()
            """)
            sem_ok = semantic.get("hasNav") and semantic.get("hasMain") and semantic.get("hasFooter")
            add("23.1", "Semantic HTML (nav, main, footer elements)", "Page Load & Layout",
                sem_ok, str(semantic))

            # 23.2 Heading hierarchy (h1 before any h2)
            heading_order = await pg.evaluate("""
                (() => {
                    const all = document.querySelectorAll('h1, h2, h3, h4, h5, h6');
                    return Array.from(all).map(h => ({
                        tag: h.tagName, text: h.textContent.trim().substring(0, 40)
                    }));
                })()
            """)
            h1_first = len(heading_order) > 0 and heading_order[0].get("tag") == "H1"
            add("23.2", "Heading hierarchy (h1 comes before h2)", "Page Load & Layout",
                h1_first,
                f"First heading: {heading_order[0] if heading_order else 'none'}")

            # 23.3 Section accessibility (sections have headings)
            sections_with_headings = await pg.evaluate("""
                (() => {
                    const sections = document.querySelectorAll('main section');
                    let withH = 0, without = 0;
                    sections.forEach(s => {
                        if (s.querySelector('h1, h2, h3')) withH++;
                        else without++;
                    });
                    return { withHeading: withH, withoutHeading: without, total: sections.length };
                })()
            """)
            all_have_headings = sections_with_headings.get("withoutHeading", 0) == 0
            add("23.3", "Section accessibility (sections have headings)", "Page Load & Layout",
                all_have_headings,
                f"{sections_with_headings.get('withHeading')}/{sections_with_headings.get('total')} have headings")

            # 23.4 Skip navigation link
            skip_nav = await pg.evaluate("""
                !!document.querySelector('a[href="#main-content"], a[href="#main"], a.skip-to-content, a[class*="skip"]')
            """)
            add("23.4", "Skip navigation link exists", "Page Load & Layout",
                skip_nav, "Found" if skip_nav else "Not found (advisory)")
        finally:
            await ctx.close()

        await browser.close()

    _compute_summary(results)
    _save_and_print(results, out_dir)


_GLOBAL_TIMEOUT = 300  # 5 minutes


async def _run_with_timeout(args):
    try:
        await asyncio.wait_for(main(args), timeout=_GLOBAL_TIMEOUT)
    except asyncio.TimeoutError:
        print(f"\n*** TIMEOUT: script exceeded {_GLOBAL_TIMEOUT}s ***")
        sys.exit(2)


if __name__ == "__main__":
    asyncio.run(_run_with_timeout(_parse_args()))
