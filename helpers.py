"""
UI 헬퍼 및 안정점수 계산.
DB에 의존하지 않는 순수 함수 모음.
"""


# ── UI 헬퍼 ──────────────────────────────────────

def mood_color(mood):
    if mood >= 8:
        return "#2ecc71"
    elif mood >= 5:
        return "#f1c40f"
    return "#e74c3c"


def mood_emoji(mood):
    if mood >= 8:
        return "😊"
    elif mood >= 5:
        return "😐"
    return "😔"


def goal_achievement(diary):
    if not diary or "weekly_checks" not in diary:
        return None
    checks = diary["weekly_checks"]
    if not checks:
        return None
    done = sum(1 for v in checks.values() if v)
    total = len(checks)
    return int(done / total * 100) if total > 0 else 0


def goal_emoji(pct):
    if pct is None:
        return ""
    if pct >= 80:
        return "✅"
    elif pct >= 50:
        return "🔶"
    return "❌"


# ── 안정점수 ──────────────────────────────────────

def calc_stability_score(diary):
    """일기 데이터로 안정 점수 계산 (0~100). 높을수록 생활이 안정적."""
    if not diary:
        return None

    score = 0

    # 수면 (30점)
    hours = diary.get("sleep", {}).get("hours", 0)
    if hours >= 7:
        score += 30
    elif hours >= 6:
        score += 20
    elif hours >= 5:
        score += 10

    # 투약 (20점)
    med = diary.get("medication", {})
    if med.get("morning", {}).get("status") == "먹었어":
        score += 10
    if med.get("night", {}).get("status") == "먹었어":
        score += 10

    # 식사 (15점)
    meal = diary.get("meal", {})
    meal_count = sum(
        1 for key in ("morning", "lunch", "dinner")
        if meal.get(key, {}).get("eaten")
    )
    score += int(meal_count / 3 * 15)

    # 운동 (15점)
    exercise = diary.get("exercise", {}).get("status", "")
    if exercise == "했어":
        score += 15
    elif exercise == "해당없음":
        score += 10

    # 음주 (10점)
    if diary.get("drinking", {}).get("status") == "안 했어":
        score += 10

    # 스트레스 역산 (10점)
    stress = diary.get("stress", 10)
    score += max(0, int((10 - stress) / 9 * 10))

    return min(score, 100)


def stability_label(score):
    if score is None:
        return "데이터 없음", "⬜"
    if score >= 80:
        return "안정", "🟢"
    elif score >= 60:
        return "보통", "🟡"
    elif score >= 40:
        return "불안정", "🟠"
    return "위험", "🔴"
