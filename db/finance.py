"""
재정 관련 테이블 CRUD.
loans / fixed_expenses / income / ledger
"""
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


# ── 대출 ──────────────────────────────────────

DEFAULT_LOANS = [
    {"name": "대출 A", "original": 10000000, "current_amount": 10000000, "monthly": 300000, "start_month": None},
    {"name": "대출 B", "original": 5000000,  "current_amount": 5000000,  "monthly": 150000, "start_month": None},
    {"name": "대출 C", "original": 3000000,  "current_amount": 3000000,  "monthly": 100000, "start_month": None},
]


@_st_cache_data(ttl=600, show_spinner=False)
def load_loans_db():
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM loans ORDER BY id")
            rows = cursor.fetchall()
        if not rows:
            for loan in DEFAULT_LOANS:
                save_loan_db(loan)
            return DEFAULT_LOANS
        return [
            {"name": r["name"], "original": r["original"],
             "current_amount": r["current_amount"], "monthly": r["monthly"],
             "start_month": r["start_month"]}
            for r in rows
        ]
    except Exception:
        logger.error("대출 로드 오류")
        return DEFAULT_LOANS
    finally:
        if conn:
            conn.close()


def save_loan_db(loan):
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO loans (name, original, current_amount, monthly, start_month)
                VALUES (%s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    current_amount=%s, monthly=%s, updated_at=CURRENT_TIMESTAMP
            """, (
                loan["name"], loan["original"], loan["current_amount"],
                loan["monthly"], loan.get("start_month"),
                loan["current_amount"], loan["monthly"],
            ))
        conn.commit()
        load_loans_db.clear()
        return True
    except Exception:
        logger.error("대출 저장 오류: name=%s", loan.get("name"))
        return False
    finally:
        if conn:
            conn.close()


# ── 고정지출 ──────────────────────────────────────

DEFAULT_FIXED = [
    {"name": "월세",   "amount": 0},
    {"name": "관리비", "amount": 0},
    {"name": "가스비", "amount": 0},
    {"name": "전기세", "amount": 0},
    {"name": "통신비", "amount": 0},
]


@_st_cache_data(ttl=600, show_spinner=False)
def load_fixed_db():
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT name, amount FROM fixed_expenses ORDER BY id")
            rows = cursor.fetchall()
        if not rows:
            for item in DEFAULT_FIXED:
                save_fixed_item_db(item["name"], item["amount"])
            return DEFAULT_FIXED
        return [{"name": r["name"], "amount": r["amount"]} for r in rows]
    except Exception:
        logger.error("고정지출 로드 오류")
        return DEFAULT_FIXED
    finally:
        if conn:
            conn.close()


def save_fixed_item_db(name, amount):
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO fixed_expenses (name, amount)
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE amount=%s, updated_at=CURRENT_TIMESTAMP
            """, (name, amount, amount))
        conn.commit()
        load_fixed_db.clear()
        return True
    except Exception:
        logger.error("고정지출 저장 오류: name=%s", name)
        return False
    finally:
        if conn:
            conn.close()


# ── 수입 ──────────────────────────────────────

@_st_cache_data(ttl=600, show_spinner=False)
def load_income_db():
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT monthly, memo FROM income ORDER BY id DESC LIMIT 1")
            row = cursor.fetchone()
        if row:
            return {"monthly": row["monthly"], "memo": row["memo"]}
        return {"monthly": 0, "memo": "수입 없음"}
    except Exception:
        logger.error("수입 로드 오류")
        return {"monthly": 0, "memo": "수입 없음"}
    finally:
        if conn:
            conn.close()


def save_income_db(monthly, memo):
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM income LIMIT 1")
            row = cursor.fetchone()
            if row:
                cursor.execute(
                    "UPDATE income SET monthly=%s, memo=%s WHERE id=%s",
                    (monthly, memo, row["id"])
                )
            else:
                cursor.execute(
                    "INSERT INTO income (monthly, memo) VALUES (%s, %s)",
                    (monthly, memo)
                )
        conn.commit()
        load_income_db.clear()
        return True
    except Exception:
        logger.error("수입 저장 오류")
        return False
    finally:
        if conn:
            conn.close()


# ── 원장(변동지출) ──────────────────────────────────────

@_st_cache_data(ttl=300, show_spinner=False)
def load_ledger_db(month_str=None):
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            if month_str:
                cursor.execute("""
                    SELECT * FROM ledger
                    WHERE DATE_FORMAT(date, '%%Y-%%m') = %s
                    ORDER BY date DESC
                """, (month_str,))
            else:
                cursor.execute("SELECT * FROM ledger ORDER BY date DESC")
            rows = cursor.fetchall()
        return [
            {"id": r["id"], "date": str(r["date"]), "type": r["type"],
             "amount": r["amount"], "category": r["category"], "memo": r["memo"]}
            for r in rows
        ]
    except Exception:
        logger.error("원장 로드 오류: month=%s", month_str)
        return []
    finally:
        if conn:
            conn.close()


def save_ledger_db(entry):
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO ledger (date, type, amount, category, memo)
                VALUES (%s, %s, %s, %s, %s)
            """, (entry["date"], entry["type"], entry["amount"],
                  entry["category"], entry["memo"]))
        conn.commit()
        load_ledger_db.clear()
        return True
    except Exception:
        logger.error("원장 저장 오류")
        return False
    finally:
        if conn:
            conn.close()


def delete_ledger_db(entry_id):
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM ledger WHERE id = %s", (entry_id,))
        conn.commit()
        load_ledger_db.clear()
        return True
    except Exception:
        logger.error("원장 삭제 오류: id=%s", entry_id)
        return False
    finally:
        if conn:
            conn.close()


def clear_ledger_db():
    """원장 전체 삭제. 백업 복원 전 중복 방지 용도."""
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM ledger")
        conn.commit()
        load_ledger_db.clear()
        return True
    except Exception:
        logger.error("원장 전체 삭제 오류")
        return False
    finally:
        if conn:
            conn.close()
