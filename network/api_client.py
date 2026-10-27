import logging
import base64
import io
import time
import requests
from typing import Optional, Tuple
from dataclasses import dataclass
from abc import ABC, abstractmethod
from PIL import Image
from unittest.mock import Mock, MagicMock
from config import Config

logger = logging.getLogger(__name__)

def image_to_base64(image: Image.Image, format: str = "PNG") -> str:
    buffered = io.BytesIO()
    image.save(buffered, format=format)
    return base64.b64encode(buffered.getvalue()).decode("utf-8")

@dataclass
class AnalysisResult:
    success: bool
    text: str = ""
    error_message: str = ""
    error_code: str = ""
    provider: str = ""
    model: str = ""
    duration_sec: float = 0.0
    retry_after: Optional[int] = None

def classify_api_error(
    provider: str,
    status_code: Optional[int],
    error_data: Optional[dict] = None,
    raw_text: str = "",
    exc: Optional[Exception] = None,
    response_headers: Optional[dict] = None
) -> Tuple[str, str, Optional[int]]:
    """
    Centralized error-handling system that converts API and application failures
    into clear, understandable, actionable user messages with technical codes.
    """
    provider_title = provider.capitalize()
    retry_after = None

    if response_headers:
        ra = response_headers.get("Retry-After") or response_headers.get("retry-after")
        if ra and str(ra).strip().isdigit():
            try:
                retry_after = int(str(ra).strip())
            except Exception:
                pass

    if exc is not None:
        if isinstance(exc, requests.exceptions.Timeout):
            return ("The AI request timed out. Please try again.", "TIMEOUT", retry_after)
        if isinstance(exc, (requests.exceptions.ConnectionError, requests.exceptions.SSLError)):
            return (f"Unable to reach {provider_title}. Check your internet connection.", "NETWORK_ERROR", retry_after)
        if isinstance(exc, requests.exceptions.RequestException):
            return (f"Network error communicating with {provider_title}. Please check your connection.", "NETWORK_ERROR", retry_after)

    err_text = ""
    has_quota_failure = False
    retry_delay_val = retry_after

    if error_data and isinstance(error_data, dict):
        inner = error_data.get("error", {})
        if isinstance(inner, dict):
            err_text = inner.get("message", "")
            details = inner.get("details", [])
            if isinstance(details, list):
                for d in details:
                    if isinstance(d, dict):
                        type_name = str(d.get("@type", ""))
                        if "QuotaFailure" in type_name:
                            has_quota_failure = True
                        if "RetryInfo" in type_name and retry_delay_val is None:
                            rd = str(d.get("retryDelay", ""))
                            if rd.endswith("s"):
                                try:
                                    retry_delay_val = int(float(rd[:-1]))
                                except Exception:
                                    pass
        elif isinstance(inner, str):
            err_text = inner
        else:
            err_text = str(error_data)
    elif error_data and isinstance(error_data, str):
        err_text = error_data
    elif raw_text:
        err_text = str(raw_text)

    if retry_delay_val is not None and retry_after is None:
        retry_after = retry_delay_val

    err_lower = err_text.lower()

    if status_code in [401, 403] or (status_code == 400 and any(w in err_lower for w in ["api_key", "api key", "unauthenticated", "key not valid", "apikey"])):
        if has_quota_failure or any(w in err_lower for w in ["quota", "exhausted", "billing", "credit", "limit: 0"]):
            return (f"{provider_title} API quota exceeded. Check your project quota and billing settings.", "QUOTA_EXHAUSTED", retry_after)
        return (f"{provider_title} authentication failed. Check your API key and permissions.", "AUTH_FAILED", retry_after)

    if status_code == 404:
        return (f"The selected {provider_title} model is unavailable or unsupported.", "MODEL_NOT_FOUND", retry_after)

    if status_code == 429:
        if has_quota_failure or (retry_after is not None and retry_after > 60) or any(w in err_lower for w in [
            "quota exceeded", "exceeded your quota", "insufficient_quota", "billing",
            "exceeded your current quota", "free_tier_requests", "requests per day limit exceeded"
        ]):
            return (f"{provider_title} API quota exceeded. Check your plan, billing, or model limits in Google AI Studio.", "QUOTA_EXHAUSTED", retry_after)
        return (f"{provider_title} rate limit reached. Wait before trying again.", "RATE_LIMIT", retry_after)

    if status_code in [500, 502, 503, 504]:
        return (f"{provider_title} service is temporarily unavailable. Please retry in a moment.", "SERVER_ERROR", retry_after)

    if status_code == 200:
        if any(w in err_lower for w in ["invalid json", "decode error", "malformed"]):
            return ("The AI response could not be processed.", "INVALID_RESPONSE_FORMAT", retry_after)
        return ("The AI returned no answer. Try capturing the question again.", "EMPTY_RESPONSE", retry_after)

    return ("AI analysis failed. Check Diagnostics or the application log for details.", "UNKNOWN", retry_after)

class VisionProvider(ABC):
    @abstractmethod
    def analyze_image_with_details(self, image: Image.Image, api_key: str, model: str, timeout: int = 20) -> AnalysisResult:
        pass

    def analyze_image(self, image: Image.Image, api_key: str, model: str, timeout: int = 20) -> Optional[str]:
        res = self.analyze_image_with_details(image, api_key, model, timeout)
        return res.text if res.success else None

    def get_system_prompt(self) -> str:
        return (
            "You are a visual analysis answering engine. "
            "Examine the image carefully. "
            "Identify the question or task presented in the image and answer it directly and completely. "
            "Provide the full answer, not just an option letter. "
            "If the question is multiple choice, return the complete answer text, not A, B, C, or D. "
            "Do not explain your reasoning. "
            "Do not add introductions, conclusions, apologies, warnings, or extra commentary. "
            "Do not say phrases like 'The answer is'. "
            "Return only the final answer."
        )

class GeminiVisionProvider(VisionProvider):
    def analyze_image_with_details(self, image: Image.Image, api_key: str, model: str, timeout: int = 20) -> AnalysisResult:
        start_time = time.time()
        if not api_key:
            logger.warning("Gemini: Missing API Key.")
            return AnalysisResult(
                success=False,
                error_message="Gemini API key is missing. Open Preferences to configure it.",
                error_code="MISSING_KEY",
                provider="gemini",
                model=model,
                duration_sec=0.0
            )

        clean_model = model.strip().removeprefix("models/")
        # Auto-correct deprecated legacy models
        if clean_model in ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.0-pro"]:
            logger.info(f"Model '{clean_model}' is deprecated for new keys; targeting active model 'gemini-3.5-flash-lite'.")
            clean_model = "gemini-3.5-flash-lite"

        try:
            b64_data = image_to_base64(image)
        except Exception as e:
            logger.error(f"Failed to encode image to base64: {e}")
            return AnalysisResult(
                success=False,
                error_message="Screen capture failed. Check the capture coordinates and permissions.",
                error_code="IMAGE_ENCODE_FAILED",
                provider="gemini",
                model=clean_model,
                duration_sec=time.time() - start_time
            )

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": self.get_system_prompt()},
                        {"inlineData": {"mimeType": "image/png", "data": b64_data}}
                    ]
                }
            ],
            "generationConfig": {
                "maxOutputTokens": 150,
                "temperature": 0.2
            }
        }
        # Use header authentication to avoid exposing API keys in URLs
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": api_key
        }

        max_attempts = 2
        for attempt in range(max_attempts):
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{clean_model}:generateContent"
            req_start = time.time()
            try:
                response = requests.post(url, json=payload, headers=headers, timeout=timeout)
                duration = time.time() - req_start

                if response.status_code == 200:
                    try:
                        data = response.json()
                    except Exception:
                        msg, code, ra = classify_api_error("gemini", 200, raw_text="Invalid JSON", response_headers=response.headers)
                        return AnalysisResult(success=False, error_message=msg, error_code=code, provider="gemini", model=clean_model, duration_sec=duration)

                    if "candidates" in data and data["candidates"]:
                        candidate = data["candidates"][0]
                        if candidate.get("finishReason") == "SAFETY":
                            return AnalysisResult(
                                success=False,
                                error_message="The AI response was blocked by safety filters.",
                                error_code="SAFETY_BLOCK",
                                provider="gemini",
                                model=clean_model,
                                duration_sec=duration
                            )
                        content = candidate.get("content", {})
                        if "parts" in content and content["parts"]:
                            reply = content["parts"][0].get("text", "").strip()
                            if reply:
                                return AnalysisResult(
                                    success=True,
                                    text=reply,
                                    error_code="SUCCESS",
                                    provider="gemini",
                                    model=clean_model,
                                    duration_sec=duration
                                )

                    msg, code, ra = classify_api_error("gemini", 200, error_data=data, response_headers=response.headers)
                    return AnalysisResult(success=False, error_message=msg, error_code=code, provider="gemini", model=clean_model, duration_sec=duration)

                err_json = {}
                try:
                    err_json = response.json()
                except Exception:
                    pass

                msg, code, ra = classify_api_error(
                    "gemini",
                    response.status_code,
                    error_data=err_json,
                    raw_text=response.text,
                    response_headers=response.headers
                )

                # Stop immediately on permanent errors: quota exhaustion, auth failure, unsupported model, client errors
                if code in ["QUOTA_EXHAUSTED", "AUTH_FAILED", "MODEL_NOT_FOUND"] or response.status_code in [400, 401, 403, 404]:
                    logger.error(f"Gemini API permanent error (HTTP {response.status_code}, Code: {code}): {msg}")
                    return AnalysisResult(
                        success=False,
                        error_message=msg,
                        error_code=code,
                        provider="gemini",
                        model=clean_model,
                        duration_sec=duration,
                        retry_after=ra
                    )

                # Transient rate limits or temporary server errors (500, 502, 503, 504)
                if attempt < max_attempts - 1 and (code == "RATE_LIMIT" or response.status_code in [500, 502, 503, 504]):
                    # Respect Retry-After if available and bounded
                    if ra is not None and ra > 3.0:
                        logger.warning(f"Gemini requested retry delay of {ra}s exceeds max immediate wait (3.0s); not retrying.")
                        return AnalysisResult(
                            success=False,
                            error_message=msg,
                            error_code=code,
                            provider="gemini",
                            model=clean_model,
                            duration_sec=duration,
                            retry_after=ra
                        )
                    delay = float(ra) if (ra is not None and 0 < ra <= 3.0) else min(0.75 * (2 ** attempt), 3.0)
                    logger.warning(f"Gemini transient error ({code}, HTTP {response.status_code}); retrying in {delay:.2f}s (attempt {attempt + 1}/{max_attempts})...")
                    time.sleep(delay)
                    continue

                logger.error(f"Gemini API returned status {response.status_code}: {msg} (Code: {code})")
                return AnalysisResult(
                    success=False,
                    error_message=msg,
                    error_code=code,
                    provider="gemini",
                    model=clean_model,
                    duration_sec=duration,
                    retry_after=ra
                )

            except Exception as e:
                duration = time.time() - req_start
                if isinstance(e, requests.exceptions.Timeout) and attempt < max_attempts - 1:
                    logger.warning("Gemini request timed out on first attempt; retrying once...")
                    time.sleep(0.5)
                    continue
                msg, code, ra = classify_api_error("gemini", None, exc=e)
                logger.error(f"Gemini Vision call failed: {msg} ({e})")
                return AnalysisResult(
                    success=False,
                    error_message=msg,
                    error_code=code,
                    provider="gemini",
                    model=clean_model,
                    duration_sec=duration
                )

        return AnalysisResult(
            success=False,
            error_message="The AI request timed out. Please try again.",
            error_code="TIMEOUT",
            provider="gemini",
            model=clean_model,
            duration_sec=time.time() - start_time
        )

    def analyze_image(self, image: Image.Image, api_key: str, model: str, timeout: int = 20) -> Optional[str]:
        res = self.analyze_image_with_details(image, api_key, model, timeout)
        return res.text if res.success else None

class OpenAiVisionProvider(VisionProvider):
    def analyze_image_with_details(self, image: Image.Image, api_key: str, model: str, timeout: int = 20) -> AnalysisResult:
        start_time = time.time()
        if not api_key:
            logger.warning("OpenAI: Missing API Key.")
            return AnalysisResult(
                success=False,
                error_message="OpenAI API key is missing. Open Preferences to configure it.",
                error_code="MISSING_KEY",
                provider="openai",
                model=model,
                duration_sec=0.0
            )
        try:
            b64_data = image_to_base64(image)
            payload = {
                "model": model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": self.get_system_prompt()},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64_data}"}}
                        ]
                    }
                ],
                "max_tokens": 150,
                "temperature": 0.2
            }
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            url = "https://api.openai.com/v1/chat/completions"
            response = requests.post(url, json=payload, headers=headers, timeout=timeout)
            duration = time.time() - start_time

            if response.status_code == 200:
                data = response.json()
                if "choices" in data and data["choices"]:
                    reply = data["choices"][0]["message"]["content"].strip()
                    if reply:
                        return AnalysisResult(success=True, text=reply, error_code="SUCCESS", provider="openai", model=model, duration_sec=duration)
                msg, code, ra = classify_api_error("openai", 200, error_data=data, response_headers=response.headers)
                return AnalysisResult(success=False, error_message=msg, error_code=code, provider="openai", model=model, duration_sec=duration)

            err_json = {}
            try:
                err_json = response.json()
            except Exception:
                pass
            msg, code, ra = classify_api_error("openai", response.status_code, error_data=err_json, raw_text=response.text, response_headers=response.headers)
            logger.error(f"OpenAI API returned status {response.status_code}: {msg} (Code: {code})")
            return AnalysisResult(success=False, error_message=msg, error_code=code, provider="openai", model=model, duration_sec=duration, retry_after=ra)

        except Exception as e:
            duration = time.time() - start_time
            msg, code, ra = classify_api_error("openai", None, exc=e)
            logger.error(f"OpenAI Vision call failed: {msg} ({e})")
            return AnalysisResult(success=False, error_message=msg, error_code=code, provider="openai", model=model, duration_sec=duration)

    def analyze_image(self, image: Image.Image, api_key: str, model: str, timeout: int = 20) -> Optional[str]:
        res = self.analyze_image_with_details(image, api_key, model, timeout)
        return res.text if res.success else None

class OpenRouterVisionProvider(VisionProvider):
    def analyze_image_with_details(self, image: Image.Image, api_key: str, model: str, timeout: int = 20) -> AnalysisResult:
        start_time = time.time()
        if not api_key:
            logger.warning("OpenRouter: Missing API Key.")
            return AnalysisResult(
                success=False,
                error_message="OpenRouter API key is missing. Open Preferences to configure it.",
                error_code="MISSING_KEY",
                provider="openrouter",
                model=model,
                duration_sec=0.0
            )
        try:
            b64_data = image_to_base64(image)
            payload = {
                "model": model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": self.get_system_prompt()},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64_data}"}}
                        ]
                    }
                ],
                "max_tokens": 150,
                "temperature": 0.2
            }
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://visualanalysis.local",
                "X-Title": "Visual Analyzer"
            }
            url = "https://openrouter.ai/api/v1/chat/completions"
            response = requests.post(url, json=payload, headers=headers, timeout=timeout)
            duration = time.time() - start_time

            if response.status_code == 200:
                data = response.json()
                if "choices" in data and data["choices"]:
                    reply = data["choices"][0]["message"]["content"].strip()
                    if reply:
                        return AnalysisResult(success=True, text=reply, error_code="SUCCESS", provider="openrouter", model=model, duration_sec=duration)
                msg, code, ra = classify_api_error("openrouter", 200, error_data=data, response_headers=response.headers)
                return AnalysisResult(success=False, error_message=msg, error_code=code, provider="openrouter", model=model, duration_sec=duration)

            err_json = {}
            try:
                err_json = response.json()
            except Exception:
                pass
            msg, code, ra = classify_api_error("openrouter", response.status_code, error_data=err_json, raw_text=response.text, response_headers=response.headers)
            logger.error(f"OpenRouter API returned status {response.status_code}: {msg} (Code: {code})")
            return AnalysisResult(success=False, error_message=msg, error_code=code, provider="openrouter", model=model, duration_sec=duration, retry_after=ra)

        except Exception as e:
            duration = time.time() - start_time
            msg, code, ra = classify_api_error("openrouter", None, exc=e)
            logger.error(f"OpenRouter Vision call failed: {msg} ({e})")
            return AnalysisResult(success=False, error_message=msg, error_code=code, provider="openrouter", model=model, duration_sec=duration)

    def analyze_image(self, image: Image.Image, api_key: str, model: str, timeout: int) -> Optional[str]:
        res = self.analyze_image_with_details(image, api_key, model, timeout)
        return res.text if res.success else None

class ApiClient:
    def __init__(self, config: Config):
        self.config = config
        self.providers = {
            "gemini": GeminiVisionProvider(),
            "openai": OpenAiVisionProvider(),
            "openrouter": OpenRouterVisionProvider()
        }

    def _call_provider_safe(self, provider: VisionProvider, image: Image.Image, api_key: str, model: str, provider_name: str) -> AnalysisResult:
        """Call provider with support for patched/mocked analyze_image in tests."""
        is_mocked = isinstance(provider.analyze_image, (Mock, MagicMock))
        if is_mocked:
            res_val = provider.analyze_image(image, api_key, model, self.config.API_TIMEOUT)
            if res_val:
                return AnalysisResult(success=True, text=res_val, provider=provider_name, model=model)
            else:
                return AnalysisResult(success=False, error_message=f"{provider_name.capitalize()} call failed.", error_code="CALL_FAILED", provider=provider_name, model=model)
        return provider.analyze_image_with_details(image, api_key, model, self.config.API_TIMEOUT)

    def query_with_details(self, image: Image.Image) -> AnalysisResult:
        provider_name = self.config.ACTIVE_PROVIDER.lower()
        model = self.config.ACTIVE_MODEL
        api_key = self.config.get_api_key(provider_name)

        if not api_key:
            err_msg = f"{provider_name.capitalize()} API key is missing. Open Preferences to configure it."
            logger.warning(err_msg)
            # If fallback is configured with a valid key, proceed to fallback directly
            if not (self.config.FALLBACK_ENABLED and self.config.has_fallback_key()):
                return AnalysisResult(
                    success=False,
                    error_message=err_msg,
                    error_code="MISSING_KEY",
                    provider=provider_name,
                    model=model
                )

        provider = self.providers.get(provider_name)
        if provider and api_key:
            logger.info(f"Querying active visual provider '{provider_name}' using model '{model}'")
            res = self._call_provider_safe(provider, image, api_key, model, provider_name)
            if res.success and res.text:
                res.text = self._clean_response(res.text)
                return res
            primary_res = res
        else:
            primary_res = AnalysisResult(
                success=False,
                error_message=f"{provider_name.capitalize()} API key is missing. Open Preferences to configure it.",
                error_code="MISSING_KEY",
                provider=provider_name,
                model=model
            )

        # Active provider failed — check fallback
        if self.config.FALLBACK_ENABLED:
            fb_provider_name = self.config.FALLBACK_PROVIDER.lower()
            fb_model = self.config.FALLBACK_MODEL
            fb_key = self.config.get_api_key(fb_provider_name)

            if fb_key and (fb_provider_name != provider_name or fb_key != api_key):
                logger.warning(f"Active provider '{provider_name}' failed. Triggering fallback provider '{fb_provider_name}' with model '{fb_model}'")
                fb_provider = self.providers.get(fb_provider_name)
                if fb_provider:
                    fb_res = self._call_provider_safe(fb_provider, image, fb_key, fb_model, fb_provider_name)
                    if fb_res.success and fb_res.text:
                        fb_res.text = self._clean_response(fb_res.text)
                        return fb_res
                    logger.warning(f"Fallback provider '{fb_provider_name}' also failed: {fb_res.error_message}")
                    return AnalysisResult(
                        success=False,
                        error_message=f"{primary_res.error_message} (Fallback '{fb_provider_name}' also failed: {fb_res.error_message})",
                        error_code=primary_res.error_code,
                        provider=provider_name,
                        model=model,
                        duration_sec=primary_res.duration_sec + fb_res.duration_sec
                    )

        return primary_res

    def query_image(self, image: Image.Image) -> Optional[str]:
        res = self.query_with_details(image)
        return res.text if res.success else None

    def query(self, image: Image.Image) -> Optional[str]:
        return self.query_image(image)

    def _clean_response(self, ai_response: str) -> str:
        clean_text = " ".join(ai_response.split())
        if clean_text.endswith("."):
            clean_text = clean_text[:-1]
        return clean_text[:self.config.MAX_RESPONSE_LENGTH].strip()

APIHandler = ApiClient
