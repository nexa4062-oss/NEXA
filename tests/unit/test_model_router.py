import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

import pytest
from routing.service import ModelRouter


class TestTaskClassification:
    def setup_method(self):
        self.router = ModelRouter()

    def test_classifies_coding_request(self):
        assert self.router.classify_task("Write a Python function to sort a list") == "coding"

    def test_classifies_vision_request_from_attachment(self):
        attachments = [{"mime_type": "image/png", "filename": "diagram.png"}]
        assert self.router.classify_task("What is in this image?", attachments) == "vision"

    def test_classifies_document_request(self):
        assert self.router.classify_task("Summarize this inspection report") == "document_reasoning"

    def test_classifies_general_reasoning(self):
        assert self.router.classify_task("Explain the difference between TCP and UDP protocols") == "general_reasoning"

    def test_classifies_short_message_as_fast_chat(self):
        assert self.router.classify_task("hello") == "fast_chat"

    def test_classifies_pdf_attachment_as_document(self):
        attachments = [{"mime_type": "application/pdf", "filename": "report.pdf"}]
        assert self.router.classify_task("Read this", attachments) == "document_reasoning"


class TestModelRouting:
    def setup_method(self):
        self.router = ModelRouter()

    @pytest.mark.asyncio
    async def test_routes_to_available_model(self):
        result = await self.router.route_request("What is 2+2?")
        # Should return a model_id (either found or None if Ollama unavailable)
        assert "model_id" in result
        assert "task_type" in result

    @pytest.mark.asyncio
    async def test_includes_fallback(self):
        result = await self.router.route_request("Write Python code")
        assert "fallback" in result

    @pytest.mark.asyncio
    async def test_respects_mode(self):
        result = await self.router.route_request("Hello", mode="fast")
        assert result.get("mode") == "fast"
