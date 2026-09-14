import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

import pytest
import tempfile
from generation.service import FileGenerator

# Override generated dir for tests
os.environ.setdefault("GENERATED_DIR", tempfile.mkdtemp())


class TestFileGeneration:
    def setup_method(self):
        self.generator = FileGenerator()
        # Override output dir
        import config
        config.get_settings.cache_clear()

    @pytest.mark.asyncio
    async def test_generate_docx(self):
        filepath = await self.generator._generate_docx(
            "Test Report", "This is test content.\nLine 2.", "test1", "20240101_000000", "INTERNAL"
        )
        assert filepath.endswith(".docx")
        assert os.path.exists(filepath)
        assert os.path.getsize(filepath) > 0
        os.unlink(filepath)

    @pytest.mark.asyncio
    async def test_generate_pptx(self):
        filepath = await self.generator._generate_pptx(
            "Test Presentation", "Slide 1 content\nSlide 2 content", "test2", "20240101_000000", "INTERNAL"
        )
        assert filepath.endswith(".pptx")
        assert os.path.exists(filepath)
        assert os.path.getsize(filepath) > 0
        os.unlink(filepath)

    @pytest.mark.asyncio
    async def test_generate_xlsx(self):
        filepath = await self.generator._generate_xlsx(
            "Test Spreadsheet", "A,B,C\n1,2,3\n4,5,6", "test3", "20240101_000000", "INTERNAL"
        )
        assert filepath.endswith(".xlsx")
        assert os.path.exists(filepath)
        assert os.path.getsize(filepath) > 0
        os.unlink(filepath)

    @pytest.mark.asyncio
    async def test_generate_pdf(self):
        filepath = await self.generator._generate_pdf(
            "Test PDF", "This is test content for the PDF.\nAnother line.", "test4", "20240101_000000", "CONFIDENTIAL"
        )
        assert filepath.endswith(".pdf")
        assert os.path.exists(filepath)
        assert os.path.getsize(filepath) > 0
        os.unlink(filepath)

    @pytest.mark.asyncio
    async def test_docx_is_valid(self):
        filepath = await self.generator._generate_docx(
            "Validation Test", "Content here", "test5", "20240101_000000", "INTERNAL"
        )
        # Verify the file can be opened by python-docx
        from docx import Document
        doc = Document(filepath)
        assert len(doc.paragraphs) > 0
        os.unlink(filepath)

    @pytest.mark.asyncio
    async def test_pdf_is_valid(self):
        filepath = await self.generator._generate_pdf(
            "PDF Validation", "Content for validation", "test6", "20240101_000000", "INTERNAL"
        )
        # Verify the file can be read by pypdf
        from pypdf import PdfReader
        reader = PdfReader(filepath)
        assert len(reader.pages) > 0
        os.unlink(filepath)
