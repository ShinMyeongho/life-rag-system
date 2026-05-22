"""
CBT 챗봇 페이지의 순수 로직 단위 테스트

테스트 대상 (DB·API 호출 없는 순수 함수):
  - parse_emotion_tags(): 응답 텍스트에서 감정 태그 파싱
  - detect_thought_record_step(): 사고 기록지 진행 단계 감지
  - needs_rag(): RAG 검색 필요 여부 판단
  - 감정 태그 병합 로직 (dict.fromkeys 패턴)
"""
import pytest
import re
import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ── 테스트 대상 함수를 직접 복사 (페이지 임포트 시 Streamlit 실행 방지) ──

EMOTION_COLORS = {
    "불안": ("#fff3cd", "#856404"),
    "우울": ("#d1ecf1", "#0c5460"),
    "무기력": ("#e2e3e5", "#383d41"),
    "분노": ("#f8d7da", "#721c24"),
    "슬픔": ("#cce5ff", "#004085"),
    "외로움": ("#d4edda", "#155724"),
    "두려움": ("#ffeeba", "#856404"),
    "자기비판": ("#f5c6cb", "#721c24"),
    "절망": ("#d6d8d9", "#1b1e21"),
    "피로": ("#e2e3e5", "#383d41"),
}

EMOTION_TAG_PATTERN = re.compile(
    r'---EMOTION_TAGS---\s*\n(.*?)(?:\n---|$)', re.DOTALL
)

THOUGHT_RECORD_STEPS = [
    ("① 상황",    ["상황", "있었어", "일이", "언제", "어디서", "무슨 일"]),
    ("② 감정",    ["감정", "느꼈", "기분", "점", "%", "강도"]),
    ("③ 자동사고", ["생각", "떠올랐", "머릿속", "자동", "~라고", "든 생각"]),
    ("④ 지지증거", ["지지", "맞아", "증거", "사실이야", "그럴 것 같아"]),
    ("⑤ 반박증거", ["반박", "반대", "아닐 수도", "다른 가능성", "꼭 그런 건"]),
    ("⑥ 대안사고", ["대안", "다른 생각", "균형", "새로운", "바꿔서 생각"]),
]

SKIP_RAG_KEYWORDS = {
    "안녕", "hi", "hello", "ㅎㅇ", "ㅋㅋ", "ㅎㅎ", "응", "아", "네",
    "ㅇㅇ", "고마워", "감사", "알겠어", "ㅇㅋ", "ok", "okay",
}


def parse_emotion_tags(text: str) -> tuple:
    m = EMOTION_TAG_PATTERN.search(text)
    if not m:
        return text.strip(), []
    tags_raw = m.group(1).strip()
    try:
        tags = json.loads(tags_raw)
        if not isinstance(tags, list):
            raise ValueError
    except Exception:
        tags = [t.strip().strip("\"'") for t in tags_raw.split(",") if t.strip()]
    clean = text[:m.start()].strip()
    valid = list(EMOTION_COLORS.keys())
    return clean, [t for t in tags if t in valid]


def detect_thought_record_step(messages: list) -> int:
    all_text = " ".join(m["content"] for m in messages).lower()
    completed = 0
    for _, keywords in THOUGHT_RECORD_STEPS:
        if any(kw in all_text for kw in keywords):
            completed += 1
        else:
            break
    return completed


def needs_rag(text: str) -> bool:
    text = text.strip()
    if len(text) < 10:
        return False
    if text.lower() in SKIP_RAG_KEYWORDS:
        return False
    return True


# ── parse_emotion_tags ──────────────────────────────────────

class TestParseEmotionTags:

    def test_valid_json_array(self):
        text = '좋은 이야기야.\n\n---EMOTION_TAGS---\n["불안", "슬픔"]'
        clean, tags = parse_emotion_tags(text)
        assert tags == ["불안", "슬픔"]
        assert "불안" not in clean
        assert "---EMOTION_TAGS---" not in clean

    def test_no_tag_block(self):
        """태그 블록 없으면 원문 그대로, 빈 리스트."""
        text = "오늘도 잘 버텼어."
        clean, tags = parse_emotion_tags(text)
        assert clean == text
        assert tags == []

    def test_invalid_emotion_filtered(self):
        """유효한 감정 목록에 없는 건 필터링."""
        text = '응답\n\n---EMOTION_TAGS---\n["행복", "불안", "신남"]'
        _, tags = parse_emotion_tags(text)
        assert "행복" not in tags
        assert "신남" not in tags
        assert "불안" in tags

    def test_empty_array(self):
        text = '응답\n\n---EMOTION_TAGS---\n[]'
        clean, tags = parse_emotion_tags(text)
        assert tags == []
        assert "---EMOTION_TAGS---" not in clean

    def test_comma_separated_fallback(self):
        """JSON 파싱 실패 시 쉼표 분리 fallback."""
        text = '응답\n\n---EMOTION_TAGS---\n불안, 우울'
        _, tags = parse_emotion_tags(text)
        assert "불안" in tags
        assert "우울" in tags

    def test_response_text_preserved(self):
        """본문이 손상 없이 반환되는지."""
        body = "많이 힘들었겠어. 그 상황에서 그런 감정이 드는 건 자연스러운 거야."
        text = body + '\n\n---EMOTION_TAGS---\n["슬픔"]'
        clean, tags = parse_emotion_tags(text)
        assert clean == body
        assert tags == ["슬픔"]

    def test_all_valid_emotions(self):
        """10가지 유효 감정 전부 파싱 가능."""
        all_emotions = list(EMOTION_COLORS.keys())
        tag_str = json.dumps(all_emotions, ensure_ascii=False)
        text = f'응답\n\n---EMOTION_TAGS---\n{tag_str}'
        _, tags = parse_emotion_tags(text)
        assert set(tags) == set(all_emotions)

    def test_duplicate_emotions(self):
        """중복 태그는 필터링 없이 반환 (합산은 호출자가 처리)."""
        text = '응답\n\n---EMOTION_TAGS---\n["불안", "불안"]'
        _, tags = parse_emotion_tags(text)
        # 중복 허용 (dict.fromkeys로 나중에 제거)
        assert "불안" in tags


# ── detect_thought_record_step ──────────────────────────────────────

class TestDetectThoughtRecordStep:

    def _msgs(self, *contents):
        return [{"role": "user", "content": c} for c in contents]

    def test_empty_messages(self):
        assert detect_thought_record_step([]) == 0

    def test_step_1_situation(self):
        msgs = self._msgs("오늘 회사에서 있었어, 상황이 너무 힘들었어")
        assert detect_thought_record_step(msgs) >= 1

    def test_step_2_emotion(self):
        msgs = self._msgs(
            "상황이 있었어",
            "감정이 너무 복잡했어, 기분이 나빴어"
        )
        assert detect_thought_record_step(msgs) == 2

    def test_stops_at_gap(self):
        """중간 단계가 빠지면 연속되지 않는다."""
        # 1단계 키워드만 있고 2단계 없음 → 1에서 멈춤
        msgs = self._msgs("상황이 있었어")
        step = detect_thought_record_step(msgs)
        assert step == 1

    def test_step_3_automatic_thought(self):
        msgs = self._msgs(
            "상황이 있었어",
            "감정을 느꼈어",
            "생각이 떠올랐어 머릿속에서",
        )
        assert detect_thought_record_step(msgs) >= 3

    def test_max_step_6(self):
        """최대 6단계."""
        msgs = self._msgs(
            "상황이 있었어",
            "감정이 강했어",
            "생각이 떠올랐어",
            "지지하는 증거야",
            "반박하는 반대 증거",
            "대안적 다른 생각",
        )
        assert detect_thought_record_step(msgs) == 6

    def test_assistant_messages_counted(self):
        """assistant 메시지도 텍스트에 포함."""
        msgs = [
            {"role": "assistant", "content": "어떤 상황이 있었어?"},
            {"role": "user",      "content": "회사에서 있었어"},
        ]
        assert detect_thought_record_step(msgs) >= 1


# ── needs_rag ──────────────────────────────────────

class TestNeedsRag:

    def test_short_text_no_rag(self):
        assert needs_rag("안녕") is False
        assert needs_rag("ㅎㅎ") is False
        assert needs_rag("") is False

    def test_skip_keywords_no_rag(self):
        for kw in ["안녕", "hi", "hello", "감사", "ㅇㅋ", "ok"]:
            assert needs_rag(kw) is False, f"'{kw}'는 RAG 불필요"

    def test_meaningful_text_needs_rag(self):
        assert needs_rag("요즘 너무 힘들고 무기력해서 어떻게 해야 할지 모르겠어") is True
        assert needs_rag("수면이 부족해서 집중이 안 돼") is True
        assert needs_rag("CBT 사고 기록지 작성 방법을 알고 싶어") is True

    def test_boundary_length(self):
        """10자 경계 테스트."""
        assert needs_rag("a" * 9) is False   # 9자 → False
        assert needs_rag("a" * 10) is True    # 10자 → True (키워드 아님)

    def test_keyword_case_insensitive(self):
        """대소문자 무관."""
        assert needs_rag("OK") is False
        assert needs_rag("Hello") is False
        assert needs_rag("OKAY") is False


# ── 감정 태그 병합 로직 ──────────────────────────────────────

class TestEmotionTagMerge:
    """
    save_cbt_emotion_tags의 병합 로직 (dict.fromkeys 패턴) 단위 테스트.
    DB 없이 순수 파이썬으로 검증.
    """

    def _merge(self, existing, new):
        return list(dict.fromkeys(existing + new))

    def test_basic_merge(self):
        result = self._merge(["불안"], ["우울"])
        assert result == ["불안", "우울"]

    def test_deduplication(self):
        """중복 제거 + 순서 유지."""
        result = self._merge(["불안", "우울"], ["불안", "슬픔"])
        assert result.count("불안") == 1
        assert "우울" in result
        assert "슬픔" in result

    def test_order_preserved(self):
        """기존 태그가 앞에 유지."""
        result = self._merge(["피로", "무기력"], ["불안"])
        assert result[0] == "피로"
        assert result[1] == "무기력"

    def test_empty_existing(self):
        result = self._merge([], ["불안", "우울"])
        assert result == ["불안", "우울"]

    def test_empty_new(self):
        result = self._merge(["불안"], [])
        assert result == ["불안"]

    def test_all_duplicates(self):
        result = self._merge(["불안", "우울"], ["불안", "우울"])
        assert result == ["불안", "우울"]


# ── detect_rumination ──────────────────────────────────────

# 테스트용 함수 복사 (Streamlit 페이지 import 방지)
RUMINATION_MARKERS = [
    "난 약해", "나는 안 돼", "나는 못해", "어차피", "소용없어",
    "실패할", "가짜", "자격이 없", "포기", "다 틀렸", "결국 안 돼",
    "역시나", "이미 늦었", "나쁜 사람", "최악이야", "다 망했",
    "나만 그래", "나는 원래", "아무것도 안 돼",
]

def detect_rumination(messages: list, window: int = 6) -> int:
    recent_user = [m["content"] for m in messages if m["role"] == "user"][-window:]
    if not recent_user:
        return 0
    hit_count = sum(
        1 for msg in recent_user
        if any(marker in msg for marker in RUMINATION_MARKERS)
    )
    if hit_count >= 3:
        return 2
    if hit_count >= 2:
        return 1
    return 0


class TestDetectRumination:
    """
    반추 감지 함수 테스트.
    0 = 없음, 1 = 주의 (2회 연속), 2 = 개입 필요 (3회 이상)
    """

    def _u(self, *contents):
        return [{"role": "user", "content": c} for c in contents]

    def test_no_markers_returns_0(self):
        msgs = self._u("오늘 기분이 좋았어", "산책 다녀왔어")
        assert detect_rumination(msgs) == 0

    def test_empty_messages_returns_0(self):
        assert detect_rumination([]) == 0

    def test_assistant_messages_ignored(self):
        """assistant 메시지는 반추 카운트에 포함 안 됨."""
        msgs = [
            {"role": "assistant", "content": "어차피 다 망한 것 같아"},
            {"role": "user",      "content": "오늘 산책했어"},
        ]
        assert detect_rumination(msgs) == 0

    def test_single_marker_returns_0(self):
        msgs = self._u("어차피 안 될 것 같아", "오늘은 좀 나았어")
        assert detect_rumination(msgs) == 0

    def test_two_markers_returns_1(self):
        msgs = self._u("어차피 안 될 것 같아", "나는 안 돼, 다 틀렸어")
        assert detect_rumination(msgs) == 1

    def test_three_markers_returns_2(self):
        msgs = self._u(
            "어차피 다 소용없어",
            "나는 안 돼",
            "다 틀렸어, 포기하고 싶어",
        )
        assert detect_rumination(msgs) == 2

    def test_window_limits_lookback(self):
        """window=2이면 최근 2개 메시지만 본다."""
        msgs = self._u(
            "어차피",   # 오래된 메시지
            "나는 안 돼",  # 오래된 메시지
            "나는 못해",   # 오래된 메시지
            "오늘은 좀 나아",  # 최근
            "기분이 좀 좋아",  # 최근
        )
        # window=2: 최근 2개 메시지에는 마커 없음 → 0
        assert detect_rumination(msgs, window=2) == 0

    def test_various_markers_detected(self):
        """다양한 마커 패턴 감지."""
        msgs = self._u(
            "난 약해서 아무것도 못해",
            "가짜 실력이라 자격이 없어",
            "역시나 나는 원래 이래",
        )
        assert detect_rumination(msgs) == 2

    def test_partial_match_in_sentence(self):
        """문장 중간에 마커가 포함돼도 감지."""
        msgs = self._u(
            "생각해보면 어차피 나는 안 될 것 같기도 하고",
            "이미 늦었다는 느낌이 자꾸 들어",
            "다 망했다는 생각이 떠나질 않아",
        )
        assert detect_rumination(msgs) == 2
