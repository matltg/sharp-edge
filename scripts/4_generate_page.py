"""
sharp-edge | Script 4 — Génération de la page HTML GitHub Pages
"""

import json
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path

TZ_FRANCE = ZoneInfo("Europe/Paris")  # gère automatiquement heure été / hiver
DOCS_DIR  = Path(__file__).parent.parent / "docs"
PICKS_DIR = DOCS_DIR / "picks"
DOCS_DIR.mkdir(exist_ok=True)
PICKS_DIR.mkdir(exist_ok=True)
CALIBRATION_PATH = Path(__file__).parent.parent / "data" / "calibration.json"


def calibration_note() -> str:
    try:
        with open(CALIBRATION_PATH, encoding="utf-8") as f:
            cal = json.load(f)
        return (f"Taux historiques : backtest du {cal['generated_at']} sur "
                f"{cal['n_matches']} matchs ({cal['seasons'][0]} → {cal['seasons'][-1]}, "
                f"{cal['source']})")
    except (OSError, KeyError, IndexError, ValueError):
        return "Taux historiques : estimations par défaut (backtest non disponible)"


def load_picks(date_str: str) -> dict:
    """Rapports du jour ; « latest » = le plus récent (généré le dernier)."""
    result = {"morning": [], "evening": [], "yesterday": None, "latest": None, "latest_at": ""}
    for suffix in ["morning", "evening"]:
        path = PICKS_DIR / f"{date_str}_{suffix}.json"
        if path.exists():
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            result[suffix] = data.get("picks", [])
            if result["yesterday"] is None:
                result["yesterday"] = data.get("yesterday")
            # anciens fichiers sans horodatage : le soir l'emporte sur le matin
            stamp = data.get("generated_at") or ("0" if suffix == "morning" else "1")
            if result["latest"] is None or stamp >= result["latest_at"]:
                result["latest"], result["latest_at"] = suffix, stamp
    return result


def proba_color(proba) -> str:
    if proba is None: return "var(--muted)"
    if proba >= 75:   return "#22c55e"
    if proba >= 65:   return "#84cc16"
    if proba >= 55:   return "#eab308"
    return "#f97316"


STAR_COLORS = {5: "#22c55e", 4: "#84cc16", 3: "#eab308", 2: "#f97316", 1: "#ef4444"}


def fmt_stars(stars, label) -> str:
    if not stars:
        return '<span class="bet-value">—</span>'
    return (f'<span class="bet-stars" style="color:{STAR_COLORS[stars]}">'
            f'{"★" * stars}{"☆" * (5 - stars)}</span>'
            f'<span class="bet-n">{label}</span>')


def fmt_value(v) -> str:
    if v is None:
        return "—"
    color = "#22c55e" if v > 0 else "#94a3b8" if v > -3 else "#f97316"
    return f'<span style="color:{color}">{v:+.1f}%</span>'


def fmt_proba(proba) -> str:
    return "—" if proba is None else f"{proba:.0f}%"


def fmt_history(hist) -> str:
    """« 79% (n=48) » → 79% avec l'effectif en petit dessous."""
    if not hist or hist == "—":
        return "—"
    pct, _, n = hist.partition(" ")
    return f'{pct}<span class="bet-n">{n}</span>' if n else pct


def match_line(pick: dict) -> str:
    """Domicile – Extérieur."""
    home = pick.get("home_team") or pick.get("favori", "?")
    away = pick.get("away_team") or pick.get("adversaire", "?")
    return f'<span class="pick-team">{home}</span><span class="pick-vs">–</span><span class="pick-team">{away}</span>'


SIDE_ICON = {"Over": "⬆️", "Under": "⬇️"}


def pick_bets(pick: dict) -> list:
    """Paris d'un match : liste « paris » (format actuel) ou ancien pari unique."""
    if "paris" in pick:
        return pick["paris"]
    return [pick] if pick.get("pari") else []


def bet_side(bet: dict) -> str:
    return bet.get("side") or bet.get("ou_side") or str(bet.get("pari", "Over")).split(" ")[0]


def render_bet_row(side: str, bet: dict | None) -> str:
    icon = SIDE_ICON.get(side, "")
    if not bet:
        return (f'<div class="bet-row bet-none"><span class="bet-name">{icon} {side}</span>'
                f'<span class="bet-empty">— pas de ligne entre 1,20 et 1,50</span></div>')
    return f"""<div class="bet-row">
        <span class="bet-name">{icon} {bet['pari'].replace(' buts', '')}</span>
        <span class="bet-value">{bet['cote']}</span>
        <span class="bet-value bet-proba" style="color:{proba_color(bet.get('proba'))}">{fmt_proba(bet.get('proba'))}</span>
        <span>{fmt_stars(bet.get('etoiles'), bet.get('note'))}</span>
      </div>"""


def render_pick_card(pick: dict) -> str:
    bets = {bet_side(b): b for b in pick_bets(pick)}
    if bets:
        rows = "".join(render_bet_row(side, bets.get(side)) for side in ("Over", "Under"))
        source = next((b.get("cote_source") for b in bets.values() if b.get("cote_source")), None)
        body = f"""
      <div class="bet-head"><span>Pari (buts)</span><span>Cote</span><span>Probabilité</span><span>Note</span></div>
      {rows}
      <div class="bet-ref">Cotes : {source or '—'}</div>"""
    else:
        body = '<div class="bet-ref">Cotes Over/Under indisponibles pour ce match</div>'
    return f"""
    <div class="pick-card">
      <div class="pick-sport">{pick.get('sport', '⚽ Football')}</div>
      <div class="pick-header">{pick['heure']} · {pick['championnat']}</div>
      <div class="pick-match">{match_line(pick)}</div>{body}
    </div>"""


def render_yesterday_card(pick: dict) -> str:
    bets = pick_bets(pick)
    results = [b.get("result", pick.get("result")) for b in bets]
    if results and all(r == "win" for r in results):
        border, bg = "#22c55e", "#14532d"
    elif results and all(r == "loss" for r in results):
        border, bg = "#ef4444", "#7f1d1d"
    else:
        border, bg = "#475569", "#1e293b"
    icon = {"win": "✅", "loss": "❌"}
    lines = "".join(
        f'<div class="yest-meta">{icon.get(b.get("result", pick.get("result")), "⏳")} '
        f'{b.get("pari", "?")} @ {b.get("cote", "?")} · {fmt_proba(b.get("proba"))}</div>'
        for b in bets)
    return f"""
    <div class="yest-card" style="border-color:{border};background:{bg}">
      <div class="yest-result">{pick.get('result_label', '⏳ Inconnu')}</div>
      <div class="yest-match">{match_line(pick)}</div>
      {lines}
      <div class="yest-meta">{pick.get('championnat', '?')} · {pick.get('heure', '?')}</div>
    </div>"""


def render_yesterday_section(yesterday: dict | None) -> str:
    if not yesterday or not yesterday.get("resolved"):
        return ""

    resolved = yesterday["resolved"]
    wins     = yesterday.get("wins", 0)
    losses   = yesterday.get("losses", 0)
    total    = yesterday.get("total", 0)
    win_rate = yesterday.get("win_rate")
    date_str = yesterday.get("date", "")

    rate_str = f"{win_rate}%" if win_rate is not None else "—"
    rate_color = "#22c55e" if (win_rate or 0) >= 70 else "#eab308" if (win_rate or 0) >= 55 else "#ef4444"

    cards = "\n".join(render_yesterday_card(p) for p in resolved)

    return f"""
    <section class="section">
      <h2>📋 Résultats de la veille <span class="date-badge">{date_str}</span></h2>
      <div class="yest-summary">
        <div class="yest-stat">
          <span class="yest-num" style="color:#22c55e">{wins}</span>
          <span class="yest-label">Validés</span>
        </div>
        <div class="yest-stat">
          <span class="yest-num" style="color:#ef4444">{losses}</span>
          <span class="yest-label">Ratés</span>
        </div>
        <div class="yest-stat">
          <span class="yest-num" style="color:{rate_color}">{rate_str}</span>
          <span class="yest-label">Taux</span>
        </div>
        <div class="yest-stat">
          <span class="yest-num" style="color:#94a3b8">{total}</span>
          <span class="yest-label">Résolus</span>
        </div>
      </div>
      <div class="yest-grid">{cards}</div>
    </section>"""


TRACKING_PATH = PICKS_DIR / "suivi.json"
PROBA_RANGES = [(0, 60, "moins de 60 %"), (60, 70, "60 – 70 %"), (70, 80, "70 – 80 %"),
                (80, 90, "80 – 90 %"), (90, 101, "90 % et plus")]


def render_tracking_section() -> str:
    """Annoncé contre réalisé, cumulé depuis le début du suivi."""
    try:
        with open(TRACKING_PATH, encoding="utf-8") as f:
            log = json.load(f)
    except (OSError, ValueError):
        log = []
    title = "<h2>📈 Suivi de fiabilité — annoncé contre réalisé</h2>"
    if not log:
        return (f'<section class="section">{title}<p class="empty">Le suivi démarre : '
                f"les résultats s'ajoutent chaque matin.</p></section>")

    def row(label, rs):
        n = len(rs)
        if not n:
            return ""
        won = sum(r["result"] == "win" for r in rs)
        real = won / n * 100
        pred = sum(r["proba"] for r in rs) / n
        gain = sum((r["cote"] - 1) if r["result"] == "win" else -1 for r in rs) / n * 100
        gap = round(real - pred)
        gap_color = "#22c55e" if gap >= 0 else "#f97316"
        return (f"<tr><td>{label}</td><td>{n}</td><td>{pred:.0f}%</td><td>{real:.0f}%</td>"
                f"<td style='color:{gap_color}'>{gap:+d}</td><td>{gain:+.1f}%</td></tr>")

    by_proba = "".join(row(label, [r for r in log if lo <= r["proba"] < hi])
                       for lo, hi, label in PROBA_RANGES)
    by_stars = "".join(row("★" * k + "☆" * (5 - k), [r for r in log if r.get("etoiles") == k])
                       for k in range(5, 0, -1))
    total_row = row("Total", log)
    side_of = lambda r: r.get("side") or str(r.get("pari", "")).split(" ")[0]
    by_side = "".join(row(f"{SIDE_ICON[sd]} {sd}", [r for r in log if side_of(r) == sd])
                      for sd in ("Over", "Under"))
    first, last = min(r["date"] for r in log), max(r["date"] for r in log)
    return f"""
    <section class="section">
      {title}
      <p class="track-note">{len(log)} paris résolus du {first} au {last}.
        « Écart » = réalisé − annoncé, en points. « Gain » = résultat moyen d'une mise de 1 à la cote affichée.
        Il faut plusieurs centaines de paris pour que ces chiffres soient significatifs.</p>
      <table class="track">
        <tr><th>Probabilité</th><th>Paris</th><th>Annoncé</th><th>Réalisé</th>
            <th>Écart</th><th>Gain</th></tr>
        {by_proba}
        {total_row}
      </table>
      <table class="track">
        <tr><th>Note</th><th>Paris</th><th>Annoncé</th><th>Réalisé</th>
            <th>Écart</th><th>Gain</th></tr>
        {by_stars}
      </table>
      <table class="track">
        <tr><th>Type</th><th>Paris</th><th>Annoncé</th><th>Réalisé</th>
            <th>Écart</th><th>Gain</th></tr>
        {by_side}
      </table>
    </section>"""


def render_picks_section(title: str, picks: list, empty_msg: str) -> str:
    if not picks:
        return f"""
    <section class="section">
      <h2>{title}</h2>
      <p class="empty">{empty_msg}</p>
    </section>"""
    cards = "\n".join(render_pick_card(p) for p in picks)
    return f"""
    <section class="section">
      <h2>{title} <span class="count">{len(picks)} matchs</span></h2>
      <div class="picks-grid">{cards}</div>
    </section>"""


def get_history_links() -> str:
    files = sorted(PICKS_DIR.glob("*_morning.json"), reverse=True)[:10]
    if not files:
        return ""
    links = [f'<a href="picks/{f.stem.replace("_morning","")}_morning.json">'
             f'{f.stem.replace("_morning","")}</a>' for f in files]
    return "<div class='history'><strong>Historique :</strong> " + " · ".join(links) + "</div>"


def generate_index(date_str: str, picks: dict):
    now_fr   = datetime.now(TZ_FRANCE).strftime("%d/%m/%Y à %Hh%M")
    yest_sec = render_yesterday_section(picks.get("yesterday"))
    # Une seule liste : le rapport le plus récent (matin ou mise à jour)
    stamp = picks.get("latest_at", "")
    at = f"{stamp[11:13]}h{stamp[14:16]}" if len(stamp) >= 16 else ""
    if picks.get("latest") == "evening":
        current = picks["evening"]
        day_sec = render_picks_section(
            f"🌆 Matchs à venir — mise à jour{' de ' + at if at else ''}", current,
            "Plus aucun match à venir aujourd'hui dans les championnats suivis.")
    else:
        current = picks["morning"]
        day_sec = render_picks_section(
            f"🌅 Matchs du jour — rapport{' de ' + at if at else ' du matin'}", current,
            "Aucun match aujourd'hui dans les championnats suivis.")
    total    = len(current)
    history  = get_history_links()
    track_sec = render_tracking_section()

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <title>Sharp-Edge — {date_str}</title>
  <style>
    :root {{
      --bg:#0f172a; --surface:#1e293b; --border:#334155;
      --text:#f1f5f9; --muted:#94a3b8; --accent:#38bdf8;
    }}
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
          background:var(--bg);color:var(--text);
          padding:env(safe-area-inset-top,0) 0 env(safe-area-inset-bottom,0);
          min-height:100vh}}
    header{{background:var(--surface);border-bottom:1px solid var(--border);
            padding:1.25rem 1.5rem;display:flex;justify-content:space-between;
            align-items:center;flex-wrap:wrap;gap:.5rem}}
    .logo{{font-size:1.4rem;font-weight:700;color:var(--accent)}}
    .meta{{font-size:.8rem;color:var(--muted)}}
    .badge{{background:var(--accent);color:#0f172a;padding:.2rem .6rem;
            border-radius:999px;font-size:.75rem;font-weight:700}}
    main{{max-width:960px;margin:0 auto;padding:1.5rem 1rem}}
    .section{{margin-bottom:2.5rem}}
    h2{{font-size:1.05rem;margin-bottom:1rem;color:var(--muted);
        display:flex;align-items:center;gap:.75rem;flex-wrap:wrap}}
    .count,.date-badge{{background:var(--border);padding:.15rem .5rem;
                        border-radius:999px;font-size:.72rem}}
    /* Picks du jour */
    .picks-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(270px,1fr));gap:1rem}}
    .pick-card{{background:var(--surface);border:1px solid var(--border);
                border-radius:.75rem;padding:1rem;display:flex;flex-direction:column;gap:.6rem}}
    .pick-sport{{font-size:.75rem;color:var(--muted)}}
    .pick-header{{font-size:.8rem;color:var(--muted)}}
    .pick-match{{display:flex;align-items:center;gap:.5rem;flex-wrap:wrap}}
    .pick-team{{font-weight:700;font-size:1rem}}
    .pick-vs{{color:var(--muted);font-size:.8rem}}
    .bet-head,.bet-row{{display:grid;grid-template-columns:1.6fr .6fr .9fr 1.1fr;gap:.4rem;align-items:center}}
    .bet-head{{font-size:.68rem;color:var(--muted);border-top:1px solid var(--border);padding-top:.6rem}}
    .bet-row{{padding:.15rem 0}}
    .bet-none{{grid-template-columns:1.6fr 2.6fr}}
    .bet-name{{font-weight:700;font-size:.88rem}}
    .bet-empty{{font-size:.75rem;color:var(--muted)}}
    .bet-stars{{display:block;font-size:.95rem;letter-spacing:.03em;line-height:1.3}}
    .bet-n{{display:block;font-size:.65rem;font-weight:400;color:var(--muted)}}
    .bet-label{{display:block;font-size:.68rem;color:var(--muted)}}
    .bet-value{{font-size:.9rem;font-weight:600}}
    .bet-proba{{font-size:1.05rem;font-weight:800}}
    .bet-ref{{font-size:.72rem;color:var(--muted)}}
    /* Résultats veille */
    .yest-summary{{display:flex;gap:1.5rem;margin-bottom:1rem;flex-wrap:wrap}}
    .yest-stat{{text-align:center}}
    .yest-num{{display:block;font-size:1.6rem;font-weight:800}}
    .yest-label{{font-size:.75rem;color:var(--muted)}}
    .yest-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:.75rem}}
    .yest-card{{border:1px solid;border-radius:.65rem;padding:.85rem;display:flex;
                flex-direction:column;gap:.4rem}}
    .yest-result{{font-size:.85rem;font-weight:700}}
    .yest-match{{font-size:.9rem;display:flex;align-items:center;gap:.4rem;flex-wrap:wrap}}
    .yest-meta{{font-size:.75rem;color:var(--muted)}}
    /* Suivi */
    .track{{width:100%;border-collapse:collapse;font-size:.78rem;margin-bottom:1rem;
            background:var(--surface);border-radius:.5rem;overflow:hidden}}
    .track th,.track td{{padding:.45rem .5rem;text-align:right;border-bottom:1px solid var(--border);
                         white-space:nowrap}}
    .track th:first-child,.track td:first-child{{text-align:left}}
    .track th{{color:var(--muted);font-weight:600}}
    .track-note{{font-size:.75rem;color:var(--muted);margin-bottom:.75rem}}
    /* Bouton de mise à jour */
    .update-btn{{background:var(--surface);color:var(--text);border:1px solid var(--border);
                 border-radius:999px;padding:.3rem .8rem;font-size:.78rem;cursor:pointer}}
    .update-btn:disabled{{opacity:.5;cursor:wait}}
    .update-status{{background:var(--surface);border:1px solid var(--border);border-radius:.5rem;
                    padding:.6rem .8rem;margin-bottom:1rem;font-size:.85rem}}
    .update-panel{{background:var(--surface);border:1px solid var(--accent);border-radius:.75rem;
                   padding:1rem;margin-bottom:1.5rem;font-size:.85rem;line-height:1.5}}
    .update-panel ol{{margin:.5rem 0 .75rem 1.25rem}}
    .update-panel a{{color:var(--accent)}}
    .token-row{{display:flex;gap:.5rem;flex-wrap:wrap}}
    .token-row input{{flex:1;min-width:200px;padding:.45rem .6rem;border-radius:.4rem;
                      border:1px solid var(--border);background:var(--bg);color:var(--text)}}
    .token-row button{{padding:.45rem .8rem;border-radius:.4rem;border:0;background:var(--accent);
                       color:#0f172a;font-weight:700;cursor:pointer}}
    .token-help{{margin-top:.6rem;font-size:.75rem;color:var(--muted)}}
    .link-btn{{background:none;border:0;color:var(--accent);cursor:pointer;font-size:.75rem;padding:0}}
    /* Misc */
    .empty{{color:var(--muted);font-style:italic;padding:1rem;background:var(--surface);
            border-radius:.5rem;border:1px solid var(--border)}}
    .history{{margin-top:2rem;font-size:.8rem;color:var(--muted)}}
    .history a{{color:var(--accent);text-decoration:none;margin:0 .2rem}}
    footer{{text-align:center;padding:2rem 1rem;font-size:.75rem;color:var(--muted);
            border-top:1px solid var(--border)}}
    @media(max-width:480px){{.picks-grid,.yest-grid{{grid-template-columns:1fr}}}}
  </style>
</head>
<body>
  <header>
    <div>
      <div class="logo">⚡ Sharp-Edge</div>
      <div class="meta">Probabilités Over/Under — matchs du jour</div>
    </div>
    <div style="display:flex;align-items:center;gap:.75rem">
      <span class="meta">{date_str} · MàJ {now_fr}</span>
      <span class="badge">{total} matchs</span>
      <button id="update-btn" class="update-btn" type="button">🔄 Mettre à jour</button>
    </div>
  </header>
  <main>
    <p id="update-status" class="update-status" hidden></p>
    <div id="update-panel" class="update-panel" hidden>
      <p><strong>Première utilisation</strong> : crée un jeton GitHub limité à ce dépôt
        (il reste enregistré dans ce navigateur uniquement).</p>
      <ol>
        <li>Ouvre <a href="https://github.com/settings/personal-access-tokens/new" target="_blank" rel="noopener">GitHub → nouveau jeton « fine-grained »</a></li>
        <li><em>Repository access</em> : <em>Only select repositories</em> → <strong>sharp-edge</strong></li>
        <li><em>Permissions</em> → <em>Repository</em> → <strong>Actions : Read and write</strong> (rien d'autre)</li>
        <li>Génère le jeton et colle-le ici :</li>
      </ol>
      <div class="token-row">
        <input id="token-input" type="password" autocomplete="off" placeholder="github_pat_…">
        <button id="token-save" type="button">Enregistrer et lancer</button>
      </div>
      <p class="token-help"><a id="actions-link" href="#" target="_blank" rel="noopener">Ou lancer depuis GitHub</a>
        · <button id="token-forget" type="button" class="link-btn">Oublier le jeton</button></p>
    </div>
    {yest_sec}
    {day_sec}
    {track_sec}
    {history}
  </main>
  <footer>
    Sharp-Edge — outil d'analyse statistique uniquement. Ne constitue pas un conseil en paris.<br>
    Sources : football-data.co.uk · The Odds API · 18 championnats/compétitions actifs<br>
    {calibration_note()}
  </footer>
  <script src="update.js"></script>
</body>
</html>"""

    output = DOCS_DIR / "index.html"
    with open(output, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✓ Page générée → {output}")


def main():
    now_fr   = datetime.now(TZ_FRANCE)
    date_str = now_fr.strftime("%Y-%m-%d")
    picks    = load_picks(date_str)
    generate_index(date_str, picks)
    total = len(picks["morning"]) + len(picks["evening"])
    print(f"  Matin : {len(picks['morning'])} matchs | Soir : {len(picks['evening'])} matchs | Total : {total}")


if __name__ == "__main__":
    main()
