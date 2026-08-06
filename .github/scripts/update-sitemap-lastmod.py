#!/usr/bin/env python3
"""Aktualisiert <lastmod> in sitemap.xml.

Fuer jede URL in der Sitemap wird das Datum des letzten Commits gesetzt,
der die zugehoerige Quelldatei geaendert hat. Neue Seiten einfach unten in
PAGES ergaenzen (URL aus <loc> -> Pfad der Quelldatei im Repo).

Das Skript veraendert die Datei nur, wenn sich wirklich ein Datum aendert,
und prueft das Ergebnis anschliessend auf XML-Wohlgeformtheit.
"""

from __future__ import annotations

import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

# <loc> der Sitemap  ->  Quelldatei, deren Aenderungsdatum gilt
PAGES: dict[str, str] = {
    "https://sib.io/": "index.html",
}

SITEMAP = Path("sitemap.xml")


def last_commit_date(path: str) -> str:
    """Datum des letzten Commits fuer `path` als YYYY-MM-DD."""
    result = subprocess.run(
        ["git", "log", "-1", "--format=%cs", "--", path],
        capture_output=True,
        text=True,
        check=True,
    )
    date = result.stdout.strip()
    if not date:
        # Datei noch nie committet (z. B. lokaler Testlauf) -> heutiges Datum
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return date


def update_url_block(block: str, seen: set[str]) -> str:
    """Setzt <lastmod> innerhalb eines einzelnen <url>-Blocks."""
    loc_match = re.search(r"<loc>\s*(.*?)\s*</loc>", block, re.DOTALL)
    if not loc_match:
        return block

    loc = loc_match.group(1)
    source = PAGES.get(loc)
    if source is None:
        print(f"  ! {loc}: keine Quelldatei in PAGES hinterlegt - uebersprungen")
        return block
    if not Path(source).exists():
        print(f"  ! {loc}: Quelldatei '{source}' fehlt - uebersprungen")
        return block

    seen.add(loc)
    date = last_commit_date(source)

    if re.search(r"<lastmod>.*?</lastmod>", block, re.DOTALL):
        new_block = re.sub(
            r"<lastmod>.*?</lastmod>",
            f"<lastmod>{date}</lastmod>",
            block,
            count=1,
            flags=re.DOTALL,
        )
    else:
        # Kein <lastmod> vorhanden -> direkt hinter </loc> einfuegen
        new_block = block.replace("</loc>", f"</loc>\n    <lastmod>{date}</lastmod>", 1)

    print(f"  - {loc} -> {date} ({source})")
    return new_block


def main() -> int:
    if not SITEMAP.exists():
        print(f"FEHLER: {SITEMAP} nicht gefunden.", file=sys.stderr)
        return 1

    original = SITEMAP.read_text(encoding="utf-8")

    print("lastmod-Daten:")
    seen: set[str] = set()
    updated = re.sub(
        r"<url>.*?</url>",
        lambda m: update_url_block(m.group(0), seen),
        original,
        flags=re.DOTALL,
    )

    for loc in PAGES:
        if loc not in seen:
            print(f"  ! {loc} steht in PAGES, fehlt aber in {SITEMAP}")

    # Ergebnis muss gueltiges XML bleiben
    try:
        ET.fromstring(updated)
    except ET.ParseError as exc:
        print(f"FEHLER: Ergebnis waere kein gueltiges XML ({exc}).", file=sys.stderr)
        return 1

    if updated == original:
        print("sitemap.xml ist bereits aktuell.")
        return 0

    SITEMAP.write_text(updated, encoding="utf-8")
    print("sitemap.xml aktualisiert.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
