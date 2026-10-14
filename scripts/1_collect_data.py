"""
sharp-edge | Script 1 — Collecte des données historiques
Source : football-data.co.uk (gratuit, sans API key)
"""

import os
import time
import requests
import pandas as pd
from datetime import date
from pathlib import Path

# Répertoire de sortie
DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

# Championnats couverts (football-data.co.uk codes)
LEAGUES = {
    # Premium
    "E0":  "Premier League (Angleterre)",
    "E1":  "Championship (Angleterre)",
    "E2":  "League One (Angleterre)",
    "E3":  "League Two (Angleterre)",
    "F1":  "Ligue 1 (France)",
    "F2":  "Ligue 2 (France)",
    "D1":  "Bundesliga (Allemagne)",
    "D2":  "2. Bundesliga (Allemagne)",
    "I1":  "Serie A (Italie)",
    "I2":  "Serie B (Italie)",
    "SP1": "LaLiga (Espagne)",
    "SP2": "Liga 2 (Espagne)",
    "N1":  "Eredivisie (Pays-Bas)",
    "B1":  "Pro League (Belgique)",
    "P1":  "Liga Portugal (Portugal)",
    "T1":  "Super Lig (Turquie)",
    "SC0": "Premiership (Ecosse)",
    "SC1": "Division 1 (Ecosse)",
    "G1":  "Super League (Grece)",
}

# Saisons à télécharger : les 5 dernières saisons complètes + la saison en cours
# (calculé automatiquement ; une saison démarre en juillet)
N_COMPLETE_SEASONS = 5

def _seasons() -> list[str]:
    today = date.today()
    current_start = today.year if today.month >= 7 else today.year - 1
    starts = range(current_start - N_COMPLETE_SEASONS, current_start + 1)
    return [f"{y}-{str(y + 1)[2:]}" for y in starts]

SEASONS = _seasons()

BASE_URL = "https://www.football-data.co.uk/mmz4281/{season}/{league}.csv"

def season_code(season: str) -> str:
    """Convertit '2023-24' en '2324'"""
    parts = season.split("-")
    return parts[0][2:] + parts[1]

def download_csv(league_code: str, season: str) -> pd.DataFrame | None:
    code = season_code(season)
    url = BASE_URL.format(season=code, league=league_code)
    try:
        r = requests.get(url, timeout=15)
        if r.status_code == 200 and len(r.content) > 500:
            from io import StringIO
            df = pd.read_csv(StringIO(r.text), on_bad_lines="skip")
            df["league_code"] = league_code
            df["league_name"] = LEAGUES[league_code]
            df["season"] = season
            return df
    except Exception as e:
        print(f"  Erreur {league_code} {season}: {e}")
    return None

def main():
    all_frames = []
    total = len(LEAGUES) * len(SEASONS)
    done = 0

    for league_code, league_name in LEAGUES.items():
        for season in SEASONS:
            done += 1
            print(f"[{done}/{total}] {league_name} {season}...")
            df = download_csv(league_code, season)
            if df is not None:
                all_frames.append(df)
                print(f"  ✓ {len(df)} matchs")
            else:
                print(f"  — indisponible")
            time.sleep(0.3)  # respecter le serveur

    if not all_frames:
        print("Aucune donnée téléchargée.")
        return

    combined = pd.concat(all_frames, ignore_index=True)

    # Normaliser les colonnes de cotes (B365 en priorité, sinon max disponible)
    # Cotes domicile : B365H, BWH, IWH, PSH...
    # On garde B365 comme référence principale
    output_path = DATA_DIR / "historical_raw.csv"
    combined.to_csv(output_path, index=False)
    print(f"\n✓ {len(combined)} matchs sauvegardés → {output_path}")
    print(f"  Colonnes disponibles : {list(combined.columns[:20])}...")

if __name__ == "__main__":
    main()
