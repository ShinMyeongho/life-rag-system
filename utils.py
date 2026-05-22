"""
하위 호환 레이어 (Backward-Compatibility Shim).

기존 코드가 `from utils import ...` 형태로 작동하도록
db/ 패키지와 helpers.py의 모든 공개 심볼을 재수출합니다.

새 코드에서는 직접 임포트를 권장합니다:
    from db import load_diary_db
    from db.finance import load_loans_db
    from helpers import calc_stability_score
"""

# DB 함수 전체 re-export
from db import (
    get_db_connection,
    save_diary_db,
    load_diary_db,
    load_diaries_range_db,
    load_month_goals_db,
    save_month_goals_db,
    load_week_goals_db,
    save_week_goals_db,
    load_loans_db,
    save_loan_db,
    load_fixed_db,
    save_fixed_item_db,
    load_income_db,
    save_income_db,
    load_ledger_db,
    save_ledger_db,
    delete_ledger_db, clear_ledger_db,
    DEFAULT_LOANS,
    DEFAULT_FIXED,
    create_cbt_session,
    update_cbt_session_title,
    load_cbt_sessions,
    load_cbt_messages,
    save_cbt_message,
    delete_cbt_session,
    save_cbt_emotion_tags,
    load_cbt_emotion_tags,
    save_cbt_summary,
    load_cbt_summary,
)

# UI 헬퍼 / 안정점수 re-export
from helpers import (
    mood_color,
    mood_emoji,
    goal_achievement,
    goal_emoji,
    calc_stability_score,
    stability_label,
)

__all__ = [
    # connection
    "get_db_connection",
    # diary
    "save_diary_db", "load_diary_db", "load_diaries_range_db",
    # goals
    "load_month_goals_db", "save_month_goals_db",
    "load_week_goals_db", "save_week_goals_db",
    # finance
    "load_loans_db", "save_loan_db",
    "load_fixed_db", "save_fixed_item_db",
    "load_income_db", "save_income_db",
    "load_ledger_db", "save_ledger_db", "delete_ledger_db", "clear_ledger_db",
    "DEFAULT_LOANS", "DEFAULT_FIXED",
    # cbt
    "create_cbt_session", "update_cbt_session_title",
    "load_cbt_sessions", "load_cbt_messages",
    "save_cbt_message", "delete_cbt_session",
    "save_cbt_emotion_tags", "load_cbt_emotion_tags",
    "save_cbt_summary", "load_cbt_summary",
    # helpers
    "mood_color", "mood_emoji",
    "goal_achievement", "goal_emoji",
    "calc_stability_score", "stability_label",
]
