"""
@AI-ANCHOR: [ZHUGAI-IMG-EXPORTER] 住改商证明前两页免签章高清 PNG 自动导图模块 (<210行微切片)
职责：从住改商 .docx 提取文本并并发渲染导出前两页高清 A4 PNG 图片供政务网直接拖拽上传。
修复记录：补齐原版遗漏的模块级 `_CACHED_FONTS` 字典定义，消除字体加载时的静默 NameError。
"""
from __future__ import annotations

import io
import logging
import os
import xml.etree.ElementTree as ET
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from typing import Any

from .models import ApplicantState

logger = logging.getLogger("gth.zhugai_img")

_IMG_EXECUTOR = ThreadPoolExecutor(max_workers=2)
list(_IMG_EXECUTOR.map(lambda _: None, range(2)))

# 模块级字体缓存（修复原版因遗漏定义导致 NameError 退化为无中文字体的问题）
_CACHED_FONTS: dict[int, Any] = {}


# @AI-ANCHOR: [ZHUGAI-FONT-AND-PARSE] 跨平台中文字体加载与 Word 分页段落提取
def _get_cjk_font(size: int) -> Any:
    if size in _CACHED_FONTS:
        return _CACHED_FONTS[size]
    try:
        from PIL import ImageFont
        font_candidates = (
            r"C:\Windows\Fonts\simsun.ttc",
            r"C:\Windows\Fonts\msyh.ttc",
            r"C:\Windows\Fonts\simhei.ttf",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        )
        for fp in font_candidates:
            if os.path.exists(fp):
                f = ImageFont.truetype(fp, size)
                _CACHED_FONTS[size] = f
                return f
        f = ImageFont.load_default()
        _CACHED_FONTS[size] = f
        return f
    except Exception as exc:
        logger.debug("加载 CJK 字体失败 (size=%d): %s", size, exc)
        return None


def _extract_pages_from_docx(docx_path: Path) -> list[list[str]]:
    """从生成的 .docx 文件中解析段落与表格内容并按分页符拆分为页列表。"""
    if not docx_path or not docx_path.exists():
        return []
    try:
        with zipfile.ZipFile(docx_path, "r") as zf:
            xml_bytes = zf.read("word/document.xml")
        root = ET.fromstring(xml_bytes)
        ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        pages: list[list[str]] = [[]]
        body = root.find("w:body", ns)
        if body is None:
            return []

        for elem in body:
            tag = elem.tag.split("}")[-1]
            if tag == "p":
                has_page_break = False
                for br in elem.findall(".//w:br", ns):
                    if br.attrib.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}type") == "page":
                        has_page_break = True
                texts = [t.text for t in elem.findall(".//w:t", ns) if t.text]
                line = "".join(texts).strip()
                if line:
                    pages[-1].append(line)
                if has_page_break and pages[-1]:
                    pages.append([])
            elif tag == "tbl":
                for row in elem.findall(".//w:tr", ns):
                    row_cells = []
                    for cell in row.findall(".//w:tc", ns):
                        c_txt = "".join(t.text for t in cell.findall(".//w:t", ns) if t.text).strip()
                        if c_txt:
                            row_cells.append(c_txt)
                    if row_cells:
                        pages[-1].append(" | ".join(row_cells))
        return [p for p in pages if p]
    except Exception as exc:
        logger.debug("解析 docx 分页内容异常: %s", exc)
        return []


# @AI-ANCHOR: [ZHUGAI-EXPORT-PNG] 并发渲染导出《住改商证明》第1页、第2页 PNG
def export_zhugai_first_two_pages(
    state: ApplicantState,
    out_dir: str | Path,
    docx_path: Path | None = None,
) -> dict[str, str]:
    """将《住改商证明》无需签字盖章的前两页并发导出为高清 PNG 图片，供直接拖拽上传政务网。"""
    p_dir = Path(out_dir)
    os.makedirs(p_dir, exist_ok=True)
    name_prefix = state.owner_name or "个体户"
    shop_title = state.shop_name or f"郯城县{name_prefix}店"
    addr = state.shop_address or state.id_addr or "山东省临沂市郯城县"
    today = date.today()
    date_str = f"{today.year}年{today.month}月{today.day}日"
    scope_str = state.scope_summary or "日用百货销售"
    ownership = "自有" if state.usage != "lease" else "租赁"

    p1_file = p_dir / f"住改商证明_{name_prefix}_第1页.png"
    p2_file = p_dir / f"住改商证明_{name_prefix}_第2页.png"

    extracted_pages = _extract_pages_from_docx(docx_path) if docx_path else []

    page1_lines = (
        extracted_pages[0]
        if len(extracted_pages) >= 2 and len(extracted_pages[0]) >= 4
        else [
            "“住改商”登记利害关系业主同意证明（第一页）",
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
            "（一）根据法律法规规定，从事娱乐场所、互联网上网服务、危险品、产生油烟餐饮、校外培训等项目的，不得使用住宅类房屋办理营业执照登记注册。",
            "（二）城镇类住宅由本栋建筑物内其他业主一致签字同意；自建类住宅由“四邻”签字同意。",
        ]
    )

    page2_lines = (
        extracted_pages[1]
        if len(extracted_pages) >= 2 and len(extracted_pages[1]) >= 4
        else [
            "“住改商”登记利害关系业主同意证明（第二页）",
            "四、法律责任",
            "《中华人民共和国市场主体登记管理条例》第四十条：提交虚假材料或者采取其他欺诈手段隐瞒重要事实取得市场主体登记的，受虚假市场主体登记影响的自然人、法人和其他组织可以向登记机关提出撤销市场主体登记的申请。",
            "第四十四条：提交虚假材料或者采取其他欺诈手段隐瞒重要事实取得市场主体登记的，由登记机关责令改正，没收违法所得，并处5万元以上20万元以下的罚款；情节严重的，处20万元以上100万元以下的罚款，吊销营业执照。",
            "五、申请人承诺",
            "1.本证明真实、合法、有效，并对因虚假承诺或提交虚假材料取得市场主体登记行为所引发的一切后果，承担相应的法律责任。",
            "2.如在经营过程中，其他利害关系人投诉反映产生噪音、扰民、油烟、安全等侵害相邻权行为，争议各方协商不成的，申请人同意立刻停止侵权行为，变更经营场所或注销该市场主体，并承担相应法律责任。",
            "附件：利害关系业主签字证明",
            f"申请人签字（盖章）：{name_prefix}",
            f"签署日期：{date_str}",
        ]
    )

    try:
        from PIL import Image, ImageDraw
        font_title = _get_cjk_font(22)
        font_body = _get_cjk_font(16)
        font_small = _get_cjk_font(13)

        def _render_a4_page(lines: list[str], out_path: Path, page_no: int) -> None:
            w, h = 840, 1188
            img = Image.new("RGB", (w, h), color=(255, 255, 255))
            draw = ImageDraw.Draw(img)

            draw.rectangle([40, 40, w - 40, h - 40], outline=(0, 0, 0), width=2)
            draw.line([60, 120, w - 60, 120], fill=(0, 0, 0), width=3)

            title_txt = lines[0] if lines else f"住宅改变为经营性用房证明（第 {page_no} 页）"
            draw.text((68, 72), title_txt, fill=(0, 0, 0), font=font_title)

            y = 148
            max_chars = 40
            for raw_line in lines[1:]:
                chunks = [raw_line[i : i + max_chars] for i in range(0, max(1, len(raw_line)), max_chars)]
                for ch_idx, chunk in enumerate(chunks):
                    prefix = "    " if ch_idx > 0 else ""
                    draw.text((68, y), prefix + chunk, fill=(20, 20, 20), font=font_body)
                    y += 30
                y += 10
                if y > h - 110:
                    break

            draw.line([60, h - 84, w - 60, h - 84], fill=(120, 120, 120), width=1)
            footer_txt = f"山东省市场主体全程电子化登记配套附件 · 住改商证明第 {page_no} 页（免签章格式页）"
            draw.text((68, h - 68), footer_txt, fill=(90, 90, 90), font=font_small)

            buf = io.BytesIO()
            img.save(buf, format="PNG", compress_level=1)
            out_path.write_bytes(buf.getvalue())

        f1 = _IMG_EXECUTOR.submit(_render_a4_page, page1_lines, p1_file, 1)
        f2 = _IMG_EXECUTOR.submit(_render_a4_page, page2_lines, p2_file, 2)
        f1.result()
        f2.result()
    except Exception as exc:
        logger.warning("PIL 渲染住改商 PNG 失败，使用最小 PNG 兜底: %s", exc)
        _MIN_PNG = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\xff\xff?"
            b"\x00\x05\xfe\x02\xfe\r\xefF\xb8\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        p1_file.write_bytes(_MIN_PNG)
        p2_file.write_bytes(_MIN_PNG)

    return {
        "zhu_gai_shang_p1_img": str(p1_file),
        "zhu_gai_shang_p2_img": str(p2_file),
    }
