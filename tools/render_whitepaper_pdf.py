#!/usr/bin/env python3
"""Render the authoritative Aegis feasibility Markdown as a guarded PDF.

The renderer intentionally implements only the Markdown constructs used by the
whitepaper.  It fails closed when the source warning contract, document ID, or
a Hangul-capable font is unavailable.  The source SHA-256 is embedded in PDF
metadata so ``--check`` can reject an attractive but stale PDF.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

import matplotlib

matplotlib.use("Agg")

from matplotlib import font_manager
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.figure import Figure
from matplotlib.font_manager import FontProperties
from matplotlib.ft2font import FT2Font
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
from matplotlib.textpath import TextToPath


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = REPOSITORY_ROOT / "docs" / "Aegis_Acoustics_B2B_Whitepaper.md"
DEFAULT_OUTPUT = REPOSITORY_ROOT / "docs" / "Aegis_Acoustics_B2B_Whitepaper.pdf"

DOCUMENT_ID_RE = re.compile(r"문서 ID\s+`([^`]+)`")
PDF_PAGE_RE = re.compile(rb"/Type\s*/Page\b")
PDF_METADATA_RE = re.compile(rb"/(Title|Subject|Keywords)\s*\(([^\r\n]*)\)")
SOURCE_SHA_RE = re.compile(rb"source-sha256=([0-9a-f]{64})")
RENDERER_SHA_RE = re.compile(rb"renderer-sha256=([0-9a-f]{64})")
TABLE_SEPARATOR_RE = re.compile(r"^\s*\|?(?:\s*:?-{3,}:?\s*\|)+\s*$")

REQUIRED_SOURCE_WARNINGS = (
    "제품 및 고객 적용 NO-GO",
    "실측 데이터는 0건",
    "근거로 사용할 수 없습니다",
    "현재 0/8 완료",
)
REQUIRED_HANGUL = "한글실측데이터제품고객적용금지"
MINIMUM_PDF_PAGES = 6
MINIMUM_PDF_BYTES = 50_000

PAGE_WIDTH = 595.28
PAGE_HEIGHT = 841.89
LEFT = 48.0
RIGHT = 48.0
TOP = 60.0
BOTTOM = 45.0
CONTENT_WIDTH = PAGE_WIDTH - LEFT - RIGHT

NAVY = "#14263D"
BLUE = "#2867A0"
PALE_BLUE = "#EAF2F8"
RED = "#B4232A"
PALE_RED = "#FCECEE"
INK = "#17202A"
MUTED = "#536273"
LINE = "#CBD4DD"
PAPER = "#FCFCFA"
TABLE_ALT = "#F4F7F9"


class RenderError(RuntimeError):
    """Raised when a trustworthy PDF cannot be produced or verified."""


@dataclass(frozen=True)
class SourceIdentity:
    document_id: str
    sha256: str
    title: str
    status_line: str


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_source_identity(source: Path) -> SourceIdentity:
    text = source.read_text(encoding="utf-8")
    missing = [warning for warning in REQUIRED_SOURCE_WARNINGS if warning not in text]
    if missing:
        raise RenderError(
            "refusing to render: required evidence-boundary language is missing: "
            + ", ".join(missing)
        )
    match = DOCUMENT_ID_RE.search(text)
    if not match:
        raise RenderError("refusing to render: Markdown document ID is missing")
    first_heading = next((line[2:].strip() for line in text.splitlines() if line.startswith("# ")), "")
    if not first_heading:
        raise RenderError("refusing to render: Markdown title is missing")
    status_line = next(
        (line.strip() for line in text.splitlines() if line.startswith("문서 상태:")),
        "문서 상태: 연구 초안",
    )
    # The document ID is already shown on its own cover line.
    status_line = status_line.split("· 문서 ID", 1)[0].strip()
    return SourceIdentity(match.group(1), sha256_file(source), first_heading, status_line)


def _font_supports_hangul(path: Path) -> bool:
    try:
        charmap = FT2Font(str(path)).get_charmap()
    except (OSError, RuntimeError, ValueError):
        return False
    return all(ord(character) in charmap for character in REQUIRED_HANGUL)


def _font_candidates() -> Iterable[Path]:
    explicit = os.environ.get("AEGIS_PDF_FONT")
    if explicit:
        yield Path(explicit)

    known = (
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",
        "/System/Library/Fonts/Supplemental/AppleGothic.ttf",
        "/Library/Fonts/NanumGothic.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJKkr-Regular.otf",
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
        "C:/Windows/Fonts/malgun.ttf",
    )
    for candidate in known:
        yield Path(candidate)

    try:
        discovered = sorted(Path(path) for path in font_manager.findSystemFonts())
    except Exception:  # pragma: no cover - defensive fallback around platform APIs
        discovered = []
    for candidate in discovered:
        yield candidate


def select_korean_font(candidates: Iterable[Path] | None = None) -> Path:
    checked: set[Path] = set()
    for candidate in candidates if candidates is not None else _font_candidates():
        candidate = candidate.expanduser()
        if candidate in checked or not candidate.is_file():
            continue
        checked.add(candidate)
        if _font_supports_hangul(candidate):
            return candidate
    raise RenderError(
        "no Hangul-capable font found; set AEGIS_PDF_FONT to a local Korean font. "
        "PDF generation is stopped to prevent missing-glyph output."
    )


def clean_inline(text: str) -> str:
    text = re.sub(r"!\[([^]]*)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\[([^]]+)\]\([^)]+\)", r"\1", text)
    text = text.replace("**", "").replace("__", "")
    text = text.replace("`", "").replace("*", "")
    return text.strip()


def split_table_row(line: str) -> list[str]:
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [clean_inline(cell.strip()) for cell in stripped.split("|")]


class WhitepaperRenderer:
    def __init__(self, pdf: PdfPages, font_path: Path, identity: SourceIdentity):
        self.pdf = pdf
        self.font_path = font_path
        self.identity = identity
        self.text_to_path = TextToPath()
        self.figure: Figure | None = None
        self.cursor_y = PAGE_HEIGHT - TOP
        self.page_number = 0

    def font(self, size: float, bold: bool = False) -> FontProperties:
        return FontProperties(
            fname=str(self.font_path),
            size=size,
            weight="bold" if bold else "normal",
        )

    def text_width(self, text: str, size: float, bold: bool = False) -> float:
        if not text:
            return 0.0
        width, _, _ = self.text_to_path.get_text_width_height_descent(
            text, self.font(size, bold), ismath=False
        )
        return float(width)

    def wrap(self, text: str, size: float, max_width: float, bold: bool = False) -> list[str]:
        text = re.sub(r"\s+", " ", clean_inline(text)).strip()
        if not text:
            return [""]
        words = text.split(" ")
        lines: list[str] = []
        current = ""
        for word in words:
            proposal = word if not current else f"{current} {word}"
            if self.text_width(proposal, size, bold) <= max_width:
                current = proposal
                continue
            if current:
                lines.append(current)
                current = ""
            if self.text_width(word, size, bold) <= max_width:
                current = word
                continue
            fragment = ""
            for character in word:
                proposal = fragment + character
                if fragment and self.text_width(proposal, size, bold) > max_width:
                    lines.append(fragment)
                    fragment = character
                else:
                    fragment = proposal
            current = fragment
        if current:
            lines.append(current)
        return lines

    def _new_figure(self) -> Figure:
        figure = Figure(figsize=(PAGE_WIDTH / 72.0, PAGE_HEIGHT / 72.0), dpi=100)
        figure.patch.set_facecolor(PAPER)
        return figure

    def _rect(
        self,
        x: float,
        y_top: float,
        width: float,
        height: float,
        facecolor: str,
        edgecolor: str | None = None,
        linewidth: float = 0.0,
    ) -> None:
        assert self.figure is not None
        if x < -0.1 or y_top > PAGE_HEIGHT + 0.1 or x + width > PAGE_WIDTH + 0.1:
            raise RenderError("renderer geometry exceeded page width")
        if y_top - height < -0.1:
            raise RenderError("renderer geometry exceeded page bottom")
        self.figure.add_artist(
            Rectangle(
                (x / PAGE_WIDTH, (y_top - height) / PAGE_HEIGHT),
                width / PAGE_WIDTH,
                height / PAGE_HEIGHT,
                transform=self.figure.transFigure,
                facecolor=facecolor,
                edgecolor=edgecolor or facecolor,
                linewidth=linewidth,
                clip_on=False,
            )
        )

    def _line(self, x1: float, y: float, x2: float, color: str = LINE, width: float = 0.7) -> None:
        assert self.figure is not None
        self.figure.add_artist(
            Line2D(
                [x1 / PAGE_WIDTH, x2 / PAGE_WIDTH],
                [y / PAGE_HEIGHT, y / PAGE_HEIGHT],
                transform=self.figure.transFigure,
                color=color,
                linewidth=width,
                clip_on=False,
            )
        )

    def _text(
        self,
        x: float,
        y_top: float,
        text: str,
        size: float,
        *,
        color: str = INK,
        bold: bool = False,
        align: str = "left",
    ) -> None:
        assert self.figure is not None
        if y_top < 0 or y_top > PAGE_HEIGHT + 0.1:
            raise RenderError("renderer attempted to place text outside page height")
        self.figure.text(
            x / PAGE_WIDTH,
            y_top / PAGE_HEIGHT,
            text,
            fontproperties=self.font(size, bold),
            color=color,
            ha=align,
            va="top",
            transform=self.figure.transFigure,
        )

    def _save_page(self) -> None:
        if self.figure is None:
            return
        self.pdf.savefig(self.figure, bbox_inches=None)
        self.figure.clear()
        self.figure = None

    def new_content_page(self) -> None:
        self._save_page()
        self.page_number += 1
        self.figure = self._new_figure()
        self._text(LEFT, PAGE_HEIGHT - 25, "AEGIS-ACOUSTICS · FEASIBILITY LIMITS", 7.8, color=MUTED, bold=True)
        self._text(PAGE_WIDTH - RIGHT, PAGE_HEIGHT - 25, self.identity.document_id, 6.8, color=MUTED, align="right")
        self._line(LEFT, PAGE_HEIGHT - 39, PAGE_WIDTH - RIGHT)
        self._line(LEFT, 34, PAGE_WIDTH - RIGHT)
        self._text(LEFT, 27, "연구 초안 · 제품 및 고객 적용 NO-GO", 7.0, color=RED, bold=True)
        self._text(PAGE_WIDTH - RIGHT, 27, str(self.page_number), 7.0, color=MUTED, align="right")
        self.cursor_y = PAGE_HEIGHT - TOP

    def ensure(self, height: float) -> bool:
        if self.figure is None:
            self.new_content_page()
            return True
        if self.cursor_y - height >= BOTTOM:
            return False
        self.new_content_page()
        return True

    def render_cover(self) -> None:
        self._save_page()
        self.page_number = 1
        self.figure = self._new_figure()
        self._rect(0, PAGE_HEIGHT, PAGE_WIDTH, 224, NAVY)
        self._text(LEFT, PAGE_HEIGHT - 46, "AEGIS-ACOUSTICS", 11, color="#BFD7EA", bold=True)
        self._text(LEFT, PAGE_HEIGHT - 82, self.identity.title, 23, color="white", bold=True)
        self._text(LEFT, PAGE_HEIGHT - 123, "반도체 대기압 인터페이스용 국소 음장 제어 연구", 12, color="white")
        self._text(LEFT, PAGE_HEIGHT - 166, self.identity.document_id, 8.4, color="#D8E3EC")
        self._text(LEFT, PAGE_HEIGHT - 185, self.identity.status_line, 8.4, color="#D8E3EC")

        self._text(LEFT, PAGE_HEIGHT - 270, "제품 및 고객 적용", 13, color=MUTED, bold=True)
        self._text(LEFT, PAGE_HEIGHT - 297, "NO-GO", 38, color=RED, bold=True)
        self._text(PAGE_WIDTH - RIGHT, PAGE_HEIGHT - 281, "현재 판정", 9, color=MUTED, align="right")
        self._text(PAGE_WIDTH - RIGHT, PAGE_HEIGHT - 301, "축소 벤치 검증 준비만 GO", 11, color=BLUE, bold=True, align="right")

        self._rect(LEFT, PAGE_HEIGHT - 365, CONTENT_WIDTH, 100, PALE_RED, RED, 1.2)
        self._text(LEFT + 16, PAGE_HEIGHT - 381, "Aegis 하드웨어 실측 데이터: 0건", 16, color=RED, bold=True)
        warning = "전기 위상 · 3D 음장 · 입자 침착 저감 · 안전성의 Aegis 하드웨어 측정값이 저장소에 없습니다."
        for index, line in enumerate(self.wrap(warning, 10.2, CONTENT_WIDTH - 32)):
            self._text(LEFT + 16, PAGE_HEIGHT - 414 - index * 15, line, 10.2, color=INK)

        self._rect(LEFT, PAGE_HEIGHT - 491, CONTENT_WIDTH, 145, PALE_BLUE, BLUE, 1.0)
        self._text(LEFT + 16, PAGE_HEIGHT - 507, "의사결정 사용 금지", 14, color=NAVY, bold=True)
        decision_warning = (
            "이 문서는 고객 성능 약속, 제품 사양, 구매·투자, fab 통합, 안전·규제 적합성 또는 "
            "생산 적용 판단의 근거로 사용할 수 없습니다."
        )
        lines = self.wrap(decision_warning, 10.4, CONTENT_WIDTH - 32)
        for index, line in enumerate(lines):
            self._text(LEFT + 16, PAGE_HEIGHT - 538 - index * 15, line, 10.4)
        no_claim = "입증하지 않음: 10–50 nm 차단 · HVAC 대체 · wafer 이송 · 에너지/수율/ROI"
        for index, line in enumerate(self.wrap(no_claim, 9.5, CONTENT_WIDTH - 32, True)):
            self._text(LEFT + 16, PAGE_HEIGHT - 591 - index * 14, line, 9.5, color=RED, bold=True)

        self._text(LEFT, 91, "권위 원본", 8, color=MUTED, bold=True)
        self._text(LEFT, 75, "docs/Aegis_Acoustics_B2B_Whitepaper.md", 8.3, color=INK)
        self._text(LEFT, 57, f"source SHA-256  {self.identity.sha256[:16]}…", 7.3, color=MUTED)
        self._text(PAGE_WIDTH - RIGHT, 57, "PDF revision is cryptographically bound to the source", 7.0, color=MUTED, align="right")

    def render_heading(self, level: int, text: str) -> None:
        if level == 2:
            self.ensure(50)
            self.cursor_y -= 8
            self._text(LEFT, self.cursor_y, text, 16, color=NAVY, bold=True)
            self.cursor_y -= 25
            self._line(LEFT, self.cursor_y + 3, PAGE_WIDTH - RIGHT, color=BLUE, width=1.1)
            self.cursor_y -= 9
        else:
            self.ensure(38)
            self.cursor_y -= 6
            self._text(LEFT, self.cursor_y, text, 12.3, color=BLUE, bold=True)
            self.cursor_y -= 23

    def render_paragraph(self, text: str) -> None:
        lines = self.wrap(text, 9.3, CONTENT_WIDTH)
        for line in lines:
            self.ensure(14.2)
            self._text(LEFT, self.cursor_y, line, 9.3)
            self.cursor_y -= 14.2
        self.cursor_y -= 5

    def render_list_item(self, marker: str, text: str) -> None:
        marker_width = 23.0
        lines = self.wrap(text, 9.1, CONTENT_WIDTH - marker_width)
        required = len(lines) * 13.8 + 3
        self.ensure(required)
        self._text(LEFT, self.cursor_y, marker, 9.1, color=BLUE, bold=True)
        for index, line in enumerate(lines):
            self._text(LEFT + marker_width, self.cursor_y - index * 13.8, line, 9.1)
        self.cursor_y -= required

    def render_quote(self, text: str) -> None:
        lines = self.wrap(text, 9.2, CONTENT_WIDTH - 34)
        height = len(lines) * 14 + 22
        self.ensure(height + 6)
        self._rect(LEFT, self.cursor_y, CONTENT_WIDTH, height, PALE_BLUE, LINE, 0.6)
        self._rect(LEFT, self.cursor_y, 5, height, BLUE)
        for index, line in enumerate(lines):
            self._text(LEFT + 17, self.cursor_y - 11 - index * 14, line, 9.2, color=NAVY)
        self.cursor_y -= height + 8

    def _table_widths(self, count: int) -> list[float]:
        if count == 2:
            ratios = (0.34, 0.66)
        elif count == 3:
            ratios = (0.29, 0.355, 0.355)
        else:
            ratios = tuple(1.0 / count for _ in range(count))
        return [CONTENT_WIDTH * ratio for ratio in ratios]

    def _render_table_row(self, cells: Sequence[str], widths: Sequence[float], header: bool) -> None:
        padding_x = 6.0
        font_size = 8.0 if len(cells) >= 3 else 8.4
        line_height = 11.6
        wrapped = [self.wrap(cell, font_size, width - 2 * padding_x, header) for cell, width in zip(cells, widths)]
        height = max(25.0, max(len(lines) for lines in wrapped) * line_height + 12)
        self.ensure(height)
        x = LEFT
        fill = NAVY if header else (TABLE_ALT if int(self.cursor_y) % 2 else "white")
        for lines, width in zip(wrapped, widths):
            self._rect(x, self.cursor_y, width, height, fill, LINE, 0.45)
            for index, line in enumerate(lines):
                self._text(
                    x + padding_x,
                    self.cursor_y - 6 - index * line_height,
                    line,
                    font_size,
                    color="white" if header else INK,
                    bold=header,
                )
            x += width
        self.cursor_y -= height

    def render_table(self, rows: Sequence[Sequence[str]]) -> None:
        if not rows:
            return
        count = len(rows[0])
        if count < 2 or any(len(row) != count for row in rows):
            raise RenderError("malformed Markdown table")
        widths = self._table_widths(count)
        self.ensure(50)
        self._render_table_row(rows[0], widths, True)
        for row in rows[1:]:
            # Estimate height to detect a page break and repeat the header.
            font_size = 8.0 if count >= 3 else 8.4
            line_count = max(
                len(self.wrap(cell, font_size, width - 12))
                for cell, width in zip(row, widths)
            )
            estimate = max(25.0, line_count * 11.6 + 12)
            if self.cursor_y - estimate < BOTTOM:
                self.new_content_page()
                self._render_table_row(rows[0], widths, True)
            self._render_table_row(row, widths, False)
        self.cursor_y -= 10

    def finish(self) -> int:
        self._save_page()
        return self.page_number


def render_markdown_body(renderer: WhitepaperRenderer, text: str) -> None:
    lines = text.splitlines()
    try:
        start = next(index for index, line in enumerate(lines) if line.startswith("## 1."))
    except StopIteration as exc:
        raise RenderError("refusing to render: numbered whitepaper body is missing") from exc

    index = start
    paragraph: list[str] = []

    def flush_paragraph() -> None:
        if paragraph:
            renderer.render_paragraph(" ".join(paragraph))
            paragraph.clear()

    while index < len(lines):
        raw = lines[index].rstrip()
        stripped = raw.strip()
        if not stripped:
            flush_paragraph()
            index += 1
            continue
        if stripped == "---":
            flush_paragraph()
            renderer.ensure(18)
            renderer._line(LEFT, renderer.cursor_y - 5, PAGE_WIDTH - RIGHT)
            renderer.cursor_y -= 18
            index += 1
            continue
        heading = re.match(r"^(#{2,3})\s+(.+)$", stripped)
        if heading:
            flush_paragraph()
            renderer.render_heading(len(heading.group(1)), clean_inline(heading.group(2)))
            index += 1
            continue
        if stripped.startswith("|") and index + 1 < len(lines) and TABLE_SEPARATOR_RE.match(lines[index + 1]):
            flush_paragraph()
            rows = [split_table_row(stripped)]
            index += 2
            while index < len(lines) and lines[index].strip().startswith("|"):
                rows.append(split_table_row(lines[index]))
                index += 1
            renderer.render_table(rows)
            continue
        if stripped.startswith(">"):
            flush_paragraph()
            quote: list[str] = []
            while index < len(lines) and lines[index].strip().startswith(">"):
                content = lines[index].strip()[1:].strip()
                if content:
                    quote.append(content)
                index += 1
            renderer.render_quote(" ".join(quote))
            continue
        item = re.match(r"^([-*]|\d+\.)\s+(.+)$", stripped)
        if item:
            flush_paragraph()
            marker = "•" if item.group(1) in {"-", "*"} else item.group(1)
            renderer.render_list_item(marker, item.group(2))
            index += 1
            continue
        paragraph.append(stripped)
        index += 1
    flush_paragraph()


def metadata_for(identity: SourceIdentity, source: Path) -> dict[str, object]:
    prefix = f"{identity.document_id} | PRODUCT NO-GO"
    timestamp = datetime.fromtimestamp(source.stat().st_mtime, tz=timezone.utc)
    renderer_sha256 = sha256_file(Path(__file__).resolve())
    return {
        "Title": f"{prefix} | Aegis-Acoustics Feasibility Whitepaper",
        "Author": "Aegis-Acoustics R&D Project",
        "Subject": (
            f"{prefix} | HARDWARE MEASUREMENTS 0 | "
            f"source-sha256={identity.sha256} | renderer-sha256={renderer_sha256}"
        ),
        "Keywords": f"{prefix}; HARDWARE DATA 0; LIMITATIONS; RESEARCH DRAFT",
        "CreationDate": timestamp,
        "ModDate": timestamp,
    }


def render_pdf(source: Path, output: Path, font_path: Path | None = None) -> tuple[int, Path]:
    identity = parse_source_identity(source)
    selected_font = font_path or select_korean_font()
    if not _font_supports_hangul(selected_font):
        raise RenderError(f"selected font does not contain required Hangul glyphs: {selected_font}")

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + ".tmp")
    try:
        with PdfPages(temporary, metadata=metadata_for(identity, source)) as pdf:
            renderer = WhitepaperRenderer(pdf, selected_font, identity)
            renderer.render_cover()
            renderer.new_content_page()
            render_markdown_body(renderer, source.read_text(encoding="utf-8"))
            pages = renderer.finish()
        temporary.replace(output)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise

    check_pdf(source, output)
    return pages, selected_font


def read_ascii_metadata(pdf_bytes: bytes) -> dict[str, str]:
    values: dict[str, str] = {}
    for match in PDF_METADATA_RE.finditer(pdf_bytes):
        values[match.group(1).decode("ascii")] = match.group(2).decode("ascii", errors="strict")
    return values


def check_pdf(source: Path, output: Path) -> int:
    identity = parse_source_identity(source)
    try:
        pdf_bytes = output.read_bytes()
    except FileNotFoundError as exc:
        raise RenderError(f"PDF does not exist: {output}") from exc
    if not pdf_bytes.startswith(b"%PDF-") or b"%%EOF" not in pdf_bytes[-1024:]:
        raise RenderError("output is not a complete PDF")
    if len(pdf_bytes) < MINIMUM_PDF_BYTES:
        raise RenderError(f"PDF is unexpectedly small: {len(pdf_bytes)} bytes")

    pages = len(PDF_PAGE_RE.findall(pdf_bytes))
    if pages < MINIMUM_PDF_PAGES:
        raise RenderError(f"PDF has only {pages} pages; expected at least {MINIMUM_PDF_PAGES}")

    metadata = read_ascii_metadata(pdf_bytes)
    for key in ("Title", "Subject", "Keywords"):
        value = metadata.get(key, "")
        if identity.document_id not in value or "NO-GO" not in value:
            raise RenderError(f"PDF {key} metadata is missing the current document ID or NO-GO")
    subject_hash = SOURCE_SHA_RE.search(metadata.get("Subject", "").encode("ascii"))
    if not subject_hash or subject_hash.group(1).decode("ascii") != identity.sha256:
        raise RenderError("PDF is stale: embedded source SHA-256 does not match Markdown")
    renderer_hash = RENDERER_SHA_RE.search(
        metadata.get("Subject", "").encode("ascii")
    )
    current_renderer_sha256 = sha256_file(Path(__file__).resolve())
    if (
        not renderer_hash
        or renderer_hash.group(1).decode("ascii") != current_renderer_sha256
    ):
        raise RenderError(
            "PDF is stale: embedded renderer SHA-256 does not match the current renderer"
        )
    if "HARDWARE MEASUREMENTS 0" not in metadata.get("Subject", ""):
        raise RenderError("PDF Subject metadata is missing the zero-hardware-data boundary")
    return pages


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--font", type=Path, help="explicit Hangul-capable TTF/OTF/TTC")
    parser.add_argument("--check", action="store_true", help="verify the existing PDF without rendering")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.check:
            pages = check_pdf(args.source, args.output)
            print(f"PASS: {args.output} matches {args.source} ({pages} pages)")
        else:
            pages, font = render_pdf(args.source, args.output, args.font)
            size = args.output.stat().st_size
            print(f"WROTE: {args.output} ({pages} pages, {size} bytes, font={font})")
    except (OSError, RenderError, UnicodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
