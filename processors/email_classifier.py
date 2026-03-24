"""
Email classifier for detecting promotional/marketing emails.
Uses both heuristic analysis and LLM-based classification.
"""
import re
from typing import List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from config.settings import Settings
from core.email_service import Email
from core.llm_service import LLMService, ClassificationResult


@dataclass
class ClassificationScore:
    """Classification scoring details."""
    is_promotional: bool
    confidence: float
    score: float  # -1 (promotional) to 1 (important)
    indicators: List[str]


class EmailClassifier:
    """
    Classifies emails as promotional/marketing or important.
    Uses multiple detection methods and can fall back to heuristics.
    """

    # Marketing keyword patterns
    MARKETING_KEYWORDS = [
        r"sale", r"discount", r"promo", r"coupon", r"offer",
        r"limited time", r"act now", r"don't miss", r"subscribe",
        r"unsubscribe", r"newsletter", r"announcement", r"update"
    ]

    # Marketing sender patterns
    MARKETING_DOMAINS = [
        r"noreply", r"no-reply", r"notifications?@", r"mailer@",
        r"newsletter@", r"deals@", r"offers@"
    ]

    # HTML density threshold for spam detection
    HTML_DENSITY_THRESHOLD = 0.7

    # Marketing HTML patterns
    MARKETING_HTML_TAGS = [
        r"unsubscribe", r"preferences?", r"newsletter",
        r"marketing", r"promotional", r"shop now", r"buy now"
    ]

    def __init__(self, settings: Settings, llm_service: Optional[LLMService] = None):
        """
        Initialize classifier.

        Args:
            settings: Application settings
            llm_service: Optional LLM service for AI-based classification
        """
        self.settings = settings
        self.llm_service = llm_service
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """Compile regex patterns for efficiency."""
        self.marketing_keywords = [
            re.compile(p, re.IGNORECASE) for p in self.MARKETING_KEYWORDS
        ]
        self.marketing_domains = [
            re.compile(p, re.IGNORECASE) for p in self.MARKETING_DOMAINS
        ]
        self.marketing_html = [
            re.compile(p, re.IGNORECASE) for p in self.MARKETING_HTML_TAGS
        ]

    async def classify(
        self,
        email: Email,
        force_llm: bool = False
    ) -> Tuple[ClassificationResult, ClassificationScore]:
        """
        Classify an email.

        Args:
            email: Email to classify
            force_llm: Whether to force LLM classification

        Returns:
            Tuple of (ClassificationResult, ClassificationScore)
        """
        # First, try heuristic-based classification (fast)
        heuristic_score = self._heuristic_classify(email)

        # If heuristic confidence is high, use it
        if heuristic_score.confidence > 0.7 or force_llm:
            return heuristic_score, heuristic_score
        elif self.llm_service:
            # Otherwise, use LLM for borderline cases
            llm_result, llm_reasoning = await self.llm_service.classify_email(
                email,
                context=self._build_context(email, heuristic_score)
            )

            if llm_reasoning:
                return llm_result, heuristic_score
            else:
                return heuristic_score, heuristic_score
        else:
            return heuristic_score, heuristic_score

    def _heuristic_classify(self, email: Email) -> ClassificationScore:
        """
        Classify email using heuristics.

        Args:
            email: Email to classify

        Returns:
            ClassificationScore with confidence and indicators
        """
        score = 0.0
        indicators: List[str] = []

        text = (email.subject + " " + (email.body or "")).lower()

        # Check marketing keywords
        keyword_count = 0
        for pattern in self.marketing_keywords:
            if pattern.search(text):
                keyword_count += 1
                indicators.append(f"marketing keyword: {pattern.pattern}")

        if keyword_count >= 3:
            score -= 0.8
        elif keyword_count >= 2:
            score -= 0.5
        elif keyword_count >= 1:
            score -= 0.2

        # Check sender domain
        sender_lower = email.from_addr.lower()
        for pattern in self.marketing_domains:
            if pattern.search(sender_lower):
                score -= 0.3
                indicators.append(f"suspicious domain pattern: {pattern.pattern}")
                break

        # Check HTML content
        if email.body_html:
            html_density = self._calculate_html_density(email.body_html)
            if html_density > self.HTML_DENSITY_THRESHOLD:
                score -= 0.3
                indicators.append("high HTML density")

            for pattern in self.marketing_html:
                if pattern.search(email.body_html):
                    score -= 0.2
                    indicators.append(f"marketing HTML pattern: {pattern.pattern}")

        # Check if email has multiple recipients (newsletter pattern)
        if "mailto:" in (email.body or "") or "cc:" in (email.body or ""):
            score -= 0.1
            indicators.append("appears to be bulk email")

        # Normalize score to -1 to 1 range
        score = max(-1.0, min(1.0, score))

        # Calculate confidence
        confidence = abs(score)

        is_promotional = score < -0.1

        return ClassificationScore(
            is_promotional=is_promotional,
            confidence=confidence,
            score=score,
            indicators=indicators
        )

    def _calculate_html_density(self, html: str) -> float:
        """
        Calculate the ratio of HTML tags to text content.

        Args:
            html: HTML content

        Returns:
            Ratio of HTML to text (0.0 to 1.0)
        """
        # Remove HTML tags to get text content
        text_content = re.sub(r"<[^>]+>", " ", html)
        text_length = len(text_content.strip())
        html_length = len(html)

        if text_length == 0:
            return 1.0 if html_length > 0 else 0.0

        # Ratio of tag characters to total
        tag_length = html_length - text_length
        return tag_length / html_length if html_length > 0 else 0.0

    def _build_context(
        self,
        email: Email,
        heuristic_score: ClassificationScore
    ) -> str:
        """
        Build context for LLM classification.

        Args:
            email: Email being classified
            heuristic_score: Heuristic classification result

        Returns:
            Context string for LLM
        """
        context_parts = []

        if heuristic_score.indicators:
            context_parts.append(
                f"Heuristic indicators: {', '.join(heuristic_score.indicators)}"
            )

        context_parts.append(
            f"Heuristic confidence: {heuristic_score.confidence:.2f}"
        )

        return "\n".join(context_parts)

    def is_marketing_email(self, email: Email) -> bool:
        """
        Quick check if email appears to be marketing.

        Args:
            email: Email to check

        Returns:
            True if likely marketing/promotional
        """
        score = self._heuristic_classify(email)
        return score.is_promotional and score.confidence > 0.5

    def get_classification_reasoning(
        self,
        email: Email,
        score: ClassificationScore
    ) -> str:
        """
        Get human-readable classification reasoning.

        Args:
            email: Email that was classified
            score: Classification score

        Returns:
            Reasoning string
        """
        if score.is_promotional:
            reasons = []
            if score.indicators:
                reasons.append(f"detected: {', '.join(score.indicators[:3])}")
            reasons.append(f"confidence: {score.confidence:.0%}")
            return f"Promotional email ({', '.join(reasons)})"
        else:
            return f"Important email (confidence: {score.confidence:.0%})"
