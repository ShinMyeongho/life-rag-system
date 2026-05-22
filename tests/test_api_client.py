"""
api_client.py 단위 테스트

테스트 대상:
  - ClaudeResponse: NamedTuple 구조
  - _should_retry_claude(): 오류 분류 로직
  - _should_retry_gemini(): 오류 분류 로직
  - 재시도 상수 검증
"""
import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import anthropic
from api_client import (
    ClaudeResponse,
    _should_retry_claude,
    _should_retry_gemini,
    MAX_RETRIES,
    BASE_DELAY,
    BACKOFF_MULT,
)


# ── ClaudeResponse ──────────────────────────────────────

class TestClaudeResponse:

    def test_fields(self):
        r = ClaudeResponse(text="안녕", input_tokens=100, output_tokens=50)
        assert r.text == "안녕"
        assert r.input_tokens == 100
        assert r.output_tokens == 50

    def test_is_named_tuple(self):
        """NamedTuple이므로 인덱스 접근 가능."""
        r = ClaudeResponse(text="테스트", input_tokens=10, output_tokens=5)
        assert r[0] == "테스트"
        assert r[1] == 10
        assert r[2] == 5

    def test_immutable(self):
        """NamedTuple은 불변."""
        r = ClaudeResponse(text="x", input_tokens=0, output_tokens=0)
        with pytest.raises(AttributeError):
            r.text = "y"

    def test_zero_tokens_allowed(self):
        """토큰 0은 정상 (오류 케이스에서 사용)."""
        r = ClaudeResponse(text="", input_tokens=0, output_tokens=0)
        assert r.input_tokens == 0


# ── _should_retry_claude ──────────────────────────────────────

def _make_mock_response(status_code: int):
    """anthropic 예외 생성에 필요한 httpx.Response 모의 객체."""
    import unittest.mock as mock
    r = mock.MagicMock()
    r.status_code = status_code
    r.headers = {}
    r.request = mock.MagicMock()
    return r


class TestShouldRetryClaude:

    def test_rate_limit_should_retry(self):
        """429 RateLimitError → 재시도."""
        exc = anthropic.RateLimitError(
            message="rate limit",
            response=_make_mock_response(429),
            body={},
        )
        assert _should_retry_claude(exc) is True

    def test_timeout_should_retry(self):
        exc = anthropic.APITimeoutError(request=None)
        assert _should_retry_claude(exc) is True

    def test_connection_error_should_retry(self):
        exc = anthropic.APIConnectionError(message="connection failed", request=None)
        assert _should_retry_claude(exc) is True

    def test_5xx_status_should_retry(self):
        """500~599 서버 오류는 재시도."""
        exc = anthropic.APIStatusError(
            message="internal server error",
            response=_make_mock_response(500),
            body={},
        )
        assert _should_retry_claude(exc) is True

    def test_4xx_non_rate_limit_no_retry(self):
        """400 Bad Request 같은 클라이언트 오류는 재시도 안 함."""
        exc = anthropic.BadRequestError(
            message="bad request",
            response=_make_mock_response(400),
            body={},
        )
        assert _should_retry_claude(exc) is False

    def test_unknown_exception_no_retry(self):
        """알 수 없는 예외는 재시도 안 함."""
        assert _should_retry_claude(ValueError("unknown")) is False
        assert _should_retry_claude(RuntimeError("something")) is False


# ── _should_retry_gemini ──────────────────────────────────────

class TestShouldRetryGemini:

    def test_google_api_core_resource_exhausted(self):
        """google.api_core.exceptions.ResourceExhausted → 재시도."""
        try:
            from google.api_core import exceptions as gax
            exc = gax.ResourceExhausted("quota exceeded")
            assert _should_retry_gemini(exc) is True
        except ImportError:
            pytest.skip("google-api-core 미설치")

    def test_google_api_core_service_unavailable(self):
        try:
            from google.api_core import exceptions as gax
            exc = gax.ServiceUnavailable("service down")
            assert _should_retry_gemini(exc) is True
        except ImportError:
            pytest.skip("google-api-core 미설치")

    def test_generic_exception_no_retry(self):
        """일반 예외는 재시도 안 함."""
        assert _should_retry_gemini(ValueError("unknown")) is False
        assert _should_retry_gemini(RuntimeError("other")) is False

    def test_name_based_fallback_exhausted(self):
        """이름에 'Exhausted' 포함된 예외 → 재시도."""
        class FakeResourceExhausted(Exception):
            pass
        FakeResourceExhausted.__name__ = "ResourceExhausted"
        assert _should_retry_gemini(FakeResourceExhausted()) is True

    def test_name_based_fallback_unavailable(self):
        class FakeUnavailable(Exception):
            pass
        FakeUnavailable.__name__ = "ServiceUnavailable"
        assert _should_retry_gemini(FakeUnavailable()) is True


# ── 재시도 상수 ──────────────────────────────────────

class TestRetryConstants:

    def test_max_retries_positive(self):
        assert MAX_RETRIES >= 1

    def test_base_delay_positive(self):
        assert BASE_DELAY > 0

    def test_backoff_mult_gt_1(self):
        """지수 백오프: 배수가 1보다 커야 시간이 늘어남."""
        assert BACKOFF_MULT > 1.0

    def test_backoff_sequence(self):
        """실제 대기 시간 수열 검증: 1s → 2s → 4s."""
        delays = [BASE_DELAY * (BACKOFF_MULT ** i) for i in range(MAX_RETRIES)]
        assert delays == sorted(delays)          # 단조 증가
        assert delays[-1] < 60                   # 합리적 상한
