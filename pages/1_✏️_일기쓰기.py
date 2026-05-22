import streamlit as st
st.set_page_config(page_title="나의 일기장", page_icon="📔", layout="wide")
import json
import os
from datetime import date, datetime, timedelta
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db.connection import check_db_connection
from utils import load_month_goals_db, load_week_goals_db, load_diary_db, save_diary_db
from theme import init_page_style

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.makedirs(os.path.join(_BASE_DIR, "data"), exist_ok=True)
os.makedirs(os.path.join(_BASE_DIR, "data", "goals"), exist_ok=True)
os.makedirs(os.path.join(_BASE_DIR, "data", "pending"), exist_ok=True)

_db_ok, _db_err = check_db_connection()
if not _db_ok:
    st.error(
        f"⚠️ **DB 연결 실패** — 일기를 저장할 수 없어요.\n\n"
        f"`{_db_err}`\n\n"
        f"MySQL이 실행 중인지 확인해줘. 연결이 복구되면 새로고침해줘."
    )
    st.stop()

init_page_style()

st.title("✏️ 오늘의 일기")

# ── 투약 알림 배너 ────────────────────────────────────────────────────────────
# 아침(6~10시) / 취침(21~24시) 시간대에 시각적 알림 표시
_now_h = datetime.now().hour
if 6 <= _now_h < 10:
    _today_diary_check = load_diary_db(date.today().strftime("%Y-%m-%d")) or {}
    _med_taken = _today_diary_check.get("medication", {}).get("morning", {}).get("status") == "먹었어"
    if not _med_taken:
        st.info("💊 **아침약 시간이야!** 오늘 아침약 챙겼어? 기록 후 저장해줘.")
elif 21 <= _now_h <= 23:
    _today_diary_check = load_diary_db(date.today().strftime("%Y-%m-%d")) or {}
    _med_taken = _today_diary_check.get("medication", {}).get("night", {}).get("status") == "먹었어"
    if not _med_taken:
        st.info("💊 **취침약 시간이야!** 오늘 취침약 챙겼어? 기록 후 저장해줘.")

today_dt = st.date_input("📅 날짜 선택", value=date.today())
today = today_dt.strftime("%Y-%m-%d")

existing = load_diary_db(today) or {}
if existing:
    st.info(f"📂 {today} 기록을 불러왔어! 수정 후 저장해줘.")

month_goals = load_month_goals_db(today_dt.year, today_dt.month)
iso_year, week_num, _ = today_dt.isocalendar()
week_goals = load_week_goals_db(iso_year, week_num)

left, right = st.columns([2, 1])

with left:
    st.subheader(f"📅 {today}")

    # ── 핵심 입력 (항상 노출) ─────────────────────────────────────────────────
    col1, col2 = st.columns(2)
    with col1:
        mood = st.slider("😊 오늘의 기분", 1, 10, existing.get("mood", 5))
        stress = st.slider("😤 스트레스", 1, 10, existing.get("stress", 5))

    with col2:
        saved_sleep = existing.get("sleep", {})
        default_sleep_start = (
            datetime.strptime(saved_sleep["start"], "%H:%M:%S").time()
            if saved_sleep.get("start") else datetime.strptime("23:00:00", "%H:%M:%S").time()
        )
        default_sleep_end = (
            datetime.strptime(saved_sleep["end"], "%H:%M:%S").time()
            if saved_sleep.get("end") else datetime.strptime("07:00:00", "%H:%M:%S").time()
        )
        sleep_start = st.time_input("🌙 취침 시간", value=default_sleep_start)
        sleep_end   = st.time_input("☀️ 기상 시간", value=default_sleep_end)

    dt_start = datetime.combine(today_dt, sleep_start)
    dt_end   = datetime.combine(
        today_dt + timedelta(days=1) if sleep_start.hour >= 18 else today_dt,
        sleep_end,
    )
    sleep_hours = (dt_end - dt_start).seconds / 3600
    st.caption(f"😴 수면: {sleep_hours:.1f}시간")

    st.markdown("---")
    st.markdown("💊 **투약**")
    saved_med = existing.get("medication", {})
    col_ma, col_mn, col_mp = st.columns(3)

    med_morning_options = ["먹었어", "안 먹었어", "해당없음"]
    med_night_options   = ["먹었어", "안 먹었어", "해당없음"]
    med_prn_options     = ["해당없음", "먹었어", "안 먹었어"]

    med_morning_default = saved_med.get("morning", {}).get("status", "먹었어")
    med_night_default   = saved_med.get("night",   {}).get("status", "먹었어")
    med_prn_default     = saved_med.get("prn",     {}).get("status", "해당없음")

    with col_ma:
        med_morning = st.selectbox("아침약", med_morning_options,
                                   index=med_morning_options.index(med_morning_default)
                                   if med_morning_default in med_morning_options else 0)
    with col_mn:
        med_night   = st.selectbox("취침약", med_night_options,
                                   index=med_night_options.index(med_night_default)
                                   if med_night_default in med_night_options else 0)
    with col_mp:
        med_prn     = st.selectbox("필요시",  med_prn_options,
                                   index=med_prn_options.index(med_prn_default)
                                   if med_prn_default in med_prn_options else 0)

    med_morning_reason = st.text_input("아침약 미복용 이유", placeholder="예: 깜빡했어",
                                       value=saved_med.get("morning", {}).get("reason", "")) \
                         if med_morning == "안 먹었어" else ""
    med_night_reason   = st.text_input("취침약 미복용 이유",
                                       value=saved_med.get("night", {}).get("reason", "")) \
                         if med_night == "안 먹었어" else ""
    med_prn_reason     = st.text_input("필요시 미복용 이유",
                                       value=saved_med.get("prn", {}).get("reason", "")) \
                         if med_prn == "안 먹었어" else ""

    st.markdown("---")
    diary_text = st.text_area("📝 일기", value=existing.get("diary", ""), height=180,
                              placeholder="오늘 있었던 일, 느낀 것, 생각 등 자유롭게 써줘.")

    # ── 상세 입력 (접힌 상태 — 필요할 때 열기) ─────────────────────────────────
    saved_meal     = existing.get("meal",     {})
    saved_exercise = existing.get("exercise", {})
    saved_drinking = existing.get("drinking", {})

    # 저장된 값이 있으면 expander를 열어둠
    _has_detail = any([
        saved_meal.get("morning", {}).get("eaten") or
        saved_meal.get("lunch",   {}).get("eaten") or
        saved_meal.get("dinner",  {}).get("eaten"),
        saved_exercise.get("status") not in ("", None),
        saved_drinking.get("status") == "했어",
    ])

    with st.expander("🍽️ 식사 · 💪 운동 · 🍺 음주 상세", expanded=_has_detail):
        st.markdown("**🍽️ 식사**")
        col_m, col_l, col_d = st.columns(3)
        with col_m:
            meal_morning = st.checkbox("아침", value=saved_meal.get("morning", {}).get("eaten", False))
            meal_morning_menu = st.text_input("아침 메뉴", placeholder="예: 토스트",
                                              value=saved_meal.get("morning", {}).get("menu", "")) \
                                if meal_morning else ""
        with col_l:
            meal_lunch = st.checkbox("점심", value=saved_meal.get("lunch", {}).get("eaten", False))
            meal_lunch_menu = st.text_input("점심 메뉴", placeholder="예: 비빔밥",
                                            value=saved_meal.get("lunch", {}).get("menu", "")) \
                              if meal_lunch else ""
        with col_d:
            meal_dinner = st.checkbox("저녁", value=saved_meal.get("dinner", {}).get("eaten", False))
            meal_dinner_menu = st.text_input("저녁 메뉴", placeholder="예: 삼겹살",
                                             value=saved_meal.get("dinner", {}).get("menu", "")) \
                               if meal_dinner else ""

        st.markdown("**💪 운동**")
        exercise_options = ["했어", "안 했어", "해당없음"]
        exercise_default = saved_exercise.get("status", "했어")
        exercise = st.selectbox("운동", exercise_options,
                                index=exercise_options.index(exercise_default)
                                if exercise_default in exercise_options else 0)
        if exercise == "했어":
            exercise_detail = st.text_input("운동 내용", placeholder="예: 풀업 3세트, 딥스 3세트",
                                            value=saved_exercise.get("detail", ""))
            exercise_reason = ""
        elif exercise == "안 했어":
            exercise_detail = ""
            exercise_reason = st.text_input("안 한 이유", placeholder="예: 너무 피곤했어",
                                            value=saved_exercise.get("reason", ""))
        else:
            exercise_detail = exercise_reason = ""

        st.markdown("**🍺 음주**")
        drinking_options = ["안 했어", "했어"]
        drinking_default = saved_drinking.get("status", "안 했어")
        drinking = st.selectbox("음주", drinking_options,
                                index=drinking_options.index(drinking_default)
                                if drinking_default in drinking_options else 0)
        if drinking == "했어":
            col_d1, col_d2 = st.columns(2)
            with col_d1:
                drinking_with   = st.text_input("누구와?", placeholder="예: 혼자, 친구",
                                                value=saved_drinking.get("with", ""))
            with col_d2:
                drinking_amount = st.text_input("얼마나?", placeholder="예: 맥주 2캔",
                                                value=saved_drinking.get("amount", ""))
        else:
            drinking_with = drinking_amount = ""

        st.markdown("**🌟 오늘 잘한 것**")
        good_thing = st.text_input("한 가지만", value=existing.get("good_thing", ""),
                                   placeholder="예: 약 빠짐없이 먹었어")

    st.markdown("---")
    st.markdown("🎯 **오늘 목표 실천 체크**")
    saved_checks = existing.get("weekly_checks", {})
    weekly_checks = {}
    if week_goals:
        for i, goal in enumerate(week_goals):
            weekly_checks[goal] = st.checkbox(f"✅ {goal}", value=saved_checks.get(goal, False),
                                              key=f"weekly_{i}")
    else:
        st.caption("이번 주 목표가 없어. 목표 관리에서 설정해줘!")

    if st.button("💾 저장", type="primary"):
        entry = {
            "date": today, "mood": mood, "stress": stress,
            "sleep": {"start": str(sleep_start), "end": str(sleep_end), "hours": round(sleep_hours, 1)},
            "medication": {
                "morning": {"status": med_morning, "reason": med_morning_reason},
                "night": {"status": med_night, "reason": med_night_reason},
                "prn": {"status": med_prn, "reason": med_prn_reason}
            },
            "meal": {
                "morning": {"eaten": meal_morning, "menu": meal_morning_menu},
                "lunch": {"eaten": meal_lunch, "menu": meal_lunch_menu},
                "dinner": {"eaten": meal_dinner, "menu": meal_dinner_menu}
            },
            "exercise": {"status": exercise, "detail": exercise_detail, "reason": exercise_reason},
            "drinking": {"status": drinking, "with": drinking_with, "amount": drinking_amount},
            "weekly_checks": weekly_checks,
            "good_thing": good_thing,
            "diary": diary_text
        }

        # ── 저장 순서: DB 먼저, 성공 후 JSON 백업 ─────────────────────────
        # [설계 이유]
        # 이전 코드는 파일 → DB 순서라 DB 실패 시 싱크가 깨졌음.
        # DB가 진실 소스(source of truth)이므로 DB를 먼저 시도하고,
        # 성공하면 data/{date}.json에 로컬 백업을 씀.
        # DB 실패 시에는 data/pending/{date}.json에 임시 보관해
        # 나중에 재시도할 수 있도록 함.
        if save_diary_db(entry):
            # DB 성공 → 로컬 JSON 백업 (실패해도 DB가 있으니 경고만)
            try:
                local_path = os.path.join(_BASE_DIR, "data", f"{today}.json")
                with open(local_path, "w", encoding="utf-8") as f:
                    json.dump(entry, f, ensure_ascii=False, indent=2)
            except OSError as e:
                st.warning(f"⚠️ DB 저장은 됐는데 로컬 파일 백업 실패: {e}")
            st.success("✅ 저장됐어!")
            st.rerun()
        else:
            # DB 실패 → pending 폴더에 임시 덤프 (데이터 유실 방지)
            try:
                pending_path = os.path.join(_BASE_DIR, "data", "pending", f"{today}.json")
                with open(pending_path, "w", encoding="utf-8") as f:
                    json.dump(entry, f, ensure_ascii=False, indent=2)
                st.error(
                    f"❌ DB 저장 실패! 입력 내용은 `{pending_path}`에 임시 보관했어. "
                    f"DB 연결 확인 후 다시 저장해줘."
                )
            except OSError:
                # pending 저장도 실패하면 화면에 JSON을 그대로 표시 (최후 수단)
                st.error("❌ DB 저장 실패! 아래 내용을 복사해서 보관해줘:")
                st.code(json.dumps(entry, ensure_ascii=False, indent=2))

with right:
    st.markdown("<div style='background:#1a2a3a; border-radius:10px; padding:16px;'>", unsafe_allow_html=True)

    if month_goals:
        st.markdown(f"**📅 {today_dt.month}월 목표**")
        for g in month_goals:
            st.markdown(f"- {g}")
    else:
        st.markdown(f"**📅 {today_dt.month}월 목표**")
        st.caption("목표를 설정해줘!")

    st.markdown("---")

    if week_goals:
        monday = today_dt - timedelta(days=today_dt.weekday())
        sunday = monday + timedelta(days=6)
        st.markdown(f"**📆 이번 주 목표** ({monday.strftime('%m/%d')}~{sunday.strftime('%m/%d')})")
        for g in week_goals:
            st.markdown(f"- {g}")
    else:
        st.markdown("**📆 이번 주 목표**")
        st.caption("목표를 설정해줘!")

    st.markdown("</div>", unsafe_allow_html=True)
