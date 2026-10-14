"""
sharp-edge | Script 3 — Matchs du jour
Liste tous les matchs du jour avec un pari Over/Under, sa cote, sa probabilité
estimée par le marché et le taux historique sur des cotes similaires.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
NOTICE D'INTENTION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

OBJECTIF : 2 rapports quotidiens (4h30 et 16h30 heure France).

AFFICHAGE : tous les matchs du jour, sans filtre, triés par valeur.
  - Pari : Over buts, ligne simple (x.5, sans remboursement partiel). On prend
    la ligne la plus haute dont la cote est dans 1,20–1,50 ; à défaut,
    la ligne dont la cote est la plus proche de cette fenêtre (signalée).
  - Cote : celle de Betclic si disponible, sinon la moyenne des bookmakers.
  - Probabilité : estimée par le marché — pour chaque bookmaker cotant Over et
    Under sur la même ligne, (1/cote Over) / (1/cote Over + 1/cote Under),
    puis moyenne (la marge du bookmaker est ainsi retirée).
  - Historique : taux de réussite observé dans le backtest sur des cotes
    similaires (data/calibration.json).
  - Valeur : probabilité × cote − 1. Au-dessus de 0 %, la cote paie plus que
    le risque estimé par le marché ; en dessous, moins.
  - Note (étoiles) : moyenne de la valeur marché et de la valeur historique
    (taux historique × cote − 1), l'historique pesant d'autant plus que son
    échantillon est grand. Seule la note est affichée.

STRATÉGIE CRÉDITS (1 crédit = 1 marché renvoyé × 1 région) :
  - Liste des matchs du jour : endpoint /events, gratuit.
  - Lignes Over/Under de chaque match (alternate_totals, à défaut totals) :
    1 crédit par match.
  - Tout est mis en cache dans docs/picks/YYYY-MM-DD_raw.json ; le rapport du
    soir relit ce cache sans rappeler l'API (sauf REFRESH_EVENING = True).
  - Résultats de la veille : endpoint scores, 2 crédits par source concernée.
  - Estimation : ~25 matchs/jour en moyenne → ~800–1 000 crédits/mois.

SOURCES RETIRÉES VOLONTAIREMENT (réactiver en décommentant) :
  - soccer_greece_super_league  : marché peu liquide, peu de matchs en semaine
  - soccer_spl                  : Écosse Premiership — faible volume
  - soccer_italy_serie_b        : peu actif les soirs de coupe européenne

SOURCES ACTIVES : 18 championnats/compétitions (Phase 1 — football uniquement)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import os
import json
import requests
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from pathlib import Path

# ── CONFIG ────────────────────────────────────────────────────────────────────
API_KEY      = os.environ.get("ODDS_API_KEY", "")
BASE_URL     = "https://api.the-odds-api.com/v4"
REPORT_TYPE  = os.environ.get("REPORT_TYPE", "morning")  # morning | evening

# Plan payant : mettre True pour rafraîchir les cotes à 16h30
REFRESH_EVENING = False

TZ_FRANCE = ZoneInfo("Europe/Paris")  # gère automatiquement heure été / hiver
SPORT_LABEL = "⚽ Football"

# ── SOURCES ACTIVES ───────────────────────────────────────────────────────────
SPORTS = [
    "soccer_epl",                            # Premier League (Angleterre)
    "soccer_efl_champ",                      # Championship (Angleterre)
    "soccer_england_league1",                # League One (Angleterre)
    "soccer_england_league2",                # League Two (Angleterre)
    "soccer_france_ligue_one",               # Ligue 1 (France)
    "soccer_france_ligue_two",               # Ligue 2 (France)
    "soccer_germany_bundesliga",             # Bundesliga (Allemagne)
    "soccer_germany_bundesliga2",            # 2. Bundesliga (Allemagne)
    "soccer_italy_serie_a",                  # Serie A (Italie)
    "soccer_spain_la_liga",                  # LaLiga (Espagne)
    "soccer_spain_segunda_division",         # Liga 2 (Espagne)
    "soccer_netherlands_eredivisie",         # Eredivisie (Pays-Bas)
    "soccer_belgium_first_div",              # Pro League (Belgique)
    "soccer_portugal_primeira_liga",         # Liga Portugal (Portugal)
    "soccer_turkey_super_league",            # Super Lig (Turquie)
    "soccer_uefa_champs_league",             # UEFA Champions League
    "soccer_uefa_europa_league",             # UEFA Europa League
    "soccer_uefa_europa_conference_league",  # UEFA Conference League
    # ── DÉSACTIVÉES — décommenter pour réactiver ──
    # "soccer_greece_super_league",          # Super League Grèce
    # "soccer_spl",                          # Premiership Écosse
    # "soccer_italy_serie_b",                # Serie B Italie
]

# ── CHOIX DE LA LIGNE ─────────────────────────────────────────────────────────
PREFERRED_BOOKMAKER = ("betclic_fr", "Betclic")  # sinon : moyenne des bookmakers
MIN_ODDS = 1.20
MAX_ODDS = 1.50

PICKS_DIR = Path(__file__).parent.parent / "docs" / "picks"
PICKS_DIR.mkdir(parents=True, exist_ok=True)

# ── HISTORIQUE (backtest) ─────────────────────────────────────────────────────
CALIBRATION_PATH = Path(__file__).parent.parent / "data" / "calibration.json"
MIN_HISTORY_N = 30  # en dessous, l'échantillon est trop petit pour être affiché


def load_buckets() -> list:
    try:
        with open(CALIBRATION_PATH, encoding="utf-8") as f:
            cal = json.load(f)
        buckets = cal["buckets"]
        print(f"  Historique : backtest du {cal['generated_at']} "
              f"({cal['seasons'][0]} → {cal['seasons'][-1]})")
        return buckets
    except (OSError, KeyError, IndexError, ValueError) as e:
        print(f"  Historique indisponible ({e})")
        return []


BUCKETS = load_buckets()


def history_stats(odds: float) -> tuple:
    """(taux de réussite %, effectif) de la tranche de cote, ou (None, 0)."""
    for b in BUCKETS:
        if b["min"] <= odds < b["max"] and b["n"] and b["win_rate"] is not None:
            return b["win_rate"], b["n"]
    return None, 0


def history_for(odds: float) -> str:
    rate, n = history_stats(odds)
    return f"{rate:.0f}% (n={n})" if rate is not None and n >= MIN_HISTORY_N else "—"


# ── NOTE EN ÉTOILES ───────────────────────────────────────────────────────────
# Poids de l'historique = n / (n + HISTORY_PRIOR_N) : 40 matchs → 12 %, 700 → 70 %
HISTORY_PRIOR_N = 300
STARS = [  # (score minimum en %, étoiles, libellé)
    (2.0,   5, "Excellent"),
    (0.0,   4, "Intéressant"),
    (-2.0,  3, "Correct"),
    (-5.0,  2, "Faible"),
    (-1e9,  1, "À éviter"),
]


def rating(proba: float | None, odds: float) -> dict:
    # Score = moyenne pondérée de la valeur marché et de la valeur historique
    market = None if proba is None else (proba / 100 * odds - 1) * 100
    rate, n = history_stats(odds)
    hist = None if rate is None else (rate / 100 * odds - 1) * 100
    if market is None and hist is None:
        return {"score": None, "etoiles": None, "note": None}
    if market is None:
        score = hist
    elif hist is None:
        score = market
    else:
        w = n / (n + HISTORY_PRIOR_N)
        score = w * hist + (1 - w) * market
    stars, label = next((s, l) for threshold, s, l in STARS if score >= threshold)
    return {"score": round(score, 1), "etoiles": stars, "note": label}


# ── UTILITAIRES ───────────────────────────────────────────────────────────────
def today_fr() -> str:
    return datetime.now(TZ_FRANCE).strftime("%Y-%m-%d")

def yesterday_fr() -> str:
    return (datetime.now(TZ_FRANCE) - timedelta(days=1)).strftime("%Y-%m-%d")

def raw_cache_path() -> Path:
    return PICKS_DIR / f"{today_fr()}_raw.json"

def kickoff_fr(event: dict) -> datetime:
    return datetime.fromisoformat(event["commence_time"].replace("Z", "+00:00")).astimezone(TZ_FRANCE)

def in_window(price: float) -> bool:
    return MIN_ODDS <= price <= MAX_ODDS

def today_bounds_utc() -> tuple:
    """Début et fin de la journée de Paris, en UTC, au format attendu par l'API."""
    start = datetime.now(TZ_FRANCE).replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    return start.astimezone(timezone.utc).strftime(fmt), end.astimezone(timezone.utc).strftime(fmt)


# ── APPELS API ────────────────────────────────────────────────────────────────
def api_get(path: str, params: dict):
    if not API_KEY:
        return None
    try:
        r = requests.get(f"{BASE_URL}{path}", timeout=15,
                         params={"apiKey": API_KEY, "dateFormat": "iso", **params})
        if r.status_code == 200:
            return r.json()
        print(f"  API {path}: HTTP {r.status_code} {r.text[:120]}")
    except Exception as e:
        print(f"  Erreur {path}: {e}")
    return None


def fetch_today_events(sport_key: str) -> list:
    """Matchs du jour (heure de Paris) — endpoint gratuit, sans cotes."""
    start, end = today_bounds_utc()
    return api_get(f"/sports/{sport_key}/events",
                   {"commenceTimeFrom": start, "commenceTimeTo": end}) or []


def fetch_totals(sport_key: str, event_id: str) -> dict:
    """Toutes les lignes Over/Under d'un match — 1 crédit (rien si vide)."""
    path = f"/sports/{sport_key}/events/{event_id}/odds"
    base = {"regions": "eu", "oddsFormat": "decimal"}
    data = api_get(path, {**base, "markets": "alternate_totals"}) or {}
    if not data.get("bookmakers"):  # pas de lignes alternatives : lignes standard
        data = api_get(path, {**base, "markets": "totals"}) or {}
    return data


# ── LECTURE DES COTES ─────────────────────────────────────────────────────────
def ref_prices(data: dict, name: str) -> dict:
    """{ligne: (cote, source)} pour 'Over' ou 'Under' : cote Betclic si elle
    existe pour cette ligne, sinon moyenne des bookmakers."""
    by_line = {}  # ligne -> {clé bookmaker: cote}
    for bk in data.get("bookmakers", []):
        for m in bk.get("markets", []):
            if m["key"] not in ("totals", "alternate_totals"):
                continue
            for o in m.get("outcomes", []):
                if o.get("name") == name and "point" in o:
                    by_line.setdefault(float(o["point"]), {})[bk["key"]] = o["price"]
    pref_key, pref_label = PREFERRED_BOOKMAKER
    out = {}
    for pt, prices in by_line.items():
        if pref_key in prices:
            out[pt] = (prices[pref_key], pref_label)
        else:
            out[pt] = (round(sum(prices.values()) / len(prices), 2),
                       f"moyenne de {len(prices)} bookmaker{'s' if len(prices) > 1 else ''}")
    return out


def fair_prob(data: dict, line: float) -> tuple:
    """Probabilité de l'Over sur `line`, marge retirée, moyenne des bookmakers.
    Retourne (probabilité en %, nombre de bookmakers)."""
    probs = []
    for bk in data.get("bookmakers", []):
        prices = {}
        for m in bk.get("markets", []):
            if m["key"] not in ("totals", "alternate_totals"):
                continue
            for o in m.get("outcomes", []):
                if o.get("point") is not None and float(o["point"]) == line:
                    prices[o["name"]] = o["price"]
        if "Over" in prices and "Under" in prices:
            inv_o, inv_u = 1 / prices["Over"], 1 / prices["Under"]
            probs.append(inv_o / (inv_o + inv_u))
    if not probs:
        return None, 0
    return round(sum(probs) / len(probs) * 100, 1), len(probs)


def choose_bet(data: dict) -> dict | None:
    """Over ligne simple (x.5) : la plus haute dans la fenêtre 1,20–1,50,
    sinon celle dont la cote est la plus proche de la fenêtre."""
    lines = [(pt, p, b) for pt, (p, b) in ref_prices(data, "Over").items() if pt % 1 == 0.5]
    if not lines:
        return None
    inside = [l for l in lines if in_window(l[1])]
    if inside:
        pt, price, book = max(inside)
    else:
        pt, price, book = min(lines, key=lambda l: min(abs(l[1] - MIN_ODDS), abs(l[1] - MAX_ODDS)))
    proba, n = fair_prob(data, pt)
    return {"line": pt, "cote": price, "source": book, "in_window": bool(inside),
            "proba": proba, "proba_books": n}


# ── COLLECTE (matin) / CACHE (soir) ───────────────────────────────────────────
def fetch_all() -> dict:
    events, odds = [], {}
    for sport in SPORTS:
        evs = fetch_today_events(sport)
        for e in evs:
            odds[e["id"]] = fetch_totals(sport, e["id"])
        events.extend(evs)
        print(f"  {sport}: {len(evs)} matchs aujourd'hui")
    return {"events": events, "odds": odds}


def load_or_fetch_raw() -> dict:
    """
    Matin  : appelle l'API et met en cache.
    Soir   : relit le cache (sauf si REFRESH_EVENING = True).
    """
    cache = raw_cache_path()
    if REPORT_TYPE == "evening" and not REFRESH_EVENING and cache.exists():
        with open(cache, encoding="utf-8") as f:
            raw = json.load(f)
        if isinstance(raw, dict) and "odds" in raw:
            print("  → Cache du matin utilisé (REFRESH_EVENING=False)")
            return raw
    print(f"  → Appel API ({REPORT_TYPE})")
    raw = fetch_all()
    with open(cache, "w", encoding="utf-8") as f:
        json.dump(raw, f, ensure_ascii=False)
    return raw


# ── CONSTRUCTION DES MATCHS ───────────────────────────────────────────────────
def build_pick(event: dict, data: dict) -> dict | None:
    kickoff = kickoff_fr(event)
    if kickoff.strftime("%Y-%m-%d") != today_fr():
        return None
    if REPORT_TYPE == "morning" and kickoff.hour >= 18:
        label = "🟡 À confirmer à 16h30"
    elif REPORT_TYPE == "evening" and kickoff.hour < 18:
        return None  # déjà couvert par le rapport du matin
    else:
        label = "🟢 Bon"

    bet = choose_bet(data)
    pick = {
        "sport": SPORT_LABEL, "status": label, "heure": kickoff.strftime("%Hh%M"),
        "championnat": event.get("sport_title", ""), "sport_key": event.get("sport_key", ""),
        "home_team": event["home_team"], "away_team": event["away_team"],
        "event_id": event.get("id", ""),
        "pari": None, "cote": None, "proba": None, "historique": "—", "valeur": None,
        "score": None, "etoiles": None, "note": None,
    }
    if bet:
        pick.update({
            "pari": f"Over {bet['line']:g} buts", "over_line": bet["line"],
            "cote": bet["cote"], "cote_source": bet["source"],
            "dans_fenetre": bet["in_window"],
            "proba": bet["proba"], "proba_books": bet["proba_books"],
            "historique": history_for(bet["cote"]),
            "valeur": (None if bet["proba"] is None
                       else round((bet["proba"] / 100 * bet["cote"] - 1) * 100, 1)),
            **rating(bet["proba"], bet["cote"]),
        })
    return pick


# ── RÉSULTATS DE LA VEILLE ────────────────────────────────────────────────────
def load_yesterday_picks() -> list:
    """Matchs de la veille, un par match (la version du soir remplace celle du matin)."""
    by_event = {}
    for suffix in ["morning", "evening"]:
        path = PICKS_DIR / f"{yesterday_fr()}_{suffix}.json"
        if path.exists():
            with open(path, encoding="utf-8") as f:
                for p in json.load(f).get("picks", []):
                    if p.get("pari"):
                        by_event[p.get("event_id") or id(p)] = p
    return list(by_event.values())


def fetch_scores(sport_key: str) -> list:
    return api_get(f"/sports/{sport_key}/scores", {"daysFrom": 2}) or []


def settle(pick: dict, hs: int, as_: int) -> str:
    if "over_line" in pick:
        return "win" if hs + as_ > pick["over_line"] else "loss"
    # anciens picks « Victoire favori »
    fav_won = (hs > as_) if pick.get("camp", "Domicile") == "Domicile" else (as_ > hs)
    return "win" if fav_won else "loss"


def resolve_yesterday(picks: list) -> list:
    if not picks:
        return []
    sports_needed = {p.get("sport_key") for p in picks} - {None, ""}
    scores_by_id, scores_by_teams = {}, {}
    for sk in sports_needed:
        for s in fetch_scores(sk):
            if s.get("completed"):
                scores_by_id[s["id"]] = s
                scores_by_teams[(s["home_team"], s["away_team"])] = s

    resolved = []
    for pick in picks:
        data = (scores_by_id.get(pick.get("event_id", "")) or
                scores_by_teams.get((pick.get("home_team", ""), pick.get("away_team", ""))))
        sc = {s["name"]: int(s["score"]) for s in (data or {}).get("scores") or []}
        hs, as_ = sc.get(pick.get("home_team")), sc.get(pick.get("away_team"))
        if not data or hs is None or as_ is None:
            pick["result"] = "unknown"
            pick["result_label"] = "⏳ Résultat non disponible"
        else:
            score_str = f"{hs}–{as_}"
            pick["result"] = settle(pick, hs, as_)
            pick["result_label"] = (f"✅ Validé ({score_str})" if pick["result"] == "win"
                                    else f"❌ Raté ({score_str})")
        resolved.append(pick)
    return resolved


# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    print(f"Sharp-Edge | {today_fr()} | Rapport : {REPORT_TYPE}")

    raw = load_or_fetch_raw()
    odds = raw.get("odds", {})
    picks = [p for e in raw.get("events", [])
             if (p := build_pick(e, odds.get(e.get("id"), {})))]
    # meilleure note d'abord (score), puis probabilité ; matchs sans cotes à la fin
    picks.sort(key=lambda x: (x["score"] is None, -(x["score"] or 0), -(x["proba"] or 0)))

    yesterday_resolved = resolve_yesterday(load_yesterday_picks())
    wins   = sum(1 for p in yesterday_resolved if p.get("result") == "win")
    losses = sum(1 for p in yesterday_resolved if p.get("result") == "loss")
    total  = wins + losses

    suffix = "morning" if REPORT_TYPE == "morning" else "evening"
    out = PICKS_DIR / f"{today_fr()}_{suffix}.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump({
            "date": today_fr(), "type": REPORT_TYPE, "picks": picks,
            "yesterday": {
                "date": yesterday_fr(), "resolved": yesterday_resolved,
                "wins": wins, "losses": losses, "total": total,
                "win_rate": round(wins / total * 100, 1) if total else None,
            },
        }, f, ensure_ascii=False, indent=2)

    print(f"\n✓ {len(picks)} matchs → {out}")
    print(f"  Veille : {wins}W / {losses}L sur {total} résolus")
    for p in picks:
        print(f"  {p['status']} | {p['heure']} | {p['championnat']} | {p['home_team']} – "
              f"{p['away_team']} | {p['pari'] or 'cotes indisponibles'} @ {p['cote']} | "
              f"{p['proba']}% | hist. {p['historique']} | valeur {p['valeur']}% | "
              f"{p['etoiles']}★ {p['note']} (score {p['score']})")


if __name__ == "__main__":
    main()
