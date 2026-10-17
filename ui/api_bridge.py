# @AI-ANCHOR: [BRIDGE-CORE-INIT] PyWebView 前后端通信桥接路由层 (<340行微切片)
"""api_bridge.py - WebView2 前后端数据交互与业务调度桥接器 (瘦身解耦版)。

架构升级重点：
1. 彻底解除上帝类膨胀：所有 Win32 API、剪贴板、文件选择框、资源管理器调起与 HUD 句柄控制已下沉至 `engine/win_os_service.py`。
2. 抽取 `_resolve_customer_workspace()` 与 `_deploy_q_scripts()` 公共辅助方法，消除 4 个出件接口中的重复目录解析与双槽位编译代码。
3. 100% 保持前端 `window.pywebview.api.*` 全部方法名与返回结构兼容。
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from engine.doc_wash_engine import generate_washed_document, wash_document_file
from engine.docx_engine import (
    _generate_zhugai_in_process,
    generate_documents,
    generate_site_proof_only,
)
from engine.history_manager import HistoryManager
from engine.models import ApplicantState, ScopeItem
from engine.ocr_cleaner import clean_raw_ocr
from engine.ocr_rules_loader import load_ocr_rules
from engine.q_compiler import _load_steps_dsl, compile_q_script, parse_q_script
from engine.scope_search import ScopeSearchEngine
from engine.subject_dir import resolve_subject_dir
from engine.win_os_service import (
    browse_doc_file_dialog,
    force_exit_process,
    get_clipboard_doc_path,
    open_file_native,
    pick_screen_coordinate,
    read_clipboard_text,
    reveal_in_explorer,
    switch_window_hud_mode,
    write_clipboard_text,
)

logger = logging.getLogger("gth.api_bridge")

_ROOT = Path(__file__).resolve().parent.parent
_CONFIG_DIR = _ROOT / "config"
_PROFILE_PATH = _CONFIG_DIR / "portal_profile_371300.json"
_MANIFEST_CACHE_DIR = _ROOT / ".cache" / "manifests"


class ApiBridge:
    """供 JavaScript 通过 window.pywebview.api 调用的轻量 IPC 路由网关。"""

    def __init__(self, app_window: Any = None) -> None:
        self._app_window = app_window
        self.current_state = ApplicantState()
        self.scope_engine = ScopeSearchEngine.instance()

    def set_app_window(self, window: Any) -> None:
        """安全注入窗口宿主句柄。"""
        self._app_window = window

    # ─── 内部公共收敛辅助方法 ───────────────────────────────────────────────
    def _resolve_customer_workspace(self, state: ApplicantState) -> tuple[str, str, Path]:
        """统一解析经营者名称、字号与桌面主体文件夹路径。"""
        owner_name = (state.owner_name or "").strip() or "个体户"
        shop_title = (state.shop_name or "").strip()
        subject_name = shop_title if (shop_title and shop_title != "未定字号") else owner_name
        customer_dir = resolve_subject_dir(subject_name)
        return owner_name, shop_title, customer_dir

    def _deploy_q_scripts(
        self,
        state: ApplicantState,
        profile: dict[str, Any],
        customer_dir: Path,
        q_filename: str,
    ) -> tuple[Path, Path, str]:
        """统一编译并分发 .Q 脚本至桌面主体目录、固定待跑槽位与按键精灵工作目录。"""
        q_file_path = customer_dir / q_filename
        compile_q_script(state, profile, q_file_path)

        fixed_slot_q = customer_dir / "【当前待跑】个体户自动填报.Q"
        compile_q_script(state, profile, fixed_slot_q)

        key_sprite_dir = Path(
            profile.get("key_sprite_script_dir", r"C:\Program Files (x86)\按键精灵\按键精灵2014\QMScript")
        )
        anjian_slot_path = ""
        if key_sprite_dir.exists():
            try:
                anjian_fixed = key_sprite_dir / "【当前待跑】个体户自动填报.Q"
                compile_q_script(state, profile, anjian_fixed)
                anjian_slot_path = str(anjian_fixed)
            except Exception as exc:
                logger.debug("写入按键精灵本机目录跳过: %s", exc)
        return q_file_path, fixed_slot_q, anjian_slot_path

    # @AI-ANCHOR: [BRIDGE-INITIAL-DATA] 首屏加载配置、套餐、历史与OCR规则
    def get_initial_data(self) -> dict[str, Any]:
        """页面加载时获取初始数据（配置、常用套餐、历史记录、OCR规则与乡镇映射）。"""
        profile = self.get_profile()
        ocr_rules = load_ocr_rules(force_reload=True)
        packages = list(self.scope_engine.packages.keys())
        history = HistoryManager.load_history()
        return {
            "profile": profile,
            "ocr_rules": ocr_rules,
            "packages": packages,
            "history": history,
            "default_package": "百货店",
        }

    def reload_all_configs(self) -> dict[str, Any]:
        """一键热重载所有 JSON 配置文件（无需重启 EXE，修改配置秒级生效）。"""
        ocr_rules = load_ocr_rules(force_reload=True)
        _load_steps_dsl(force_reload=True)
        self.scope_engine._load_data()
        return {
            "status": "success",
            "profile": self.get_profile(),
            "ocr_rules": ocr_rules,
            "packages": list(self.scope_engine.packages.keys()),
            "history": HistoryManager.load_history(),
        }

    # @AI-ANCHOR: [BRIDGE-OCR-CLEAN] 接收前端文本或剪贴板执行 OCR 智能脱水
    def clean_ocr(self, raw_text: str) -> dict[str, Any]:
        """清洗 OCR 文本并根据原生经营范围比对套餐。"""
        load_ocr_rules()
        self.current_state = clean_raw_ocr(raw_text)
        pkg_name = self.current_state.active_package or "百货店"

        diff_summary: dict[str, Any] | None = None
        if self.current_state.raw_scope_text:
            diff_res = self.scope_engine.diff_package_with_native(pkg_name, self.current_state.raw_scope_text)
            diff_summary = diff_res
            self.current_state.scopes = [ScopeItem.from_dict(s) for s in diff_res["scopes"]]
        else:
            codes = self.scope_engine.get_package_codes(pkg_name) or self.scope_engine.get_package_codes("百货")
            self.current_state.scopes = []
            for i, code in enumerate(codes):
                item = self.scope_engine.code_map.get(code)
                if item:
                    self.current_state.scopes.append(
                        ScopeItem(
                            code=code,
                            name=item["name"],
                            is_primary=(i == 0),
                            is_permit=bool(item.get("is_permit", False)),
                            excluded=False,
                            is_native_existing=False,
                        )
                    )

        state_dict = self.current_state.to_dict()
        if diff_summary:
            state_dict["diff_summary"] = {
                "package_name": diff_summary["package_name"],
                "total_package_count": diff_summary["total_package_count"],
                "native_hit_count": diff_summary["native_hit_count"],
                "to_add_count": diff_summary["to_add_count"],
                "out_of_package_count": diff_summary["out_of_package_count"],
                "native_hit_items": diff_summary["native_hit_items"],
                "out_of_package_items": diff_summary["out_of_package_items"],
            }
        return state_dict

    def diff_native_scopes(self, package_name: str, raw_scope_text: str) -> dict[str, Any]:
        """按套餐比对原生经营范围：把原生已有但套餐包含的从待点选清单中剔除。"""
        pkg_name = package_name or self.current_state.active_package or "百货店"
        diff_res = self.scope_engine.diff_package_with_native(pkg_name, raw_scope_text)
        self.current_state.active_package = pkg_name
        self.current_state.raw_scope_text = raw_scope_text
        self.current_state.scopes = [ScopeItem.from_dict(s) for s in diff_res["scopes"]]
        return diff_res

    def load_package_items(self, package_name: str) -> list[dict[str, Any]]:
        """按行业黄金套餐加载条目。"""
        codes = self.scope_engine.get_package_codes(package_name)
        items: list[dict[str, Any]] = []
        for i, code in enumerate(codes):
            it = self.scope_engine.code_map.get(code)
            if it:
                items.append({
                    "code": code,
                    "name": it["name"],
                    "is_primary": (i == 0),
                    "is_permit": bool(it.get("is_permit", False)),
                    "excluded": False,
                })
        return items

    def search_scope(self, query: str) -> list[dict[str, Any]]:
        """拼音首字母或关键词毫秒检索底库（< 1.0 ms）。"""
        return self.scope_engine.search(query, limit=25)

    def get_profile(self) -> dict[str, Any]:
        """获取当前门户配置字典。"""
        if _PROFILE_PATH.exists():
            try:
                return json.loads(_PROFILE_PATH.read_text(encoding="utf-8"))
            except Exception as exc:
                logger.warning("读取配置文件失败: %s", exc)
        return {}

    # @AI-ANCHOR: [BRIDGE-PROFILE-COORD] 保存门户坐标/延时配置与屏幕坐标拾取器
    def save_profile(self, new_profile: dict[str, Any]) -> bool:
        """保存更新外置配置并热重载生效。"""
        try:
            _PROFILE_PATH.write_text(json.dumps(new_profile, ensure_ascii=False, indent=2), encoding="utf-8")
            return True
        except Exception as exc:
            logger.error("保存配置异常: %s", exc)
            return False

    def pick_coordinate_3s(self) -> dict[str, int]:
        """3秒倒计时拾取当前鼠标物理屏幕坐标。"""
        return pick_screen_coordinate(3.0)

    def read_clipboard(self) -> str:
        """读取系统剪贴板纯文本。"""
        return read_clipboard_text()

    def copy_text(self, text: str) -> bool:
        """复制文本至剪贴板。"""
        return write_clipboard_text(text)

    def delete_history_item(self, index: int = -1, record_id: str = "") -> dict[str, Any]:
        """删除单条历史办件档案。"""
        updated = HistoryManager.delete_snapshot(index=index, record_id=record_id)
        return {"status": "success", "history": updated}

    def clear_all_history(self) -> dict[str, Any]:
        """清空全部历史办件档案。"""
        updated = HistoryManager.clear_history()
        return {"status": "success", "history": updated}

    # @AI-ANCHOR: [BRIDGE-PARSE-Q] 逆向解析外部或历史 .Q 脚本还原表单
    def parse_q_file(self, q_path_or_text: str) -> dict[str, Any]:
        """直接从 .Q 脚本文件或内容逆向解析恢复办件状态。"""
        try:
            st = parse_q_script(q_path_or_text)
            self.current_state = st
            return {"status": "success", "state": st.to_dict()}
        except Exception as exc:
            return {"status": "error", "message": f"解析 .Q 脚本失败: {exc}"}

    # @AI-ANCHOR: [BRIDGE-DOC-WASH] 业务员进料智能洗牌与桌面直通出件 IPC 接口
    def wash_document(self, file_path: str) -> dict[str, Any]:
        """清洗业务员进料文书 (.doc/.docx)，提取关键要素并识别文书类型。"""
        try:
            return wash_document_file(file_path)
        except Exception as exc:
            return {"status": "error", "message": f"文书清洗解析异常: {exc}"}

    def generate_washed_document(self, doc_type: str, fields: dict[str, Any], overwrite: bool = True) -> dict[str, Any]:
        """将清洗后的要素生成标准新文书并直接输出到桌面根目录。"""
        try:
            return generate_washed_document(doc_type, fields, overwrite)
        except Exception as exc:
            return {"status": "error", "message": f"文书生成落盘异常: {exc}"}

    def get_clipboard_doc_path(self) -> str:
        """从 Windows 系统剪贴板提取复制的文件物理路径。"""
        return get_clipboard_doc_path()

    def browse_doc_file(self) -> str:
        """调用 Windows 原生对话框选取 .doc 或 .docx 文件。"""
        return browse_doc_file_dialog()

    def open_word_file(self, file_path: str) -> bool:
        """直接在 Windows 中调起 Word / WPS 打开指定文档。"""
        return open_file_native(file_path)

    def reveal_in_desktop(self, file_path: str) -> bool:
        """在 Windows 资源管理器中选中高亮桌面生成的文件。"""
        return reveal_in_explorer(file_path)

    def generate_site_proof_standalone(self, state_dict: dict[str, Any]) -> dict[str, Any]:
        """独立一键生成《经营场所使用证明》（前置准备专用功能）。"""
        t0 = time.perf_counter()
        try:
            state = HistoryManager.restore_state(state_dict)
            self.current_state = state
            _, _, customer_dir = self._resolve_customer_workspace(state)
            docs = generate_site_proof_only(state, customer_dir)
            latest_docx = list(docs.values())[0] if docs else ""
            cost_ms = (time.perf_counter() - t0) * 1000
            return {
                "status": "success",
                "cost_ms": round(cost_ms, 2),
                "target_dir": str(customer_dir),
                "customer_folder": customer_dir.name,
                "docs": docs,
                "latest_docx": latest_docx,
            }
        except Exception as exc:
            return {"status": "error", "message": f"场地证明生成失败: {exc}", "cost_ms": 0.0}

    def generate_zhugai_standalone(self, state_dict: dict[str, Any]) -> dict[str, Any]:
        """独立一键生成《住改商证明》（纯 DOCX 出件，不用写生图）。"""
        t0 = time.perf_counter()
        try:
            state = HistoryManager.restore_state(state_dict)
            self.current_state = state
            owner_name, shop_title, customer_dir = self._resolve_customer_workspace(state)
            eff_shop = shop_title or f"郯城县{owner_name}店"
            zhugai_file = customer_dir / f"住改商证明_{owner_name}.docx"
            _generate_zhugai_in_process(state, zhugai_file, eff_shop)
            docs = {"zhu_gai_shang": str(zhugai_file)}
            cost_ms = (time.perf_counter() - t0) * 1000
            return {
                "status": "success",
                "cost_ms": round(cost_ms, 2),
                "target_dir": str(customer_dir),
                "customer_folder": customer_dir.name,
                "docs": docs,
                "latest_docx": str(zhugai_file),
            }
        except Exception as exc:
            return {"status": "error", "message": f"住改商生成失败: {exc}", "cost_ms": 0.0}

    # @AI-ANCHOR: [BRIDGE-GENERATE-ALL] 一键并发生成全套文书、住改商导图与 .Q 脚本
    def generate_all(self, state_dict: dict[str, Any]) -> dict[str, Any]:
        """一键生成登记文书与填报脚本。"""
        t0 = time.perf_counter()
        state = HistoryManager.restore_state(state_dict)
        self.current_state = state
        profile = self.get_profile()

        include_site_proof = bool(state_dict.get("include_site_proof", False))
        export_zhugai_images = bool(state_dict.get("export_zhugai_images", True))

        try:
            owner_name, _, customer_dir = self._resolve_customer_workspace(state)
            folder_name = customer_dir.name

            active_steps = state.get_active_steps()
            if state.run_mode == "single_step" or len(active_steps) == 1:
                step_label = f"单步第{active_steps[0]}步"
            elif active_steps == list(range(active_steps[0], active_steps[-1] + 1)):
                step_label = f"{active_steps[0]}至{active_steps[-1]}步"
            else:
                step_label = f"组合步({'-'.join(str(s) for s in active_steps)})"

            q_filename = f"个体户填报_{owner_name}_{step_label}.Q"
            q_file_path, fixed_slot_q, anjian_slot_path = self._deploy_q_scripts(
                state, profile, customer_dir, q_filename
            )

            docs_generated = generate_documents(
                state,
                customer_dir,
                include_site_proof=include_site_proof,
                export_zhugai_images=export_zhugai_images,
            )

            legacy_desk_manifest = customer_dir / f"{folder_name}.manifest.json"
            if legacy_desk_manifest.exists():
                legacy_desk_manifest.unlink(missing_ok=True)

            _MANIFEST_CACHE_DIR.mkdir(parents=True, exist_ok=True)
            manifest_file = _MANIFEST_CACHE_DIR / f"{folder_name}.manifest.json"
            manifest_data = {
                "version": "demo",
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "owner_name": state.owner_name,
                "owner_id": state.owner_id,
                "phone": state.phone,
                "id_addr": state.id_addr,
                "shop_name": state.shop_name,
                "shop_address": state.shop_address,
                "town": state.town,
                "supervisor": state.supervisor,
                "stage": state.stage,
                "usage": state.usage,
                "step_start": state.step_start,
                "step_end": state.step_end,
                "enabled_steps": active_steps,
                "run_mode": state.run_mode,
                "scopes": [sc.to_dict() for sc in state.scopes],
                "generated_files": {
                    "q_archive": str(q_file_path),
                    "q_fixed_slot": str(fixed_slot_q),
                    "docx_files": docs_generated,
                },
            }
            manifest_file.write_text(json.dumps(manifest_data, ensure_ascii=False, indent=2), encoding="utf-8")

            latest_docx = next((v for v in docs_generated.values() if v.endswith(".docx")), "")
            if not latest_docx and docs_generated:
                latest_docx = list(docs_generated.values())[0]

            HistoryManager.save_snapshot(state, {"target_dir": str(customer_dir), "q_file": str(q_file_path)})

            cost_ms = (time.perf_counter() - t0) * 1000
            return {
                "status": "success",
                "cost_ms": round(cost_ms, 2),
                "target_dir": str(customer_dir),
                "customer_folder": folder_name,
                "q_file": str(q_file_path),
                "fixed_slot_q": str(fixed_slot_q),
                "anjian_direct_path": anjian_slot_path,
                "docs": docs_generated,
                "manifest_file": str(manifest_file),
                "latest_docx": latest_docx,
                "step_label": step_label,
                "active_steps": active_steps,
                "owner_name": state.owner_name,
            }
        except Exception as exc:
            return {"status": "error", "message": f"出件失败: {exc}", "cost_ms": 0.0}

    # @AI-ANCHOR: [BRIDGE-SINGLE-STEP-Q] 单步或积木组合秒级重编 .Q 脚本
    def quick_recompile_step(self, step_idx: int, state_dict: dict[str, Any] | None = None) -> dict[str, Any]:
        """单步填报脚本重新生成：快速重新编译指定步骤到固定待执行脚本与客户目录。"""
        t0 = time.perf_counter()
        try:
            if state_dict:
                self.current_state = HistoryManager.restore_state(state_dict)
            state = ApplicantState.from_dict(self.current_state.to_dict())
            state.step_start = int(step_idx)
            state.step_end = int(step_idx)
            state.enabled_steps = [int(step_idx)]
            state.run_mode = "single_step"
            profile = self.get_profile()

            owner_name, _, customer_dir = self._resolve_customer_workspace(state)
            q_filename = f"个体户填报_{owner_name}_单步第{step_idx}步.Q"
            step_q, fixed_slot_q, anjian_slot_path = self._deploy_q_scripts(
                state, profile, customer_dir, q_filename
            )

            cost_ms = (time.perf_counter() - t0) * 1000
            return {
                "status": "success",
                "step": step_idx,
                "cost_ms": round(cost_ms, 2),
                "target_dir": str(customer_dir),
                "customer_folder": customer_dir.name,
                "q_file": str(step_q),
                "fixed_slot_q": str(fixed_slot_q),
                "anjian_direct_path": anjian_slot_path,
            }
        except Exception as exc:
            return {"status": "error", "step": step_idx, "message": f"重编失败: {exc}", "cost_ms": 0.0}

    def open_customer_folder(self, target_path_str: str = "") -> None:
        """在资源管理器中打开客户主体目录并高亮定位目标文件。"""
        reveal_in_explorer(target_path_str)

    def open_directory(self, dir_path: str) -> None:
        reveal_in_explorer(dir_path)

    def toggle_mini_hud(self, enable: bool) -> dict[str, Any]:
        """全景工作台与悬浮伴随窗模式切换。"""
        return switch_window_hud_mode(self._app_window, enable)

    def set_window_mode(self, mode: str) -> None:
        self.toggle_mini_hud(mode == "hud")

    def exit_app(self) -> None:
        force_exit_process(self._app_window)

    def ready_to_show(self) -> None:
        if self._app_window:
            try:
                self._app_window.show()
            except Exception as exc:
                logger.debug("显示主窗口异常: %s", exc)
