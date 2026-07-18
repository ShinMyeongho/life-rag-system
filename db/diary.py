"""
일기(diary) 테이블 CRUD.
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


def _row_to_diary(row):
    """DB row → diary dict. 내부 공용 헬퍼."""
    return {
        "date": str(row["date"]),
        "mood": row["mood"],
        "stress": row["stress"],
        "sleep": {
            "start": str(row["sleep_start"]),
            "end":   str(row["sleep_end"]),
            "hours": row["sleep_hours"],
        },
        "medication": {
            "morning": {"status": row["med_morning"], "reason": row["med_morning_reason"]},
            "night":   {"status": row["med_night"],   "reason": row["med_night_reason"]},
            "prn":     {"status": row["med_prn"],     "reason": row["med_prn_reason"]},
        },
        "meal": {
            "morning": {"eaten": bool(row["meal_morning"]), "menu": row["meal_morning_menu"]},
            "lunch":   {"eaten": bool(row["meal_lunch"]),   "menu": row["meal_lunch_menu"]},
            "dinner":  {"eaten": bool(row["meal_dinner"]),  "menu": row["meal_dinner_menu"]},
        },
        "exercise": {
            "status": row["exercise"],
            "detail": row["exercise_detail"],
            "reason": row["exercise_reason"],
        },
        "drinking": {
            "status": row["drinking"],
            "with":   row["drinking_with"],
            "amount": row["drinking_amount"],
        },
        "weekly_checks": json.loads(row["weekly_checks"]) if row["weekly_checks"] else {},
        "good_thing": row["good_thing"],
        "diary": row["diary_text"],
    }


@_st_cache_data(ttl=300, show_spinner=False)
def load_diary_db(date_str):
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM diary WHERE date = %s", (date_str,))
            row = cursor.fetchone()
        return _row_to_diary(row) if row else None
    except Exception:
        logger.exception("일기 로드 오류: date=%s", date_str)
        return None
    finally:
        if conn:
            conn.close()


@_st_cache_data(ttl=300, show_spinner=False)
def load_diaries_range_db(start_date, end_date):
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM diary WHERE date BETWEEN %s AND %s ORDER BY date ASC",
                (start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))
            )
            rows = cursor.fetchall()
        return [_row_to_diary(row) for row in rows]
    except Exception:
        logger.exception("일기 범위 로드 오류: %s ~ %s", start_date, end_date)
        return []
    finally:
        if conn:
            conn.close()


def save_diary_db(entry):
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            sql = """
            INSERT INTO diary (
                date, mood, stress,
                sleep_start, sleep_end, sleep_hours,
                med_morning, med_morning_reason,
                med_night, med_night_reason,
                med_prn, med_prn_reason,
                meal_morning, meal_morning_menu,
                meal_lunch, meal_lunch_menu,
                meal_dinner, meal_dinner_menu,
                exercise, exercise_detail, exercise_reason,
                drinking, drinking_with, drinking_amount,
                weekly_checks, good_thing, diary_text
            ) VALUES (
                %(date)s, %(mood)s, %(stress)s,
                %(sleep_start)s, %(sleep_end)s, %(sleep_hours)s,
                %(med_morning)s, %(med_morning_reason)s,
                %(med_night)s, %(med_night_reason)s,
                %(med_prn)s, %(med_prn_reason)s,
                %(meal_morning)s, %(meal_morning_menu)s,
                %(meal_lunch)s, %(meal_lunch_menu)s,
                %(meal_dinner)s, %(meal_dinner_menu)s,
                %(exercise)s, %(exercise_detail)s, %(exercise_reason)s,
                %(drinking)s, %(drinking_with)s, %(drinking_amount)s,
                %(weekly_checks)s, %(good_thing)s, %(diary_text)s
            )
            ON DUPLICATE KEY UPDATE
                mood=%(mood)s, stress=%(stress)s,
                sleep_start=%(sleep_start)s, sleep_end=%(sleep_end)s, sleep_hours=%(sleep_hours)s,
                med_morning=%(med_morning)s, med_morning_reason=%(med_morning_reason)s,
                med_night=%(med_night)s, med_night_reason=%(med_night_reason)s,
                med_prn=%(med_prn)s, med_prn_reason=%(med_prn_reason)s,
                meal_morning=%(meal_morning)s, meal_morning_menu=%(meal_morning_menu)s,
                meal_lunch=%(meal_lunch)s, meal_lunch_menu=%(meal_lunch_menu)s,
                meal_dinner=%(meal_dinner)s, meal_dinner_menu=%(meal_dinner_menu)s,
                exercise=%(exercise)s, exercise_detail=%(exercise_detail)s, exercise_reason=%(exercise_reason)s,
                drinking=%(drinking)s, drinking_with=%(drinking_with)s, drinking_amount=%(drinking_amount)s,
                weekly_checks=%(weekly_checks)s, good_thing=%(good_thing)s, diary_text=%(diary_text)s,
                updated_at=CURRENT_TIMESTAMP
            """
            params = {
                "date":               entry["date"],
                "mood":               entry["mood"],
                "stress":             entry["stress"],
                "sleep_start":        entry["sleep"]["start"],
                "sleep_end":          entry["sleep"]["end"],
                "sleep_hours":        entry["sleep"]["hours"],
                "med_morning":        entry["medication"]["morning"]["status"],
                "med_morning_reason": entry["medication"]["morning"]["reason"],
                "med_night":          entry["medication"]["night"]["status"],
                "med_night_reason":   entry["medication"]["night"]["reason"],
                "med_prn":            entry["medication"]["prn"]["status"],
                "med_prn_reason":     entry["medication"]["prn"]["reason"],
                "meal_morning":       entry["meal"]["morning"]["eaten"],
                "meal_morning_menu":  entry["meal"]["morning"]["menu"],
                "meal_lunch":         entry["meal"]["lunch"]["eaten"],
                "meal_lunch_menu":    entry["meal"]["lunch"]["menu"],
                "meal_dinner":        entry["meal"]["dinner"]["eaten"],
                "meal_dinner_menu":   entry["meal"]["dinner"]["menu"],
                "exercise":           entry["exercise"]["status"],
                "exercise_detail":    entry["exercise"]["detail"],
                "exercise_reason":    entry["exercise"]["reason"],
                "drinking":           entry["drinking"]["status"],
                "drinking_with":      entry["drinking"]["with"],
                "drinking_amount":    entry["drinking"]["amount"],
                "weekly_checks":      json.dumps(entry["weekly_checks"], ensure_ascii=False),
                "good_thing":         entry["good_thing"],
                "diary_text":         entry["diary"],
            }
            cursor.execute(sql, params)
        conn.commit()
        # 일기 저장 후 관련 캐시 무효화
        load_diary_db.clear()
        load_diaries_range_db.clear()
        return True
    except Exception:
        logger.exception("일기 저장 오류: date=%s", entry.get("date"))
        return False
    finally:
        if conn:
            conn.close()
