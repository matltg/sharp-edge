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

Tous les matchs du jour des 18 championnats suivis, sans filtre, triés par
note (meilleure d'abord). Pour chaque match :

| Élément | Contenu |
|---------|---------|
| Sport | ⚽ Football |
| Statut | 🟢 Bon (avant 18h) · 🟡 À confirmer à 16h30 (18h et après) |
| Heure · championnat | Heure de Paris |
| Match | Domicile – Extérieur |
| Pari | Over ou Under buts, ligne simple (x.5) : parmi ceux cotés 1,20 – 1,50, la meilleure note ; à défaut le plus proche de la fenêtre (signalé) |
| Cote | Betclic si disponible, sinon moyenne des bookmakers (source indiquée) |
| Probabilité | Pinnacle (à défaut moyenne des bookmakers), Over vs Under sur la même ligne, marge retirée par la méthode « puissance » |
| Note | ★ à ★★★★★ : combine (sans les afficher) la valeur marché (probabilité × cote − 1) et la valeur historique (taux historique aux cotes similaires × cote − 1), l'historique pesant selon la taille de son échantillon. ★★★★★ ≥ +2 %, ★★★★ ≥ 0 %, ★★★ ≥ −2 %, ★★ ≥ −5 %, ★ en dessous |

Le backtest hebdomadaire (`data/calibration.json`) porte sur les 5 dernières
saisons complètes + la saison en cours (fenêtre qui avance seule chaque
1er juillet). football-data.co.uk ne fournit des cotes que pour la ligne 2.5,
mais donne le score de chaque match : les cotes Over/Under 2.5 de Pinnacle
donnent le nombre de buts attendu (loi de Poisson), d'où une probabilité
prédite pour chaque ligne (0.5 à 4.5), comparée au résultat réel. On obtient
ainsi un historique réel de l'Over 1.5 sur ~34 000 matchs (prédit à ~1 point
près).

La section « Suivi de fiabilité » compare, cumulé depuis le début, la
probabilité annoncée et le taux réalisé des picks (`docs/picks/suivi.json`).

Crédits The Odds API : liste des matchs gratuite (/events) + 1 crédit par match
(lignes Over/Under) + scores de la veille, soit ~800–1 000/mois.

## 🗺️ Feuille de route

- **Phase 1** (actuelle) : Football européen, données gratuites
- **Phase 2** : NCAA basket + football américain
- **Phase 3** : Handball, Rugby XV, Volleyball (Highlightly Pro)
- **Futur** : CLV, gestion de bankroll dynamique, ML

---
*Outil d'analyse statistique uniquement. Ne constitue pas un conseil en paris.*
