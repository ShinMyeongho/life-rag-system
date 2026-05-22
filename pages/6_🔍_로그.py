import streamlit as st
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from logger import read_api_logs, read_error_logs

st.set_page_config(page_title="나의 일기장", page_icon="📔", layout="wide")
from theme import init_page_style
init_page_style()

st.title("🔍 로그 분석")

tab_api, tab_err = st.tabs(["📡 API 호출 이력", "⚠️ 에러 로그"])

with tab_api:
    logs = read_api_logs(limit=200)

    if not logs:
        st.info("아직 API 호출 기록이 없어. Claude 분석을 먼저 실행해봐!")
    else:
        # ── 요약 지표 ──────────────────────────────────────
        total_calls   = len(logs)
        avg_duration  = sum(e["duration_sec"] for e in logs) / total_calls
        total_tokens  = sum(e["total_tokens"] for e in logs)
        avg_rag_docs  = sum(e["rag_docs_count"] for e in logs) / total_calls
        error_count   = sum(1 for e in logs if e.get("error"))

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("총 호출 수",      f"{total_calls}회")
        c2.metric("평균 응답 시간",   f"{avg_duration:.1f}초")
        c3.metric("누적 토큰",        f"{total_tokens:,}")
        c4.metric("평균 RAG 문서 수", f"{avg_rag_docs:.1f}개")
        c5.metric("에러 횟수",        f"{error_count}회")

        st.markdown("---")

        # ── 응답 시간 추이 차트 ──────────────────────────────────────
        if total_calls >= 2:
            import pandas as pd
            df = pd.DataFrame(logs)
            df["ts"] = pd.to_datetime(df["ts"])
            df = df.set_index("ts")

            st.markdown("#### 응답 시간 추이 (초)")
            st.line_chart(df["duration_sec"])

            st.markdown("#### 호출별 토큰 사용량")
            st.bar_chart(df[["input_tokens", "output_tokens"]])

        st.markdown("---")

        # ── 최근 호출 테이블 ──────────────────────────────────────
        st.markdown("#### 최근 호출 이력")

        for e in reversed(logs[-50:]):
            status = "🔴 실패" if e.get("error") else "🟢 성공"
            with st.expander(
                f"{status} | {e['ts']} | {e['duration_sec']}초 | "
                f"토큰 {e['total_tokens']:,} | {e['query_summary']}"
            ):
                col_l, col_r = st.columns(2)
                with col_l:
                    st.write(f"**페이지:** {e['page']}")
                    st.write(f"**입력 토큰:** {e['input_tokens']:,}")
                    st.write(f"**출력 토큰:** {e['output_tokens']:,}")
                with col_r:
                    st.write(f"**RAG 문서 수:** {e['rag_docs_count']}")
                    st.write(f"**응답 시간:** {e['duration_sec']}초")
                    if e.get("error"):
                        st.error(f"에러: {e['error']}")

with tab_err:
    errors = read_error_logs(limit=100)

    if not errors:
        st.success("에러 로그가 없어! 정상 동작 중이야.")
    else:
        st.warning(f"총 {len(errors)}개의 에러/경고가 기록됐어.")
        st.markdown("---")
        for line in reversed(errors):
            st.code(line, language=None)
