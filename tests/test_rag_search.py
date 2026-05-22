"""
rag_search.py 단위 테스트

테스트 대상:
  - _tokenize_ko(): 한국어 토크나이저
  - HybridSearcher._rrf_merge(): RRF 점수 계산 및 병합
  - HybridSearcher._rerank(): cross-encoder 없을 때 fallback
  - RRF 파라미터 상수 검증
"""
import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rag_search import _tokenize_ko, HybridSearcher, RRF_K, CROSS_ENCODER_MODEL


# ── _tokenize_ko ──────────────────────────────────────

class TestTokenizeKo:

    def test_basic_korean(self):
        tokens = _tokenize_ko("수면 부족 인지행동치료")
        assert "수면" in tokens
        assert "부족" in tokens
        assert "인지행동치료" in tokens

    def test_removes_special_chars(self):
        tokens = _tokenize_ko("CBT! 기법@#$ 소개")
        # 특수문자 제거 후 토큰화
        for t in tokens:
            assert all(c.isalnum() or '가' <= c <= '힣' for c in t), \
                f"특수문자 포함된 토큰: {t}"

    def test_short_tokens_filtered(self):
        """1글자 토큰은 제거."""
        tokens = _tokenize_ko("나 는 공 부 해")
        assert all(len(t) > 1 for t in tokens)

    def test_empty_string(self):
        assert _tokenize_ko("") == []

    def test_english_preserved(self):
        tokens = _tokenize_ko("CBT therapy")
        assert "CBT" in tokens or "therapy" in tokens

    def test_mixed_content(self):
        tokens = _tokenize_ko("수면 quality 향상 방법")
        assert len(tokens) >= 2


# ── HybridSearcher._rrf_merge ──────────────────────────────────────

class TestRRFMerge:

    def setup_method(self):
        self.s = HybridSearcher()

    def test_faiss_only(self):
        """BM25 결과 없을 때 FAISS 순서 유지."""
        faiss = [(0, 90.0), (1, 85.0), (2, 80.0)]
        merged = self.s._rrf_merge(faiss, [])
        idxs = [i for i, _ in merged]
        assert idxs[0] == 0  # FAISS 1위가 최상위

    def test_bm25_only(self):
        """FAISS 결과 없을 때 BM25 순서 유지."""
        bm25 = [(2, 5.2), (0, 4.1), (1, 3.0)]
        merged = self.s._rrf_merge([], bm25)
        idxs = [i for i, _ in merged]
        assert idxs[0] == 2  # BM25 1위가 최상위

    def test_both_sources_merged(self):
        """두 소스가 합산되어 상위에 오를 수 있다."""
        # doc 2: faiss rank3 + bm25 rank1 → 합산 높아야 함
        # doc 0: faiss rank1 + bm25 rank2
        faiss = [(0, 90.0), (1, 85.0), (2, 80.0)]
        bm25  = [(2, 5.2),  (0, 4.1),  (3, 3.0)]
        merged = self.s._rrf_merge(faiss, bm25)
        idxs = [i for i, _ in merged]
        assert 0 in idxs[:2] and 2 in idxs[:2]

    def test_rrf_scores_positive(self):
        """모든 RRF 점수는 양수."""
        faiss = [(0, 90.0), (1, 85.0)]
        bm25  = [(1, 3.0),  (2, 2.0)]
        merged = self.s._rrf_merge(faiss, bm25)
        for _, score in merged:
            assert score > 0

    def test_rrf_scores_sorted_descending(self):
        """결과는 점수 내림차순."""
        faiss = [(0, 90.0), (1, 85.0), (2, 80.0)]
        bm25  = [(2, 5.2),  (1, 4.1),  (0, 3.0)]
        merged = self.s._rrf_merge(faiss, bm25)
        scores = [s for _, s in merged]
        assert scores == sorted(scores, reverse=True)

    def test_no_duplicates(self):
        """같은 doc_idx가 중복 없이 결과에 나온다."""
        faiss = [(0, 90.0), (1, 85.0)]
        bm25  = [(0, 5.0),  (1, 4.0)]   # 같은 doc 두 번 등장
        merged = self.s._rrf_merge(faiss, bm25)
        idxs = [i for i, _ in merged]
        assert len(idxs) == len(set(idxs))  # 중복 없음

    def test_weight_effect(self):
        """FAISS 가중치 높으면 FAISS 상위 doc가 더 유리."""
        faiss = [(0, 90.0)]    # doc 0이 FAISS 1위
        bm25  = [(1, 5.0)]     # doc 1이 BM25 1위

        faiss_heavy = self.s._rrf_merge(faiss, bm25, faiss_weight=0.9, bm25_weight=0.1)
        bm25_heavy  = self.s._rrf_merge(faiss, bm25, faiss_weight=0.1, bm25_weight=0.9)

        faiss_heavy_idxs = [i for i, _ in faiss_heavy]
        bm25_heavy_idxs  = [i for i, _ in bm25_heavy]

        assert faiss_heavy_idxs[0] == 0  # FAISS 가중치 높으면 doc 0이 1위
        assert bm25_heavy_idxs[0] == 1   # BM25 가중치 높으면 doc 1이 1위

    def test_rrf_k_constant(self):
        """RRF_K = 60 (논문 권장값)."""
        assert RRF_K == 60

    def test_empty_both(self):
        assert self.s._rrf_merge([], []) == []


# ── HybridSearcher._rerank ──────────────────────────────────────

class TestRerank:

    def setup_method(self):
        self.s = HybridSearcher()
        # cross_encoder 없이 fallback 테스트
        self.s._cross_encoder = None

    def _make_docs(self, n):
        return [
            {"content": f"문서 내용 {i}", "source": f"doc{i}.pdf", "rrf_score": 1.0 / (i + 1)}
            for i in range(n)
        ]

    def test_fallback_no_cross_encoder(self):
        """cross_encoder 없으면 원본 순서대로 top_n 반환."""
        docs = self._make_docs(5)
        result = self.s._rerank("테스트 쿼리", docs, top_n=3)
        assert len(result) == 3
        assert result[0]["source"] == "doc0.pdf"

    def test_top_n_limit(self):
        docs = self._make_docs(10)
        result = self.s._rerank("쿼리", docs, top_n=4)
        assert len(result) == 4

    def test_empty_candidates(self):
        result = self.s._rerank("쿼리", [], top_n=5)
        assert result == []

    def test_top_n_larger_than_candidates(self):
        """요청한 top_n이 후보보다 많으면 가진 것만 반환."""
        docs = self._make_docs(2)
        result = self.s._rerank("쿼리", docs, top_n=10)
        assert len(result) == 2


# ── HybridSearcher 초기화 상태 ──────────────────────────────────────

class TestHybridSearcherInit:

    def test_not_initialized_at_creation(self):
        """생성 시 아직 초기화 안 됨."""
        s = HybridSearcher()
        assert s._initialized is False

    def test_embeddings_stored_on_searcher(self):
        """_embeddings가 HybridSearcher 인스턴스에 저장될 필드를 가짐."""
        s = HybridSearcher()
        assert hasattr(s, "_embeddings")

    def test_is_ready_false_without_load(self):
        """FAISS 인덱스 없으면 is_ready=False."""
        import unittest.mock as mock
        s = HybridSearcher()
        with mock.patch("os.path.exists", return_value=False):
            s._load()
        assert s.is_ready is False


# ── _faiss_search 병목 수정 검증 ──────────────────────────────────────

class TestFaissSearchBottleneck:
    """
    [병목 수정 검증]

    구현 방식이 page_content 선형 비교(O(k×n))가 아니라
    FAISS 정수 인덱스 직접 조회(O(k)) 방식인지 소스 레벨로 검증.

    실제 FAISS 인덱스 없이도 코드 구조를 검증할 수 있다.
    """

    def _get_faiss_search_source(self):
        import inspect
        return inspect.getsource(HybridSearcher._faiss_search)

    def test_no_page_content_comparison(self):
        """O(k×n) 병목 원인인 page_content 문자열 비교가 코드에 없어야 함.
        docstring에 언급되는 건 괜찮지만, 실제 코드 라인에서는 제거돼야 한다."""
        import ast
        src = self._get_faiss_search_source()

        # docstring을 제외한 실제 코드 라인만 검사
        # 들여쓰기 정규화 후 AST 파싱으로 docstring 라인 식별
        lines = src.splitlines()
        # 따옴표로 시작하는 주석/docstring 블록 제거
        in_docstring = False
        code_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('"""') or stripped.startswith("'''"):
                in_docstring = not in_docstring
                continue
            if not in_docstring and not stripped.startswith("#"):
                code_lines.append(line)

        code_only = "\n".join(code_lines)
        assert "page_content" not in code_only, (
            "_faiss_search 코드에 page_content 비교가 남아있음. "
            "FAISS 정수 인덱스 직접 조회로 교체 필요."
        )

    def test_uses_direct_index_search(self):
        """vectorstore.index.search() 직접 호출로 정수 인덱스를 획득해야 함."""
        src = self._get_faiss_search_source()
        assert "index.search" in src, (
            "vectorstore.index.search() 직접 호출이 없음. "
            "similarity_search_with_score()를 쓰면 인덱스 정보가 손실됨."
        )

    def test_no_nested_loop_over_all_docs(self):
        """
        id_to_idx.items()를 순회하는 내부 루프가 없어야 함.
        이 패턴이 O(k×n)의 원인이었다.
        """
        src = self._get_faiss_search_source()
        assert "id_to_idx.items()" not in src, (
            "id_to_idx.items() 순회가 남아있음. "
            "FAISS 인덱스 → self._docs 직접 매핑으로 교체 필요."
        )

    def test_faiss_negative_index_guard(self):
        """FAISS가 미검색 시 반환하는 -1 인덱스를 걸러내는 코드가 있어야 함."""
        src = self._get_faiss_search_source()
        assert "faiss_idx < 0" in src or "< 0" in src, (
            "FAISS -1 인덱스 가드 없음. 인덱스 미검색 시 오류 발생 가능."
        )

    def test_vectorstore_none_returns_empty(self):
        """vectorstore 없으면 빈 리스트 반환."""
        s = HybridSearcher()
        s._vectorstore = None
        s._embeddings = None
        result = s._faiss_search("테스트", k=5)
        assert result == []

    def test_faiss_search_with_mock_index(self):
        """mock FAISS 인덱스로 O(1) 조회 경로 검증."""
        import unittest.mock as mock
        import numpy as np

        s = HybridSearcher()
        s._initialized = True
        s._docs = [
            {"content": f"문서{i}", "source": f"s{i}.pdf"}
            for i in range(5)
        ]

        # mock embeddings: 쿼리 → 고정 벡터
        mock_emb = mock.MagicMock()
        mock_emb.embed_query.return_value = [0.1] * 768
        s._embeddings = mock_emb

        # mock FAISS index: search → distances, indices
        mock_index = mock.MagicMock()
        mock_index.search.return_value = (
            np.array([[1.0, 2.0, 3.0]]),   # distances
            np.array([[2,   0,   4  ]]),    # faiss indices
        )
        mock_vs = mock.MagicMock()
        mock_vs.index = mock_index
        s._vectorstore = mock_vs

        result = s._faiss_search("테스트 쿼리", k=3)

        # index.search()가 호출됐는지 확인
        mock_index.search.assert_called_once()

        # 결과가 (faiss_idx, distance) 형식인지
        assert len(result) == 3
        idxs = [idx for idx, _ in result]
        assert 2 in idxs
        assert 0 in idxs
        assert 4 in idxs

    def test_faiss_search_filters_negative_index(self):
        """FAISS가 -1을 반환하면 해당 항목은 결과에서 제외."""
        import unittest.mock as mock
        import numpy as np

        s = HybridSearcher()
        s._initialized = True
        s._docs = [{"content": f"문서{i}", "source": f"s{i}"} for i in range(3)]

        mock_emb = mock.MagicMock()
        mock_emb.embed_query.return_value = [0.0] * 768
        s._embeddings = mock_emb

        mock_index = mock.MagicMock()
        mock_index.search.return_value = (
            np.array([[0.5, 9.9]]),
            np.array([[1, -1]]),   # -1은 미검색 항목
        )
        mock_vs = mock.MagicMock()
        mock_vs.index = mock_index
        s._vectorstore = mock_vs

        result = s._faiss_search("쿼리", k=2)
        idxs = [idx for idx, _ in result]
        assert -1 not in idxs   # -1은 걸러져야 함
        assert 1 in idxs


# ── Cross-encoder 모델 선택 검증 ──────────────────────────────────────

class TestCrossEncoderModel:
    """
    [면접 준비] Cross-encoder 모델 선택 근거 테스트.

    영어 전용 모델(ms-marco-MiniLM)을 사용하면 한국어 토큰이 대부분
    [UNK] 처리되어 리랭킹이 무의미해진다. mMARCO 계열 multilingual 모델을
    사용해야 한국어 패시지 relevance를 올바르게 평가할 수 있다.
    """

    def test_not_english_only_model(self):
        """영어 전용 ms-marco 모델을 사용하지 않음."""
        assert "ms-marco-MiniLM" not in CROSS_ENCODER_MODEL, (
            "영어 전용 모델은 한국어 문서에 사용 불가. "
            "mMARCO multilingual 모델 또는 한국어 전용 모델 필요."
        )

    def test_multilingual_or_korean_model(self):
        """다국어 또는 한국어 지원 모델을 사용."""
        multilingual_hints = ["mmarco", "multilingual", "ko-", "klue", "korean", "bge"]
        model_lower = CROSS_ENCODER_MODEL.lower()
        assert any(hint in model_lower for hint in multilingual_hints), (
            f"'{CROSS_ENCODER_MODEL}'은 한국어 지원 모델이 아닐 수 있음. "
            f"힌트 중 하나가 모델명에 포함되어야 함: {multilingual_hints}"
        )

    def test_model_name_is_string(self):
        assert isinstance(CROSS_ENCODER_MODEL, str)
        assert len(CROSS_ENCODER_MODEL) > 0


# ── refine_rag 로컬 정제 로직 ──────────────────────────────────────

class TestRefineLocal:
    """
    refine_text_local()의 규칙 기반 정제 로직 테스트.
    Claude API 없이 노이즈를 제거할 수 있어야 한다.
    """

    def setup_method(self):
        from text_cleaner import refine_text_local
        self.refine = refine_text_local

    def test_removes_standalone_page_number(self):
        text = "수면 개선 방법에 대해 알아보자.\n\n42\n\n규칙적인 기상 시간이 중요하다."
        result = self.refine(text, "test.pdf")
        assert "42" not in result.split() or "42" in "수면 개선".split()
        assert "수면 개선" in result

    def test_removes_page_N_of_M(self):
        text = "CBT 기법 설명\nPage 3 of 15\n인지 재구성이란"
        result = self.refine(text, "test.pdf")
        assert "Page 3 of 15" not in result
        assert "인지 재구성" in result

    def test_removes_references_section(self):
        text = "치료 효과가 입증되었다.\n\nReferences\nBeck, A.T. (1979)..."
        result = self.refine(text, "test.pdf")
        assert "References" not in result
        assert "치료 효과" in result

    def test_removes_참고문헌(self):
        text = "자기 모니터링이 핵심이다.\n\n참고문헌\n1. 홍길동 (2020)"
        result = self.refine(text, "test.pdf")
        assert "참고문헌" not in result
        assert "자기 모니터링" in result

    def test_removes_url(self):
        text = "더 알아보려면 https://example.com/cbt 를 참조하세요. 수면 위생이란"
        result = self.refine(text, "test.pdf")
        assert "https://" not in result
        assert "수면 위생" in result

    def test_removes_email(self):
        text = "연락처: author@university.ac.kr\n주요 내용은 다음과 같다."
        result = self.refine(text, "test.pdf")
        assert "@" not in result
        assert "주요 내용" in result

    def test_preserves_core_content(self):
        """핵심 내용(수치, 방법론)은 보존."""
        text = "인지행동치료의 효과: 우울증 환자의 68%에서 증상 감소 확인. (Beck, 2019)"
        result = self.refine(text, "test.pdf")
        assert "68%" in result
        assert "인지행동치료" in result

    def test_empty_input_returns_empty(self):
        result = self.refine("", "test.pdf")
        assert result == ""

    def test_no_noise_unchanged(self):
        """노이즈 없는 텍스트는 내용이 유지된다."""
        text = "수면 부족은 인지 기능 저하를 유발한다. 하루 7-8시간 수면이 권장된다."
        result = self.refine(text, "test.pdf")
        assert "수면 부족" in result
        assert "7-8시간" in result


# ── RAG k 동적 결정 로직 ──────────────────────────────────────

class TestRagKForRange:
    """
    날짜 범위에 따라 k 값이 올바르게 결정되는지 검증.

    범위가 좁으면 (오늘 하루) 노이즈를 줄이기 위해 k=3,
    범위가 넓으면 (연간 리뷰) 더 많은 참고 문서가 필요하므로 k=10.
    """

    def setup_method(self):
        from datetime import date

        # Streamlit 임포트 없이 순수 함수만 복사
        def _rag_k_for_range(start_date, end_date) -> int:
            days = (end_date - start_date).days
            if days == 0:
                return 3
            if days <= 7:
                return 5
            if days <= 31:
                return 7
            return 10

        self.fn = _rag_k_for_range
        self.date = date

    def test_same_day_returns_3(self):
        """오늘 하루만 분석 → k=3."""
        d = self.date(2025, 5, 19)
        assert self.fn(d, d) == 3

    def test_one_week_returns_5(self):
        """7일 범위 → k=5."""
        start = self.date(2025, 5, 13)
        end = self.date(2025, 5, 19)
        assert self.fn(start, end) == 5

    def test_one_day_range_returns_5(self):
        """1일 차이(어제~오늘) → k=5 (days=1, ≤7)."""
        start = self.date(2025, 5, 18)
        end = self.date(2025, 5, 19)
        assert self.fn(start, end) == 5

    def test_one_month_returns_7(self):
        """31일 범위 → k=7."""
        start = self.date(2025, 4, 19)
        end = self.date(2025, 5, 19)  # 30일 차이
        assert self.fn(start, end) == 7

    def test_boundary_31_days_returns_7(self):
        """정확히 31일 → k=7 (상한 포함)."""
        start = self.date(2025, 4, 18)
        end = self.date(2025, 5, 19)  # 31일 차이
        assert self.fn(start, end) == 7

    def test_over_31_days_returns_10(self):
        """32일 이상 → k=10."""
        start = self.date(2025, 4, 1)
        end = self.date(2025, 5, 19)  # 48일 차이
        assert self.fn(start, end) == 10

    def test_full_year_returns_10(self):
        """연간 분석 → k=10."""
        start = self.date(2025, 1, 1)
        end = self.date(2025, 12, 31)
        assert self.fn(start, end) == 10

    def test_k_is_always_positive(self):
        """k는 항상 양수."""
        from datetime import date, timedelta
        for days in [0, 1, 7, 14, 31, 60, 365]:
            start = date(2025, 1, 1)
            end = start + timedelta(days=days)
            assert self.fn(start, end) > 0
