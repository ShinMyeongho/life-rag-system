import streamlit as st
import json
import os
import time
from datetime import date, datetime, timedelta
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from logger import get_logger, log_api_call
from utils import (
    load_diaries_range_db, load_month_goals_db, load_week_goals_db,
    goal_achievement, calc_stability_score, stability_label,
    load_loans_db, load_fixed_db, load_income_db, load_ledger_db,
)
from user_config import USER_PROFILE
from api_client import call_claude
from rag_search import HybridSearcher

st.set_page_config(page_title="나의 일기장", page_icon="📔", layout="wide")
from theme import init_page_style
init_page_style()

logger = get_logger(__name__)


# ── RAG 검색기 (캐시로 한 번만 초기화) ───────────────────────────────────────
@st.cache_resource
def load_rag():
    searcher = HybridSearcher()
    searcher.preload()
    return searcher


def _rag_k_for_range(start_date, end_date) -> int:
    """
    날짜 범위 크기에 따라 RAG 검색 k 값을 동적으로 결정.

    범위가 넓을수록 더 다양한 참고 문서가 필요하므로 k를 늘린다.
    너무 크면 노이즈·비용·latency 모두 증가하므로 상한은 10으로 고정.

    - 1일       → 3  (오늘 단독 분석)
    - ~1주(≤7)  → 5  (주간 리뷰)
    - ~1달(≤31) → 7  (월간 리뷰)
    - 그 이상   → 10 (장기/연간 리뷰)
    """
    days = (end_date - start_date).days
    if days == 0:
        return 3
    if days <= 7:
        return 5
    if days <= 31:
        return 7
    return 10


def search_rag(query, k=5):
    """하이브리드 검색 (FAISS + BM25 → RRF → Cross-encoder 리랭킹)."""
    try:
        searcher = load_rag()
        raw = searcher.search(query, k=k, fetch_k=k * 3)
        results = []
        for doc in raw:
            source = doc.get("source", "알 수 없음")
            ce = doc.get("ce_score")
            score_str = f"CE={ce:.2f}" if ce is not None else f"RRF={doc.get('rrf_score', 0):.4f}"
            results.append({
                "content": f"[출처: {source} | {score_str}]\n{doc['content'][:300]}",
                "score":   doc.get("rrf_score", 0),
                "source":  source,
                "doc_type": doc.get("doc_type", "refined"),
            })
        return results
    except Exception:
        logger.exception("RAG 검색 오류")
        return []


def build_rag_queries(diaries, a_mood, a_sleep, a_exercise, a_med, a_finance):
    """실제 일기 데이터를 분석해 상태에 맞는 검색 쿼리를 동적 생성."""
    if not diaries:
        return []

    queries = []
    n = len(diaries)

    if a_mood:
        avg_mood = sum(d["mood"] for d in diaries) / n
        avg_stress = sum(d["stress"] for d in diaries) / n
        diary_texts = " ".join(d.get("diary", "") for d in diaries if d.get("diary"))[:300]

        if avg_mood < 4:
            queries.append(f"심한 우울 무기력 회복 인지행동치료 {diary_texts}")
        elif avg_mood < 6 or avg_stress > 7:
            queries.append(f"우울 스트레스 감정 조절 CBT {diary_texts}")
        else:
            queries.append(f"감정 웰빙 정신건강 유지 {diary_texts}")

    if a_sleep:
        avg_sleep = sum(d["sleep"]["hours"] for d in diaries) / n
        if avg_sleep < 5:
            queries.append("심한 수면 부족 불면증 수면 장애 치료 방법")
        elif avg_sleep < 7:
            queries.append("수면 부족 수면 위생 개선 수면 패턴")
        else:
            queries.append("수면 품질 유지 수면 건강")

    if a_exercise:
        drink_days = sum(1 for d in diaries if d["drinking"]["status"] == "했어")
        exercise_days = sum(1 for d in diaries if d["exercise"]["status"] == "했어")
        if drink_days > n * 0.3:
            queries.append("음주 절주 생활습관 정신건강 음주 영향")
        elif exercise_days < n * 0.3:
            queries.append("운동 부족 신체활동 정신건강 동기부여")
        else:
            queries.append("운동 생활습관 정신건강 유지")

    if a_med:
        missed = sum(
            1 for d in diaries
            if d["medication"]["morning"]["status"] == "안 먹었어"
            or d["medication"]["night"]["status"] == "안 먹었어"
        )
        if missed > 0:
            queries.append(f"항우울제 약물 복용 순응도 누락 {missed}회 영향")
        else:
            queries.append("항우울제 약물 복용 지속 효과 정신과 치료")

    if a_finance:
        queries.append("부채 재정 관리 스트레스 경제적 어려움 심리")

    return queries


def _list_retrospects() -> list[str]:
    """data/retrospects/ 폴더의 마크다운 파일 목록을 최신순으로 반환."""
    retro_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data", "retrospects",
    )
    if not os.path.isdir(retro_dir):
        return []
    files = sorted(
        [f for f in os.listdir(retro_dir) if f.endswith(".md")],
        reverse=True,
    )
    return [os.path.join(retro_dir, f) for f in files]


# ── UI: 제목 + 입력 폼 ────────────────────────────────────────────────────────
st.title("🤖 Claude 분석")

st.markdown("**📅 분석 기간 선택**")
quick = st.radio("빠른 선택", ["오늘", "이번 주", "이번 달", "올해", "직접 선택"], horizontal=True)

today_dt = date.today()
if quick == "오늘":
    start_date = today_dt
    end_date = today_dt
elif quick == "이번 주":
    start_date = today_dt - timedelta(days=today_dt.weekday())
    end_date = today_dt
elif quick == "이번 달":
    start_date = today_dt.replace(day=1)
    end_date = today_dt
elif quick == "올해":
    start_date = today_dt.replace(month=1, day=1)
    end_date = today_dt
else:
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("시작일", value=today_dt - timedelta(days=7))
    with col2:
        end_date = st.date_input("종료일", value=today_dt)

st.markdown(f"**선택 기간: {start_date.strftime('%Y.%m.%d')} ~ {end_date.strftime('%Y.%m.%d')}**")

st.markdown("**분석 항목 선택**")
col1, col2, col3 = st.columns(3)
with col1:
    a_mood = st.checkbox("😊 기분/스트레스", value=True)
    a_sleep = st.checkbox("😴 수면 패턴", value=True)
with col2:
    a_exercise = st.checkbox("💪 운동/음주", value=True)
    a_meal = st.checkbox("🍽️ 식사 패턴", value=True)
with col3:
    a_goal = st.checkbox("🎯 목표 달성률", value=True)
    a_med = st.checkbox("💊 투약 패턴", value=True)
    a_finance = st.checkbox("💰 재무 상태", value=True)


# ── 분석 버튼 핸들러 ──────────────────────────────────────────────────────────
if st.button("🤖 분석 시작", type="primary"):
    diaries = load_diaries_range_db(start_date, end_date)

    if not diaries:
        st.warning("선택한 기간에 일기가 없어!")
    else:
        scores = [calc_stability_score(d) for d in diaries]
        avg_score = int(sum(s for s in scores if s is not None) / len(scores)) if scores else 0
        label, emoji = stability_label(avg_score)

        col_s1, col_s2, col_s3 = st.columns(3)
        with col_s1:
            st.metric("🔋 평균 안정 점수", f"{avg_score}점")
        with col_s2:
            st.metric("📊 상태", f"{emoji} {label}")
        with col_s3:
            st.metric("📅 분석 일수", f"{len(diaries)}일")

        st.progress(avg_score / 100)
        st.markdown("---")

        with st.spinner("Claude가 분석 중이야... 잠깐만!"):
            month_goals = load_month_goals_db(start_date.year, start_date.month)
            iso_year, week_num, _ = start_date.isocalendar()
            week_goals = load_week_goals_db(iso_year, week_num)

            summary = f"분석 기간: {start_date} ~ {end_date}, 총 {len(diaries)}일\n\n"

            if month_goals:
                summary += f"📅 월간 목표: {', '.join(month_goals)}\n"
            if week_goals:
                summary += f"📆 주간 목표: {', '.join(week_goals)}\n"
            summary += "\n"

            for d in diaries:
                summary += f"[{d['date']}]\n"
                if a_mood:
                    summary += f"- 기분: {d['mood']}점, 스트레스: {d['stress']}점\n"
                if a_sleep:
                    summary += f"- 수면: {d['sleep']['hours']}시간\n"
                if a_exercise:
                    summary += f"- 운동: {d['exercise']['status']}"
                    if d['exercise'].get('detail'):
                        summary += f" ({d['exercise']['detail']})"
                    summary += f"\n- 음주: {d['drinking']['status']}"
                    if d['drinking'].get('amount'):
                        summary += f" ({d['drinking']['amount']})"
                    summary += "\n"
                if a_meal:
                    m = d['meal']
                    summary += f"- 식사: 아침({'O' if m['morning']['eaten'] else 'X'}) 점심({'O' if m['lunch']['eaten'] else 'X'}) 저녁({'O' if m['dinner']['eaten'] else 'X'})\n"
                if a_med:
                    med = d['medication']
                    summary += f"- 투약: 아침약({med['morning']['status']}) 취침약({med['night']['status']})\n"
                if a_goal and d.get('weekly_checks'):
                    pct = goal_achievement(d)
                    summary += f"- 목표달성률: {pct}%\n"
                    for goal, done in d['weekly_checks'].items():
                        summary += f"  {'✅' if done else '❌'} {goal}\n"
                if d.get('diary'):
                    summary += f"- 일기: {d['diary']}\n"
                summary += "\n"

            if a_finance:
                loans = load_loans_db()
                fixed = load_fixed_db()
                income = load_income_db()
                ledger = load_ledger_db()

                total_current = sum(l["current_amount"] for l in loans)
                total_original = sum(l["original"] for l in loans)
                total_monthly_repay = sum(l["monthly"] for l in loans)
                total_fixed = sum(f["amount"] for f in fixed) + total_monthly_repay

                this_month = start_date.strftime("%Y-%m")
                month_ledger = [e for e in ledger if e["date"].startswith(this_month)]
                variable_expense = sum(e["amount"] for e in month_ledger if e["type"] == "지출")
                total_expense = total_fixed + variable_expense
                balance = income["monthly"] - total_expense

                summary += "💰 재무 상태\n"
                summary += f"- 현재 수입: {income['monthly']:,}원 ({income['memo']})\n"
                summary += f"- 총 대출 잔액: {total_current:,}원\n"
                summary += f"- 월 고정지출: {total_fixed:,}원\n"
                summary += f"- 이번 달 변동지출: {variable_expense:,}원\n"
                summary += f"- 이번 달 잔액: {balance:,}원\n\n"

            rag_queries = build_rag_queries(diaries, a_mood, a_sleep, a_exercise, a_med, a_finance)
            rag_k = _rag_k_for_range(start_date, end_date)

            rag_context = ""
            all_sources = []
            seen_contents = set()
            for query in rag_queries:
                for r in search_rag(query, k=rag_k):
                    content_key = r["content"][:150]
                    if content_key not in seen_contents:
                        seen_contents.add(content_key)
                        rag_context += r["content"] + "\n\n"
                        all_sources.append(r["source"])

            u = USER_PROFILE
            goals_str = "\n".join(f"{i+1}. {g}" for i, g in enumerate(u["goals"]))
            prompt = f"""
너는 내 생활 운영 코치야.
전문 문서 참고해서 근거 있게 분석해줘.
근데 나를 고장난 사람처럼 보지 말고, 생활 패턴이랑 흐름 중심으로 현실적으로 봐줘.
친구처럼 반말로 친근하게 알려줘

[나에 대해]
- 이름: {u["name"]}, {u["age"]}세
{u["about"]}

[현재 목표]
{goals_str}

[분석할 때 이것만 지켜줘]
{u["analysis_rules"]}

[전문 문서 참고자료]
{rag_context}

[일기 데이터]
{summary}

아래 순서로 분석해줘. 반말로, 너무 무겁지 않게, 담백하게:

1. 📊 이번 기간 패턴 (수면/운동/음주/투약/감정)
   - 전문 문서 내용이 직접 관련되면 "수면 가이드에 따르면~" 식으로 자연스럽게 인용
   - 섹션 끝에 참고한 문서명 한 줄로 표시

2. 💡 눈에 띄는 것 (패턴, 연결고리)
   - 전문 문서 근거 있으면 인라인으로 인용

3. ⚠️ 신경 쓸 부분 (과하지 않게, 1~2개만)
   - 전문 문서 근거 있으면 인라인으로 인용

4. 🌟 잘 되고 있는 것 (안정 요소 중심)

5. 🎯 루틴 지속 가능성

6. 💪 내일 바로 할 수 있는 것 (1~2개만, 작고 현실적으로)

7. 💰 재무 흐름 (간단하게)

인용 방식:
- 본문 중간: "수면 가이드에 따르면~", "CBT 워크북에서는~" 식으로 자연스럽게
- 섹션 끝: (참고: 파일명) 형식으로 간단하게
- 관련 없으면 억지로 인용하지 마
"""

            t0 = time.time()
            try:
                response = call_claude(
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=8000,
                    timeout=120.0,
                )
                duration = time.time() - t0
                log_api_call(
                    page="Claude분석",
                    query_summary=f"{start_date}~{end_date} | {len(diaries)}일",
                    rag_docs_count=len(all_sources),
                    duration_sec=duration,
                    input_tokens=response.input_tokens,
                    output_tokens=response.output_tokens,
                )
                logger.info(
                    "분석 완료: %s~%s | %.1fs | 토큰 %d+%d",
                    start_date, end_date, duration,
                    response.input_tokens, response.output_tokens,
                )
            except RuntimeError:
                duration = time.time() - t0
                log_api_call(
                    page="Claude분석",
                    query_summary=f"{start_date}~{end_date} | {len(diaries)}일",
                    rag_docs_count=len(all_sources),
                    duration_sec=duration,
                    input_tokens=0,
                    output_tokens=0,
                    error="API 호출 실패",
                )
                st.error("Claude API 호출에 실패했어. 잠시 후 다시 시도해줘.")
                st.stop()

            # 분석 결과를 session_state에 저장 후 즉시 rerun
            # → 버튼 핸들러 바깥의 렌더링 블록이 결과를 표시함
            st.session_state["last_analysis"] = {
                "text":        response.text,
                "avg_score":   avg_score,
                "score_label": f"{emoji} {label}",
                "period":      f"{start_date} ~ {end_date}",
                "start_date":  str(start_date),
                "end_date":    str(end_date),
                "days":        len(diaries),
                "all_sources": all_sources,
            }
            st.rerun()


# ── 분석 결과 표시 (버튼 핸들러 바깥 → 회고저장/CBT 버튼 정상 작동) ──────────
if "last_analysis" in st.session_state:
    _la = st.session_state["last_analysis"]

    st.markdown("---")
    st.markdown("### 🤖 Claude의 분석")
    st.markdown(_la["text"])

    with st.expander("📚 참고한 전문 문서"):
        for source in dict.fromkeys(_la["all_sources"]):
            st.caption(f"📄 {source}")

    st.markdown("---")
    _act1, _act2 = st.columns(2)

    with _act1:
        st.markdown("**📝 회고로 저장하기**")
        st.caption("data/retrospects/ 폴더에 마크다운 파일로 남겨져.")
        if st.button("💾 회고로 저장", type="secondary", width="stretch"):
            _retro_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "data", "retrospects",
            )
            os.makedirs(_retro_dir, exist_ok=True)
            _ts = datetime.now().strftime("%Y%m%d_%H%M")
            _fname = f"{_la['start_date']}_{_la['end_date']}_{_ts}.md"
            _fpath = os.path.join(_retro_dir, _fname)
            _rc = (
                f"# 회고: {_la['start_date']} ~ {_la['end_date']}\n\n"
                f"**저장 시각**: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
                f"**분석 일수**: {_la['days']}일\n\n"
                f"---\n\n"
                f"{_la['text']}\n"
            )
            try:
                with open(_fpath, "w", encoding="utf-8") as _f:
                    _f.write(_rc)
                st.success(f"✅ 회고 저장 완료! → {_fname}")
            except OSError as e:
                st.error(f"❌ 저장 실패: {e}")

    with _act2:
        st.markdown("**🧠 CBT 상담으로 이어가기**")
        st.caption("분석 결과를 CBT 챗봇에 전달해서 바로 대화를 시작할 수 있어.")
        if st.button("🧠 CBT로 이어가기", type="primary", width="stretch"):
            st.session_state["cbt_from_analysis"] = {
                "period":        _la["period"],
                "days":          _la["days"],
                "avg_score":     _la["avg_score"],
                "score_label":   _la["score_label"],
                "analysis_text": _la["text"],
            }
            st.switch_page("pages/7_🧠_CBT챗봇.py")


# ── 저장된 회고 목록 (페이지 하단) ───────────────────────────────────────────
retro_files = _list_retrospects()
if retro_files:
    st.markdown("---")
    st.markdown("### 📚 저장된 회고")
    st.caption(f"총 {len(retro_files)}개")
    for fpath in retro_files:
        fname = os.path.basename(fpath)
        label = fname.replace("_", " ").replace(".md", "")
        with st.expander(f"📝 {label}"):
            try:
                with open(fpath, encoding="utf-8") as f:
                    retro_content = f.read()
                st.markdown(retro_content)
                st.download_button(
                    "⬇️ 마크다운 다운로드",
                    data=retro_content.encode("utf-8"),
                    file_name=fname,
                    mime="text/markdown",
                    key=f"retro_dl_{fname}",
                )
            except OSError:
                st.error("파일을 읽을 수 없어.")
