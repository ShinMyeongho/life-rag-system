"""
CBT 세션/메시지(cbt_sessions, cbt_messages) 테이블 CRUD.
"""
import json
from logger import get_logger
from db.connection import get_db_connection

logger = get_logger(__name__)


# ── 스키마 자동 마이그레이션 ──────────────────────────────────────

def _ensure_columns():
    """
    cbt_sessions 테이블에 emotion_tags, summary 컬럼이 없으면 자동으로 추가.
    앱 기동 시 1회 호출됨.
    """
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SHOW COLUMNS FROM cbt_sessions")
            existing = {row["Field"] for row in cursor.fetchall()}

            if "emotion_tags" not in existing:
                cursor.execute(
                    "ALTER TABLE cbt_sessions ADD COLUMN emotion_tags TEXT DEFAULT NULL"
                )
                logger.info("cbt_sessions: emotion_tags 컬럼 추가")

            if "summary" not in existing:
                cursor.execute(
                    "ALTER TABLE cbt_sessions ADD COLUMN summary TEXT DEFAULT NULL"
                )
                logger.info("cbt_sessions: summary 컬럼 추가")

        conn.commit()
    except Exception:
        logger.error("cbt_sessions 스키마 마이그레이션 오류")
    finally:
        if conn:
            conn.close()


# 모듈 임포트 시 자동 실행
_ensure_columns()


# ── 세션 CRUD ──────────────────────────────────────

def create_cbt_session(session_date, title="새 대화"):
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO cbt_sessions (date, title) VALUES (%s, %s)",
                (session_date, title)
            )
            session_id = cursor.lastrowid
        conn.commit()
        return session_id
    except Exception:
        logger.error("CBT 세션 생성 오류")
        return None
    finally:
        if conn:
            conn.close()


def update_cbt_session_title(session_id, title):
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                "UPDATE cbt_sessions SET title=%s WHERE id=%s",
                (title[:200], session_id)
            )
        conn.commit()
        return True
    except Exception:
        logger.error("CBT 세션 제목 업데이트 오류: id=%s", session_id)
        return False
    finally:
        if conn:
            conn.close()


def load_cbt_sessions(limit=30):
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id, date, title, emotion_tags, created_at "
                "FROM cbt_sessions ORDER BY created_at DESC LIMIT %s",
                (limit,)
            )
            rows = cursor.fetchall()
        return [
            {
                "id":           r["id"],
                "date":         str(r["date"]),
                "title":        r["title"],
                "emotion_tags": json.loads(r["emotion_tags"]) if r.get("emotion_tags") else [],
                "created_at":   str(r["created_at"]),
            }
            for r in rows
        ]
    except Exception:
        logger.error("CBT 세션 목록 로드 오류")
        return []
    finally:
        if conn:
            conn.close()


def load_cbt_messages(session_id):
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT role, content, created_at FROM cbt_messages "
                "WHERE session_id=%s ORDER BY created_at ASC",
                (session_id,)
            )
            rows = cursor.fetchall()
        return [
            {"role": r["role"], "content": r["content"],
             "created_at": str(r["created_at"])}
            for r in rows
        ]
    except Exception:
        logger.error("CBT 메시지 로드 오류: session_id=%s", session_id)
        return []
    finally:
        if conn:
            conn.close()


def save_cbt_message(session_id, role, content):
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO cbt_messages (session_id, role, content) VALUES (%s, %s, %s)",
                (session_id, role, content)
            )
        conn.commit()
        return True
    except Exception:
        logger.error("CBT 메시지 저장 오류: session_id=%s", session_id)
        return False
    finally:
        if conn:
            conn.close()


def delete_cbt_session(session_id):
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM cbt_messages WHERE session_id=%s", (session_id,))
            cursor.execute("DELETE FROM cbt_sessions WHERE id=%s", (session_id,))
        conn.commit()
        return True
    except Exception:
        logger.error("CBT 세션 삭제 오류: id=%s", session_id)
        return False
    finally:
        if conn:
            conn.close()


# ── 감정 태그 ──────────────────────────────────────

def save_cbt_emotion_tags(session_id, tags: list[str]) -> bool:
    """세션의 감정 태그 목록을 저장 (기존 태그와 합집합)."""
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT emotion_tags FROM cbt_sessions WHERE id=%s", (session_id,)
            )
            row = cursor.fetchone()
            existing = json.loads(row["emotion_tags"]) if row and row.get("emotion_tags") else []
            merged = list(dict.fromkeys(existing + tags))   # 순서 유지 중복 제거
            cursor.execute(
                "UPDATE cbt_sessions SET emotion_tags=%s WHERE id=%s",
                (json.dumps(merged, ensure_ascii=False), session_id)
            )
        conn.commit()
        return True
    except Exception:
        logger.error("감정 태그 저장 오류: session_id=%s", session_id)
        return False
    finally:
        if conn:
            conn.close()


def load_cbt_emotion_tags(session_id) -> list[str]:
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT emotion_tags FROM cbt_sessions WHERE id=%s", (session_id,)
            )
            row = cursor.fetchone()
        if row and row.get("emotion_tags"):
            return json.loads(row["emotion_tags"])
        return []
    except Exception:
        logger.error("감정 태그 로드 오류: session_id=%s", session_id)
        return []
    finally:
        if conn:
            conn.close()


# ── 세션 요약 ──────────────────────────────────────

def save_cbt_summary(session_id, summary: str) -> bool:
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                "UPDATE cbt_sessions SET summary=%s WHERE id=%s",
                (summary, session_id)
            )
        conn.commit()
        return True
    except Exception:
        logger.error("세션 요약 저장 오류: session_id=%s", session_id)
        return False
    finally:
        if conn:
            conn.close()


def load_cbt_summary(session_id) -> str | None:
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT summary FROM cbt_sessions WHERE id=%s", (session_id,)
            )
            row = cursor.fetchone()
        return row["summary"] if row else None
    except Exception:
        logger.error("세션 요약 로드 오류: session_id=%s", session_id)
        return None
    finally:
        if conn:
            conn.close()
