/**
 * SYNTROPION OS — Web Dashboard Interactive Application Logic
 * Pure ES6 with zero bloated external dependencies.
 */

let currentIdeaId = "idea-pilot-001-radtrack";
let currentStep = 1;

document.addEventListener("DOMContentLoaded", () => {
  initNavigation();
  loadMetrics();
  loadVenturesTable();
  initProposalForm();
  initSocraticChat();
  initPilotSandbox();
  initCircuitBreaker();
});

// --- 1. Tab Navigation ---
function initNavigation() {
  const buttons = document.querySelectorAll(".nav-btn");
  buttons.forEach(btn => {
    btn.addEventListener("click", () => {
      buttons.forEach(b => b.classList.remove("active"));
      btn.classList.add("active");

      const targetId = btn.getAttribute("data-target");
      document.querySelectorAll(".workspace-panel").forEach(p => p.classList.remove("active"));
      const targetPanel = document.getElementById(targetId);
      if (targetPanel) targetPanel.classList.add("active");
    });
  });
}

// --- 2. Live Metrics Polling ---
async function loadMetrics() {
  try {
    const res = await fetch("/metrics");
    if (!res.ok) return;
    const data = await res.json();

    document.getElementById("metric-mrr").textContent = `$${data.portfolio_total_mrr_usd.toLocaleString("en-US", {minimumFractionDigits: 2})}`;
    document.getElementById("metric-subs").textContent = `${data.total_active_b2b_subscribers} Şirket`;
    document.getElementById("metric-payouts").textContent = `$${data.total_expert_rev_share_paid_usd.toLocaleString("en-US", {minimumFractionDigits: 2})}`;
    document.getElementById("metric-treasury").textContent = `$${data.total_treasury_accumulated_usd.toLocaleString("en-US", {minimumFractionDigits: 2})}`;
  } catch (e) {
    console.warn("Metrics fetch error:", e);
  }
}

// --- 3. Proposal Submission ($10 Stake Gate) ---
function initProposalForm() {
  const form = document.getElementById("proposal-form");
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const btn = document.getElementById("btn-submit-proposal");
    btn.disabled = true;
    btn.textContent = "Emanet Blokesi ve FSEK Sözleşmesi İmzalanıyor...";

    const payload = {
      expert: {
        full_name: document.getElementById("prop-name").value,
        email: document.getElementById("prop-email").value,
        industry_domain: document.getElementById("prop-domain").value,
        years_of_experience: parseInt(document.getElementById("prop-exp").value) || 10,
        ip_assignment_signed: true,
        fsek_terms_version: "v1.0-2026"
      },
      title: document.getElementById("prop-title").value,
      problem_statement: document.getElementById("prop-problem").value,
      target_audience: document.getElementById("prop-audience").value,
      current_workaround: document.getElementById("prop-workaround").value,
      stake_amount_usd: 10.00,
      stripe_payment_method_id: "pm_card_visa_live_sim",
      fsek_clickwrap_accepted: true
    };

    try {
      const res = await fetch("/api/v1/proposals/submit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Kayıt başarısız");

      currentIdeaId = data.idea_id;
      document.getElementById("display-idea-id").textContent = data.idea_id;
      document.getElementById("display-fsek-hash").textContent = data.fsek_contract_hash.substring(0, 24) + "...";
      
      const badge = document.getElementById("escrow-badge");
      badge.textContent = "HELD_IN_ESCROW ($10.00)";
      badge.className = "status-badge held";

      alert(`Fikriniz kaydedildi! $10 Emanet blokesi konuldu.\nFSEK Sözleşme Hash: ${data.fsek_contract_hash.substring(0, 16)}...\nŞimdi 2. Adım Sokratik Mülakata geçiyorsunuz.`);

      // Switch to Panel 2
      document.querySelector('.nav-btn[data-target="panel-socratic"]').click();
      loadQuestionForStep(1);
    } catch (err) {
      alert("Hata: " + err.message);
    } finally {
      btn.disabled = false;
      btn.textContent = "$10 Emanet Yetkisi Ver & Sokratik Mülakata Geç";
    }
  });
}

// --- 4. Socratic AI Interviewer ---
async function loadQuestionForStep(step) {
  currentStep = step;
  updateStepIndicator(step);

  try {
    const res = await fetch(`/api/v1/interview/question/${step}`);
    const data = await res.json();
    const qText = data.question.text;

    document.getElementById("current-question-text").textContent = `[ADIM ${step}/5: ${data.question.title}]\n\n${qText}`;
  } catch (e) {
    document.getElementById("current-question-text").textContent = `Soru ${step} yüklenemedi.`;
  }
}

function updateStepIndicator(activeStep) {
  document.querySelectorAll(".step-item").forEach(item => {
    const s = parseInt(item.getAttribute("data-step"));
    item.classList.toggle("active", s === activeStep);
  });
}

function initSocraticChat() {
  const form = document.getElementById("socratic-form");
  const input = document.getElementById("socratic-input");
  const viewport = document.getElementById("chat-viewport");

  loadQuestionForStep(1);

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const text = input.value.trim();
    if (!text) return;

    // Append expert bubble
    appendChatBubble("expert", "SAHA UZMANI", text);
    input.value = "";

    const btn = document.getElementById("btn-submit-step");
    btn.disabled = true;
    btn.textContent = "Değerlendiriliyor...";

    try {
      const res = await fetch("/api/v1/interview/step", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          idea_id: currentIdeaId,
          step: currentStep,
          expert_response: text
        })
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Değerlendirme hatası");

      // Update Gauge
      updateDDSGauge(data.domain_depth_score_running, data.status);
      updateEvaluationTags(data.regulatory_flags, data.edge_cases_identified);

      // AI Response Bubble
      appendChatBubble("ai", "SYNTROPION EVALUATION", `${data.feedback}\n\n${data.next_question || "Mülakat tamamlandı!"}`);

      if (data.is_completed) {
        if (data.status === "PASSED_THRESHOLD") {
          document.getElementById("btn-synthesize-action").style.display = "block";
          alert(`Tebrikler! Mülakat başarıyla tamamlandı. Ortalama DDS Skoru: ${data.domain_depth_score_running:.2f}.\n$10 Stake sermayeye aktarıldı. Şimdi mikro-SaaS kodunu sentezleyebilirsiniz!`);
        } else {
          alert(`Mülakat reddedildi. DDS Skoru: ${data.domain_depth_score_running:.2f} (Eşik 0.75).\n$10 tutarındaki emanet kartınıza iade edildi.`);
        }
      } else {
        currentStep += 1;
        updateStepIndicator(currentStep);
      }
    } catch (err) {
      appendChatBubble("ai", "HATA", err.message);
    } finally {
      btn.disabled = false;
      btn.textContent = "Yanıtı Gönder & Değerlendir";
    }
  });

  // Synthesize Venture Click
  const synthBtn = document.getElementById("btn-synthesize-action");
  synthBtn.addEventListener("click", async () => {
    synthBtn.disabled = true;
    synthBtn.textContent = "Kod Sentezleniyor & Test Ediliyor (AST Inspection)...";

    try {
      const res = await fetch("/api/v1/ventures/synthesize", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ idea_id: currentIdeaId })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Sentez hatası");

      alert(`✅ Mikro-SaaS Başarıyla Üretildi!\nSlug: ${data.code_slug}\nAPI Yolu: ${data.api_prefix_path}\nTier 1 Hak Ediş ve Ömür Boyu Lisans Anahtarı tahsis edildi!`);
      document.querySelector('.nav-btn[data-target="panel-cockpit"]').click();
      loadVenturesTable();
      loadMetrics();
    } catch (e) {
      alert("Sentez Hatası: " + e.message);
    } finally {
      synthBtn.disabled = false;
      synthBtn.textContent = "⚡ Otonom Mikro-SaaS Kod Sentezini Başlat";
    }
  });
}

function appendChatBubble(type, sender, message) {
  const viewport = document.getElementById("chat-viewport");
  const bubble = document.createElement("div");
  bubble.className = `chat-bubble ${type}`;
  bubble.innerHTML = `<div class="sender">${sender}</div><div class="message">${message.replace(/\n/g, "<br>")}</div>`;
  viewport.appendChild(bubble);
  viewport.scrollTop = viewport.scrollHeight;
}

function updateDDSGauge(score, status) {
  document.getElementById("dds-score-num").textContent = score.toFixed(2);
  const pct = Math.min(100, Math.round(score * 100));
  document.getElementById("dds-gauge-fill").style.width = `${pct}%`;

  const verdict = document.getElementById("dds-verdict");
  if (status === "PASSED_THRESHOLD") {
    verdict.textContent = "ONAYLANDI (DDS >= 0.75)";
    verdict.style.color = "var(--accent-emerald)";
  } else if (status === "REJECTED_LOW_SCORE") {
    verdict.textContent = "REDDEDİLDİ (DDS < 0.75)";
    verdict.style.color = "#ef4444";
  } else {
    verdict.textContent = `MÜLAKAT SÜRÜYOR (%${pct})`;
    verdict.style.color = "var(--accent-amber)";
  }
}

function updateEvaluationTags(regFlags, edgeCases) {
  const regContainer = document.getElementById("detected-reg");
  if (regFlags && regFlags.length > 0) {
    regContainer.innerHTML = regFlags.map(r => `<span class="tag">${r.toUpperCase()}</span>`).join("");
  }

  const edgeContainer = document.getElementById("detected-edges");
  if (edgeCases && edgeCases.length > 0) {
    edgeContainer.innerHTML = edgeCases.map(e => `<li>${e}</li>`).join("");
  }
}

// --- 5. Pilot Sandbox Execution ---
const PILOT_CONFIGS = {
  radtrack: {
    title: "RadTrack AI — RECIST 1.1 Lezyon Kıyaslama Ajanı",
    inputs: [
      { id: "rad-base", label: "Bazal Lezyon Çapı (mm)", type: "number", value: 24.0 },
      { id: "rad-follow", label: "Kontrol İnceleme Çapı (mm)", type: "number", value: 14.4 }
    ],
    runEndpoint: "/api/v1/pilots/radtrack",
    buildPayload: () => ({
      baseline_mm: parseFloat(document.getElementById("rad-base").value),
      follow_up_mm: parseFloat(document.getElementById("rad-follow").value)
    })
  },
  lexnotice: {
    title: "LexNotice AI — TTK Ayıp ve İhtarname Süre Ajanı",
    inputs: [
      { id: "lex-delivery", label: "Mal/Hizmet Teslim Tarihi", type: "text", value: "2026-09-01" },
      { id: "lex-current", label: "Bugünün Tarihi", type: "text", value: "2026-09-06" },
      { id: "lex-amount", label: "Fatura Tutarı (TL)", type: "number", value: 250000.0 }
    ],
    runEndpoint: "/api/v1/pilots/lexnotice",
    buildPayload: () => ({
      delivery_date: document.getElementById("lex-delivery").value,
      current_date: document.getElementById("lex-current").value,
      invoice_amount_try: parseFloat(document.getElementById("lex-amount").value)
    })
  },
  taxcross: {
    title: "TaxCrossAudit — GİB e-Fatura vs Muhasebe Çapraz Denetim",
    inputs: [
      { id: "tax-gib", label: "GİB e-Fatura XML Toplamı (TL)", type: "number", value: 1250000.0 },
      { id: "tax-ledger", label: "Mizan Muhasebe Fişi Toplamı (TL)", type: "number", value: 1242000.0 }
    ],
    runEndpoint: "/api/v1/pilots/taxcross",
    buildPayload: () => ({
      gib_invoices_total_try: parseFloat(document.getElementById("tax-gib").value),
      accounting_ledger_total_try: parseFloat(document.getElementById("tax-ledger").value)
    })
  },
  tarifa: {
    title: "TarifaCustoms AI — 12 Haneli GTİP & Menşe Sınıflandırıcı",
    inputs: [
      { id: "tar-desc", label: "Teknik Ürün Tanımı", type: "text", value: "Yüksek yoğunluklu polietilen plastik granül" },
      { id: "tar-origin", label: "Menşe Ülke Kodu", type: "text", value: "CN" }
    ],
    runEndpoint: "/api/v1/pilots/tarifa",
    buildPayload: () => ({
      product_description: document.getElementById("tar-desc").value,
      country_of_origin: document.getElementById("tar-origin").value
    })
  },
  demurrage: {
    title: "DemurrageShield — Liman Serbest Süre ve Demuraj Denetimi",
    inputs: [
      { id: "dem-dis", label: "Gemi Tahliye Tarihi (Discharge)", type: "text", value: "2026-09-01" },
      { id: "dem-gate", label: "Konteyner Liman Çıkış Tarihi (Gate-Out)", type: "text", value: "2026-09-12" },
      { id: "dem-free", label: "Serbest Gün Hakkı (Free Time)", type: "number", value: 7 },
      { id: "dem-rate", label: "Günlük Ceza Tarifesi ($/TEU)", type: "number", value: 180.0 }
    ],
    runEndpoint: "/api/v1/pilots/demurrage",
    buildPayload: () => ({
      discharge_date: document.getElementById("dem-dis").value,
      gate_out_date: document.getElementById("dem-gate").value,
      free_time_days: parseInt(document.getElementById("dem-free").value),
      daily_rate_usd: parseFloat(document.getElementById("dem-rate").value)
    })
  }
};

function initPilotSandbox() {
  const tabs = document.querySelectorAll(".pilot-tab");
  tabs.forEach(tab => {
    tab.addEventListener("click", () => {
      tabs.forEach(t => t.classList.remove("active"));
      tab.classList.add("active");
      renderPilotUI(tab.getAttribute("data-pilot"));
    });
  });

  renderPilotUI("radtrack");
}

function renderPilotUI(pilotKey) {
  const conf = PILOT_CONFIGS[pilotKey];
  const container = document.getElementById("pilot-sandbox");

  const inputsHtml = conf.inputs.map(inp => `
    <div class="form-group">
      <label>${inp.label}</label>
      <input type="${inp.type}" id="${inp.id}" value="${inp.value}">
    </div>
  `).join("");

  container.innerHTML = `
    <div class="pilot-exec-grid">
      <div class="pilot-form-side">
        <h4 style="margin-bottom:0.75rem; color:var(--text-main); font-size:0.95rem;">${conf.title}</h4>
        ${inputsHtml}
        <button class="primary-btn" id="btn-run-pilot">Modeli Çalıştır ve Sonuç Al</button>
      </div>
      <div class="pilot-result-side">
        <h4 style="margin-bottom:0.75rem; color:var(--text-dim); font-size:0.8rem; text-transform:uppercase; font-family:var(--font-mono);">Deterministik Çıktı &amp; Denetim Logu</h4>
        <div class="pilot-result-box" id="pilot-output-box">Çalıştırmak için butona tıklayınız...</div>
      </div>
    </div>
  `;

  document.getElementById("btn-run-pilot").addEventListener("click", async () => {
    const outBox = document.getElementById("pilot-output-box");
    outBox.textContent = "Hesaplanıyor...";

    try {
      const payload = conf.buildPayload();
      const res = await fetch(conf.runEndpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      outBox.textContent = JSON.stringify(data, null, 2);
    } catch (e) {
      outBox.textContent = "Hata: " + e.message;
    }
  });
}

// --- 6. Ventures & Dividends Table ---
async function loadVenturesTable() {
  const tbody = document.getElementById("ventures-table-body");
  try {
    const res = await fetch("/api/v1/ventures");
    if (!res.ok) return;
    const ventures = await res.json();

    if (ventures.length === 0) {
      tbody.innerHTML = `<tr><td colspan="7" class="center-text">Henüz girişim bulunmuyor.</td></tr>`;
      return;
    }

    tbody.innerHTML = ventures.map(v => {
      const mrr = v.current_monthly_mrr_usd || 0.0;
      const expertShare = mrr * 0.20;
      const treasuryShare = mrr * 0.75;

      return `
        <tr>
          <td><strong>${v.display_name}</strong></td>
          <td><code>${v.code_slug}</code></td>
          <td><span class="status-badge held">${v.status}</span></td>
          <td><strong>$${mrr.toLocaleString("en-US", {minimumFractionDigits: 2})}</strong></td>
          <td style="color:var(--accent-emerald)">$${expertShare.toLocaleString("en-US", {minimumFractionDigits: 2})}</td>
          <td>$${treasuryShare.toLocaleString("en-US", {minimumFractionDigits: 2})}</td>
          <td>
            <a class="action-link" onclick="executeManualSplit('${v.venture_id}', ${mrr})">Kârı Dağıt</a>
          </td>
        </tr>
      `;
    }).join("");
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="7" class="center-text">Veri yüklenemedi.</td></tr>`;
  }
}

window.executeManualSplit = async function(ventureId, currentMrr) {
  if (currentMrr <= 0) {
    alert("Bu girişimin henüz cirosu bulunmuyor.");
    return;
  }

  const period = new Date().toISOString().substring(0, 7);
  try {
    const res = await fetch("/api/v1/revenue/calculate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        venture_id: ventureId,
        billing_period: period,
        gross_revenue_usd: currentMrr,
        infra_costs_usd: Math.round(currentMrr * 0.05)
      })
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Dağıtım başarısız");

    alert(`✅ Kâr Dağıtımı Gerçekleştirildi!\nNet Kâr: $${data.net_profit_usd}\nUzman Payı (%20): $${data.expert_rev_share_usd}\nHazine Payı (%75): $${data.treasury_share_usd}\nStripe Transfer ID: ${data.stripe_transfer_id}\nZero-Copy IPC: ${data.ipc_telemetry_dispatched ? 'Aktarıldı' : 'Beklemede'}`);
    loadMetrics();
  } catch (err) {
    alert("Hata: " + err.message);
  }
};

// --- 7. Circuit Breaker & Safe Mode Telemetry ---
function initCircuitBreaker() {
  const badge = document.getElementById("circuit-badge");
  const statusText = document.getElementById("circuit-status-text");
  const btnKillSwitch = document.getElementById("btn-kill-switch");

  if (!badge || !statusText || !btnKillSwitch) return;

  async function updateStatus() {
    try {
      const res = await fetch("/api/v1/system/circuit-breaker");
      if (!res.ok) return;
      const data = await res.json();

      if (data.kill_switch_active || data.state === "OPEN") {
        badge.classList.add("safe-mode");
        statusText.textContent = data.kill_switch_active 
          ? `GÜVENLİ KAPATMA (${data.kill_switch_reason || 'Manuel'})`
          : `KESİCİ AÇIK (%${data.recent_failure_rate_pct} Hata)`;
        btnKillSwitch.textContent = "🟢 Devam Et";
        btnKillSwitch.style.background = "rgba(16, 185, 129, 0.25)";
        btnKillSwitch.style.borderColor = "rgba(16, 185, 129, 0.5)";
        btnKillSwitch.style.color = "#a7f3d0";
      } else if (data.state === "HALF_OPEN") {
        badge.classList.remove("safe-mode");
        statusText.textContent = "KESİCİ: TEST MODU (HALF-OPEN)";
        btnKillSwitch.textContent = "🛑 Safe Stop";
      } else {
        badge.classList.remove("safe-mode");
        statusText.textContent = "KESİCİ: KAPALI (NORMAL)";
        btnKillSwitch.textContent = "🛑 Safe Stop";
        btnKillSwitch.style.background = "";
        btnKillSwitch.style.borderColor = "";
        btnKillSwitch.style.color = "";
      }
    } catch (e) {
      console.warn("Circuit status error:", e);
    }
  }

  btnKillSwitch.addEventListener("click", async () => {
    try {
      const isSafeMode = badge.classList.contains("safe-mode");
      if (isSafeMode) {
        // Deactivate
        const res = await fetch("/api/v1/system/kill-switch/deactivate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ operator: "operator@syntropion.org" })
        });
        if (res.ok) updateStatus();
      } else {
        // Activate emergency stop
        const reason = prompt("Acil durum güvenli kapatma gerekçesini giriniz:", "Operatör Güvenli Duruşu");
        if (!reason) return;
        const res = await fetch("/api/v1/system/kill-switch", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ operator: "operator@syntropion.org", reason })
        });
        if (res.ok) updateStatus();
      }
    } catch (err) {
      alert("Hata: " + err.message);
    }
  });

  updateStatus();
  setInterval(updateStatus, 5000);
}
