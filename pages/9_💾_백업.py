"""
데이터 백업 / 복원 페이지.

백업 방식:
  - MySQL DB의 모든 데이터를 기존 load 함수로 읽어 JSON 직렬화
  - data/ 폴더의 JSON 파일(보조 데이터)도 포함
  - 전부 ZIP 아카이브로 묶어 브라우저 다운로드 제공

복원 방식:
  - 백업 ZIP 업로드 → 각 JSON 파일을 기존 save 함수로 재주입
  - 기존 데이터 위에 덮어씌우므로 복원 전 반드시 확인 받음

[설계 이유]
  mysqldump 대신 애플리케이션 레이어 백업을 택한 이유:
  - mysqldump 실행 권한이 없는 환경(호스팅, Docker)에서도 동작
  - 앱 코드와 독립적으로 스키마 변경에 강함
  - Streamlit download_button으로 클릭 한 번에 다운로드 가능
"""
import streamlit as st
import json
import os
import io
import zipfile
from datetime import date, datetime, timedelta
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import (
    load_diaries_range_db,
    load_month_goals_db, load_week_goals_db,
    load_loans_db, load_fixed_db, load_income_db, load_ledger_db,
    load_cbt_sessions, load_cbt_messages, load_cbt_emotion_tags, load_cbt_summary,
    save_diary_db, save_loan_db, save_fixed_item_db, save_income_db,
    save_ledger_db, save_month_goals_db, save_week_goals_db, clear_ledger_db,
)
from theme import init_page_style

st.set_page_config(page_title="나의 일기장", page_icon="📔", layout="wide")
init_page_style()

st.title("💾 데이터 백업 / 복원")
st.caption("개인 데이터를 안전하게 내보내거나 복원할 수 있어.")

BACKUP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backups")
os.makedirs(BACKUP_DIR, exist_ok=True)


# ════════════════════════════════════════════════════════════════════════════
# 헬퍼
# ════════════════════════════════════════════════════════════════════════════

def _collect_all_data() -> dict:
    """
    모든 데이터를 딕셔너리로 수집.
    각 키는 백업 ZIP 안의 파일명이 된다.
    """
    data: dict[str, object] = {}

    # ── 일기 (전 기간) ──────────────────────────────────────
    all_diaries = load_diaries_range_db(date(2000, 1, 1), date(2099, 12, 31))
    data["diaries.json"] = all_diaries

    # ── 목표 (최근 5년치 + 내년까지 월/주 목표) ──────────────────────────────────────
    goals_monthly: list[dict] = []
    goals_weekly:  list[dict] = []
    today = date.today()
    for year in range(today.year - 4, today.year + 2):
        for month in range(1, 13):
            g = load_month_goals_db(year, month)
            if g:
                goals_monthly.append({"year": year, "month": month, "goals": g})
        for week in range(1, 54):   # ISO 주차: 1~53
            g = load_week_goals_db(year, week)
            if g:
                goals_weekly.append({"year": year, "week": week, "goals": g})
    data["goals_monthly.json"] = goals_monthly
    data["goals_weekly.json"]  = goals_weekly

    # ── 재무 ──────────────────────────────────────
    data["loans.json"]  = load_loans_db()
    data["fixed.json"]  = load_fixed_db()
    data["income.json"] = load_income_db()

    # 원장 전체 (월 지정 없이 전부 로드)
    all_ledger = load_ledger_db()   # 월 인자 없으면 전체 반환 여부 확인 필요
    data["ledger.json"] = all_ledger

    # ── CBT 세션 ──────────────────────────────────────
    sessions = load_cbt_sessions()
    cbt_export: list[dict] = []
    for s in sessions:
        sid = s["id"]
        messages   = load_cbt_messages(sid)
        tags       = load_cbt_emotion_tags(sid)
        summary    = load_cbt_summary(sid)
        cbt_export.append({
            "session":  s,
            "messages": messages,
            "tags":     tags,
            "summary":  summary,
        })
    data["cbt_sessions.json"] = cbt_export

    return data


def _build_zip(data: dict) -> bytes:
    """딕셔너리 → ZIP bytes."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        # 메타 정보
        meta = {
            "backup_time": datetime.now().isoformat(),
            "files":       list(data.keys()),
            "diary_count": len(data.get("diaries.json", [])),
        }
        zf.writestr("_meta.json", json.dumps(meta, ensure_ascii=False, indent=2))

        # 각 데이터 파일
        for filename, payload in data.items():
            zf.writestr(filename, json.dumps(payload, ensure_ascii=False, indent=2, default=str))

        # data/ 폴더 내 보조 JSON 파일도 포함
        data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
        if os.path.isdir(data_dir):
            for fname in os.listdir(data_dir):
                if fname.endswith(".json"):
                    fpath = os.path.join(data_dir, fname)
                    try:
                        with open(fpath, encoding="utf-8") as f:
                            zf.writestr(f"data_raw/{fname}", f.read())
                    except OSError:
                        pass

    return buf.getvalue()


def _save_local_backup(zip_bytes: bytes, label: str) -> str:
    """ZIP을 backups/ 폴더에 저장하고 경로 반환."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(BACKUP_DIR, f"backup_{label}_{ts}.zip")
    with open(path, "wb") as f:
        f.write(zip_bytes)
    return path


# ════════════════════════════════════════════════════════════════════════════
# 탭 구성
# ════════════════════════════════════════════════════════════════════════════
tab_backup, tab_restore, tab_history = st.tabs(["📤 백업", "📥 복원", "🗂️ 백업 이력"])


# ── 탭1: 백업 ─────────────────────────────────────────────────────────────────
with tab_backup:
    st.subheader("📤 데이터 내보내기")

    st.info(
        "백업 파일에 포함되는 내용:\n"
        "- 📔 **일기** (전체 기간)\n"
        "- 🎯 **목표** (월간/주간, 최근 5년 + 내년)\n"
        "- 💰 **재무** (대출·고정지출·수입·원장)\n"
        "- 🧠 **CBT 세션** (대화·감정태그·요약)\n"
        "- 📁 **data/ 보조 파일**"
    )

    label_input = st.text_input("백업 이름 (선택)", placeholder="예: 5월_정기백업", max_chars=30)
    label = label_input.strip().replace(" ", "_") or "manual"

    if st.button("🔄 백업 데이터 준비", type="primary"):
        with st.spinner("데이터 수집 중..."):
            try:
                all_data  = _collect_all_data()
                zip_bytes = _build_zip(all_data)
                local_path = _save_local_backup(zip_bytes, label)

                diary_cnt   = len(all_data.get("diaries.json", []))
                ledger_cnt  = len(all_data.get("ledger.json",  []))
                cbt_cnt     = len(all_data.get("cbt_sessions.json", []))
                size_kb     = len(zip_bytes) / 1024

                st.success(f"✅ 백업 완료! ({size_kb:.1f} KB)")
                st.caption(
                    f"일기 {diary_cnt}건 · 원장 {ledger_cnt}건 · "
                    f"CBT {cbt_cnt}세션 · 로컬 저장: `{local_path}`"
                )

                fname = f"diary_backup_{label}_{datetime.now().strftime('%Y%m%d')}.zip"
                st.download_button(
                    label="⬇️ ZIP 다운로드",
                    data=zip_bytes,
                    file_name=fname,
                    mime="application/zip",
                    width="stretch",
                )
            except Exception as e:
                st.error(f"❌ 백업 실패: {e}")


# ── 탭2: 복원 ─────────────────────────────────────────────────────────────────
with tab_restore:
    st.subheader("📥 데이터 복원")

    st.warning(
        "⚠️ **주의**: 복원하면 현재 데이터 위에 덮어씌워. "
        "복원 전에 반드시 최신 백업을 먼저 받아두고 진행해줘!"
    )

    uploaded = st.file_uploader("백업 ZIP 파일 선택", type=["zip"])

    if uploaded:
        try:
            zf = zipfile.ZipFile(io.BytesIO(uploaded.read()))
            names = zf.namelist()

            # 메타 정보 표시
            if "_meta.json" in names:
                meta = json.loads(zf.read("_meta.json"))
                st.markdown("**백업 정보**")
                c1, c2, c3 = st.columns(3)
                c1.metric("백업 시각", meta.get("backup_time", "알 수 없음")[:16].replace("T", " "))
                c2.metric("포함 파일",  f"{len(meta.get('files', []))}개")
                c3.metric("일기 수",    f"{meta.get('diary_count', '?')}건")

            # 복원 항목 선택
            st.markdown("**복원할 항목 선택**")
            restore_diaries  = st.checkbox("📔 일기",        value=True,  disabled="diaries.json" not in names)
            restore_goals    = st.checkbox("🎯 목표",        value=True,  disabled="goals_monthly.json" not in names)
            restore_finance  = st.checkbox("💰 재무",        value=True,  disabled="loans.json" not in names)
            restore_ledger   = st.checkbox("📒 원장(변동지출)", value=True, disabled="ledger.json" not in names)

            st.markdown("---")
            confirm = st.checkbox("⚠️ 기존 데이터가 덮어씌워질 수 있다는 걸 이해했어")

            if st.button("🔁 복원 시작", type="primary", disabled=not confirm):
                # 복원 전 현재 데이터 자동 백업
                with st.spinner("복원 전 현재 데이터 자동 백업 중..."):
                    try:
                        pre_data  = _collect_all_data()
                        pre_zip   = _build_zip(pre_data)
                        pre_path  = _save_local_backup(pre_zip, "pre_restore")
                        st.info(f"🔒 복원 전 자동 백업 저장됨 → `{os.path.basename(pre_path)}`")
                    except Exception as e:
                        st.warning(f"⚠️ 복원 전 자동 백업 실패 ({e}). 그래도 계속할게.")

                progress = st.progress(0)
                status   = st.empty()
                errors: list[str] = []
                step = [0]   # 리스트로 감싸야 중첩 함수에서 수정 가능 (nonlocal 대신)
                total_steps = sum([restore_diaries, restore_goals, restore_finance, restore_ledger])
                if total_steps == 0:
                    st.warning("복원할 항목을 하나 이상 선택해줘!")
                    st.stop()

                def advance(msg: str):
                    step[0] += 1
                    progress.progress(step[0] / total_steps)
                    status.info(msg)

                # 일기 복원
                if restore_diaries and "diaries.json" in names:
                    diaries = json.loads(zf.read("diaries.json"))
                    ok = err = 0
                    for d in diaries:
                        if save_diary_db(d):
                            ok += 1
                        else:
                            err += 1
                            errors.append(f"일기 {d.get('date')}: 저장 실패 (로그 확인)")
                    advance(f"📔 일기 복원 완료 ({ok}건 성공, {err}건 실패)")

                # 목표 복원
                if restore_goals:
                    goal_err = 0
                    if "goals_monthly.json" in names:
                        for item in json.loads(zf.read("goals_monthly.json")):
                            if not save_month_goals_db(item["year"], item["month"], item["goals"]):
                                goal_err += 1
                                errors.append(f"월 목표 {item['year']}-{item['month']:02d}: 저장 실패")
                    if "goals_weekly.json" in names:
                        for item in json.loads(zf.read("goals_weekly.json")):
                            if not save_week_goals_db(item["year"], item["week"], item["goals"]):
                                goal_err += 1
                                errors.append(f"주 목표 {item['year']}-W{item['week']:02d}: 저장 실패")
                    advance(f"🎯 목표 복원 완료 (실패 {goal_err}건)")

                # 재무 복원
                if restore_finance:
                    if "loans.json" in names:
                        for loan in json.loads(zf.read("loans.json")):
                            if not save_loan_db(loan):
                                errors.append(f"대출 '{loan.get('name')}': 저장 실패")
                    if "fixed.json" in names:
                        for item in json.loads(zf.read("fixed.json")):
                            if not save_fixed_item_db(item["name"], item["amount"]):
                                errors.append(f"고정지출 '{item.get('name')}': 저장 실패")
                    if "income.json" in names:
                        inc = json.loads(zf.read("income.json"))
                        if not save_income_db(inc["monthly"], inc.get("memo", "")):
                            errors.append("수입: 저장 실패")
                    advance("💰 재무 복원 완료")

                # 원장 복원 — 기존 데이터 전체 삭제 후 재삽입 (중복 방지)
                if restore_ledger and "ledger.json" in names:
                    ledger = json.loads(zf.read("ledger.json"))
                    ok = err = 0
                    if not clear_ledger_db():
                        errors.append("원장 초기화 실패 — 중복 데이터가 생길 수 있음")
                    for entry in ledger:
                        entry_copy = {k: v for k, v in entry.items() if k != "id"}
                        if save_ledger_db(entry_copy):
                            ok += 1
                        else:
                            err += 1
                            errors.append(f"원장 {entry.get('date')}: 저장 실패")
                    advance(f"📒 원장 복원 완료 ({ok}건 성공, {err}건 실패)")

                # 결과
                if errors:
                    st.warning(f"⚠️ {len(errors)}개 항목에서 오류 발생:")
                    with st.expander("오류 상세"):
                        for e in errors[:20]:
                            st.code(e)
                else:
                    st.success("✅ 복원 완료! 앱을 새로고침하면 반영돼.")
                    st.balloons()

        except zipfile.BadZipFile:
            st.error("❌ 유효한 ZIP 파일이 아니야!")
        except Exception as e:
            st.error(f"❌ 복원 오류: {e}")


# ── 탭3: 백업 이력 ─────────────────────────────────────────────────────────────
with tab_history:
    st.subheader("🗂️ 로컬 백업 이력")

    backup_files = sorted(
        [f for f in os.listdir(BACKUP_DIR) if f.endswith(".zip")],
        reverse=True,
    )

    if not backup_files:
        st.info("아직 로컬에 저장된 백업 파일이 없어. 백업 탭에서 먼저 만들어줘!")
    else:
        st.caption(f"총 {len(backup_files)}개 백업 파일 · 저장 위치: `{os.path.abspath(BACKUP_DIR)}/`")
        st.markdown("---")

        for fname in backup_files:
            fpath = os.path.join(BACKUP_DIR, fname)
            size_kb = os.path.getsize(fpath) / 1024
            mtime   = datetime.fromtimestamp(os.path.getmtime(fpath)).strftime("%Y-%m-%d %H:%M")

            col_info, col_dl, col_del = st.columns([6, 2, 1])
            with col_info:
                st.markdown(f"📦 **{fname}**")
                st.caption(f"{mtime} · {size_kb:.1f} KB")
            with col_dl:
                with open(fpath, "rb") as f:
                    st.download_button(
                        "⬇️ 다운로드",
                        data=f.read(),
                        file_name=fname,
                        mime="application/zip",
                        key=f"dl_{fname}",
                        width="stretch",
                    )
            with col_del:
                if st.button("🗑️", key=f"del_{fname}", help="이 백업 삭제"):
                    os.remove(fpath)
                    st.rerun()

        st.markdown("---")
        st.markdown("**💡 백업 관리 팁**")
        st.markdown(
            "- 정기적으로 ZIP을 외부 드라이브나 클라우드에 복사해두는 걸 추천해\n"
            "- 백업 파일에는 민감한 개인 정보가 있으니 안전한 곳에 보관해줘\n"
            "- 오래된 백업은 주기적으로 정리해서 용량을 관리해"
        )
