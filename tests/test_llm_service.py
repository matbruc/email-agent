"""
Tests for LLM service.
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from core.llm_service import LLMService, ClassificationResult, LLMResponse


class TestLLMService:
    """Test cases for LLMService."""

    def test_build_classification_prompt(self, settings, llm_service):
        """Test classification prompt generation."""
        email = MagicMock()
        email.subject = "Test Subject"
        email.from_addr = "test@example.com"
        email.body = "Test body content"

        prompt = llm_service._build_classification_prompt(email, None)

        assert "Test Subject" in prompt
        assert "test@example.com" in prompt
        assert "Test body content" in prompt
        assert "PROMOTIONS" in prompt
        assert "IMPORTANT" in prompt

    def test_build_summarization_prompt(self, settings, llm_service):
        """Test summarization prompt generation."""
        email = MagicMock()
        email.subject = "Meeting Notes"
        email.from_addr = "colleague@example.com"
        email.body = "Discussion points: Q4 goals, budget review"

        prompt = llm_service._build_summarization_prompt(email, None)

        assert "Meeting Notes" in prompt
        assert "Q4 goals" in prompt
        assert "summary" in prompt.lower()

    def test_parse_classification_response_promotions(self, settings, llm_service):
        """Test parsing promotions classification."""
        response = "PROMOTIONS\nThis is clearly a marketing email with sale keywords."

        result, reasoning = llm_service._parse_classification_response(response)

        assert result == ClassificationResult.PROMOTIONS
        assert "marketing" in reasoning.lower()

    def test_parse_classification_response_important(self, settings, llm_service):
        """Test parsing important classification."""
        response = "IMPORTANT\nThis is a personal email from a colleague."

        result, reasoning = llm_service._parse_classification_response(response)

        assert result == ClassificationResult.IMPORTANT
        assert "personal" in reasoning.lower()

    def test_heuristic_classification_promotional(self, settings, llm_service):
        """Test heuristic-based promotional classification."""
        email = MagicMock()
        email.subject = "50% Off Today!"
        email.from_addr = "noreply@deals.com"
        email.body = "Don't miss out on this limited time offer!"

        result = llm_service._heuristic_classification(email)

        assert result == ClassificationResult.PROMOTIONS

    def test_heuristic_classification_important(self, settings, llm_service):
        """Test heuristic-based important classification."""
        email = MagicMock()
        email.subject = "Project Deadline"
        email.from_addr = "manager@company.com"
        email.body = "Please submit your report by Friday."

        result = llm_service._heuristic_classification(email)

        assert result == ClassificationResult.IMPORTANT

    def test_heuristic_summary(self, settings, llm_service):
        """Test heuristic summary generation."""
        email = MagicMock()
        email.subject = "Test Email"
        email.from_addr = "test@example.com"
        email.body = "This is the body content of the email."

        summary = llm_service._heuristic_summary(email)

        assert "test@example.com" in summary
        assert "Test Email" in summary
        assert "This is the body content" in summary

    @pytest.mark.asyncio
    async def test_call_llm_timeout(self, settings, llm_service):
        """Test LLM call timeout handling."""
        with patch("requests.post") as mock_post:
            from requests.exceptions import Timeout
            mock_post.side_effect = Timeout("Request timed out")

            with pytest.raises(Exception):  # requests.exceptions.RequestException
                await llm_service.summarize_email(MagicMock())
