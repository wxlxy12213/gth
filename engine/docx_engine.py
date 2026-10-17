"""
@AI-ANCHOR: [DOCX-ENGINE-CORE] 工商登记配套文书统一单源渲染引擎 (<370行微切片)
docx_engine.py - 工商登记配套文书与住改商前两页自动导图单源内核 (双轨合一版)。

核心升级：
1. 彻底消除 `docx_engine.py` 与 `doc_wash_engine.py` 的双轨分裂：本模块提供统一的进程内文书生成内核（场地证明、租赁合同、住改商证明、餐饮承诺书），同时供「场景01 填报总控」与「场景03 文书工坊」调用。
2. 消除环境脆弱性：优先调用 `engine/doc_writers` 或外部技能脚本；若运行环境无外部脚本，内置的纯内存 OpenXML 渲染器直接输出含完整法定五段式条款与 `<w:tbl>` 四邻/业主签字表的标准公文，绝不退化为简陋草稿。
3. 移除原版硬编码的 `"王五"` 房东假名兜底，未填房东时使用规范下划线留白。
"""
from __future__ import annotations

import contextlib
import io
import logging
import os
import re
import shutil
import sys
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from .models import ApplicantState

try:
    from .zhugai_img_exporter import export_zhugai_first_two_pages
except ModuleNotFoundError:
    import importlib.util as _ilu
    _spec = _ilu.spec_from_file_location("engine.zhugai_img_exporter", Path(__file__).resolve().parent / "zhugai_img_exporter.py")
    _mod = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    export_zhugai_first_two_pages = _mod.export_zhugai_first_two_pages

logger = logging.getLogger("gth.docx_engine")

_ROOT_DIR = Path(__file__).resolve().parent.parent
_INTERNAL_WRITERS = _ROOT_DIR / "engine" / "doc_writers"
_INTERNAL_TEMPLATES = _ROOT_DIR / "assets" / "templates"

_SKILLS_ROOT = Path.home() / ".gemini" / "config" / "skills"
_WENDANG_PATH = _SKILLS_ROOT / "wendang" / "scripts"
_CHANGDI_PATH = _SKILLS_ROOT / "changdi-zhengming" / "scripts"
_ZULIN_PATH = _SKILLS_ROOT / "zulin-hetong" / "scripts"
_ZHUGAI_PATH = _SKILLS_ROOT / "zhu-gai-shang" / "scripts"
_SHIPIN_PATH = _SKILLS_ROOT / "shipin-xuke" / "scripts"

_DESKTOP_DIR = Path.home() / "Desktop"
_TEMPLATES_DIR = (
    _INTERNAL_TEMPLATES
    if (_INTERNAL_TEMPLATES / "住改商（民房）.docx").exists()
    else (_DESKTOP_DIR / "工商材料")
)
_TPL_ZHUGAI_RURAL = _TEMPLATES_DIR / "住改商（民房）.docx"
_TPL_ZHUGAI_APT = _TEMPLATES_DIR / "住改商（小区楼房）.docx"

_skills_loaded = False
_has_external_skills = False
_DOCX_EXECUTOR = ThreadPoolExecutor(max_workers=4)
list(_DOCX_EXECUTOR.map(lambda _: None, range(4)))


# @AI-ANCHOR: [DOCX-SKILL-LOADER] 外部/内置 OpenXML 文书脚本挂载器
def _ensure_external_skills() -> bool:
    """一次性检测并挂载本机内聚或外部文书技能脚本。"""
    global _skills_loaded, _has_external_skills
    if _skills_loaded:
        return _has_external_skills
    _skills_loaded = True
    search_paths = (_INTERNAL_WRITERS, _WENDANG_PATH, _CHANGDI_PATH, _ZULIN_PATH, _ZHUGAI_PATH, _SHIPIN_PATH)
    if not any(p.exists() for p in search_paths):
        _has_external_skills = False
        return False
    for p in search_paths:
        if p.exists() and str(p) not in sys.path:
            sys.path.insert(0, str(p))
    try:
        import fill_lease_contract  # noqa: F401
        import fill_site_proof  # noqa: F401
        import fill_zhu_gai_shang  # noqa: F401
        from safe_docx_write import load_docx, save_docx  # noqa: F401
        _has_external_skills = True
    except Exception as exc:
        logger.debug("外部文书技能未全量就绪，启用内置标准 OpenXML 引擎: %s", exc)
        _has_external_skills = False
    return _has_external_skills


_ensure_external_skills()

_CONTENT_TYPES_XML = (
    b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    b'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    b'<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    b'<Default Extension="xml" ContentType="application/xml"/>'
    b'<Override PartName="/word/document.xml" '
    b'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
    b"</Types>"
)
_RELS_XML = (
    b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    b'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    b'<Relationship Id="rId1" '
    b'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
    b'Target="word/document.xml"/>'
    b"</Relationships>"
)


# @AI-ANCHOR: [DOCX-OPENXML-WRITER] 零外部进程纯内存 OpenXML (.docx) 极速构建器（含表格支持）
def _build_openxml_table(rows: list[list[str]]) -> str:
    """构建标准 Word OpenXML 表格节点 `<w:tbl>`。"""
    tbl_rows_xml = []
    for r_idx, row in enumerate(rows):
        cells_xml = []
        for cell_text in row:
            bold_tag = "<w:b/>" if r_idx == 0 else ""
            cells_xml.append(
                "<w:tc>"
                "<w:tcPr><w:tcW w:w=\"2000\" w:type=\"dxa\"/></w:tcPr>"
                "<w:p><w:pPr><w:jc w:val=\"center\"/></w:pPr>"
                f"<w:r><w:rPr>{bold_tag}<w:sz w:val=\"21\"/></w:rPr><w:t>{escape(str(cell_text))}</w:t></w:r>"
                "</w:p></w:tc>"
            )
        tbl_rows_xml.append(f"<w:tr>{''.join(cells_xml)}</w:tr>")
    return (
        "<w:tbl>"
        "<w:tblPr>"
        "<w:tblW w:w=\"5000\" w:type=\"pct\"/>"
        "<w:tblBorders>"
        "<w:top w:val=\"single\" w:sz=\"6\" w:space=\"0\" w:color=\"000000\"/>"
        "<w:left w:val=\"single\" w:sz=\"6\" w:space=\"0\" w:color=\"000000\"/>"
        "<w:bottom w:val=\"single\" w:sz=\"6\" w:space=\"0\" w:color=\"000000\"/>"
        "<w:right w:val=\"single\" w:sz=\"6\" w:space=\"0\" w:color=\"000000\"/>"
        "<w:insideH w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"000000\"/>"
        "<w:insideV w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"000000\"/>"
        "</w:tblBorders>"
        "</w:tblPr>"
        f"{''.join(tbl_rows_xml)}"
        "</w:tbl>"
    )


def _write_minimal_openxml_docx(
    out_file: Path,
    title: str,
    paragraphs: list[str],
    table_rows: list[list[str]] | None = None,
) -> str:
    """内置零依赖纯内存 OpenXML (.docx) 极速写入器（支持居中大标题、分页符与标准实线表格）。"""
    body_xml = [
        '<w:p><w:pPr><w:jc w:val="center"/></w:pPr>'
        f'<w:r><w:rPr><w:b/><w:sz w:val="32"/></w:rPr><w:t>{escape(title)}</w:t></w:r></w:p>'
    ]
    for p_text in paragraphs:
        if p_text == "---PAGE_BREAK---":
            body_xml.append('<w:p><w:r><w:br w:type="page"/></w:r></w:p>')
        else:
            is_heading = bool(re.match(r"^[一二三四五六七八九十]+、|^附件：", p_text))
            b_tag = "<w:b/>" if is_heading else ""
            body_xml.append(
                f'<w:p><w:r><w:rPr>{b_tag}<w:sz w:val="24"/></w:rPr><w:t>{escape(p_text)}</w:t></w:r></w:p>'
            )
    if table_rows:
        body_xml.append(_build_openxml_table(table_rows))

    doc_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f'<w:body>{"".join(body_xml)}</w:body>'
        "</w:document>"
    ).encode("utf-8")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_STORED) as zf:
        zf.writestr("[Content_Types].xml", _CONTENT_TYPES_XML)
        zf.writestr("_rels/.rels", _RELS_XML)
        zf.writestr("word/document.xml", doc_xml)
    raw = buf.getvalue()
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_bytes(raw)
    return str(out_file)


# @AI-ANCHOR: [DOCX-SITE-PROOF] 场地使用证明（自有/无偿/租赁）内存生成
def _generate_site_proof_in_process(
    state: ApplicantState,
    out_file: Path,
    is_norent: bool,
    landlord_name: str = "",
    landlord_id: str = "",
) -> str:
    addr = state.shop_address or state.id_addr or "山东省临沂市郯城县"
    ownership = "自有" if is_norent else "租赁"
    if _has_external_skills:
        try:
            import fill_site_proof
            with contextlib.redirect_stdout(io.StringIO()):
                fill_site_proof.generate_site_proof(
                    operator=state.owner_name or "经营者",
                    operator_id=state.owner_id or "",
                    address=addr,
                    name=state.shop_name or "",
                    house_type="民房",
                    ownership=ownership,
                    landlord=landlord_name,
                    landlord_id=landlord_id,
                    output=str(out_file),
                    overwrite=True,
                )
            if out_file.exists():
                return str(out_file)
        except Exception as exc:
            logger.debug("fill_site_proof 调用回退内置渲染: %s", exc)

    today = date.today()
    date_str = f"{today.year}年 {today.month} 月 {today.day} 日"
    owner_name = state.owner_name or "______"
    owner_id = state.owner_id or "__________________"
    title_suffix = "（自有房屋）" if is_norent else "（租赁房屋）"

    if is_norent:
        core_line = (
            f"兹有我辖区居民 {owner_name} ，身份证号：{owner_id}，有房屋一处位于{addr}。"
            "该房屋性质为居民住宅，因经营需要，现以该处房屋作为经营场所申请办理个体营业执照。"
            "该房屋不是危房、不是违建，经营内容无污染、无扰民现象，不在拆迁范围。"
        )
    else:
        ll_name = landlord_name.strip() or "______"
        ll_id_txt = f"（身份证号：{landlord_id}）" if landlord_id else ""
        core_line = (
            f"兹有产权人 {ll_name}{ll_id_txt} 有房屋一处位于{addr}，现租赁给 {owner_name}（身份证号：{owner_id}）"
            "作为经营场所申请办理个体营业执照。该房屋不是危房、不是违建，经营内容无污染、无扰民现象，不在拆迁范围。"
        )

    paragraphs = [
        core_line,
        "情况属实，特此证明。",
        "（此证明仅用于办理营业执照使用）",
        f"申报主体名称：{state.shop_name or '个体工商户（免字号）'}",
        "出具单位（盖章）：",
        date_str,
    ]
    return _write_minimal_openxml_docx(out_file, f"经营场所证明{title_suffix}", paragraphs)


# @AI-ANCHOR: [DOCX-LEASE-CONTRACT] 房屋租赁合同内存生成
def _generate_lease_contract_in_process(
    state: ApplicantState,
    out_file: Path,
    shop_title: str,
    rent_amount: int = 10000,
) -> str:
    landlord = (state.landlord_name or "").strip()
    addr = state.shop_address or state.id_addr or "山东省临沂市郯城县"
    if _has_external_skills:
        try:
            import fill_lease_contract
            args = [
                "--landlord", landlord or "房东",
                "--tenant", shop_title,
                "--tenant-rep", state.owner_name or "经营者",
                "--tenant-id", state.owner_id or "",
                "--address", addr,
                "--rent-amount", str(rent_amount or 10000),
                "--output", str(out_file),
                "--overwrite",
            ]
            if state.landlord_id:
                args.extend(["--landlord-id", state.landlord_id])
            with contextlib.redirect_stdout(io.StringIO()):
                fill_lease_contract.main(args)
            if out_file.exists():
                return str(out_file)
        except Exception as exc:
            logger.debug("fill_lease_contract 调用回退内置渲染: %s", exc)

    today = date.today()
    date_str = f"{today.year}年{today.month}月{today.day}日"
    ll_display = landlord or "________"
    ll_id_display = state.landlord_id or "__________________"
    tenant_rep = state.owner_name or "________"
    tenant_id = state.owner_id or "__________________"

    return _write_minimal_openxml_docx(
        out_file,
        "房屋租赁合同",
        [
            f"出租方（甲方）：{ll_display}    身份证号：{ll_id_display}",
            f"承租方（乙方）：{shop_title}（经营者：{tenant_rep}，身份证号：{tenant_id}）",
            "根据《中华人民共和国民法典》及相关法律法规，甲乙双方在自愿、平等、互利的基础上，就甲方将其合法拥有的房屋出租给乙方作为经营场所使用事宜，订立本合同：",
            f"一、租赁场地坐落：甲方将位于 {addr} 的房屋出租给乙方作为商业经营场所使用。",
            "二、租赁期限：租赁期自本合同签署之日起算，为期叁年。期满后乙方在同等条件下享有优先承租权。",
            f"三、租金标准及支付方式：年租金为人民币 {rent_amount or 10000} 元整（¥{rent_amount or 10000}元/年），按年支付。",
            "四、房屋使用与维护：乙方在租赁期间应合法合规经营，按时交纳水电及物业费用，不得擅自改变房屋主体承重结构。",
            "五、本合同一式两份，甲乙双方各执一份，自双方签字之日起生效，可作为市场主体登记注册之法定场所权属证明。",
            f"甲方（出租方）签字：{ll_display}            乙方（承租方）签字：{tenant_rep}",
            f"签署日期：{date_str}",
        ],
    )


# @AI-ANCHOR: [DOCX-ZHUGAI-DOC] 住宅改变为经营性用房证明 (.docx) 内存生成
def _generate_zhugai_in_process(state: ApplicantState, out_file: Path, shop_title: str) -> str:
    addr = state.shop_address or state.id_addr or "山东省临沂市郯城县"
    today = date.today()
    date_str = f"{today.year}年{today.month}月{today.day}日"
    scope_str = state.scope_summary or "日用百货销售"
    ownership = "自有" if state.usage != "lease" else "租赁"
    is_apartment = bool(re.search(r"(?:[0-9]{3,4}室|[0-9]+号楼|[0-9]+单元|小区|花园|公寓)", addr))

    if _has_external_skills:
        try:
            import fill_zhu_gai_shang
            from safe_docx_write import load_docx, save_docx
            tpl_path = _TPL_ZHUGAI_APT if (is_apartment and _TPL_ZHUGAI_APT.exists()) else (
                _TPL_ZHUGAI_RURAL if _TPL_ZHUGAI_RURAL.exists() else _TPL_ZHUGAI_APT
            )
            if tpl_path.exists():
                root, other_files = load_docx(tpl_path)
                fill_zhu_gai_shang.assemble_rural_zhu_gai_shang(
                    root,
                    name=shop_title,
                    biz_type="个体经营户",
                    owner=state.owner_name or "经营者",
                    address=addr,
                    scope=scope_str,
                    ownership=ownership,
                    neighbors_str="东,西,南,北",
                    date_str=date_str,
                )
                save_docx(out_file, root, other_files)
                if out_file.exists():
                    return str(out_file)
        except Exception as exc:
            logger.debug("fill_zhu_gai_shang 调用回退内置标准五段式渲染: %s", exc)

    owner_display = state.owner_name or "经营者"
    if is_apartment:
        table_rows = [
            ["序号", "门牌号（同层及上下相邻楼层）", "业主签字（签字即为同意）", "联系电话", "备注"],
            ["1", "本层邻户", "", "", ""],
            ["2", "楼上相邻户", "", "", ""],
            ["3", "楼下相邻户", "", "", ""],
            ["4", "其他关联户", "", "", ""],
        ]
    else:
        table_rows = [
            ["序号", "门牌号", "业主签字（签字即为同意）", "联系电话", "备注"],
            ["1", "东邻", "", "", ""],
            ["2", "西邻", "", "", ""],
            ["3", "南邻", "", "", ""],
            ["4", "北邻", "", "", ""],
        ]

    return _write_minimal_openxml_docx(
        out_file,
        "“住改商”登记利害关系业主同意证明",
        [
            "一、基本信息",
            f"市场主体名称：{shop_title}",
            "统一社会信用代码：（设立登记无需填写）",
            "市场主体类型：个体经营户（个体经营户/企业/农民专业合作社）",
            f"详细地址：{addr}",
            f"主要经营范围：{scope_str}",
            f"房屋权属及法定用途：{ownership}（租赁/自有）住宅",
            "利害关系业主：共有0户",
            "二、法律依据",
            "《民法典》第二百七十九条规定：业主不得违反法律、法规以及管理规约，将住宅改变为经营性用房。业主将住宅改变为经营性用房的，除遵守法律、法规以及管理规约外，应当经有利害关系的业主一致同意。",
            "三、申报须知",
            "（一）根据法律法规规定，从事娱乐场所、互联网上网服务、生产（储存、经营）危险品、产生油烟（异味、废气）的餐饮服务项目、校外培训服务等行业的，不得使用住宅类房屋办理营业执照登记注册。",
            "（二）城镇类住宅由本栋建筑物内其他业主一致签字同意；自建类住宅由“四邻”签字同意。",
            "---PAGE_BREAK---",
            "四、法律责任",
            "《中华人民共和国市场主体登记管理条例》第四十条：提交虚假材料或者采取其他欺诈手段隐瞒重要事实取得市场主体登记的，受虚假市场主体登记影响的自然人、法人和其他组织可以向登记机关提出撤销市场主体登记的申请。经调查认定存在虚假市场主体登记情形的，登记机关应当撤销市场主体登记。",
            "第四十四条：提交虚假材料或者采取其他欺诈手段隐瞒重要事实取得市场主体登记的，由登记机关责令改正，没收违法所得，并处5万元以上20万元以下的罚款；情节严重的，处20万元以上100万元以下的罚款，吊销营业执照。",
            "五、申请人承诺",
            "1.本证明真实、合法、有效，并对因虚假承诺或提交虚假材料取得市场主体登记行为所引发的一切后果，承担相应的法律责任。",
            "2.如在经营过程中，其他利害关系人投诉反映产生噪音、扰民、油烟、安全等侵害相邻权行为，争议各方协商不成的，申请人同意立刻停止侵权行为，变更经营场所或注销该市场主体，并承担相应法律责任。",
            f"申请人签字（盖章）：{owner_display}",
            f"签署日期：{date_str}",
            "---PAGE_BREAK---",
            "附件：利害关系业主签字证明",
            f"根据市场主体登记有关规定，现征求利害关系业主意见，是否同意经营者{owner_display}在{addr}设立市场主体，办理营业执照。",
        ],
        table_rows=table_rows,
    )


# @AI-ANCHOR: [DOCX-CANYIN-DOC] 餐饮服务承诺书内存生成（支持模板替换与零模板内置兜底）
def generate_canyin_commitment_in_process(
    out_file: Path,
    subject: str = "",
    operator: str = "",
    address: str = "",
    date_cn: str = "",
) -> str:
    """生成《餐饮服务承诺书》（优先匹配本地模板，无模板时直接输出标准 OpenXML 文档）。"""
    today = date.today()
    today_cn = date_cn or f"{today.year}年{today.month}月{today.day}日"
    tpl_candidates = [
        _INTERNAL_TEMPLATES / "餐饮承诺书.docx",
        _DESKTOP_DIR / "工商材料" / "餐饮承诺书.docx",
        _SHIPIN_PATH.parent / "assets" / "templates" / "餐饮承诺书.docx",
    ]
    tpl = next((p for p in tpl_candidates if p.is_file()), None)
    if tpl and _has_external_skills:
        try:
            from safe_docx_write import body_paragraphs, load_docx, paragraph_text, replace_across_runs, save_docx
            root, other_files = load_docx(tpl)
            date_re = re.compile(r"\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日")
            for para in body_paragraphs(root):
                text = paragraph_text(para)
                if date_re.search(text):
                    replace_across_runs(para, date_re.search(text).group(0), today_cn)
                if operator and operator != "经营者" and "签字" in text and "：" in text:
                    replace_across_runs(para, "签字：", f"签字：{operator}")
            out_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(tpl, out_file)
            save_docx(out_file, root, other_files)
            return str(out_file)
        except Exception as exc:
            logger.debug("餐饮承诺书模板写入回退内置渲染: %s", exc)

    op_txt = operator if (operator and operator != "经营者") else "________"
    subj_txt = subject or "个体餐饮经营户"
    addr_txt = address or "山东省临沂市郯城县"
    return _write_minimal_openxml_docx(
        out_file,
        "餐饮服务食品安全与环保合规承诺书",
        [
            f"承诺单位（字号）：{subj_txt}",
            f"经营者（负责人）：{op_txt}",
            f"经营场所地址：{addr_txt}",
            "一、本人（单位）郑重承诺严格遵守《中华人民共和国食品安全法》《山东省小餐饮登记管理办法》及相关法律法规。",
            "二、经营场所严格落实餐饮油烟净化、餐厨废弃物规范处置与隔音降噪措施，确保不产生油烟、异味、废气及噪音扰民问题。",
            "三、从业人员均取得有效健康证明后上岗，严格执行食品原料进货查验、索证索票及餐具清洗消毒制度。",
            "四、若在经营过程中违反上述承诺或引发周边居民环保、安全投诉，本单位自愿承担相应法律责任并无条件配合整改。",
            f"承诺人（签字）：{op_txt}",
            f"签署日期：{today_cn}",
        ],
    )


# @AI-ANCHOR: [DOCX-SITE-PROOF-ONLY] 独立一键生成《场地使用证明》入口
def generate_site_proof_only(state: ApplicantState, out_dir: str | Path) -> dict[str, str]:
    """独立生成《经营场所使用证明》（供办件前置准备阶段单独调用）。"""
    p_dir = Path(out_dir)
    os.makedirs(p_dir, exist_ok=True)
    name_prefix = state.owner_name or "个体户"
    is_lease = state.usage == "lease" or bool(state.landlord_name.strip()) or bool(state.landlord_id.strip())
    if is_lease:
        proof_file = p_dir / f"场地使用证明（租赁）_{name_prefix}.docx"
        res_path = _generate_site_proof_in_process(state, proof_file, False, state.landlord_name.strip(), state.landlord_id or "")
        return {"site_proof": res_path}
    elif not state.shop_name.strip():
        proof_file = p_dir / f"场地使用证明（免字号自有）_{name_prefix}.docx"
        res_path = _generate_site_proof_in_process(state, proof_file, True)
        return {"site_proof_exempt": res_path}
    else:
        proof_file = p_dir / f"场地使用证明（自有）_{name_prefix}.docx"
        res_path = _generate_site_proof_in_process(state, proof_file, True)
        return {"site_proof": res_path}


# @AI-ANCHOR: [DOCX-GENERATE-ALL] 全套工商配套文书 + 住改商前两页PNG并发总入口
def generate_documents(
    state: ApplicantState,
    out_dir: str | Path,
    include_site_proof: bool = True,
    export_zhugai_images: bool = False,
) -> dict[str, str]:
    """按办件状态智能分流并发极速出件。"""
    p_dir = Path(out_dir)
    os.makedirs(p_dir, exist_ok=True)
    generated: dict[str, str] = {}
    name_prefix = state.owner_name or "个体户"
    shop_title = state.shop_name or f"郯城县{name_prefix}店"

    tasks: list[tuple[str, Path, Any]] = []
    zhugai_file: Path | None = None

    if state.stage == 1:
        if include_site_proof:
            proof_file = p_dir / f"场地使用证明（免字号自有）_{name_prefix}.docx"
            tasks.append(("site_proof_exempt", proof_file, lambda: _generate_site_proof_in_process(state, proof_file, True)))
    elif state.stage == 2:
        if include_site_proof:
            proof_file = p_dir / f"场地使用证明（自有）_{name_prefix}.docx"
            tasks.append(("site_proof", proof_file, lambda: _generate_site_proof_in_process(state, proof_file, True)))
        zhugai_file = p_dir / f"住改商证明_{name_prefix}.docx"
        tasks.append(("zhu_gai_shang", zhugai_file, lambda: _generate_zhugai_in_process(state, zhugai_file, shop_title)))
    elif state.stage == 3:
        lease_file = p_dir / f"房屋租赁合同_{name_prefix}.docx"
        tasks.append(("lease_contract", lease_file, lambda: _generate_lease_contract_in_process(state, lease_file, shop_title)))
        if include_site_proof:
            proof_file = p_dir / f"场地使用证明（租赁）_{name_prefix}.docx"
            tasks.append(("site_proof", proof_file, lambda: _generate_site_proof_in_process(state, proof_file, False, state.landlord_name.strip(), state.landlord_id or "")))
        zhugai_file = p_dir / f"住改商证明_{name_prefix}.docx"
        tasks.append(("zhu_gai_shang", zhugai_file, lambda: _generate_zhugai_in_process(state, zhugai_file, shop_title)))

    if not tasks:
        return generated

    futures = {_DOCX_EXECUTOR.submit(func): key for key, _, func in tasks}
    for fut, key in futures.items():
        try:
            res_path = fut.result()
            if res_path:
                generated[key] = res_path
        except Exception as exc:
            logger.warning("文书 %s 生成异常: %s", key, exc)

    if export_zhugai_images and zhugai_file is not None:
        img_res = export_zhugai_first_two_pages(state, p_dir, zhugai_file)
        generated.update(img_res)

    return generated
