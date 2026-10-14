"""
sharp-edge | Script 4 — Génération de la page HTML GitHub Pages
"""

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

TZ_FRANCE = timezone(timedelta(hours=1))
DOCS_DIR  = Path(__file__).parent.parent / "docs"
PICKS_DIR = DOCS_DIR / "picks"
DOCS_DIR.mkdir(exist_ok=True)
PICKS_DIR.mkdir(exist_ok=True)


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


def fiability_color(fiabilite: str) -> str:
    if "Très solide" in fiabilite: return "#22c55e"
    elif "Solide"     in fiabilite: return "#84cc16"
    elif "Correct"    in fiabilite: return "#eab308"
    else:                           return "#f97316"


def render_pick_card(pick: dict) -> str:
    color    = fiability_color(pick["fiabilite"])
    status_bg = "#166534" if "Jouer" in pick["status"] else "#854d0e"
    return f"""
    <div class="pick-card">
      <div class="pick-status" style="background:{status_bg}">{pick['status']}</div>
      <div class="pick-header">
        <span class="pick-time">{pick['heure']}</span>
        <span class="pick-league">{pick['championnat']}</span>
      </div>
      <div class="pick-match">
        <span class="pick-fav">{pick['favori']}</span>
        <span class="pick-vs">vs</span>
        <span class="pick-opp">{pick['adversaire']}</span>
      </div>
      <div class="pick-details">
        <div class="pick-odds">
          <span class="odds-label">Cote</span>
          <span class="odds-value" style="color:{color}">{pick['cote']}</span>
        </div>
        <div class="pick-pct">
          <span class="pct-label">Historique</span>
          <span class="pct-value">{pick['pct_victoire_historique']}</span>
        </div>
      </div>
      <div class="pick-fiability" style="color:{color}">{pick['fiabilite']}</div>
      <div class="pick-bet">📋 {pick['pari']} — réf. {pick['bookmaker_ref']}</div>
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
        <strong>{pick.get('favori','?')}</strong>
        <span class="pick-vs">vs</span>
        {pick.get('adversaire','?')}
      </div>
      <div class="yest-meta">
        {pick.get('championnat','?')} · {pick.get('heure','?')} · cote {pick.get('cote','?')}
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
      <h2>{title} <span class="count">{len(picks)} picks</span></h2>
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
        "🌅 Rapport 4h30 — Picks du jour", picks["morning"],
        "Aucun pick validé ce matin.")
    even_sec = render_picks_section(
        "🌆 Rapport 16h30 — Confirmation matchs du soir", picks["evening"],
        "Rapport du soir non encore généré ou aucun match à confirmer.")
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
    .pick-status{{display:inline-block;padding:.2rem .6rem;border-radius:.4rem;
                  font-size:.72rem;font-weight:600;width:fit-content}}
    .pick-header{{display:flex;justify-content:space-between;font-size:.8rem;color:var(--muted)}}
    .pick-match{{display:flex;align-items:center;gap:.5rem;flex-wrap:wrap}}
    .pick-fav{{font-weight:700;font-size:1rem}}
    .pick-vs{{color:var(--muted);font-size:.8rem}}
    .pick-opp{{color:var(--muted);font-size:.9rem}}
    .pick-details{{display:flex;gap:1.5rem}}
    .odds-label,.pct-label{{display:block;font-size:.7rem;color:var(--muted)}}
    .odds-value{{font-size:1.4rem;font-weight:800}}
    .pct-value{{font-size:.95rem;font-weight:600}}
    .pick-fiability{{font-size:.8rem;font-weight:600}}
    .pick-bet{{font-size:.75rem;color:var(--muted);border-top:1px solid var(--border);padding-top:.5rem}}
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
      <div class="meta">Sports betting filter — low odds favourites</div>
    </div>
    <div style="display:flex;align-items:center;gap:.75rem">
      <span class="meta">{date_str} · MàJ {now_fr}</span>
      <span class="badge">{total} picks</span>
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
    Sources : football-data.co.uk · The Odds API · 18 championnats/compétitions actifs
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
    print(f"  Matin : {len(picks['morning'])} picks | Soir : {len(picks['evening'])} picks | Total : {total}")


if __name__ == "__main__":
    main()
