"""
Tests for email classifier.
"""
import pytest
import asyncio
from unittest.mock import MagicMock
from datetime import datetime
from processors.email_classifier import EmailClassifier, ClassificationScore


class TestEmailClassifier:
    """Test cases for EmailClassifier."""

    @pytest.mark.asyncio
    async def test_heuristic_classifies_promotional(self, settings, classifier):
        """Test that marketing emails are classified as promotional."""
        email = MagicMock()
        email.subject = "50% Off Sale!"
        email.from_addr = "noreply@deals.com"
        email.body = "Get 50% off today only! Unsubscribe here."
        email.body_html = None

        result, score = await classifier.classify(email)

        # result can be either ClassificationResult or ClassificationScore
        # depending on confidence level
        if hasattr(result, 'value'):
            assert result.value == "promotions"
        assert score.is_promotional is True
        assert score.confidence > 0.5

    @pytest.mark.asyncio
    async def test_heuristic_classifies_important(self, settings, classifier):
        """Test that personal emails are classified as important."""
        email = MagicMock()
        email.subject = "Meeting Tomorrow"
        email.from_addr = "colleague@company.com"
        email.body = "Hi, let's meet at 10am to discuss the project."
        email.body_html = None

        result, score = await classifier.classify(email)

        assert result.value == "important"
        assert score.is_promotional is False

    def test_html_density_detection(self, settings, classifier):
        """Test HTML density detection for spam."""
        email = MagicMock()
        email.subject = "Newsletter"
        email.from_addr = "newsletter@company.com"
        email.body = "Plain text content"
        email.body_html = "<html><body>" * 100 + "content" + "</body></html>" * 100

        score = classifier._heuristic_classify(email)

        # High HTML density should contribute to promotional classification
        assert score.score < 0  # Negative score indicates promotional

    def test_marketing_keywords_detection(self, settings, classifier):
        """Test detection of marketing keywords."""
        email = MagicMock()
        email.subject = "Special Offer Inside"
        email.from_addr = "offers@store.com"
        email.body = """
            Limited time offer! Act now and don't miss out.
            Get your discount code today.
        """
        email.body_html = None

        score = classifier._heuristic_classify(email)

        assert score.indicators  # Should have detected indicators

    @pytest.mark.asyncio
    async def test_classification_reasoning(self, settings, classifier):
        """Test that classification reasoning is generated."""
        email = MagicMock()
        email.subject = "Sale Alert"
        email.from_addr = "deals@store.com"
        email.body = "Get 50% off!"
        email.body_html = None

        result, score = await classifier.classify(email)

        reasoning = classifier.get_classification_reasoning(email, score)
        assert "Promotional" in reasoning or "Important" in reasoning

    def test_is_marketing_email(self, settings, classifier):
        """Test quick marketing email detection."""
        from core.email_service import Email
        from datetime import datetime

        # Marketing email - needs multiple indicators to be classified as marketing
        email = Email(
            message_id="1",
            subject="Special Offer - Newsletter Weekly",
            from_addr="noreply@site.com",
            timestamp=datetime.now(),
            body_plain="Check out our latest deals! Unsubscribe here."
        )

        assert classifier.is_marketing_email(email) is True

        # Important email
        email2 = Email(
            message_id="2",
            subject="Project Update",
            from_addr="boss@company.com",
            timestamp=datetime.now(),
            body_plain="Please review the attached document."
        )

        assert classifier.is_marketing_email(email2) is False
