"""
sharp-edge | Script 2 — Backtesting Over/Under
Mesure, sur l'historique football-data.co.uk, le taux de réussite réel de
l'Over selon sa cote. L'historique ne contient que la ligne 2.5 : le taux
observé à une cote donnée sert de référence pour toute ligne Over cotée pareil.

Produit data/calibration.json (taux par tranche de cote), relu par
3_daily_picks.py (colonne « Historique ») et 4_generate_page.py.
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
SOURCE_LABELS = {"b365": "B365", "avg": "moyenne", "max": "meilleure cote"}
REFERENCE_SOURCE = "max"  # comme 3_daily_picks.py (meilleure cote du marché)

# Tranches de cote [min, max) pour la colonne « Historique »
BUCKET_EDGES = [1.01, 1.20, 1.25, 1.30, 1.35, 1.40, 1.45, 1.50,
                1.60, 1.70, 1.80, 1.90, 2.00, 2.20, 2.50, 3.00, 4.00, 100.0]


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
    bets = pd.DataFrame({
        "league": df["league_name"], "season": df["season"], "odds": odds,
        "won": won, "profit": np.where(won, odds - 1, -1.0),
    })
    return bets[odds.notna() & goals.notna()]


def stats(sub: pd.DataFrame) -> dict:
    n = len(sub)
    if n == 0:
        return {"n": 0, "win_rate": None, "roi": None}
    return {
        "n": n,
        "win_rate": round(float(sub["won"].mean()) * 100, 1),
        "roi": round(float(sub["profit"].mean()) * 100, 2),
    }


def bucket_stats(bets: pd.DataFrame) -> list:
    rows = []
    for lo, hi in zip(BUCKET_EDGES[:-1], BUCKET_EDGES[1:]):
        s = stats(bets[(bets["odds"] >= lo) & (bets["odds"] < hi)])
        rows.append({"min": lo, "max": hi, **s})
    return rows


def main():
    df = load_data()
    overs = {src: over_bets(df, src) for src in OVER_SOURCES}
    ref = overs[REFERENCE_SOURCE]

    # 1. Par tranche de cote, pour chaque source
    print("\n=== OVER 2.5 — TAUX DE RÉUSSITE PAR TRANCHE DE COTE ===")
    table = []
    for src, bets in overs.items():
        for b in bucket_stats(bets):
            table.append({"Source": SOURCE_LABELS[src], "Cote min": b["min"],
                          "Cote max": b["max"], "Matchs": b["n"],
                          "Réussite%": b["win_rate"], "ROI%": b["roi"]})
    pd.DataFrame(table).to_csv(DATA_DIR / "backtest_global.csv", index=False)

    buckets = bucket_stats(ref)
    for b in buckets:
        if b["n"]:
            print(f"  {b['min']:.2f}–{b['max']:.2f} | n={b['n']:5d} | "
                  f"réussite={b['win_rate']:5.1f}% | ROI={b['roi']:+6.2f}%")

    # 2. Par saison (fenêtre 1.20–1.50, meilleure cote) : stabilité
    window = ref[(ref["odds"] >= 1.20) & (ref["odds"] <= 1.50)]
    season_rows = [{"Saison": s, **stats(window[window["season"] == s])}
                   for s in sorted(window["season"].dropna().unique())]
    pd.DataFrame(season_rows).to_csv(DATA_DIR / "backtest_by_season.csv", index=False)

    # 3. Par championnat (fenêtre 1.20–1.50, meilleure cote)
    league_rows = [{"Championnat": l, **stats(window[window["league"] == l])}
                   for l in window["league"].dropna().unique()]
    pd.DataFrame(league_rows).sort_values("n", ascending=False).to_csv(
        DATA_DIR / "backtest_by_league.csv", index=False)

    # 4. Calibration, relue par les scripts de picks et de page
    calibration = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "market": "Over 2.5 buts",
        "source": f"Over 2.5, {SOURCE_LABELS[REFERENCE_SOURCE]}",
        "seasons": sorted(df["season"].dropna().unique().tolist()),
        "n_matches": int(len(df)),
        "buckets": buckets,
    }
    with open(DATA_DIR / "calibration.json", "w", encoding="utf-8") as f:
        json.dump(calibration, f, ensure_ascii=False, indent=2)

    # Anciens fichiers devenus sans objet
    for old in ("backtest_filters.csv", "backtest_handicap.csv"):
        (DATA_DIR / old).unlink(missing_ok=True)

    print(f"\n✓ Résultats sauvegardés dans {DATA_DIR}")


if __name__ == "__main__":
    main()
