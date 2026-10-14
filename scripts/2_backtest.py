"""
sharp-edge | Script 2 — Backtesting
Vérifie que le biais favori-outsider est présent sur nos championnats.
Calcule le ROI de différentes stratégies de mise sur les favoris 1.20-1.50,
pour plusieurs sources de cotes (Bet365, moyenne du marché, meilleure cote).

Produit aussi data/calibration.json : taux de victoire observés par palier de
cote, relu par 3_daily_picks.py et 4_generate_page.py. Les pourcentages
affichés sur les picks suivent donc automatiquement la fenêtre de saisons.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

# Sources de cotes : par ligne, la 1re colonne renseignée est utilisée
# (les colonnes Bb* servent de secours pour les anciennes saisons)
ODDS_SOURCES = {
    "b365": {"H": ["B365H"],          "A": ["B365A"]},
    "avg":  {"H": ["AvgH", "BbAvH"],  "A": ["AvgA", "BbAvA"]},
    "max":  {"H": ["MaxH", "BbMxH"],  "A": ["MaxA", "BbMxA"]},
}
SOURCE_LABELS = {"b365": "B365", "avg": "moyenne", "max": "meilleure cote"}

# "max" = meilleure cote du marché, comme 3_daily_picks.py (best odds EU)
REFERENCE_SOURCE = "max"

MIN_ODDS = 1.20

# Fenêtres de cotes à tester (borne basse exclue sauf 1.20, borne haute incluse,
# comme les filtres de 3_daily_picks.py)
ODDS_WINDOWS = [
    (1.20, 1.30),
    (1.30, 1.40),
    (1.40, 1.50),
    (1.20, 1.50),  # fenêtre globale
]

# Paliers de fiabilité affichés sur les picks
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
    print(f"Données chargées : {len(df)} matchs")
    return df


def coalesce(df: pd.DataFrame, cols: list) -> pd.Series:
    out = pd.Series(np.nan, index=df.index)
    for col in cols:
        if col in df.columns:
            out = out.fillna(pd.to_numeric(df[col], errors="coerce"))
    return out


def favourites(df: pd.DataFrame, source: str) -> pd.DataFrame:
    """Une ligne par match : cote du favori, camp ('H'/'A'), victoire du favori."""
    h = coalesce(df, ODDS_SOURCES[source]["H"])
    a = coalesce(df, ODDS_SOURCES[source]["A"])
    home_fav = h < a
    fav = pd.DataFrame({
        "league": df["league_name"],
        "season": df["season"],
        "odds":   np.where(home_fav, h, a),
        "camp":   np.where(home_fav, "H", "A"),
        "won":    np.where(home_fav, df["FTR"] == "H", df["FTR"] == "A"),
    })
    valid = h.notna() & a.notna() & df["FTR"].isin(["H", "D", "A"])
    return fav[valid]


def in_range(odds: pd.Series, lo: float, hi: float) -> pd.Series:
    lower = odds >= lo if lo <= MIN_ODDS else odds > lo
    return lower & (odds <= hi)


def select(fav: pd.DataFrame, lo: float, hi: float, home_only: bool) -> pd.DataFrame:
    mask = in_range(fav["odds"], lo, hi)
    if home_only:
        mask &= fav["camp"] == "H"
    return fav[mask]


def stats(sub: pd.DataFrame) -> dict:
    n = len(sub)
    if n == 0:
        return {"n": 0, "win_rate": None, "roi": None}
    profit = np.where(sub["won"], sub["odds"] - 1, -1.0)
    return {
        "n": n,
        "win_rate": round(float(sub["won"].mean()) * 100, 1),
        "roi": round(float(profit.mean()) * 100, 2),
    }


def main():
    df = load_data()
    favs = {src: favourites(df, src) for src in ODDS_SOURCES}
    for src, fav in favs.items():
        print(f"  {SOURCE_LABELS[src]:15s} : {len(fav)} matchs exploitables")
    ref = favs[REFERENCE_SOURCE]

    # 1. Résultats globaux par fenêtre de cotes, pour chaque source
    print("\n=== BACKTESTING GLOBAL (tous championnats) ===")
    summary_rows = []
    for lo, hi in ODDS_WINDOWS:
        for home_only in [False, True]:
            label = f"{lo}–{hi}" + (" domicile" if home_only else " tous")
            row = {"Stratégie": label}
            for src, fav in favs.items():
                s = stats(select(fav, lo, hi, home_only))
                name = SOURCE_LABELS[src]
                row[f"n ({name})"] = s["n"]
                row[f"Win% ({name})"] = s["win_rate"]
                row[f"ROI% ({name})"] = s["roi"]
            summary_rows.append(row)
            print(f"  {label:20s} | " + " | ".join(
                f"{SOURCE_LABELS[s]} n={row[f'n ({SOURCE_LABELS[s]})']:5d} "
                f"ROI={row[f'ROI% ({SOURCE_LABELS[s]})'] or 0:+6.2f}%"
                for s in favs))
    pd.DataFrame(summary_rows).to_csv(DATA_DIR / "backtest_global.csv", index=False)

    # 2. Par saison (fenêtre 1.20–1.50, domicile, meilleure cote) : stabilité
    print("\n=== PAR SAISON (1.20–1.50 domicile, meilleure cote) ===")
    season_rows = []
    for season in sorted(ref["season"].dropna().unique()):
        s = stats(select(ref[ref["season"] == season], 1.20, 1.50, home_only=True))
        season_rows.append({"Saison": season, "Matchs": s["n"],
                            "Win%": s["win_rate"], "ROI%": s["roi"]})
    season_df = pd.DataFrame(season_rows)
    print(season_df.to_string(index=False))
    season_df.to_csv(DATA_DIR / "backtest_by_season.csv", index=False)

    # 3. Par championnat (fenêtre 1.20–1.50, meilleure cote)
    print("\n=== PAR CHAMPIONNAT (1.20–1.50, meilleure cote) ===")
    league_rows = []
    for league in ref["league"].dropna().unique():
        sub = ref[ref["league"] == league]
        s_all = stats(select(sub, 1.20, 1.50, home_only=False))
        s_home = stats(select(sub, 1.20, 1.50, home_only=True))
        league_rows.append({
            "Championnat": league,
            "Matchs (tous)": s_all["n"], "Win% (tous)": s_all["win_rate"],
            "ROI% (tous)": s_all["roi"],
            "Matchs (domicile)": s_home["n"], "Win% (domicile)": s_home["win_rate"],
            "ROI% (domicile)": s_home["roi"],
        })
    league_df = pd.DataFrame(league_rows).sort_values("ROI% (tous)", ascending=False)
    print(league_df.to_string(index=False))
    league_df.to_csv(DATA_DIR / "backtest_by_league.csv", index=False)

    # 4. Filtres candidats — échantillons faibles : à confirmer avant usage
    good = league_df[(league_df["ROI% (domicile)"] > 0) &
                     (league_df["Matchs (domicile)"] > 50)]
    good.to_csv(DATA_DIR / "backtest_filters.csv", index=False)

    # 5. Calibration des paliers, relue par les scripts de picks et de page
    tiers = []
    for lo, hi, label in TIERS:
        tiers.append({
            "min": lo, "max": hi, "label": label,
            "home": stats(select(ref, lo, hi, home_only=True)),
            "all":  stats(select(ref, lo, hi, home_only=False)),
        })
    seasons = sorted(df["season"].dropna().unique().tolist())
    calibration = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "source": SOURCE_LABELS[REFERENCE_SOURCE],
        "seasons": seasons,
        "n_matches": int(len(df)),
        "tiers": tiers,
    }
    with open(DATA_DIR / "calibration.json", "w", encoding="utf-8") as f:
        json.dump(calibration, f, ensure_ascii=False, indent=2)

    print("\n=== CALIBRATION (domicile, meilleure cote) ===")
    for t in tiers:
        s = t["home"]
        print(f"  {t['label']:22s} {t['min']}–{t['max']} | n={s['n']:5d} | "
              f"win={s['win_rate']}% | ROI={s['roi']}%")
    print(f"\n✓ Résultats sauvegardés dans {DATA_DIR}")


if __name__ == "__main__":
    main()
