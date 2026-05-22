import streamlit as st
import os
import sys
from datetime import date, timedelta
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import (
    load_diary_db, load_diaries_range_db,
    load_loans_db, load_fixed_db, load_income_db, load_ledger_db,
    load_month_goals_db, load_week_goals_db,
    calc_stability_score, stability_label, mood_emoji,
)
from theme import init_page_style

st.set_page_config(page_title="나의 일기장", page_icon="📔", layout="wide")
init_page_style()

today_dt = date.today()
today_str = today_dt.strftime("%Y-%m-%d")
this_month = today_dt.strftime("%Y-%m")
iso_year, week_num, _ = today_dt.isocalendar()

# ── 데이터 로드 ───────────────────────────────────────────────────────────────
today_diary    = load_diary_db(today_str) or {}
last_14_days   = load_diaries_range_db(today_dt - timedelta(days=13), today_dt)
loans          = load_loans_db()
fixed          = load_fixed_db()
income         = load_income_db()
month_ledger   = load_ledger_db(this_month)
month_goals    = load_month_goals_db(today_dt.year, today_dt.month)
week_goals     = load_week_goals_db(iso_year, week_num)

# ── 계산 ─────────────────────────────────────────────────────────────────────
# 재무
total_current      = sum(l["current_amount"] for l in loans)
total_monthly_repay = sum(l["monthly"] for l in loans)
total_fixed_amt    = sum(f["amount"] for f in fixed) + total_monthly_repay
variable_expense   = sum(e["amount"] for e in month_ledger if e["type"] == "지출")
variable_income    = sum(e["amount"] for e in month_ledger if e["type"] == "수입")
total_income_all   = income["monthly"] + variable_income
total_expense_all  = total_fixed_amt + variable_expense
month_balance      = total_income_all - total_expense_all

# 지난 14일 평균 (비교용)
diaries_14 = last_14_days  # 최대 14개
recent_7   = [d for d in diaries_14 if d["date"] >= (today_dt - timedelta(days=6)).strftime("%Y-%m-%d")]
prev_7     = [d for d in diaries_14 if d["date"] < (today_dt - timedelta(days=6)).strftime("%Y-%m-%d")]

avg_mood_now  = (sum(d["mood"] for d in recent_7)  / len(recent_7))  if recent_7  else None
avg_mood_prev = (sum(d["mood"] for d in prev_7)    / len(prev_7))    if prev_7    else None
avg_sleep_now = (sum(d["sleep"]["hours"] for d in recent_7) / len(recent_7)) if recent_7 else None

mood_delta  = round(avg_mood_now  - avg_mood_prev, 1) if (avg_mood_now is not None and avg_mood_prev is not None) else None

# 안정 점수
scores     = [s for d in recent_7 if (s := calc_stability_score(d)) is not None]
avg_score  = int(sum(scores) / len(scores)) if scores else None
stab_label = stability_label(avg_score) if avg_score is not None else ("데이터 없음", "❓")

# 오늘 기록 여부
has_diary   = bool(today_diary)
med_morning = today_diary.get("medication", {}).get("morning", {}).get("status", "") == "먹었어"
med_night   = today_diary.get("medication", {}).get("night",   {}).get("status", "") == "먹었어"
exercise_done = today_diary.get("exercise", {}).get("status", "") == "했어"


# ════════════════════════════════════════════════════════════════════════════
# 헤더
# ════════════════════════════════════════════════════════════════════════════
weekday_ko = ["월", "화", "수", "목", "금", "토", "일"][today_dt.weekday()]
st.markdown(
    f"## 🏠 홈  "
    f"<span style='font-size:1rem; color:#888; font-weight:normal;'>"
    f"{today_dt.strftime('%Y년 %m월 %d일')} ({weekday_ko})"
    f"</span>",
    unsafe_allow_html=True,
)

# ── 미기록 경고 배너 ─────────────────────────────────────────────────────────
if not has_diary:
    st.warning("📝 **오늘 일기를 아직 안 썼어!** 지금 기록하러 가볼까?")

# ════════════════════════════════════════════════════════════════════════════
# 섹션 1: 오늘 상태 칩
# ════════════════════════════════════════════════════════════════════════════
st.markdown("### 📋 오늘 체크리스트")

def status_chip(label: str, done: bool) -> str:
    color  = "#2ecc71" if done else "#e74c3c"
    icon   = "✅" if done else "❌"
    bg     = "#e8faf0" if done else "#fdecea"
    return (
        f"<span style='background:{bg}; border:1.5px solid {color}; "
        f"border-radius:20px; padding:4px 14px; margin:4px; "
        f"font-size:0.9rem; color:{color}; font-weight:600;'>"
        f"{icon} {label}</span>"
    )

chips_html = "".join([
    status_chip("일기 작성",   has_diary),
    status_chip("아침약",       med_morning),
    status_chip("취침약",       med_night),
    status_chip("운동",         exercise_done),
])
st.markdown(f"<div style='margin:8px 0 16px 0;'>{chips_html}</div>", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════════════
# 섹션 2: 핵심 지표 4개
# ════════════════════════════════════════════════════════════════════════════
st.markdown("### 📊 이번 주 핵심 지표")
c1, c2, c3, c4 = st.columns(4)

with c1:
    if avg_mood_now is not None:
        emoji = mood_emoji(round(avg_mood_now))
        delta_str = f"{mood_delta:+.1f}" if mood_delta is not None else None
        st.metric(f"{emoji} 평균 기분", f"{avg_mood_now:.1f}점", delta=delta_str)
    else:
        st.metric("😐 평균 기분", "기록 없음")

with c2:
    if avg_sleep_now is not None:
        sleep_color = "normal" if avg_sleep_now >= 7 else "inverse"
        st.metric("😴 평균 수면", f"{avg_sleep_now:.1f}시간")
    else:
        st.metric("😴 평균 수면", "기록 없음")

with c3:
    balance_color = "normal" if month_balance >= 0 else "inverse"
    st.metric("💰 이번 달 잔액", f"{month_balance:,.0f}원")

with c4:
    if avg_score is not None:
        label_text, label_emoji = stab_label
        st.metric("🔋 안정 점수", f"{avg_score}점", help=f"{label_emoji} {label_text}")
        st.progress(avg_score / 100)
    else:
        st.metric("🔋 안정 점수", "기록 없음")

st.markdown("---")

# ════════════════════════════════════════════════════════════════════════════
# 섹션 3: 최근 14일 트렌드 차트 (기분 + 수면)
# ════════════════════════════════════════════════════════════════════════════
st.markdown("### 📈 최근 14일 트렌드")

if len(diaries_14) >= 2:
    chart_col1, chart_col2 = st.columns(2)

    # 날짜 정렬
    diaries_sorted = sorted(diaries_14, key=lambda d: d["date"])
    dates  = [d["date"][5:] for d in diaries_sorted]   # MM-DD
    moods  = [d["mood"]              for d in diaries_sorted]
    stress = [d["stress"]            for d in diaries_sorted]
    sleeps = [d["sleep"]["hours"]    for d in diaries_sorted]

    with chart_col1:
        st.caption("😊 기분 / 😤 스트레스 (1~10점)")
        df_mood = pd.DataFrame({"기분": moods, "스트레스": stress}, index=dates)
        st.line_chart(df_mood, height=200)

    with chart_col2:
        st.caption("😴 수면 시간 (시간)")
        df_sleep = pd.DataFrame({"수면": sleeps}, index=dates)
        st.bar_chart(df_sleep, height=200)
else:
    st.info("📊 차트를 보려면 최소 2일 이상의 일기가 필요해!")

st.markdown("---")

# ════════════════════════════════════════════════════════════════════════════
# 섹션 4: 재무 스냅샷 + 목표 현황 (좌/우)
# ════════════════════════════════════════════════════════════════════════════
left_col, right_col = st.columns(2)

with left_col:
    st.markdown("### 💳 재무 스냅샷")

    # 대출 전체 진행률
    total_original = sum(l["original"] for l in loans)
    total_paid     = total_original - total_current
    repay_pct      = (total_paid / total_original * 100) if total_original > 0 else 0

    st.markdown(f"**🏦 남은 대출:** {total_current:,.0f}원")
    st.progress(min(1.0, max(0.0, repay_pct / 100)))
    st.caption(f"전체 {total_original:,.0f}원 중 {repay_pct:.1f}% 상환 완료")

    st.markdown("---")

    # 이번 달 수지
    balance_color = "#2ecc71" if month_balance >= 0 else "#e74c3c"
    st.markdown(
        f"<div style='background:{balance_color}22; border-left:4px solid {balance_color}; "
        f"padding:10px 14px; border-radius:8px; margin-top:8px;'>"
        f"<b>이번 달 수입</b>: {total_income_all:,.0f}원<br>"
        f"<b>이번 달 지출</b>: {total_expense_all:,.0f}원<br>"
        f"<b>잔액</b>: <span style='color:{balance_color}; font-size:1.1rem;'>"
        f"{month_balance:+,.0f}원</span>"
        f"</div>",
        unsafe_allow_html=True,
    )

with right_col:
    st.markdown("### 🎯 목표 현황")

    def render_goals(title: str, goals: list) -> None:
        st.markdown(f"**{title}**")
        if goals:
            for g in goals:
                st.markdown(f"- {g}")
        else:
            st.caption("아직 목표가 없어!")

    monday  = today_dt - timedelta(days=today_dt.weekday())
    sunday  = monday + timedelta(days=6)
    render_goals(
        f"📅 {today_dt.strftime('%m월')} 월간 목표",
        month_goals,
    )
    st.markdown("")
    render_goals(
        f"📆 {monday.strftime('%m/%d')}~{sunday.strftime('%m/%d')} 주간 목표",
        week_goals,
    )

st.markdown("---")

# ════════════════════════════════════════════════════════════════════════════
# 섹션 5: 바로가기
# ════════════════════════════════════════════════════════════════════════════
st.markdown("### 🔗 바로가기")

links = [
    ("✏️ 일기 쓰기",  "pages/1_✏️_일기쓰기.py"),
    ("📖 일기 보기",  "pages/2_📖_일기보기.py"),
    ("🤖 Claude 분석", "pages/3_🤖_Claude분석.py"),
    ("🎯 목표 관리",  "pages/4_🎯_목표관리.py"),
    ("💰 가계부",     "pages/5_💰_가계부.py"),
    ("🧠 CBT 챗봇",  "pages/7_🧠_CBT챗봇.py"),
]

# Streamlit page_link (1.27+)
cols = st.columns(len(links))
for col, (label, path) in zip(cols, links):
    with col:
        st.page_link(path, label=label, width="stretch")
