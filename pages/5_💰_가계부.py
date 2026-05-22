import streamlit as st
import json
import os
from datetime import date, timedelta
import pandas as pd
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import (load_loans_db, save_loan_db, load_fixed_db, save_fixed_item_db,
                   load_income_db, save_income_db, load_ledger_db, save_ledger_db,
                   delete_ledger_db)
from theme import init_page_style

st.set_page_config(page_title="나의 일기장", page_icon="📔", layout="wide")
init_page_style()

LAST_REPAY_FILE = "data/last_repay.json"


def format_won(amount):
    return f"{amount:,.0f}원"


def _load_last_repay_month() -> str:
    """
    마지막 상환 반영 월을 읽어 반환. 파일 손상·없음 시 빈 문자열 반환.

    [방어 코드]
    json.load() 실패(파일 깨짐, 권한 오류 등) 시 앱 전체 크래시 방지.
    손상된 파일은 백업 후 초기화.
    """
    if not os.path.exists(LAST_REPAY_FILE):
        return ""
    try:
        with open(LAST_REPAY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("month", "")
    except (json.JSONDecodeError, OSError):
        # 파일이 깨진 경우 → 백업 후 초기화
        backup = LAST_REPAY_FILE + ".bak"
        try:
            os.replace(LAST_REPAY_FILE, backup)
        except OSError:
            pass
        return ""


def _save_last_repay_month(month: str) -> None:
    """마지막 상환 반영 월을 저장. 쓰기 실패 시 경고 로그만 남기고 계속."""
    os.makedirs(os.path.dirname(LAST_REPAY_FILE), exist_ok=True)
    try:
        with open(LAST_REPAY_FILE, "w", encoding="utf-8") as f:
            json.dump({"month": month}, f)
    except OSError as e:
        st.warning(f"⚠️ 상환 기록 저장 실패 (다음 실행 시 재처리됩니다): {e}")


def repay_month_done(this_month: str) -> bool:
    """이번 달 상환이 이미 반영됐는지 확인."""
    return _load_last_repay_month() == this_month


def apply_monthly_repay(loans: list, this_month: str) -> list:
    """
    대출 목록에 이번 달 월 상환액을 차감하고 DB에 저장.
    UI 렌더링이 아닌 **사용자의 명시적 버튼 클릭** 시에만 호출.

    [격리 이유]
    이전 구현은 페이지 로드마다 auto_repay_loans()가 실행되어
    탭을 리프레시할 때마다 잔액이 중복 차감될 위험이 있었음.
    → 사용자가 직접 트리거하는 방식으로 변경.
    """
    updated = []
    for loan in loans:
        if loan["name"] == "전북" and this_month < "2026-07":
            updated.append(loan)
            continue
        loan["current_amount"] = max(0, loan["current_amount"] - loan["monthly"])
        save_loan_db(loan)
        updated.append(loan)
    _save_last_repay_month(this_month)
    return updated


st.title("💰 가계부")

loans = load_loans_db()
fixed = load_fixed_db()
income = load_income_db()

# ── 월 상환 반영 배너 (명시적 트리거) ──────────────────────────────────────
this_month = date.today().strftime("%Y-%m")
if not repay_month_done(this_month):
    total_monthly = sum(l["monthly"] for l in loans)
    st.warning(
        f"📅 **{this_month} 월 상환이 아직 반영되지 않았어.** "
        f"월 상환 예정액: **{total_monthly:,.0f}원**"
    )
    if st.button("✅ 이번 달 대출 상환 반영하기", type="primary"):
        loans = apply_monthly_repay(loans, this_month)
        st.success("✅ 이번 달 상환이 반영됐어!")
        st.rerun()

total_monthly_repay = sum(l["monthly"] for l in loans)
total_fixed = sum(f["amount"] for f in fixed) + total_monthly_repay

tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 대출 현황", "🏠 고정지출/수입", "📝 변동지출", "📈 월별 요약", "📊 지출 차트"])

# ── 탭1: 대출 현황 ──────────────────────────────────────
with tab1:
    st.subheader("📊 대출 현황")

    total_original = sum(l["original"] for l in loans)
    total_current = sum(l["current_amount"] for l in loans)
    total_paid = total_original - total_current
    overall_pct = (total_paid / total_original * 100) if total_original > 0 else 0

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("💳 총 대출", format_won(total_original))
    with col2:
        st.metric("💸 남은 대출", format_won(total_current))
    with col3:
        st.metric("✅ 갚은 금액", format_won(total_paid))
    with col4:
        st.metric("📅 월 상환액", format_won(total_monthly_repay))

    st.markdown("---")
    st.markdown(f"**🎯 전체 상환 진행률: {overall_pct:.1f}%**")
    st.progress(min(1.0, max(0.0, overall_pct / 100)))
    st.markdown(f"앞으로 **{format_won(total_current)}** 남았어!")
    st.markdown("---")

    st.subheader("개별 대출")
    for i, loan in enumerate(loans):
        paid = loan["original"] - loan["current_amount"]
        pct = (paid / loan["original"] * 100) if loan["original"] > 0 else 0

        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(f"**{loan['name']}**")
            st.progress(min(1.0, max(0.0, pct / 100)))
            st.caption(f"남은 금액: {format_won(loan['current_amount'])} / 총 {format_won(loan['original'])} ({pct:.1f}% 상환)")
        with col2:
            st.markdown(f"월 상환: **{format_won(loan['monthly'])}**")
            new_current = st.number_input(
                "현재 잔액 수정",
                value=float(loan["current_amount"]),
                step=10000.0,
                key=f"loan_{i}"
            )
            if st.button("업데이트", key=f"loan_btn_{i}"):
                loans[i]["current_amount"] = int(new_current)
                save_loan_db(loans[i])
                st.success("업데이트됐어!")
                st.rerun()
        st.markdown("---")

# ── 탭2: 고정지출/수입 ──────────────────────────────────────
with tab2:
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("🏠 고정지출")
        st.caption("매달 나가는 고정 비용")

        new_fixed = []
        for i, item in enumerate(fixed):
            col_a, col_b = st.columns([1, 2])
            with col_a:
                st.markdown(f"**{item['name']}**")
            with col_b:
                amt = st.number_input(
                    "금액",
                    value=float(item["amount"]),
                    step=1000.0,
                    key=f"fixed_{i}",
                    label_visibility="collapsed"
                )
            new_fixed.append({"name": item["name"], "amount": int(amt)})

        st.markdown("---")
        st.markdown(f"**대출 상환** (자동): **{format_won(total_monthly_repay)}**")
        total_fixed_display = sum(f["amount"] for f in new_fixed) + total_monthly_repay
        st.markdown(f"**총 고정지출: {format_won(total_fixed_display)}**")

        if st.button("💾 고정지출 저장", type="primary"):
            for item in new_fixed:
                save_fixed_item_db(item["name"], item["amount"])
            st.success("✅ 저장됐어!")
            st.rerun()

    with col_right:
        st.subheader("💚 수입")
        st.caption("매달 들어오는 수입")

        new_monthly = st.number_input("월 수입", value=float(income["monthly"]), step=10000.0)
        new_memo = st.text_input("메모", value=income["memo"], placeholder="예: 대연아이앤티 월급")

        if st.button("💾 수입 저장", type="primary"):
            save_income_db(int(new_monthly), new_memo)
            st.success("✅ 저장됐어!")
            st.rerun()

        st.markdown("---")
        st.markdown("**💡 월 여유자금**")
        surplus = income["monthly"] - total_fixed
        color = "#2ecc71" if surplus >= 0 else "#e74c3c"
        st.markdown(
            f"<div style='background:{color}22; border-left:4px solid {color}; padding:10px; border-radius:8px;'>"
            f"<b>{format_won(income['monthly'])} - {format_won(total_fixed)} = {format_won(surplus)}</b>"
            f"</div>",
            unsafe_allow_html=True
        )

# ── 탭3: 변동지출 ──────────────────────────────────────
with tab3:
    st.subheader("📝 변동지출 기록")

    col1, col2 = st.columns(2)
    with col1:
        entry_date = st.date_input("날짜", value=date.today())
        entry_type = st.selectbox("종류", ["지출", "수입"])
        amount = st.number_input("금액", min_value=0, step=1000)
    with col2:
        category_options = {
            "지출": ["생활비", "유흥비", "교통비", "식비", "의료/약", "문화", "기타"],
            "수입": ["급여 외 수입", "기타"]
        }
        category = st.selectbox("카테고리", category_options[entry_type])
        memo = st.text_input("메모", placeholder="예: 편의점, 택시")

    if st.button("💾 기록 추가", type="primary"):
        entry = {
            "date": entry_date.strftime("%Y-%m-%d"),
            "type": entry_type,
            "amount": amount,
            "category": category,
            "memo": memo
        }
        if save_ledger_db(entry):
            st.success("✅ 기록됐어!")
            st.rerun()
        else:
            st.error("❌ 저장 실패!")

    st.markdown("---")
    st.subheader("📋 이번 달 변동지출")
    this_month = date.today().strftime("%Y-%m")
    month_ledger = load_ledger_db(this_month)

    if month_ledger:
        for e in month_ledger:
            color = "#e74c3c" if e["type"] == "지출" else "#2ecc71"
            sign = "-" if e["type"] == "지출" else "+"
            col_info, col_del = st.columns([10, 1])
            with col_info:
                st.markdown(
                    f"<div style='display:flex; justify-content:space-between; padding:8px; "
                    f"border-left:3px solid {color}; margin:4px 0;'>"
                    f"<span>{e['date']} | {e['category']} | {e['memo']}</span>"
                    f"<span style='color:{color};font-weight:bold;'>{sign}{format_won(e['amount'])}</span>"
                    f"</div>",
                    unsafe_allow_html=True
                )
            with col_del:
                if st.button("🗑️", key=f"del_{e['id']}", help="삭제"):
                    if delete_ledger_db(e["id"]):
                        st.rerun()
    else:
        st.info("이번 달 변동지출 기록이 없어!")

# ── 탭4: 월별 요약 ──────────────────────────────────────
with tab4:
    st.subheader("📈 이번 달 요약")
    this_month = date.today().strftime("%Y-%m")
    month_ledger = load_ledger_db(this_month)

    variable_expense = sum(e["amount"] for e in month_ledger if e["type"] == "지출")
    variable_income = sum(e["amount"] for e in month_ledger if e["type"] == "수입")
    total_income_all = income["monthly"] + variable_income
    total_expense_all = total_fixed + variable_expense
    final_balance = total_income_all - total_expense_all

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("💚 총 수입", format_won(total_income_all))
        st.caption(f"월급: {format_won(income['monthly'])} + 기타: {format_won(variable_income)}")
    with col2:
        st.metric("❤️ 총 지출", format_won(total_expense_all))
        st.caption(f"고정: {format_won(total_fixed)} + 변동: {format_won(variable_expense)}")
    with col3:
        st.metric("💙 이번 달 잔액", format_won(final_balance))

    st.markdown("---")
    st.markdown("**카테고리별 변동지출**")
    if month_ledger:
        expense_by_cat = {}
        for e in month_ledger:
            if e["type"] == "지출":
                expense_by_cat[e["category"]] = expense_by_cat.get(e["category"], 0) + e["amount"]

        for cat, amt in sorted(expense_by_cat.items(), key=lambda x: x[1], reverse=True):
            pct = (amt / variable_expense * 100) if variable_expense > 0 else 0
            st.markdown(f"**{cat}**: {format_won(amt)} ({pct:.1f}%)")
            st.progress(min(1.0, max(0.0, pct / 100)))
    else:
        st.info("이번 달 변동지출 기록이 없어!")

# ── 탭5: 지출 차트 ──────────────────────────────────────
with tab5:
    st.subheader("📊 지출 시각화")

    # ── 기간 선택 ──────────────────────────────────────
    today_dt = date.today()
    chart_period = st.radio(
        "기간 선택",
        ["이번 달", "최근 3개월", "최근 6개월", "올해"],
        horizontal=True,
        key="chart_period",
    )

    if chart_period == "이번 달":
        months_list = [today_dt.strftime("%Y-%m")]
    elif chart_period == "최근 3개월":
        months_list = [
            (today_dt.replace(day=1) - timedelta(days=1)).replace(day=1).strftime("%Y-%m")
            if i > 0 else today_dt.strftime("%Y-%m")
            for i in range(3)
        ]
        # 올바른 방법으로 재계산
        months_list = []
        cur = today_dt.replace(day=1)
        for _ in range(3):
            months_list.append(cur.strftime("%Y-%m"))
            cur = (cur - timedelta(days=1)).replace(day=1)
        months_list.reverse()
    elif chart_period == "최근 6개월":
        months_list = []
        cur = today_dt.replace(day=1)
        for _ in range(6):
            months_list.append(cur.strftime("%Y-%m"))
            cur = (cur - timedelta(days=1)).replace(day=1)
        months_list.reverse()
    else:  # 올해
        months_list = [
            f"{today_dt.year}-{m:02d}"
            for m in range(1, today_dt.month + 1)
        ]

    # ── 월별 수지 데이터 수집 ──────────────────────────────────────
    monthly_data = []
    for ym in months_list:
        ledger = load_ledger_db(ym)
        var_exp = sum(e["amount"] for e in ledger if e["type"] == "지출")
        var_inc = sum(e["amount"] for e in ledger if e["type"] == "수입")
        monthly_data.append({
            "월":     ym[5:] + "월",
            "수입":   income["monthly"] + var_inc,
            "지출":   total_fixed + var_exp,
            "잔액":   income["monthly"] + var_inc - total_fixed - var_exp,
        })

    df_monthly = pd.DataFrame(monthly_data).set_index("월")

    # ── 차트 1: 월별 수입/지출 막대 ──────────────────────────────────────
    st.markdown("#### 💹 월별 수입 vs 지출")
    st.bar_chart(df_monthly[["수입", "지출"]], height=280)

    # ── 차트 2: 월별 잔액 추이 ──────────────────────────────────────
    st.markdown("#### 💰 월별 잔액 추이")
    st.line_chart(df_monthly[["잔액"]], height=220)

    st.markdown("---")

    # ── 차트 3: 이번 달 카테고리별 지출 비율 ──────────────────────────────────────
    st.markdown("#### 🥧 이번 달 카테고리별 지출 비율")

    this_month_str = today_dt.strftime("%Y-%m")
    this_ledger = load_ledger_db(this_month_str)
    cat_expense: dict[str, int] = {}
    for e in this_ledger:
        if e["type"] == "지출":
            cat_expense[e["category"]] = cat_expense.get(e["category"], 0) + e["amount"]

    if cat_expense:
        # 고정지출 항목도 포함
        cat_all = {"대출상환": total_monthly_repay}
        for f in fixed:
            cat_all[f["name"]] = f["amount"]
        cat_all.update(cat_expense)

        total_all = sum(cat_all.values())
        df_pie = pd.DataFrame(
            {"금액": list(cat_all.values())},
            index=list(cat_all.keys()),
        )

        # Streamlit 기본 bar_chart로 비율 표시 (plotly 없이)
        df_pie_sorted = df_pie.sort_values("금액", ascending=False)
        st.bar_chart(df_pie_sorted, height=260)

        # 텍스트 테이블
        st.markdown("**카테고리별 상세**")
        for cat, row in df_pie_sorted.iterrows():
            amt = int(row["금액"])
            pct = amt / total_all * 100 if total_all > 0 else 0
            bar_w = int(pct)
            color = "#3498db" if cat in [f["name"] for f in fixed] + ["대출상환"] else "#e74c3c"
            st.markdown(
                f"<div style='display:flex; align-items:center; gap:8px; margin:3px 0;'>"
                f"<span style='width:90px; font-size:0.85rem;'>{cat}</span>"
                f"<div style='flex:1; background:#eee; border-radius:4px; height:16px;'>"
                f"<div style='background:{color}; width:{bar_w}%; height:16px; border-radius:4px;'></div>"
                f"</div>"
                f"<span style='width:120px; text-align:right; font-size:0.85rem;'>"
                f"{amt:,.0f}원 ({pct:.1f}%)</span>"
                f"</div>",
                unsafe_allow_html=True,
            )
    else:
        st.info("이번 달 변동지출 기록이 없어서 고정지출만 표시할게!")
        cat_fixed = {"대출상환": total_monthly_repay}
        for f in fixed:
            cat_fixed[f["name"]] = f["amount"]
        df_fixed_only = pd.DataFrame({"금액": list(cat_fixed.values())}, index=list(cat_fixed.keys()))
        st.bar_chart(df_fixed_only.sort_values("금액", ascending=False), height=220)