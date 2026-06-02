# Showcase site (GitHub Pages)

The static showcase / explainer for the **UNIQA Conversion Coach** lives in this
`docs/` folder. It's a single self-contained page — no build step.

- `index.html` — the page
- `assets/css/styles.css` — styling
- `assets/js/main.js` — interactivity + charts (all numbers come from the real
  `leonardo_sim/artifacts/eval_metrics.json`, mirrored into the JS so the page
  stays accurate even if the engine isn't run client-side)
- `assets/img/*.png` — the authentic matplotlib evaluation artifacts, copied from
  `leonardo_sim/artifacts/`
- `.nojekyll` — disables Jekyll so asset paths are served verbatim

External libraries (Chart.js, Mermaid, Google Fonts) load from CDNs; everything
else is local.

## Publish it

**Recommended — GitHub Actions** (already wired up in
[`.github/workflows/pages.yml`](../.github/workflows/pages.yml)):

1. Repo **Settings → Pages**
2. **Source: GitHub Actions**
3. Push to `main` — the workflow deploys automatically.

**Or — deploy from branch** (no Actions):

1. Repo **Settings → Pages**
2. **Source: Deploy from a branch** → Branch `main` → Folder `/docs` → Save.

Live URL: `https://valgsgit.github.io/ZeroOneHack-PromptCorn-Sub/`

## Keeping the numbers in sync

If you re-run the evaluation (`./run.sh eval`), refresh the page by:

1. copying the regenerated charts:
   `cp leonardo_sim/artifacts/eval_*.png leonardo_sim/artifacts/classifier_eval.png docs/assets/img/`
2. updating the `METRICS` object at the top of `assets/js/main.js` from
   `leonardo_sim/artifacts/eval_metrics.json`.
