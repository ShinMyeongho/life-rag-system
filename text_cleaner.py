"""
규칙 기반 텍스트 정제 유틸리티.

PDF에서 추출한 원문의 노이즈(페이지 번호, 헤더, 참고문헌, OCR 아티팩트)를
규칙 기반으로 제거한다. 외부 패키지 의존성 없음 (표준 라이브러리만 사용).

사용 예:
    from text_cleaner import refine_text_local

    refined = refine_text_local(raw_text, filename="doc.pdf")
"""

import re

# ── 노이즈 패턴 정의 ──────────────────────────────────────
# 각 항목: (컴파일된 패턴, 대체 문자열)
# 순서가 중요 – 위에서부터 순서대로 적용

NOISE_PATTERNS: list[tuple[re.Pattern, str]] = [
    # 페이지 번호: "- 42 -", "– 5 –" 형태 (단독 줄)
    (re.compile(r"^\s*[-–]\s*\d+\s*[-–]\s*$", re.MULTILINE), ""),

    # 페이지 번호: "Page 3", "Page 3 of 15" 형태 (단독 줄)
    (re.compile(r"^\s*Page\s+\d+(\s+of\s+\d+)?\s*$", re.MULTILINE | re.IGNORECASE), ""),

    # 페이지 번호: "3 / 15" 형태 (단독 줄)
    (re.compile(r"^\s*\d+\s*/\s*\d+\s*$", re.MULTILINE), ""),

    # 단독 줄의 숫자 (3자리 이하) → 페이지 번호로 간주
    (re.compile(r"^\s*\d{1,3}\s*$", re.MULTILINE), ""),

    # 참고문헌 섹션 이후 모두 제거 (한국어/영어 헤딩 인식)
    (re.compile(
        r"\n\s*(References|Bibliography|참고문헌|참고\s*자료|REFERENCES|BIBLIOGRAPHY)\s*\n.*",
        re.DOTALL | re.IGNORECASE,
    ), ""),

    # OCR 아티팩트: 알파벳·한글·숫자가 아닌 특수문자 3개 이상 연속
    (re.compile(r"[^\w\s가-힣]{3,}"), " "),

    # 이메일 주소
    (re.compile(r"[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}"), ""),

    # URL (http/https)
    (re.compile(r"https?://\S+"), ""),

    # DOI / ISBN / ISSN 식별자
    (re.compile(r"\b(DOI|doi|ISBN|ISSN)\s*:?\s*[\S]+"), ""),

    # 3줄 이상 연속 빈 줄 → 2줄로 압축
    (re.compile(r"\n{3,}"), "\n\n"),
]


def refine_text_local(text: str, filename: str = "") -> str:
    """
    규칙 기반 텍스트 정제 (API 호출 없음).

    NOISE_PATTERNS를 순서대로 적용해 노이즈를 제거하고,
    원문의 핵심 내용(방법론·수치·사례)을 최대한 보존한다.

    Args:
        text:     정제할 원문
        filename: 로깅용 파일명 (처리 로직에는 미사용)

    Returns:
        정제된 텍스트. 입력이 빈 문자열이면 빈 문자열 반환.
    """
    if not text or not text.strip():
        return ""

    result = text
    for pattern, replacement in NOISE_PATTERNS:
        result = pattern.sub(replacement, result)

    # 줄 끝 공백 정리
    lines = [line.rstrip() for line in result.splitlines()]
    result = "\n".join(lines).strip()

    # 정제 후 완전히 비어버리면 원문 반환 (안전망)
    return result if result else text.strip()
