# ⚡ Sharp-Edge

**Sports betting filter — low odds favourites validator**

Analyse quotidienne des favoris à cote basse (1,20–1,50) sur les principaux championnats de football européens. Deux rapports par jour, disponibles à 4h30 et 16h30 (heure France).

## 📊 Accès aux picks

👉 **[matltg.github.io/sharp-edge](https://matltg.github.io/sharp-edge)**

## 🚀 Installation en 4 étapes

### 1. Clé API The Odds API (gratuit)
1. Créer un compte sur [the-odds-api.com](https://the-odds-api.com)
2. Copier la clé API gratuite

### 2. Ajouter le secret GitHub
1. Dans ce repo → **Settings** → **Secrets and variables** → **Actions**
2. Cliquer **New repository secret**
3. Nom : `ODDS_API_KEY` | Valeur : ta clé API

### 3. Activer GitHub Pages
1. Dans ce repo → **Settings** → **Pages**
2. Source : **Deploy from a branch**
3. Branch : `main` | Folder : `/docs`
4. Cliquer **Save**

### 4. Lancer le premier backtest (ensuite automatique chaque lundi)
1. Onglet **Actions** → **Sharp-Edge Backtest**
2. Cliquer **Run workflow**
3. Attendre ~5 minutes
4. Les résultats apparaissent dans `data/`

## 🏗️ Architecture

```
sharp-edge/
├── scripts/
│   ├── 1_collect_data.py     # Télécharge l'historique football-data.co.uk
│   ├── 2_backtest.py         # Analyse du biais favori sur l'historique
│   ├── 3_daily_picks.py      # Picks du jour via The Odds API
│   └── 4_generate_page.py    # Génère la page HTML GitHub Pages
├── data/                     # Données historiques + résultats backtest
├── docs/                     # Site GitHub Pages
│   ├── index.html            # Page principale (picks du jour)
│   └── picks/                # Archives JSON par jour
├── .github/workflows/
│   ├── morning.yml           # Rapport 4h30 France (cron UTC)
│   ├── evening.yml           # Rapport 16h30 France (cron UTC)
│   └── backtest.yml          # Backtest hebdo (lundi) + manuel
└── requirements.txt
```

## 🎯 Ce qu'affiche la page (Phase 1 — football)

Tous les matchs du jour des 18 championnats suivis, sans filtre, triés du plus
probable au moins probable. Pour chaque match :

| Élément | Contenu |
|---------|---------|
| Sport | ⚽ Football |
| Statut | 🟢 Bon (avant 18h) · 🟡 À confirmer à 16h30 (18h et après) |
| Heure · championnat | Heure de Paris |
| Match | Domicile – Extérieur |
| Pari | Over buts, ligne simple (x.5) la plus haute cotée 1,20 – 1,50 ; à défaut la plus proche (signalée) |
| Cote | Meilleure cote du marché (bookmaker indiqué) |
| Probabilité | Estimée par le marché : moyenne des bookmakers, marge retirée (Over vs Under sur la même ligne) |
| Historique | Taux de réussite de l'Over aux cotes similaires dans le backtest |

Le backtest hebdomadaire (`data/calibration.json`) porte sur les 5 dernières
saisons complètes + la saison en cours (fenêtre qui avance seule chaque
1er juillet). L'historique football-data.co.uk ne contient que la ligne 2.5 :
le taux observé à une cote donnée sert de référence pour toute ligne Over.

Crédits The Odds API : liste des matchs gratuite (/events) + 1 crédit par match
(lignes Over/Under) + scores de la veille, soit ~800–1 000/mois.

## 🗺️ Feuille de route

- **Phase 1** (actuelle) : Football européen, données gratuites
- **Phase 2** : NCAA basket + football américain
- **Phase 3** : Handball, Rugby XV, Volleyball (Highlightly Pro)
- **Futur** : CLV, gestion de bankroll dynamique, ML

---
*Outil d'analyse statistique uniquement. Ne constitue pas un conseil en paris.*
