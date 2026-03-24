"""
Local LLM service for email classification and summarization.
Wraps llama.cpp HTTP API for inference.
"""
import json
import time
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass
from enum import Enum

import requests

from config.settings import Settings
from core.email_service import Email


class ClassificationResult(Enum):
    """Email classification results."""
    PROMOTIONS = "promotions"
    IMPORTANT = "important"
    UNCERTAIN = "uncertain"


@dataclass
class LLMResponse:
    """Represents an LLM API response."""
    content: str
    model: str
    usage: Optional[Dict[str, int]] = None
    raw_response: Optional[Dict[str, Any]] = None


class LLMService:
    """
    Service for interacting with local LLM (llama.cpp).
    Handles classification and summarization prompts.
    """

    def __init__(self, settings: Settings):
        """
        Initialize LLM service.

        Args:
            settings: Application settings with LLM configuration
        """
        self.settings = settings
        self.api_url = settings.llm_api_url
        self.model = settings.LLM_MODEL
        self.timeout = settings.LLM_TIMEOUT_SECONDS

    async def classify_email(
        self,
        email: Email,
        context: Optional[str] = None
    ) -> Tuple[ClassificationResult, str]:
        """
        Classify an email as promotions or important.

        Args:
            email: Email to classify
            context: Additional context for classification

        Returns:
            Tuple of (ClassificationResult, reasoning)
        """
        prompt = self._build_classification_prompt(email, context)

        try:
            response = await self._call_llm(prompt)
            return self._parse_classification_response(response.content)
        except Exception as e:
            # Fallback: heuristic-based classification
            return self._heuristic_classification(email), str(e)

    async def summarize_email(
        self,
        email: Email,
        focus_areas: Optional[List[str]] = None
    ) -> str:
        """
        Generate a summary of an email.

        Args:
            email: Email to summarize
            focus_areas: Specific areas to focus on in summary

        Returns:
            Summary text
        """
        prompt = self._build_summarization_prompt(email, focus_areas)

        try:
            response = await self._call_llm(prompt)
            return response.content.strip()
        except Exception as e:
            # Fallback: simple extraction
            return self._heuristic_summary(email)

    async def _call_llm(self, prompt: str) -> LLMResponse:
        """
        Make API call to local LLM.

        Args:
            prompt: User prompt

        Returns:
            LLMResponse object

        Raises:
            requests.exceptions.Timeout: If LLM request times out
            requests.exceptions.RequestException: If request fails
        """
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self._system_prompt()},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3,
            "max_tokens": 500,
            "stream": False
        }

        start_time = time.time()
        response = requests.post(
            self.api_url,
            json=payload,
            timeout=self.timeout
        )
        response.raise_for_status()

        result = response.json()

        return LLMResponse(
            content=result["choices"][0]["message"]["content"],
            model=result["model"],
            usage=result.get("usage"),
            raw_response=result
        )

    def _build_classification_prompt(
        self,
        email: Email,
        context: Optional[str]
    ) -> str:
        """Build prompt for email classification."""
        context_text = f"\n\nContext: {context}" if context else ""

        return f"""You are an email classification assistant. Analyze this email and determine if it is:
1. PROMOTIONS - Marketing, advertising, newsletters, sales, promotional content
2. IMPORTANT - Personal messages, work-related, urgent, legitimate communications

Email Details:
- Subject: {email.subject}
- From: {email.from_addr}
- Body: {email.body or "[No body content]"}{context_text}

Respond with ONLY one of these exact words: PROMOTIONS or IMPORTANT
Then briefly explain your reasoning in 1-2 sentences.

Example response format:
IMPORTANT
This appears to be a personal message from a colleague about a project deadline."""

    def _build_summarization_prompt(
        self,
        email: Email,
        focus_areas: Optional[List[str]]
    ) -> str:
        """Build prompt for email summarization."""
        focus_text = (
            f"\n\nPlease focus on extracting information related to: {', '.join(focus_areas)}"
            if focus_areas else ""
        )

        return f"""You are an email summarization assistant. Provide a concise summary of this email.

Email Details:
- Subject: {email.subject}
- From: {email.from_addr}
- Body: {email.body or "[No body content]"}{focus_text}

Provide a summary that includes:
1. The main purpose of the email
2. Any action items or deadlines mentioned
3. Key information or decisions discussed
4. A brief 1-2 sentence overall summary

Keep the summary under 150 words."""

    def _system_prompt(self) -> str:
        """Return system instruction for LLM."""
        return """You are a helpful email assistant. You should be concise, accurate, and professional in your responses. Always prioritize clarity and brevity."""

    def _parse_classification_response(self, response_text: str) -> Tuple[ClassificationResult, str]:
        """
        Parse LLM response for classification.

        Args:
            response_text: Raw LLM response text

        Returns:
            Tuple of (ClassificationResult, reasoning)
        """
        response_upper = response_text.upper()

        if "PROMOTIONS" in response_upper or "MARKETING" in response_upper:
            return ClassificationResult.PROMOTIONS, self._extract_reasoning(response_text)
        elif "IMPORTANT" in response_upper:
            return ClassificationResult.IMPORTANT, self._extract_reasoning(response_text)
        else:
            # Default to uncertain if response doesn't match expected format
            return ClassificationResult.UNCERTAIN, "Could not determine classification from response"

    def _extract_reasoning(self, response_text: str) -> str:
        """Extract reasoning portion from response."""
        lines = response_text.strip().split("\n")
        if len(lines) > 1:
            return " ".join(lines[1:]).strip()
        return "No reasoning provided"

    def _heuristic_classification(self, email: Email) -> ClassificationResult:
        """
        Fallback heuristic-based classification.

        Args:
            email: Email to classify

        Returns:
            ClassificationResult based on heuristics
        """
        # Check for marketing indicators
        marketing_patterns = [
            r"unsubscribe", r"newsletter", r"promotion", r"sale",
            r"discount", r"offer", r"coupon", r"gift card",
            r"limited time", r"act now", r"don't miss out"
        ]

        search_text = (email.subject + " " + (email.body or "")).lower()

        if any(pattern.lower() in search_text for pattern in marketing_patterns):
            return ClassificationResult.PROMOTIONS

        # Check sender domain patterns
        sender_lower = email.from_addr.lower()
        marketing_domains = [
            "newsletter", "noreply", "no-reply", "marketing", "deal",
            "shop", "store", "ecommerce"
        ]

        if any(domain in sender_lower for domain in marketing_domains):
            return ClassificationResult.PROMOTIONS

        return ClassificationResult.IMPORTANT

    def _heuristic_summary(self, email: Email) -> str:
        """
        Fallback simple summary.

        Args:
            email: Email to summarize

        Returns:
            Simple summary text
        """
        # Extract first paragraph or first 200 chars
        body = email.body or "No content"
        first_newline = body.find("\n")
        if first_newline > 0 and first_newline < 200:
            summary = body[:first_newline]
        else:
            summary = body[:200] + "..." if len(body) > 200 else body

        return f"Email from {email.from_addr} about '{email.subject}'. Content: {summary}"
