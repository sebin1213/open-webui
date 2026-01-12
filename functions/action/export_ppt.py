"""
title: PowerPoint Export
name: ppt 생성
author: taehee
version: 1.0.0
description: Export chat content to PowerPoint with unified processing: Text (all text elements) → Tables → Code blocks.
icon_url: data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjQiIGhlaWdodD0iMjQiIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KICA8cmVjdCB4PSIyIiB5PSIyIiB3aWR0aD0iMjAiIGhlaWdodD0iMjAiIHJ4PSIzIiBmaWxsPSIjRDI0NzI2Ii8+CiAgPHJlY3QgeD0iNSIgeT0iNyIgd2lkdGg9IjEyIiBoZWlnaHQ9IjgiIHJ4PSIxIiBmaWxsPSJ3aGl0ZSIvPgogIDxwYXRoIGQ9Ik03IDloNXYySDdWOW0wIDNoOHYySDd2LTJaIiBmaWxsPSIjRDI0NzI2Ii8+CiAgPGNpcmNsZSBjeD0iMTYuNSIgY3k9IjE2LjUiIHI9IjMuNSIgZmlsbD0id2hpdGUiLz4KICA8cGF0aCBkPSJNMTYuNSAxM3YzLjVIMjBBMy41IDMuNSAwIDAgMCAxNi41IDEzeiIgZmlsbD0iI0QyNDcyNiIvPgo8L3N2Zz4=
"""

import base64
import html
import io
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, List, Tuple

from pydantic import BaseModel
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt
from pptx.oxml.ns import qn
from pptx.oxml.xmlchemy import OxmlElement


# -------------------- Inline Markdown --------------------
INLINE_MD_PATTERN = re.compile(
    r"(`[^`]+`)|(\*\*[^*]+\*\*)|(\*[^*]+\*)"  # `code` | **bold** | *italic*
)


def _set_paragraph_lang(p, lang: str):
    pPr = p._p.get_or_add_pPr()
    rPr = pPr.get_or_add_defRPr()
    rPr.set(qn("a:lang"), lang)


def _force_run_font_family(run, family_name: str):
    """latin/ea/cs typeface 모두 지정 (필요 시)."""
    r = run._r
    rPr = r.get_or_add_rPr()

    def _set_face(tag: str):
        for child in list(rPr):
            if child.tag == qn(tag):
                rPr.remove(child)
        el = OxmlElement(tag)
        el.set("typeface", family_name)
        rPr.append(el)

    for tag in ("a:latin", "a:ea", "a:cs"):
        _set_face(tag)


def _is_font_available(font_name: str) -> bool:
    """PowerPoint에서 보이는 패밀리명 기준(간단 체크)."""
    return font_name in {
        "원신한 Bold",
        "원신한 Medium",
        "원신한 Light",
        "Consolas",
        "맑은 고딕",
    }


def _get_fallback_font(original_font: Optional[str]) -> str:
    if original_font and _is_font_available(original_font):
        return original_font
    return "맑은 고딕"


def _append_run(
    paragraph,
    text,
    *,
    bold=False,
    italic=False,
    mono=False,
    size_pt=16,
    font_name=None,
    code_font_name=None,
    force_family=False,
):
    run = paragraph.add_run()
    run.text = text
    run.font.bold = bold
    run.font.italic = italic
    chosen = code_font_name if mono else font_name
    if chosen:
        fallback = _get_fallback_font(chosen)
        run.font.name = fallback
        if force_family:
            _force_run_font_family(run, fallback)
    run.font.size = Pt(size_pt)
    return run


def _add_rich_paragraph(
    text_frame,
    text,
    *,
    level=0,
    size=16,
    mono=False,
    align=None,
    font_name=None,
    code_font_name=None,
    force_family=False,
    lang: Optional[str] = None,
):
    """**bold** / *italic* / `code` 지원."""

    if not text_frame.text:
        p = text_frame.paragraphs[0]
    else:
        p = text_frame.add_paragraph()
    p.level = level
    if align is not None:
        p.alignment = align
    if lang:
        _set_paragraph_lang(p, lang)

    if mono:
        _append_run(
            p,
            html.unescape(text),
            mono=True,
            size_pt=size,
            font_name=font_name,
            code_font_name=code_font_name,
            force_family=force_family,
        )
        return p

    pos = 0
    for m in INLINE_MD_PATTERN.finditer(text):
        if m.start() > pos:
            _append_run(
                p,
                html.unescape(text[pos : m.start()]),
                size_pt=size,
                font_name=font_name,
                code_font_name=code_font_name,
                force_family=force_family,
            )
        token = m.group(0)
        if token.startswith("`") and token.endswith("`"):
            _append_run(
                p,
                html.unescape(token[1:-1]),
                mono=True,
                size_pt=size,
                font_name=font_name,
                code_font_name=code_font_name,
                force_family=force_family,
            )
        elif token.startswith("**") and token.endswith("**"):
            _append_run(
                p,
                html.unescape(token[2:-2]),
                bold=True,
                size_pt=size,
                font_name=font_name,
                code_font_name=code_font_name,
                force_family=force_family,
            )
        elif token.startswith("*") and token.endswith("*"):
            _append_run(
                p,
                html.unescape(token[1:-1]),
                italic=True,
                size_pt=size,
                font_name=font_name,
                code_font_name=code_font_name,
                force_family=force_family,
            )
        pos = m.end()

    if pos < len(text):
        _append_run(
            p,
            html.unescape(text[pos:]),
            size_pt=size,
            font_name=font_name,
            code_font_name=code_font_name,
            force_family=force_family,
        )

    return p


def _add_rich_text_to_cell(
    cell,
    text,
    size=11,
    is_header=False,
    force_family=False,
    font_name=None,
    code_font_name=None,
    lang=None,
):
    """표 셀에 마크다운 서식 적용."""
    tf = cell.text_frame
    tf.clear()

    if is_header:
        p = tf.paragraphs[0]
        p.text = text
        p.font.bold = True
        p.font.size = Pt(size)
        p.font.color.rgb = RGBColor(255, 255, 255)
        ff = _get_fallback_font(font_name)
        p.font.name = ff
        if force_family:
            _force_run_font_family(p.runs[0], ff)
        if lang:
            _set_paragraph_lang(p, lang)
        return

    p = tf.paragraphs[0]
    if lang:
        _set_paragraph_lang(p, lang)

    pos = 0
    for m in INLINE_MD_PATTERN.finditer(text):
        if m.start() > pos:
            r = p.add_run()
            r.text = html.unescape(text[pos : m.start()])
            r.font.size = Pt(size)
            ff = _get_fallback_font(font_name)
            r.font.name = ff
            if force_family:
                _force_run_font_family(r, ff)

        token = m.group(0)
        r = p.add_run()
        if token.startswith("`") and token.endswith("`"):
            r.text = html.unescape(token[1:-1])
            ff = _get_fallback_font(code_font_name)
            r.font.name = ff
            if force_family:
                _force_run_font_family(r, ff)
        elif token.startswith("**") and token.endswith("**"):
            r.text = html.unescape(token[2:-2])
            r.font.bold = True
            ff = _get_fallback_font(font_name)
            r.font.name = ff
            if force_family:
                _force_run_font_family(r, ff)
        elif token.startswith("*") and token.endswith("*"):
            r.text = html.unescape(token[1:-1])
            r.font.italic = True
            ff = _get_fallback_font(font_name)
            r.font.name = ff
            if force_family:
                _force_run_font_family(r, ff)
        r.font.size = Pt(size)
        pos = m.end()

    if pos < len(text):
        r = p.add_run()
        r.text = html.unescape(text[pos:])
        r.font.size = Pt(size)
        ff = _get_fallback_font(font_name)
        r.font.name = ff
        if force_family:
            _force_run_font_family(r, ff)


def _strip_inline_md(text: str) -> str:
    if not text:
        return ""
    t = re.sub(r"```(.*?)```", "", text, flags=re.DOTALL)
    t = re.sub(r"\*\*([^*]+)\*\*", r"\1", t)
    t = re.sub(r"\*([^*]+)\*", r"\1", t)
    t = re.sub(r"`([^`]+)`", r"\1", t)
    return t.strip()


# -------------------- Theme access (python-pptx 1.0.2 robust) --------------------
def _get_theme_element_robust(prs: Presentation):
    theme_part = getattr(prs.part, "theme_part", None)
    if theme_part is not None:
        try:
            return theme_part.element
        except Exception:
            pass

    theme = getattr(prs.part, "theme", None)
    if theme is not None:
        try:
            return getattr(theme, "element", None) or getattr(
                getattr(theme, "part", None), "element", None
            )
        except Exception:
            pass

    try:
        for rel in prs.part.rels.values():
            if getattr(rel, "reltype", "").endswith("/theme"):
                target = getattr(rel, "_target", None)
                if target is not None:
                    return getattr(target, "element", None)
    except Exception:
        pass

    return None


def _set_theme_font_family_robust(prs: Presentation, family: str) -> bool:
    theme_el = _get_theme_element_robust(prs)
    if theme_el is None:
        return False
    font_scheme = theme_el.find(qn("a:fontScheme"))
    if font_scheme is None:
        return False

    changed = False
    fallback_family = _get_fallback_font(family)

    for node_name in ("a:majorFont", "a:minorFont"):
        node = font_scheme.find(qn(node_name))
        if node is None:
            continue
        for tag in ("a:latin", "a:ea", "a:cs"):
            el = node.find(qn(tag))
            if el is None:
                el = OxmlElement(tag)
                node.append(el)
            el.set("typeface", fallback_family)
            changed = True
    return changed


# -------------------- Action --------------------
class Action:
    class Valves(BaseModel):
        # 파일/슬라이드
        default_filename_prefix: str = "presentation"
        max_slides: int = 20
        slide_title_from_headers: bool = True

        # 템플릿 (기본: PowerPoint 기본 레이아웃 사용, 커스텀 템플릿은 선택사항)
        use_custom_template: bool = (
            True  # 커스텀 템플릿 활성화 (없어도 기본 레이아웃 사용)
        )
        template_directory: str = "templates/ppt"
        template_filename: str = "ppt_template.pptx"

        # 폰트 (PowerPoint 표시명)
        title_font_name: Optional[str] = "원신한 Bold"
        subtitle_font_name: Optional[str] = "원신한 Medium"
        body_font_name: Optional[str] = "원신한 Light"
        code_font_name: Optional[str] = "Consolas"

        # 테마/언어
        use_theme_font_mapping: bool = True
        theme_font_family: str = "원신한 Medium"
        default_lang: str = "ko-KR"
        force_run_font_family: bool = True  # 확실한 폰트 적용 보장

    def __init__(self):
        self.valves = self.Valves()
        self._status_started = False
        self._status_done = False
        self.logger = logging.getLogger(__name__)

    # ---------- Template / Presentation ----------
    def get_template_path(self) -> Optional[Path]:
        if not self.valves.use_custom_template:
            return None

        # 여러 가능한 경로 시도
        possible_paths = [
            Path("/app/backend/open_webui/static")
            / self.valves.template_directory
            / self.valves.template_filename,
            Path("static")
            / self.valves.template_directory
            / self.valves.template_filename,
            Path(".") / self.valves.template_directory / self.valves.template_filename,
            Path(self.valves.template_directory) / self.valves.template_filename,
            Path(self.valves.template_filename),  # 현재 디렉토리
        ]

        for path in possible_paths:
            if path.exists() and path.is_file():
                self.logger.info(f"Template found at: {path}")
                return path

        self.logger.warning(
            f"Template not found in any of these paths: {[str(p) for p in possible_paths]}"
        )
        return None

    def load_presentation_template(self) -> Presentation:
        """기본은 빈 프리젠테이션. 커스텀 템플릿이 활성화된 경우에만 로드."""
        if self.valves.use_custom_template:
            template_path = self.get_template_path()
            if template_path is not None:
                try:
                    prs = Presentation(str(template_path))
                    self.logger.info(f"Template loaded successfully: {template_path}")
                    self.logger.info(
                        f"Available layouts: {[layout.name for layout in prs.slide_layouts]}"
                    )
                    return prs
                except Exception as e:
                    self.logger.error(f"Failed to load template {template_path}: {e}")
            else:
                self.logger.info("Template path not found, using blank presentation")
        return Presentation()

    def _get_blank_layout(self, prs: Presentation):
        """가장 '빈' 레이아웃 탐색: 이름이 Blank이거나 placeholder가 없는 첫 레이아웃."""
        # 1) 이름 기반 탐색
        for layout in prs.slide_layouts:
            title = getattr(layout, "name", "") or ""
            if "Blank" in title or "빈" in title:
                return layout
        # 2) placeholder 수가 0인 레이아웃
        for layout in prs.slide_layouts:
            try:
                if len(layout.placeholders) == 0:
                    return layout
            except Exception:
                pass
        # 3) 마지막 수단: 인덱스 5(전통적 Blank) 또는 0
        return (
            prs.slide_layouts[5] if len(prs.slide_layouts) > 5 else prs.slide_layouts[0]
        )

    def _get_title_slide_layout(self, prs: Presentation):
        """PowerPoint에서 제목 슬라이드 레이아웃을 찾음 (기본/커스텀 모두 지원)."""
        # Searching for title slide layout

        # PowerPoint 기본 레이아웃 인덱스 우선 시도 (Title Slide는 보통 첫 번째)
        if len(prs.slide_layouts) > 0:
            layout = prs.slide_layouts[0]
            name = getattr(layout, "name", "")
            self.logger.info(
                f"Using first layout as title: '{name}' (PowerPoint default structure)"
            )
            return layout

        # Title Slide 키워드로 탐색 (커스텀 템플릿 지원)
        title_keywords = ["title slide", "제목 슬라이드", "title"]
        for layout in prs.slide_layouts:
            name = getattr(layout, "name", "") or ""
            # Checking layout

            if any(keyword in name.lower() for keyword in title_keywords):
                self.logger.info(f"Found title layout by keyword: '{name}'")
                return layout

        self.logger.warning("No title slide layout found")
        return None

    def _get_content_layout(self, prs: Presentation):
        """PowerPoint에서 컨텐츠 슬라이드 레이아웃을 찾음 (기본/커스텀 모두 지원)."""
        # Searching for content slide layout

        # PowerPoint 기본 레이아웃 인덱스 우선 시도 (Title and Content는 보통 두 번째)
        if len(prs.slide_layouts) > 1:
            layout = prs.slide_layouts[1]
            name = getattr(layout, "name", "")
            self.logger.info(
                f"Using second layout as content: '{name}' (PowerPoint default structure)"
            )
            return layout

        # Content 키워드로 탐색 (커스텀 템플릿 지원)
        content_keywords = ["content", "내용", "text", "body"]
        for layout in prs.slide_layouts:
            name = getattr(layout, "name", "") or ""
            # Checking layout

            # Title Slide가 아니면서 content 키워드가 포함된 레이아웃
            if "title slide" not in name.lower() and any(
                keyword in name.lower() for keyword in content_keywords
            ):
                self.logger.info(f"Found content layout by keyword: '{name}'")
                return layout

        # 폴백: 첫 번째 레이아웃 사용
        if len(prs.slide_layouts) > 0:
            layout = prs.slide_layouts[0]
            name = getattr(layout, "name", "")
            self.logger.info(f"Using first layout as content fallback: '{name}'")
            return layout

        self.logger.warning("No content slide layout found")
        return None

    # Obsolete function - removed (replaced by _get_title_slide_layout and _get_content_layout)

    def _find_slide_placeholders(self, slide):
        """슬라이드에서 실제 사용 가능한 placeholder 찾기 (마스터가 아닌 슬라이드 인스턴스)"""
        title_ph = None
        content_ph = None

        try:
            # 슬라이드의 shapes에서 placeholder 찾기
            placeholders = []
            for shape in slide.shapes:
                if (
                    hasattr(shape, "placeholder_format")
                    and shape.placeholder_format is not None
                ):
                    placeholders.append(shape)

            # Found placeholders in slide shapes

            # 1) PowerPoint placeholder 타입으로 식별
            for ph in placeholders:
                try:
                    ph_type = getattr(ph, "placeholder_format", None)
                    if ph_type is not None:
                        type_id = getattr(ph_type, "type", None)
                        # Slide Placeholder type_id check

                        # PowerPoint placeholder 타입: 1=제목, 2=본문, 8=내용, 7=개체
                        if type_id == 1 and title_ph is None:  # Title
                            title_ph = ph
                            # Found slide title placeholder
                        elif (
                            type_id in [2, 8, 7] and content_ph is None
                        ):  # Body/Content/Object
                            content_ph = ph
                            # Found slide content placeholder
                except Exception:
                    pass  # Error analyzing slide placeholder

            # 2) 타입으로 찾지 못했으면 순서대로 할당
            if title_ph is None or content_ph is None:
                # Assigning slide placeholders by order
                if len(placeholders) >= 1 and title_ph is None:
                    title_ph = placeholders[0]
                    # Assigned first slide placeholder as title
                if len(placeholders) >= 2 and content_ph is None:
                    content_ph = placeholders[1]
                    # Assigned second slide placeholder as content
                elif len(placeholders) >= 1 and content_ph is None:
                    content_ph = placeholders[0]  # 하나만 있으면 그것을 내용으로 사용
                    # Assigned first slide placeholder as content (no separate title)

        except Exception as e:
            self.logger.error(f"Error finding slide placeholders: {e}")

        # Slide Placeholders found - Title and Content detection completed

        return title_ph, content_ph

    # Obsolete function - removed (replaced by _find_slide_placeholders)

    # ---------- Messaging ----------
    async def _emit_status(self, emitter, description: str, done: bool):
        if emitter is None:
            return
        if not done:
            if self._status_started:
                return
            self._status_started = True
        else:
            if self._status_done:
                return
            self._status_done = True
        try:
            await emitter(
                {"type": "status", "data": {"description": description, "done": done}}
            )
        except Exception:
            pass

    # ---------- Main ----------
    async def action(
        self, body: Dict[str, Any], __event_emitter__: Optional[Any] = None
    ) -> Optional[Dict[str, Any]]:
        self._status_started = False
        self._status_done = False

        try:
            await self._emit_status(__event_emitter__, "PPT 생성 중...", done=False)

            # 대상 메시지
            msg_id = body.get("id")
            all_messages = body.get("messages", [])
            message_content = ""
            for m in all_messages:
                if isinstance(m, dict) and m.get("id") == msg_id:
                    message_content = m.get("content", "")
                    break

            if not message_content:
                self.logger.error("Target message not found for PPT generation")
                await __event_emitter__(
                    {
                        "type": "function_exception",
                        "data": {
                            "message": "PPT 생성 실패: 내보낼 메시지를 찾을 수 없습니다",
                            "error": "target message not found",
                        },
                    }
                )
                return {"status": "error", "message": "target message not found"}

            ppt_bytes = self.create_powerpoint(message_content)

            # 파일 이름/링크
            chat_title = body.get("chat", {}).get(
                "title", self.valves.default_filename_prefix
            )
            filename = f"{self.sanitize_filename(chat_title)}.pptx"
            content = base64.b64encode(ppt_bytes).decode("utf-8")

            # 자동 다운로드 트리거
            await __event_emitter__(
                {
                    "type": "document_generation",
                    "data": {
                        "name": filename,
                        "content": content,
                        "content_type": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                    },
                }
            )
            await self._emit_status(__event_emitter__, "PPT 생성 완료", done=True)

            return {"status": "success", "message": f"PPT 파일 '{filename}' 생성 완료"}

        except Exception as e:
            self.logger.error(f"PPT generation failed: {str(e)}", exc_info=True)
            await __event_emitter__(
                {
                    "type": "function_exception",
                    "data": {"message": f"PPT 생성 실패: {str(e)}", "error": str(e)},
                }
            )
            return {"status": "error", "message": str(e)}
        finally:
            if not self._status_done:
                await self._emit_status(__event_emitter__, "처리 종료", done=True)
            self._status_started = False
            self._status_done = False

    # ---------- PowerPoint creation ----------
    def create_powerpoint(self, content: str) -> bytes:
        prs = self.load_presentation_template()

        # 테마 폰트 매핑 (실패 시 run 강제 지정 폴백)
        if self.valves.use_theme_font_mapping:
            ok = _set_theme_font_family_robust(prs, self.valves.theme_font_family)
            if not ok:
                self.valves.force_run_font_family = True

        slides = self.parse_markdown_to_slides(content)
        title_md = "AI Generated Presentation"
        if self.valves.slide_title_from_headers:
            h1 = self._extract_first_h1(slides)
            if h1:
                title_md = h1
        title_plain = _strip_inline_md(title_md)

        lang = self.valves.default_lang
        force = self.valves.force_run_font_family

        # 레이아웃 선택 - 항상 PowerPoint 기본 레이아웃 구조 사용
        template_path = self.get_template_path()
        has_custom_template = (
            self.valves.use_custom_template and template_path is not None
        )

        self.logger.info(
            f"Template usage: custom_enabled={self.valves.use_custom_template}, custom_path_exists={template_path is not None}, has_custom={has_custom_template}"
        )

        # 커스텀 템플릿이 있든 없든 PowerPoint 레이아웃 구조 사용
        title_layout = self._get_title_slide_layout(prs)  # 제목 슬라이드용
        content_layout = self._get_content_layout(prs)  # 컨텐츠 슬라이드용

        # 레이아웃을 찾지 못했을 때만 Blank 폴백
        if not title_layout:
            self.logger.warning("No title layout found, using blank layout for title")
            title_layout = self._get_blank_layout(prs)
        if not content_layout:
            self.logger.warning(
                "No content layout found, using blank layout for content"
            )
            content_layout = self._get_blank_layout(prs)

        # 항상 템플릿 방식 사용 (placeholder 활용)
        use_template_layout = True

        # 제목 슬라이드
        if title_plain:
            if use_template_layout and title_layout:
                # 템플릿의 제목 슬라이드 레이아웃 사용
                slide = prs.slides.add_slide(title_layout)
                title_ph, subtitle_ph = self._find_slide_placeholders(slide)

                if title_ph:
                    title_tf = title_ph.text_frame
                    title_tf.clear()
                    _add_rich_paragraph(
                        title_tf,
                        title_md,
                        size=36,
                        align=PP_ALIGN.CENTER,
                        font_name=self.valves.title_font_name,
                        code_font_name=self.valves.code_font_name,
                        force_family=force,
                        lang=lang,
                    )

                if subtitle_ph:
                    subtitle_tf = subtitle_ph.text_frame
                    subtitle_tf.clear()
                    _add_rich_paragraph(
                        subtitle_tf,
                        f"생성일: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                        size=14,
                        align=PP_ALIGN.CENTER,
                        font_name=self.valves.subtitle_font_name,
                        code_font_name=self.valves.code_font_name,
                        force_family=force,
                        lang=lang,
                    )
            else:
                # Blank 레이아웃으로 직접 텍스트박스 생성
                slide = prs.slides.add_slide(title_layout)
                title_box = slide.shapes.add_textbox(
                    Inches(0.5), Inches(2.0), Inches(9.0), Inches(1.5)
                )
                title_tf = title_box.text_frame
                title_tf.clear()
                _add_rich_paragraph(
                    title_tf,
                    title_md,
                    size=36,
                    align=PP_ALIGN.CENTER,
                    font_name=self.valves.title_font_name,
                    code_font_name=self.valves.code_font_name,
                    force_family=force,
                    lang=lang,
                )

                subtitle_box = slide.shapes.add_textbox(
                    Inches(0.5), Inches(4.0), Inches(9.0), Inches(0.8)
                )
                subtitle_tf = subtitle_box.text_frame
                subtitle_tf.clear()
                _add_rich_paragraph(
                    subtitle_tf,
                    f"생성일: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                    size=14,
                    align=PP_ALIGN.CENTER,
                    font_name=self.valves.subtitle_font_name,
                    code_font_name=self.valves.code_font_name,
                    force_family=force,
                    lang=lang,
                )

        # 컨텐츠 슬라이드들
        for sd in slides[: self.valves.max_slides]:
            self.create_slide_from_data(prs, sd, content_layout, use_template_layout)

        buf = io.BytesIO()
        prs.save(buf)
        buf.seek(0)
        return buf.getvalue()

    def _extract_first_h1(self, slides_content: List[Dict[str, Any]]) -> Optional[str]:
        for s in slides_content:
            if s.get("level") == 1 and s.get("title"):
                return s["title"]
        return None

    # ---------- Parsing ----------
    def parse_markdown_to_slides(self, content: str) -> List[Dict[str, Any]]:
        slides: List[Dict[str, Any]] = []
        lines = content.split("\n")
        current = {
            "title": "",
            "content": [],
            "bullet_points": [],
            "tables": [],
            "code_blocks": [],
            "quotes": [],
            "level": None,
        }

        i = 0
        while i < len(lines):
            line = lines[i].strip()

            if line.startswith("#"):
                if current["title"] or any(
                    current[k]
                    for k in [
                        "content",
                        "bullet_points",
                        "tables",
                        "code_blocks",
                        "quotes",
                    ]
                ):
                    slides.append(current)
                level = len(line) - len(line.lstrip("#"))
                title = line.lstrip("#").strip()
                current = {
                    "title": title,
                    "content": [],
                    "bullet_points": [],
                    "tables": [],
                    "code_blocks": [],
                    "quotes": [],
                    "level": level,
                }
                i += 1
                continue

            if "|" in line and line.count("|") >= 2:
                table_data, next_i = self.parse_table(lines, i)
                if table_data:
                    current["tables"].append(table_data)
                i = next_i
                continue

            if line.startswith("```"):
                code_block, next_i = self.parse_code_block(lines, i)
                if code_block:
                    current["code_blocks"].append(code_block)
                i = next_i
                continue

            if line.startswith(">"):
                quote_text = line[1:].strip()
                if quote_text:
                    # 인용문도 일반 텍스트로 취급 (표/코드만 특수 처리)
                    current["quotes"].append(quote_text)
                    current["content"].append(quote_text)
                i += 1
                continue

            # 들여쓰기된 리스트 항목 처리
            stripped_line = line.lstrip()
            if stripped_line.startswith(("- ", "* ", "+ ")) or re.match(
                r"^\d+\.\s", stripped_line
            ):
                # 불릿도 일반 텍스트로 취급 (표/코드만 특수 처리)
                bullet_text = re.sub(r"^[-*+]\s|\d+\.\s", "", stripped_line).strip()
                if bullet_text:
                    # 메타 정보는 유지(호환), 렌더링은 텍스트로
                    current["bullet_points"].append({"text": bullet_text, "level": 0})
                    current["content"].append(bullet_text)
                i += 1
                continue

            if line and not line.startswith(("#", "---", "***")):
                current["content"].append(line)

            i += 1

        if current["title"] or any(
            current[k]
            for k in ["content", "bullet_points", "tables", "code_blocks", "quotes"]
        ):
            slides.append(current)

        return slides

    def parse_table(
        self, lines: List[str], start_index: int
    ) -> Tuple[Optional[List[List[str]]], int]:
        data: List[List[str]] = []
        i = start_index
        while i < len(lines):
            line = lines[i].strip()
            if not line or "|" not in line:
                break
            # 구분자 행 무시
            if re.match(r"^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)+\|?\s*$", line):
                i += 1
                continue
            cells = [
                c.strip()
                for c in (
                    line.split("|")[1:-1] if line.startswith("|") else line.split("|")
                )
            ]
            if cells:
                data.append(cells)
            i += 1
        return (data if data else None), i

    def parse_code_block(
        self, lines: List[str], start_index: int
    ) -> Tuple[Optional[Dict[str, str]], int]:
        i = start_index + 1
        code_lines: List[str] = []
        fence_line = lines[start_index].strip()
        language = fence_line.replace("```", "").strip()
        while i < len(lines):
            if lines[i].strip() == "```":
                return (
                    (
                        {"language": language, "code": "\n".join(code_lines)}
                        if code_lines
                        else None
                    ),
                    i + 1,
                )
            code_lines.append(lines[i])
            i += 1
        return (
            (
                {"language": language, "code": "\n".join(code_lines)}
                if code_lines
                else None
            ),
            i,
        )

    # ---------- Slide Builders ----------
    def create_slide_from_data(
        self,
        prs: Presentation,
        slide_data: Dict[str, Any],
        layout,
        use_template_layout: bool = False,
    ) -> None:
        slide = prs.slides.add_slide(layout)

        # 모든 슬라이드를 통합 처리: 텍스트 → 표 → 코드 순서로 처리
        self._unified_slide(slide, slide_data, use_template_layout=use_template_layout)

    def _unified_slide(self, slide, sd, use_template_layout: bool = False):
        """통합 슬라이드 처리: 텍스트 → 표 → 코드 순서로 처리
        - 텍스트: 불릿포인트, 인용문, 일반텍스트 등 모든 텍스트 요소 통합
        - 표: 테이블 데이터 별도 처리
        - 코드: 코드 블록 별도 처리
        """
        title_md = (sd.get("title") or "").strip()
        content_lines = sd.get("content", [])
        tables = sd.get("tables", [])
        code_blocks = sd.get("code_blocks", [])

        lang = self.valves.default_lang
        force = self.valves.force_run_font_family
        has_title = bool(_strip_inline_md(title_md))

        # 1단계: 제목 처리
        if has_title:
            if use_template_layout:
                title_ph, _ = self._find_slide_placeholders(slide)
                if title_ph:
                    title_tf = title_ph.text_frame
                    title_tf.clear()
                    _add_rich_paragraph(
                        title_tf,
                        title_md,
                        size=24,
                        font_name=self.valves.title_font_name,
                        code_font_name=self.valves.code_font_name,
                        force_family=force,
                        lang=lang,
                    )
            else:
                self._title_box(slide, title_md, lang, force)

        # 현재 위치 계산
        current_top = Inches(1.2) if has_title else Inches(0.8)

        # 2단계: 모든 텍스트 요소 통합 처리 (불릿포인트, 인용문, 일반텍스트 등)
        # content_lines에는 이미 모든 텍스트 요소가 순서대로 포함됨
        if content_lines:
            current_top = self._add_text_content(
                slide, content_lines, current_top, use_template_layout, lang, force
            )

        # 3단계: 표 처리
        if tables:
            current_top = self._add_tables(slide, tables, current_top, lang, force)

        # 4단계: 코드 처리 (새로운 텍스트박스)
        if code_blocks:
            current_top = self._add_code_blocks(
                slide, code_blocks, current_top, lang, force
            )

    def _add_text_content(
        self, slide, content_lines, current_top, use_template_layout, lang, force
    ):
        """텍스트 내용을 템플릿 placeholder 또는 텍스트박스에 추가

        - placeholder가 있으면 그 안에 텍스트를 쓰고, 표/코드가 겹치지 않도록 placeholder 하단으로 current_top 이동
        - placeholder가 없으면 텍스트박스를 생성하고, 그 하단으로 current_top 이동
        """
        if use_template_layout:
            # 템플릿 사용: placeholder에 텍스트 작성
            _, content_ph = self._find_slide_placeholders(slide)
            if content_ph:
                content_tf = content_ph.text_frame
                content_tf.clear()
                self._write_text_to_textframe(content_tf, content_lines, lang, force)
                return content_ph.top + content_ph.height + Inches(0.3)
            # placeholder가 없으면 텍스트박스로 폴백

        # 템플릿 미사용 또는 placeholder 없음: 새 텍스트박스 생성
        text_height = Inches(len(content_lines) * 0.25 + 0.5)
        text_box = slide.shapes.add_textbox(
            Inches(0.5), current_top, Inches(9), text_height
        )
        tf = text_box.text_frame
        tf.clear()
        self._write_text_to_textframe(tf, content_lines, lang, force)
        return current_top + text_height + Inches(0.3)

    def _add_tables(self, slide, tables, current_top, lang, force):
        """표를 슬라이드에 추가"""
        for table_data in tables:
            if not table_data:
                continue

            rows = len(table_data)
            cols = len(table_data[0]) if rows > 0 else 1
            table_height = Inches(min(2.5, rows * 0.4))

            tbl = slide.shapes.add_table(
                rows, cols, Inches(0.5), current_top, Inches(9), table_height
            ).table

            # 테이블 데이터 채우기
            for r, row in enumerate(table_data):
                for c in range(cols):
                    text = str(row[c]) if c < len(row) else ""
                    cell = tbl.cell(r, c)
                    if r == 0:  # 헤더 행
                        cell.fill.solid()
                        cell.fill.fore_color.rgb = RGBColor(68, 114, 196)
                        _add_rich_text_to_cell(
                            cell,
                            text,
                            size=12,
                            is_header=True,
                            force_family=force,
                            font_name=self.valves.body_font_name,
                            code_font_name=self.valves.code_font_name,
                            lang=lang,
                        )
                    else:
                        _add_rich_text_to_cell(
                            cell,
                            text,
                            size=11,
                            is_header=False,
                            force_family=force,
                            font_name=self.valves.body_font_name,
                            code_font_name=self.valves.code_font_name,
                            lang=lang,
                        )

            current_top += table_height + Inches(0.3)

        return current_top

    def _add_code_blocks(self, slide, code_blocks, current_top, lang, force):
        """코드 블록을 새로운 텍스트박스에 추가"""
        for block in code_blocks:
            code_text = block.get("code", "")
            language = block.get("language", "")

            if not code_text:
                continue

            # 코드 블록용 새 텍스트박스 생성
            code_height = Inches(len(code_text.split("\n")) * 0.2 + 0.8)
            code_box = slide.shapes.add_textbox(
                Inches(0.5), current_top, Inches(9), code_height
            )
            tf = code_box.text_frame
            tf.clear()

            # 언어 표시와 함께 코드 추가
            display_text = f"[{language}]\n{code_text}" if language else code_text
            _add_rich_paragraph(
                tf,
                display_text,
                size=12,
                mono=True,
                font_name=self.valves.body_font_name,
                code_font_name=self.valves.code_font_name,
                force_family=force,
                lang=lang,
            )

            current_top += code_height + Inches(0.3)

        return current_top

    def _write_text_to_textframe(self, tf, content_lines, lang, force):
        """텍스트 프레임에 내용 작성 (표/코드 제외 전부 일반 텍스트)"""
        for item in content_lines:
            text = item.get("text", "") if isinstance(item, dict) else str(item)
            _add_rich_paragraph(
                tf,
                text,
                size=16,
                font_name=self.valves.body_font_name,
                code_font_name=self.valves.code_font_name,
                force_family=force,
                lang=lang,
            )

    def _title_box(self, slide, title_md: str, lang: str, force: bool):
        if not _strip_inline_md(title_md):
            return None
        box = slide.shapes.add_textbox(Inches(0.5), Inches(0.3), Inches(9), Inches(0.8))
        tf = box.text_frame
        tf.clear()
        _add_rich_paragraph(
            tf,
            title_md,
            size=24,
            font_name=self.valves.title_font_name,
            code_font_name=self.valves.code_font_name,
            force_family=force,
            lang=lang,
        )
        return box

    def _add_content_to_placeholder_or_textbox(
        self,
        slide,
        title_md: str,
        content_lines,
        use_template_layout: bool,
        content_type: str = "normal",
    ):
        """템플릿 placeholder를 사용하거나 직접 텍스트박스를 생성하여 컨텐츠 추가"""
        lang = self.valves.default_lang
        force = self.valves.force_run_font_family
        has_title = bool(_strip_inline_md(title_md))

        # Adding content to slide

        if use_template_layout:
            # 슬라이드의 실제 placeholder 사용 (마스터가 아닌 슬라이드 인스턴스)
            title_ph, content_ph = self._find_slide_placeholders(slide)

            # 제목 추가
            if has_title and title_ph:
                title_tf = title_ph.text_frame
                title_tf.clear()
                _add_rich_paragraph(
                    title_tf,
                    title_md,
                    size=24,
                    font_name=self.valves.title_font_name,
                    code_font_name=self.valves.code_font_name,
                    force_family=force,
                    lang=lang,
                )
            elif has_title:
                self.logger.warning(f"Title placeholder not found for: '{title_md}'")

            # 본문 추가
            if content_ph and content_lines:
                content_tf = content_ph.text_frame
                content_tf.clear()

                if content_type in ["bullet", "bullet_mixed"]:
                    for bullet in content_lines:
                        # bullet이 dict인 경우 (새 형식)와 string인 경우 (기존 형식) 모두 지원
                        if isinstance(bullet, dict):
                            bullet_text = bullet["text"]
                            bullet_level = bullet["level"]
                        else:
                            bullet_text = bullet
                            bullet_level = 0

                        # Adding bullet point
                        _add_rich_paragraph(
                            content_tf,
                            bullet_text,
                            level=bullet_level,
                            size=16,
                            font_name=self.valves.body_font_name,
                            code_font_name=self.valves.code_font_name,
                            force_family=force,
                            lang=lang,
                        )
                elif content_type in ["code", "code_mixed"]:
                    for item in content_lines:
                        # 일반 텍스트인지 코드 블록인지 확인
                        if isinstance(item, dict) and item.get("code"):
                            # 코드 블록
                            text = (
                                f"[{item.get('language','')}]\n{item.get('code','')}"
                                if item.get("language")
                                else item.get("code", "")
                            )
                            _add_rich_paragraph(
                                content_tf,
                                text,
                                size=12,
                                mono=True,
                                font_name=self.valves.body_font_name,
                                code_font_name=self.valves.code_font_name,
                                force_family=force,
                                lang=lang,
                            )
                        elif isinstance(item, str) and not item.startswith(
                            "[CODE_INSERT_"
                        ):
                            # 일반 텍스트
                            _add_rich_paragraph(
                                content_tf,
                                item,
                                size=16,
                                font_name=self.valves.body_font_name,
                                code_font_name=self.valves.code_font_name,
                                force_family=force,
                                lang=lang,
                            )
                elif content_type in ["quote", "quote_mixed"]:
                    for item in content_lines:
                        if isinstance(item, str):
                            if item.startswith("[QUOTE_INSERT_"):
                                # 인용문 마커는 건너뜀 (별도 처리)
                                continue
                            elif any(
                                keyword in item.lower()
                                for keyword in ["인용", "quote", "말씀", "언급"]
                            ):
                                # 인용 키워드가 있는 텍스트는 일반 텍스트로 처리
                                _add_rich_paragraph(
                                    content_tf,
                                    item,
                                    size=16,
                                    font_name=self.valves.body_font_name,
                                    code_font_name=self.valves.code_font_name,
                                    force_family=force,
                                    lang=lang,
                                )
                            else:
                                # 실제 인용문
                                _add_rich_paragraph(
                                    content_tf,
                                    f'"{item}"',
                                    size=18,
                                    align=PP_ALIGN.CENTER,
                                    font_name=self.valves.body_font_name,
                                    code_font_name=self.valves.code_font_name,
                                    force_family=force,
                                    lang=lang,
                                )
                elif content_type in ["table_mixed"]:
                    # 테이블 혼합 모드: 마커가 아닌 일반 텍스트만 처리
                    for item in content_lines:
                        if isinstance(item, str) and not item.startswith(
                            "[TABLE_INSERT_"
                        ):
                            _add_rich_paragraph(
                                content_tf,
                                item,
                                size=16,
                                font_name=self.valves.body_font_name,
                                code_font_name=self.valves.code_font_name,
                                force_family=force,
                                lang=lang,
                            )
                else:  # normal content
                    for line in content_lines:
                        # Adding normal content
                        _add_rich_paragraph(
                            content_tf,
                            line,
                            size=16,
                            font_name=self.valves.body_font_name,
                            code_font_name=self.valves.code_font_name,
                            force_family=force,
                            lang=lang,
                        )
            elif content_ph and not content_lines:
                self.logger.warning(
                    "Content placeholder found but no content lines to add"
                )
                # 빈 컨텐츠라도 placeholder에 기본 텍스트 추가
                content_tf = content_ph.text_frame
                content_tf.clear()
                _add_rich_paragraph(
                    content_tf,
                    "[내용이 없습니다]",
                    size=16,
                    font_name=self.valves.body_font_name,
                    code_font_name=self.valves.code_font_name,
                    force_family=force,
                    lang=lang,
                )
            elif not content_ph and content_lines:
                self.logger.warning(
                    f"Content lines available ({len(content_lines)}) but no content placeholder found"
                )
            elif not content_ph and not content_lines:
                # No content placeholder and no content lines - empty slide
                pass

            # Content processing completed
        else:
            # 직접 텍스트박스 생성 (기존 방식)
            if has_title:
                self._title_box(slide, title_md, lang, force)
                if content_type in ["quote", "quote_mixed"]:
                    content_box = slide.shapes.add_textbox(
                        Inches(1.0), Inches(2.5), Inches(8.0), Inches(2.5)
                    )
                else:
                    content_box = slide.shapes.add_textbox(
                        Inches(0.5), Inches(1.2), Inches(9), Inches(5.3)
                    )
            else:
                if content_type in ["quote", "quote_mixed"]:
                    content_box = slide.shapes.add_textbox(
                        Inches(1.0), Inches(3.0), Inches(8.0), Inches(2.0)
                    )
                else:
                    content_box = slide.shapes.add_textbox(
                        Inches(0.5), Inches(0.5), Inches(9), Inches(6.5)
                    )

            tf = content_box.text_frame
            tf.clear()

            if content_type in ["bullet", "bullet_mixed"]:
                for bullet in content_lines:
                    # bullet이 dict인 경우 (새 형식)와 string인 경우 (기존 형식) 모두 지원
                    if isinstance(bullet, dict):
                        bullet_text = bullet["text"]
                        bullet_level = bullet["level"]
                    else:
                        bullet_text = bullet
                        bullet_level = 0

                    _add_rich_paragraph(
                        tf,
                        bullet_text,
                        level=bullet_level,
                        size=16,
                        font_name=self.valves.body_font_name,
                        code_font_name=self.valves.code_font_name,
                        force_family=force,
                        lang=lang,
                    )
            elif content_type in ["code", "code_mixed"]:
                for item in content_lines:
                    # 일반 텍스트인지 코드 블록인지 확인
                    if isinstance(item, dict) and item.get("code"):
                        # 코드 블록
                        text = (
                            f"[{item.get('language','')}]\n{item.get('code','')}"
                            if item.get("language")
                            else item.get("code", "")
                        )
                        _add_rich_paragraph(
                            tf,
                            text,
                            size=12,
                            mono=True,
                            font_name=self.valves.body_font_name,
                            code_font_name=self.valves.code_font_name,
                            force_family=force,
                            lang=lang,
                        )
                    elif isinstance(item, str) and not item.startswith("[CODE_INSERT_"):
                        # 일반 텍스트
                        _add_rich_paragraph(
                            tf,
                            item,
                            size=16,
                            font_name=self.valves.body_font_name,
                            code_font_name=self.valves.code_font_name,
                            force_family=force,
                            lang=lang,
                        )
            elif content_type in ["quote", "quote_mixed"]:
                for item in content_lines:
                    if isinstance(item, str):
                        if item.startswith("[QUOTE_INSERT_"):
                            # 인용문 마커는 건너뜀
                            continue
                        elif any(
                            keyword in item.lower()
                            for keyword in ["인용", "quote", "말씀", "언급"]
                        ):
                            # 인용 키워드가 있는 텍스트는 일반 텍스트로 처리
                            _add_rich_paragraph(
                                tf,
                                item,
                                size=16,
                                font_name=self.valves.body_font_name,
                                code_font_name=self.valves.code_font_name,
                                force_family=force,
                                lang=lang,
                            )
                        else:
                            # 실제 인용문
                            _add_rich_paragraph(
                                tf,
                                f'"{item}"',
                                size=18,
                                align=PP_ALIGN.CENTER,
                                font_name=self.valves.body_font_name,
                                code_font_name=self.valves.code_font_name,
                                force_family=force,
                                lang=lang,
                            )
            elif content_type in ["table_mixed"]:
                # 테이블 혼합 모드: 마커가 아닌 일반 텍스트만 처리
                for item in content_lines:
                    if isinstance(item, str) and not item.startswith("[TABLE_INSERT_"):
                        _add_rich_paragraph(
                            tf,
                            item,
                            size=16,
                            font_name=self.valves.body_font_name,
                            code_font_name=self.valves.code_font_name,
                            force_family=force,
                            lang=lang,
                        )
            else:  # normal content
                for line in content_lines:
                    _add_rich_paragraph(
                        tf,
                        line,
                        size=16,
                        font_name=self.valves.body_font_name,
                        code_font_name=self.valves.code_font_name,
                        force_family=force,
                        lang=lang,
                    )
                    
    # ---------- Utils ----------
    def count_slides(self, content: str) -> int:
        return len(self.parse_markdown_to_slides(content)) + 1  # 제목 포함

    def sanitize_filename(self, filename: str) -> str:
        invalid_chars = '<>:"/\\|?*'
        for ch in invalid_chars:
            filename = filename.replace(ch, "_")
        return filename.strip() or "presentation"
