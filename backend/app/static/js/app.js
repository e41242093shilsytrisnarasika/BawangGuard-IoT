(() => {
  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => [...document.querySelectorAll(sel)];

  let trendChart = null;
  let statusChart = null;

  const statusClass = {
    COCOK: "ok",
    KURANG_COCOK: "warn",
    TIDAK_COCOK: "bad",
  };

  async function api(path, options) {
    const res = await fetch(path, {
      headers: { "Content-Type": "application/json", ...(options?.headers || {}) },
      ...options,
    });
    if (!res.ok) {
      const text = await res.text();
      throw new Error(text || res.statusText);
    }
    return res.json();
  }

  function fmtTime(v) {
    if (!v) return "—";
    const d = new Date(v);
    return d.toLocaleString("id-ID", {
      day: "2-digit",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  function setBar(el, pct, sev) {
    el.style.width = `${Math.max(4, Math.min(100, pct))}%`;
    const metric = el.closest(".metric");
    if (metric) metric.dataset.sev = sev || "ok";
  }

  function severityFromIdeal(value, min, max) {
    if (value >= min && value <= max) return "ok";
    const mid = (min + max) / 2;
    const span = (max - min) / 2 + 0.001;
    const dist = Math.abs(value - mid) / span;
    return dist < 1.6 ? "warn" : "bad";
  }

  function renderReading(data) {
    const status = data.status;
    const hero = $("#statusHero");
    hero.dataset.status = status;
    $("#statusTitle").textContent = data.status_label || status;
    $("#statusSummary").textContent =
      data.recommendations?.summary ||
      "Monitoring sensor IoT untuk kesesuaian lahan bawang merah.";
    $("#scoreValue").textContent = Math.round(data.score ?? 0);
    $("#scoreRing").style.setProperty("--p", `${Math.round(data.score ?? 0)}%`);
    $("#nodeId").textContent = data.node_id || data.reading?.node_id || "NODE-01";
    $("#updatedAt").textContent = fmtTime(data.created_at);
    $("#seasonBadge").textContent = data.season || "Musim —";
    $("#methodBadge").textContent =
      data.method === "fuzzy"
        ? "Fuzzy Logic"
        : data.method === "decision_tree"
          ? "Decision Tree"
          : data.method === "random_forest"
            ? "Random Forest"
            : data.method || "AI";

    const moisture = data.soil_moisture ?? data.reading?.soil_moisture;
    const temp = data.soil_temp ?? data.reading?.soil_temp;
    const ph = data.soil_ph ?? data.reading?.soil_ph;
    const drain = data.drainage_score ?? data.reading?.drainage_score ?? 0.7;

    $("#mMoisture").textContent = Number(moisture).toFixed(1);
    $("#mTemp").textContent = Number(temp).toFixed(1);
    $("#mPh").textContent = Number(ph).toFixed(2);
    $("#mDrain").textContent = Number(drain).toFixed(2);

    setBar($("#barMoisture"), moisture, severityFromIdeal(moisture, 50, 70));
    setBar($("#barTemp"), ((temp - 15) / 25) * 100, severityFromIdeal(temp, 25, 32));
    setBar($("#barPh"), ((ph - 4) / 4) * 100, severityFromIdeal(ph, 5.5, 6.5));
    setBar($("#barDrain"), drain * 100, drain >= 0.6 ? "ok" : drain >= 0.4 ? "warn" : "bad");

    renderRecommendations(data);
    renderFactors(data.factors || []);
  }

  function renderRecommendations(data) {
    const rec = data.recommendations || {};
    $("#recSummary").textContent = rec.summary || "Belum ada rekomendasi.";
    const fill = (id, items, empty) => {
      const el = $(id);
      el.innerHTML = "";
      const arr = items?.length ? items : [empty];
      arr.forEach((t) => {
        const li = document.createElement("li");
        li.textContent = typeof t === "string" ? t : t.cause || t.label || JSON.stringify(t);
        el.appendChild(li);
      });
    };
    fill(
      "#listLimiting",
      (data.limiting_factors || []).map((f) => f.cause || f.label),
      "Tidak ada faktor pembatas signifikan"
    );
    fill("#listPriority", rec.priority_actions, "Pertahankan kondisi saat ini");
    fill("#listFertilizer", rec.fertilizers, "—");
    const methods = [...(rec.ameliorants || []), ...(rec.methods || [])];
    fill("#listMethods", methods, "—");
    $("#plantingWindow").textContent = rec.planting_window || "";
  }

  function renderFactors(factors) {
    const box = $("#factorCards");
    box.innerHTML = "";
    if (!factors.length) {
      box.innerHTML = "<p class='lede'>Jalankan analisis untuk melihat membership fuzzy tiap faktor.</p>";
      return;
    }
    factors.forEach((f) => {
      const card = document.createElement("div");
      card.className = "factor-card";
      const sev = f.severity || "ok";
      card.innerHTML = `
        <div class="top">
          <h3>${f.label}</h3>
          <span class="sev ${sev}">${sev}</span>
        </div>
        <p><strong>${f.value ?? "—"} ${f.unit || ""}</strong> · ideal ${f.ideal_min}–${f.ideal_max}</p>
        <p>${f.cause || ""}</p>
        <div class="membership"><span style="width:${Math.round((f.membership || 0) * 100)}%"></span></div>
      `;
      box.appendChild(card);
    });
  }

  async function loadLatest() {
    const latest = await api("/api/latest");
    renderReading(latest);
  }

  async function loadStatsAndCharts() {
    const [stats, readings] = await Promise.all([
      api("/api/stats"),
      api("/api/readings?limit=36"),
    ]);
    if (stats.season) $("#seasonBadge").textContent = stats.season;

    const labels = readings.map((r) => fmtTime(r.created_at));
    const moisture = readings.map((r) => r.soil_moisture);
    const temp = readings.map((r) => r.soil_temp);
    const ph = readings.map((r) => r.soil_ph);

    const ctx1 = $("#trendChart");
    if (trendChart) trendChart.destroy();
    trendChart = new Chart(ctx1, {
      type: "line",
      data: {
        labels,
        datasets: [
          {
            label: "Kelembapan %",
            data: moisture,
            borderColor: "#1f6b45",
            backgroundColor: "rgba(31,107,69,0.12)",
            tension: 0.35,
            fill: true,
            yAxisID: "y",
          },
          {
            label: "Suhu °C",
            data: temp,
            borderColor: "#c9851a",
            tension: 0.35,
            yAxisID: "y",
          },
          {
            label: "pH",
            data: ph,
            borderColor: "#b42318",
            tension: 0.35,
            yAxisID: "y1",
          },
        ],
      },
      options: {
        responsive: true,
        interaction: { mode: "index", intersect: false },
        plugins: { legend: { position: "bottom", labels: { boxWidth: 12 } } },
        scales: {
          y: { beginAtZero: false, grid: { color: "rgba(28,42,34,0.06)" } },
          y1: {
            position: "right",
            min: 4,
            max: 8,
            grid: { drawOnChartArea: false },
          },
          x: { ticks: { maxTicksLimit: 6 }, grid: { display: false } },
        },
      },
    });

    const counts = stats.counts || { COCOK: 0, KURANG_COCOK: 0, TIDAK_COCOK: 0 };
    const ctx2 = $("#statusChart");
    if (statusChart) statusChart.destroy();
    statusChart = new Chart(ctx2, {
      type: "doughnut",
      data: {
        labels: ["COCOK", "KURANG COCOK", "TIDAK COCOK"],
        datasets: [
          {
            data: [counts.COCOK || 0, counts.KURANG_COCOK || 0, counts.TIDAK_COCOK || 0],
            backgroundColor: ["#1f6b45", "#c9851a", "#b42318"],
            borderWidth: 0,
          },
        ],
      },
      options: {
        cutout: "68%",
        plugins: { legend: { display: false } },
      },
    });

    $("#statusLegend").innerHTML = `
      <li><span><i class="dot" style="background:#1f6b45"></i>COCOK</span><span>${counts.COCOK || 0}</span></li>
      <li><span><i class="dot" style="background:#c9851a"></i>KURANG</span><span>${counts.KURANG_COCOK || 0}</span></li>
      <li><span><i class="dot" style="background:#b42318"></i>TIDAK</span><span>${counts.TIDAK_COCOK || 0}</span></li>
    `;
  }

  async function loadNotifications() {
    const items = await api("/api/notifications");
    const unread = items.filter((n) => !n.is_read).length;
    $("#notifCount").textContent = unread;
    const list = $("#notifList");
    list.innerHTML = "";
    items.forEach((n) => {
      const el = document.createElement("article");
      el.className = "notif-item";
      el.innerHTML = `
        <h3>${n.title}</h3>
        <p>${n.message}</p>
        <time>${fmtTime(n.created_at)} · ${n.role} · ${n.channel}</time>
      `;
      el.addEventListener("click", async () => {
        if (!n.is_read) {
          await api(`/api/notifications/${n.id}/read`, { method: "POST" });
          loadNotifications();
        }
      });
      list.appendChild(el);
    });
  }

  async function simulate(scenario) {
    const method = $("#methodSelect").value || "fuzzy";
    const data = await api(`/api/simulate?scenario=${scenario}&method=${method}`, {
      method: "POST",
    });
    renderReading(data);
    await Promise.all([loadStatsAndCharts(), loadNotifications()]);
  }

  function formToPayload(form) {
    const fd = new FormData(form);
    const num = (k) => {
      const v = fd.get(k);
      return v === "" || v == null ? null : Number(v);
    };
    return {
      soil_moisture: num("soil_moisture"),
      soil_temp: num("soil_temp"),
      soil_ph: num("soil_ph"),
      drainage_score: num("drainage_score"),
      organic_carbon: num("organic_carbon"),
      nitrogen: num("nitrogen"),
      phosphorus: num("phosphorus"),
      potassium: num("potassium"),
      method: fd.get("method") || "fuzzy",
      node_id: "NODE-MANUAL",
    };
  }

  $("#analyzeForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const payload = formToPayload(e.target);
    const data = await api("/api/analyze", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    renderReading(data);
    await Promise.all([loadStatsAndCharts(), loadNotifications()]);
  });

  $("#labForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const body = Object.fromEntries([...fd.entries()].map(([k, v]) => [k, v === "" ? null : isNaN(Number(v)) ? v : Number(v)]));
    await api("/api/lab", { method: "POST", body: JSON.stringify(body) });
    alert("Data uji tanah tersimpan.");
  });

  $("#btnLoadLab").addEventListener("click", async () => {
    const lab = await api("/api/lab/latest");
    if (!lab) {
      alert("Belum ada data lab. Isi form uji tanah dulu.");
      return;
    }
    const form = $("#analyzeForm");
    ["organic_carbon", "nitrogen", "phosphorus", "potassium"].forEach((k) => {
      if (lab[k] != null) form.elements[k].value = lab[k];
    });
  });

  $("#btnSimulateIdeal").addEventListener("click", () => simulate("ideal"));
  $("#btnSimulateRandom").addEventListener("click", () => simulate("random"));
  $("#btnSimulateProblem").addEventListener("click", () => {
    const pick = ["dry", "wet", "acid", "alkaline"][Math.floor(Math.random() * 4)];
    simulate(pick);
  });

  function toggleNotif(open) {
    $("#notifDrawer").hidden = !open;
    $("#notifBackdrop").hidden = !open;
  }
  $("#btnNotif").addEventListener("click", () => toggleNotif(true));
  $("#btnCloseNotif").addEventListener("click", () => toggleNotif(false));
  $("#notifBackdrop").addEventListener("click", () => toggleNotif(false));

  async function boot() {
    try {
      await Promise.all([loadLatest(), loadStatsAndCharts(), loadNotifications()]);
    } catch (err) {
      $("#statusTitle").textContent = "Gagal memuat data";
      $("#statusSummary").textContent = String(err.message || err);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
