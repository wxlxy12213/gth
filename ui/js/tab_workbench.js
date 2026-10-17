// ============================================================================
// @AI-ANCHOR: [JS-TAB1-WORKBENCH] 场景 01：表单事件绑定、粘贴即自动识萃、Q脚本逆向还原与一键出件中心
// 升级重点 (GTH Demo)：
// 1. 严格遵守单一职责：仅管理场景 01 (填报总控) 的 DOM 与事件（场景 02/03/04/05 的监听器已全部归位至对应 tab_*.js）。
// 2. 新增「粘贴即自动脱水识别」、「同户籍地址一键复制」、「一键清空新办件」、「送文书工坊洗牌」等符合人类直觉的高频微交互。
// ============================================================================

// @AI-ANCHOR: [WB-FORM-LISTENERS] 核心表单输入监听、自动识萃、解析.Q弹窗与交付柜操作
function initFormListeners() {
  FORM_FIELD_IDS.forEach(id => {
    const el = document.getElementById(`field-${id}`);
    if (el) {
      el.addEventListener("input", () => {
        currentState[id] = el.value.trim();
      });
    }
  });

  const townSel = document.getElementById("field-town");
  townSel?.addEventListener("change", () => {
    currentState.town = townSel.value;
    const sup = TOWN_SUPERVISOR_MAP[currentState.town] || `${currentState.town}所`;
    currentState.supervisor = sup;
    const supEl = document.getElementById("field-supervisor");
    const supTag = document.getElementById("sup-desc-tag");
    if (supEl) supEl.value = sup;
    if (supTag) supTag.textContent = sup;
  });

  const usageBtns = document.querySelectorAll(".usage-tab-btn");
  usageBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      usageBtns.forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      const u = btn.getAttribute("data-usage");
      currentState.usage = u;
      const leaseBox = document.getElementById("lease-box");
      if (leaseBox) leaseBox.style.display = u === "lease" ? "block" : "none";
    });
  });

  // 同户籍地址一键复制
  document.getElementById("btn-copy-id-addr")?.addEventListener("click", () => {
    const idAddr = (currentState.id_addr || document.getElementById("field-id_addr")?.value || "").trim();
    if (!idAddr) {
      showToast("请先填写或识别出户籍住所地址", "warning");
      return;
    }
    currentState.shop_address = idAddr;
    const shopAddrEl = document.getElementById("field-shop_address");
    if (shopAddrEl) shopAddrEl.value = idAddr;
    showToast("已将户籍地址同步至经营场所地址", "success");
  });

  // 一键清空 / 新办件按钮（顶部导航 + 第 2 栏右上角）
  const handleReset = () => {
    resetApplicantState();
    const artBox = document.getElementById("output-artifact-list");
    if (artBox) {
      artBox.innerHTML = "<div>已重置为新办件状态，请粘贴新客户资料...</div>";
    }
    showToast("已清空当前客户表单，可开始下一单新办件", "info");
  };
  document.getElementById("btn-reset-form")?.addEventListener("click", handleReset);
  document.getElementById("btn-top-reset")?.addEventListener("click", handleReset);

  // 送入文书工坊按钮
  document.getElementById("btn-push-to-docs")?.addEventListener("click", () => {
    if (typeof window.syncWorkbenchToDocsStudio === "function") {
      window.syncWorkbenchToDocsStudio(true);
    }
  });

  document.getElementById("chk-include-site-proof")?.addEventListener("change", (e) => {
    currentState.include_site_proof = !!e.target.checked;
  });

  document.getElementById("chk-export-zhugai-img")?.addEventListener("change", (e) => {
    currentState.export_zhugai_images = !!e.target.checked;
  });

  document.getElementById("btn-read-clipboard")?.addEventListener("click", async () => {
    if (window.pywebview?.api?.read_clipboard) {
      const text = await window.pywebview.api.read_clipboard();
      if (text) {
        document.getElementById("ocr-raw-input").value = text;
        await cleanOcrText(text);
      } else {
        showToast("剪贴板中无有效文本", "warning");
      }
    }
  });

  document.getElementById("btn-clean-ocr")?.addEventListener("click", async () => {
    const text = document.getElementById("ocr-raw-input").value;
    await cleanOcrText(text);
  });

  // 粘贴进料文本框即自动触发智能脱水（免二次点击）
  const ocrInput = document.getElementById("ocr-raw-input");
  ocrInput?.addEventListener("paste", () => {
    setTimeout(async () => {
      const text = ocrInput.value.trim();
      if (text.length >= 6) {
        await cleanOcrText(text);
      }
    }, 60);
  });

  document.getElementById("btn-generate-all")?.addEventListener("click", executeGenerateAll);
  document.getElementById("btn-gen-site-proof")?.addEventListener("click", executeGenerateSiteProofOnly);
  document.getElementById("btn-gen-zhugai-img")?.addEventListener("click", executeGenerateZhugaiOnly);

  document.getElementById("btn-open-dir")?.addEventListener("click", () => {
    if (window.pywebview?.api?.open_customer_folder) {
      window.pywebview.api.open_customer_folder(currentOutputDir);
    }
  });

  // 解析已有 .Q 脚本弹窗
  const parseModal = document.getElementById("parse-q-modal");
  document.getElementById("btn-parse-q-trigger")?.addEventListener("click", () => {
    parseModal?.classList.add("open");
    document.getElementById("parse-q-input")?.focus();
  });
  document.getElementById("btn-parse-q-close")?.addEventListener("click", () => {
    parseModal?.classList.remove("open");
  });
  document.getElementById("btn-parse-q-confirm")?.addEventListener("click", async () => {
    const val = document.getElementById("parse-q-input")?.value.trim();
    if (!val) {
      showToast("请粘贴 .Q 脚本内容或路径", "warning");
      return;
    }
    if (window.pywebview?.api?.parse_q_file) {
      const res = await window.pywebview.api.parse_q_file(val);
      if (res && res.status === "success" && res.state) {
        batchUpdateState(res.state, true);
        parseModal?.classList.remove("open");
        showToast(`已从 .Q 脚本直接还原客户：${currentState.owner_name || currentState.shop_name || "成功"}`, "success");
      } else {
        showToast(res?.message || "解析失败", "error");
      }
    }
  });
}

// @AI-ANCHOR: [WB-OCR-CLEAN] 调用后端清洗 OCR 原始文本并同步响应式状态树
async function cleanOcrText(rawText) {
  if (!rawText || !rawText.trim()) {
    showToast("请输入或粘贴原始进料文本", "warning");
    return;
  }
  const t0 = performance.now();
  try {
    const state = await window.pywebview.api.clean_ocr(rawText);
    const cost = (performance.now() - t0).toFixed(2);
    const badge = document.getElementById("ocr-cost-badge");
    if (badge) badge.textContent = `${cost} ms`;

    if (state) {
      const keepSteps = currentState.enabled_steps;
      const keepSiteProof = currentState.include_site_proof;
      const keepZhugaiImg = currentState.export_zhugai_images;
      batchUpdateState({
        ...state,
        enabled_steps: keepSteps,
        include_site_proof: keepSiteProof,
        export_zhugai_images: keepZhugaiImg
      }, true);

      if (state.warnings && state.warnings.length > 0) {
        showToast(`识别完成 (${cost}ms)：${state.warnings[0]}`, "warning");
      } else {
        showToast(`智能脱水完成 (${cost}ms)`, "success");
      }
    }
  } catch (err) {
    showToast(`OCR 脱水异常: ${err}`, "error");
  }
}

// @AI-ANCHOR: [WB-GENERATE-DISPATCH] 全套一键出件、单步重编 .Q、独立场地证明与住改商单出
function baseName(p) {
  return (p || "").split(/[/\\]/).pop() || p;
}

window.executeGenerateAll = async function() {
  if (isGenerating) return;

  const activeSteps = getActiveStepsList();
  const check = validateStateForSteps(activeSteps);
  if (!check.ok) {
    showToast(check.msg, "error");
    return;
  }

  isGenerating = true;
  const btn = document.getElementById("btn-generate-all");
  if (btn) {
    btn.disabled = true;
    btn.textContent = "⏳ 正在编译脚本与生成配套文书...";
  }

  try {
    const includeSite = !!document.getElementById("chk-include-site-proof")?.checked;
    const exportImgs = document.getElementById("chk-export-zhugai-img")
      ? !!document.getElementById("chk-export-zhugai-img").checked
      : true;

    const payload = {
      ...currentState,
      enabled_steps: activeSteps,
      include_site_proof: includeSite,
      export_zhugai_images: exportImgs
    };
    const res = await window.pywebview.api.generate_all(payload);
    if (res && res.status === "success") {
      currentOutputDir = res.target_dir;
      const docs = res.docs || {};
      const docLines = Object.entries(docs).map(([, v]) => {
        const icon = v.endsWith(".png") ? "🖼️ 直传图" : "📄 文书";
        return `<div style="color: #000; font-weight: 900;">✓ ${icon}: ${baseName(v)}</div>`;
      }).join("");

      const artBox = document.getElementById("output-artifact-list");
      if (artBox) {
        artBox.innerHTML = `
          <div style="color: #000; font-weight: 900;">✓ 填报脚本 (${res.step_label}): ${baseName(res.q_file)}</div>
          <div style="color: #000; font-weight: 900;">✓ F10 待跑槽位: ${baseName(res.fixed_slot_q)}</div>
          ${docLines}
          <div style="color: var(--color-gray-700);">📂 桌面主体目录: ${res.customer_folder}</div>
          <div style="color: var(--accent-pink); font-weight: 900;">⚡ 总耗时: ${res.cost_ms} ms</div>
        `;
      }
      showToast(`出件成功 (${res.cost_ms}ms)！已生成脚本 [${res.step_label}] 与配套材料`, "success");

      const initData = await window.pywebview.api.get_initial_data();
      if (initData?.history) {
        historyList = initData.history;
        renderHistoryList(historyList);
        updateHistoryCounters(historyList.length);
      }
    } else {
      showToast(`出件失败: ${res?.message || "未知错误"}`, "error");
    }
  } catch (err) {
    showToast(`出件异常: ${err}`, "error");
  } finally {
    isGenerating = false;
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = "<span>⚡ 一键编译出件 (所选步骤 .Q + 配套文书)</span>";
    }
  }
};

window.recompileStep = async function(stepIdx) {
  const check = validateStateForSteps([stepIdx]);
  if (!check.ok) {
    showToast(check.msg, "error");
    return;
  }

  showToast(`正在单独重编第 ${stepIdx} 步...`, "info");
  const res = await window.pywebview.api.quick_recompile_step(stepIdx, currentState);
  if (res && res.status === "success") {
    currentOutputDir = res.target_dir || currentOutputDir;
    const artBox = document.getElementById("output-artifact-list");
    if (artBox) {
      artBox.innerHTML = `
        <div style="color: #000; background: var(--accent-green); padding: 2px 6px; border: 2px solid #000; font-weight: 900;">✓ 单步直发就绪：仅第 0${stepIdx} 步已推送至 F10 待跑槽位！</div>
        <div style="color: #000; font-weight: 900; margin-top: 3px;">✓ 单步脚本: ${baseName(res.q_file)}</div>
        <div style="color: #000; font-weight: 900;">✓ F10 槽位: ${baseName(res.fixed_slot_q)}</div>
        <div style="color: var(--accent-pink); font-weight: 900;">⚡ 耗时: ${res.cost_ms} ms (现在切去政务网按 F10 仅跑第 ${stepIdx} 步)</div>
      `;
    }
    showToast(`第 0${stepIdx} 步单步重编完成 (${res.cost_ms}ms)，按 F10 即可执行！`, "success");
  } else {
    showToast(`单步重编失败: ${res?.message || ""}`, "error");
  }
};

async function executeGenerateSiteProofOnly() {
  if (!currentState.owner_name && !currentState.shop_name) {
    showToast("生成《场地使用证明》请至少填写经营者姓名或字号", "warning");
    return;
  }
  const res = await window.pywebview.api.generate_site_proof_standalone(currentState);
  if (res && res.status === "success") {
    currentOutputDir = res.target_dir;
    const files = Object.values(res.docs || {}).map(baseName).join(", ");
    const artBox = document.getElementById("output-artifact-list");
    if (artBox) {
      artBox.innerHTML = `
        <div style="color: #000; background: var(--accent-yellow); padding: 2px 6px; border: 2px solid #000; font-weight: 900;">🏢 独立场地使用证明已生成！</div>
        <div style="color: #000; font-weight: 900; margin-top: 3px;">✓ 文件: ${files}</div>
        <div style="color: var(--color-gray-700);">📂 桌面目录: ${res.customer_folder} (${res.cost_ms}ms)</div>
      `;
    }
    showToast(`已单独生成《场地使用证明》(${res.cost_ms}ms)`, "success");
  } else {
    showToast(res?.message || "场地证明生成失败", "error");
  }
}

async function executeGenerateZhugaiOnly() {
  if (!currentState.owner_name && !currentState.shop_name) {
    showToast("生成《住改商证明》请至少填写姓名或字号", "warning");
    return;
  }
  const res = await window.pywebview.api.generate_zhugai_standalone(currentState);
  if (res && res.status === "success") {
    currentOutputDir = res.target_dir;
    const docList = Object.values(res.docs || {}).map(v => `<div style="color:#000;font-weight:900;">✓ ${baseName(v)}</div>`).join("");
    const artBox = document.getElementById("output-artifact-list");
    if (artBox) {
      artBox.innerHTML = `
        <div style="color: #000; background: var(--accent-blue); padding: 2px 6px; border: 2px solid #000; font-weight: 900;">🏠 住改商证明已生成（纯 DOCX 出件）！</div>
        ${docList}
        <div style="color: var(--color-gray-700);">📂 桌面目录: ${res.customer_folder} (${res.cost_ms}ms)</div>
      `;
    }
    showToast(`住改商证明已生成 (${res.cost_ms}ms)`, "success");
  } else {
    showToast(res?.message || "生成失败", "error");
  }
}

window.executeGenerateSiteProofOnly = executeGenerateSiteProofOnly;
window.executeGenerateZhugaiOnly = executeGenerateZhugaiOnly;
window.executeGenerateZhugaiImagesOnly = executeGenerateZhugaiOnly;
