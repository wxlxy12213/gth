// ============================================================================
// @AI-ANCHOR: [JS-TAB2-SCOPE] 场景 02：经营范围黄金套餐速切、2064底库检索与代数差集计算 (<210行微切片)
// 升级重点 (GTH)：
// 1. 将原本越界写在 `tab_workbench.js` 中的经营范围检索框、首项选入、清空列表与代数差集事件完整收拢回本模块。
// 2. 同时驱动场景 01 (填报总控) 第 3 栏的黄金套餐胶囊条 (`#wb-quick-pkg-bar`) 与实时预览窗 (`#wb-scope-preview-text`)。
// ============================================================================

// @AI-ANCHOR: [SCOPE-PACKAGE-GRID] 黄金套餐按钮渲染与一键加载套餐
function renderPackageGrid(pkgs) {
  const container = document.getElementById("package-list-container");
  const quickBar = document.getElementById("wb-quick-pkg-bar");
  const countBadge = document.getElementById("package-count-badge");
  if (countBadge) countBadge.textContent = `${pkgs.length} 个`;

  if (container) {
    container.innerHTML = "";
    pkgs.forEach(pkg => {
      const tile = document.createElement("div");
      tile.className = `package-bento-tile ${currentState.active_package === pkg ? "active" : ""}`;
      tile.innerHTML = `
        <div style="font-weight: 900; font-size: 16.5px;">📦 ${pkg}</div>
        <div style="font-family: var(--font-mono); font-size: 12px; font-weight: 800; color: #333;">官方标准黄金组合</div>
      `;
      tile.onclick = async () => {
        await loadPackage(pkg);
      };
      container.appendChild(tile);
    });
  }

  if (quickBar) {
    quickBar.innerHTML = "";
    pkgs.forEach(pkg => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = `wb-pkg-pill ${currentState.active_package === pkg ? "active" : ""}`;
      btn.textContent = pkg;
      btn.onclick = async () => {
        await loadPackage(pkg);
      };
      quickBar.appendChild(btn);
    });
  }
}

async function loadPackage(pkgName, silent = false) {
  currentState.active_package = pkgName;
  renderPackageGrid(allPackages);
  if (window.pywebview?.api?.load_package_items) {
    const items = await window.pywebview.api.load_package_items(pkgName);
    if (items && items.length > 0) {
      currentState.scopes = items;
      if (pkgName === "百货店" && !window._defaultPackageScopes) {
        window._defaultPackageScopes = JSON.parse(JSON.stringify(items));
      }
      renderSelectedScopes();
      if (!silent) {
        showToast(`已装配套餐 [${pkgName}]，共 ${items.length} 个条目`, "success");
      }
    }
  }
}

// @AI-ANCHOR: [SCOPE-SELECTED-LIST] 已选经营范围渲染、工作台微件同步与主营/剔除操作
window.renderSelectedScopes = function() {
  const container = document.getElementById("selected-scopes-stream");
  const badge = document.getElementById("scope-count-badge");
  const navBadge = document.getElementById("nav-scope-count");
  const wbCount = document.getElementById("wb-scope-count");
  const wbPreview = document.getElementById("wb-scope-preview-text");

  const activeScopes = (currentState.scopes || []).filter(s => !s.excluded);
  if (badge) badge.textContent = activeScopes.length;
  if (navBadge) navBadge.textContent = activeScopes.length;
  if (wbCount) wbCount.textContent = activeScopes.length;

  if (wbPreview) {
    if (activeScopes.length > 0) {
      wbPreview.textContent = activeScopes.map((s, i) => `${i === 0 || s.is_primary ? "★" : ""}${s.name}`).join(" ； ");
    } else {
      wbPreview.textContent = "尚未选择经营范围，请点击上方套餐胶囊或进入 02 沙盒检索添加";
    }
  }

  if (!container) return;
  container.innerHTML = "";

  (currentState.scopes || []).forEach((sc, idx) => {
    const row = document.createElement("div");
    row.className = `scope-row-card ${sc.is_primary ? "is-primary" : ""} ${sc.is_permit ? "is-permit" : ""} ${sc.excluded ? "is-excluded" : ""}`;
    row.innerHTML = `
      <div style="display: flex; align-items: center; gap: 10px; flex: 1; flex-wrap: wrap;">
        <span style="font-family: var(--font-mono); font-size: 15px; font-weight: 900; color: var(--color-gray-500);">${String(idx + 1).padStart(2, "0")}.</span>
        <span style="font-size: 17.5px; font-weight: 900;">${sc.name}</span>
        <span style="font-family: var(--font-mono); font-size: 13px; color: var(--color-gray-500);">[${sc.code}]</span>
        ${sc.is_primary ? '<span style="background: var(--accent-yellow); padding: 2px 8px; font-size: 12.5px; border: 2px solid #000;">★ 主营置顶</span>' : ""}
        ${sc.is_permit ? '<span style="background: var(--accent-pink); color: #fff; padding: 2px 8px; font-size: 12.5px; border: 2px solid #000;">⚠️ 许可项目</span>' : ""}
      </div>
      <div style="display: flex; gap: 8px; flex-shrink: 0;">
        <button class="brutal-btn" style="padding: 4px 10px; font-size: 13px;" onclick="togglePrimary(${idx})">⭐设主营</button>
        <button class="brutal-btn" style="padding: 4px 10px; font-size: 13px;" onclick="toggleExclude(${idx})">${sc.excluded ? "↺ 恢复" : "✂️ 划线排除"}</button>
        <button class="brutal-btn btn-pink" style="padding: 4px 10px; font-size: 13px;" onclick="removeScope(${idx})">✕</button>
      </div>
    `;
    container.appendChild(row);
  });
  evalConfidence();
};

window.togglePrimary = function(idx) {
  currentState.scopes.forEach((s, i) => { s.is_primary = (i === idx); });
  renderSelectedScopes();
};
window.toggleExclude = function(idx) {
  currentState.scopes[idx].excluded = !currentState.scopes[idx].excluded;
  renderSelectedScopes();
};
window.removeScope = function(idx) {
  currentState.scopes.splice(idx, 1);
  renderSelectedScopes();
};

// @AI-ANCHOR: [SCOPE-SEARCH-DIFF-LISTENERS] 场景 02 检索框、选入首项、清空与差集比对事件绑定
function initScopeSandboxListeners() {
  const searchInput = document.getElementById("scope-search-input");
  const searchDrop = document.getElementById("scope-search-dropdown");
  let lastSearchHits = [];

  async function addScopeItem(h) {
    if (!h) return;
    const exists = currentState.scopes.some(s => s.code === h.code || s.name === h.name);
    if (!exists) {
      currentState.scopes.push({
        code: h.code || "CUSTOM",
        name: h.name,
        is_primary: currentState.scopes.length === 0,
        is_permit: !!h.is_permit,
        excluded: false
      });
      renderSelectedScopes();
      showToast(`已选入: ${h.name}`, "success");
    } else {
      showToast(`条目「${h.name}」已在列表中`, "warning");
    }
    if (searchDrop) searchDrop.style.display = "none";
    if (searchInput) searchInput.value = "";
  }

  searchInput?.addEventListener("input", async () => {
    const q = searchInput.value.trim();
    if (!q) {
      if (searchDrop) searchDrop.style.display = "none";
      lastSearchHits = [];
      return;
    }
    if (window.pywebview?.api?.search_scope) {
      const hits = await window.pywebview.api.search_scope(q);
      lastSearchHits = hits || [];
      if (lastSearchHits.length > 0 && searchDrop) {
        searchDrop.innerHTML = "";
        searchDrop.style.display = "block";
        lastSearchHits.slice(0, 12).forEach(h => {
          const row = document.createElement("div");
          row.style.padding = "9px 14px";
          row.style.borderBottom = "2px solid #000";
          row.style.cursor = "pointer";
          row.style.fontSize = "16px";
          row.style.fontWeight = "900";
          row.style.display = "flex";
          row.style.justifyContent = "space-between";
          row.innerHTML = `
            <span>＋ ${h.name} ${h.is_permit ? '<b style="color:var(--accent-pink);">[许可]</b>' : ""}</span>
            <span style="font-family: var(--font-mono); font-size: 13px; color: var(--color-gray-500);">[${h.code}]</span>
          `;
          row.onmouseover = () => { row.style.background = "var(--accent-yellow)"; };
          row.onmouseout = () => { row.style.background = "#ffffff"; };
          row.onclick = () => addScopeItem(h);
          searchDrop.appendChild(row);
        });
      } else if (searchDrop) {
        searchDrop.style.display = "none";
      }
    }
  });

  searchInput?.addEventListener("keydown", async (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      document.getElementById("btn-add-searched-scope")?.click();
    }
  });

  document.getElementById("btn-add-searched-scope")?.addEventListener("click", async () => {
    const q = (searchInput?.value || "").trim();
    if (!q) {
      showToast("请先输入拼音首字母或关键词检索经营范围", "warning");
      return;
    }
    if (lastSearchHits.length > 0) {
      await addScopeItem(lastSearchHits[0]);
    } else if (window.pywebview?.api?.search_scope) {
      const hits = await window.pywebview.api.search_scope(q);
      if (hits && hits.length > 0) {
        await addScopeItem(hits[0]);
      } else {
        showToast("未匹配到对应官方经营范围条目", "warning");
      }
    }
  });

  document.getElementById("btn-clear-scopes")?.addEventListener("click", () => {
    currentState.scopes = [];
    renderSelectedScopes();
    showToast("已清空已选经营范围", "info");
  });

  document.getElementById("btn-exec-diff")?.addEventListener("click", async () => {
    const text = document.getElementById("native-scope-text")?.value.trim() || "";
    if (!text) {
      showToast("请先粘贴政务网原生经营范围文本", "warning");
      return;
    }
    try {
      const res = await window.pywebview.api.diff_native_scopes(currentState.active_package, text);
      if (res) {
        const box = document.getElementById("diff-summary-content");
        if (box) {
          box.innerHTML = `
            <div style="color: #000; font-weight: 900;">✓ 套餐总条目: ${res.total_package_count} 项</div>
            <div style="color: var(--accent-pink); font-weight: 900;">⚡ 自动剔除已有项: ${res.native_hit_count} 项 (免重复勾选)</div>
            <div style="color: #000; background: var(--accent-green); padding: 2px 6px; border: 2px solid #000; display: inline-block; margin-top: 4px;">★ 本次实际待补勾选: ${res.to_add_count} 项</div>
            <div style="color: var(--color-gray-500); font-size: 13px; margin-top: 4px;">套餐外保留项: ${res.out_of_package_count} 项</div>
          `;
        }
        if (res.scopes) {
          currentState.scopes = res.scopes;
          renderSelectedScopes();
        }
        showToast(`差集计算完成，已自动剔除 ${res.native_hit_count} 个已有项`, "success");
      }
    } catch (err) {
      showToast(`差集计算异常: ${err}`, "error");
    }
  });
}

window.initScopeSandboxListeners = initScopeSandboxListeners;
window.loadPackage = loadPackage;
window.renderPackageGrid = renderPackageGrid;
