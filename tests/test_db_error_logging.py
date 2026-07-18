"""
db/ 레이어 예외 로깅 규약 테스트.

[배경]
db 모듈의 except 블록이 logger.error("... 오류")만 남기고 실제 예외
(pymysql.err.OperationalError의 원인, IntegrityError 상세 등)를 통째로
버리고 있었음. 실데이터 저장 실패 시 로그(logs/app.log, 로그 페이지)에
"저장 오류"라는 문구만 남아 원인 추적이 불가능했다.

규약: rag_search.py처럼 except 블록에서는 traceback이 포함되도록
logger.exception(또는 exc_info=True)을 사용한다.

DB는 절대 건드리지 않음: get_db_connection을 예외를 던지는 스텁으로 교체.
"""
import logging
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db.cbt
import db.diary
import db.finance
import db.goals


def _raise_connection_error():
    raise RuntimeError("boom: DB connection failed (테스트용 스텁)")


CASES = [
    (db.diary, "save_diary_db", ({},)),
    (db.finance, "save_loan_db", ({},)),
    (db.finance, "save_ledger_db", ({},)),
    (db.finance, "save_income_db", (0, "")),
    (db.goals, "save_month_goals_db", (2026, 1, ["목표"])),
    (db.goals, "save_week_goals_db", (2026, 1, ["목표"])),
    (db.cbt, "save_cbt_message", (1, "user", "hi")),
    (db.cbt, "create_cbt_session", ("2026-01-01",)),
]


@pytest.mark.parametrize(
    "module,func_name,args",
    CASES,
    ids=[f"{m.__name__}.{f}" for m, f, _ in CASES],
)
def test_db_error_log_includes_traceback(monkeypatch, caplog, module, func_name, args):
    """DB 오류 시 실패를 반환하되, 로그에 예외 traceback이 포함돼야 한다."""
    monkeypatch.setattr(module, "get_db_connection", _raise_connection_error)

    with caplog.at_level(logging.ERROR, logger=module.__name__):
        result = getattr(module, func_name)(*args)

    # 실패는 False/None으로 조용히 반환 (기존 계약 유지)
    assert result in (False, None)

    error_records = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert error_records, "오류 로그가 하나도 남지 않음"
    assert any(r.exc_info for r in error_records), (
        "예외 정보(traceback) 없이 오류 메시지만 기록됨 — "
        "logger.exception()을 사용해야 원인 추적이 가능하다"
    )
