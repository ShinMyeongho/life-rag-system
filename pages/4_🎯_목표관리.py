import streamlit as st
import os
from datetime import date, timedelta
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import load_month_goals_db, load_week_goals_db, save_month_goals_db, save_week_goals_db

st.set_page_config(page_title="나의 일기장", page_icon="📔", layout="wide")
from theme import init_page_style
init_page_style()

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
            st.session_state.monthly_goals.pop(i)
            st.rerun()
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
            st.session_state.weekly_goals.pop(i)
            st.rerun()
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
