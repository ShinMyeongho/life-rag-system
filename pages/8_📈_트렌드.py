import streamlit as st
import os
import sys
from datetime import date, timedelta
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import load_diaries_range_db, calc_stability_score
from theme import init_page_style

st.set_page_config(page_title="나의 일기장", page_icon="📔", layout="wide")
init_page_style()

st.title("📈 트렌드 분석")

# ── 기간 선택 ─────────────────────────────────────────────────────────────────
today_dt = date.today()

period = st.radio(
    "📅 기간",
    ["최근 7일", "최근 14일", "최근 30일", "최근 90일", "직접 선택"],
    horizontal=True,
)

if period == "최근 7일":
    start_dt = today_dt - timedelta(days=6)
    end_dt   = today_dt
elif period == "최근 14일":
    start_dt = today_dt - timedelta(days=13)
    end_dt   = today_dt
elif period == "최근 30일":
    start_dt = today_dt - timedelta(days=29)
    end_dt   = today_dt
elif period == "최근 90일":
    start_dt = today_dt - timedelta(days=89)
    end_dt   = today_dt
else:
    c1, c2 = st.columns(2)
    with c1:
        start_dt = st.date_input("시작일", value=today_dt - timedelta(days=29))
    with c2:
        end_dt = st.date_input("종료일", value=today_dt)

diaries = load_diaries_range_db(start_dt, end_dt)

if not diaries:
    st.info(f"📭 **{start_dt} ~ {end_dt}** 기간에 일기가 없어!")
    st.stop()

# ── 데이터 정리 ───────────────────────────────────────────────────────────────
diaries_sorted = sorted(diaries, key=lambda d: d["date"])
n = len(diaries_sorted)

dates_labels = [d["date"][5:] for d in diaries_sorted]   # MM-DD
dates_full   = [d["date"]     for d in diaries_sorted]

moods    = [d["mood"]              for d in diaries_sorted]
stress   = [d["stress"]            for d in diaries_sorted]
sleeps   = [d["sleep"]["hours"]    for d in diaries_sorted]
exercise = [1 if d["exercise"]["status"] == "했어" else 0 for d in diaries_sorted]
drinking = [1 if d["drinking"]["status"] == "했어" else 0 for d in diaries_sorted]
stab     = [calc_stability_score(d) or 0 for d in diaries_sorted]

med_morning = [
    1 if d["medication"]["morning"]["status"] == "먹었어" else 0
    for d in diaries_sorted
]
med_night = [
    1 if d["medication"]["night"]["status"] == "먹었어" else 0
    for d in diaries_sorted
]

# ── 요약 지표 ─────────────────────────────────────────────────────────────────
st.markdown(f"**📊 {start_dt} ~ {end_dt} ({n}일)**")

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("😊 평균 기분",    f"{sum(moods)/n:.1f}점")
c2.metric("😤 평균 스트레스", f"{sum(stress)/n:.1f}점")
c3.metric("😴 평균 수면",    f"{sum(sleeps)/n:.1f}시간")
c4.metric("💪 운동 일수",    f"{sum(exercise)}일 / {n}일")
c5.metric("🔋 평균 안정점수", f"{sum(stab)//n}점")

st.markdown("---")

# ── 차트 탭 ───────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs(["😊 기분/스트레스", "😴 수면", "💪 생활습관", "📅 달력 히트맵"])

# ── 탭1: 기분 + 스트레스 ───────────────────────────────────────────────────────
with tab1:
    st.markdown("#### 기분 / 스트레스 추이")

    df_mood = pd.DataFrame(
        {"기분": moods, "스트레스": stress, "안정점수(÷10)": [s / 10 for s in stab]},
        index=dates_labels,
    )
    st.line_chart(df_mood, height=300)

    # 기분 분포
    st.markdown("#### 기분 점수 분포")
    bins = {str(i): moods.count(i) for i in range(1, 11)}
    df_dist = pd.DataFrame.from_dict(bins, orient="index", columns=["일수"])
    st.bar_chart(df_dist, height=200)

    # 고기분 / 저기분 일 요약
    high_days = [d["date"] for d, m in zip(diaries_sorted, moods) if m >= 8]
    low_days  = [d["date"] for d, m in zip(diaries_sorted, moods) if m <= 3]
    col_h, col_l = st.columns(2)
    with col_h:
        st.success(f"😊 **기분 좋았던 날 ({len(high_days)}일)**")
        for day in high_days[-5:]:
            st.caption(f"• {day}")
    with col_l:
        st.error(f"😔 **기분 힘들었던 날 ({len(low_days)}일)**")
        for day in low_days[-5:]:
            st.caption(f"• {day}")


# ── 탭2: 수면 ─────────────────────────────────────────────────────────────────
with tab2:
    st.markdown("#### 수면 시간 추이")

    # 권장 수면 기준선 표시
    df_sleep = pd.DataFrame(
        {"수면시간": sleeps, "권장(7h)": [7.0] * n},
        index=dates_labels,
    )
    st.line_chart(df_sleep, height=300)

    # 수면 품질 분류
    good  = sum(1 for s in sleeps if s >= 7)
    okay  = sum(1 for s in sleeps if 5 <= s < 7)
    bad   = sum(1 for s in sleeps if s < 5)

    st.markdown("#### 수면 품질 분류")
    sc1, sc2, sc3 = st.columns(3)
    sc1.metric("🟢 충분 (7h+)",    f"{good}일",  help="권장 수면량 달성")
    sc2.metric("🟡 보통 (5~7h)",   f"{okay}일",  help="최소 수면량 충족")
    sc3.metric("🔴 부족 (5h 미만)", f"{bad}일",   help="수면 부족 주의")

    if bad > 0:
        bad_dates = [d["date"] for d, s in zip(diaries_sorted, sleeps) if s < 5]
        st.warning(f"⚠️ 수면 부족 날짜: {', '.join(bad_dates)}")


# ── 탭3: 생활습관 ─────────────────────────────────────────────────────────────
with tab3:
    st.markdown("#### 운동 / 음주 / 투약 현황")

    df_habits = pd.DataFrame(
        {
            "운동":     exercise,
            "음주":     drinking,
            "아침약":   med_morning,
            "취침약":   med_night,
        },
        index=dates_labels,
    )
    st.bar_chart(df_habits, height=300)

    # 비율 요약
    st.markdown("#### 기간 내 비율")
    r1, r2, r3, r4 = st.columns(4)

    def pct_bar(col, label: str, cnt: int, total: int, good_high: bool = True):
        pct = cnt / total * 100 if total > 0 else 0
        color = "#2ecc71" if (good_high and pct >= 70) or (not good_high and pct <= 30) else \
                "#f1c40f" if (good_high and pct >= 40) or (not good_high and pct <= 60) else "#e74c3c"
        col.metric(label, f"{cnt}/{total}일 ({pct:.0f}%)")
        col.markdown(
            f"<div style='background:#eee; border-radius:4px; height:8px;'>"
            f"<div style='background:{color}; width:{pct:.0f}%; height:8px; border-radius:4px;'></div>"
            f"</div>",
            unsafe_allow_html=True,
        )

    pct_bar(r1, "💪 운동",    sum(exercise),     n, good_high=True)
    pct_bar(r2, "🍺 음주",    sum(drinking),     n, good_high=False)
    pct_bar(r3, "💊 아침약",  sum(med_morning),  n, good_high=True)
    pct_bar(r4, "💊 취침약",  sum(med_night),    n, good_high=True)


# ── 탭4: 달력 히트맵 ──────────────────────────────────────────────────────────
with tab4:
    st.markdown("#### 📅 기분 달력 히트맵")
    st.caption("날짜별 기분 점수를 달력 형태로 확인해. 색이 진할수록 기분이 좋은 날이야.")

    # 날짜 → 기분 매핑
    mood_map = {d["date"]: d["mood"] for d in diaries_sorted}

    # 표시할 월 범위 계산
    months_range: list[tuple[int, int]] = []
    cur = start_dt.replace(day=1)
    while cur <= end_dt:
        months_range.append((cur.year, cur.month))
        # 다음 달
        if cur.month == 12:
            cur = cur.replace(year=cur.year + 1, month=1)
        else:
            cur = cur.replace(month=cur.month + 1)

    import calendar

    for (yr, mo) in months_range:
        st.markdown(f"**{yr}년 {mo}월**")
        cal = calendar.monthcalendar(yr, mo)

        # 헤더
        header_cols = st.columns(7)
        for i, day_name in enumerate(["월", "화", "수", "목", "금", "토", "일"]):
            color = "#e74c3c" if day_name == "일" else "#3498db" if day_name == "토" else "#555"
            header_cols[i].markdown(
                f"<div style='text-align:center; color:{color}; font-weight:600; "
                f"font-size:0.85rem;'>{day_name}</div>",
                unsafe_allow_html=True,
            )

        # 날짜 셀
        for week in cal:
            week_cols = st.columns(7)
            for i, day in enumerate(week):
                if day == 0:
                    week_cols[i].markdown(
                        "<div style='height:44px;'></div>",
                        unsafe_allow_html=True,
                    )
                    continue

                date_str = f"{yr}-{mo:02d}-{day:02d}"
                mood_val = mood_map.get(date_str)

                if mood_val is None:
                    bg, text_color, content = "#f5f5f5", "#ccc", f"{day}"
                else:
                    # 기분 → 배경색 그라디언트 (1=빨강, 10=초록)
                    ratio = (mood_val - 1) / 9
                    r = int(231 + (46 - 231) * ratio)
                    g = int(76  + (204 - 76) * ratio)
                    b = int(60  + (113 - 60) * ratio)
                    bg = f"rgb({r},{g},{b})"
                    text_color = "white"
                    content = f"{day}<br><span style='font-size:0.7rem;'>{mood_val}점</span>"

                is_today = (date_str == today_dt.strftime("%Y-%m-%d"))
                border = "2px solid #333" if is_today else "1px solid #ddd"

                week_cols[i].markdown(
                    f"<div style='background:{bg}; border:{border}; border-radius:6px; "
                    f"text-align:center; padding:6px 2px; height:44px; color:{text_color}; "
                    f"font-size:0.85rem; line-height:1.3;'>{content}</div>",
                    unsafe_allow_html=True,
                )

        st.markdown("")   # 월 간격
