import os
import asyncio
from typing import Optional

IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp", ".gif")
EXCEL_EXTENSIONS = (".xlsx", ".xlsm", ".xls")


class DocumentProcessor:
    """Process documents into chunks for indexing.

    Tracks whether OCR was used for the most recent `process()` call via
    `self.last_used_ocr`, so callers can persist that on the Document row.
    """

    CHUNK_SIZE = 1000
    CHUNK_OVERLAP = 200

    def __init__(self):
        self.last_used_ocr = False

    async def process(self, file_path: str, mime_type: str) -> list[dict]:
        self.last_used_ocr = False
        if not os.path.exists(file_path):
            return []

        lower_path = file_path.lower()

        if mime_type == "application/pdf" or lower_path.endswith(".pdf"):
            return await self._process_pdf(file_path)
        elif mime_type in ("text/plain", "text/markdown") and not lower_path.endswith(EXCEL_EXTENSIONS):
            return await self._process_text(file_path)
        elif mime_type in ("application/vnd.openxmlformats-officedocument.wordprocessingml.document",) \
                or lower_path.endswith(".docx"):
            return await self._process_docx(file_path)
        elif mime_type in (
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "application/vnd.ms-powerpoint",
        ) or lower_path.endswith((".pptx", ".ppt")):
            return await self._process_pptx(file_path)
        elif mime_type in (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/vnd.ms-excel",
        ) or lower_path.endswith(EXCEL_EXTENSIONS):
            return await self._process_xlsx(file_path)
        elif mime_type.startswith("image/") or lower_path.endswith(IMAGE_EXTENSIONS):
            # Covers photos, scanned pages, handwritten notes, and
            # engineering drawings - all routed through OCR.
            return await self._process_image(file_path)
        else:
            return await self._process_text(file_path)

    async def _process_pdf(self, file_path: str) -> list[dict]:
        try:
            from pypdf import PdfReader
            reader = PdfReader(file_path)
            chunks = []
            for page_num, page in enumerate(reader.pages, 1):
                text = page.extract_text() or ""
                if not text.strip():
                    # Attempt OCR for scanned pages
                    text = await self._ocr_page(file_path, page_num)
                    if text.strip():
                        self.last_used_ocr = True
                page_chunks = self._chunk_text(text, page_number=page_num)
                chunks.extend(page_chunks)
            return chunks
        except Exception as e:
            return [{"content": f"Error processing PDF: {str(e)}", "page_number": 1}]

    async def _process_docx(self, file_path: str) -> list[dict]:
        try:
            from docx import Document
            doc = Document(file_path)
            full_text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
            return self._chunk_text(full_text)
        except Exception as e:
            return [{"content": f"Error processing DOCX: {str(e)}"}]

    async def _process_pptx(self, file_path: str) -> list[dict]:
        try:
            from pptx import Presentation
            prs = Presentation(file_path)
            chunks = []
            for slide_num, slide in enumerate(prs.slides, 1):
                texts = []
                for shape in slide.shapes:
                    if shape.has_text_frame:
                        for para in shape.text_frame.paragraphs:
                            text = "".join(run.text for run in para.runs)
                            if text.strip():
                                texts.append(text)
                    if shape.has_table:
                        for row in shape.table.rows:
                            row_text = " | ".join(cell.text for cell in row.cells if cell.text)
                            if row_text.strip():
                                texts.append(row_text)
                    if shape.shape_type == 19:  # placeholder catch-all fallback
                        pass
                if slide.has_notes_slide and slide.notes_slide.notes_text_frame:
                    notes = slide.notes_slide.notes_text_frame.text
                    if notes.strip():
                        texts.append(f"Speaker notes: {notes}")

                slide_text = "\n".join(texts)
                if slide_text.strip():
                    chunks.extend(self._chunk_text(slide_text, page_number=slide_num))
            return chunks
        except Exception as e:
            return [{"content": f"Error processing PPTX: {str(e)}", "page_number": 1}]

    async def _process_xlsx(self, file_path: str) -> list[dict]:
        try:
            from openpyxl import load_workbook
            wb = load_workbook(file_path, data_only=True, read_only=True)
            chunks = []
            for sheet_index, sheet in enumerate(wb.worksheets, 1):
                rows_text = []
                for row in sheet.iter_rows(values_only=True):
                    cells = ["" if c is None else str(c) for c in row]
                    if any(cell.strip() for cell in cells):
                        rows_text.append(" | ".join(cells))
                sheet_text = "\n".join(rows_text)
                if sheet_text.strip():
                    sheet_header = f"Sheet: {sheet.title}\n"
                    chunks.extend(self._chunk_text(sheet_header + sheet_text, page_number=sheet_index))
            return chunks
        except Exception as e:
            return [{"content": f"Error processing spreadsheet: {str(e)}", "page_number": 1}]

    async def _process_image(self, file_path: str) -> list[dict]:
        """OCR a standalone image - photos, handwritten notes, engineering
        drawings, or scans - into indexable text."""
        try:
            import pytesseract
            from PIL import Image

            with Image.open(file_path) as img:
                # Upscale small images a bit; helps OCR accuracy on dense
                # engineering drawings and faint handwriting.
                if img.width < 1000:
                    scale = 1000 / img.width
                    img = img.resize((int(img.width * scale), int(img.height * scale)))
                if img.mode not in ("L", "RGB"):
                    img = img.convert("RGB")
                # pytesseract.image_to_string shells out to the tesseract
                # binary and blocks synchronously until it returns. Called
                # directly inside this async method, it froze the entire
                # event loop for the whole OCR duration - every other
                # request (including unrelated users' logins/queries) would
                # just hang with no response until OCR finished. Running it
                # in a worker thread keeps the event loop free.
                text = await asyncio.to_thread(pytesseract.image_to_string, img)

            self.last_used_ocr = True
            if not text.strip():
                return [{
                    "content": "[Image contains no machine-readable text, or handwriting/diagram "
                               "could not be recognized by OCR.]",
                    "page_number": 1,
                }]
            return self._chunk_text(text, page_number=1)
        except Exception as e:
            return [{"content": f"Error processing image (OCR): {str(e)}", "page_number": 1}]

    async def _process_text(self, file_path: str) -> list[dict]:
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
            return self._chunk_text(text)
        except Exception as e:
            return [{"content": f"Error processing text: {str(e)}"}]

    async def _ocr_page(self, file_path: str, page_num: int) -> str:
        """OCR a specific page from a PDF."""
        try:
            import pytesseract
            from PIL import Image
            from pypdf import PdfReader
            import io

            # Simple text extraction fallback
            reader = PdfReader(file_path)
            if page_num <= len(reader.pages):
                page = reader.pages[page_num - 1]
                for image in page.images:
                    img = Image.open(io.BytesIO(image.data))
                    text = await asyncio.to_thread(pytesseract.image_to_string, img)
                    if text.strip():
                        return text
            return ""
        except Exception:
            return ""

    def _chunk_text(self, text: str, page_number: Optional[int] = None) -> list[dict]:
        if not text.strip():
            return []

        chunks = []
        words = text.split()
        current_chunk = []
        current_length = 0

        for word in words:
            current_chunk.append(word)
            current_length += len(word) + 1

            if current_length >= self.CHUNK_SIZE:
                chunk_text = " ".join(current_chunk)
                chunks.append({
                    "content": chunk_text,
                    "page_number": page_number,
                    "metadata": {"char_count": len(chunk_text)},
                })
                # Keep overlap
                overlap_words = current_chunk[-20:]
                current_chunk = overlap_words
                current_length = sum(len(w) + 1 for w in current_chunk)

        if current_chunk:
            chunk_text = " ".join(current_chunk)
            # Keep any non-trivial remainder, even if short - a 50-char
            # cutoff was dropping whole short documents (a single-line
            # handwritten note, a small spreadsheet, a short scan) when
            # they didn't reach the chunk size threshold at all.
            if chunk_text.strip():
                chunks.append({
                    "content": chunk_text,
                    "page_number": page_number,
                    "metadata": {"char_count": len(chunk_text)},
                })

        return chunks
