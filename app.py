import streamlit as st
import os
import pandas as pd
from datetime import date, timedelta

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.makedirs(os.path.join(_BASE_DIR, "data"), exist_ok=True)
os.makedirs(os.path.join(_BASE_DIR, "data", "goals"), exist_ok=True)

st.set_page_config(
    page_title="나의 일기장",
    page_icon="📔",
    layout="wide"
)

from theme import init_page_style
init_page_style()

from db.connection import check_db_connection
from utils import (
    load_loans_db, load_diaries_range_db, load_diary_db,
    load_week_goals_db, calc_stability_score, stability_label,
    mood_emoji, goal_achievement, goal_emoji,
)

_db_ok, _db_err = check_db_connection()
if not _db_ok:
    st.error(
        f"⚠️ **DB 연결 실패** — 데이터를 불러올 수 없어요.\n\n"
        f"`{_db_err}`\n\n"
        f"MySQL이 실행 중인지, `.env` 설정(DB_HOST / DB_PORT / DB_USER / DB_PASSWORD)이 "
        f"올바른지 확인해줘."
    )
    st.stop()

def format_won(amount):
    return f"{amount:,.0f}원"

# ── 데이터 로드 ──────────────────────────────────────
today_dt = date.today()
loans = load_loans_db()
total_original = sum(l["original"] for l in loans)
total_current  = sum(l["current_amount"] for l in loans)
total_paid     = total_original - total_current
overall_pct    = (total_paid / total_original * 100) if total_original > 0 else 0

# 최근 7일 일기
start_7 = today_dt - timedelta(days=6)
recent_diaries = load_diaries_range_db(start_7, today_dt)
diary_map = {d["date"]: d for d in recent_diaries}

# 오늘 일기 & 주간 목표
today_diary  = diary_map.get(today_dt.strftime("%Y-%m-%d"))
iso_year, week_num, _ = today_dt.isocalendar()
week_goals   = load_week_goals_db(iso_year, week_num)

st.title("📔 나의 일기장")

# ── 상단: 목표 배너 ──────────────────────────────────────
st.markdown(f"""
<div style='background: linear-gradient(135deg, #1e3a5f, #2d6a9f);
            padding: 12px 20px; border-radius: 10px; margin-bottom: 16px;'>
    <h4 style='color: #FFD700; margin: 0 0 8px 0;'>🌟 목표</h4>
    <div style='display:flex; gap:40px; align-items:center; flex-wrap:wrap;'>
        <div>
            <span style='color: white; font-size:1.1rem;'>💰 재정 목표 달성!</span><br>
            <span style='color:#aad4f5; font-size:0.85rem;'>상환 진행률: {overall_pct:.1f}%</span>
            <div style='background:#ffffff33; border-radius:10px; height:8px; margin-top:4px; width:300px;'>
                <div style='background:#FFD700; border-radius:10px; height:8px; width:{min(overall_pct, 100):.1f}%;'></div>
            </div>
        </div>
        <div><span style='color: white; font-size:1.1rem;'>🎯 장기 목표 달성!</span></div>
        <div><span style='color: white; font-size:1.1rem;'>🤖 AI/데이터 역량 쌓기!</span></div>
    </div>
</div>
""", unsafe_allow_html=True)

# ── 본문 2컬럼 ──────────────────────────────────────
col_left, col_right = st.columns([3, 2])

with col_left:
    st.markdown("### 📈 최근 7일 안정점수")

    if recent_diaries:
        score_data = {}
        for d in recent_diaries:
            s = calc_stability_score(d)
            if s is not None:
                score_data[d["date"]] = s

        if score_data:
            df = pd.DataFrame({"안정점수": score_data})
            st.line_chart(df)

            avg_score = int(sum(score_data.values()) / len(score_data))
            label, emoji = stability_label(avg_score)
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("7일 평균 안정점수", f"{avg_score}점")
            with c2:
                st.metric("상태", f"{emoji} {label}")
            with c3:
                recorded = len(recent_diaries)
                st.metric("기록 일수", f"{recorded}/7일")
        else:
            st.info("안정점수를 계산할 데이터가 없어.")
    else:
        st.info("최근 7일간 일기가 없어. 일기를 써줘!")

    # 최근 7일 간단 달력
    st.markdown("### 🗓️ 최근 7일")
    day_names = ["월", "화", "수", "목", "금", "토", "일"]
    cols = st.columns(7)
    for i, col in enumerate(cols):
        d = start_7 + timedelta(days=i)
        diary = diary_map.get(d.strftime("%Y-%m-%d"))
        with col:
            st.markdown(f"**{day_names[d.weekday()]}**")
            st.markdown(f"**{d.day}일**")
            if diary:
                color = "#2ecc71" if diary["mood"] >= 8 else "#f1c40f" if diary["mood"] >= 5 else "#e74c3c"
                st.markdown(
                    f"<div style='background:{color}44; border-radius:8px; padding:6px; text-align:center;'>"
                    f"{mood_emoji(diary['mood'])}<br><small>{diary['mood']}점</small></div>",
                    unsafe_allow_html=True
                )
            else:
                is_today = (d == today_dt)
                border = "2px solid #888" if is_today else "1px solid #333"
                st.markdown(
                    f"<div style='background:#2a2a2a; border:{border}; border-radius:8px; "
                    f"padding:6px; text-align:center; color:#666;'>-</div>",
                    unsafe_allow_html=True
                )

with col_right:
    # 오늘 상태
    st.markdown("### 📋 오늘 상태")
    if today_diary:
        score = calc_stability_score(today_diary)
        label, emoji = stability_label(score)
        st.markdown(
            f"<div style='background:#1a2a3a; border-radius:10px; padding:14px;'>"
            f"<div style='font-size:1.1rem;'>{mood_emoji(today_diary['mood'])} 기분 {today_diary['mood']}점 "
            f"| 😤 스트레스 {today_diary['stress']}점</div>"
            f"<div style='margin-top:6px; color:#aad4f5;'>😴 수면 {today_diary['sleep']['hours']}시간 "
            f"| 💊 아침약 {today_diary['medication']['morning']['status']}</div>"
            f"<div style='margin-top:6px;'>🔋 안정점수: <b>{score}점</b> {emoji} {label}</div>"
            f"</div>",
            unsafe_allow_html=True
        )
    else:
        st.info(f"오늘({today_dt.strftime('%m/%d')}) 일기가 없어!\n\n👈 일기쓰기 메뉴에서 작성해줘.")

    # 이번 주 목표
    st.markdown("### 🎯 이번 주 목표")
    if week_goals:
        monday = today_dt - timedelta(days=today_dt.weekday())
        sunday = monday + timedelta(days=6)
        st.caption(f"{monday.strftime('%m/%d')} ~ {sunday.strftime('%m/%d')}")

        # 오늘 일기의 체크 상태 반영
        today_checks = today_diary.get("weekly_checks", {}) if today_diary else {}
        for g in week_goals:
            done = today_checks.get(g, False)
            st.markdown(f"{'✅' if done else '⬜'} {g}")

        if today_diary:
            pct = goal_achievement(today_diary)
            if pct is not None:
                st.progress(pct / 100)
                st.caption(f"오늘 달성률: {pct}%")
    else:
        st.caption("이번 주 목표가 없어. 목표 관리 메뉴에서 설정해줘!")

    # 대출 요약
    st.markdown("### 💳 대출 현황")
    st.markdown(
        f"<div style='background:#1a2a3a; border-radius:10px; padding:12px;'>"
        f"남은 대출: <b>{format_won(total_current)}</b><br>"
        f"<small style='color:#aad4f5;'>전체 진행률 {overall_pct:.1f}% | 매월 {format_won(sum(l['monthly'] for l in loans))} 상환</small>"
        f"</div>",
        unsafe_allow_html=True
    )
