"""
Claude / Gemini API 래퍼.

지수 백오프 retry + timeout + 오류 분류를 통합 처리합니다.
각 페이지에서 직접 client.messages.create / evaluator.generate_content를
호출하는 대신 이 모듈의 함수를 사용합니다.

사용 예:
    from api_client import call_claude, call_gemini

    # Claude – 토큰 정보 포함 응답
    resp = call_claude(
        messages=[{"role": "user", "content": "안녕"}],
        system="너는 친절한 도우미야.",
        max_tokens=500,
    )
    print(resp.text)            # 응답 텍스트
    print(resp.input_tokens)    # 입력 토큰 수
    print(resp.output_tokens)   # 출력 토큰 수

    # Gemini – 텍스트만 반환
    score_text = call_gemini("이 답변을 평가해줘: ...")
"""

import os
import time
from typing import NamedTuple

import anthropic
from dotenv import load_dotenv

from logger import get_logger

load_dotenv()
logger = get_logger(__name__)

# google-genai는 선택적 의존성: 없어도 Claude 관련 기능은 동작
try:
    from google import genai as _genai
    from google.genai import types as _genai_types
    _GOOGLE_AVAILABLE = True
except ImportError:
    _genai = None          # type: ignore[assignment]
    _genai_types = None    # type: ignore[assignment]
    _GOOGLE_AVAILABLE = False


# ── 응답 타입 ──────────────────────────────────────

class ClaudeResponse(NamedTuple):
    """call_claude()의 반환값."""
    text: str
    input_tokens: int
    output_tokens: int


# ── 클라이언트 초기화 (모듈 레벨 싱글턴) ──────────────────────────────────────
_claude_client: anthropic.Anthropic | None = None
_gemini_client = None


def _get_claude() -> anthropic.Anthropic:
    global _claude_client
    if _claude_client is None:
        _claude_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    return _claude_client


def _get_gemini():
    global _gemini_client
    if not _GOOGLE_AVAILABLE:
        raise RuntimeError("google-genai 패키지가 설치되지 않았습니다: pip install google-genai")
    if _gemini_client is None:
        _gemini_client = _genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    return _gemini_client


# ── 재시도 설정 ──────────────────────────────────────
MAX_RETRIES  = 3    # 최대 재시도 횟수
BASE_DELAY   = 1.0  # 첫 대기 시간 (초)
BACKOFF_MULT = 2.0  # 지수 백오프 배수


def _should_retry_claude(exc: Exception) -> bool:
    """재시도 가능한 Claude 오류인지 판단."""
    if isinstance(exc, (
        anthropic.RateLimitError,      # 429 – 요청 한도 초과
        anthropic.APITimeoutError,     # 요청 시간 초과
        anthropic.APIConnectionError,  # 네트워크 연결 실패
    )):
        return True
    if isinstance(exc, anthropic.APIStatusError) and exc.status_code >= 500:
        return True    # 5xx 서버 오류
    return False       # AuthError, BadRequestError 등 – 재시도 불필요


def _should_retry_gemini(exc: Exception) -> bool:
    """재시도 가능한 Gemini 오류인지 판단."""
    try:
        from google.api_core import exceptions as gax
        if isinstance(exc, (
            gax.ResourceExhausted,   # 429
            gax.ServiceUnavailable,  # 503
            gax.DeadlineExceeded,    # Timeout
            gax.InternalServerError, # 500
        )):
            return True
    except ImportError:
        pass
    # 예외 이름 fallback (google.genai 포함)
    name = type(exc).__name__
    return any(k in name for k in ("Exhausted", "Unavailable", "Timeout", "Internal", "TooManyRequests"))


# ── Claude 래퍼 ──────────────────────────────────────

def call_claude(
    messages: list[dict],
    *,
    system: str | None = None,
    model: str = "claude-sonnet-4-6",
    max_tokens: int = 500,
    timeout: float = 60.0,
) -> ClaudeResponse:
    """
    Claude API 호출 (retry + timeout 포함).

    Args:
        messages:   대화 히스토리 [{"role": ..., "content": ...}, ...]
        system:     시스템 프롬프트 (선택)
        model:      사용할 Claude 모델
        max_tokens: 최대 출력 토큰 수
        timeout:    단일 요청 타임아웃 (초)

    Returns:
        ClaudeResponse(text, input_tokens, output_tokens)

    Raises:
        RuntimeError: MAX_RETRIES 소진 또는 재시도 불가 오류 시
    """
    client = _get_claude()
    kwargs: dict = {
        "model":      model,
        "max_tokens": max_tokens,
        "messages":   messages,
        "timeout":    timeout,
    }
    if system:
        kwargs["system"] = system

    delay = BASE_DELAY
    for attempt in range(1, MAX_RETRIES + 2):
        try:
            resp = client.messages.create(**kwargs)
            return ClaudeResponse(
                text=resp.content[0].text,
                input_tokens=resp.usage.input_tokens,
                output_tokens=resp.usage.output_tokens,
            )

        except Exception as exc:
            is_last = attempt > MAX_RETRIES
            if is_last or not _should_retry_claude(exc):
                logger.error(
                    "Claude 최종 실패 (시도 %d/%d): %s – %s",
                    attempt, MAX_RETRIES + 1, type(exc).__name__, exc,
                )
                raise RuntimeError(f"Claude API 오류: {exc}") from exc

            logger.warning(
                "Claude 오류 (시도 %d/%d, %.0fs 후 재시도): %s",
                attempt, MAX_RETRIES + 1, delay, exc,
            )
            time.sleep(delay)
            delay *= BACKOFF_MULT

    raise RuntimeError("call_claude: 예상치 못한 종료")   # type-checker용


# ── Gemini 래퍼 ──────────────────────────────────────

def call_gemini(
    prompt: str,
    *,
    timeout: float = 30.0,
) -> str:
    """
    Gemini API 호출 (retry + timeout 포함).

    Args:
        prompt:  입력 프롬프트
        timeout: 단일 요청 타임아웃 (초)

    Returns:
        응답 텍스트 (str)

    Raises:
        RuntimeError: MAX_RETRIES 소진 또는 재시도 불가 오류 시
    """
    client = _get_gemini()

    delay = BASE_DELAY
    for attempt in range(1, MAX_RETRIES + 2):
        try:
            resp = client.models.generate_content(
                model="gemini-1.5-flash",
                contents=prompt,
                config=_genai_types.GenerateContentConfig(
                    http_options=_genai_types.HttpOptions(timeout=int(timeout * 1000)),
                ),
            )
            return resp.text.strip()

        except Exception as exc:
            is_last = attempt > MAX_RETRIES
            if is_last or not _should_retry_gemini(exc):
                logger.error(
                    "Gemini 최종 실패 (시도 %d/%d): %s – %s",
                    attempt, MAX_RETRIES + 1, type(exc).__name__, exc,
                )
                raise RuntimeError(f"Gemini API 오류: {exc}") from exc

            logger.warning(
                "Gemini 오류 (시도 %d/%d, %.0fs 후 재시도): %s",
                attempt, MAX_RETRIES + 1, delay, exc,
            )
            time.sleep(delay)
            delay *= BACKOFF_MULT

    raise RuntimeError("call_gemini: 예상치 못한 종료")
