import streamlit as st
import os
import re
from datetime import date, timedelta
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import load_month_goals_db, load_week_goals_db, save_month_goals_db, save_week_goals_db

st.set_page_config(page_title="나의 일기장", page_icon="📔", layout="wide")
from theme import init_page_style
init_page_style()


# ── 목표 삭제 헬퍼 ──────────────────────────────────────
# [버그 수정 배경]
# 목표 입력칸은 인덱스 기반 key(month_0, month_1, ...)를 쓰는데,
# 삭제 시 백업 리스트만 pop하면 Streamlit이 key 기준으로 위젯 값을
# 유지해서 화면에는 엉뚱한 항목이 남는다 (i번째를 지워도 마지막 항목이
# 사라진 것처럼 보임). 그 상태로 저장하면 잘못된 목표가 DB에 기록됨.
# → 삭제 시점의 '현재 입력값'으로 리스트를 재구성하고,
#   다음 실행 시작 시(위젯 생성 전) 위젯 상태를 초기화한다.

def _clear_pending_widget_reset(prefix: str) -> None:
    """직전 실행에서 목표가 삭제됐으면 인덱스 기반 위젯 상태를 초기화.
    반드시 해당 위젯들이 생성되기 전에 호출해야 한다."""
    if st.session_state.pop(f"_{prefix}_reset", False):
        for key in [k for k in st.session_state.keys()
                    if re.fullmatch(rf"{prefix}_\d+", str(k))]:
            del st.session_state[key]


def _delete_goal(prefix: str, state_key: str, index: int) -> None:
    """index번째 목표 삭제. 수정 중이던 다른 칸의 입력값도 보존한다."""
    goals = st.session_state[state_key]
    current = [st.session_state.get(f"{prefix}_{j}", v) for j, v in enumerate(goals)]
    current.pop(index)
    st.session_state[state_key] = current if current else [""]
    st.session_state[f"_{prefix}_reset"] = True
    st.rerun()


_clear_pending_widget_reset("month")
_clear_pending_widget_reset("week")

st.title("🎯 목표 관리")

today_dt = date.today()

# ── 월간 목표 ──────────────────────────────────────
st.subheader("📅 월간 목표")
existing_monthly = load_month_goals_db(today_dt.year, today_dt.month)
st.markdown(f"**{today_dt.strftime('%Y년 %m월')} 목표**")

if "monthly_goals" not in st.session_state:
    st.session_state.monthly_goals = existing_monthly if existing_monthly else [""]

monthly_goals = []
for i, val in enumerate(st.session_state.monthly_goals):
    col_input, col_del = st.columns([10, 1])
    with col_input:
        goal = st.text_input(f"월간 목표 {i+1}", value=val, key=f"month_{i}")
        monthly_goals.append(goal)
    with col_del:
        st.markdown("<div style='margin-top:28px'>", unsafe_allow_html=True)
        if st.button("🗑️", key=f"month_del_{i}", help="삭제"):
            _delete_goal("month", "monthly_goals", i)
        st.markdown("</div>", unsafe_allow_html=True)

col_empty, col_add, col_save = st.columns([6, 1, 1])
with col_add:
    if len(st.session_state.monthly_goals) < 5:
        if st.button("➕ 추가", key="month_add"):
            st.session_state.monthly_goals.append("")
            st.rerun()
with col_save:
    if st.button("💾 저장", key="month_save", type="primary"):
        goals_to_save = [g for g in monthly_goals if g.strip()]
        st.session_state.monthly_goals = goals_to_save if goals_to_save else [""]
        if save_month_goals_db(today_dt.year, today_dt.month, goals_to_save):
            st.success("✅ 월간 목표 저장됐어!")
        else:
            st.error("❌ 저장 실패!")

st.markdown("---")

# ── 주간 목표 ──────────────────────────────────────
st.subheader("📆 주간 목표")
iso_year, week_num, _ = today_dt.isocalendar()
existing_weekly = load_week_goals_db(iso_year, week_num)

monday = today_dt - timedelta(days=today_dt.weekday())
sunday = monday + timedelta(days=6)
st.markdown(f"**{monday.strftime('%m/%d')} ~ {sunday.strftime('%m/%d')} 목표**")

if "weekly_goals" not in st.session_state:
    st.session_state.weekly_goals = existing_weekly if existing_weekly else [""]

weekly_goals = []
for i, val in enumerate(st.session_state.weekly_goals):
    col_input, col_del = st.columns([10, 1])
    with col_input:
        goal = st.text_input(f"주간 목표 {i+1}", value=val, key=f"week_{i}")
        weekly_goals.append(goal)
    with col_del:
        st.markdown("<div style='margin-top:28px'>", unsafe_allow_html=True)
        if st.button("🗑️", key=f"week_del_{i}", help="삭제"):
            _delete_goal("week", "weekly_goals", i)
        st.markdown("</div>", unsafe_allow_html=True)

col_empty2, col_add2, col_save2 = st.columns([6, 1, 1])
with col_add2:
    if len(st.session_state.weekly_goals) < 5:
        if st.button("➕ 추가", key="week_add"):
            st.session_state.weekly_goals.append("")
            st.rerun()
with col_save2:
    if st.button("💾 저장", key="week_save", type="primary"):
        goals_to_save = [g for g in weekly_goals if g.strip()]
        st.session_state.weekly_goals = goals_to_save if goals_to_save else [""]
        if save_week_goals_db(iso_year, week_num, goals_to_save):
            st.success("✅ 주간 목표 저장됐어!")
        else:
            st.error("❌ 저장 실패!")
