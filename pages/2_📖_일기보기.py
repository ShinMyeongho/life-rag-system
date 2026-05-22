import streamlit as st
import os
import calendar
from datetime import date, timedelta
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import (
    load_diary_db, load_diaries_range_db,
    load_month_goals_db, load_week_goals_db,
    mood_color, mood_emoji, goal_achievement, goal_emoji,
    calc_stability_score, stability_label,
)

st.set_page_config(page_title="나의 일기장", page_icon="📔", layout="wide")
from theme import init_page_style
init_page_style()

st.title("📖 일기 보기")

view_type = st.radio("보기 방식", ["📅 월간", "📆 주간", "📄 일간", "📈 트렌드"], horizontal=True)

if view_type == "📅 월간":
    col_y, col_m = st.columns(2)
    with col_y:
        year = st.selectbox("년도", list(range(2024, 2028)), index=2)
    with col_m:
        month = st.selectbox("월", list(range(1, 13)), index=date.today().month - 1)

    month_goals = load_month_goals_db(year, month)
    if month_goals:
        st.markdown(f"**🎯 {year}년 {month}월 목표**")
        cols = st.columns(len(month_goals))
        for i, g in enumerate(month_goals):
            with cols[i]:
                st.markdown(f"- {g}")
        st.markdown("---")

    # 월 전체를 한 번에 로드
    first_day = date(year, month, 1)
    last_day = date(year, month, calendar.monthrange(year, month)[1])
    diaries_list = load_diaries_range_db(first_day, last_day)
    diary_map = {d["date"]: d for d in diaries_list}

    cal = calendar.monthcalendar(year, month)
    days_header = ["월", "화", "수", "목", "금", "토", "일"]

    header_html = "<div style='display:grid; grid-template-columns: repeat(7, 1fr); gap:4px; margin-bottom:8px;'>"
    for d in days_header:
        header_html += f"<div style='text-align:center; font-weight:bold; color:#aaa;'>{d}</div>"
    header_html += "</div>"

    grid_html = "<div style='display:grid; grid-template-columns: repeat(7, 1fr); gap:4px;'>"
    for week in cal:
        for day in week:
            if day == 0:
                grid_html += "<div></div>"
            else:
                date_str = f"{year}-{month:02d}-{day:02d}"
                diary = diary_map.get(date_str)
                if diary:
                    color = mood_color(diary["mood"])
                    m_emoji = mood_emoji(diary["mood"])
                    pct = goal_achievement(diary)
                    g_emoji = goal_emoji(pct)
                    pct_text = f"{pct}%" if pct is not None else ""
                    grid_html += f"""
                    <div style='background:{color}22; border:2px solid {color};
                                border-radius:8px; padding:6px; text-align:center;'>
                        <div style='font-weight:bold;'>{day}</div>
                        <div>{m_emoji}</div>
                        <div style='font-size:11px;'>{g_emoji} {pct_text}</div>
                    </div>"""
                else:
                    is_today = (date_str == date.today().strftime("%Y-%m-%d"))
                    border = "2px solid #888" if is_today else "1px solid #333"
                    grid_html += f"""
                    <div style='background:#2a2a2a; border:{border};
                                border-radius:8px; padding:6px; text-align:center;'>
                        <div style='color:#666;'>{day}</div>
                    </div>"""
    grid_html += "</div>"

    st.markdown(header_html + grid_html, unsafe_allow_html=True)
    st.markdown("---")
    st.markdown("**범례**")
    col1, col2, col3, col4 = st.columns(4)
    with col1: st.markdown("🟢 기분 좋음 (8-10)")
    with col2: st.markdown("🟡 보통 (5-7)")
    with col3: st.markdown("🔴 힘든 날 (1-4)")
    with col4: st.markdown("⬜ 일기 없음")

elif view_type == "📆 주간":
    today_dt = date.today()
    monday = today_dt - timedelta(days=today_dt.weekday())
    week_start = st.date_input("주 시작일 (월요일)", value=monday)
    week_end = week_start + timedelta(days=6)

    iso = week_start.isocalendar()
    week_num = iso[1]
    week_goals = load_week_goals_db(iso[0], week_num)
    if week_goals:
        st.markdown(f"**🎯 {week_start.strftime('%m/%d')} ~ {week_end.strftime('%m/%d')} 주간 목표**")
        cols = st.columns(len(week_goals))
        for i, g in enumerate(week_goals):
            with cols[i]:
                st.markdown(f"- {g}")
        st.markdown("---")

    diaries_list = load_diaries_range_db(week_start, week_end)
    diary_map = {d["date"]: d for d in diaries_list}

    st.markdown(f"**{week_start.strftime('%m/%d')} ~ {week_end.strftime('%m/%d')}**")
    cols = st.columns(7)
    day_names = ["월", "화", "수", "목", "금", "토", "일"]

    for i, col in enumerate(cols):
        d = week_start + timedelta(days=i)
        diary = diary_map.get(d.strftime("%Y-%m-%d"))
        with col:
            st.markdown(f"**{day_names[i]}**")
            st.markdown(f"**{d.day}일**")
            if diary:
                color = mood_color(diary["mood"])
                st.markdown(
                    f"<div style='background:{color}44; border-radius:8px; padding:8px; text-align:center;'>"
                    f"{mood_emoji(diary['mood'])}<br>{diary['mood']}점</div>",
                    unsafe_allow_html=True
                )
                pct = goal_achievement(diary)
                if pct is not None:
                    st.markdown(f"{goal_emoji(pct)} {pct}%")
            else:
                st.markdown(
                    "<div style='background:#2a2a2a; border-radius:8px; padding:8px; text-align:center; color:#666;'>-</div>",
                    unsafe_allow_html=True
                )

elif view_type == "📄 일간":
    selected = st.date_input("날짜 선택", value=date.today())
    diary = load_diary_db(selected.strftime("%Y-%m-%d"))

    if diary:
        color = mood_color(diary["mood"])
        st.markdown(
            f"<div style='background:{color}22; border-left:4px solid {color}; padding:10px; border-radius:8px;'>"
            f"<b>{mood_emoji(diary['mood'])} 기분: {diary['mood']}점 | 😤 스트레스: {diary['stress']}점</b></div>",
            unsafe_allow_html=True
        )
        st.markdown("")

        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**😴 수면:** {diary['sleep']['start']} ~ {diary['sleep']['end']} ({diary['sleep']['hours']}시간)")
            st.markdown(f"**💊 아침약:** {diary['medication']['morning']['status']}")
            st.markdown(f"**💊 취침약:** {diary['medication']['night']['status']}")
            st.markdown(f"**💊 필요시:** {diary['medication']['prn']['status']}")
        with col2:
            st.markdown(f"**💪 운동:** {diary['exercise']['status']} {diary['exercise'].get('detail', '')}")
            st.markdown(f"**🍺 음주:** {diary['drinking']['status']} {diary['drinking'].get('amount', '')}")
            meals = diary['meal']
            st.markdown(f"**🍽️ 식사:** 아침({'O' if meals['morning']['eaten'] else 'X'}) 점심({'O' if meals['lunch']['eaten'] else 'X'}) 저녁({'O' if meals['dinner']['eaten'] else 'X'})")

        if diary.get("weekly_checks"):
            st.markdown("**🎯 목표 달성:**")
            for goal, done in diary["weekly_checks"].items():
                st.markdown(f"{'✅' if done else '❌'} {goal}")

        if diary.get("good_thing"):
            st.markdown(f"**🌟 오늘 잘한 것:** {diary['good_thing']}")

        if diary.get("diary"):
            st.markdown("**📝 일기**")
            diary_text_formatted = diary['diary'].replace('\n', '  \n> ')
            st.markdown(f"> {diary_text_formatted}")
    else:
        st.info("이 날은 일기가 없어.")

elif view_type == "📈 트렌드":
    col_y, col_m = st.columns(2)
    with col_y:
        year = st.selectbox("년도", list(range(2024, 2028)), index=2)
    with col_m:
        month = st.selectbox("월", list(range(1, 13)), index=date.today().month - 1)

    first_day = date(year, month, 1)
    last_day = date(year, month, calendar.monthrange(year, month)[1])
    diaries = load_diaries_range_db(first_day, last_day)

    if not diaries:
        st.info("이 달에 일기가 없어.")
    else:
        dates = [d["date"] for d in diaries]

        st.markdown("### 😊 기분 / 😤 스트레스")
        mood_data = {
            "기분": {d["date"]: d["mood"] for d in diaries},
            "스트레스": {d["date"]: d["stress"] for d in diaries},
        }
        import pandas as pd
        mood_df = pd.DataFrame(mood_data, index=dates)
        st.line_chart(mood_df)

        st.markdown("### 😴 수면 시간")
        sleep_data = {d["date"]: d["sleep"]["hours"] for d in diaries}
        sleep_df = pd.DataFrame({"수면(시간)": sleep_data})
        st.line_chart(sleep_df)

        st.markdown("### 🔋 안정 점수")
        scores = {d["date"]: calc_stability_score(d) for d in diaries}
        scores = {k: v for k, v in scores.items() if v is not None}
        if scores:
            score_df = pd.DataFrame({"안정점수": scores})
            st.line_chart(score_df)

            avg = int(sum(scores.values()) / len(scores))
            label, emoji = stability_label(avg)
            col1, col2 = st.columns(2)
            with col1:
                st.metric("이번 달 평균 안정점수", f"{avg}점")
            with col2:
                st.metric("상태", f"{emoji} {label}")

        st.markdown("### 💪 운동 / 🍺 음주")
        exercise_data = {d["date"]: 1 if d["exercise"]["status"] == "했어" else 0 for d in diaries}
        drinking_data = {d["date"]: 1 if d["drinking"]["status"] == "했어" else 0 for d in diaries}
        habit_df = pd.DataFrame({"운동": exercise_data, "음주": drinking_data})
        st.bar_chart(habit_df)
