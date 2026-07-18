"""
pages/4_목표관리.py 목표 삭제 로직 테스트 (Streamlit AppTest).

[버그 배경]
목표 입력 위젯이 인덱스 기반 key(month_0, month_1, ...)를 사용하는데,
삭제 시 백업 리스트(st.session_state.monthly_goals)만 pop하고
위젯 상태(st.session_state["month_i"])는 정리하지 않았음.
→ Streamlit은 key 기준으로 위젯 값을 유지하므로, i번째를 지워도
  화면에는 엉뚱한 항목이 남고(마지막 항목이 사라짐), 그대로 저장하면
  잘못된 목표 리스트가 DB에 기록됨.

DB는 절대 건드리지 않음: utils의 로더를 스텁으로 교체하고,
저장 버튼은 클릭하지 않는다.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import utils

PAGE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "pages",
    "4_\U0001F3AF_목표관리.py",
)


@pytest.fixture
def app(monkeypatch):
    """DB 로더를 스텁으로 교체한 AppTest 인스턴스."""
    from streamlit.testing.v1 import AppTest

    monkeypatch.setattr(utils, "load_month_goals_db", lambda y, m: [])
    monkeypatch.setattr(utils, "load_week_goals_db", lambda y, w: [])
    return AppTest.from_file(PAGE_PATH)


def _month_values(at):
    return [ti.value for ti in at.text_input if (ti.key or "").startswith("month_")]


def _week_values(at):
    return [ti.value for ti in at.text_input if (ti.key or "").startswith("week_")]


class TestMonthlyGoalDelete:

    def test_delete_first_goal_removes_correct_item(self, app):
        """0번(A)을 지우면 화면에도 [B, C]가 남아야 한다."""
        app.session_state["monthly_goals"] = ["A", "B", "C"]
        app.session_state["weekly_goals"] = [""]
        app.run(timeout=30)
        assert _month_values(app) == ["A", "B", "C"]

        app.button(key="month_del_0").click()
        app.run(timeout=30)

        assert app.session_state["monthly_goals"] == ["B", "C"]
        assert _month_values(app) == ["B", "C"]

    def test_delete_middle_goal(self, app):
        """가운데(B)를 지우면 [A, C]가 남아야 한다."""
        app.session_state["monthly_goals"] = ["A", "B", "C"]
        app.session_state["weekly_goals"] = [""]
        app.run(timeout=30)

        app.button(key="month_del_1").click()
        app.run(timeout=30)

        assert _month_values(app) == ["A", "C"]

    def test_delete_preserves_unsaved_edits(self, app):
        """다른 칸의 수정 중이던 값은 삭제 후에도 보존돼야 한다."""
        app.session_state["monthly_goals"] = ["A", "B"]
        app.session_state["weekly_goals"] = [""]
        app.run(timeout=30)

        app.text_input(key="month_1").input("B-수정본").run(timeout=30)
        app.button(key="month_del_0").click()
        app.run(timeout=30)

        assert _month_values(app) == ["B-수정본"]

    def test_delete_last_remaining_goal_leaves_one_blank_input(self, app):
        """마지막 남은 목표를 지우면 빈 입력칸 1개가 남아야 한다."""
        app.session_state["monthly_goals"] = ["A"]
        app.session_state["weekly_goals"] = [""]
        app.run(timeout=30)

        app.button(key="month_del_0").click()
        app.run(timeout=30)

        assert _month_values(app) == [""]


class TestWeeklyGoalDelete:

    def test_delete_first_weekly_goal(self, app):
        """주간 목표도 동일한 삭제 로직 버그가 없어야 한다."""
        app.session_state["monthly_goals"] = [""]
        app.session_state["weekly_goals"] = ["운동", "독서", "명상"]
        app.run(timeout=30)

        app.button(key="week_del_0").click()
        app.run(timeout=30)

        assert app.session_state["weekly_goals"] == ["독서", "명상"]
        assert _week_values(app) == ["독서", "명상"]
