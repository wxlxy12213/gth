"""
@AI-ANCHOR: [Q-SCRIPT-PARSER] 按键精灵 .Q 脚本逆向解析还原器 (<130行微切片)
职责：无需依赖伴生 manifest.json，优先从 .Q 脚本内嵌的 `@GTH-STATE-IR` 结构化元数据 O(1) 零损还原 ApplicantState；
若为历史旧版 .Q 脚本，则自动回退至注释与指令流正则提取，保证 100% 向后兼容。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .models import ApplicantState, ScopeItem
from .ocr_rules_loader import SUPERVISOR_MAP


# @AI-ANCHOR: [Q-PARSE-MAIN] 逆向解析 .Q 脚本还原姓名/身份证/字号/步骤积木/经营范围
def parse_q_script(q_source: str | Path) -> ApplicantState:
    """直接逆向解析 .Q 脚本文件或文本内容（优先解析 @GTH-STATE-IR，旧版脚本自动回退正则解析）。"""
    if isinstance(q_source, Path) or (isinstance(q_source, str) and "\n" not in q_source and Path(q_source).exists()):
        p = Path(q_source)
        raw_bytes = p.read_bytes()
        try:
            text = raw_bytes.decode("gbk")
        except Exception:
            text = raw_bytes.decode("utf-8", errors="replace")
    else:
        text = str(q_source)

    # 1. 优先尝试解析 V3.0 结构化内嵌元数据 @GTH-STATE-IR（零损耗还原，不受单步裁剪或注释微调影响）
    m_ir = re.search(r"//\s*@GTH-STATE-IR:\s*(\{[^\r\n]+\})", text)
    if m_ir:
        try:
            ir_data = json.loads(m_ir.group(1).strip())
            if isinstance(ir_data, dict):
                st = ApplicantState.from_dict(ir_data)
                if st.enabled_steps:
                    st.step_start = st.enabled_steps[0]
                    st.step_end = st.enabled_steps[-1]
                    st.run_mode = "single_step" if len(st.enabled_steps) == 1 else "to_end"
                if not st.supervisor and st.town in SUPERVISOR_MAP:
                    st.supervisor = SUPERVISOR_MAP[st.town]
                return st
        except Exception:
            pass

    # 2. 兼容旧版 .Q 脚本：从头部标签与中文步骤注释逆向提取
    st = ApplicantState()

    m_shop = re.search(r"Shop=([^|\r\n]*)", text)
    if m_shop:
        st.shop_name = m_shop.group(1).strip()

    m_steps = re.search(r"Steps=([0-9,]+)", text)
    if m_steps:
        st.enabled_steps = [int(x) for x in m_steps.group(1).split(",") if x.isdigit()]
    else:
        found_stages = [int(m.group(1)) for m in re.finditer(r"// ===== 第 ([1-5]) 阶段：", text)]
        if found_stages:
            st.enabled_steps = sorted(set(found_stages))

    if st.enabled_steps:
        st.step_start = st.enabled_steps[0]
        st.step_end = st.enabled_steps[-1]
        st.run_mode = "single_step" if len(st.enabled_steps) == 1 else "to_end"

    m_name = re.search(r"(?:经营者姓名|名称（姓名）)：点击(?:输入框)?并输入「([^」]+)」", text)
    if m_name:
        st.owner_name = m_name.group(1).strip()

    m_id = re.search(r"(?:身份证号码|证件号码)：点击(?:输入框)?并输入「([^」]+)」", text)
    if m_id:
        st.owner_id = m_id.group(1).strip()

    m_phone = re.search(r"(?:经营者联系电话|联系电话)：点击.*输入(?:客户电话)?「([^」]+)」", text)
    if m_phone:
        st.phone = m_phone.group(1).strip()

    m_email = re.search(r"(?:电子邮箱|法律文书送达邮箱)：点击并输入「([^」]+)」", text)
    if m_email:
        st.email = m_email.group(1).strip()

    m_id_addr = re.search(r"住所（身份证地址）：点击并输入「([^」]+)」", text)
    if m_id_addr:
        st.id_addr = m_id_addr.group(1).strip()

    m_town = re.search(r"乡镇下拉：.*选择(?:底页)?「([^」]+)」", text)
    if m_town:
        st.town = m_town.group(1).strip()

    m_street = re.search(r"街路门牌输入框：输入详细地址「([^」]+)」", text)
    if m_street:
        st.street_rest = m_street.group(1).strip()

    m_map = re.search(r"地图搜索框：输入地址关键词「([^」]+)」", text)
    if m_map:
        st.shop_address = m_map.group(1).strip()
    elif st.id_addr:
        st.shop_address = st.id_addr

    m_usage = re.search(r"使用方式：点击单选「([^」]+)」", text)
    if m_usage:
        u_txt = m_usage.group(1).strip()
        st.usage = "lease" if u_txt == "租赁" else ("free" if u_txt == "无偿使用" else "own")

    if st.usage == "lease":
        m_ll = re.search(r"所有权人姓名：点击并输入「([^」]+)」", text)
        if m_ll:
            st.landlord_name = m_ll.group(1).strip()
        m_ll_id = re.search(r"产权人证件号码：点击并输入「([^」]+)」", text)
        if m_ll_id:
            st.landlord_id = m_ll_id.group(1).strip()

    m_sup = re.search(r"属地监管所：点击选择「([^」]+)」", text)
    if m_sup:
        st.supervisor = m_sup.group(1).strip()
    elif st.town in SUPERVISOR_MAP:
        st.supervisor = SUPERVISOR_MAP[st.town]

    scope_matches = re.finditer(r"搜索输入代码「([^」]+)」(?:【([^】]+)】)?", text)
    scopes: list[ScopeItem] = []
    for idx, sm in enumerate(scope_matches):
        scopes.append(ScopeItem(
            code=sm.group(1).strip(),
            name=(sm.group(2) or sm.group(1)).strip(),
            is_primary=(idx == 0),
        ))
    st.scopes = scopes
    return st
