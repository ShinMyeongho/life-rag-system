"""
RAG 문서 한국어 번역 스크립트.

rag_documents 테이블에 저장된 영문 원문을 Claude API로 한국어 번역한다.
이미 한국어인 문서(is_korean() 판정)는 자동 스킵.

사용 예:
    python translate_rag.py              # 미번역 문서 전체 처리
    python translate_rag.py --estimate   # API 비용 추정만 출력 (번역 없음)
    python translate_rag.py --limit 10   # 최대 10건만 처리 (테스트용)

[비용 구조]
  원문 ~800자 + 프롬프트 오버헤드 ≈ 입력 700tok + 출력 600tok
  claude-sonnet-4-5 기준: $3/M input + $15/M output
  → 건당 약 $0.011, 100건 기준 약 $1.1
"""

import re
import argparse
from utils import get_db_connection
from api_client import call_claude


# ── 한국어 판별 ──────────────────────────────────────

def is_korean(text: str) -> bool:
    """텍스트의 20% 이상이 한글이면 한국어로 판단."""
    if not text:
        return False
    korean_chars = len(re.findall(r'[가-힣]', text))
    return korean_chars / len(text) > 0.2


# ── Claude 번역 ──────────────────────────────────────

def translate_to_korean(text: str, filename: str) -> str:
    """영문 텍스트를 한국어로 번역. 내용 없으면 빈 문자열 반환."""
    prompt = f"""다음 전문 문서를 한국어로 번역해줘.

요구사항:
1. 원문 내용을 최대한 보존하면서 자연스러운 한국어로 번역
2. 전문 용어는 한국어 용어 사용 (예: cognitive behavioral therapy → 인지행동치료)
3. 참고문헌, 저자 정보, 페이지 번호는 제외
4. 마크다운 없이 plain text로
5. 내용이 없거나 의미없는 텍스트면 "내용없음" 이라고만 써줘

문서명: {filename}

원문:
{text[:3000]}

한국어 번역:
"""
    resp = call_claude(
        messages=[{"role": "user", "content": prompt}],
        max_tokens=2000,
        timeout=90.0,
    )
    translated = resp.text.strip()
    return "" if translated == "내용없음" else translated


# ── 비용 추정 ──────────────────────────────────────

def estimate_cost(rows: list[dict]) -> dict:
    """
    번역 대상 건수 기반 Claude API 비용 추정.
    claude-sonnet-4-5 기준: $3/M input + $15/M output
    """
    chars_per_token = 4
    overhead_chars  = 400   # 프롬프트 템플릿 오버헤드

    total_input_chars  = sum(min(len(r["original_text"] or ""), 3000) + overhead_chars for r in rows)
    total_output_chars = sum(min(len(r["original_text"] or ""), 3000) for r in rows)

    input_tokens  = total_input_chars  / chars_per_token
    output_tokens = total_output_chars / chars_per_token

    return {
        "doc_count":       len(rows),
        "input_tokens":    int(input_tokens),
        "output_tokens":   int(output_tokens),
        "input_cost_usd":  round(input_tokens  / 1_000_000 * 3.0,  4),
        "output_cost_usd": round(output_tokens / 1_000_000 * 15.0, 4),
        "total_cost_usd":  round((input_tokens / 1_000_000 * 3.0)
                                 + (output_tokens / 1_000_000 * 15.0), 4),
    }


# ── 메인 로직 ──────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="RAG 문서 한국어 번역")
    parser.add_argument("--estimate", action="store_true",
                        help="비용 추정만 출력 (번역 없음)")
    parser.add_argument("--limit", type=int, default=0,
                        help="처리할 최대 건수 (0 = 전체)")
    args = parser.parse_args()

    conn = get_db_connection()

    # 번역 대상: original_korean이 NULL인 문서
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT id, filename, original_text
            FROM rag_documents
            WHERE original_korean IS NULL AND original_text IS NOT NULL
        """)
        rows = cursor.fetchall()

    if not rows:
        print("번역할 문서 없음.")
        conn.close()
        return

    # --limit 적용
    if args.limit > 0:
        rows = rows[:args.limit]

    # 비용 추정 출력
    est = estimate_cost(rows)
    print(f"\n{'─'*45}")
    print(f"  번역 대상:   {est['doc_count']}건")
    print(f"  입력 토큰:   {est['input_tokens']:,}")
    print(f"  출력 토큰:   {est['output_tokens']:,}")
    print(f"  예상 비용:   ${est['total_cost_usd']:.4f} USD")
    print(f"{'─'*45}")

    if args.estimate:
        conn.close()
        return

    confirm = input("\nClaude API로 번역 실행하시겠습니까? (yes/N): ").strip().lower()
    if confirm != "yes":
        print("취소됨.")
        conn.close()
        return

    print(f"\n🚀 한국어 번역 시작! ({len(rows)}건)")

    skipped = saved = failed = 0

    for i, row in enumerate(rows, 1):
        label = (row["filename"] or "")[:45]
        print(f"  [{i}/{len(rows)}] {label}...", end="\r")

        # 이미 한국어 → 빈 문자열로 마킹 (재시도 방지)
        if is_korean(row["original_text"] or ""):
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE rag_documents SET original_korean = '' WHERE id = %s",
                    (row["id"],)
                )
            conn.commit()
            skipped += 1
            continue

        try:
            translated = translate_to_korean(row["original_text"], row["filename"])
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE rag_documents SET original_korean = %s WHERE id = %s",
                    (translated, row["id"])
                )
            conn.commit()
            saved += 1
        except RuntimeError as e:
            print(f"\n  ❌ [{i}] API 오류 (retry 소진): {e}")
            failed += 1

    conn.close()
    print(f"\n🎉 완료! 번역 {saved}건 / 한국어 스킵 {skipped}건 / 오류 {failed}건")


if __name__ == "__main__":
    main()
