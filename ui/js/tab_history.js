// ============================================================================
// @AI-ANCHOR: [JS-TAB5-HISTORY] 场景 05：历史办件档案列表渲染、搜索过滤、单条删除与一键调入 (<120行微切片)
// 升级重点 (GTH)：
// 将历史档案搜索过滤与清空全部历史的事件监听器收拢回本模块，保持微切片高内聚。
// ============================================================================

// @AI-ANCHOR: [HISTORY-RENDER-LIST] 历史办件计数器更新与卡片列表渲染绑定
function updateHistoryCounters(count) {
  const el1 = document.getElementById("metric-total-records");
  const el2 = document.getElementById("metric-total-records-inline");
  if (el1) el1.textContent = count;
  if (el2) el2.textContent = count;
}

function renderHistoryList(records) {
  const container = document.getElementById("history-stream-container");
  if (!container) return;
  container.innerHTML = "";

  if (!records || records.length === 0) {
    container.innerHTML = `<div style="font-size: 16px; font-weight: 900; color: var(--color-gray-500); padding: 20px;">暂无匹配的办件历史记录</div>`;
    return;
  }

  records.forEach((r, idx) => {
    const card = document.createElement("div");
    card.className = "history-record-card";
    const folderPath = r.extra?.target_dir || "";
    const recId = r.id || "";

    card.innerHTML = `
      <div style="display: flex; align-items: center; gap: 14px; flex: 1; min-width: 0;">
        <span style="font-family: var(--font-mono); font-size: 19px; font-weight: 900; background: #000; color: var(--accent-green); padding: 2px 8px;">${String(idx + 1).padStart(2, "0")}</span>
        <div style="min-width: 0;">
          <div style="font-size: 17.5px; font-weight: 900; color: #000;">${r.owner_name || "未填姓名"} <span style="font-size: 13.5px; color: var(--accent-pink);">[${r.town || "郯城"}]</span></div>
          <div style="font-size: 14.5px; font-weight: 800; color: #333; margin-top: 2px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${r.shop_name || "免字号个体户"} · ${r.phone || r.owner_id || ""}</div>
          <div style="font-family: var(--font-mono); font-size: 12px; color: var(--color-gray-500); margin-top: 2px;">🕒 ${r.timestamp || ""}</div>
        </div>
      </div>
      <div style="display: flex; gap: 6px; flex-shrink: 0;">
        <button class="brutal-btn btn-green btn-hist-restore" style="padding: 6px 10px; font-size: 13px;">⚡ 复原</button>
        ${folderPath ? `<button class="brutal-btn btn-yellow btn-hist-dir" style="padding: 6px 10px; font-size: 13px;">📂 目录</button>` : ""}
        <button class="brutal-btn btn-pink btn-hist-del" style="padding: 6px 10px; font-size: 13px;">🗑️ 删除</button>
      </div>
    `;

    const doRestore = () => {
      batchUpdateState(r.state_dict || r, true);
      document.querySelector('.avant-top-bar .avant-nav-pill[data-tab="workbench"]')?.click();
      showToast(`已复原历史办件: ${r.owner_name || r.shop_name}`, "success");
    };

    card.addEventListener("click", (e) => {
      if (e.target.closest("button")) return;
      doRestore();
    });
    card.querySelector(".btn-hist-restore")?.addEventListener("click", (e) => {
      e.stopPropagation();
      doRestore();
    });
    card.querySelector(".btn-hist-dir")?.addEventListener("click", (e) => {
      e.stopPropagation();
      window.pywebview?.api?.open_customer_folder(folderPath);
    });
    card.querySelector(".btn-hist-del")?.addEventListener("click", async (e) => {
      e.stopPropagation();
      if (window.pywebview?.api?.delete_history_item) {
        const res = await window.pywebview.api.delete_history_item(idx, recId);
        if (res && res.status === "success") {
          historyList = res.history || [];
          renderHistoryList(historyList);
          updateHistoryCounters(historyList.length);
          showToast(`已删除「${r.owner_name || r.shop_name}」的历史记录`, "info");
        }
      }
    });

    container.appendChild(card);
  });
}

// @AI-ANCHOR: [HISTORY-SEARCH-LISTENERS] 历史档案关键词实时过滤与一键清空监听
function initHistoryVaultListeners() {
  document.getElementById("history-search-input")?.addEventListener("input", (e) => {
    const q = e.target.value.trim().toLowerCase();
    if (!q) {
      renderHistoryList(historyList);
      return;
    }
    const filtered = historyList.filter(r => {
      const hay = `${r.owner_name || ""} ${r.shop_name || ""} ${r.town || ""} ${r.phone || ""} ${r.owner_id || ""} ${r.timestamp || ""}`.toLowerCase();
      return hay.includes(q);
    });
    renderHistoryList(filtered);
  });

  document.getElementById("btn-clear-history")?.addEventListener("click", async () => {
    if (window.pywebview?.api?.clear_all_history) {
      const res = await window.pywebview.api.clear_all_history();
      if (res && res.status === "success") {
        historyList = [];
        renderHistoryList([]);
        updateHistoryCounters(0);
        showToast("已清空全部历史办件记录", "success");
      }
    }
  });
}

window.initHistoryVaultListeners = initHistoryVaultListeners;
window.renderHistoryList = renderHistoryList;
window.updateHistoryCounters = updateHistoryCounters;
