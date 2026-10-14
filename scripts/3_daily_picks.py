"""
sharp-edge | Script 3 — Matchs du jour
Liste tous les matchs du jour avec un pari Over/Under, sa cote, sa probabilité
estimée par le marché et le taux historique sur des cotes similaires.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
NOTICE D'INTENTION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

OBJECTIF : 2 rapports quotidiens (4h30 et 16h30 heure France).

AFFICHAGE : tous les matchs du jour, sans filtre, triés par nombre d'étoiles
  puis, à étoiles égales, par probabilité.
  - Pari : Over ou Under buts, ligne simple (x.5, sans remboursement partiel).
    Parmi tous ceux cotés dans 1,20–1,50, on prend la meilleure note (puis la
    meilleure probabilité) ; à défaut, celui dont la cote est la plus proche
    de cette fenêtre (signalé).
  - Cote : celle de Betclic si disponible, sinon la moyenne des bookmakers.
  - Probabilité : cotes Over et Under de Pinnacle (bookmaker de référence, le
    moins margé) sur la même ligne, marge retirée par la méthode « puissance » ;
    sans Pinnacle, moyenne des autres bookmakers calculée de la même façon.
  - Historique : taux de réussite réel, dans le backtest, des matchs dont la
    probabilité prédite sur cette ligne était similaire (data/calibration.json).
    La prédiction est faite comme dans le backtest : ligne 2.5 de Pinnacle →
    nombre de buts attendu (Poisson) → probabilité de la ligne.
  - Suivi : chaque pick résolu est ajouté à docs/picks/suivi.json (annoncé
    contre réalisé), affiché sur la page.
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
  - Le rapport du soir reprend tous les matchs pas encore commencés et
    remplace celui du matin sur la page.
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
from math import exp, factorial
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


def load_calibration() -> dict:
    """{ligne: [tranches de probabilité]} issu du backtest."""
    try:
        with open(CALIBRATION_PATH, encoding="utf-8") as f:
            cal = json.load(f)
        lines = {float(k): v for k, v in cal["lines"].items()}
        print(f"  Historique : backtest du {cal['generated_at']} "
              f"({cal['seasons'][0]} → {cal['seasons'][-1]})")
        return lines
    except (OSError, KeyError, IndexError, ValueError) as e:
        print(f"  Historique indisponible ({e})")
        return {}


CALIBRATION = load_calibration()


def history_stats(side: str, line: float, proba: float | None) -> tuple:
    """(taux de réussite réel %, effectif) des matchs passés dont la probabilité
    prédite sur cette ligne était dans la même tranche, ou (None, 0).
    Le backtest est calculé pour l'Over : un Under passe quand l'Over échoue."""
    if proba is None:
        return None, 0
    over_proba = proba if side == "Over" else 100 - proba
    # Interpolation linéaire entre les tranches voisines (sur leur probabilité
    # prédite moyenne) : évite qu'un petit écart franchissant une frontière de
    # tranche fasse sauter le taux de plusieurs points.
    bins = [b for b in CALIBRATION.get(line, []) if b["n"] >= MIN_HISTORY_N]
    if not bins or not bins[0]["pred"] <= over_proba <= bins[-1]["pred"]:
        return None, 0
    for lo, hi in zip(bins, bins[1:] + bins[-1:]):
        if lo["pred"] <= over_proba <= hi["pred"]:
            t = 0 if hi is lo else (over_proba - lo["pred"]) / (hi["pred"] - lo["pred"])
            rate = lo["win_rate"] + t * (hi["win_rate"] - lo["win_rate"])
            n = round(lo["n"] + t * (hi["n"] - lo["n"]))
            return round(rate if side == "Over" else 100 - rate, 1), n
    return None, 0


def history_for(side: str, line: float, proba: float | None) -> str:
    rate, n = history_stats(side, line, proba)
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


def rating(proba: float | None, odds: float, side: str, line: float,
           model_proba: float | None) -> dict:
    # Score = moyenne pondérée de la valeur marché et de la valeur historique.
    # L'historique est cherché avec la probabilité « modèle » (Poisson depuis la
    # ligne 2.5), comme dans le backtest — pas avec la probabilité de marché.
    market = None if proba is None else (proba / 100 * odds - 1) * 100
    rate, n = history_stats(side, line, model_proba)
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


REFERENCE_BOOKMAKER = ("pinnacle", "Pinnacle")  # le moins margé, cotes les plus précises


def power_devig(over: float, under: float) -> float:
    """Probabilité de l'Over, marge retirée par la méthode « puissance » :
    on cherche k tel que (1/over)^k + (1/under)^k = 1. Contrairement à la
    méthode proportionnelle, elle ne sous-estime pas le côté favori."""
    io, iu = 1 / over, 1 / under
    lo, hi = 0.5, 3.0
    for _ in range(60):
        k = (lo + hi) / 2
        lo, hi = (k, hi) if io ** k + iu ** k > 1 else (lo, k)
    return io ** ((lo + hi) / 2)


def fair_prob(data: dict, line: float) -> tuple:
    """Probabilité de l'Over sur `line`, marge retirée : Pinnacle si disponible,
    sinon moyenne des autres bookmakers. Retourne (probabilité %, source)."""
    probs = {}
    for bk in data.get("bookmakers", []):
        prices = {}
        for m in bk.get("markets", []):
            if m["key"] not in ("totals", "alternate_totals"):
                continue
            for o in m.get("outcomes", []):
                if o.get("point") is not None and float(o["point"]) == line:
                    prices[o["name"]] = o["price"]
        if prices.get("Over", 0) > 1 and prices.get("Under", 0) > 1:
            probs[bk["key"]] = power_devig(prices["Over"], prices["Under"])
    if not probs:
        return None, None
    ref_key, ref_label = REFERENCE_BOOKMAKER
    if ref_key in probs:
        return round(probs[ref_key] * 100, 1), ref_label
    return (round(sum(probs.values()) / len(probs) * 100, 1),
            f"moyenne de {len(probs)} bookmaker{'s' if len(probs) > 1 else ''}")


def p_over_poisson(lam: float, line: float) -> float:
    """P(buts > line) pour une loi de Poisson de moyenne lam."""
    return 1 - sum(exp(-lam) * lam ** i / factorial(i) for i in range(int(line) + 1))


def match_lambda(data: dict) -> float | None:
    """Nombre de buts attendu, déduit de la ligne 2.5 (Pinnacle, marge retirée)
    comme dans le backtest ; à défaut, de la ligne x.5 disponible la plus proche."""
    lines = sorted({float(o["point"]) for bk in data.get("bookmakers", [])
                    for m in bk.get("markets", []) for o in m.get("outcomes", [])
                    if o.get("point") is not None and float(o["point"]) % 1 == 0.5},
                   key=lambda pt: abs(pt - 2.5))
    for pt in lines:
        p, _ = fair_prob(data, pt)
        if p is None or not 0.5 < p < 99.5:
            continue
        lo, hi = 0.05, 10.0
        for _ in range(60):
            lam = (lo + hi) / 2
            lo, hi = (lam, hi) if p_over_poisson(lam, pt) < p / 100 else (lo, lam)
        return (lo + hi) / 2
    return None


def choose_bet(data: dict) -> dict | None:
    """Parmi tous les Over et Under en ligne simple (x.5) cotés dans 1,20–1,50 :
    celui qui a la meilleure note, puis la meilleure probabilité. Sans candidat
    dans la fenêtre : celui dont la cote en est la plus proche."""
    lam = match_lambda(data)
    candidates = []
    for side in ("Over", "Under"):
        for pt, (price, book) in ref_prices(data, side).items():
            if pt % 1 != 0.5:
                continue
            over_proba, proba_source = fair_prob(data, pt)
            proba = (None if over_proba is None
                     else over_proba if side == "Over" else round(100 - over_proba, 1))
            model_over = None if lam is None else p_over_poisson(lam, pt) * 100
            model = (None if model_over is None
                     else round(model_over if side == "Over" else 100 - model_over, 1))
            candidates.append({"side": side, "line": pt, "cote": price, "source": book,
                               "in_window": in_window(price), "proba": proba,
                               "proba_source": proba_source, "proba_modele": model,
                               **rating(proba, price, side, pt, model)})
    if not candidates:
        return None
    inside = [c for c in candidates if c["in_window"]]
    if inside:
        return max(inside, key=lambda c: (c["score"] if c["score"] is not None else -1e9,
                                          c["proba"] or 0))
    distance = lambda c: min(abs(c["cote"] - MIN_ODDS), abs(c["cote"] - MAX_ODDS))
    return min(candidates, key=lambda c: (distance(c), -(c["proba"] or 0)))


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
    # Le rapport du soir remplace celui du matin sur la page : il reprend
    # tous les matchs pas encore commencés.
    if REPORT_TYPE == "evening" and kickoff <= datetime.now(TZ_FRANCE):
        return None

    bet = choose_bet(data)
    pick = {
        "sport": SPORT_LABEL, "heure": kickoff.strftime("%Hh%M"),
        "championnat": event.get("sport_title", ""), "sport_key": event.get("sport_key", ""),
        "home_team": event["home_team"], "away_team": event["away_team"],
        "event_id": event.get("id", ""),
        "pari": None, "cote": None, "proba": None, "historique": "—", "valeur": None,
        "score": None, "etoiles": None, "note": None,
    }
    if bet:
        pick.update({
            "pari": f"{bet['side']} {bet['line']:g} buts",
            "ou_side": bet["side"], "ou_line": bet["line"],
            "cote": bet["cote"], "cote_source": bet["source"],
            "dans_fenetre": bet["in_window"],
            "proba": bet["proba"], "proba_source": bet["proba_source"],
            "proba_modele": bet["proba_modele"],
            "historique": history_for(bet["side"], bet["line"], bet["proba_modele"]),
            "valeur": (None if bet["proba"] is None
                       else round((bet["proba"] / 100 * bet["cote"] - 1) * 100, 1)),
            "score": bet["score"], "etoiles": bet["etoiles"], "note": bet["note"],
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
    if "ou_line" in pick:
        over_won = hs + as_ > pick["ou_line"]
        return "win" if over_won == (pick["ou_side"] == "Over") else "loss"
    if "over_line" in pick:  # picks antérieurs à l'ajout des Unders
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


# ── SUIVI ANNONCÉ / RÉALISÉ ───────────────────────────────────────────────────
TRACKING_PATH = PICKS_DIR / "suivi.json"


def update_tracking(resolved: list, date: str) -> int:
    """Ajoute les picks résolus (gagnés/perdus) au journal cumulé, sans doublon."""
    try:
        with open(TRACKING_PATH, encoding="utf-8") as f:
            log = json.load(f)
    except (OSError, ValueError):
        log = []
    seen = {(r["date"], r["event_id"]) for r in log}
    added = 0
    for p in resolved:
        if p.get("result") not in ("win", "loss") or p.get("proba") is None:
            continue
        key = (date, p.get("event_id", ""))
        if key in seen:
            continue
        log.append({"date": date, "event_id": key[1], "championnat": p.get("championnat"),
                    "match": f"{p.get('home_team')} – {p.get('away_team')}",
                    "pari": p.get("pari"), "cote": p.get("cote"), "proba": p.get("proba"),
                    "etoiles": p.get("etoiles"), "result": p["result"]})
        seen.add(key)
        added += 1
    with open(TRACKING_PATH, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=1)
    return added


def yesterday_from_morning() -> dict | None:
    """Le soir, reprend les résultats de la veille déjà calculés le matin
    (évite de repayer l'appel scores)."""
    path = PICKS_DIR / f"{today_fr()}_morning.json"
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f).get("yesterday")
    except (OSError, ValueError):
        return None


# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    print(f"Sharp-Edge | {today_fr()} | Rapport : {REPORT_TYPE}")

    raw = load_or_fetch_raw()
    odds = raw.get("odds", {})
    picks = [p for e in raw.get("events", [])
             if (p := build_pick(e, odds.get(e.get("id"), {})))]
    # plus d'étoiles d'abord, puis la probabilité (les écarts de score à l'intérieur
    # d'un même nombre d'étoiles ne sont pas significatifs) ; sans cotes à la fin
    picks.sort(key=lambda x: (x["etoiles"] is None, -(x["etoiles"] or 0), -(x["proba"] or 0)))

    cached = yesterday_from_morning() if REPORT_TYPE == "evening" else None
    yesterday_resolved = (cached or {}).get("resolved") or resolve_yesterday(load_yesterday_picks())
    wins   = sum(1 for p in yesterday_resolved if p.get("result") == "win")
    losses = sum(1 for p in yesterday_resolved if p.get("result") == "loss")
    total  = wins + losses
    added = update_tracking(yesterday_resolved, yesterday_fr())
    print(f"  Suivi : {added} pick(s) ajouté(s) à {TRACKING_PATH.name}")

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
        print(f"  {p['heure']} | {p['championnat']} | {p['home_team']} – "
              f"{p['away_team']} | {p['pari'] or 'cotes indisponibles'} @ {p['cote']} | "
              f"{p['proba']}% | hist. {p['historique']} | valeur {p['valeur']}% | "
              f"{p['etoiles']}★ {p['note']} (score {p['score']})")


if __name__ == "__main__":
    main()
