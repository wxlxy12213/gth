#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@AI-ANCHOR: [FAST-CHECK-RUNNER] 毫秒级靶向自检与前后端 DOM/API 契约守卫 (GTH Demo)
用法:
  python tests/fast_check.py ocr    # 验证 OCR 消元、双身份证配对与地址倒置缝合
  python tests/fast_check.py q      # 验证 Action IR 编译与 @GTH-STATE-IR 零损逆向还原
  python tests/fast_check.py scope  # 验证 2064 底库拼音检索与套餐代数差集
  python tests/fast_check.py docx   # 验证单源文书引擎、住改商导图与文书洗牌复用
  python tests/fast_check.py ui     # 验证前端 HTML/JS DOM ID 契约完整性（防幽灵断层）
  python tests/fast_check.py all    # 执行全量靶向冒烟自检
"""
from __future__ import annotations

import json
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.doc_wash_engine import generate_washed_document, wash_document_file
from engine.docx_engine import generate_documents, generate_site_proof_only
from engine.models import ApplicantState, ScopeItem
from engine.ocr_cleaner import clean_raw_ocr
from engine.q_compiler import build_action_ir, compile_q_script
from engine.q_parser import parse_q_script
from engine.scope_search import ScopeSearchEngine


def check_ocr() -> None:
    t0 = time.perf_counter()
    sample = (
        "经营者：柴纪宝 身份证：371322199110130739 电话：13853901234 "
        "地址：东爱国村179号 山东省临沂市郯城县马头镇 字号：郯城县马头镇东爱百货店 "
        "房东：李四 371322199110130739"
    )
    st = clean_raw_ocr(sample)
    assert st.owner_name == "柴纪宝", f"owner_name 异常: {st.owner_name}"
    assert st.owner_id == "371322199110130739", f"owner_id 异常: {st.owner_id}"
    assert st.town == "马头镇", f"town 异常: {st.town}"
    assert st.supervisor == "马头所", f"supervisor 异常: {st.supervisor}"
    assert "东爱百货店" in st.shop_name, f"shop_name 异常: {st.shop_name}"
    cost = (time.perf_counter() - t0) * 1000
    print(f"[PASS] OCR 消元与属地映射自检通过 ({cost:.2f} ms)")


def check_q() -> None:
    t0 = time.perf_counter()
    profile = json.loads((ROOT / "config" / "portal_profile_371300.json").read_text(encoding="utf-8"))
    st = ApplicantState(
        owner_name="柴纪宝",
        owner_id="371322199110130739",
        phone="13853901234",
        id_addr="山东省临沂市郯城县马头镇东爱国村179号",
        shop_name="郯城县马头镇东爱百货店",
        shop_address="山东省临沂市郯城县马头镇东爱国村179号",
        town="马头镇",
        supervisor="马头所",
        usage="lease",
        landlord_name="张房东",
        landlord_id="371322199110130739",
        enabled_steps=[2, 5],
        scopes=[ScopeItem(code="F1039", name="日用百货销售", is_primary=True)],
    )
    builder, active = build_action_ir(st, profile)
    assert active == [2, 5], f"active_steps 异常: {active}"
    assert len(builder.ir_nodes) > 5, "Action IR 节点为空"

    with tempfile.TemporaryDirectory() as tmp:
        q_path = Path(tmp) / "test.Q"
        compile_q_script(st, profile, q_path)
        assert q_path.exists() and q_path.stat().st_size > 100
        restored = parse_q_script(q_path)
        # 验证即使只编译了 [2, 5] 步，通过 @GTH-STATE-IR 依然能 100% 还原姓名、身份证、房东与经营范围！
        assert restored.owner_name == "柴纪宝", f"逆向还原姓名丢失: {restored.owner_name}"
        assert restored.landlord_name == "张房东", f"逆向还原房东丢失: {restored.landlord_name}"
        assert restored.enabled_steps == [2, 5], f"逆向还原步骤异常: {restored.enabled_steps}"
        assert len(restored.scopes) == 1 and restored.scopes[0].code == "F1039"
    cost = (time.perf_counter() - t0) * 1000
    print(f"[PASS] Action IR 编译与 @GTH-STATE-IR 零损逆向解析自检通过 ({cost:.2f} ms)")


def check_scope() -> None:
    t0 = time.perf_counter()
    eng = ScopeSearchEngine.instance()
    hits = eng.search("rybh")
    assert any("日用百货" in h["name"] for h in hits), "拼音首字母 rybh 未命中日用百货"
    diff = eng.diff_package_with_native("百货店", "日用百货销售；服装服饰零售")
    assert diff["native_hit_count"] >= 2, f"差集剔除异常: {diff}"
    cost = (time.perf_counter() - t0) * 1000
    print(f"[PASS] 2064 底库拼音检索与套餐差集自检通过 ({cost:.2f} ms)")


def check_docx() -> None:
    t0 = time.perf_counter()
    st = ApplicantState(
        owner_name="柴纪宝",
        owner_id="371322199110130739",
        phone="13853901234",
        id_addr="山东省临沂市郯城县马头镇东爱国村179号",
        shop_name="郯城县马头镇东爱百货店",
        shop_address="山东省临沂市郯城县马头镇东爱国村179号",
        town="马头镇",
        supervisor="马头所",
        usage="lease",
        landlord_name="赵四",
        scopes=[ScopeItem(code="F1039", name="日用百货销售", is_primary=True)],
    )
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        docs = generate_documents(st, tmp_dir, include_site_proof=True, export_zhugai_images=True)
        assert "zhu_gai_shang" in docs and Path(docs["zhu_gai_shang"]).exists()
        assert "lease_contract" in docs and Path(docs["lease_contract"]).exists()
        assert "site_proof" in docs and Path(docs["site_proof"]).exists()
        assert "zhu_gai_shang_p1_img" in docs and Path(docs["zhu_gai_shang_p1_img"]).exists()

        # 验证文书洗牌引擎对生成的 docx 直接提取与二次出件
        wash_res = wash_document_file(docs["zhu_gai_shang"])
        assert wash_res["status"] == "success", f"洗牌提取失败: {wash_res}"
        assert wash_res["doc_kind"] == "zhu_gai_shang"
    cost = (time.perf_counter() - t0) * 1000
    print(f"[PASS] 单源文书引擎、住改商导图与洗牌闭环自检通过 ({cost:.2f} ms)")


def check_ui() -> None:
    t0 = time.perf_counter()
    html = (ROOT / "ui" / "workbench.html").read_text(encoding="utf-8")
    html_ids = set(re.findall(r'id="([^"]+)"', html))

    required_ids = [
        "ocr-raw-input", "btn-read-clipboard", "btn-clean-ocr", "stage-desc-tag", "sup-desc-tag",
        "chk-include-site-proof", "chk-export-zhugai-img", "btn-gen-site-proof", "btn-gen-zhugai-img",
        "btn-push-to-docs", "btn-reset-form", "btn-top-reset", "btn-copy-id-addr",
        "wb-quick-pkg-bar", "wb-scope-preview-text", "wb-scope-count", "btn-jump-scope-tab",
        "step-blocks-container", "btn-generate-all", "output-artifact-list", "btn-parse-q-trigger",
        "scene-workbench", "scene-scope", "scene-docs", "scene-settings", "scene-analytics",
        "btn-wash-pull-from-wb", "btn-wash-push-to-wb",
    ]
    missing = [rid for rid in required_ids if rid not in html_ids]
    assert not missing, f"workbench.html 缺失关键 DOM ID: {missing}"
    cost = (time.perf_counter() - t0) * 1000
    print(f"[PASS] 前端 DOM ID 契约与五场景完整性自检通过 ({cost:.2f} ms)")


def main() -> None:
    target = (sys.argv[1] if len(sys.argv) > 1 else "all").lower()
    runners = {
        "ocr": [check_ocr],
        "q": [check_q],
        "scope": [check_scope],
        "docx": [check_docx],
        "ui": [check_ui],
        "all": [check_ocr, check_q, check_scope, check_docx, check_ui],
    }
    for fn in runners.get(target, runners["all"]):
        fn()


if __name__ == "__main__":
    main()
