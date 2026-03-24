"""
Tests for email classifier.
"""
import pytest
from processors.email_classifier import EmailClassifier, ClassificationScore


class TestEmailClassifier:
    """Test cases for EmailClassifier."""

    def test_heuristic_classifies_promotional(self, settings, classifier):
        """Test that marketing emails are classified as promotional."""
        from datetime import datetime
        email = MagicMock()
        email.subject = "50% Off Sale!"
        email.from_addr = "noreply@deals.com"
        email.body = "Get 50% off today only! Unsubscribe here."
        email.body_html = None

        result, score = classifier.classify(email)

        assert result.value == "promotions"
        assert score.is_promotional is True
        assert score.confidence > 0.5

    def test_heuristic_classifies_important(self, settings, classifier):
        """Test that personal emails are classified as important."""
        from datetime import datetime
        email = MagicMock()
        email.subject = "Meeting Tomorrow"
        email.from_addr = "colleague@company.com"
        email.body = "Hi, let's meet at 10am to discuss the project."
        email.body_html = None

        result, score = classifier.classify(email)

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

    def test_classification_reasoning(self, settings, classifier):
        """Test that classification reasoning is generated."""
        email = MagicMock()
        email.subject = "Sale Alert"
        email.from_addr = "deals@store.com"
        email.body = "Get 50% off!"
        email.body_html = None

        result, score = classifier.classify(email)

        reasoning = classifier.get_classification_reasoning(email, score)
        assert "Promotional" in reasoning or "Important" in reasoning

    def test_is_marketing_email(self, settings, classifier):
        """Test quick marketing email detection."""
        email = MagicMock()
        email.subject = "Newsletter Weekly"
        email.from_addr = "newsletter@site.com"
        email.body = "Check out our latest deals!"
        email.body_html = None

        assert classifier.is_marketing_email(email) is True

        # Important email
        email.subject = "Project Update"
        email.from_addr = "boss@company.com"
        email.body = "Please review the attached document."

        assert classifier.is_marketing_email(email) is False
