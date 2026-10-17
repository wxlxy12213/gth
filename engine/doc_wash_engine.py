"""
@AI-ANCHOR: [DOC-WASH-ENGINE-CORE] 业务员文书智能洗牌与桌面直通出件引擎 (<350行微切片)
doc_wash_engine.py - 针对业务员随手制作的 .doc/.docx 进料，智能清洗要素并生成标准新文书 (GTH V3.0 单源复用版)。

架构升级重点：
1. 彻底解决「文件生成引擎双轨分裂」与「外部环境脆弱性」：
   - 提取层：优先调用外部 `doc_case_extract`，若当前环境无外部技能，自动回退至内置的 OpenXML 段落+表格全文读取器并复用 `engine.ocr_cleaner.clean_raw_ocr` 消元引擎。
   - 生成层：优先查找内聚目录 `engine/doc_writers/` 与外部技能目录；若外部脚本不存在或执行失败，100% 复用 `engine.docx_engine` 的进程内单源渲染器（`_generate_zhugai_in_process`, `_generate_lease_contract_in_process`, `_generate_site_proof_in_process`, `generate_canyin_commitment_in_process`）。
2. 保持桌面直通契约：产物一律直接落盘至桌面根目录 (`Desktop`)，住改商纯 DOCX 出件绝不产生 PNG 图片。
"""
from __future__ import annotations

import logging
import re
import subprocess
import sys
import time
import urllib.parse
import xml.etree.ElementTree as ET
import zipfile
from datetime import date
from pathlib import Path
from typing import Any, Dict, Optional

from .docx_engine import (
    _generate_lease_contract_in_process,
    _generate_site_proof_in_process,
    _generate_zhugai_in_process,
    generate_canyin_commitment_in_process,
)
from .models import ApplicantState, ScopeItem
from .ocr_cleaner import clean_raw_ocr

logger = logging.getLogger("gth.doc_wash")

_ROOT = Path(__file__).resolve().parent.parent
_INTERNAL_WRITERS = _ROOT / "engine" / "doc_writers"
_SKILLS_ROOT = Path.home() / ".gemini" / "config" / "skills"
_ZULIN_SCRIPTS = _SKILLS_ROOT / "zulin-hetong" / "scripts"
_ZHUGAI_SCRIPTS = _SKILLS_ROOT / "zhu-gai-shang" / "scripts"
_SHIPIN_SCRIPTS = _SKILLS_ROOT / "shipin-xuke" / "scripts"
_CHANGDI_SCRIPTS = _SKILLS_ROOT / "changdi-zhengming" / "scripts"
_WENDANG_SCRIPTS = _SKILLS_ROOT / "wendang" / "scripts"

for _p in (_INTERNAL_WRITERS, _ZULIN_SCRIPTS, _ZHUGAI_SCRIPTS, _SHIPIN_SCRIPTS, _CHANGDI_SCRIPTS, _WENDANG_SCRIPTS):
    if _p.exists() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

_DESKTOP_DIR = Path.home() / "Desktop"

RE_ZHU_KEYWORDS = re.compile(r"住改商|利害关系业主|四邻|住宅改变为经营性用房")
RE_LEASE_KEYWORDS = re.compile(r"房屋租赁合同|租赁合同|出租方|承租方")
RE_CANYIN_KEYWORDS = re.compile(r"餐饮服务承诺书|餐饮承诺书|小餐饮|食品经营承诺书")
RE_SITE_KEYWORDS = re.compile(r"经营场所使用证明|场所使用证明|场地证明|房屋使用证明|经营场所证明")


def _strip_smart_quotes(s: str) -> str:
    """消除中英文成对包裹的外层引号、URI scheme 与两端空白。"""
    s = (s or "").strip()
    if s.lower().startswith("file:///"):
        s = s[8:]
        s = urllib.parse.unquote(s)
        if len(s) >= 3 and s[0] == "/" and s[2] == ":":
            s = s[1:]
    if s.startswith('\\"') and s.endswith('\\"'):
        s = s[2:-2].strip()
    elif s.startswith("\\'") and s.endswith("\\'"):
        s = s[2:-2].strip()
    pairs = [('"', '"'), ("'", "'"), ("“", "”"), ("‘", "’"), ("“", '"'), ('"', "”")]
    changed = True
    while changed:
        changed = False
        s = s.strip()
        for left, right in pairs:
            if s.startswith(left) and s.endswith(right) and len(s) >= 2:
                s = s[len(left) : -len(right)].strip()
                changed = True
                break
    return s.strip()


def resolve_incoming_file_path(raw_path: str | Path) -> Optional[Path]:
    """多级智能穿透自愈：当用户拖拽仅提供文件名或路径不存在时，穿透查找真实物理文件。"""
    if not raw_path:
        return None
    clean_str = _strip_smart_quotes(str(raw_path))
    if not clean_str:
        return None
    p = Path(clean_str)

    try:
        if p.is_file():
            return p.resolve()
        resolved = p.resolve()
        if resolved.is_file():
            return resolved
    except Exception:
        pass

    raw_name = p.name
    if not raw_name:
        return None

    raw_unquoted = urllib.parse.unquote(raw_name)
    alt_name = raw_name.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
    alt_cn_name = raw_name.replace('"', "“").replace('"', "”").replace("'", "‘").replace("'", "’")
    target_names = {nm for nm in (raw_name, raw_unquoted, alt_name, alt_cn_name) if nm}

    candidates: list[Path] = []
    user_home = Path.home()

    search_roots = [
        _DESKTOP_DIR,
        user_home / "OneDrive" / "桌面",
        user_home / "OneDrive" / "Desktop",
        user_home / "Downloads",
        Path.cwd(),
        _ROOT,
        _ROOT / ".cache" / "_warmup",
    ]

    for root in search_roots:
        if not root.is_dir():
            continue
        for name in target_names:
            target = root / name
            if target.is_file():
                candidates.append(target)
        try:
            for sub in root.iterdir():
                if sub.is_dir() and not sub.name.startswith((".", "$")):
                    for name in target_names:
                        target = sub / name
                        if target.is_file():
                            candidates.append(target)
        except Exception:
            pass

    wx_dirs = [
        user_home / "Documents" / "xwechat_files",
        user_home / "Documents" / "WeChat Files",
        user_home / "OneDrive" / "Documents" / "xwechat_files",
        user_home / "OneDrive" / "Documents" / "WeChat Files",
    ]
    for wx_base in wx_dirs:
        if not wx_base.is_dir():
            continue
        try:
            for wx_user in wx_base.iterdir():
                if not wx_user.is_dir():
                    continue
                for sub_rel in ("msg/file", "FileStorage/File", "cache", "File"):
                    folder = wx_user / Path(sub_rel)
                    if not folder.is_dir():
                        continue
                    try:
                        for month_dir in folder.iterdir():
                            if month_dir.is_dir():
                                for name in target_names:
                                    cand = month_dir / name
                                    if cand.is_file():
                                        candidates.append(cand)
                            elif month_dir.is_file() and month_dir.name in target_names:
                                candidates.append(month_dir)
                    except Exception:
                        pass
        except Exception:
            pass

    if candidates:
        unique_cands = list({str(c.resolve()): c.resolve() for c in candidates}.values())
        unique_cands.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        return unique_cands[0]

    return None


def _builtin_extract_docx_text(docx_path: Path) -> str:
    """内置零依赖 .docx 全文（段落+表格）提取器，消除对外部 wendang 脚本的强依赖。"""
    with zipfile.ZipFile(docx_path, "r") as zf:
        xml_bytes = zf.read("word/document.xml")
    root = ET.fromstring(xml_bytes)
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    lines: list[str] = []
    body = root.find("w:body", ns)
    if body is None:
        return ""
    for elem in body:
        tag = elem.tag.split("}")[-1]
        if tag == "p":
            txt = "".join(t.text for t in elem.findall(".//w:t", ns) if t.text).strip()
            if txt:
                lines.append(txt)
        elif tag == "tbl":
            for row in elem.findall(".//w:tr", ns):
                cells = [
                    "".join(t.text for t in tc.findall(".//w:t", ns) if t.text).strip()
                    for tc in row.findall(".//w:tc", ns)
                ]
                cells = [c for c in cells if c]
                if cells:
                    lines.append("  ".join(cells))
    return "\n".join(lines)


def _builtin_extract_fields_from_doc_text(text: str) -> dict[str, Any]:
    """内置单源文书要素提取器：结合公文标签正则与 `clean_raw_ocr` 通用消元流水线。"""
    st = clean_raw_ocr(text)

    # 针对标准公文标签做精确覆盖提纯
    m_subj = re.search(r"(?:市场主体名称|商号名称|字号名称|承租方（乙方）|承租方)[：:\s]*([^\r\n（(，,；;]+)", text)
    subject = m_subj.group(1).strip() if m_subj else st.shop_name

    m_op = re.search(
        r"(?:村民|居民|经营者姓名|经营者|申请人签字（盖章）|法定代表人)[：:\s]*([\u4e00-\u9fa5]{2,10})",
        text,
    )
    operator = m_op.group(1).strip() if m_op else st.owner_name

    m_addr = re.search(r"(?:详细地址|位于|房屋坐落|经营场所地址|租赁房屋坐落)[：:\s]*([^\r\n。；;]+)", text)
    address = m_addr.group(1).strip() if m_addr else (st.shop_address or st.id_addr)

    m_scope = re.search(r"(?:主要经营范围|经营范围)[：:\s]*([^\r\n。；;]+)", text)
    scope = m_scope.group(1).strip() if m_scope else (st.raw_scope_text or "日用百货销售")

    m_rent = re.search(r"(\d{3,7})\s*元\s*/?\s*年", text)
    rent_amount = int(m_rent.group(1)) if m_rent else 10000

    return {
        "subject": subject or "",
        "operator": operator or "",
        "operator_id": st.owner_id or "",
        "address": address or "",
        "scope": scope or "日用百货销售",
        "landlord": st.landlord_name or "",
        "landlord_id": st.landlord_id or "",
        "rent_amount": rent_amount,
        "ownership": "租赁" if st.usage == "lease" else "自有",
    }


# @AI-ANCHOR: [DOC-WASH-PARSE] 文书要素解析与清洗器（支持外部技能与内置引擎无缝切换）
def wash_document_file(file_path: str | Path) -> Dict[str, Any]:
    """读取并清洗业务员文书，提取关键业务要素并推导文书类型。"""
    clean_p = resolve_incoming_file_path(file_path)
    if not clean_p or not clean_p.is_file():
        return {
            "status": "error",
            "message": f"未找到进料文件: {file_path}（已穿透检索桌面、下载与微信目录，请核对文件名或点击浏览选择）",
            "file_path": str(file_path),
        }

    suffix = clean_p.suffix.lower()
    if suffix not in (".doc", ".docx"):
        return {
            "status": "error",
            "message": f"仅支持 .doc 或 .docx 格式，收到: {suffix}",
            "file_path": str(clean_p),
        }

    text = ""
    f: dict[str, Any] = {}
    tmp_docx: Optional[Path] = None

    try:
        from doc_case_extract import convert_doc_to_docx, extract_fields, extract_full_text
        if suffix == ".doc":
            tmp_docx = convert_doc_to_docx(clean_p)
            text = extract_full_text(tmp_docx)
        else:
            text = extract_full_text(clean_p)
        if text.strip():
            ext = extract_fields(text)
            f = ext.get("fields", {})
    except Exception as exc:
        logger.debug("外部 doc_case_extract 不可用，启用内置单源解析器: %s", exc)
        if suffix == ".docx":
            try:
                text = _builtin_extract_docx_text(clean_p)
                if text.strip():
                    f = _builtin_extract_fields_from_doc_text(text)
            except Exception as inner_exc:
                return {
                    "status": "error",
                    "message": f"读取文书全文失败: {inner_exc}",
                    "file_path": str(clean_p),
                }
        else:
            return {
                "status": "error",
                "message": f"当前环境处理旧版二进制 .doc 需要本机 Word COM 组件，请另存为 .docx 后重试 ({exc})",
                "file_path": str(clean_p),
            }
    finally:
        if tmp_docx and tmp_docx.exists():
            tmp_docx.unlink(missing_ok=True)

    if not text.strip():
        return {
            "status": "error",
            "message": "文书内容为空，无法提取业务要素",
            "file_path": str(clean_p),
        }

    if not f:
        f = _builtin_extract_fields_from_doc_text(text)

    filename = clean_p.name
    doc_kind = "zhu_gai_shang"
    if RE_CANYIN_KEYWORDS.search(filename) or RE_CANYIN_KEYWORDS.search(text[:300]):
        doc_kind = "canyin_chengnuoshu"
    elif RE_ZHU_KEYWORDS.search(filename) or RE_ZHU_KEYWORDS.search(text[:300]):
        doc_kind = "zhu_gai_shang"
    elif RE_LEASE_KEYWORDS.search(filename) or RE_LEASE_KEYWORDS.search(text[:300]):
        doc_kind = "lease_contract"
    elif RE_SITE_KEYWORDS.search(filename) or RE_SITE_KEYWORDS.search(text[:300]):
        doc_kind = "site_proof"

    today_str = date.today().strftime("%Y-%m-%d")

    return {
        "status": "success",
        "file_path": str(clean_p),
        "file_name": clean_p.name,
        "doc_kind": doc_kind,
        "fields": {
            "subject": f.get("subject") or "",
            "operator": f.get("operator") or "",
            "operator_id": f.get("operator_id") or "",
            "address": f.get("address") or "",
            "scope": f.get("scope") or "",
            "landlord": f.get("landlord") or "",
            "landlord_id": f.get("landlord_id") or "",
            "rent_amount": f.get("rent_amount") or 10000,
            "sign_date": today_str,
            "ownership": f.get("ownership") or "自有",
        },
        "raw_preview": text[:350].replace("\r", " ").replace("\n", " "),
    }


def _find_skill_script(script_name: str, external_dir: Path) -> Optional[Path]:
    """优先查找项目内聚 `engine/doc_writers/`，次选外部技能目录。"""
    internal_cand = _INTERNAL_WRITERS / script_name
    if internal_cand.is_file():
        return internal_cand
    external_cand = external_dir / script_name
    if external_cand.is_file():
        return external_cand
    return None


# @AI-ANCHOR: [DOC-WASH-GENERATE] 标准文书生成与桌面直通落盘（复用 docx_engine 单源内核）
def generate_washed_document(doc_type: str, fields: Dict[str, Any], overwrite: bool = True) -> Dict[str, Any]:
    """根据清洗后的要素与规范，生成标准 DOCX 并直接落地桌面根目录（优先外部脚本，自动无缝回退 docx_engine 进程内内核）。"""
    t0 = time.perf_counter()
    desktop = _DESKTOP_DIR
    try:
        desktop.mkdir(parents=True, exist_ok=True)
    except Exception:
        desktop = _ROOT / ".cache" / "Desktop"
        desktop.mkdir(parents=True, exist_ok=True)

    subject = (fields.get("subject") or "").strip()
    operator = (fields.get("operator") or "").strip() or "经营者"
    address = (fields.get("address") or "").strip() or "山东省临沂市郯城县"
    scope = (fields.get("scope") or "").strip() or "日用百货销售"
    landlord = (fields.get("landlord") or "").strip()
    landlord_id = (fields.get("landlord_id") or "").strip()
    operator_id = (fields.get("operator_id") or "").strip()
    rent_amount = int(fields.get("rent_amount") or 10000)

    today = date.today()
    today_cn = f"{today.year}年{today.month}月{today.day}日"

    # 构造共享 ApplicantState 供 docx_engine 单源渲染器直接复用
    shared_state = ApplicantState(
        owner_name=operator,
        owner_id=operator_id,
        shop_name=subject,
        shop_address=address,
        id_addr=address,
        usage="lease" if landlord else "own",
        landlord_name=landlord,
        landlord_id=landlord_id,
        scopes=[ScopeItem(code="WASH", name=scope, is_primary=True)],
    )

    out_file: Optional[Path] = None

    if doc_type == "zhu_gai_shang":
        is_apartment = bool(re.search(r"(?:[0-9]{3,4}室|[0-9]+号楼|[0-9]+单元|小区|花园|公寓)", address))
        route_tag = "小区楼房" if is_apartment else "民房"
        stem = f"住改商（{route_tag}）-{subject}-{operator}" if subject else f"住改商（{route_tag}）-{operator}"
        out_file = desktop / f"{stem}.docx"

        script = _find_skill_script("fill_zhu_gai_shang.py", _ZHUGAI_SCRIPTS)
        if script:
            cmd = [
                sys.executable, "-B", str(script),
                "--name", subject or f"郯城县{operator}店",
                "--owner", operator,
                "--address", address,
                "--scope", scope,
                "--output", str(out_file),
                "--no-images",
            ]
            if overwrite:
                cmd.append("--overwrite")
            proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=60)
            if proc.returncode != 0 and not out_file.exists():
                logger.info("外部 fill_zhu_gai_shang 执行未产出文件，切换 docx_engine 单源内核渲染")
                _generate_zhugai_in_process(shared_state, out_file, subject or f"郯城县{operator}店")
        else:
            _generate_zhugai_in_process(shared_state, out_file, subject or f"郯城县{operator}店")

    elif doc_type == "lease_contract":
        stem = f"租赁合同-{operator}"
        out_file = desktop / f"{stem}.docx"

        script = _find_skill_script("fill_lease_contract.py", _ZULIN_SCRIPTS)
        if script:
            cmd = [
                sys.executable, "-B", str(script),
                "--tenant", subject or f"郯城县{operator}店",
                "--tenant-rep", operator,
                "--tenant-id", operator_id,
                "--landlord", landlord or "房东",
                "--address", address,
                "--rent-amount", str(rent_amount),
                "--output", str(out_file),
            ]
            if landlord_id:
                cmd.extend(["--landlord-id", landlord_id])
            if overwrite:
                cmd.append("--overwrite")
            proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=60)
            if proc.returncode != 0 and not out_file.exists():
                _generate_lease_contract_in_process(shared_state, out_file, subject or f"郯城县{operator}店", rent_amount=rent_amount)
        else:
            _generate_lease_contract_in_process(shared_state, out_file, subject or f"郯城县{operator}店", rent_amount=rent_amount)

    elif doc_type == "canyin_chengnuoshu":
        if subject:
            stem = f"餐饮承诺书-{subject}"
        elif operator and operator != "经营者":
            stem = f"餐饮承诺书-{operator}"
        else:
            stem = "餐饮承诺书"
        out_file = desktop / f"{stem}.docx"
        generate_canyin_commitment_in_process(
            out_file=out_file,
            subject=subject,
            operator=operator,
            address=address,
            date_cn=today_cn,
        )

    elif doc_type == "site_proof":
        stem = f"场地证明-{subject}-{operator}" if subject else f"场地证明-{operator}"
        out_file = desktop / f"{stem}.docx"

        script = _find_skill_script("fill_site_proof.py", _CHANGDI_SCRIPTS)
        if script:
            cmd = [
                sys.executable, "-B", str(script),
                "--operator", operator,
                "--operator-id", operator_id,
                "--address", address,
                "--output", str(out_file),
            ]
            if subject:
                cmd.extend(["--name", subject])
            if landlord:
                cmd.extend(["--landlord", landlord])
                if landlord_id:
                    cmd.extend(["--landlord-id", landlord_id])
            if overwrite:
                cmd.append("--overwrite")
            proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=60)
            if proc.returncode != 0 and not out_file.exists():
                _generate_site_proof_in_process(shared_state, out_file, not bool(landlord), landlord, landlord_id)
        else:
            _generate_site_proof_in_process(shared_state, out_file, not bool(landlord), landlord, landlord_id)

    else:
        return {"status": "error", "message": f"不支持的文书类型: {doc_type}"}

    cost_ms = (time.perf_counter() - t0) * 1000

    if out_file and out_file.exists():
        return {
            "status": "success",
            "doc_type": doc_type,
            "filename": out_file.name,
            "output_path": str(out_file),
            "file_size": out_file.stat().st_size,
            "cost_ms": round(cost_ms, 2),
            "date": today_cn,
        }
    return {
        "status": "error",
        "message": "文书生成流程已结束，但未能在桌面检测到产物落地",
        "cost_ms": round(cost_ms, 2),
    }
