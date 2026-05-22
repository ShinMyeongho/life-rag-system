"""
helpers.py 단위 테스트

테스트 대상:
  - calc_stability_score(): 점수 계산 로직
  - stability_label(): 점수 → 레이블 매핑
  - mood_emoji() / mood_color(): 기분 값 → UI 표현
  - goal_achievement(): 주간 체크리스트 달성률
  - goal_emoji(): 달성률 → 이모지
"""
import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from helpers import (
    calc_stability_score,
    stability_label,
    mood_emoji,
    mood_color,
    goal_achievement,
    goal_emoji,
)


# ── 픽스처 ──────────────────────────────────────

def _diary(
    sleep_hours=7,
    stress=5,
    med_morning="먹었어",
    med_night="먹었어",
    meal_count=3,
    exercise="했어",
    drinking="안 했어",
):
    """테스트용 일기 dict 생성 헬퍼."""
    meals = ["morning", "lunch", "dinner"]
    return {
        "sleep": {"hours": sleep_hours},
        "stress": stress,
        "medication": {
            "morning": {"status": med_morning},
            "night":   {"status": med_night},
            "prn":     {"status": ""},
        },
        "meal": {
            k: {"eaten": i < meal_count}
            for i, k in enumerate(meals)
        },
        "exercise": {"status": exercise},
        "drinking": {"status": drinking},
    }


# ── calc_stability_score ──────────────────────────────────────

class TestCalcStabilityScore:

    def test_none_returns_none(self):
        assert calc_stability_score(None) is None

    def test_empty_dict_returns_none(self):
        """빈 dict는 falsy → None 반환 (데이터 없음으로 처리)."""
        assert calc_stability_score({}) is None

    def test_perfect_diary(self):
        """모든 항목이 최적이면 100점."""
        score = calc_stability_score(_diary(
            sleep_hours=8, stress=1, med_morning="먹었어", med_night="먹었어",
            meal_count=3, exercise="했어", drinking="안 했어",
        ))
        assert score == 100

    def test_terrible_diary(self):
        """수면 0, 스트레스 10, 약 안 먹음, 식사 0, 음주 → 낮은 점수."""
        score = calc_stability_score(_diary(
            sleep_hours=0, stress=10, med_morning="안 먹었어",
            med_night="안 먹었어", meal_count=0,
            exercise="안 했어", drinking="했어",
        ))
        assert score <= 10

    def test_score_bounded_0_to_100(self):
        for kw in [
            dict(sleep_hours=10, stress=0),
            dict(sleep_hours=0, stress=10),
        ]:
            score = calc_stability_score(_diary(**kw))
            assert 0 <= score <= 100, f"점수 범위 초과: {score}"

    # 수면 부분 점수
    @pytest.mark.parametrize("hours,expected_sleep_score", [
        (7, 30), (8, 30),   # ≥7h → 30점
        (6, 20),            # ≥6h → 20점
        (5, 10),            # ≥5h → 10점
        (4, 0),             # <5h → 0점
    ])
    def test_sleep_contribution(self, hours, expected_sleep_score):
        """수면 시간별 기여 점수 검증 (다른 요소 고정)."""
        base = _diary(
            sleep_hours=hours, stress=10,
            med_morning="안 먹었어", med_night="안 먹었어",
            meal_count=0, exercise="안 했어", drinking="했어",
        )
        assert calc_stability_score(base) == expected_sleep_score

    def test_medication_contribution(self):
        """아침·저녁약 각 10점씩."""
        no_med   = calc_stability_score(_diary(sleep_hours=0, stress=10, med_morning="안 먹었어", med_night="안 먹었어", meal_count=0, exercise="안 했어", drinking="했어"))
        both_med = calc_stability_score(_diary(sleep_hours=0, stress=10, med_morning="먹었어",   med_night="먹었어",   meal_count=0, exercise="안 했어", drinking="했어"))
        assert both_med - no_med == 20

    def test_exercise_해당없음(self):
        """'해당없음'은 '했어'보다 5점 낮다."""
        did     = calc_stability_score(_diary(exercise="했어",   sleep_hours=0, stress=10, med_morning="안 먹었어", med_night="안 먹었어", meal_count=0, drinking="했어"))
        na      = calc_stability_score(_diary(exercise="해당없음", sleep_hours=0, stress=10, med_morning="안 먹었어", med_night="안 먹었어", meal_count=0, drinking="했어"))
        no_ex   = calc_stability_score(_diary(exercise="안 했어", sleep_hours=0, stress=10, med_morning="안 먹었어", med_night="안 먹었어", meal_count=0, drinking="했어"))
        assert did > na > no_ex


# ── stability_label ──────────────────────────────────────

class TestStabilityLabel:

    @pytest.mark.parametrize("score,expected_label,expected_emoji", [
        (100, "안정",   "🟢"),
        (80,  "안정",   "🟢"),
        (79,  "보통",   "🟡"),
        (60,  "보통",   "🟡"),
        (59,  "불안정", "🟠"),
        (40,  "불안정", "🟠"),
        (39,  "위험",   "🔴"),
        (0,   "위험",   "🔴"),
    ])
    def test_label_thresholds(self, score, expected_label, expected_emoji):
        label, emoji = stability_label(score)
        assert label == expected_label, f"score={score}: {label} != {expected_label}"
        assert emoji == expected_emoji

    def test_none_score(self):
        label, emoji = stability_label(None)
        assert label == "데이터 없음"
        assert emoji == "⬜"


# ── mood_emoji ──────────────────────────────────────

class TestMoodEmoji:

    @pytest.mark.parametrize("mood,expected", [
        (10, "😊"), (8, "😊"),
        (7,  "😐"), (5, "😐"),
        (4,  "😔"), (1, "😔"),
    ])
    def test_emoji_by_mood(self, mood, expected):
        assert mood_emoji(mood) == expected


# ── mood_color ──────────────────────────────────────

class TestMoodColor:

    def test_high_mood_green(self):
        assert mood_color(8) == "#2ecc71"
        assert mood_color(10) == "#2ecc71"

    def test_mid_mood_yellow(self):
        assert mood_color(5) == "#f1c40f"
        assert mood_color(7) == "#f1c40f"

    def test_low_mood_red(self):
        assert mood_color(4) == "#e74c3c"
        assert mood_color(1) == "#e74c3c"


# ── goal_achievement ──────────────────────────────────────

class TestGoalAchievement:

    def test_all_done(self):
        diary = {"weekly_checks": {"운동": True, "독서": True, "명상": True}}
        assert goal_achievement(diary) == 100

    def test_none_done(self):
        diary = {"weekly_checks": {"운동": False, "독서": False}}
        assert goal_achievement(diary) == 0

    def test_partial(self):
        diary = {"weekly_checks": {"a": True, "b": False, "c": False, "d": True}}
        assert goal_achievement(diary) == 50

    def test_empty_checks(self):
        assert goal_achievement({"weekly_checks": {}}) is None

    def test_no_weekly_checks_key(self):
        assert goal_achievement({}) is None

    def test_none_diary(self):
        assert goal_achievement(None) is None


# ── goal_emoji ──────────────────────────────────────

class TestGoalEmoji:

    @pytest.mark.parametrize("pct,expected", [
        (100, "✅"), (80, "✅"),
        (79,  "🔶"), (50, "🔶"),
        (49,  "❌"), (0,  "❌"),
        (None, ""),
    ])
    def test_emoji_by_pct(self, pct, expected):
        assert goal_emoji(pct) == expected
