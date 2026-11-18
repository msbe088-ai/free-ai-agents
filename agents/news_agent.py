"""News agent: Yahoo Finance RSS headlines (free, keyless)."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

from .common import UA_BROWSER, UA_DEFAULT, http_get, iso, riyadh_label, ok, fail

SOURCE = "Yahoo Finance RSS"
URL = "https://feeds.finance.yahoo.com/rss/2.0/headline"


def fetch(yahoo_symbol: str, limit: int = 10) -> dict:
    try:
        r, last = None, None
        for ua in (UA_DEFAULT, "Mozilla/5.0", UA_BROWSER):  # Yahoo throttles some UAs
            try:
                r = http_get(URL, params={"s": yahoo_symbol, "region": "US", "lang": "en-US"},
                             headers={"User-Agent": ua}, retries=2)
                break
            except Exception as e:  # noqa: BLE001
                last = e
        if r is None:
            raise RuntimeError(last)
        root = ET.fromstring(r.content)
        items = []
        for it in root.iter("item"):
            title = (it.findtext("title") or "").strip()
            if not title:
                continue
            pub = it.findtext("pubDate")
            dt = None
            if pub:
                try:
                    dt = parsedate_to_datetime(pub)
                except (TypeError, ValueError):
                    dt = None
            items.append({"title": title, "link": (it.findtext("link") or "").strip(),
                          "published": iso(dt), "published_label": riyadh_label(dt)})
        items.sort(key=lambda x: x["published"] or "", reverse=True)
        items = items[:limit]
        if not items:
            raise RuntimeError("RSS returned no headlines")
        newest = max((x["published"] for x in items if x["published"]), default=None)
        from datetime import datetime
        nd = datetime.fromisoformat(newest) if newest else None
        return ok({"items": items, "count": len(items)}, SOURCE, nd)
    except Exception as e:  # noqa: BLE001
        return fail(SOURCE, e)
