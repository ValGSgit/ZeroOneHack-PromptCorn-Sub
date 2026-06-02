/* ============================================================
   UNIQA Conversion Coach — showcase site logic
   All numbers below are the real outputs of
   leonardo_sim/evaluate.py → artifacts/eval_metrics.json
   ============================================================ */

const METRICS = {
  baseline: 0.048,
  coach: 0.17733,
  multiplier: 3.69,
  upliftPts: 12.93,
  persona: {
    Franz:  { baseline: 0.0633, coach: 0.2200, color: "#4f8cff" },
    Judith: { baseline: 0.0300, coach: 0.1467, color: "#c084fc" },
    Peter:  { baseline: 0.0367, coach: 0.1167, color: "#fbbf24" },
  },
  dropoff: {
    labels: ["1 cover", "2 for-whom", "3 personal", "4 init-price", "6 health-Q", "7 final-price", "12 close"],
    baseline: [0.1017, 0.0757, 0.0458, 0.6731, 0.0335, 0.8043, 0.0204],
    coach:    [0.1003, 0.0763, 0.0441, 0.4637, 0.0321, 0.5400, 0.0650],
  },
  quality: {
    precision: 0.7175, recall: 0.8699, annoyance: 0.2825, fired: 1062,
    mix: {
      "Simplify recommendation": 345,
      "Term glossary": 192,
      "Suggest online tariff": 129,
      "Advisor booking (proactive)": 128,
      "Market comparison": 124,
      "Value justification": 76,
      "Reassurance / transparency": 68,
    },
  },
};

const FONT = "Inter, sans-serif";
const GRID = "rgba(255,255,255,0.07)";
const TICK = "#9aa7bd";

/* ---------- NAV ---------- */
const nav = document.getElementById("nav");
const navToggle = document.getElementById("navToggle");
const navLinks = document.getElementById("navLinks");
addEventListener("scroll", () => nav.classList.toggle("scrolled", scrollY > 20));
navToggle.addEventListener("click", () => navLinks.classList.toggle("open"));
navLinks.querySelectorAll("a").forEach((a) => a.addEventListener("click", () => navLinks.classList.remove("open")));

/* ---------- reveal on scroll ---------- */
const io = new IntersectionObserver(
  (entries) => entries.forEach((e) => { if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); } }),
  { threshold: 0.12 }
);
document.querySelectorAll(".reveal").forEach((el) => io.observe(el));

/* ---------- count-up ---------- */
function countUp(el) {
  const target = parseFloat(el.dataset.count);
  const dec = parseInt(el.dataset.dec || "0");
  const suffix = el.dataset.suffix || "";
  const prefix = target >= 100 ? "" : "";
  const dur = 1400;
  const start = performance.now();
  function tick(now) {
    const p = Math.min((now - start) / dur, 1);
    const eased = 1 - Math.pow(1 - p, 3);
    const val = target * eased;
    el.textContent = (val >= 1000 ? Math.round(val).toLocaleString() : val.toFixed(dec)) + suffix;
    if (p < 1) requestAnimationFrame(tick);
    else el.textContent = (target >= 1000 ? Math.round(target).toLocaleString() : target.toFixed(dec)) + suffix;
  }
  requestAnimationFrame(tick);
}
const countIO = new IntersectionObserver((entries) => entries.forEach((e) => {
  if (e.isIntersecting) { countUp(e.target); countIO.unobserve(e.target); }
}), { threshold: 0.5 });
document.querySelectorAll("[data-count]").forEach((el) => countIO.observe(el));

/* ---------- FUNNEL viz (problem section) ---------- */
(function buildFunnel() {
  const viz = document.getElementById("funnelViz");
  const steps = [
    { name: "Start", pct: 100, cliff: false },
    { name: "Coverage", pct: 89.8, cliff: false },
    { name: "For whom", pct: 83.0, cliff: false },
    { name: "Personal data", pct: 79.2, cliff: false },
    { name: "Initial price", pct: 25.9, cliff: true, flag: "66% cliff" },
    { name: "Health questions", pct: 25.0, cliff: false },
    { name: "Final price", pct: 4.9, cliff: true, flag: "78% cliff" },
    { name: "Closing", pct: 4.8, cliff: false },
  ];
  steps.forEach((s) => {
    const row = document.createElement("div");
    row.className = "funnel-bar-row";
    row.innerHTML = `<span class="step-name">${s.name}</span>
      <div class="funnel-track"><div class="funnel-fill ${s.cliff ? "cliff" : ""}" data-w="${s.pct}">${s.pct}%</div></div>`;
    viz.appendChild(row);
    if (s.flag) {
      const flag = document.createElement("div");
      flag.className = "cliff-flag";
      flag.textContent = `↳ ${s.flag} — the surviving cohort collapses here`;
      viz.appendChild(flag);
    }
  });
  const fillIO = new IntersectionObserver((entries) => {
    if (entries[0].isIntersecting) {
      viz.querySelectorAll(".funnel-fill").forEach((f, i) =>
        setTimeout(() => (f.style.width = f.dataset.w + "%"), i * 90));
      fillIO.disconnect();
    }
  }, { threshold: 0.3 });
  fillIO.observe(viz);
})();

/* ---------- PERSONA tabs (content section) ---------- */
const personaTabs = document.querySelectorAll("#personaTabs .persona-tab");
const personaPanels = document.querySelectorAll(".persona-panel");
personaTabs.forEach((tab) => tab.addEventListener("click", () => {
  const p = tab.dataset.p;
  personaTabs.forEach((t) => t.classList.toggle("active", t === tab));
  personaPanels.forEach((panel) => panel.classList.toggle("active", panel.dataset.p === p));
}));

/* ============================================================
   INTERACTIVE DEMO
   ============================================================ */
const DEMO = {
  franz: {
    hint: "Drops at: final price (step 7) · color online",
    color: "#4f8cff",
    steps: ["Coverage", "For whom", "Personal", "Init price", "Health Q", "Final price", "Close"],
    risk:  [12, 10, 16, 44, 30, 88, 18],
    leaveIdx: 5,
    leaveMsg: "ABANDONED at the final price — €68 estimate became €74 with no explanation.",
    interventions: {
      3: { trig: "[rule:repeated_back_navigation | seg=online | best]", msg: "Optimal sits below ~80% of comparable private-doctor tariffs for this cover — fully online, no advisor needed." },
      5: { trig: "[rule:final_price_jump | seg=online | best]", msg: "That €74 includes your risk surcharge — here's the one-line breakdown, still below market median. Nothing left to decide; tap continue." },
    },
    win: "CONVERTED online ✓ — shown the data, never pushed to an advisor.",
  },
  judith: {
    hint: "Drops at: initial price (step 4) · color hybrid",
    color: "#c084fc",
    steps: ["Coverage", "For whom", "Personal", "Init price", "Health Q", "Final price", "Close"],
    risk:  [15, 12, 22, 72, 40, 58, 22],
    leaveIdx: 3,
    leaveMsg: "ABANDONED at the initial price — unfamiliar terms, two tariffs advisor-only. \"I'll come back and call.\"",
    interventions: {
      3: { trig: "[risk=0.55 | seg=hybrid | dropoff | best]", msg: "Quick glossary: 'refractive eye surgery' = laser vision correction; 'medical aids' = hearing aids, orthotics. Hover any term." },
      5: { trig: "[rule:repeated_back_navigation | seg=hybrid | best]", msg: "The small increase is your risk surcharge — fair value for this cover. You're one step from done." },
    },
    win: "CONVERTED online ✓ — the terms were explained at the exact moment she hesitated.",
  },
  peter: {
    hint: "Drops at: early, steps 1–3 (overwhelm) · color service",
    color: "#fbbf24",
    steps: ["Coverage", "For whom", "Personal", "Init price", "Health Q", "Final price", "Close"],
    risk:  [28, 34, 70, 52, 40, 44, 18],
    leaveIdx: 2,
    leaveMsg: "ABANDONED early — too many numbers, no 'recommended for you'. Closed the tab to call instead.",
    interventions: {
      2: { trig: "[rule:repeated_back_navigation | seg=service | dropoff | best]", msg: "This is a lot to take in. Want a quick callback? An advisor can walk you through it in 5 minutes — no need to figure it out alone." },
      3: { trig: "[risk=0.99 | seg=service | best]", msg: "Most people with your needs pick Optimal — solid cover, fully online, no advisor needed. One click to continue." },
    },
    win: "CONVERTED — or a warm callback booked ✓. For Peter, a clean handoff is a correct exit, counted separately.",
  },
};

const demo = {
  persona: "franz",
  idx: -1,
  ended: false,
  coachOn: true,
};

const elSteps = document.getElementById("demoSteps");
const elRiskFill = document.getElementById("riskFill");
const elRiskPct = document.getElementById("riskPct");
const elBubble = document.getElementById("coachBubble");
const elTrigger = document.getElementById("coachTrigger");
const elMsg = document.getElementById("coachMsg");
const elOutcome = document.getElementById("demoOutcome");
const elHint = document.getElementById("demoPersonaHint");
const btnNext = document.getElementById("demoNext");
const btnReset = document.getElementById("demoReset");
const coachToggle = document.getElementById("coachToggle");

function riskColor(r) {
  if (r < 35) return "#34d399";
  if (r < 65) return "#fbbf24";
  return "#f87171";
}

function renderSteps() {
  const cfg = DEMO[demo.persona];
  elSteps.innerHTML = "";
  cfg.steps.forEach((name, i) => {
    const d = document.createElement("div");
    d.className = "demo-step";
    if (i < demo.idx) d.classList.add("done");
    if (i === demo.idx) d.classList.add(demo.ended && !demo.won ? "left" : "current");
    d.innerHTML = `<span class="dn">${i + 1}</span>${name}`;
    elSteps.appendChild(d);
  });
}

function resetDemo() {
  demo.idx = -1; demo.ended = false; demo.won = false;
  const cfg = DEMO[demo.persona];
  elHint.textContent = cfg.hint;
  elRiskFill.style.width = "0%";
  elRiskFill.style.background = "#34d399";
  elRiskPct.textContent = "0%";
  elBubble.classList.remove("show");
  elOutcome.classList.remove("show");
  elOutcome.innerHTML = "";
  btnNext.disabled = false;
  btnNext.textContent = "Next step →";
  renderSteps();
}

function nextStep() {
  if (demo.ended) return;
  const cfg = DEMO[demo.persona];
  demo.idx++;
  if (demo.idx >= cfg.steps.length) { finish(true); return; }

  let r = cfg.risk[demo.idx];
  const intervention = cfg.interventions[demo.idx];
  const isLeavePoint = demo.idx === cfg.leaveIdx;

  // Coach fires at scripted intervention steps when enabled
  if (demo.coachOn && intervention) {
    elTrigger.textContent = "⚡ coach fired  " + intervention.trig;
    elMsg.textContent = intervention.msg;
    elBubble.classList.add("show");
    // the intervention defuses the risk
    r = Math.min(r, 30);
  } else {
    elBubble.classList.remove("show");
  }

  // update meter
  elRiskFill.style.width = r + "%";
  elRiskFill.style.background = riskColor(r);
  elRiskPct.textContent = Math.round(r) + "%";

  renderSteps();

  // leave logic when coach is off (or didn't catch this segment's drop point)
  if (!demo.coachOn && isLeavePoint && cfg.risk[demo.idx] >= 65) {
    finish(false);
    return;
  }
  if (demo.idx === cfg.steps.length - 1) finish(true);
}

function finish(won) {
  demo.ended = true;
  demo.won = won;
  const cfg = DEMO[demo.persona];
  btnNext.disabled = true;
  renderSteps();
  elOutcome.classList.add("show");
  if (won) {
    elOutcome.innerHTML = `<span class="ok">✓ ${cfg.win}</span>`;
  } else {
    elBubble.classList.remove("show");
    elRiskFill.style.width = "100%";
    elRiskFill.style.background = "#f87171";
    elRiskPct.textContent = "left";
    elOutcome.innerHTML = `<span class="bad">✕ ${cfg.leaveMsg}</span>
      <div style="font-size:.82rem;color:var(--muted);margin-top:.5rem;font-family:var(--font)">Toggle the coach back on and replay — it catches this moment.</div>`;
  }
}

document.querySelectorAll("#demoPick button").forEach((b) =>
  b.addEventListener("click", () => {
    document.querySelectorAll("#demoPick button").forEach((x) => x.classList.toggle("active", x === b));
    demo.persona = b.dataset.p;
    resetDemo();
  })
);
btnNext.addEventListener("click", nextStep);
btnReset.addEventListener("click", resetDemo);
coachToggle.addEventListener("change", () => { demo.coachOn = coachToggle.checked; resetDemo(); });
resetDemo();

/* ============================================================
   CHARTS (Chart.js)
   ============================================================ */
Chart.defaults.font.family = FONT;
Chart.defaults.color = TICK;
Chart.defaults.font.size = 12;

const pct = (v) => (v * 100).toFixed(1) + "%";

function whenVisible(id, build) {
  const el = document.getElementById(id);
  if (!el) return;
  const obs = new IntersectionObserver((entries) => {
    if (entries[0].isIntersecting) { build(el); obs.disconnect(); }
  }, { threshold: 0.25 });
  obs.observe(el);
}

/* Dimension 1 — overall conversion */
whenVisible("chartConversion", (el) => new Chart(el, {
  type: "bar",
  data: {
    labels: ["Baseline", "With coach"],
    datasets: [{
      data: [METRICS.baseline * 100, METRICS.coach * 100],
      backgroundColor: ["rgba(248,113,113,0.7)", "rgba(52,211,153,0.8)"],
      borderColor: ["#f87171", "#34d399"],
      borderWidth: 1.5, borderRadius: 8, maxBarThickness: 90,
    }],
  },
  options: {
    responsive: true, maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: { callbacks: { label: (c) => c.parsed.y.toFixed(1) + "% online conversion" } },
    },
    scales: {
      y: { beginAtZero: true, grid: { color: GRID }, ticks: { callback: (v) => v + "%" } },
      x: { grid: { display: false } },
    },
  },
}));

/* Dimension 2 — per persona */
whenVisible("chartPersona", (el) => {
  const names = Object.keys(METRICS.persona);
  new Chart(el, {
    type: "bar",
    data: {
      labels: names,
      datasets: [
        { label: "Baseline", data: names.map((n) => METRICS.persona[n].baseline * 100),
          backgroundColor: "rgba(248,113,113,0.55)", borderRadius: 6, maxBarThickness: 34 },
        { label: "With coach", data: names.map((n) => METRICS.persona[n].coach * 100),
          backgroundColor: "rgba(52,211,153,0.8)", borderRadius: 6, maxBarThickness: 34 },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { position: "bottom", labels: { boxWidth: 12, padding: 14 } },
        tooltip: { callbacks: { label: (c) => `${c.dataset.label}: ${c.parsed.y.toFixed(1)}%` } },
      },
      scales: {
        y: { beginAtZero: true, grid: { color: GRID }, ticks: { callback: (v) => v + "%" } },
        x: { grid: { display: false } },
      },
    },
  });
});

/* Dimension 3 — intervention mix doughnut */
whenVisible("chartQuality", (el) => {
  const mix = METRICS.quality.mix;
  new Chart(el, {
    type: "doughnut",
    data: {
      labels: Object.keys(mix),
      datasets: [{
        data: Object.values(mix),
        backgroundColor: ["#4f8cff", "#22d3ee", "#2dd4bf", "#fbbf24", "#c084fc", "#fb7185", "#34d399"],
        borderColor: "#070b16", borderWidth: 2,
      }],
    },
    options: {
      responsive: true, maintainAspectRatio: false, cutout: "58%",
      plugins: {
        legend: { position: "right", labels: { boxWidth: 10, padding: 7, font: { size: 10.5 } } },
        tooltip: { callbacks: { label: (c) => `${c.label}: ${c.parsed} fires` } },
      },
    },
  });
});

/* Per-step drop-off */
whenVisible("chartDropoff", (el) => new Chart(el, {
  type: "bar",
  data: {
    labels: METRICS.dropoff.labels,
    datasets: [
      { label: "Baseline drop-off", data: METRICS.dropoff.baseline.map((v) => v * 100),
        backgroundColor: "rgba(248,113,113,0.6)", borderRadius: 6 },
      { label: "With coach", data: METRICS.dropoff.coach.map((v) => v * 100),
        backgroundColor: "rgba(79,140,255,0.8)", borderRadius: 6 },
    ],
  },
  options: {
    responsive: true, maintainAspectRatio: false,
    plugins: {
      legend: { position: "bottom", labels: { boxWidth: 12, padding: 14 } },
      tooltip: { callbacks: { label: (c) => `${c.dataset.label}: ${c.parsed.y.toFixed(1)}% drop` } },
    },
    scales: {
      y: { beginAtZero: true, max: 100, grid: { color: GRID }, ticks: { callback: (v) => v + "%" }, title: { display: true, text: "conditional drop-off", color: TICK } },
      x: { grid: { display: false } },
    },
  },
}));

/* ---------- copy buttons ---------- */
document.querySelectorAll(".copy-btn").forEach((btn) =>
  btn.addEventListener("click", () => {
    navigator.clipboard.writeText(btn.dataset.copy).then(() => {
      const t = btn.textContent;
      btn.textContent = "copied ✓";
      setTimeout(() => (btn.textContent = t), 1400);
    });
  })
);

/* ---------- mermaid ---------- */
if (window.mermaid) {
  mermaid.initialize({
    startOnLoad: true,
    theme: "base",
    themeVariables: {
      background: "#0b1220",
      primaryColor: "#0f1a2e",
      primaryTextColor: "#e8edf6",
      primaryBorderColor: "#4f8cff",
      lineColor: "#6b7689",
      secondaryColor: "#101826",
      tertiaryColor: "#101826",
      fontFamily: "Inter, sans-serif",
      fontSize: "13px",
    },
  });
}
