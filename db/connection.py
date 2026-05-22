"""
DB 연결 팩토리.
모든 DB 모듈이 이 함수를 공유합니다.
"""
import os
import pymysql
from dotenv import load_dotenv

load_dotenv()


def get_db_connection():
    return pymysql.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", 3306)),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "diary_db"),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=5,
    )


def check_db_connection() -> tuple[bool, str]:
    """
    DB 연결 가능 여부를 확인합니다.

    Returns:
        (True, "") — 연결 성공
        (False, 오류 메시지) — 연결 실패
    """
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
        conn.close()
        return True, ""
    except pymysql.OperationalError as e:
        host = os.getenv("DB_HOST", "localhost")
        port = os.getenv("DB_PORT", "3306")
        return False, f"MySQL 연결 실패 ({host}:{port}): {e}"
    except Exception as e:
        return False, f"DB 오류: {e}"
