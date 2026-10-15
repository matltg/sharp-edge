// Sharp-Edge — bouton « Mettre à jour » : lance le workflow GitHub Actions de
// mise à jour depuis la page. Le jeton GitHub reste dans le navigateur
// (localStorage), il n'est jamais écrit dans la page publique.
(function () {
  const WORKFLOW = "evening.yml";          // mise à jour des matchs à venir
  const TOKEN_KEY = "sharp-edge-token";
  const owner = location.hostname.split(".")[0];
  const repo = location.pathname.split("/").filter(Boolean)[0] || "sharp-edge";
  const api = `https://api.github.com/repos/${owner}/${repo}/actions/workflows/${WORKFLOW}`;
  const actionsUrl = `https://github.com/${owner}/${repo}/actions/workflows/${WORKFLOW}`;

  const btn = document.getElementById("update-btn");
  const panel = document.getElementById("update-panel");
  const status = document.getElementById("update-status");
  if (!btn) return;

  const getToken = () => { try { return localStorage.getItem(TOKEN_KEY); } catch (e) { return null; } };
  const setToken = (t) => { try { localStorage.setItem(TOKEN_KEY, t); } catch (e) {} };
  const clearToken = () => { try { localStorage.removeItem(TOKEN_KEY); } catch (e) {} };
  const say = (msg) => { status.textContent = msg; status.hidden = false; };
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const headers = (t) => ({ Authorization: `Bearer ${t}`, Accept: "application/vnd.github+json" });

  function showSetup() {
    panel.hidden = false;
    document.getElementById("actions-link").href = actionsUrl;
  }

  document.getElementById("token-save").addEventListener("click", () => {
    const t = document.getElementById("token-input").value.trim();
    if (!t) return;
    setToken(t);
    document.getElementById("token-input").value = "";
    panel.hidden = true;
    launch();
  });
  document.getElementById("token-forget").addEventListener("click", () => {
    clearToken();
    say("Jeton effacé de ce navigateur.");
  });

  async function latestRunId(t) {
    const r = await fetch(`${api}/runs?per_page=1&event=workflow_dispatch`, { headers: headers(t) });
    if (!r.ok) return null;
    const runs = (await r.json()).workflow_runs || [];
    return runs.length ? runs[0] : null;
  }

  async function launch() {
    const t = getToken();
    if (!t) { showSetup(); return; }
    btn.disabled = true;
    const before = await latestRunId(t);
    say("Lancement de l'analyse…");
    const r = await fetch(`${api}/dispatches`, {
      method: "POST", headers: headers(t), body: JSON.stringify({ ref: "main" }),
    });
    if (r.status !== 204) {
      btn.disabled = false;
      if (r.status === 401 || r.status === 403 || r.status === 404) {
        clearToken();
        say(`Jeton refusé par GitHub (HTTP ${r.status}). Vérifie ses droits puis recommence.`);
        showSetup();
      } else {
        say(`Échec du lancement (HTTP ${r.status}).`);
      }
      return;
    }
    // Suivi : attendre le nouveau run, puis sa fin, puis la publication de la page
    const started = Date.now();
    let run = null;
    while (Date.now() - started < 10 * 60 * 1000) {
      await sleep(10000);
      const last = await latestRunId(t);
      if (last && (!before || last.id !== before.id)) run = last;
      if (!run) { say("Analyse en file d'attente chez GitHub…"); continue; }
      if (run.status !== "completed") { say("Analyse en cours… (1 à 2 minutes)"); continue; }
      if (run.conclusion !== "success") {
        btn.disabled = false;
        say(`L'analyse a échoué (${run.conclusion}). Détails sur GitHub Actions.`);
        return;
      }
      say("Analyse terminée, publication de la page… (environ 1 minute)");
      await sleep(60000);
      location.replace(location.pathname + "?t=" + Date.now());
      return;
    }
    btn.disabled = false;
    say("L'analyse prend plus de temps que prévu : recharge la page dans quelques minutes.");
  }

  btn.addEventListener("click", launch);
})();
