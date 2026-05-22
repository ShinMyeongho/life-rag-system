"""
db 패키지 공개 API.
하위 모듈의 모든 함수를 re-export해 기존 코드와 호환성을 유지합니다.

사용 예:
    from db import get_db_connection, load_diary_db
    from db.finance import load_loans_db
"""
from db.connection import get_db_connection

from db.diary import (
    save_diary_db,
    load_diary_db,
    load_diaries_range_db,
)

from db.goals import (
    load_month_goals_db,
    save_month_goals_db,
    load_week_goals_db,
    save_week_goals_db,
)

from db.finance import (
    load_loans_db,
    save_loan_db,
    load_fixed_db,
    save_fixed_item_db,
    load_income_db,
    save_income_db,
    load_ledger_db,
    save_ledger_db,
    delete_ledger_db,
    clear_ledger_db,
    DEFAULT_LOANS,
    DEFAULT_FIXED,
)

from db.cbt import (
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
]
