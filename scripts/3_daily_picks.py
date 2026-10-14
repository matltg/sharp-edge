"""
sharp-edge | Script 3 — Picks du jour
Récupère les matchs via The Odds API et applique les filtres de validation.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
NOTICE D'INTENTION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

OBJECTIF : 2 rapports quotidiens (4h30 et 16h30 heure France).

STRATÉGIE CRÉDITS (plan gratuit = 500 crédits/mois) :
  - L'appel API est effectué UNE SEULE FOIS le matin (rapport 4h30).
  - Les données sont mises en cache dans docs/picks/YYYY-MM-DD_raw.json.
  - Le rapport du soir (16h30) relit ce cache sans rappeler l'API.
  - Coût réel : 18 sources × 1 appel × 30 jours ≈ 540 crédits/mois
    (légèrement au-dessus du gratuit — retirer 1-2 sources peu actives
    suffit à rester dans les 500, ou accepter le dépassement minimal).

PASSAGE AU PLAN PAYANT (10$/mois = 10 000 crédits) :
  Dès que le bot est stable et les résultats validés sur 200+ paris,
  passer au plan payant The Odds API et activer REFRESH_EVENING = True
  ci-dessous pour rafraîchir les cotes réelles à 16h30.
  Cela donnera : 18 × 2 × 30 = 1 080 crédits/mois (11% du plan payant).

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

PICKS_DIR = Path(__file__).parent.parent / "docs" / "picks"
PICKS_DIR.mkdir(parents=True, exist_ok=True)

# ── PALIERS DE FIABILITÉ ──────────────────────────────────────────────────────
# Les taux affichés viennent de data/calibration.json (généré chaque semaine par
# 2_backtest.py). Valeurs ci-dessous utilisées seulement si le fichier manque.
CALIBRATION_PATH = Path(__file__).parent.parent / "data" / "calibration.json"
DEFAULT_TIERS = [
    (1.25, "★★★★★ Très solide",  "~82–85%"),
    (1.30, "★★★★☆ Solide",       "~77–82%"),
    (1.40, "★★★☆☆ Correct",      "~72–77%"),
    (1.50, "★★☆☆☆ À surveiller", "~68–72%"),
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


# ── APPEL API ─────────────────────────────────────────────────────────────────
def fetch_odds(sport_key: str) -> list:
    if not API_KEY:
        return []
    try:
        r = requests.get(
            f"{BASE_URL}/sports/{sport_key}/odds",
            params={"apiKey": API_KEY, "regions": "eu",
                    "markets": "h2h", "oddsFormat": "decimal", "dateFormat": "iso"},
            timeout=15,
        )
        if r.status_code == 200:
            return r.json()
        print(f"  API {sport_key}: HTTP {r.status_code}")
    except Exception as e:
        print(f"  Erreur {sport_key}: {e}")
    return []


def fetch_all_odds() -> list:
    """Appelle l'API pour toutes les sources et retourne la liste brute."""
    all_events = []
    for sport in SPORTS:
        events = fetch_odds(sport)
        all_events.extend(events)
        print(f"  {sport}: {len(events)} matchs")
    return all_events


def load_or_fetch_raw() -> list:
    """
    Matin  : appelle l'API et met en cache.
    Soir   : relit le cache (sauf si REFRESH_EVENING = True).
    """
    cache = raw_cache_path()

    if REPORT_TYPE == "morning" or (REPORT_TYPE == "evening" and REFRESH_EVENING):
        print(f"  → Appel API ({REPORT_TYPE})")
        events = fetch_all_odds()
        with open(cache, "w", encoding="utf-8") as f:
            json.dump(events, f, ensure_ascii=False)
        return events

    # Rapport du soir sans refresh : on relit le cache du matin
    if cache.exists():
        print(f"  → Cache du matin utilisé (REFRESH_EVENING=False — plan gratuit)")
        with open(cache, encoding="utf-8") as f:
            return json.load(f)

    # Cache absent : on appelle quand même (cas rare — matin raté)
    print(f"  → Cache absent, appel API de secours")
    events = fetch_all_odds()
    with open(cache, "w", encoding="utf-8") as f:
        json.dump(events, f, ensure_ascii=False)
    return events


# ── TRAITEMENT DES MATCHS ─────────────────────────────────────────────────────
def extract_best_odds(event: dict) -> dict | None:
    bookmakers = event.get("bookmakers", [])
    if not bookmakers:
        return None
    home, away = event["home_team"], event["away_team"]
    best_home = best_away = best_draw = book_home = book_away = None
    for bk in bookmakers:
        for market in bk.get("markets", []):
            if market["key"] != "h2h":
                continue
            for o in market["outcomes"]:
                p, n = o["price"], o["name"]
                if n == home:
                    if best_home is None or p > best_home:
                        best_home = p; book_home = bk["title"]
                elif n == away:
                    if best_away is None or p > best_away:
                        best_away = p; book_away = bk["title"]
                elif n == "Draw":
                    if best_draw is None or p > best_draw:
                        best_draw = p
    if best_home is None or best_away is None:
        return None
    return {"home": home, "away": away, "commence": event["commence_time"],
            "odds_home": best_home, "odds_away": best_away, "odds_draw": best_draw,
            "book_home": book_home, "book_away": book_away, "sport": event.get("sport_title", ""),
            "event_id": event.get("id", "")}


def identify_favourite(match: dict) -> dict | None:
    h, a = match["odds_home"], match["odds_away"]
    if h < a:
        fav_odds, fav_team, fav_camp, opp_team = h, match["home"], "H", match["away"]
    else:
        fav_odds, fav_team, fav_camp, opp_team = a, match["away"], "A", match["home"]

    if not (MIN_ODDS <= fav_odds <= MAX_ODDS):
        return None
    if HOME_ONLY and fav_camp != "H":
        return None

    commence_dt = datetime.fromisoformat(match["commence"].replace("Z", "+00:00"))
    commence_fr = commence_dt.astimezone(TZ_FRANCE)
    if commence_fr.strftime("%Y-%m-%d") != today_fr():
        return None

    hour = commence_fr.hour
    if REPORT_TYPE == "morning" and hour >= 18:
        label = "🟡 À confirmer à 16h30"
    elif REPORT_TYPE == "evening" and hour < 18:
        return None  # déjà couvert par le rapport du matin
    else:
        label = "🟢 Jouer maintenant"

    fiab, pct = tier_for(fav_odds)

    return {
        "status": label, "heure": commence_fr.strftime("%Hh%M"),
        "championnat": match["sport"], "favori": fav_team,
        "adversaire": opp_team, "camp": "Domicile" if fav_camp == "H" else "Extérieur",
        "cote": fav_odds, "pct_victoire_historique": pct,
        "fiabilite": fiab, "bookmaker_ref": match["book_home"] if fav_camp == "H" else match["book_away"],
        "pari": f"Victoire {fav_team}",
        "home_team": match["home"], "away_team": match["away"],
        "event_id": match["event_id"],
    }


# ── RÉSULTATS DE LA VEILLE ────────────────────────────────────────────────────
def load_yesterday_picks() -> list:
    picks = []
    for suffix in ["morning", "evening"]:
        path = PICKS_DIR / f"{yesterday_fr()}_{suffix}.json"
        if path.exists():
            with open(path, encoding="utf-8") as f:
                picks.extend(json.load(f).get("picks", []))
    return picks


def fetch_scores(sport_key: str) -> list:
    if not API_KEY:
        return []
    try:
        r = requests.get(
            f"{BASE_URL}/sports/{sport_key}/scores",
            params={"apiKey": API_KEY, "daysFrom": 2, "dateFormat": "iso"},
            timeout=15,
        )
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return []


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


def resolve_yesterday(picks: list) -> list:
    if not picks:
        return []
    sports_needed = {SPORT_NAME_TO_KEY[p["championnat"]]
                     for p in picks if p.get("championnat") in SPORT_NAME_TO_KEY}
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
        if not data or not data.get("completed"):
            pick["result"] = "unknown"
            pick["result_label"] = "⏳ Résultat non disponible"
        else:
            sc = {s["name"]: int(s["score"]) for s in data.get("scores", [])}
            hs = sc.get(pick.get("home_team"))
            as_ = sc.get(pick.get("away_team"))
            if hs is None or as_ is None:
                pick["result"] = "unknown"
                pick["result_label"] = "⏳ Score indisponible"
            else:
                score_str = f"{hs}–{as_}"
                fav_won = (hs > as_) if pick.get("camp") == "Domicile" else (as_ > hs)
                pick["result"] = "win" if fav_won else "loss"
                pick["result_label"] = (f"✅ Validé ({score_str})"
                                        if fav_won else f"❌ Raté ({score_str})")
        resolved.append(pick)
    return resolved


# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    print(f"Sharp-Edge | {today_fr()} | Rapport : {REPORT_TYPE}")
    print(f"Filtres : cote {MIN_ODDS}–{MAX_ODDS} | domicile={'oui' if HOME_ONLY else 'non'}")
    print(f"Mode : {'appel API' if REPORT_TYPE == 'morning' or REFRESH_EVENING else 'cache matin (plan gratuit)'}")

    events = load_or_fetch_raw()
    picks = []
    for event in events:
        match = extract_best_odds(event)
        if match:
            pick = identify_favourite(match)
            if pick:
                picks.append(pick)
    picks.sort(key=lambda x: x["cote"])

    yesterday_picks = load_yesterday_picks()
    yesterday_resolved = resolve_yesterday(yesterday_picks)
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
        print(f"  {p['status']} | {p['heure']} | {p['championnat']} | "
              f"{p['favori']} @ {p['cote']} | {p['fiabilite']}")


if __name__ == "__main__":
    main()
