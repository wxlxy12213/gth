// ============================================================================
// @AI-ANCHOR: [JS-TAB3-DOCS] 场景 03：业务员文书智能洗牌、与填报总控双向同步及独立出件工坊 (<320行微切片)
// 升级重点 (GTH V3.0)：
// 1. 修复原版 `handleDocPaste` 中误查 `#tab5-docs` 和 `.hidden` 导致 Ctrl+V 粘贴失效的 Bug（已对齐 `#scene-docs.active`）。
// 2. 打通「01 填报总控」与「03 文书工坊」的数据孤岛：支持一键从填报总控带入客户信息，以及将洗牌后的要素一键回填至填报总控。
// ============================================================================

let currentWashedDocType = "auto";
let currentDetectedDocType = "zhu_gai_shang";
let currentLoadedFilePath = "";
let currentGeneratedOutputPath = "";

const DOC_TYPE_META = {
  zhu_gai_shang: { name: "住改商证明", icon: "🏠", color: "var(--accent-yellow)", desc: "自动路由民房四邻表/小区楼房业主表，匹配店名，纯DOCX绝不生图" },
  lease_contract: { name: "房屋租赁合同", icon: "📑", color: "var(--accent-blue)", desc: "纯租赁合同按人名命名（租赁合同-姓名.docx），直通桌面" },
  canyin_chengnuoshu: { name: "餐饮承诺书", icon: "📜", color: "var(--accent-green)", desc: "自动刷新为办理当日最新日期，直接生成至桌面" },
  site_proof: { name: "场地使用证明", icon: "🏢", color: "var(--accent-pink)", desc: "自动判定自有或租赁，支持免字号或匹配店名" }
};

function getEffectiveDocType() {
  if (currentWashedDocType === "auto") {
    return currentDetectedDocType || "zhu_gai_shang";
  }
  return currentWashedDocType;
}

// @AI-ANCHOR: [DOC-TYPE-PILLS] 文书规范切换胶囊与预期出件文件名实时预览
function updateDocTypePills() {
  document.querySelectorAll(".doc-type-pill").forEach(pill => {
    const type = pill.getAttribute("data-doc-type");
    pill.classList.toggle("active", type === currentWashedDocType);
  });

  const effType = getEffectiveDocType();
  const meta = DOC_TYPE_META[effType] || DOC_TYPE_META.zhu_gai_shang;
  const badge = document.getElementById("wash-doc-type-badge");
  if (badge) {
    badge.textContent = `${meta.icon} 当前出件标准: ${meta.name} (${currentWashedDocType === "auto" ? "智能识别" : "手动锁定"})`;
  }
  const hint = document.getElementById("wash-rule-hint");
  if (hint) {
    hint.textContent = meta.desc;
  }
  updateEstimatedFilename();
}

function updateEstimatedFilename() {
  const effType = getEffectiveDocType();
  const subject = document.getElementById("wash-subject")?.value?.trim() || "";
  const operator = document.getElementById("wash-operator")?.value?.trim() || "经营者";
  const address = document.getElementById("wash-address")?.value?.trim() || "";

  let est = "";
  if (effType === "zhu_gai_shang") {
    const isApt = /(?:[0-9]{3,4}室|[0-9]+号楼|[0-9]+单元|小区|花园|公寓)/.test(address);
    const tag = isApt ? "小区楼房" : "民房";
    est = subject ? `住改商（${tag}）-${subject}-${operator}.docx` : `住改商（${tag}）-${operator}.docx`;
  } else if (effType === "lease_contract") {
    est = `租赁合同-${operator}.docx`;
  } else if (effType === "canyin_chengnuoshu") {
    est = subject ? `餐饮承诺书-${subject}.docx` : (operator && operator !== "经营者" ? `餐饮承诺书-${operator}.docx` : "餐饮承诺书.docx");
  } else if (effType === "site_proof") {
    est = subject ? `场地证明-${subject}-{operator}.docx`.replace("{operator}", operator) : `场地证明-${operator}.docx`;
  }

  const estElem = document.getElementById("wash-estimated-filename");
  if (estElem) estElem.textContent = est;
}

// @AI-ANCHOR: [DOC-WORKBENCH-SYNC] 填报总控 <-> 文书工坊 客户要素双向一键互通
window.syncWorkbenchToDocsStudio = function(switchToTab = false) {
  const setVal = (id, val) => {
    const el = document.getElementById(id);
    if (el) el.value = val || "";
  };
  const primaryScope = (currentState.scopes || []).find(s => !s.excluded && s.is_primary)
    || (currentState.scopes || []).find(s => !s.excluded);

  setVal("wash-subject", currentState.shop_name);
  setVal("wash-operator", currentState.owner_name);
  setVal("wash-operator-id", currentState.owner_id);
  setVal("wash-address", currentState.shop_address || currentState.id_addr);
  setVal("wash-scope", primaryScope ? primaryScope.name : "日用百货销售");
  setVal("wash-landlord", currentState.landlord_name);
  const _now = new Date();
  const _todayLocal = `${_now.getFullYear()}-${String(_now.getMonth() + 1).padStart(2, "0")}-${String(_now.getDate()).padStart(2, "0")}`;
  setVal("wash-sign-date", _todayLocal);

  if (currentState.usage === "lease" || currentState.landlord_name) {
    currentDetectedDocType = "lease_contract";
  } else {
    currentDetectedDocType = "zhu_gai_shang";
  }
  updateDocTypePills();

  if (switchToTab) {
    document.querySelector('.avant-top-bar .avant-nav-pill[data-tab="docs"]')?.click();
  }
  showToast(`已从填报总控带入客户「${currentState.owner_name || currentState.shop_name || "当前办件"}」`, "success");
};

window.syncDocsStudioToWorkbench = function() {
  const subject = document.getElementById("wash-subject")?.value?.trim() || "";
  const operator = document.getElementById("wash-operator")?.value?.trim() || "";
  const operatorId = document.getElementById("wash-operator-id")?.value?.trim() || "";
  const address = document.getElementById("wash-address")?.value?.trim() || "";
  const landlord = document.getElementById("wash-landlord")?.value?.trim() || "";
  const landlordId = document.getElementById("wash-landlord-id")?.value?.trim() || "";

  if (!subject && !operator && !address) {
    showToast("当前文书工坊尚无有效客户要素可回填", "warning");
    return;
  }

  batchUpdateState({
    shop_name: subject || currentState.shop_name,
    owner_name: operator || currentState.owner_name,
    owner_id: operatorId || currentState.owner_id,
    shop_address: address || currentState.shop_address,
    id_addr: currentState.id_addr || address,
    landlord_name: landlord,
    landlord_id: landlordId,
    usage: landlord ? "lease" : currentState.usage
  }, true);

  document.querySelector('.avant-top-bar .avant-nav-pill[data-tab="workbench"]')?.click();
  showToast(`已将清洗要素回填至 01 填报总控：${operator || subject}`, "success");
};

// @AI-ANCHOR: [DOC-WASH-DISPATCH] 接收文件路径调用后端清洗与桌面直通出件
async function processDocumentWash(filePath) {
  if (!filePath || !filePath.trim()) return;
  const cleanPath = filePath.trim().replace(/^["“”'‘’]+|["“”'‘’]+$/g, "").trim();
  currentLoadedFilePath = cleanPath;

  const statusLabel = document.getElementById("wash-file-status");
  if (statusLabel) {
    statusLabel.innerHTML = `正在清洗文书: <b>${cleanPath.split(/[/\\]/).pop()}</b>...`;
    statusLabel.style.display = "block";
  }

  if (!window.pywebview?.api?.wash_document) {
    showToast("后端通信接口尚未就绪，请稍后", "error");
    return;
  }

  const res = await window.pywebview.api.wash_document(cleanPath);
  if (res && res.status === "success") {
    currentDetectedDocType = res.doc_kind || "zhu_gai_shang";
    if (res.file_path) {
      currentLoadedFilePath = res.file_path;
      const pathInput = document.getElementById("doc-path-input");
      if (pathInput) pathInput.value = res.file_path;
    }
    const f = res.fields || {};
    const setVal = (id, val) => {
      const el = document.getElementById(id);
      if (el) el.value = val || "";
    };

    setVal("wash-subject", f.subject);
    setVal("wash-operator", f.operator);
    setVal("wash-operator-id", f.operator_id);
    setVal("wash-address", f.address);
    setVal("wash-scope", f.scope);
    setVal("wash-landlord", f.landlord);
    setVal("wash-landlord-id", f.landlord_id);
    setVal("wash-rent-amount", f.rent_amount || 10000);
    setVal("wash-sign-date", f.sign_date);

    updateDocTypePills();
    updateEstimatedFilename();

    if (statusLabel) {
      statusLabel.innerHTML = `✓ 已成功清洗解析: <b>${res.file_name}</b> (识别为: ${DOC_TYPE_META[res.doc_kind]?.name || res.doc_kind})`;
    }
    showToast(`文书清洗成功！识别为 ${DOC_TYPE_META[res.doc_kind]?.name || res.doc_kind}`, "success");
  } else {
    if (statusLabel) {
      statusLabel.innerHTML = `❌ 清洗失败: ${res?.message || "未知错误"}`;
    }
    showToast(res?.message || "文书清洗失败", "error");
  }
}

async function executeWashAndGenerate() {
  const effType = getEffectiveDocType();
  const fields = {
    subject: document.getElementById("wash-subject")?.value?.trim() || "",
    operator: document.getElementById("wash-operator")?.value?.trim() || "",
    operator_id: document.getElementById("wash-operator-id")?.value?.trim() || "",
    address: document.getElementById("wash-address")?.value?.trim() || "",
    scope: document.getElementById("wash-scope")?.value?.trim() || "",
    landlord: document.getElementById("wash-landlord")?.value?.trim() || "",
    landlord_id: document.getElementById("wash-landlord-id")?.value?.trim() || "",
    rent_amount: parseInt(document.getElementById("wash-rent-amount")?.value, 10) || 10000,
    sign_date: document.getElementById("wash-sign-date")?.value?.trim() || ""
  };

  if (effType !== "canyin_chengnuoshu" && !fields.operator && !fields.subject && !fields.address) {
    showToast("请至少填写或清洗出经营者姓名、主体店名或经营场所地址", "warning");
    return;
  }

  const btn = document.getElementById("btn-exec-wash-generate");
  if (btn) {
    btn.disabled = true;
    btn.textContent = "⚡ 正在生成标准文书至桌面...";
  }

  try {
    const res = await window.pywebview.api.generate_washed_document(effType, fields, true);
    if (res && res.status === "success") {
      currentGeneratedOutputPath = res.output_path;
      const resultCard = document.getElementById("wash-delivery-result");
      if (resultCard) {
        resultCard.style.display = "block";
        document.getElementById("wash-result-filename").textContent = res.filename;
        document.getElementById("wash-result-path").textContent = res.output_path;
        document.getElementById("wash-result-meta").textContent = `文件大小: ${(res.file_size / 1024).toFixed(1)} KB · 耗时: ${res.cost_ms}ms · 签署日期: ${res.date}`;
      }
      showToast(`已生成到桌面：${res.filename} (${res.cost_ms}ms)`, "success");
    } else {
      showToast(res?.message || "文书生成失败", "error");
    }
  } catch (err) {
    showToast(`文书生成异常: ${err}`, "error");
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = "⚡ 一键洗牌生成标准文书并直通桌面 (免建文件夹 · 纯净无图)";
    }
  }
}

function initDocsStudio() {
  const dropZone = document.getElementById("doc-drop-zone");
  const pathInput = document.getElementById("doc-path-input");
  const browseBtn = document.getElementById("btn-browse-doc");
  const washBtn = document.getElementById("btn-wash-path");

  // 修复原版 #tab5-docs ID 不匹配问题：正确检测 #scene-docs.active
  const handleDocPaste = async (e) => {
    const sceneDocs = document.getElementById("scene-docs");
    if (!sceneDocs || !sceneDocs.classList.contains("active")) return;
    if (e.target && e.target.tagName === "INPUT" && e.target.id !== "doc-path-input") return;

    const files = e.clipboardData?.files;
    if (files && files.length > 0) {
      e.preventDefault();
      const file = files[0];
      const filePath = file.path || file.name;
      if (pathInput) pathInput.value = filePath;
      await processDocumentWash(filePath);
      return;
    }

    const text = e.clipboardData?.getData("text")?.trim();
    if (text) {
      const cleanT = text.replace(/^["“”'‘’]+|["“”'‘’]+$/g, "").trim();
      if (/\.docx?$/i.test(cleanT)) {
        e.preventDefault();
        if (pathInput) pathInput.value = cleanT;
        await processDocumentWash(cleanT);
        return;
      }
    }

    if (window.pywebview?.api?.get_clipboard_doc_path) {
      const nativeDoc = await window.pywebview.api.get_clipboard_doc_path();
      if (nativeDoc) {
        e.preventDefault();
        if (pathInput) pathInput.value = nativeDoc;
        await processDocumentWash(nativeDoc);
      }
    }
  };

  if (dropZone) {
    dropZone.addEventListener("dragover", (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropZone.classList.add("drag-hover");
    });
    dropZone.addEventListener("dragleave", (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropZone.classList.remove("drag-hover");
    });
    dropZone.addEventListener("drop", async (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropZone.classList.remove("drag-hover");
      const files = e.dataTransfer?.files;
      if (files && files.length > 0) {
        const file = files[0];
        const filePath = file.path || file.name;
        if (pathInput) pathInput.value = filePath;
        await processDocumentWash(filePath);
      }
    });
    dropZone.addEventListener("click", async () => {
      if (window.pywebview?.api?.browse_doc_file) {
        const p = await window.pywebview.api.browse_doc_file();
        if (p) {
          if (pathInput) pathInput.value = p;
          await processDocumentWash(p);
        }
      }
    });
  }

  window.addEventListener("paste", handleDocPaste);

  browseBtn?.addEventListener("click", async (e) => {
    e.stopPropagation();
    if (window.pywebview?.api?.browse_doc_file) {
      const p = await window.pywebview.api.browse_doc_file();
      if (p) {
        if (pathInput) pathInput.value = p;
        await processDocumentWash(p);
      }
    }
  });

  document.getElementById("btn-wash-pull-from-wb")?.addEventListener("click", (e) => {
    e.stopPropagation();
    window.syncWorkbenchToDocsStudio(false);
  });

  document.getElementById("btn-wash-push-to-wb")?.addEventListener("click", () => {
    window.syncDocsStudioToWorkbench();
  });

  washBtn?.addEventListener("click", async () => {
    const p = pathInput?.value?.trim();
    if (!p) {
      showToast("请输入或拖拽进料文档路径", "warning");
      return;
    }
    await processDocumentWash(p);
  });

  pathInput?.addEventListener("keydown", async (e) => {
    if (e.key === "Enter") {
      const p = pathInput?.value?.trim();
      if (p) await processDocumentWash(p);
    }
  });

  document.querySelectorAll(".doc-type-pill").forEach(pill => {
    pill.addEventListener("click", () => {
      currentWashedDocType = pill.getAttribute("data-doc-type") || "auto";
      updateDocTypePills();
    });
  });

  ["wash-subject", "wash-operator", "wash-address"].forEach(id => {
    document.getElementById(id)?.addEventListener("input", updateEstimatedFilename);
  });

  document.getElementById("btn-exec-wash-generate")?.addEventListener("click", executeWashAndGenerate);

  document.getElementById("btn-wash-open-file")?.addEventListener("click", () => {
    if (currentGeneratedOutputPath && window.pywebview?.api?.open_word_file) {
      window.pywebview.api.open_word_file(currentGeneratedOutputPath);
    }
  });

  document.getElementById("btn-wash-reveal-file")?.addEventListener("click", () => {
    if (currentGeneratedOutputPath && window.pywebview?.api?.reveal_in_desktop) {
      window.pywebview.api.reveal_in_desktop(currentGeneratedOutputPath);
    }
  });

  document.getElementById("btn-wash-reset")?.addEventListener("click", () => {
    currentLoadedFilePath = "";
    if (pathInput) pathInput.value = "";
    const statusLabel = document.getElementById("wash-file-status");
    if (statusLabel) statusLabel.style.display = "none";
    const resultCard = document.getElementById("wash-delivery-result");
    if (resultCard) resultCard.style.display = "none";
    ["wash-subject", "wash-operator", "wash-operator-id", "wash-address", "wash-scope", "wash-landlord", "wash-landlord-id"].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.value = "";
    });
    updateDocTypePills();
    showToast("已清空文书洗牌工坊", "info");
  });

  updateDocTypePills();
}

window.initDocsStudio = initDocsStudio;
window.processDocumentWash = processDocumentWash;
