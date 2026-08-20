"""Regression checks for the generated, source-bound whitepaper PDF."""

import hashlib
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
TOOLS = REPOSITORY_ROOT / "tools"
SOURCE = REPOSITORY_ROOT / "docs" / "Aegis_Acoustics_B2B_Whitepaper.md"
PDF = REPOSITORY_ROOT / "docs" / "Aegis_Acoustics_B2B_Whitepaper.pdf"

import sys

sys.path.insert(0, str(TOOLS))
import render_whitepaper_pdf as renderer  # noqa: E402


class WhitepaperPdfTests(unittest.TestCase):
    def test_shipped_pdf_is_current_complete_and_multipage(self):
        pages = renderer.check_pdf(SOURCE, PDF)
        self.assertGreaterEqual(pages, renderer.MINIMUM_PDF_PAGES)
        self.assertGreaterEqual(PDF.stat().st_size, renderer.MINIMUM_PDF_BYTES)

    def test_metadata_repeats_document_id_and_no_go(self):
        identity = renderer.parse_source_identity(SOURCE)
        metadata = renderer.read_ascii_metadata(PDF.read_bytes())
        for key in ("Title", "Subject", "Keywords"):
            with self.subTest(key=key):
                self.assertIn(identity.document_id, metadata[key])
                self.assertIn("NO-GO", metadata[key])
        self.assertIn("HARDWARE MEASUREMENTS 0", metadata["Subject"])
        self.assertIn(f"source-sha256={identity.sha256}", metadata["Subject"])
        renderer_sha256 = hashlib.sha256(
            Path(renderer.__file__).resolve().read_bytes()
        ).hexdigest()
        self.assertIn(
            f"renderer-sha256={renderer_sha256}", metadata["Subject"]
        )

    def test_pdf_uses_a4_pages(self):
        content = PDF.read_bytes()
        self.assertIn(b"/MediaBox [ 0 0 595.28 841.89 ]", content)

    def test_checker_rejects_even_a_small_source_change(self):
        with tempfile.TemporaryDirectory() as directory:
            changed = Path(directory) / "whitepaper.md"
            changed.write_text(SOURCE.read_text(encoding="utf-8") + "\n", encoding="utf-8")
            self.assertNotEqual(
                hashlib.sha256(changed.read_bytes()).hexdigest(),
                renderer.parse_source_identity(SOURCE).sha256,
            )
            with self.assertRaisesRegex(renderer.RenderError, "stale"):
                renderer.check_pdf(changed, PDF)

    def test_font_selection_fails_closed_without_hangul_glyphs(self):
        with tempfile.TemporaryDirectory() as directory:
            invalid_font = Path(directory) / "not-a-font.ttf"
            invalid_font.write_bytes(b"not a font")
            with self.assertRaisesRegex(renderer.RenderError, "Hangul-capable"):
                renderer.select_korean_font([invalid_font])


if __name__ == "__main__":
    unittest.main()
