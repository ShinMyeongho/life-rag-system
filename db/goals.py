"""
월간/주간 목표(monthly_goals, weekly_goals) 테이블 CRUD.
"""
import json
from logger import get_logger
from db.connection import get_db_connection

try:
    from streamlit import cache_data as _st_cache_data
except ImportError:
    def _st_cache_data(**kwargs):  # type: ignore[misc]
        def _decorator(func):
            func.clear = lambda: None
            return func
        return _decorator

logger = get_logger(__name__)


# ── 월간 목표 ──────────────────────────────────────

@_st_cache_data(ttl=300, show_spinner=False)
def load_month_goals_db(year, month):
    ym = f"{year}-{month:02d}"
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT goals FROM monthly_goals WHERE ym = %s", (ym,))
            row = cursor.fetchone()
        if row and row["goals"]:
            goals = json.loads(row["goals"]) if isinstance(row["goals"], str) else row["goals"]
            return [g for g in goals if g]
        return []
    except Exception:
        logger.exception("월간 목표 로드 오류: ym=%s", ym)
        return []
    finally:
        if conn:
            conn.close()


def save_month_goals_db(year, month, goals):
    ym = f"{year}-{month:02d}"
    conn = None
    try:
        conn = get_db_connection()
        goals_json = json.dumps(goals, ensure_ascii=False)
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO monthly_goals (ym, goals)
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE goals=%s, updated_at=CURRENT_TIMESTAMP
            """, (ym, goals_json, goals_json))
        conn.commit()
        load_month_goals_db.clear()
        return True
    except Exception:
        logger.exception("월간 목표 저장 오류: ym=%s", ym)
        return False
    finally:
        if conn:
            conn.close()


# ── 주간 목표 ──────────────────────────────────────

@_st_cache_data(ttl=300, show_spinner=False)
def load_week_goals_db(year, week):
    yw = f"{year}-{week:02d}"
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT goals FROM weekly_goals WHERE yw = %s", (yw,))
            row = cursor.fetchone()
        if row and row["goals"]:
            goals = json.loads(row["goals"]) if isinstance(row["goals"], str) else row["goals"]
            return [g for g in goals if g]
        return []
    except Exception:
        logger.exception("주간 목표 로드 오류: yw=%s", yw)
        return []
    finally:
        if conn:
            conn.close()


def save_week_goals_db(year, week, goals):
    yw = f"{year}-{week:02d}"
    conn = None
    try:
        conn = get_db_connection()
        goals_json = json.dumps(goals, ensure_ascii=False)
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO weekly_goals (yw, goals)
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE goals=%s, updated_at=CURRENT_TIMESTAMP
            """, (yw, goals_json, goals_json))
        conn.commit()
        load_week_goals_db.clear()
        return True
    except Exception:
        logger.exception("주간 목표 저장 오류: yw=%s", yw)
        return False
    finally:
        if conn:
            conn.close()
