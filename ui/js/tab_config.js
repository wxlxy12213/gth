// ============================================================================
// @AI-ANCHOR: [JS-TAB4-CONFIG] 场景 04：01~05 积木式步骤卡片交互、双击调参弹窗与坐标/延时工作台
// 升级重点 (GTH V3.0)：
// 将原本散落在 `tab_workbench.js` 中的场景 04 分组切换、搜索过滤、JSON 模式切换、保存与 3 秒拾取事件全部收拢至本模块。
// ============================================================================

let isJsonMode = false;
let activeConfigGroup = "all";

// @AI-ANCHOR: [CFG-STEP-BLOCKS] 01~05 积木式步骤卡片单击启停、双击快调弹窗与面板工具栏绑定
function initStepBlocksInteraction() {
  const stepCards = document.querySelectorAll("#step-blocks-container .step-track-card");
  let clickTimer = null;

  stepCards.forEach(card => {
    const stepNum = Number(card.getAttribute("data-step"));

    card.addEventListener("click", (e) => {
      if (e.target.closest("button")) return;
      if (clickTimer) clearTimeout(clickTimer);
      clickTimer = setTimeout(() => {
        toggleStepBlock(stepNum);
        clickTimer = null;
      }, 180);
    });

    card.addEventListener("dblclick", (e) => {
      if (e.target.closest("button")) return;
      if (clickTimer) {
        clearTimeout(clickTimer);
        clickTimer = null;
      }
      openStepConfigModal(`step${stepNum}`);
    });
  });

  const presetBtns = document.querySelectorAll(".preset-blocks-bar .preset-pill");
  presetBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      const stepsStr = btn.getAttribute("data-preset") || "1,2,3,4,5";
      const parsed = stepsStr.split(",").map(Number).filter(n => n >= 1 && n <= 5);
      batchUpdateState({
        enabled_steps: parsed,
        step_start: parsed[0] || 1,
        step_end: parsed[parsed.length - 1] || 5,
        run_mode: parsed.length === 1 ? "single_step" : "to_end"
      }, true);
      showToast(`已切换积木组合: 第 [${parsed.join(", ")}] 步`, "info");
    });
  });

  // 双击弹窗关闭与保存
  document.getElementById("btn-step-modal-close")?.addEventListener("click", closeStepConfigModal);
  document.getElementById("step-config-modal")?.addEventListener("click", (e) => {
    if (e.target.id === "step-config-modal") closeStepConfigModal();
  });
  document.getElementById("btn-step-modal-save")?.addEventListener("click", async () => {
    if (window.pywebview?.api?.save_profile) {
      const ok = await window.pywebview.api.save_profile(initialProfile);
      if (ok) {
        syncJsonFromVisual();
        renderVisualConfig();
        showToast("当前步骤坐标与时间参数已保存并实时生效！", "success");
        closeStepConfigModal();
      } else {
        showToast("保存配置失败", "error");
      }
    }
  });

  // 场景 04 配置面板顶部按钮与搜索栏事件
  document.querySelectorAll("#config-step-pills .avant-nav-pill").forEach(pill => {
    pill.addEventListener("click", () => {
      document.querySelectorAll("#config-step-pills .avant-nav-pill").forEach(p => p.classList.remove("active"));
      pill.classList.add("active");
      activeConfigGroup = pill.dataset.cfgGroup;
      filterConfigCards();
    });
  });

  document.getElementById("config-search-input")?.addEventListener("input", filterConfigCards);

  document.getElementById("btn-toggle-json-mode")?.addEventListener("click", () => {
    isJsonMode = !isJsonMode;
    const vToolbar = document.getElementById("config-visual-toolbar");
    const vContainer = document.getElementById("config-visual-container");
    const jContainer = document.getElementById("config-json-container");
    const toggleText = document.getElementById("btn-toggle-json-text");

    if (isJsonMode) {
      syncJsonFromVisual();
      if (vToolbar) vToolbar.style.display = "none";
      if (vContainer) vContainer.style.display = "none";
      if (jContainer) jContainer.style.display = "flex";
      if (toggleText) toggleText.textContent = "🎨 返回可视化积木";
    } else {
      syncVisualFromJson();
      if (jContainer) jContainer.style.display = "none";
      if (vToolbar) vToolbar.style.display = "flex";
      if (vContainer) vContainer.style.display = "flex";
      if (toggleText) toggleText.textContent = "📝 切换专家 JSON 模式";
    }
  });

  document.getElementById("btn-save-profile")?.addEventListener("click", async () => {
    try {
      if (isJsonMode) {
        const raw = document.getElementById("profile-json-editor").value;
        initialProfile = JSON.parse(raw);
      }
      const ok = await window.pywebview.api.save_profile(initialProfile);
      if (ok) {
        showToast("坐标与延时配置已保存并热重载生效！", "success");
      } else {
        showToast("配置保存失败", "error");
      }
    } catch (e) {
      showToast("JSON 语法解析错误，保存中止", "error");
    }
  });

  document.getElementById("btn-pick-coord")?.addEventListener("click", async () => {
    if (isPickingCoord) return;
    isPickingCoord = true;
    showToast("请在 3 秒内将鼠标移至目标屏幕物理点...", "warning");
    const res = await window.pywebview.api.pick_coordinate_3s();
    isPickingCoord = false;
    if (res) {
      showToast(`已捕获屏幕坐标: [${res.x}, ${res.y}]`, "success");
    }
  });
}

window.toggleStepBlock = function(stepNum) {
  let active = getActiveStepsList();
  if (active.includes(stepNum)) {
    if (active.length === 1) {
      showToast("至少需要保留 1 个执行步骤！", "warning");
      return;
    }
    active = active.filter(s => s !== stepNum);
  } else {
    active.push(stepNum);
    active.sort((a, b) => a - b);
  }
  batchUpdateState({
    enabled_steps: active,
    step_start: active[0],
    step_end: active[active.length - 1],
    run_mode: active.length === 1 ? "single_step" : "to_end"
  }, true);
};

window.syncStepBlocksUI = function() {
  const active = getActiveStepsList();
  document.querySelectorAll("#step-blocks-container .step-track-card").forEach(card => {
    const s = Number(card.getAttribute("data-step"));
    const isOn = active.includes(s);
    card.classList.toggle("active", isOn);
    const chk = card.querySelector(".step-check-box");
    if (chk) chk.textContent = isOn ? "✓" : "✕";
  });

  const badge = document.getElementById("active-steps-badge");
  if (badge) {
    badge.textContent = `已选 ${active.length} 步 (${active.join("-")})`;
  }

  const activeKey = active.join(",");
  document.querySelectorAll(".preset-blocks-bar .preset-pill").forEach(btn => {
    btn.classList.toggle("active", btn.getAttribute("data-preset") === activeKey);
  });
};

window.openStepConfigModal = function(stepGroupId) {
  const modal = document.getElementById("step-config-modal");
  const titleEl = document.getElementById("step-modal-title");
  const bodyEl = document.getElementById("step-modal-body");
  if (!modal || !bodyEl) return;

  const coordGroup = CONFIG_METADATA.find(g => g.groupId === stepGroupId);
  const delayGroup = CONFIG_METADATA.find(g => g.groupId === "delays");
  const relatedDelayKeys = STEP_DELAY_MAP[stepGroupId] || [];
  const relatedDelays = (delayGroup?.items || []).filter(it => relatedDelayKeys.includes(it.key));

  titleEl.textContent = `${coordGroup ? coordGroup.title : stepGroupId} · 坐标方块与时间方块直调`;
  bodyEl.innerHTML = "";

  const coords = initialProfile.coordinates || {};
  const delays = initialProfile.delays || {};

  if (relatedDelays.length > 0) {
    const dSec = document.createElement("div");
    dSec.className = "config-group-section";
    dSec.innerHTML = `
      <div class="config-group-header">
        <div class="config-group-title">
          <span>⏱️ 本步关联时间/延时方块</span>
          <span class="config-group-badge">TIMING BLOCKS</span>
        </div>
        <span style="font-family: var(--font-mono); font-size: 13px; font-weight: 900;">${relatedDelays.length} 个时间方块</span>
      </div>
      <div class="config-grid" id="modal-delay-grid"></div>
    `;
    bodyEl.appendChild(dSec);
    const dGrid = dSec.querySelector("#modal-delay-grid");
    relatedDelays.forEach(item => {
      dGrid.appendChild(createConfigCardDOM(item, coords, delays, "modal"));
    });
  }

  if (coordGroup && coordGroup.items.length > 0) {
    const cSec = document.createElement("div");
    cSec.className = "config-group-section";
    cSec.innerHTML = `
      <div class="config-group-header">
        <div class="config-group-title">
          <span>🎯 本步屏幕物理坐标积木块</span>
          <span class="config-group-badge">${coordGroup.badge}</span>
        </div>
        <span style="font-family: var(--font-mono); font-size: 13px; font-weight: 900;">${coordGroup.items.length} 步</span>
      </div>
      <div class="config-grid" id="modal-coord-grid"></div>
    `;
    bodyEl.appendChild(cSec);
    const cGrid = cSec.querySelector("#modal-coord-grid");
    coordGroup.items.forEach(item => {
      cGrid.appendChild(createConfigCardDOM(item, coords, delays, "modal"));
    });
  }

  bindConfigEvents(bodyEl);
  modal.classList.add("open");
};

function closeStepConfigModal() {
  document.getElementById("step-config-modal")?.classList.remove("open");
}

function createConfigCardDOM(item, coords, delays, prefix = "cfg") {
  const card = document.createElement("div");
  card.className = `config-item-card ${item.type === "delay" ? "is-delay-block" : ""}`;
  card.id = `${prefix}-card-${item.key}`;
  card.dataset.key = item.key;
  card.dataset.label = item.label;
  card.dataset.desc = item.desc;

  if (item.type === "coord") {
    const currentVal = coords[item.key] || [0, 0];
    const delayKey = item.delayKey || "default_ms";
    const delayMs = delays[delayKey] !== undefined ? delays[delayKey] : 350;
    const secVal = delayMs % 100 === 0 ? (delayMs / 1000).toFixed(1) : Number((delayMs / 1000).toFixed(2));
    card.dataset.delayKey = delayKey;
    card.innerHTML = `
      <div class="config-item-top">
        <span class="config-item-label">🎯 ${item.label}</span>
        <div class="config-delay-badge config-delay-editable" data-delay-key="${delayKey}" title="关联延时键: ${delayKey} (${delayMs}ms)">
          <span class="delay-badge-prefix">⏱️ 延时</span>
          <input type="number" class="coord-delay-sec-input" data-delay-key="${delayKey}" value="${secVal}" step="0.1" min="0" placeholder="0.3">
          <span class="delay-badge-suffix">s</span>
        </div>
        <span class="config-item-key">${item.key}</span>
      </div>
      <div class="config-item-desc">${item.desc}</div>
      <div class="config-coord-controls">
        <div class="coord-inputs-flex">
          <div class="coord-field-pill">
            <span>X:</span>
            <input type="number" class="coord-val-x" value="${currentVal[0]}" data-key="${item.key}">
          </div>
          <div class="coord-field-pill">
            <span>Y:</span>
            <input type="number" class="coord-val-y" value="${currentVal[1]}" data-key="${item.key}">
          </div>
        </div>
        <button class="btn-pick-single" data-key="${item.key}" data-label="${item.label}">
          <span>🎯 3秒拾取</span>
        </button>
      </div>
    `;
  } else {
    const currentMs = delays[item.key] !== undefined ? delays[item.key] : 1000;
    const sec = (currentMs / 1000).toFixed(1);
    card.innerHTML = `
      <div class="config-item-top">
        <span class="config-item-label">⏱️ ${item.label}</span>
        <span class="config-item-key">${item.key}</span>
      </div>
      <div class="config-item-desc">${item.desc}</div>
      <div class="config-coord-controls">
        <div class="delay-input-pill">
          <input type="number" class="delay-val-input" value="${currentMs}" step="100" data-key="${item.key}">
          <span>ms</span>
        </div>
        <span class="delay-sec-hint" data-sec-key="${item.key}">= ${sec} 秒</span>
      </div>
    `;
  }
  return card;
}

// @AI-ANCHOR: [CFG-VISUAL-EDITOR] 坐标方块与时间方块可视化卡片渲染、实时搜索过滤与 JSON 双向同步
function renderVisualConfig() {
  const container = document.getElementById("config-visual-container");
  if (!container) return;
  container.innerHTML = "";

  const coords = initialProfile.coordinates || {};
  const delays = initialProfile.delays || {};

  CONFIG_METADATA.forEach(group => {
    const section = document.createElement("div");
    section.className = "config-group-section";
    section.dataset.groupId = group.groupId;

    const header = document.createElement("div");
    header.className = "config-group-header";
    header.innerHTML = `
      <div class="config-group-title">
        <span>${group.title}</span>
        <span class="config-group-badge">${group.badge}</span>
      </div>
      <span style="font-family: var(--font-mono); font-size: 13px; font-weight: 900; color: var(--color-gray-700);">${group.items.length} 步</span>
    `;
    section.appendChild(header);

    const grid = document.createElement("div");
    grid.className = "config-grid";

    group.items.forEach(item => {
      grid.appendChild(createConfigCardDOM(item, coords, delays, "cfg"));
    });

    section.appendChild(grid);
    container.appendChild(section);
  });

  bindConfigEvents(container);
}

function bindConfigEvents(rootEl = document) {
  rootEl.querySelectorAll(".coord-val-x, .coord-val-y").forEach(input => {
    input.addEventListener("input", e => {
      const key = e.target.dataset.key;
      const card = e.target.closest(".config-item-card");
      if (!card) return;
      const x = parseInt(card.querySelector(".coord-val-x").value, 10) || 0;
      const y = parseInt(card.querySelector(".coord-val-y").value, 10) || 0;
      if (!initialProfile.coordinates) initialProfile.coordinates = {};
      initialProfile.coordinates[key] = [x, y];
      syncJsonFromVisual();
    });
  });

  rootEl.querySelectorAll(".coord-delay-sec-input").forEach(input => {
    input.addEventListener("click", e => e.stopPropagation());
    input.addEventListener("dblclick", e => e.stopPropagation());

    input.addEventListener("input", e => {
      const key = e.target.dataset.delayKey;
      if (!key) return;
      const rawVal = e.target.value.trim();
      const sec = parseFloat(rawVal);
      if (isNaN(sec) || sec < 0) return;

      const ms = Math.round(sec * 1000);
      if (!initialProfile.delays) initialProfile.delays = {};
      initialProfile.delays[key] = ms;

      document.querySelectorAll(`.coord-delay-sec-input[data-delay-key="${key}"]`).forEach(otherSecInput => {
        if (otherSecInput !== e.target) {
          otherSecInput.value = rawVal;
        }
      });

      document.querySelectorAll(`.delay-val-input[data-key="${key}"]`).forEach(msInput => {
        if (msInput !== document.activeElement) {
          msInput.value = ms;
        }
      });

      document.querySelectorAll(`[data-sec-key="${key}"]`).forEach(secHint => {
        secHint.textContent = `= ${(ms / 1000).toFixed(1)} 秒`;
      });

      document.querySelectorAll(`.config-delay-badge[data-delay-key="${key}"]`).forEach(badge => {
        badge.title = `关联延时键: ${key} (${ms}ms)`;
      });

      syncJsonFromVisual();
    });

    input.addEventListener("blur", e => {
      const key = e.target.dataset.delayKey;
      const rawVal = e.target.value.trim();
      const sec = parseFloat(rawVal);
      if (!isNaN(sec) && sec >= 0) {
        const ms = Math.round(sec * 1000);
        e.target.value = ms % 100 === 0 ? (ms / 1000).toFixed(1) : Number((ms / 1000).toFixed(2));
      } else {
        const currentMs = initialProfile.delays?.[key] ?? 350;
        e.target.value = currentMs % 100 === 0 ? (currentMs / 1000).toFixed(1) : Number((currentMs / 1000).toFixed(2));
      }
    });
  });

  rootEl.querySelectorAll(".delay-val-input").forEach(input => {
    input.addEventListener("input", e => {
      const key = e.target.dataset.key;
      const ms = parseInt(e.target.value, 10) || 0;
      if (!initialProfile.delays) initialProfile.delays = {};
      initialProfile.delays[key] = ms;

      const secVal = ms % 100 === 0 ? (ms / 1000).toFixed(1) : Number((ms / 1000).toFixed(2));

      document.querySelectorAll(`[data-sec-key="${key}"]`).forEach(secHint => {
        secHint.textContent = `= ${(ms / 1000).toFixed(1)} 秒`;
      });

      document.querySelectorAll(`.coord-delay-sec-input[data-delay-key="${key}"]`).forEach(secInput => {
        if (secInput !== document.activeElement) {
          secInput.value = secVal;
        }
      });

      document.querySelectorAll(`.config-delay-badge[data-delay-key="${key}"]`).forEach(badge => {
        badge.title = `关联延时键: ${key} (${ms}ms)`;
      });

      syncJsonFromVisual();
    });
  });

  rootEl.querySelectorAll(".btn-pick-single").forEach(btn => {
    btn.addEventListener("click", async e => {
      e.stopPropagation();
      if (isPickingCoord) return;
      const key = btn.dataset.key;
      const label = btn.dataset.label;
      const card = btn.closest(".config-item-card");

      isPickingCoord = true;
      btn.classList.add("picking");
      btn.innerHTML = "<span>⏳ 倒数3秒...</span>";
      showToast(`请在 3 秒内将鼠标移至【${label}】屏幕位置...`, "warning");

      try {
        const res = await window.pywebview.api.pick_coordinate_3s();
        if (res && res.x !== undefined) {
          if (!initialProfile.coordinates) initialProfile.coordinates = {};
          initialProfile.coordinates[key] = [res.x, res.y];
          if (card) {
            card.querySelector(".coord-val-x").value = res.x;
            card.querySelector(".coord-val-y").value = res.y;
            card.classList.add("highlight-flash");
            setTimeout(() => card.classList.remove("highlight-flash"), 1500);
          }
          syncJsonFromVisual();
          showToast(`【${label}】坐标已锁定: [${res.x}, ${res.y}]`, "success");
        }
      } catch (err) {
        showToast(`拾取异常: ${err}`, "error");
      } finally {
        isPickingCoord = false;
        btn.classList.remove("picking");
        btn.innerHTML = "<span>🎯 3秒拾取</span>";
      }
    });
  });
}

function syncJsonFromVisual() {
  const editor = document.getElementById("profile-json-editor");
  if (editor) {
    editor.value = JSON.stringify(initialProfile, null, 2);
  }
}

function syncVisualFromJson() {
  try {
    const editor = document.getElementById("profile-json-editor");
    if (!editor) return;
    initialProfile = JSON.parse(editor.value);
    renderVisualConfig();
    filterConfigCards();
  } catch (e) {
    showToast("JSON 语法解析错误，无法切回可视化面板", "error");
  }
}

function filterConfigCards() {
  const q = (document.getElementById("config-search-input")?.value || "").toLowerCase().trim();
  const groupPill = activeConfigGroup;

  document.querySelectorAll("#config-visual-container .config-group-section").forEach(sec => {
    const secGroup = sec.dataset.groupId;
    const groupMatches = groupPill === "all" || groupPill === secGroup;
    if (!groupMatches) {
      sec.style.display = "none";
      return;
    }

    let visibleCount = 0;
    sec.querySelectorAll(".config-item-card").forEach(card => {
      const text = `${card.dataset.label} ${card.dataset.key} ${card.dataset.desc}`.toLowerCase();
      const matches = !q || text.includes(q);
      card.style.display = matches ? "flex" : "none";
      if (matches) visibleCount++;
    });

    sec.style.display = visibleCount > 0 ? "flex" : "none";
  });
}

window.closeStepConfigModal = closeStepConfigModal;
window.renderVisualConfig = renderVisualConfig;
