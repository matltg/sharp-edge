"""
sharp-edge | Script 2 — Backtesting Over/Under, toutes lignes
L'historique football-data.co.uk ne contient des cotes que pour la ligne 2.5,
mais il contient le score de chaque match. Pour chaque match :
  1. cotes Over/Under 2.5 (Pinnacle, à défaut moyenne du marché) → probabilité
     de 3 buts ou plus, marge retirée par la méthode « puissance » ;
  2. on en déduit le nombre de buts attendu λ (loi de Poisson) ;
  3. on calcule la probabilité de chaque ligne (Over 0.5, 1.5, 2.5, 3.5, 4.5) ;
  4. on compare au résultat réel (le score dit si l'Over est passé).
On obtient, par ligne et par tranche de probabilité, le taux de réussite réel :
c'est la colonne « historique » utilisée dans la note des picks.

Produit data/calibration.json, relu par 3_daily_picks.py et 4_generate_page.py.
"""

import json
from datetime import datetime, timezone
from math import factorial
from pathlib import Path

import numpy as np
import pandas as pd

DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

# Par ligne, la 1re colonne renseignée est utilisée
OVER_COLS  = ["P>2.5", "Avg>2.5", "BbAv>2.5"]
UNDER_COLS = ["P<2.5", "Avg<2.5", "BbAv<2.5"]

LINES = [0.5, 1.5, 2.5, 3.5, 4.5]
PROBA_BINS = np.round(np.arange(0.0, 1.0001, 0.05), 2)  # tranches de 5 points


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


def power_devig(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Probabilité de l'issue a (cotes a et b), marge retirée par la méthode
    « puissance » : on cherche k tel que (1/a)^k + (1/b)^k = 1."""
    ia, ib = 1 / a, 1 / b
    lo, hi = np.full_like(ia, 0.5), np.full_like(ia, 3.0)
    for _ in range(60):
        k = (lo + hi) / 2
        too_big = ia ** k + ib ** k > 1
        lo, hi = np.where(too_big, k, lo), np.where(too_big, hi, k)
    return ia ** ((lo + hi) / 2)


def p_over(lam: np.ndarray, line: float) -> np.ndarray:
    """P(buts > line) pour une loi de Poisson de moyenne lam."""
    k = int(line)
    return 1 - sum(np.exp(-lam) * lam ** i / factorial(i) for i in range(k + 1))


def lambda_from_over25(p: np.ndarray) -> np.ndarray:
    lo, hi = np.full_like(p, 0.05), np.full_like(p, 8.0)
    for _ in range(60):
        lam = (lo + hi) / 2
        low = p_over(lam, 2.5) < p
        lo, hi = np.where(low, lam, lo), np.where(low, hi, lam)
    return (lo + hi) / 2


def build(df: pd.DataFrame) -> pd.DataFrame:
    o, u = coalesce(df, OVER_COLS), coalesce(df, UNDER_COLS)
    goals = pd.to_numeric(df["FTHG"], errors="coerce") + pd.to_numeric(df["FTAG"], errors="coerce")
    ok = (o > 1) & (u > 1) & goals.notna()
    p25 = power_devig(o[ok].to_numpy(float), u[ok].to_numpy(float))
    lam = lambda_from_over25(p25)
    out = pd.DataFrame({"league": df.loc[ok, "league_name"].to_numpy(),
                        "season": df.loc[ok, "season"].to_numpy(),
                        "goals": goals[ok].to_numpy(), "lambda": lam})
    for line in LINES:
        out[f"pred_{line}"] = p_over(lam, line)
        out[f"won_{line}"] = out["goals"] > line
    return out


def calibration_bins(t: pd.DataFrame, line: float) -> list:
    pred, won = t[f"pred_{line}"], t[f"won_{line}"]
    rows = []
    for lo, hi in zip(PROBA_BINS[:-1], PROBA_BINS[1:]):
        m = (pred >= lo) & (pred < hi)
        n = int(m.sum())
        if n:
            rows.append({"min": float(lo) * 100, "max": float(hi) * 100, "n": n,
                         "pred": round(float(pred[m].mean()) * 100, 1),
                         "win_rate": round(float(won[m].mean()) * 100, 1)})
    return rows


def main():
    df = load_data()
    t = build(df)
    print(f"Matchs avec cotes Over/Under 2.5 : {len(t)}")

    # 1. Calibration par ligne et tranche de probabilité
    lines = {}
    table = []
    for line in LINES:
        bins = calibration_bins(t, line)
        lines[str(line)] = bins
        print(f"\n=== OVER {line} — prédit moyen {t[f'pred_{line}'].mean() * 100:.1f}% "
              f"| réel {t[f'won_{line}'].mean() * 100:.1f}% ===")
        for b in bins:
            table.append({"Ligne": line, **b})
            if b["n"] >= 50:
                print(f"  {b['min']:.0f}–{b['max']:.0f}% | n={b['n']:5d} | "
                      f"prédit {b['pred']:5.1f}% | réel {b['win_rate']:5.1f}%")
    pd.DataFrame(table).to_csv(DATA_DIR / "backtest_global.csv", index=False)

    # 2. Stabilité par saison et par championnat (prédit vs réel, par ligne)
    for col, name in (("season", "backtest_by_season.csv"), ("league", "backtest_by_league.csv")):
        rows = []
        for key, sub in t.groupby(col):
            row = {col: key, "Matchs": len(sub)}
            for line in (1.5, 2.5):
                row[f"Over {line} prédit%"] = round(sub[f"pred_{line}"].mean() * 100, 1)
                row[f"Over {line} réel%"] = round(sub[f"won_{line}"].mean() * 100, 1)
            rows.append(row)
        pd.DataFrame(rows).to_csv(DATA_DIR / name, index=False)

    # 3. Calibration, relue par les scripts de picks et de page
    calibration = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "market": "Over/Under, lignes 0.5 à 4.5",
        "source": "Over/Under 2.5 Pinnacle → toutes lignes (Poisson), comparé aux scores réels",
        "seasons": sorted(df["season"].dropna().unique().tolist()),
        "n_matches": int(len(t)),
        "lines": lines,
    }
    with open(DATA_DIR / "calibration.json", "w", encoding="utf-8") as f:
        json.dump(calibration, f, ensure_ascii=False, indent=2)
    print(f"\n✓ Résultats sauvegardés dans {DATA_DIR}")


if __name__ == "__main__":
    main()
