// @AI-ANCHOR: [STATE-STORE-CONTRACT] 微响应式状态树 (Micro-Reactive Store)、GB11643 国标模算与动态按需校验 (GTH Demo)
/**
 * state.js - 全局微响应式状态中心 (GTH Demo)
 * 核心升级：
 * 1. 引入基于 ES6 Proxy + 发布订阅 (`subscribeState` / `batchUpdateState`) 的轻量微响应式机制，彻底告别散乱的手动 DOM 同步。
 * 2. 内置与后端 `engine/id_validator.py` 完全同源的 18 位身份证 ISO 7064:1983.MOD 11-2 模算校验器。
 * 3. 人性化温和三态核验芯片（未填显示中性 `待填` / `免字号`，填错格式或校验位才亮红 `格式有误`，通过亮绿 `✓ 就绪`）。
 */

const _INITIAL_STATE_TEMPLATE = {
  owner_name: "",
  owner_id: "",
  phone: "",
  email: "",
  id_addr: "",
  shop_name: "",
  shop_address: "",
  town: "马头镇",
  supervisor: "马头所",
  stage: 2,
  usage: "own",
  landlord_name: "",
  landlord_id: "",
  step_start: 1,
  step_end: 5,
  run_mode: "to_end",
  enabled_steps: [1, 2, 3, 4, 5],
  include_site_proof: false,
  export_zhugai_images: true,
  scopes: [],
  active_package: "百货店",
  confidence: {},
  warnings: []
};

const _stateListeners = new Set();
let _syncScheduled = false;
let _rawState = JSON.parse(JSON.stringify(_INITIAL_STATE_TEMPLATE));

function _scheduleReactiveSync(changedKey) {
  if (_syncScheduled) return;
  _syncScheduled = true;
  queueMicrotask(() => {
    _syncScheduled = false;
    evalConfidence();
    _stateListeners.forEach(fn => {
      try {
        fn(window.currentState, changedKey);
      } catch (err) {
        console.debug("[GTH StateListener Error]", err);
      }
    });
  });
}

window.currentState = new Proxy(_rawState, {
  set(target, prop, value) {
    const prev = target[prop];
    target[prop] = value;
    if (prev !== value) {
      _scheduleReactiveSync(String(prop));
    }
    return true;
  }
});

window.subscribeState = function(listener) {
  if (typeof listener === "function") {
    _stateListeners.add(listener);
  }
  return () => _stateListeners.delete(listener);
};

window.batchUpdateState = function(patch, syncDom = true) {
  if (!patch || typeof patch !== "object") return;
  Object.assign(_rawState, patch);
  if (syncDom) {
    renderFormFromState();
  }
  _scheduleReactiveSync("*");
};

window.resetApplicantState = function() {
  const defaultScopes = Array.isArray(window._defaultPackageScopes)
    ? JSON.parse(JSON.stringify(window._defaultPackageScopes))
    : [];
  Object.assign(_rawState, JSON.parse(JSON.stringify(_INITIAL_STATE_TEMPLATE)), {
    scopes: defaultScopes,
    supervisor: window.TOWN_SUPERVISOR_MAP["马头镇"] || "马头所"
  });
  const ocrInput = document.getElementById("ocr-raw-input");
  if (ocrInput) ocrInput.value = "";
  renderFormFromState();
  evalConfidence();
  _scheduleReactiveSync("reset");
};

window.initialProfile = {};
window.allPackages = [];
window.historyList = [];
window.isGenerating = false;
window.isPickingCoord = false;
window.currentOutputDir = "";

// 默认乡镇-监管所映射（启动后自动从后端 config/ocr_rules.json 同步覆盖并动态渲染下拉框）
window.TOWN_SUPERVISOR_MAP = {
  "马头镇": "马头所",
  "郯城街道": "城区所",
  "郯城镇": "城区所",
  "李庄镇": "李庄所",
  "重坊镇": "重坊所",
  "红花镇": "红花所",
  "庙山镇": "庙山所",
  "杨集镇": "杨集所",
  "港上镇": "港上所",
  "高峰头镇": "高峰头所",
  "归昌乡": "归昌所",
  "胜利镇": "胜利所",
  "泉源镇": "泉源所",
  "花园镇": "花园所",
  "花园乡": "花园所",
  "郯城经济开发区": "经济开发区所"
};

window.FORM_FIELD_IDS = [
  "owner_name",
  "owner_id",
  "phone",
  "id_addr",
  "shop_name",
  "shop_address",
  "landlord_name",
  "landlord_id"
];

// @AI-ANCHOR: [STATE-ID-CHECKSUM] 前端 GB 11643 身份证 18 位加权模 11 实时核验器
const _ID_WEIGHTS = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2];
const _ID_CHECKS = ["1", "0", "X", "9", "8", "7", "6", "5", "4", "3", "2"];

window.validateIdCardFront = function(rawId) {
  const s = (rawId || "").trim().toUpperCase();
  if (!s) return { empty: true, valid: false, msg: "待填" };
  if (!/^\d{17}[\dX]$/.test(s)) {
    return { empty: false, valid: false, msg: `${s.length}/18位` };
  }
  let sum = 0;
  for (let i = 0; i < 17; i++) {
    sum += parseInt(s[i], 10) * _ID_WEIGHTS[i];
  }
  const expected = _ID_CHECKS[sum % 11];
  if (s[17] !== expected) {
    return { empty: false, valid: false, msg: `末位应为${expected}` };
  }
  return { empty: false, valid: true, msg: "✓ 模算通过" };
};

window.logCyberTerminal = function(level, text) {
  if (window.console && typeof window.console.debug === "function") {
    window.console.debug(`[GTH ${level}] ${text}`);
  }
};

window.showToast = function(msg, type = "info") {
  const container = document.getElementById("toast-container");
  if (!container) return;
  const b = document.createElement("div");
  b.className = `toast-box ${type}`;
  b.innerHTML = `<span>${type === "success" ? "✓" : (type === "error" ? "✗" : "⚡")}</span> <span>${msg}</span>`;
  container.appendChild(b);
  setTimeout(() => {
    b.style.opacity = "0";
    setTimeout(() => b.remove(), 220);
  }, 3200);
};

// @AI-ANCHOR: [STATE-STEPS-VALIDATOR] 积木步骤激活列表计算与按需动态必填校验
window.getActiveStepsList = function() {
  if (Array.isArray(currentState.enabled_steps) && currentState.enabled_steps.length > 0) {
    return [...new Set(currentState.enabled_steps.map(Number))].filter(n => n >= 1 && n <= 5).sort((a, b) => a - b);
  }
  const s = Math.max(1, Math.min(5, Number(currentState.step_start) || 1));
  const e = currentState.run_mode === "single_step" ? s : Math.max(s, Math.min(5, Number(currentState.step_end) || 5));
  const arr = [];
  for (let i = s; i <= e; i++) arr.push(i);
  return arr;
};

window.validateStateForSteps = function(steps) {
  const active = steps || getActiveStepsList();
  if (!active || active.length === 0) {
    return { ok: false, msg: "请至少点选启用 1 个步骤" };
  }

  const needStep1 = active.includes(1);
  const needStep2 = active.includes(2);
  const needStep3 = active.includes(3);
  const needStep4 = active.includes(4);
  const onlyStep2 = active.length === 1 && needStep2;
  const onlyStep5 = active.length === 1 && active.includes(5);

  if (onlyStep2) {
    const activeScopes = (currentState.scopes || []).filter(s => !s.excluded);
    if (activeScopes.length === 0) {
      return { ok: false, msg: "单跑【02 经营范围】时，请至少保留 1 条有效经营范围" };
    }
    return { ok: true, msg: "仅经营范围模式就绪" };
  }

  if (onlyStep5) {
    if (!currentState.town) {
      return { ok: false, msg: "单跑【05 属地监管所】时，请选择属地乡镇" };
    }
    return { ok: true, msg: "仅监管所模式就绪" };
  }

  if (needStep1) {
    if (!currentState.shop_name || !currentState.shop_name.trim()) {
      return { ok: false, msg: "包含【01 核名申报】时必须填写店铺全称/字号！（若办免字号请单击右侧取消 01 步）" };
    }
    if (!currentState.owner_name || !currentState.owner_name.trim()) {
      return { ok: false, msg: "包含【01 核名申报】时必须填写经营者姓名" };
    }
    const idCheck = validateIdCardFront(currentState.owner_id);
    if (!idCheck.valid) {
      return { ok: false, msg: `经营者身份证号未通过校验 (${idCheck.msg})` };
    }
  }

  if (needStep3) {
    if (!currentState.owner_name || !currentState.owner_name.trim()) {
      return { ok: false, msg: "执行【03 人员录入】需要填写经营者姓名" };
    }
    if (!/^1[3-9]\d{9}$/.test(currentState.phone || "")) {
      return { ok: false, msg: "执行【03 人员录入】需要有效的 11 位联系电话" };
    }
    const idCheck = validateIdCardFront(currentState.owner_id);
    if (!idCheck.valid) {
      return { ok: false, msg: `执行【03 人员录入】需要有效的 18 位身份证号 (${idCheck.msg})` };
    }
  }

  if (needStep4) {
    const addr = (currentState.shop_address || currentState.id_addr || "").trim();
    if (addr.length < 4) {
      return { ok: false, msg: "执行【04 场所填报】需要填写经营场所详细地址" };
    }
    if (currentState.usage === "lease" && !(currentState.landlord_name || "").trim()) {
      return { ok: false, msg: "租赁门面模式下，请填写出租方（房东）姓名" };
    }
  }

  return { ok: true, msg: "校验通过" };
};

// @AI-ANCHOR: [STATE-CONFIDENCE-STAGE] 温和三态字段置信度着色与文书 Stage 自动分流
window.evalConfidence = function() {
  function setFieldChip(id, stateType, label) {
    const chip = document.getElementById(`chip-${id}`);
    const input = document.getElementById(`field-${id}`);
    if (chip) {
      const clsMap = {
        pass: "conf-chip conf-green",
        warn: "conf-chip conf-amber",
        error: "conf-chip conf-red",
        neutral: "conf-chip conf-neutral"
      };
      chip.className = clsMap[stateType] || clsMap.neutral;
      chip.textContent = label;
    }
    if (input) {
      input.classList.toggle("input-error", stateType === "error");
    }
  }

  const active = getActiveStepsList();
  const hasStep1 = active.includes(1);
  const onlyStep2 = active.length === 1 && active.includes(2);
  const onlyStep5 = active.length === 1 && active.includes(5);

  // 1. 经营者姓名
  const nameVal = (currentState.owner_name || "").trim();
  if (nameVal.length >= 2) {
    setFieldChip("owner_name", "pass", "✓ 就绪");
  } else if (nameVal.length === 1) {
    setFieldChip("owner_name", "error", "至少2字");
  } else if (onlyStep2 || onlyStep5) {
    setFieldChip("owner_name", "warn", "本步免填");
  } else {
    setFieldChip("owner_name", "neutral", "待填");
  }

  // 2. 联系电话
  const phoneVal = (currentState.phone || "").trim();
  if (/^1[3-9]\d{9}$/.test(phoneVal)) {
    setFieldChip("phone", "pass", "✓ 就绪");
  } else if (phoneVal.length > 0) {
    setFieldChip("phone", "error", `${phoneVal.length}/11位`);
  } else if (onlyStep2 || onlyStep5 || (!active.includes(3) && !active.includes(4))) {
    setFieldChip("phone", "warn", "选填");
  } else {
    setFieldChip("phone", "neutral", "待填");
  }

  // 3. 身份证号 (GB 11643 模 11 校验)
  const idRes = validateIdCardFront(currentState.owner_id);
  if (idRes.valid) {
    setFieldChip("owner_id", "pass", idRes.msg);
  } else if (!idRes.empty) {
    setFieldChip("owner_id", "error", idRes.msg);
  } else if (onlyStep2 || onlyStep5 || (!hasStep1 && !active.includes(3))) {
    setFieldChip("owner_id", "warn", "选填");
  } else {
    setFieldChip("owner_id", "neutral", "待填");
  }

  // 4. 户籍地址
  const idAddrVal = (currentState.id_addr || "").trim();
  if (idAddrVal.length >= 4) {
    setFieldChip("id_addr", "pass", "✓ 就绪");
  } else if (idAddrVal.length > 0) {
    setFieldChip("id_addr", "error", "地址过短");
  } else if (!active.includes(3)) {
    setFieldChip("id_addr", "warn", "选填");
  } else {
    setFieldChip("id_addr", "neutral", "待填");
  }

  // 5. 店铺字号
  const shopVal = (currentState.shop_name || "").trim();
  if (shopVal.length >= 2) {
    setFieldChip("shop_name", "pass", "✓ 就绪");
  } else if (!hasStep1) {
    setFieldChip("shop_name", "warn", "免字号");
  } else {
    setFieldChip("shop_name", "neutral", "01步必填");
  }

  // 6. 属地乡镇
  setFieldChip("town", currentState.town ? "pass" : "neutral", currentState.town ? "✓ 就绪" : "待选");

  // 7. 经营场所地址
  const shopAddrVal = (currentState.shop_address || "").trim();
  if (shopAddrVal.length >= 4) {
    setFieldChip("shop_address", "pass", "✓ 就绪");
  } else if (shopAddrVal.length > 0) {
    setFieldChip("shop_address", "error", "地址过短");
  } else if (onlyStep2 || onlyStep5 || !active.includes(4)) {
    setFieldChip("shop_address", "warn", "选填");
  } else {
    setFieldChip("shop_address", "neutral", "待填");
  }

  // 8. 租赁模式下房东信息校验
  const llName = (currentState.landlord_name || "").trim();
  setFieldChip("landlord_name", llName ? "pass" : "neutral", llName ? "✓ 就绪" : "租赁必填");
  const llIdRes = validateIdCardFront(currentState.landlord_id);
  if (llIdRes.valid) {
    setFieldChip("landlord_id", "pass", "✓ 模算通过");
  } else if (!llIdRes.empty) {
    setFieldChip("landlord_id", "error", llIdRes.msg);
  } else {
    setFieldChip("landlord_id", "neutral", "选填");
  }

  // 更新顶部规则徽章与动态说明条
  const ruleBadge = document.getElementById("audit-rule-badge");
  const ruleStrip = document.getElementById("dynamic-rule-strip");
  if (ruleBadge && ruleStrip) {
    if (onlyStep2) {
      ruleBadge.className = "conf-chip conf-green";
      ruleBadge.textContent = "仅范围模式 (免填个人信息)";
      ruleStrip.innerHTML = "💡 <b>当前校验策略</b>：仅执行【02 经营范围】，无需强制填写姓名/身份证/字号，选好套餐或经营范围即可一键直发！";
    } else if (hasStep1) {
      ruleBadge.className = "conf-chip conf-amber";
      ruleBadge.textContent = `含核名 (${active.join("-")}步 · 需字号)`;
      ruleStrip.innerHTML = "💡 <b>当前校验策略</b>：含【01 核名申报】，<b>店铺字号、姓名、身份证</b>为必填；若办无字号个体户，请单击右侧「01」取消勾选。";
    } else {
      ruleBadge.className = "conf-chip conf-green";
      ruleBadge.textContent = `局部积木 (${active.join("-")}步 · 可免字号)`;
      ruleStrip.innerHTML = `💡 <b>当前校验策略</b>：已跳过【01 核名】，当前执行步骤 <b>[${active.join(", ")}]</b>，<b>支持免字号出件</b>，仅按所选环节校验必填项。`;
    }
  }

  // 更新文书分流显示与 HUD 标题
  const stageTag = document.getElementById("stage-desc-tag");
  if (stageTag) {
    if (currentState.usage === "lease" || currentState.landlord_name || currentState.landlord_id) {
      _rawState.stage = 3;
      stageTag.textContent = "Stage 3 (租赁合同 + 住改商)";
    } else if (!currentState.shop_name && (!currentState.shop_address || currentState.shop_address === currentState.id_addr)) {
      _rawState.stage = 1;
      stageTag.textContent = "Stage 1 (免字号模式)";
    } else {
      _rawState.stage = 2;
      stageTag.textContent = "Stage 2 (住改商 + 前两页导图)";
    }
  }

  const hudName = document.getElementById("hud-customer-name");
  if (hudName) {
    hudName.textContent = currentState.owner_name || currentState.shop_name || "待办客户";
  }
};

// @AI-ANCHOR: [STATE-DOM-SYNC] 状态树向工作台表单 DOM 双向渲染同步
window.renderFormFromState = function() {
  FORM_FIELD_IDS.forEach(f => {
    const el = document.getElementById(`field-${f}`);
    if (el && el !== document.activeElement) {
      el.value = currentState[f] || "";
    } else if (el && !el.value && currentState[f]) {
      el.value = currentState[f] || "";
    }
  });

  if (currentState.town) {
    const townSel = document.getElementById("field-town");
    if (townSel) townSel.value = currentState.town;
    const sup = currentState.supervisor || TOWN_SUPERVISOR_MAP[currentState.town] || "";
    _rawState.supervisor = sup;
    const supInput = document.getElementById("field-supervisor");
    const supTag = document.getElementById("sup-desc-tag");
    if (supInput) supInput.value = sup;
    if (supTag) supTag.textContent = sup;
  }

  const usage = currentState.usage || "own";
  document.querySelectorAll(".usage-tab-btn").forEach(btn => {
    btn.classList.toggle("active", btn.getAttribute("data-usage") === usage);
  });
  const leaseBox = document.getElementById("lease-box");
  if (leaseBox) {
    leaseBox.style.display = usage === "lease" ? "block" : "none";
  }

  const chkSite = document.getElementById("chk-include-site-proof");
  if (chkSite) chkSite.checked = !!currentState.include_site_proof;

  const chkZhugaiImg = document.getElementById("chk-export-zhugai-img");
  if (chkZhugaiImg) chkZhugaiImg.checked = currentState.export_zhugai_images !== false;

  if (typeof window.syncStepBlocksUI === "function") {
    window.syncStepBlocksUI();
  }

  if (typeof window.renderSelectedScopes === "function") {
    window.renderSelectedScopes();
  }
};
