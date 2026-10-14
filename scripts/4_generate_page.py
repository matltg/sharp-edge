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
    result = {"morning": [], "evening": [], "yesterday": None}
    for suffix in ["morning", "evening"]:
        path = PICKS_DIR / f"{date_str}_{suffix}.json"
        if path.exists():
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
                result[suffix] = data.get("picks", [])
                if result["yesterday"] is None:
                    result["yesterday"] = data.get("yesterday")
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


def render_pick_card(pick: dict) -> str:
    status_bg = "#854d0e" if "confirmer" in pick["status"] else "#166534"
    if pick.get("pari"):
        note = "" if pick.get("dans_fenetre", True) else " · hors fenêtre 1,20–1,50"
        bet = f"""
      <div class="bet-name">{pick['pari']}</div>
      <div class="bet-grid">
        <div><span class="bet-label">Cote</span><span class="bet-value">{pick['cote']}</span></div>
        <div><span class="bet-label">Probabilité</span>
             <span class="bet-value bet-proba" style="color:{proba_color(pick.get('proba'))}">{fmt_proba(pick.get('proba'))}</span></div>
        <div><span class="bet-label">Note</span>{fmt_stars(pick.get('etoiles'), pick.get('note'))}</div>
      </div>
      <div class="bet-ref">Cote : {pick.get('cote_source') or pick.get('bookmaker_ref', '—')}{note}</div>"""
    else:
        bet = '<div class="bet-ref">Cotes Over/Under indisponibles pour ce match</div>'
    return f"""
    <div class="pick-card">
      <div class="pick-top">
        <span class="pick-sport">{pick.get('sport', '⚽ Football')}</span>
        <span class="pick-status" style="background:{status_bg}">{pick['status']}</span>
      </div>
      <div class="pick-header">{pick['heure']} · {pick['championnat']}</div>
      <div class="pick-match">{match_line(pick)}</div>{bet}
    </div>"""


def render_yesterday_card(pick: dict) -> str:
    result = pick.get("result", "unknown")
    label  = pick.get("result_label", "⏳ Inconnu")
    if result == "win":
        border = "#22c55e"; bg = "#14532d"
    elif result == "loss":
        border = "#ef4444"; bg = "#7f1d1d"
    else:
        border = "#475569"; bg = "#1e293b"

    return f"""
    <div class="yest-card" style="border-color:{border};background:{bg}">
      <div class="yest-result">{label}</div>
      <div class="yest-match">
        {match_line(pick)}
      </div>
      <div class="yest-meta">
        {pick.get('pari','?')} @ {pick.get('cote','?')} · {pick.get('championnat','?')} · {pick.get('heure','?')}
      </div>
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
    total    = len(picks["morning"]) + len(picks["evening"])
    yest_sec = render_yesterday_section(picks.get("yesterday"))
    morn_sec = render_picks_section(
        "🌅 Rapport 4h30 — Matchs du jour", picks["morning"],
        "Aucun match aujourd'hui dans les championnats suivis.")
    even_sec = render_picks_section(
        "🌆 Rapport 16h30 — Confirmation matchs du soir", picks["evening"],
        "Rapport du soir non encore généré ou aucun match après 18h.")
    history  = get_history_links()

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
    .pick-top{{display:flex;justify-content:space-between;align-items:center;gap:.5rem}}
    .pick-sport{{font-size:.75rem;color:var(--muted)}}
    .pick-status{{display:inline-block;padding:.2rem .6rem;border-radius:.4rem;
                  font-size:.72rem;font-weight:600;width:fit-content}}
    .pick-header{{font-size:.8rem;color:var(--muted)}}
    .pick-match{{display:flex;align-items:center;gap:.5rem;flex-wrap:wrap}}
    .pick-team{{font-weight:700;font-size:1rem}}
    .pick-vs{{color:var(--muted);font-size:.8rem}}
    .bet-name{{font-weight:700;font-size:.95rem;border-top:1px solid var(--border);padding-top:.6rem}}
    .bet-grid{{display:grid;grid-template-columns:.8fr 1fr 1.4fr;gap:.5rem}}
    .bet-stars{{display:block;font-size:1.05rem;letter-spacing:.05em;line-height:1.4}}
    .bet-n{{display:block;font-size:.65rem;font-weight:400;color:var(--muted)}}
    .bet-label{{display:block;font-size:.68rem;color:var(--muted)}}
    .bet-value{{font-size:.9rem;font-weight:600}}
    .bet-proba{{font-size:1.15rem;font-weight:800}}
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
    </div>
  </header>
  <main>
    {yest_sec}
    {morn_sec}
    {even_sec}
    {history}
  </main>
  <footer>
    Sharp-Edge — outil d'analyse statistique uniquement. Ne constitue pas un conseil en paris.<br>
    Sources : football-data.co.uk · The Odds API · 18 championnats/compétitions actifs<br>
    {calibration_note()}
  </footer>
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
