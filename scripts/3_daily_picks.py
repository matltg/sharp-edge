"""
sharp-edge | Script 3 — Picks du jour
Récupère les matchs via The Odds API et applique les filtres de validation.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
NOTICE D'INTENTION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

OBJECTIF : 2 rapports quotidiens (4h30 et 16h30 heure France).

PARIS (notice Phase 1 football) :
  - Sélection : favori à domicile, repéré par le handicap asiatique médian des
    bookmakers (domicile rend au moins HOME_FAV_MAX_LINE but).
  - Pari principal : Over buts, ligne simple (x.5, sans remboursement partiel).
    On prend la ligne la plus haute dont la meilleure cote est dans 1,20–1,50.
    Pas de ligne dans la fenêtre → pas de pick.
  - Pari de secours (toujours affiché) : handicap asiatique ligne entière
    (0, -1, -2…) pour l'équipe à domicile, même règle de fenêtre ; à défaut,
    la ligne entière la plus proche, signalée hors fenêtre.
  - Tri : du plus solide au moins fort — proxy Phase 1 : cote croissante.

STRATÉGIE CRÉDITS (1 crédit = 1 marché × 1 région) :
  - Matin : handicap asiatique (spreads) pour les 18 sources = 18 crédits,
    puis lignes alternatives (alternate_totals + alternate_spreads) pour les
    seuls favoris à domicile du jour = ~2 crédits/match.
  - Tout est mis en cache dans docs/picks/YYYY-MM-DD_raw.json ; le rapport du
    soir relit ce cache sans rappeler l'API (sauf REFRESH_EVENING = True).
  - Résultats de la veille : endpoint scores, 2 crédits par source concernée.
  - Estimation : ~700–750 crédits/mois → au-delà du plan gratuit (500).

PASSAGE AU PLAN PAYANT :
  Activer REFRESH_EVENING = True ci-dessous pour rafraîchir les cotes à 16h30.

SOURCES RETIRÉES VOLONTAIREMENT (réactiver en décommentant) :
  - soccer_greece_super_league  : marché peu liquide, peu de matchs en semaine
  - soccer_spl                  : Écosse Premiership — faible volume
  - soccer_italy_serie_b        : peu actif les soirs de coupe européenne
  Ces 3 sources peuvent aussi être réactivées lors du passage au plan payant.

SOURCES ACTIVES : 18 championnats/compétitions (Phase 1 — football uniquement)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import os
import json
import statistics
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path

# ── CONFIG ────────────────────────────────────────────────────────────────────
API_KEY      = os.environ.get("ODDS_API_KEY", "")
BASE_URL     = "https://api.the-odds-api.com/v4"
REPORT_TYPE  = os.environ.get("REPORT_TYPE", "morning")  # morning | evening

# Plan payant : mettre True pour rafraîchir les cotes à 16h30
REFRESH_EVENING = False  # ← passer à True lors du passage au plan payant

TZ_FRANCE = ZoneInfo("Europe/Paris")  # gère automatiquement heure été / hiver

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
    # ── DÉSACTIVÉES — décommenter pour réactiver (plan payant recommandé) ──
    # "soccer_greece_super_league",          # Super League Grèce
    # "soccer_spl",                          # Premiership Écosse
    # "soccer_italy_serie_b",                # Serie B Italie
]

# ── FILTRES ───────────────────────────────────────────────────────────────────
MIN_ODDS  = 1.20
MAX_ODDS  = 1.50
HOME_ONLY = True  # notice Phase 1 : domicile uniquement (ne pas modifier avant 200 paris loggés)
# Favori à domicile = handicap asiatique médian du domicile ≤ cette ligne.
# -0.75 correspond à peu près à une cote 1X2 domicile ≤ 1,55.
HOME_FAV_MAX_LINE = -0.75

PICKS_DIR = Path(__file__).parent.parent / "docs" / "picks"
PICKS_DIR.mkdir(parents=True, exist_ok=True)

# ── PALIERS DE FIABILITÉ ──────────────────────────────────────────────────────
# Les taux affichés viennent de data/calibration.json (généré chaque semaine par
# 2_backtest.py, sur l'Over 2.5 — seule ligne disponible dans l'historique).
# Valeurs ci-dessous utilisées seulement si le fichier manque.
CALIBRATION_PATH = Path(__file__).parent.parent / "data" / "calibration.json"
DEFAULT_TIERS = [
    (1.25, "★★★★★ Très solide",  "—"),
    (1.30, "★★★★☆ Solide",       "—"),
    (1.40, "★★★☆☆ Correct",      "—"),
    (1.50, "★★☆☆☆ À surveiller", "—"),
]


def load_tiers() -> list:
    """Retourne [(cote_max, label, pct_affiché), ...] trié par cote."""
    try:
        with open(CALIBRATION_PATH, encoding="utf-8") as f:
            cal = json.load(f)
        key = "home" if HOME_ONLY else "all"
        tiers = []
        for t in cal["tiers"]:
            s = t[key]
            pct = f"{s['win_rate']}% (n={s['n']})" if s["n"] else "—"
            tiers.append((t["max"], t["label"], pct))
        source = f"backtest du {cal['generated_at']} ({cal['seasons'][0]} → {cal['seasons'][-1]})"
    except (OSError, KeyError, IndexError, ValueError) as e:
        print(f"  Calibration absente ou invalide ({e}) — valeurs par défaut")
        return DEFAULT_TIERS
    print(f"  Calibration : {source}")
    return sorted(tiers)


TIERS = load_tiers()


def tier_for(odds: float) -> tuple:
    for max_odds, label, pct in TIERS:
        if odds <= max_odds:
            return label, pct
    return TIERS[-1][1], TIERS[-1][2]


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

def fmt_line(point: float) -> str:
    return f"{point:+g}" if point else "0"


# ── APPELS API ────────────────────────────────────────────────────────────────
def api_get(path: str, params: dict):
    if not API_KEY:
        return None
    try:
        r = requests.get(f"{BASE_URL}{path}", timeout=15,
                         params={"apiKey": API_KEY, "regions": "eu",
                                 "oddsFormat": "decimal", "dateFormat": "iso", **params})
        if r.status_code == 200:
            return r.json()
        print(f"  API {path}: HTTP {r.status_code} {r.text[:120]}")
    except Exception as e:
        print(f"  Erreur {path}: {e}")
    return None


def fetch_spreads(sport_key: str) -> list:
    """Handicap asiatique (ligne principale) de tous les matchs à venir — 1 crédit."""
    return api_get(f"/sports/{sport_key}/odds", {"markets": "spreads"}) or []


def fetch_alternates(sport_key: str, event_id: str) -> dict:
    """Toutes les lignes Over/Under et handicap d'un match — ~2 crédits."""
    return api_get(f"/sports/{sport_key}/events/{event_id}/odds",
                   {"markets": "alternate_totals,alternate_spreads"}) or {}


# ── LECTURE DES COTES ─────────────────────────────────────────────────────────
def home_lines(event: dict, market_keys: tuple) -> dict:
    """{ligne handicap domicile: (meilleure cote, bookmaker)}"""
    best = {}
    for bk in event.get("bookmakers", []):
        for m in bk.get("markets", []):
            if m["key"] not in market_keys:
                continue
            for o in m.get("outcomes", []):
                if o.get("name") != event["home_team"] or "point" not in o:
                    continue
                pt = float(o["point"]) + 0.0  # normalise -0.0
                if pt not in best or o["price"] > best[pt][0]:
                    best[pt] = (o["price"], bk["title"])
    return best


def consensus_home_line(event: dict) -> float | None:
    """Ligne handicap principale médiane donnée au domicile par les bookmakers."""
    pts = []
    for bk in event.get("bookmakers", []):
        for m in bk.get("markets", []):
            if m["key"] != "spreads":
                continue
            for o in m.get("outcomes", []):
                if o.get("name") == event["home_team"] and "point" in o:
                    pts.append(float(o["point"]))
    return statistics.median(pts) if pts else None


def over_lines(event: dict) -> dict:
    """{ligne Over: (meilleure cote, bookmaker)}"""
    best = {}
    for bk in event.get("bookmakers", []):
        for m in bk.get("markets", []):
            if m["key"] not in ("totals", "alternate_totals"):
                continue
            for o in m.get("outcomes", []):
                if o.get("name") != "Over" or "point" not in o:
                    continue
                pt = float(o["point"])
                if pt not in best or o["price"] > best[pt][0]:
                    best[pt] = (o["price"], bk["title"])
    return best


def choose_over(alt: dict) -> dict | None:
    """Ligne simple (x.5) la plus haute dont la meilleure cote est dans la fenêtre."""
    ok = [(pt, p, b) for pt, (p, b) in over_lines(alt).items()
          if pt % 1 == 0.5 and in_window(p)]
    if not ok:
        return None
    pt, price, book = max(ok)
    return {"line": pt, "cote": price, "bookmaker": book}


def choose_handicap(event: dict, alt: dict) -> dict | None:
    """Ligne entière (0, -1, -2…) pour le domicile : la plus forte dans la fenêtre,
    sinon la plus proche de la fenêtre (signalée hors fenêtre)."""
    lines = home_lines(event, ("spreads",))
    lines.update({pt: v for pt, v in home_lines(alt, ("spreads", "alternate_spreads")).items()
                  if pt not in lines or v[0] > lines[pt][0]})
    whole = [(pt, p, b) for pt, (p, b) in lines.items() if pt % 1 == 0 and pt <= 0]
    if not whole:
        return None
    inside = [w for w in whole if in_window(w[1])]
    if inside:
        pt, price, book = min(inside)  # handicap le plus fort
        return {"line": pt, "cote": price, "bookmaker": book, "in_window": True}
    pt, price, book = min(whole, key=lambda w: min(abs(w[1] - MIN_ODDS), abs(w[1] - MAX_ODDS)))
    return {"line": pt, "cote": price, "bookmaker": book, "in_window": False}


# ── COLLECTE (matin) / CACHE (soir) ───────────────────────────────────────────
def is_today_candidate(event: dict) -> bool:
    if kickoff_fr(event).strftime("%Y-%m-%d") != today_fr():
        return False
    line = consensus_home_line(event)
    return line is not None and line <= HOME_FAV_MAX_LINE


def fetch_all() -> dict:
    events, alternates = [], {}
    for sport in SPORTS:
        evs = fetch_spreads(sport)
        events.extend(evs)
        cands = [e for e in evs if is_today_candidate(e)]
        for e in cands:
            alternates[e["id"]] = fetch_alternates(sport, e["id"])
        print(f"  {sport}: {len(evs)} matchs, {len(cands)} favoris domicile aujourd'hui")
    return {"events": events, "alternates": alternates}


def load_or_fetch_raw() -> dict:
    """
    Matin  : appelle l'API et met en cache.
    Soir   : relit le cache (sauf si REFRESH_EVENING = True).
    """
    cache = raw_cache_path()
    if REPORT_TYPE == "evening" and not REFRESH_EVENING and cache.exists():
        with open(cache, encoding="utf-8") as f:
            raw = json.load(f)
        if isinstance(raw, dict) and "alternates" in raw:
            print("  → Cache du matin utilisé (REFRESH_EVENING=False)")
            return raw
    print(f"  → Appel API ({REPORT_TYPE})")
    raw = fetch_all()
    with open(cache, "w", encoding="utf-8") as f:
        json.dump(raw, f, ensure_ascii=False)
    return raw


# ── CONSTRUCTION DES PICKS ────────────────────────────────────────────────────
def build_pick(event: dict, alt: dict) -> dict | None:
    if not is_today_candidate(event):
        return None
    hour = kickoff_fr(event).hour
    if REPORT_TYPE == "morning" and hour >= 18:
        label = "🟡 À confirmer à 16h30"
    elif REPORT_TYPE == "evening" and hour < 18:
        return None  # déjà couvert par le rapport du matin
    else:
        label = "🟢 Jouer maintenant"

    main = choose_over(alt)
    if main is None:
        return None  # filtre sur le pari lui-même : pas d'Over dans la fenêtre
    backup = choose_handicap(event, alt)
    home, away = event["home_team"], event["away_team"]
    fiab, pct = tier_for(main["cote"])

    return {
        "status": label, "heure": kickoff_fr(event).strftime("%Hh%M"),
        "championnat": event.get("sport_title", ""), "sport_key": event.get("sport_key", ""),
        "favori": home, "adversaire": away, "camp": "Domicile",
        "home_team": home, "away_team": away, "event_id": event.get("id", ""),
        "handicap_consensus": consensus_home_line(event),
        "pari": f"Over {main['line']:g} buts", "over_line": main["line"],
        "cote": main["cote"], "bookmaker_ref": main["bookmaker"],
        "pct_victoire_historique": pct, "fiabilite": fiab,
        "secours": None if backup is None else {
            "pari": f"Handicap asiatique {home} {fmt_line(backup['line'])}",
            "ah_line": backup["line"], "cote": backup["cote"],
            "bookmaker": backup["bookmaker"], "dans_fenetre": backup["in_window"],
        },
    }


# ── RÉSULTATS DE LA VEILLE ────────────────────────────────────────────────────
def load_yesterday_picks() -> list:
    """Picks de la veille, un par match (la version du soir remplace celle du matin)."""
    by_event = {}
    for suffix in ["morning", "evening"]:
        path = PICKS_DIR / f"{yesterday_fr()}_{suffix}.json"
        if path.exists():
            with open(path, encoding="utf-8") as f:
                for p in json.load(f).get("picks", []):
                    by_event[p.get("event_id") or id(p)] = p
    return list(by_event.values())


def fetch_scores(sport_key: str) -> list:
    return api_get(f"/sports/{sport_key}/scores", {"daysFrom": 2}) or []


SPORT_NAME_TO_KEY = {
    "Premier League":              "soccer_epl",
    "Championship":                "soccer_efl_champ",
    "League One":                  "soccer_england_league1",
    "League Two":                  "soccer_england_league2",
    "Ligue 1 - France":            "soccer_france_ligue_one",
    "Ligue 2 - France":            "soccer_france_ligue_two",
    "Bundesliga - Germany":        "soccer_germany_bundesliga",
    "Bundesliga 2 - Germany":      "soccer_germany_bundesliga2",
    "Serie A - Italy":             "soccer_italy_serie_a",
    "La Liga - Spain":             "soccer_spain_la_liga",
    "La Liga 2 - Spain":           "soccer_spain_segunda_division",
    "Dutch Eredivisie":            "soccer_netherlands_eredivisie",
    "Belgium First Div":           "soccer_belgium_first_div",
    "Primeira Liga - Portugal":    "soccer_portugal_primeira_liga",
    "Turkey Super League":         "soccer_turkey_super_league",
    "UEFA Champions League":       "soccer_uefa_champs_league",
    "UEFA Europa League":          "soccer_uefa_europa_league",
    "UEFA Europa Conference League": "soccer_uefa_europa_conference_league",
}


def settle(pick: dict, hs: int, as_: int) -> tuple:
    """(résultat principal, résultat secours) : 'win' | 'push' | 'loss' | None."""
    if "over_line" in pick:
        main = "win" if hs + as_ > pick["over_line"] else "loss"
    else:  # anciens picks « Victoire favori » (avant la notice Over/Under)
        fav_won = (hs > as_) if pick.get("camp") == "Domicile" else (as_ > hs)
        main = "win" if fav_won else "loss"
    backup = None
    if pick.get("secours"):
        res = hs - as_ + pick["secours"]["ah_line"]
        backup = "win" if res > 0 else "push" if res == 0 else "loss"
    return main, backup


BACKUP_LABELS = {"win": "✅ gagné", "push": "↩️ remboursé", "loss": "❌ perdu"}


def resolve_yesterday(picks: list) -> list:
    if not picks:
        return []
    sports_needed = {p.get("sport_key") or SPORT_NAME_TO_KEY.get(p.get("championnat"))
                     for p in picks} - {None, ""}
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
            main, backup = settle(pick, hs, as_)
            pick["result"] = main
            pick["result_label"] = (f"✅ Validé ({score_str})" if main == "win"
                                    else f"❌ Raté ({score_str})")
            if backup:
                pick["secours"]["result"] = backup
                pick["secours_label"] = f"Secours : {BACKUP_LABELS[backup]}"
        resolved.append(pick)
    return resolved


# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    print(f"Sharp-Edge | {today_fr()} | Rapport : {REPORT_TYPE}")
    print(f"Filtres : favori domicile (handicap ≤ {HOME_FAV_MAX_LINE}) | "
          f"Over ligne simple coté {MIN_ODDS}–{MAX_ODDS}")

    raw = load_or_fetch_raw()
    alternates = raw.get("alternates", {})
    picks = []
    for event in raw.get("events", []):
        pick = build_pick(event, alternates.get(event.get("id"), {}))
        if pick:
            picks.append(pick)
    picks.sort(key=lambda x: x["cote"])

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

    print(f"\n✓ {len(picks)} picks → {out}")
    print(f"  Veille : {wins}W / {losses}L sur {total} résolus")
    for p in picks:
        s = p["secours"]
        print(f"  {p['status']} | {p['heure']} | {p['championnat']} | {p['home_team']} – "
              f"{p['away_team']} | {p['pari']} @ {p['cote']} | secours : "
              f"{s['pari'] + ' @ ' + str(s['cote']) if s else '—'}")


if __name__ == "__main__":
    main()
