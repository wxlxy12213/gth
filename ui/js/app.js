// ============================================================================
// @AI-ANCHOR: [JS-APP-BOOTSTRAP] 前端启动总控：DOM初始化、动态真源挂载、F5热重载、Tab导航、Mini-HUD与CMD+K
// 升级重点 (GTH)：
// 1. 按微模块职责分别初始化 `initFormListeners`, `initScopeSandboxListeners`, `initDocsStudio`, `initStepBlocksInteraction`, `initHistoryVaultListeners`。
// 2. 从 `config/ocr_rules.json` 动态同步渲染属地乡镇 `<select>` 下拉框与 `TOWN_SUPERVISOR_MAP`，彻底收敛离散真源。
// 3. 新增 Alt+1 ~ Alt+5 场景极速切换快捷键。
// ============================================================================

// @AI-ANCHOR: [APP-INIT-DATA] 页面加载初始化、F5 配置热重载与后端首屏数据拉取
window.addEventListener("DOMContentLoaded", async () => {
  initTabNavigation();
  initHudToggle();
  initCmdKPalette();
  initFormListeners();
  if (window.initScopeSandboxListeners) window.initScopeSandboxListeners();
  if (window.initDocsStudio) window.initDocsStudio();
  initStepBlocksInteraction();
  if (window.initHistoryVaultListeners) window.initHistoryVaultListeners();
  initHotReloadShortcut();

  if (window.pywebview?.api) {
    await initBackendData();
    window.pywebview.api.ready_to_show();
  } else {
    window.addEventListener("pywebviewready", async () => {
      await initBackendData();
      window.pywebview.api.ready_to_show();
    });
  }
});

function initHotReloadShortcut() {
  window.addEventListener("keydown", async (e) => {
    if (e.key === "F5" || ((e.ctrlKey || e.metaKey) && (e.key === "r" || e.key === "R"))) {
      e.preventDefault();
      if (window.pywebview?.api?.reload_all_configs) {
        await window.pywebview.api.reload_all_configs();
      }
      location.reload();
    } else if (e.altKey && ["1", "2", "3", "4", "5"].includes(e.key)) {
      e.preventDefault();
      const idx = parseInt(e.key, 10) - 1;
      const pills = document.querySelectorAll(".avant-top-bar .avant-nav-pill");
      if (pills[idx]) pills[idx].click();
    }
  });
}

function syncTownSelectFromRules(ocrRules) {
  if (!ocrRules) return;
  if (ocrRules.supervisor_map) {
    Object.assign(TOWN_SUPERVISOR_MAP, ocrRules.supervisor_map);
  }
  const towns = ocrRules.towns_list;
  const townSel = document.getElementById("field-town");
  if (Array.isArray(towns) && towns.length > 0 && townSel) {
    const prevVal = currentState.town || townSel.value || "马头镇";
    townSel.innerHTML = "";
    // 优先将最常用的马头镇、郯城街道排在前面
    const ordered = [...new Set(["马头镇", "郯城街道", ...towns])];
    ordered.forEach(tw => {
      const opt = document.createElement("option");
      opt.value = tw;
      opt.textContent = tw;
      townSel.appendChild(opt);
    });
    if (ordered.includes(prevVal)) {
      townSel.value = prevVal;
    }
  }
}

async function initBackendData() {
  try {
    const res = await window.pywebview.api.get_initial_data();
    if (res) {
      initialProfile = res.profile || {};
      allPackages = res.packages || [];
      historyList = res.history || [];
      syncTownSelectFromRules(res.ocr_rules);

      const jsonEditor = document.getElementById("profile-json-editor");
      if (jsonEditor) jsonEditor.value = JSON.stringify(initialProfile, null, 2);

      renderVisualConfig();
      updateHistoryCounters(historyList.length);
      renderPackageGrid(allPackages);
      renderHistoryList(historyList);

      const defaultPkg = res.default_package || initialProfile.form_defaults?.default_package || "百货店";
      await loadPackage(defaultPkg, true);
      evalConfidence();
    }
  } catch (err) {
    showToast(`初始数据加载异常: ${err}`, "error");
  }
}

// @AI-ANCHOR: [APP-TAB-HUD-CTRL] 顶部五大场景 Tab 切换与 380x140 悬浮 Mini-HUD 伴随窗控制
function initTabNavigation() {
  const pills = document.querySelectorAll(".avant-top-bar .avant-nav-pill");
  pills.forEach(pill => {
    pill.addEventListener("click", () => {
      pills.forEach(p => p.classList.remove("active"));
      pill.classList.add("active");
      const target = pill.getAttribute("data-tab");
      document.querySelectorAll(".tab-scene").forEach(s => s.classList.remove("active"));
      const targetScene = document.getElementById(`scene-${target}`);
      if (targetScene) targetScene.classList.add("active");
    });
  });

  document.getElementById("btn-jump-scope-tab")?.addEventListener("click", () => {
    document.querySelector('.avant-top-bar .avant-nav-pill[data-tab="scope"]')?.click();
  });
}

function initHudToggle() {
  document.getElementById("btn-toggle-hud")?.addEventListener("click", () => setWindowMode(true));
  document.getElementById("btn-hud-restore")?.addEventListener("click", () => setWindowMode(false));

  window.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && (e.key === "m" || e.key === "M")) {
      e.preventDefault();
      const isHud = document.body.classList.contains("hud-mode");
      setWindowMode(!isHud);
    }
  });
}

window.setWindowMode = async function(enableHud) {
  if (enableHud) {
    document.body.classList.add("hud-mode");
    const active = getActiveStepsList();
    document.getElementById("hud-customer-name").textContent = currentState.owner_name || currentState.shop_name || "待办客户";
    document.getElementById("hud-step-tag").textContent = `步 ${active.join(",")}`;
  } else {
    document.body.classList.remove("hud-mode");
  }
  if (window.pywebview?.api?.toggle_mini_hud) {
    await window.pywebview.api.toggle_mini_hud(enableHud);
  }
};

window.copyHudField = async function(field) {
  let val = "";
  let desc = "";
  if (field === "name") { val = currentState.owner_name; desc = "姓名"; }
  else if (field === "id") { val = currentState.owner_id; desc = "身份证号"; }
  else if (field === "phone") { val = currentState.phone; desc = "联系电话"; }
  else if (field === "addr") { val = currentState.shop_address || currentState.id_addr; desc = "经营场所"; }

  if (!val) {
    showToast(`当前未提取到${desc}`, "warning");
    return;
  }
  if (window.pywebview?.api?.copy_text) {
    const ok = await window.pywebview.api.copy_text(val);
    if (ok) showToast(`已复制: ${val}`, "success");
    else showToast("剪贴板写入失败", "error");
  }
};

// @AI-ANCHOR: [APP-CMDK-PALETTE] CMD+K 极速命令面板与全局快捷键绑定
function initCmdKPalette() {
  const backdrop = document.getElementById("cmdk-backdrop");
  const input = document.getElementById("cmdk-search-input");
  const triggerBtn = document.getElementById("btn-trigger-cmdk");
  const results = document.getElementById("cmdk-results-container");

  function openPalette() {
    backdrop.classList.add("open");
    input.value = "";
    input.focus();
    renderCmdkResults("");
  }
  function closePalette() {
    backdrop.classList.remove("open");
  }

  triggerBtn?.addEventListener("click", openPalette);
  backdrop?.addEventListener("click", (e) => {
    if (e.target === backdrop) closePalette();
  });

  window.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && (e.key === "k" || e.key === "K")) {
      e.preventDefault();
      if (backdrop.classList.contains("open")) closePalette();
      else openPalette();
    } else if (e.key === "Escape") {
      closePalette();
      closeStepConfigModal();
      document.getElementById("parse-q-modal")?.classList.remove("open");
    }
  });

  input?.addEventListener("input", () => {
    renderCmdkResults(input.value.trim());
  });

  const SYSTEM_ACTIONS = [
    { label: "⚡ 一键编译出件 (所选积木步骤填报)", pinyin: "yjsc", action: () => { closePalette(); executeGenerateAll(); } },
    { label: "🧹 清空当前表单 / 开始下一单新办件", pinyin: "qk xbj reset", action: () => { closePalette(); document.getElementById("btn-top-reset")?.click(); } },
    { label: "📑 将当前客户送入 03 文书工坊精调洗牌", pinyin: "wsgf dlws", action: () => { closePalette(); window.syncWorkbenchToDocsStudio(true); } },
    { label: "🏢 单独生成《经营场所使用证明》 (前置准备专用)", pinyin: "cdzm", action: () => { closePalette(); executeGenerateSiteProofOnly(); } },
    { label: "🏠 单独生成《住改商证明》 (纯DOCX出件)", pinyin: "zgs", action: () => { closePalette(); executeGenerateZhugaiOnly(); } },
    { label: "🔄 直接解析 .Q 脚本恢复办件状态", pinyin: "jxq", action: () => { closePalette(); document.getElementById("btn-parse-q-trigger")?.click(); } },
    { label: "🔄 热重载全部 JSON 配置与界面 (Hot Reload - F5)", pinyin: "rzz", action: async () => { closePalette(); if (window.pywebview?.api?.reload_all_configs) await window.pywebview.api.reload_all_configs(); location.reload(); } },
    { label: "🪟 切换 380x140 悬浮伴随窗 (Toggle HUD)", pinyin: "hud", action: () => { closePalette(); setWindowMode(!document.body.classList.contains("hud-mode")); } },
    { label: "📋 抓取系统剪贴板并清洗 (Clipboard OCR)", pinyin: "jtb", action: () => { closePalette(); document.getElementById("btn-read-clipboard")?.click(); } },
    { label: "📂 打开客户主体输出目录 (Open Folder)", pinyin: "dkgd", action: () => { closePalette(); document.getElementById("btn-open-dir")?.click(); } }
  ];

  async function renderCmdkResults(q) {
    results.innerHTML = "";
    const query = q.toLowerCase();

    const matchedActions = SYSTEM_ACTIONS.filter(a => a.label.toLowerCase().includes(query) || a.pinyin.includes(query));
    matchedActions.forEach(act => {
      const row = document.createElement("div");
      row.className = "cmdk-row";
      row.innerHTML = `<span>${act.label}</span><span style="font-family: var(--font-mono); font-size: 13px; background: var(--accent-yellow); padding: 1px 6px; border: 2px solid #000;">ACTION</span>`;
      row.onclick = act.action;
      results.appendChild(row);
    });

    if (q.length >= 1 && window.pywebview?.api?.search_scope) {
      const hits = await window.pywebview.api.search_scope(q);
      if (hits && hits.length > 0) {
        hits.slice(0, 8).forEach(h => {
          const row = document.createElement("div");
          row.className = "cmdk-row";
          row.innerHTML = `<span>＋ 选入经营范围: <b>${h.name}</b></span><span style="font-family: var(--font-mono); font-size: 13px; background: var(--accent-pink); color: #fff; padding: 1px 6px; border: 2px solid #000;">SCOPE [${h.code}]</span>`;
          row.onclick = () => {
            currentState.scopes.push({
              code: h.code,
              name: h.name,
              is_primary: currentState.scopes.length === 0,
              is_permit: h.is_permit || false,
              excluded: false
            });
            renderSelectedScopes();
            showToast(`已选入经营范围: ${h.name}`, "success");
            closePalette();
          };
          results.appendChild(row);
        });
      }
    }
  }
}
