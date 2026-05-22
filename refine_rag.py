"""
RAG 문서 정제 스크립트.

기본: 규칙 기반 로컬 정제 (API 비용 없음)
옵션: --claude 플래그 사용 시 Claude API로 고품질 정제 (비용 발생)

사용 예:
    python refine_rag.py              # 로컬 정제 (무료)
    python refine_rag.py --claude     # Claude 정제 (비용 발생, 실행 전 추정치 출력)
    python refine_rag.py --estimate   # 비용 추정만 (API 호출 없음)

[비용 구조]
  청크 당 ~800자 입력 + ~800자 출력 ≈ 입력 600tok + 출력 600tok
  claude-sonnet-4-5 기준: $3/M input + $15/M output
  → 청크 100개 기준 약 $0.11, 청크 1,000개 기준 약 $1.1
"""

import os
import re
import sys
import argparse

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from utils import get_db_connection
from text_cleaner import refine_text_local  # noqa: F401  (re-exported for callers)

RAG_DOCS_DIR = "rag_docs"

CATEGORIES = {
    "CBT 기반 상담 데이터셋": "cbt",
    "COCOA": "cbt",
    "depression": "depression",
    "doing what matters": "stress",
    "Sleep": "sleep",
    "wellbeing": "cbt",
    "mental_health": "mental_health",
    "finance": "finance"
}

# RecursiveCharacterTextSplitter: chunk_size=800, overlap=150
# → 문맥 연결 유지하면서 세밀한 검색 가능
splitter = RecursiveCharacterTextSplitter(
    chunk_size=800,
    chunk_overlap=150,
    separators=["\n\n", "\n", ".", " ", ""],
)


def get_category(filename: str) -> str:
    for key, val in CATEGORIES.items():
        if key.lower() in filename.lower():
            return val
    return "general"


# ── 로컬 규칙 기반 정제 ──────────────────────────────────────
# text_cleaner.refine_text_local 에서 import (외부 의존성 없음, 테스트 가능)


# ── Claude 정제 (옵션) ──────────────────────────────────────

def refine_text_with_claude(text: str, filename: str) -> str:
    """
    Claude API로 고품질 정제.
    노이즈 제거 + 문맥 흐름 정리 + 한국어 통일.
    규칙 기반으로 처리하기 어려운 복잡한 노이즈에 효과적.
    """
    from api_client import call_claude

    prompt = f"""다음은 정신건강/CBT/수면/재정 관련 전문 문서의 일부야.
이 텍스트에서 노이즈만 제거하고 핵심 내용을 최대한 보존해서 한국어로 정리해줘.

제거 대상 (이것만 제거):
- 페이지 번호, 헤더, 푸터
- 저자 정보, 출판사, ISBN
- 참고문헌 목록
- 의미 없는 반복 텍스트나 깨진 글자

보존 대상 (이것은 반드시 유지):
- 모든 구체적인 방법론, 기법, 절차
- 수치, 통계, 연구 결과
- 사례, 예시, 설명
- 핵심 개념과 정의

출력 형식: 마크다운 없이 plain text. 분량 제한 없음 (원문 내용 최대 보존).

문서명: {filename}

원문:
{text}

정제된 내용:"""

    resp = call_claude(
        messages=[{"role": "user", "content": prompt}],
        max_tokens=2000,
        timeout=90.0,
    )
    return resp.text


# ── 비용 추정 ──────────────────────────────────────

def estimate_cost(chunks: list[str]) -> dict:
    """
    Claude API 호출 비용 추정.
    claude-sonnet-4-5 기준: $3/M input + $15/M output
    """
    # 문자 4개 ≈ 1 토큰 (한국어 혼합 텍스트 기준 근사값)
    chars_per_token = 4
    total_input_chars  = sum(len(c) + 400 for c in chunks)  # 프롬프트 오버헤드 포함
    total_output_chars = sum(len(c) for c in chunks)         # 정제 후 ≈ 원문 분량

    input_tokens  = total_input_chars  / chars_per_token
    output_tokens = total_output_chars / chars_per_token

    input_cost  = input_tokens  / 1_000_000 * 3.0   # $3/M
    output_cost = output_tokens / 1_000_000 * 15.0  # $15/M
    total_cost  = input_cost + output_cost

    return {
        "chunk_count":    len(chunks),
        "input_tokens":   int(input_tokens),
        "output_tokens":  int(output_tokens),
        "input_cost_usd": round(input_cost, 4),
        "output_cost_usd": round(output_cost, 4),
        "total_cost_usd": round(total_cost, 4),
    }


# ── 메인 로직 ──────────────────────────────────────

def process_file(
    filename: str,
    filepath: str,
    conn,
    use_claude: bool,
) -> int:
    """단일 파일 처리. 저장된 청크 수 반환."""
    category = get_category(filename)
    print(f"\n📄 처리 중: {filename} [{category}]")

    try:
        if filename.endswith(".pdf"):
            loader = PyPDFLoader(filepath)
            pages  = loader.load()
            full_text = "\n".join(p.page_content for p in pages)
        else:
            with open(filepath, "r", encoding="utf-8") as f:
                full_text = f.read()

        chunks = splitter.split_text(full_text)
        chunks = [c for c in chunks if len(c.strip()) >= 100]
        print(f"  총 {len(chunks)}개 청크 (청크 크기 ~800자)")

        if not chunks:
            print("  ⚠️ 유효 청크 없음, 스킵")
            return 0

        refine_fn = refine_text_with_claude if use_claude else refine_text_local
        mode_label = "Claude" if use_claude else "로컬 규칙"

        saved = 0
        for i, chunk_text in enumerate(chunks, 1):
            print(f"  청크 {i}/{len(chunks)} 정제 중... [{mode_label}]", end="\r")
            refined = refine_fn(chunk_text, filename)

            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO rag_documents (filename, category, original_text, refined_text)
                    VALUES (%s, %s, %s, %s)
                """, (filename, category, chunk_text[:5000], refined))
            conn.commit()
            saved += 1

        print(f"  ✅ {saved}개 청크 저장 완료 [{mode_label}]          ")
        return saved

    except Exception as e:
        print(f"  ❌ 오류: {e}")
        return 0


def main():
    parser = argparse.ArgumentParser(description="RAG 문서 정제 스크립트")
    parser.add_argument("--claude",   action="store_true",
                        help="Claude API 사용 (비용 발생)")
    parser.add_argument("--estimate", action="store_true",
                        help="비용 추정만 출력 (DB 저장 없음)")
    args = parser.parse_args()

    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("SELECT DISTINCT filename FROM rag_documents")
        existing_files = {row["filename"] for row in cursor.fetchall()}

    target_files = [
        f for f in os.listdir(RAG_DOCS_DIR)
        if (f.endswith(".pdf") or f.endswith(".txt")) and f not in existing_files
    ]

    if not target_files:
        print("처리할 새 파일 없음.")
        conn.close()
        return

    # ── 비용 추정 (Claude 모드) ──────────────────────────────────────
    if args.claude or args.estimate:
        print("📊 비용 추정 중...")
        all_chunks: list[str] = []
        for filename in target_files:
            filepath = os.path.join(RAG_DOCS_DIR, filename)
            try:
                if filename.endswith(".pdf"):
                    pages = PyPDFLoader(filepath).load()
                    text  = "\n".join(p.page_content for p in pages)
                else:
                    text = open(filepath, encoding="utf-8").read()
                chunks = splitter.split_text(text)
                all_chunks.extend(c for c in chunks if len(c.strip()) >= 100)
            except Exception as e:
                print(f"  추정 오류 ({filename}): {e}")

        est = estimate_cost(all_chunks)
        print(f"\n{'─'*45}")
        print(f"  대상 파일: {len(target_files)}개")
        print(f"  총 청크:   {est['chunk_count']}개")
        print(f"  입력 토큰: {est['input_tokens']:,}")
        print(f"  출력 토큰: {est['output_tokens']:,}")
        print(f"  예상 비용: ${est['total_cost_usd']:.4f} USD")
        print(f"{'─'*45}")

        if args.estimate:
            conn.close()
            return

        confirm = input("\nClaude API로 실행하시겠습니까? (yes/N): ").strip().lower()
        if confirm != "yes":
            print("취소됨.")
            conn.close()
            return

    # ── 실행 ──────────────────────────────────────
    mode = "Claude API" if args.claude else "로컬 규칙 기반 (무료)"
    print(f"\n🚀 RAG 문서 정제 시작! [모드: {mode}]")

    total_saved = 0
    for filename in target_files:
        filepath = os.path.join(RAG_DOCS_DIR, filename)
        total_saved += process_file(filename, filepath, conn, use_claude=args.claude)

    conn.close()
    print(f"\n🎉 완료! 총 {total_saved}개 청크 저장됨.")


if __name__ == "__main__":
    main()
