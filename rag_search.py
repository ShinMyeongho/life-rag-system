"""
하이브리드 RAG 검색 모듈.

파이프라인:
  FAISS (벡터) ─┐
                ├─ RRF 병합 ─→ Cross-encoder 리랭킹 ─→ 최종 결과
  BM25 (키워드) ─┘

사용 예:
    from rag_search import get_searcher

    searcher = get_searcher()           # 캐시됨 (최초 1회 초기화)
    results  = searcher.search("수면 부족 회복 방법", k=5)
    # [{"content": ..., "source": ..., "score": float, ...}, ...]
"""

import os
import re
from typing import Optional
from logger import get_logger

logger = get_logger(__name__)

FAISS_INDEX_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "faiss_index")

# Cross-encoder 리랭킹 모델
#
# [선택 근거]
# ❌ cross-encoder/ms-marco-MiniLM-L-6-v2  → 영어 MS MARCO 전용.
#    한국어 토큰이 대부분 [UNK] 처리되어 리랭킹 의미 없음.
# ❌ bongsoo/klue-cross-encoder-v1          → KLUE NLI(자연어 추론) 모델.
#    출력이 entailment/neutral/contradiction 레이블 logit이라
#    relevance score로 사용하기에 목적 불일치.
# ✅ mmarco-mMiniLMv2-L12-H384-v1          → MS MARCO를 한국어 포함 13개 언어로
#    번역한 mMARCO 데이터셋으로 학습된 multilingual reranker.
#    패시지 검색 relevance 점수 출력 → 목적·언어 모두 적합.
CROSS_ENCODER_MODEL = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"

# ── RRF 파라미터 ──────────────────────────────────────
RRF_K = 60   # RRF smoothing constant (논문 권장값)


def _tokenize_ko(text: str) -> list[str]:
    """간단한 한국어 토크나이저: 특수문자 제거 후 공백 분리."""
    text = re.sub(r"[^\w\s가-힣]", " ", text)
    return [t for t in text.split() if len(t) > 1]


class HybridSearcher:
    """
    FAISS 벡터 검색 + BM25 키워드 검색을 RRF로 병합하고
    Cross-encoder로 리랭킹하는 검색 엔진.
    """

    def __init__(self):
        self._vectorstore = None
        self._embeddings = None        # 쿼리 임베딩에 재사용 (모델 재로드 방지)
        self._bm25 = None
        self._docs: list[dict] = []    # {"content": str, "source": str, ...}
        # self._docs[i] ↔ FAISS 인덱스 i  (1:1 대응 보장)
        self._cross_encoder = None
        self._initialized = False

    def _load(self):
        """지연 초기화 – 첫 search() 호출 시 실행."""
        if self._initialized:
            return

        # ── FAISS 로드 ──────────────────────────────────────
        if not os.path.exists(FAISS_INDEX_DIR):
            logger.warning("FAISS 인덱스 없음: %s", FAISS_INDEX_DIR)
            self._initialized = True
            return

        try:
            from langchain_huggingface import HuggingFaceEmbeddings
            from langchain_community.vectorstores import FAISS

            self._embeddings = HuggingFaceEmbeddings(
                model_name="jhgan/ko-sroberta-multitask",
                model_kwargs={"device": "cpu"},
            )
            self._vectorstore = FAISS.load_local(
                FAISS_INDEX_DIR, self._embeddings, allow_dangerous_deserialization=True
            )
            logger.info("FAISS 로드 완료: %d 벡터", self._vectorstore.index.ntotal)
        except Exception:
            logger.exception("FAISS 로드 실패")

        # ── BM25 인덱스 구축 ──────────────────────────────────────
        if self._vectorstore is not None:
            try:
                from rank_bm25 import BM25Okapi

                # FAISS 인덱스에서 모든 문서 추출
                docstore = self._vectorstore.docstore
                index_to_id = self._vectorstore.index_to_docstore_id
                raw_docs = [docstore.search(index_to_id[i])
                            for i in range(len(index_to_id))]

                self._docs = [
                    {
                        "content":  d.page_content,
                        "source":   d.metadata.get("source", ""),
                        "category": d.metadata.get("category", ""),
                        "doc_type": d.metadata.get("doc_type", "refined"),
                    }
                    for d in raw_docs
                ]

                # 1:1 대응 검증: self._docs[i] ↔ FAISS index i 보장 확인
                # FAISS index.ntotal == len(self._docs) 이어야 안전
                faiss_total = self._vectorstore.index.ntotal
                if faiss_total != len(self._docs):
                    logger.warning(
                        "FAISS ntotal(%d) ≠ docs(%d): 인덱스 불일치 가능성",
                        faiss_total, len(self._docs),
                    )

                corpus = [_tokenize_ko(d["content"]) for d in self._docs]
                self._bm25 = BM25Okapi(corpus)
                logger.info("BM25 인덱스 구축 완료: %d 문서", len(self._docs))
            except Exception:
                logger.exception("BM25 구축 실패")

        # ── Cross-encoder 로드 ──────────────────────────────────────
        try:
            from sentence_transformers import CrossEncoder
            self._cross_encoder = CrossEncoder(CROSS_ENCODER_MODEL)
            logger.info("Cross-encoder 로드 완료: %s", CROSS_ENCODER_MODEL)
        except Exception:
            logger.warning("Cross-encoder 로드 실패 – 리랭킹 없이 진행")

        self._initialized = True

    # ── 내부 검색 함수 ──────────────────────────────────────

    def _faiss_search(self, query: str, k: int) -> list[tuple[int, float]]:
        """
        FAISS 검색 → [(doc_idx, l2_distance), ...]

        [병목 수정]
        구: similarity_search_with_score() → Document 객체 반환 → page_content 문자열 비교로
            FAISS 정수 인덱스 역추적 → O(k × n) 문자열 비교

        신: vectorstore.index.search() 로 FAISS 정수 인덱스를 직접 획득 →
            self._docs[faiss_idx] 로 O(1) 조회
            전체 복잡도 O(k) (n과 무관)
        """
        if self._vectorstore is None or self._embeddings is None:
            return []
        try:
            import numpy as np

            # 1. 쿼리 임베딩 (이미 로드된 모델 재사용)
            query_vector = np.array(
                [self._embeddings.embed_query(query)], dtype=np.float32
            )

            # 2. FAISS raw search → (distances, faiss_indices) 직접 획득
            #    distances: L2 거리, faiss_indices: FAISS 내부 정수 인덱스
            distances, faiss_indices = self._vectorstore.index.search(query_vector, k)

            # 3. FAISS 인덱스 → self._docs 인덱스 (1:1 대응)
            #    faiss_idx == self._docs 배열 인덱스 (구축 시 순서 보장)
            out = []
            for faiss_idx, dist in zip(faiss_indices[0], distances[0]):
                if faiss_idx < 0 or faiss_idx >= len(self._docs):
                    continue   # FAISS가 -1 (미검색)을 반환할 수 있음
                out.append((int(faiss_idx), float(dist)))

            return out
        except Exception:
            logger.exception("FAISS 검색 오류")
            return []

    def _bm25_search(self, query: str, k: int) -> list[tuple[int, float]]:
        """BM25 검색 → [(doc_idx, bm25_score), ...]"""
        if self._bm25 is None or not self._docs:
            return []
        try:
            tokens = _tokenize_ko(query)
            scores = self._bm25.get_scores(tokens)
            ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
            return [(idx, float(score)) for idx, score in ranked[:k] if score > 0]
        except Exception:
            logger.exception("BM25 검색 오류")
            return []

    @staticmethod
    def _rrf_merge(
        faiss_results: list[tuple[int, float]],
        bm25_results:  list[tuple[int, float]],
        faiss_weight: float = 0.6,
        bm25_weight:  float = 0.4,
    ) -> list[tuple[int, float]]:
        """
        Reciprocal Rank Fusion으로 두 결과 병합.
        RRF score = Σ weight / (RRF_K + rank)
        """
        scores: dict[int, float] = {}

        for rank, (idx, _) in enumerate(faiss_results, start=1):
            scores[idx] = scores.get(idx, 0.0) + faiss_weight / (RRF_K + rank)

        for rank, (idx, _) in enumerate(bm25_results, start=1):
            scores[idx] = scores.get(idx, 0.0) + bm25_weight / (RRF_K + rank)

        return sorted(scores.items(), key=lambda x: x[1], reverse=True)

    def _rerank(self, query: str, candidates: list[dict], top_n: int) -> list[dict]:
        """Cross-encoder로 candidates를 재정렬. 실패 시 원본 순서 유지."""
        if self._cross_encoder is None or not candidates:
            return candidates[:top_n]
        try:
            pairs = [(query, c["content"][:512]) for c in candidates]
            ce_scores = self._cross_encoder.predict(pairs)
            ranked = sorted(
                zip(ce_scores, candidates),
                key=lambda x: x[0],
                reverse=True,
            )
            results = []
            for ce_score, doc in ranked[:top_n]:
                doc = dict(doc)
                doc["ce_score"] = float(ce_score)
                results.append(doc)
            return results
        except Exception:
            logger.exception("Cross-encoder 리랭킹 오류")
            return candidates[:top_n]

    # ── 공개 인터페이스 ──────────────────────────────────────

    def search(
        self,
        query: str,
        k: int = 5,
        fetch_k: int = 15,
    ) -> list[dict]:
        """
        하이브리드 검색 (FAISS + BM25 → RRF → Cross-encoder).

        Args:
            query:   검색 쿼리
            k:       최종 반환 문서 수
            fetch_k: 리랭킹 전 후보 풀 크기 (k보다 커야 효과적)

        Returns:
            [{"content", "source", "category", "doc_type",
              "rrf_score", "ce_score"(optional)}, ...]
        """
        self._load()

        if not self._docs:
            return []

        # 1단계: 두 검색기에서 후보 수집
        faiss_res = self._faiss_search(query, k=fetch_k)
        bm25_res  = self._bm25_search(query,  k=fetch_k)

        # 2단계: RRF 병합
        merged = self._rrf_merge(faiss_res, bm25_res)

        # 3단계: 후보 풀 구성 (fetch_k개)
        candidates = []
        seen = set()
        for idx, rrf_score in merged[:fetch_k]:
            if idx in seen or idx >= len(self._docs):
                continue
            seen.add(idx)
            doc = dict(self._docs[idx])
            doc["rrf_score"] = round(rrf_score, 6)
            candidates.append(doc)

        # FAISS 단독 fallback (BM25도 없을 때)
        if not candidates and faiss_res:
            for idx, score in faiss_res[:fetch_k]:
                if idx >= len(self._docs):
                    continue
                doc = dict(self._docs[idx])
                doc["rrf_score"] = 0.0
                candidates.append(doc)

        # 4단계: Cross-encoder 리랭킹 → 최종 k개
        return self._rerank(query, candidates, top_n=k)

    def preload(self):
        """인덱스와 모델을 미리 로드합니다 (앱 시작 시 호출용)."""
        self._load()

    @property
    def is_ready(self) -> bool:
        self._load()
        return bool(self._docs)


# ── 모듈 레벨 싱글턴 ──────────────────────────────────────
_searcher: Optional[HybridSearcher] = None


def get_searcher() -> HybridSearcher:
    """
    앱 전체에서 공유하는 HybridSearcher 싱글턴을 반환.
    Streamlit 환경에서는 @st.cache_resource로 감싸서 사용하는 것을 권장.
    """
    global _searcher
    if _searcher is None:
        _searcher = HybridSearcher()
    return _searcher
