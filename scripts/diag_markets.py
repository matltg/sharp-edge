"""
sharp-edge | Diagnostic ponctuel — couverture Over/Under et handicap asiatique
Mesure ce que The Odds API renvoie pour le football (région eu) avant de coder
la logique de la notice. Coût : ~10 crédits. Résultat : docs/diagnostic/markets.json
"""

import json
import os
from collections import Counter, defaultdict
from pathlib import Path

import requests

API_KEY  = os.environ["ODDS_API_KEY"]
BASE_URL = "https://api.the-odds-api.com/v4"
SPORTS   = ["soccer_epl", "soccer_france_ligue_one", "soccer_germany_bundesliga"]
OUT      = Path(__file__).parent.parent / "docs" / "diagnostic" / "markets.json"


def summarize(events: list) -> dict:
    books = Counter()
    lines = defaultdict(Counter)  # market -> Counter(point)
    for ev in events:
        for bk in ev.get("bookmakers", []):
            for m in bk.get("markets", []):
                books[(m["key"], bk["key"])] += 1
                for o in m.get("outcomes", []):
                    if "point" in o:
                        lines[m["key"]][str(o["point"])] += 1
    return {
        "events": len(events),
        "events_with_markets": sum(1 for e in events if e.get("bookmakers")),
        "bookmakers_per_market": {f"{k}|{b}": n for (k, b), n in books.most_common(40)},
        "lines": {k: dict(v.most_common(20)) for k, v in lines.items()},
        "sample": events[:1],
    }


def main():
    report = {"featured": {}, "event_level": {}, "credits": {}}

    # 1. Marchés principaux, par championnat (2 crédits/appel)
    first_event = None
    for sport in SPORTS:
        r = requests.get(f"{BASE_URL}/sports/{sport}/odds", timeout=20, params={
            "apiKey": API_KEY, "regions": "eu", "markets": "totals,spreads",
            "oddsFormat": "decimal", "dateFormat": "iso"})
        report["credits"][sport] = {h: r.headers.get(h) for h in
                                    ("x-requests-used", "x-requests-remaining", "x-requests-last")}
        events = r.json() if r.status_code == 200 else []
        report["featured"][sport] = {"http": r.status_code, **summarize(events)}
        if first_event is None and events:
            first_event = (sport, events[0]["id"])
        print(sport, r.status_code, len(events), "events")

    # 2. Lignes alternatives, sur un seul match (coût = marchés renvoyés)
    if first_event:
        sport, eid = first_event
        r = requests.get(f"{BASE_URL}/sports/{sport}/events/{eid}/odds", timeout=20, params={
            "apiKey": API_KEY, "regions": "eu",
            "markets": "alternate_totals,alternate_spreads",
            "oddsFormat": "decimal", "dateFormat": "iso"})
        report["credits"]["event_level"] = {h: r.headers.get(h) for h in
                                            ("x-requests-used", "x-requests-remaining", "x-requests-last")}
        data = r.json() if r.status_code == 200 else {}
        report["event_level"] = {"http": r.status_code, "sport": sport,
                                 **summarize([data] if data else [])}
        print("event-level", r.status_code)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"✓ {OUT}")


if __name__ == "__main__":
    main()
