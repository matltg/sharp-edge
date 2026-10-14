"""
sharp-edge | Script 2 — Backtesting (paris de la notice Phase 1)
- Pari principal : Over buts coté 1,20–1,50. L'historique football-data.co.uk
  ne contient que la ligne 2.5 : elle sert de proxy (les picks réels prennent
  souvent l'Over 1.5, non backtestable ici).
- Pari de secours : handicap asiatique ligne entière pour le favori, sur la
  ligne principale du marché (seule disponible dans l'historique).
- Favori = équipe dont la ligne handicap est ≤ -0.75 (domicile ou extérieur),
  comme 3_daily_picks.py. Les résultats « favori domicile » restent calculés.

Produit data/calibration.json (taux de réussite de l'Over par palier de cote),
relu par 3_daily_picks.py et 4_generate_page.py.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

# Par ligne, la 1re colonne renseignée est utilisée (Bb* = anciennes saisons)
OVER_SOURCES = {
    "b365": ["B365>2.5"],
    "avg":  ["Avg>2.5", "BbAv>2.5"],
    "max":  ["Max>2.5", "BbMx>2.5"],
}
AH_LINE = ["AHh", "BbAHh"]
AH_HOME_SOURCES = {
    "b365": ["B365AHH"],
    "avg":  ["AvgAHH", "BbAvAHH"],
    "max":  ["MaxAHH", "BbMxAHH"],
}
AH_AWAY_SOURCES = {
    "b365": ["B365AHA"],
    "avg":  ["AvgAHA", "BbAvAHA"],
    "max":  ["MaxAHA", "BbMxAHA"],
}
SOURCE_LABELS = {"b365": "B365", "avg": "moyenne", "max": "meilleure cote"}
REFERENCE_SOURCE = "max"  # comme 3_daily_picks.py (meilleure cote du marché)

MIN_ODDS, MAX_ODDS = 1.20, 1.50
FAV_MAX_LINE = -0.75

ODDS_WINDOWS = [(1.20, 1.30), (1.30, 1.40), (1.40, 1.50), (1.20, 1.50)]

# Paliers de fiabilité affichés sur les picks (cote du pari principal)
TIERS = [
    (1.20, 1.25, "★★★★★ Très solide"),
    (1.25, 1.30, "★★★★☆ Solide"),
    (1.30, 1.40, "★★★☆☆ Correct"),
    (1.40, 1.50, "★★☆☆☆ À surveiller"),
]


def load_data() -> pd.DataFrame:
    path = DATA_DIR / "historical_raw.csv"
    if not path.exists():
        raise FileNotFoundError("Lance d'abord 1_collect_data.py")
    df = pd.read_csv(path, low_memory=False)
    df = df[df["FTR"].isin(["H", "D", "A"])].copy()
    print(f"Données chargées : {len(df)} matchs joués")
    return df


def coalesce(df: pd.DataFrame, cols: list) -> pd.Series:
    out = pd.Series(np.nan, index=df.index)
    for col in cols:
        if col in df.columns:
            out = out.fillna(pd.to_numeric(df[col], errors="coerce"))
    return out


def over_bets(df: pd.DataFrame, source: str) -> pd.DataFrame:
    goals = pd.to_numeric(df["FTHG"], errors="coerce") + pd.to_numeric(df["FTAG"], errors="coerce")
    odds = coalesce(df, OVER_SOURCES[source])
    won = goals > 2.5
    line = coalesce(df, AH_LINE)
    bets = pd.DataFrame({
        "league": df["league_name"], "season": df["season"], "odds": odds,
        "home_fav": line <= FAV_MAX_LINE,
        "fav": (line <= FAV_MAX_LINE) | (-line <= FAV_MAX_LINE),
        "won": won, "profit": np.where(won, odds - 1, -1.0),
    })
    return bets[odds.notna() & goals.notna()]


def ah_bets(df: pd.DataFrame, source: str) -> pd.DataFrame:
    """Handicap ligne entière sur le favori (domicile ou extérieur)."""
    home_line = coalesce(df, AH_LINE)
    home_fav = home_line <= FAV_MAX_LINE
    line = pd.Series(np.where(home_fav, home_line, -home_line), index=df.index)  # vue du favori
    odds = pd.Series(np.where(home_fav, coalesce(df, AH_HOME_SOURCES[source]),
                              coalesce(df, AH_AWAY_SOURCES[source])), index=df.index)
    margin = pd.to_numeric(df["FTHG"], errors="coerce") - pd.to_numeric(df["FTAG"], errors="coerce")
    res = pd.Series(np.where(home_fav, margin, -margin), index=df.index) + line
    bets = pd.DataFrame({
        "season": df["season"], "line": line, "odds": odds, "home_fav": home_fav,
        "won": res > 0, "push": res == 0,
        "profit": np.select([res > 0, res == 0], [odds - 1, 0.0], -1.0),
    })
    mask = odds.notna() & (line % 1 == 0) & (line <= FAV_MAX_LINE)
    return bets[mask]


def in_range(odds: pd.Series, lo: float, hi: float) -> pd.Series:
    lower = odds >= lo if lo <= MIN_ODDS else odds > lo
    return lower & (odds <= hi)


def select(bets: pd.DataFrame, lo: float, hi: float, home_only: bool) -> pd.DataFrame:
    mask = in_range(bets["odds"], lo, hi) & bets["home_fav" if home_only else "fav"]
    return bets[mask]


def stats(sub: pd.DataFrame) -> dict:
    n = len(sub)
    if n == 0:
        return {"n": 0, "win_rate": None, "roi": None}
    return {
        "n": n,
        "win_rate": round(float(sub["won"].mean()) * 100, 1),
        "roi": round(float(sub["profit"].mean()) * 100, 2),
    }


def main():
    df = load_data()
    overs = {src: over_bets(df, src) for src in OVER_SOURCES}
    ref = overs[REFERENCE_SOURCE]

    # 1. Over 2.5 : résultats globaux par fenêtre de cotes, pour chaque source
    print("\n=== OVER 2.5 — GLOBAL ===")
    rows = []
    for lo, hi in ODDS_WINDOWS:
        for home_only in [False, True]:
            label = f"{lo}–{hi}" + (" favori domicile" if home_only else " favori dom./ext.")
            row = {"Stratégie": label}
            for src, bets in overs.items():
                s = stats(select(bets, lo, hi, home_only))
                name = SOURCE_LABELS[src]
                row[f"n ({name})"] = s["n"]
                row[f"Win% ({name})"] = s["win_rate"]
                row[f"ROI% ({name})"] = s["roi"]
            rows.append(row)
            r = row[f"ROI% ({SOURCE_LABELS[REFERENCE_SOURCE]})"]
            print(f"  {label:28s} | n={row[f'n ({SOURCE_LABELS[REFERENCE_SOURCE]})']:5d} | "
                  f"ROI meilleure cote={r if r is not None else 0:+6.2f}%")
    pd.DataFrame(rows).to_csv(DATA_DIR / "backtest_global.csv", index=False)

    # 2. Par saison (1.20–1.50, favori dom./ext., meilleure cote) : stabilité
    print("\n=== OVER 2.5 — PAR SAISON (1.20–1.50 favori dom./ext., meilleure cote) ===")
    season_rows = []
    for season in sorted(ref["season"].dropna().unique()):
        s = stats(select(ref[ref["season"] == season], MIN_ODDS, MAX_ODDS, home_only=False))
        season_rows.append({"Saison": season, "Matchs": s["n"],
                            "Win%": s["win_rate"], "ROI%": s["roi"]})
    season_df = pd.DataFrame(season_rows)
    print(season_df.to_string(index=False))
    season_df.to_csv(DATA_DIR / "backtest_by_season.csv", index=False)

    # 3. Par championnat (1.20–1.50, meilleure cote)
    league_rows = []
    for league in ref["league"].dropna().unique():
        sub = ref[ref["league"] == league]
        s_all = stats(select(sub, MIN_ODDS, MAX_ODDS, home_only=False))
        s_home = stats(select(sub, MIN_ODDS, MAX_ODDS, home_only=True))
        league_rows.append({
            "Championnat": league,
            "Matchs (favori dom./ext.)": s_all["n"], "Win% (favori dom./ext.)": s_all["win_rate"],
            "ROI% (favori dom./ext.)": s_all["roi"],
            "Matchs (favori domicile)": s_home["n"], "Win% (favori domicile)": s_home["win_rate"],
            "ROI% (favori domicile)": s_home["roi"],
        })
    league_df = pd.DataFrame(league_rows).sort_values("ROI% (favori dom./ext.)", ascending=False)
    league_df.to_csv(DATA_DIR / "backtest_by_league.csv", index=False)
    # Filtres candidats — échantillons faibles : à confirmer avant usage
    league_df[(league_df["ROI% (favori dom./ext.)"] > 0) &
              (league_df["Matchs (favori dom./ext.)"] > 50)].to_csv(
        DATA_DIR / "backtest_filters.csv", index=False)

    # 4. Secours : handicap asiatique ligne entière (ligne principale)
    print("\n=== SECOURS — HANDICAP ASIATIQUE LIGNE ENTIÈRE (favori dom./ext.) ===")
    ah_rows = []
    for src in AH_HOME_SOURCES:
        b = ah_bets(df, src)
        s = stats(b)
        ah_rows.append({"Source": SOURCE_LABELS[src], **s,
                        "Remboursés%": round(float(b["push"].mean()) * 100, 1) if len(b) else None,
                        "Cote médiane": round(float(b["odds"].median()), 2) if len(b) else None})
        print(f"  {SOURCE_LABELS[src]:15s} | n={s['n']:5d} | gagnés={s['win_rate']}% | ROI={s['roi']}%")
    pd.DataFrame(ah_rows).to_csv(DATA_DIR / "backtest_handicap.csv", index=False)

    # 5. Calibration des paliers (Over 2.5, meilleure cote)
    tiers = [{"min": lo, "max": hi, "label": label,
              "home": stats(select(ref, lo, hi, home_only=True)),
              "all":  stats(select(ref, lo, hi, home_only=False))}
             for lo, hi, label in TIERS]
    calibration = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "market": "Over 2.5 buts",
        "source": f"Over 2.5, {SOURCE_LABELS[REFERENCE_SOURCE]}",
        "seasons": sorted(df["season"].dropna().unique().tolist()),
        "n_matches": int(len(df)),
        "tiers": tiers,
    }
    with open(DATA_DIR / "calibration.json", "w", encoding="utf-8") as f:
        json.dump(calibration, f, ensure_ascii=False, indent=2)

    print("\n=== CALIBRATION (Over 2.5, favori dom./ext., meilleure cote) ===")
    for t in tiers:
        s = t["all"]
        print(f"  {t['label']:22s} {t['min']}–{t['max']} | n={s['n']:5d} | "
              f"win={s['win_rate']}% | ROI={s['roi']}%")
    print(f"\n✓ Résultats sauvegardés dans {DATA_DIR}")


if __name__ == "__main__":
    main()
