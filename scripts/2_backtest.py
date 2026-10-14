"""
sharp-edge | Script 2 — Backtesting
Vérifie que le biais favori-outsider est présent sur nos championnats.
Calcule le ROI de différentes stratégies de mise sur les favoris 1.20-1.50.
"""

import pandas as pd
import numpy as np
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
RESULTS_DIR = Path(__file__).parent.parent / "data"
RESULTS_DIR.mkdir(exist_ok=True)

# Fenêtres de cotes à tester
ODDS_WINDOWS = [
    (1.20, 1.30),
    (1.30, 1.40),
    (1.40, 1.50),
    (1.20, 1.50),  # fenêtre globale
]

def load_data() -> pd.DataFrame:
    path = DATA_DIR / "historical_raw.csv"
    if not path.exists():
        raise FileNotFoundError("Lance d'abord 1_collect_data.py")
    df = pd.read_csv(path, low_memory=False)
    print(f"Données chargées : {len(df)} matchs")
    return df

def get_odds_column(df: pd.DataFrame) -> str:
    """Trouve la meilleure colonne de cotes disponible (B365 en priorité)."""
    candidates = {
        "home": ["B365H", "BWH", "IWH", "PSH", "WHH"],
        "away": ["B365A", "BWA", "IWA", "PSA", "WHA"],
        "draw": ["B365D", "BWD", "IWD", "PSD", "WHD"],
    }
    found = {}
    for side, cols in candidates.items():
        for col in cols:
            if col in df.columns:
                found[side] = col
                break
    return found

def identify_favourite(row, odds_cols: dict) -> tuple:
    """
    Retourne (cote_favori, camp_favori, résultat_favori_gagne)
    camp : 'H' = domicile, 'A' = extérieur
    """
    try:
        h = float(row[odds_cols["home"]])
        a = float(row[odds_cols["away"]])
        if pd.isna(h) or pd.isna(a):
            return None, None, None
        if h < a:
            fav_odds = h
            fav_camp = "H"
            fav_won = row["FTR"] == "H"
        else:
            fav_odds = a
            fav_camp = "A"
            fav_won = row["FTR"] == "A"
        return fav_odds, fav_camp, fav_won
    except Exception:
        return None, None, None

def backtest_window(df: pd.DataFrame, odds_cols: dict,
                    min_odds: float, max_odds: float,
                    home_only: bool = False) -> dict:
    results = []
    for _, row in df.iterrows():
        fav_odds, fav_camp, fav_won = identify_favourite(row, odds_cols)
        if fav_odds is None:
            continue
        if not (min_odds <= fav_odds < max_odds):
            continue
        if home_only and fav_camp != "H":
            continue
        if fav_won is None:
            continue
        profit = (fav_odds - 1) if fav_won else -1
        results.append({
            "league": row.get("league_name", row.get("league_code", "?")),
            "season": row.get("season", "?"),
            "fav_odds": fav_odds,
            "fav_camp": fav_camp,
            "fav_won": fav_won,
            "profit": profit,
        })

    if not results:
        return {"n": 0, "win_rate": 0, "roi": 0, "profit_total": 0}

    rdf = pd.DataFrame(results)
    n = len(rdf)
    win_rate = rdf["fav_won"].mean()
    roi = rdf["profit"].mean()
    profit_total = rdf["profit"].sum()

    return {
        "n": n,
        "win_rate": round(win_rate * 100, 1),
        "roi": round(roi * 100, 2),
        "profit_total": round(profit_total, 2),
    }

def backtest_by_league(df: pd.DataFrame, odds_cols: dict,
                       min_odds: float = 1.20,
                       max_odds: float = 1.50) -> pd.DataFrame:
    rows = []
    for league in df["league_name"].dropna().unique():
        sub = df[df["league_name"] == league]
        res_all = backtest_window(sub, odds_cols, min_odds, max_odds)
        res_home = backtest_window(sub, odds_cols, min_odds, max_odds, home_only=True)
        rows.append({
            "Championnat": league,
            "Matchs (tous)": res_all["n"],
            "Win% (tous)": res_all["win_rate"],
            "ROI% (tous)": res_all["roi"],
            "Matchs (domicile)": res_home["n"],
            "Win% (domicile)": res_home["win_rate"],
            "ROI% (domicile)": res_home["roi"],
        })
    return pd.DataFrame(rows).sort_values("ROI% (tous)", ascending=False)

def main():
    df = load_data()
    odds_cols = get_odds_column(df)
    print(f"Colonnes de cotes utilisées : {odds_cols}")

    # 1. Résultats globaux par fenêtre de cotes
    print("\n=== BACKTESTING GLOBAL (tous championnats) ===")
    summary_rows = []
    for min_o, max_o in ODDS_WINDOWS:
        for home_only in [False, True]:
            label = f"{min_o}–{max_o}" + (" domicile" if home_only else " tous")
            res = backtest_window(df, odds_cols, min_o, max_o, home_only)
            summary_rows.append({"Stratégie": label, **res})
            print(f"  {label:25s} | n={res['n']:5d} | win={res['win_rate']:5.1f}% | ROI={res['roi']:+6.2f}%")

    summary_df = pd.DataFrame(summary_rows)
    summary_df.to_csv(RESULTS_DIR / "backtest_global.csv", index=False)

    # 2. Résultats par championnat (fenêtre 1.20–1.50)
    print("\n=== BACKTESTING PAR CHAMPIONNAT (1.20–1.50) ===")
    league_df = backtest_by_league(df, odds_cols)
    print(league_df.to_string(index=False))
    league_df.to_csv(RESULTS_DIR / "backtest_by_league.csv", index=False)

    # 3. Filtres recommandés
    print("\n=== FILTRES RECOMMANDÉS (ROI > 0, n > 50) ===")
    good = league_df[
        (league_df["ROI% (domicile)"] > 0) &
        (league_df["Matchs (domicile)"] > 50)
    ]
    print(good[["Championnat", "Matchs (domicile)", "Win% (domicile)", "ROI% (domicile)"]].to_string(index=False))
    good.to_csv(RESULTS_DIR / "backtest_filters.csv", index=False)

    print(f"\n✓ Résultats sauvegardés dans {RESULTS_DIR}")

if __name__ == "__main__":
    main()
