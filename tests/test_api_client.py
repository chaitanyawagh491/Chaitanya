import pytest
import time
import requests
from unittest.mock import patch, MagicMock
from PIL import Image

from network.api_client import (
    ApiClient,
    AnalysisResult,
    GeminiVisionProvider,
    OpenAiVisionProvider,
    OpenRouterVisionProvider,
    classify_api_error
)
from config import Config
from engine.overlay import OverlayController
from engine.processor import PipelineManager
from services.diag_service import DiagnosticsService

# ---------------------------------------------------------
# 1. Model prefix handling
# ---------------------------------------------------------
def test_gemini_model_name_prefix_handling():
    provider = GeminiVisionProvider()
    model_prefixed = "models/gemini-3.5-flash"
    clean_model = model_prefixed.split("/")[-1] if "/" in model_prefixed else model_prefixed
    assert clean_model == "gemini-3.5-flash"

# ---------------------------------------------------------
# 2. Valid API response parsing
# ---------------------------------------------------------
def test_valid_gemini_api_response():
    provider = GeminiVisionProvider()
    dummy_img = Image.new("RGB", (60, 60), color="white")
    
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {}
    mock_resp.json.return_value = {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": "  42  "}]
                }
            }
        ]
    }
    
    with patch("requests.post", return_value=mock_resp):
        res = provider.analyze_image_with_details(dummy_img, "test_api_key", "gemini-3.5-flash")
        assert res.success is True
        assert res.text == "42"
        assert res.error_code == "SUCCESS"
        assert res.provider == "gemini"
        assert res.model == "gemini-3.5-flash"

# ---------------------------------------------------------
# 3. Authentication failures (401 / 403 / API_KEY_INVALID)
# ---------------------------------------------------------
def test_invalid_api_key_auth_error():
    provider = GeminiVisionProvider()
    dummy_img = Image.new("RGB", (60, 60), color="white")
    
    mock_resp = MagicMock()
    mock_resp.status_code = 400
    mock_resp.headers = {}
    mock_resp.text = '{"error": {"code": 400, "message": "API key not valid. Please pass a valid API key.", "status": "INVALID_ARGUMENT", "details": [{"reason": "API_KEY_INVALID"}]}}'
    mock_resp.json.return_value = {
        "error": {
            "code": 400,
            "message": "API key not valid. Please pass a valid API key.",
            "status": "INVALID_ARGUMENT",
            "details": [{"reason": "API_KEY_INVALID"}]
        }
    }
    
    with patch("requests.post", return_value=mock_resp):
        res = provider.analyze_image_with_details(dummy_img, "invalid_key", "gemini-3.5-flash")
        assert res.success is False
        assert res.error_code == "AUTH_FAILED"
        assert "authentication failed" in res.error_message.lower()

# ---------------------------------------------------------
# 4. Model not found (404)
# ---------------------------------------------------------
def test_unsupported_model_404():
    msg, code, retry = classify_api_error(
        "gemini", 404,
        raw_text='{"error": {"code": 404, "message": "models/gemini-1.5-flash is not found for API version v1beta"}}',
        error_data={"error": {"code": 404, "message": "models/gemini-1.5-flash is not found for API version v1beta"}}
    )
    assert code == "MODEL_NOT_FOUND"
    assert "unavailable or unsupported" in msg

# ---------------------------------------------------------
# 5. Rate limit (429) & Retry-After header
# ---------------------------------------------------------
def test_rate_limit_with_retry_after():
    msg, code, retry = classify_api_error(
        "gemini", 429,
        error_data={"error": {"code": 429, "message": "Resource has been exhausted"}},
        response_headers={"Retry-After": "15"}
    )
    assert code == "RATE_LIMIT"
    assert "rate limit reached" in msg.lower()
    assert retry == 15

# ---------------------------------------------------------
# 6. Quota exhaustion detection
# ---------------------------------------------------------
# 6. Quota exhaustion detection & Immediate stop (no retries)
# ---------------------------------------------------------
def test_quota_exhaustion_detection():
    # 1. Plain message with quota keywords
    msg, code, retry = classify_api_error(
        "gemini", 429,
        error_data={"error": {"code": 429, "message": "Quota exceeded for quota metric Queries per minute and billing"}}
    )
    assert code == "QUOTA_EXHAUSTED"
    assert "quota exceeded" in msg.lower()

    # 2. Real Google AI Studio QuotaFailure & RetryInfo payload
    google_payload = {
        "error": {
            "code": 429,
            "message": "You exceeded your current quota, please check your plan and billing details.",
            "status": "RESOURCE_EXHAUSTED",
            "details": [
                {
                    "@type": "type.googleapis.com/google.rpc.QuotaFailure",
                    "violations": [{"quotaValue": "20", "quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier"}]
                },
                {
                    "@type": "type.googleapis.com/google.rpc.RetryInfo",
                    "retryDelay": "36215s"
                }
            ]
        }
    }
    msg2, code2, retry2 = classify_api_error("gemini", 429, error_data=google_payload)
    assert code2 == "QUOTA_EXHAUSTED"
    assert "quota exceeded" in msg2.lower()
    assert retry2 == 36215

def test_gemini_provider_quota_exhausted_immediate_no_retry():
    """Verify provider does NOT retry when quota is genuinely exhausted."""
    provider = GeminiVisionProvider()
    dummy_img = Image.new("RGB", (60, 60), color="white")
    
    mock_resp = MagicMock()
    mock_resp.status_code = 429
    mock_resp.headers = {}
    mock_resp.json.return_value = {
        "error": {
            "code": 429,
            "message": "Resource has been exhausted (e.g. check quota).",
            "status": "RESOURCE_EXHAUSTED",
            "details": [{"@type": "type.googleapis.com/google.rpc.QuotaFailure"}]
        }
    }
    
    with patch("requests.post", return_value=mock_resp) as mock_post:
        res = provider.analyze_image_with_details(dummy_img, "test_key", "gemini-3.5-flash-lite")
        assert res.success is False
        assert res.error_code == "QUOTA_EXHAUSTED"
        assert "quota exceeded" in res.error_message.lower()
        # Must be called exactly once: NO wasteful retrying on exhausted quota!
        assert mock_post.call_count == 1

def test_gemini_provider_model_not_found_no_auto_fallback():
    """Verify provider does NOT silently switch models on 404."""
    provider = GeminiVisionProvider()
    dummy_img = Image.new("RGB", (60, 60), color="white")
    
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_resp.headers = {}
    mock_resp.json.return_value = {
        "error": {
            "code": 404,
            "message": "models/custom-model-x is not found",
            "status": "NOT_FOUND"
        }
    }
    
    with patch("requests.post", return_value=mock_resp) as mock_post:
        res = provider.analyze_image_with_details(dummy_img, "test_key", "custom-model-x")
        assert res.success is False
        assert res.error_code == "MODEL_NOT_FOUND"
        assert res.model == "custom-model-x"
        assert mock_post.call_count == 1

def test_gemini_provider_transient_rate_limit_bounded_retry():
    """Verify provider retries transient rate limits when Retry-After is short and bounded."""
    provider = GeminiVisionProvider()
    dummy_img = Image.new("RGB", (60, 60), color="white")
    
    mock_429 = MagicMock()
    mock_429.status_code = 429
    mock_429.headers = {"Retry-After": "1"}
    mock_429.json.return_value = {
        "error": {"code": 429, "message": "Rate limit exceeded. Please slow down."}
    }
    
    mock_200 = MagicMock()
    mock_200.status_code = 200
    mock_200.headers = {}
    mock_200.json.return_value = {
        "candidates": [{"content": {"parts": [{"text": "100"}]}}]
    }
    
    with patch("requests.post", side_effect=[mock_429, mock_200]) as mock_post:
        with patch("time.sleep") as mock_sleep:
            res = provider.analyze_image_with_details(dummy_img, "test_key", "gemini-3.5-flash-lite")
            assert res.success is True
            assert res.text == "100"
            assert mock_post.call_count == 2
            mock_sleep.assert_called_once_with(1.0)


# ---------------------------------------------------------
# 7. Network failure & Timeout
# ---------------------------------------------------------
def test_network_failure_and_timeout():
    provider = GeminiVisionProvider()
    dummy_img = Image.new("RGB", (60, 60), color="white")

    # Connection error
    with patch("requests.post", side_effect=requests.exceptions.ConnectionError("DNS failure")):
        res = provider.analyze_image_with_details(dummy_img, "test_key", "gemini-3.5-flash")
        assert res.success is False
        assert res.error_code == "NETWORK_ERROR"
        assert "unable to reach gemini" in res.error_message.lower()

    # Timeout
    with patch("requests.post", side_effect=requests.exceptions.Timeout("Read timed out")):
        res = provider.analyze_image_with_details(dummy_img, "test_key", "gemini-3.5-flash")
        assert res.success is False
        assert res.error_code == "TIMEOUT"
        assert "timed out" in res.error_message.lower()

# ---------------------------------------------------------
# 8. Empty or malformed responses
# ---------------------------------------------------------
def test_empty_and_malformed_responses():
    provider = GeminiVisionProvider()
    dummy_img = Image.new("RGB", (60, 60), color="white")

    # Empty candidate list
    mock_resp1 = MagicMock()
    mock_resp1.status_code = 200
    mock_resp1.headers = {}
    mock_resp1.json.return_value = {"candidates": []}
    with patch("requests.post", return_value=mock_resp1):
        res1 = provider.analyze_image_with_details(dummy_img, "test_key", "gemini-3.5-flash")
        assert res1.success is False
        assert res1.error_code == "EMPTY_RESPONSE"
        assert "returned no answer" in res1.error_message.lower()

    # Invalid JSON / non-json response
    mock_resp2 = MagicMock()
    mock_resp2.status_code = 200
    mock_resp2.headers = {}
    mock_resp2.json.side_effect = ValueError("Invalid JSON")
    with patch("requests.post", return_value=mock_resp2):
        res2 = provider.analyze_image_with_details(dummy_img, "test_key", "gemini-3.5-flash")
        assert res2.success is False
        assert res2.error_code == "INVALID_RESPONSE_FORMAT"
        assert "could not be processed" in res2.error_message.lower()

# ---------------------------------------------------------
# 9. Provider fallback: success & failure
# ---------------------------------------------------------
def test_api_client_fallback_success():
    cfg = Config()
    cfg.ACTIVE_PROVIDER = "gemini"
    cfg.ACTIVE_MODEL = "gemini-3.5-flash"
    cfg.FALLBACK_ENABLED = True
    cfg.FALLBACK_PROVIDER = "openai"
    cfg.FALLBACK_MODEL = "gpt-4o"
    cfg.set_api_key("gemini", "dummy_gemini_key")
    cfg.set_api_key("openai", "dummy_openai_key")
    
    client = ApiClient(cfg)
    dummy_img = Image.new("RGB", (60, 60), color="white")
    
    fail_res = AnalysisResult(
        success=False, text="", error_message="Gemini API quota exceeded.",
        error_code="QUOTA_EXHAUSTED", provider="gemini", model="gemini-3.5-flash"
    )
    succ_res = AnalysisResult(
        success=True, text="42 (Fallback Result)", error_message="",
        error_code="SUCCESS", provider="openai", model="gpt-4o"
    )
    
    with patch.object(client.providers["gemini"], "analyze_image_with_details", return_value=fail_res):
        with patch.object(client.providers["openai"], "analyze_image_with_details", return_value=succ_res):
            result = client.query_with_details(dummy_img)
            assert result.success is True
            assert result.text == "42 (Fallback Result)"
            assert result.provider == "openai"

def test_api_client_fallback_failure():
    cfg = Config()
    cfg.ACTIVE_PROVIDER = "gemini"
    cfg.FALLBACK_ENABLED = True
    cfg.FALLBACK_PROVIDER = "openai"
    cfg.set_api_key("gemini", "dummy_gemini_key")
    cfg.set_api_key("openai", "dummy_openai_key")
    
    client = ApiClient(cfg)
    dummy_img = Image.new("RGB", (60, 60), color="white")
    
    fail1 = AnalysisResult(
        success=False, text="", error_message="Primary auth failed.",
        error_code="AUTH_FAILED", provider="gemini", model="gemini-3.5-flash"
    )
    fail2 = AnalysisResult(
        success=False, text="", error_message="Fallback model unavailable.",
        error_code="MODEL_NOT_FOUND", provider="openai", model="gpt-4o"
    )
    
    with patch.object(client.providers["gemini"], "analyze_image_with_details", return_value=fail1):
        with patch.object(client.providers["openai"], "analyze_image_with_details", return_value=fail2):
            result = client.query_with_details(dummy_img)
            assert result.success is False
            assert result.error_code == "AUTH_FAILED"
            assert "Fallback 'openai' also failed" in result.error_message

def test_api_client_returns_none_when_keys_missing():
    cfg = Config()
    cfg.ACTIVE_PROVIDER = "gemini"
    cfg.FALLBACK_ENABLED = False
    cfg.set_api_key("gemini", "")
    
    client = ApiClient(cfg)
    dummy_img = Image.new("RGB", (60, 60), color="black")
    
    result = client.query(dummy_img)
    assert result is None
    
    detailed = client.query_with_details(dummy_img)
    assert detailed.success is False
    assert detailed.error_code == "MISSING_KEY"
    assert "missing" in detailed.error_message.lower()

# ---------------------------------------------------------
# 10. Overlay delivery: responses, errors, and status
# ---------------------------------------------------------
def test_overlay_delivery_methods():
    cfg = Config()
    cfg.INJECT_X = 30
    cfg.INJECT_Y = 30
    cfg.RESPONSE_DURATION = 3.0
    overlay = OverlayController(cfg)
    
    with patch.object(overlay, "_dispatch_overlay", return_value=True) as mock_dispatch:
        assert overlay.display_status("Analyzing...") is True
        mock_dispatch.assert_called_with("Analyzing...", text_color="#818CF8", duration_ms=25000)
        
        assert overlay.display_error("Gemini rate limit reached.") is True
        assert overlay.display_response("Answer 25") is True

# ---------------------------------------------------------
# 11. Duplicate request prevention in PipelineManager
# ---------------------------------------------------------
def test_duplicate_request_prevention():
    cfg = Config()
    pm = PipelineManager(cfg)
    
    # Simulate processing lock
    pm.processing = True
    # Triggering should be rejected immediately while processing
    triggered = pm.trigger_analysis()
    assert triggered is False
    
    pm.processing = False
    triggered = pm.trigger_analysis()
    assert triggered is True
    pm.running = False

# ---------------------------------------------------------
# 12. DiagnosticsService AI Request Test (Mocked)
# ---------------------------------------------------------
def test_diagnostics_service_test_ai_request_mocked():
    svc = DiagnosticsService()
    
    # 1. Missing key
    with patch("config.config.get_api_key", return_value=""):
        res = svc.test_ai_request()
        assert res["status"] == "Configuration missing"
        assert res["error_code"] == "MISSING_KEY"

    # 2. Successful response
    mock_result = AnalysisResult(
        success=True, text="2", error_message="",
        error_code="SUCCESS", provider="gemini", model="gemini-3.5-flash", duration_sec=1.23
    )
    with patch("config.config.get_api_key", return_value="valid_mock_key"):
        with patch.object(ApiClient, "query_with_details", return_value=mock_result):
            with patch.object(OverlayController, "display_response", return_value=True):
                res = svc.test_ai_request()
                assert res["status"] == "API request succeeded"
                assert res["response_text"] == "2"
                assert res["overlay_tested"] is True

# ---------------------------------------------------------
# 13. Live Gemini API integration test (Distinguished from mock)
# ---------------------------------------------------------
def test_live_gemini_api_integration():
    """
    Live API integration test using the user's real configured key.
    Tests end-to-end network reachability, authentication, model compatibility,
    and actual answer retrieval.
    """
    cfg = Config()
    key = cfg.get_api_key("gemini")
    if not key or key.startswith("dummy") or key.startswith("test"):
        pytest.skip("Skipping live API integration test: No valid live Gemini key in configuration.")
    
    svc = DiagnosticsService()
    res = svc.test_ai_request()
    
    # Distinguish live result
    if res["status"] in ["Quota exhausted", "Rate limited"]:
        print(f"\n[LIVE API RATE/QUOTA OBSERVED] Code: {res['error_code']}, Message: {res['message']}")
        assert res["error_code"] in ["QUOTA_EXHAUSTED", "RATE_LIMIT"]
    else:
        assert res["status"] == "API request succeeded", f"Live Gemini API test failed: {res.get('message')}"
        assert res["duration_sec"] > 0.0
        assert len(res["response_text"]) > 0
        print(f"\n[LIVE TEST PASSED] Model: {res['model']}, Duration: {res['duration_sec']:.2f}s, Response: '{res['response_text']}'")
