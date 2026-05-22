import streamlit as st
import os
import sys
import re
import time
import json
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.connection import check_db_connection
from logger import get_logger, log_api_call
from api_client import call_claude
from rag_search import HybridSearcher
from utils import (
    load_diary_db, calc_stability_score, stability_label,
    create_cbt_session, update_cbt_session_title,
    load_cbt_sessions, load_cbt_messages, save_cbt_message, delete_cbt_session,
    save_cbt_emotion_tags, load_cbt_emotion_tags,
    save_cbt_summary, load_cbt_summary,
)
from user_config import USER_PROFILE
from theme import init_page_style

st.set_page_config(page_title="나의 일기장", page_icon="📔", layout="wide")

_db_ok, _db_err = check_db_connection()
if not _db_ok:
    st.error(
        f"⚠️ **DB 연결 실패** — 대화 내용을 저장할 수 없어요.\n\n"
        f"`{_db_err}`\n\n"
        f"MySQL이 실행 중인지 확인해줘."
    )
    st.stop()

init_page_style(extra_css="""
.emotion-chip {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 12px;
    font-size: 0.8rem;
    margin: 2px;
    background: #e8f4f8;
    color: #2c7da0;
    border: 1px solid #a9d6e5;
}
""")

logger = get_logger(__name__)

# ── CBT 모드 ──────────────────────────────────────
CBT_MODES = {
    "자유 대화": (
        "대화 단계에 따라 역할을 바꿔.\n"
        "• 초반(1~3턴): 공감·경청 우선. 판단 없이 상황을 파악해.\n"
        "• 중반(4~7턴): 인지 패턴을 탐색해. '그 생각이 사실이라는 증거는 뭐야?' "
        "같은 소크라테스식 질문으로 왜곡(흑백논리, 재앙화, 자기비난 등)을 부드럽게 짚어.\n"
        "• 후반(8턴+): 재구성(reframing)을 시도하고, 통찰이 나왔으면 "
        "이번 주 실천할 수 있는 가장 작은 행동 1가지를 구체적으로 제안해.\n"
        "공감만 하는 루프에 갇히지 마. 위로는 1~2회로 충분해."
    ),
    "자동사고 탐색": (
        "사용자가 경험한 상황에서 떠오른 자동적 사고를 탐색해.\n"
        "• '그 순간 머릿속에 어떤 말이 지나갔어?' 같은 소크라테스식 질문으로 유도해.\n"
        "• 자동사고가 나오면: '그 생각이 100% 사실이라는 증거가 있어?'로 검증 단계로 넘어가.\n"
        "• 인지 왜곡 패턴(흑백논리·과잉일반화·재앙화·자기비난·독심술)을 감지하면 "
        "부드럽게 이름을 붙여줘. 예: '지금 조금 재앙화가 일어나는 것 같아.'\n"
        "• 탐색 후 반드시 대안 사고를 같이 찾아봐."
    ),
    "사고 기록지": (
        "구조화된 순서로 한 번에 하나씩 질문해:\n"
        "① 상황 파악 → ② 감정과 강도(0~100%) → ③ 자동사고 →\n"
        "④ 그 생각을 지지하는 증거 → ⑤ 반박하는 증거 → ⑥ 대안적 사고 도출.\n"
        "⑤ 반박 증거 단계에서는 절대 서두르지 마. "
        "사용자가 '반박 증거 없어'라고 하면 "
        "'그동안 잘 해낸 경험 중 작은 것 하나만 떠올려봐' 같이 유도해.\n"
        "⑥ 대안 사고 도출 후 '이 새로운 생각을 가지고 이번 주에 뭘 해볼 수 있어?'로 마무리해."
    ),
    "행동 활성화": (
        "우울·무기력 상태에서 작은 행동을 계획하도록 도와.\n"
        "• 오늘 일기의 운동/외출/수면 기록을 참고해 현실적인 활동을 제안해.\n"
        "• '완벽한 계획'이 아니라 '지금 당장 5분 안에 할 수 있는 것'에 집중해.\n"
        "• 행동 제안 형식: 언제 / 어디서 / 무엇을 / 얼마나. 추상적 제안 금지.\n"
        "  예) '운동해봐'(X) → '오늘 저녁 9시, 집 앞 10분 산책'(O)\n"
        "• 사용자가 '못 할 것 같아'라고 하면 더 작게 쪼개. '5분도 괜찮아'로."
    ),
}

# ── 반추 감지 ──────────────────────────────────────
# 부정 자기지시 패턴 — 이 마커가 최근 메시지에 반복되면 반추로 판단
RUMINATION_MARKERS = [
    "난 약해", "나는 안 돼", "나는 못해", "어차피", "소용없어",
    "실패할", "가짜", "자격이 없", "포기", "다 틀렸", "결국 안 돼",
    "역시나", "이미 늦었", "나쁜 사람", "최악이야", "다 망했",
    "나만 그래", "나는 원래", "아무것도 안 돼",
]

def detect_rumination(messages: list[dict], window: int = 6) -> int:
    """
    최근 window개 사용자 메시지에서 반추 패턴 빈도 반환.
    0 = 없음, 1 = 주의 (2회 연속), 2 = 개입 필요 (3회 이상)
    """
    recent_user = [m["content"] for m in messages if m["role"] == "user"][-window:]
    if not recent_user:
        return 0
    hit_count = sum(
        1 for msg in recent_user
        if any(marker in msg for marker in RUMINATION_MARKERS)
    )
    if hit_count >= 3:
        return 2
    if hit_count >= 2:
        return 1
    return 0

# 사고 기록지 단계 감지용 키워드
THOUGHT_RECORD_STEPS = [
    ("① 상황",    ["상황", "있었어", "일이", "언제", "어디서", "무슨 일"]),
    ("② 감정",    ["감정", "느꼈", "기분", "점", "%", "강도"]),
    ("③ 자동사고", ["생각", "떠올랐", "머릿속", "자동", "~라고", "든 생각"]),
    ("④ 지지증거", ["지지", "맞아", "증거", "사실이야", "그럴 것 같아"]),
    ("⑤ 반박증거", ["반박", "반대", "아닐 수도", "다른 가능성", "꼭 그런 건"]),
    ("⑥ 대안사고", ["대안", "다른 생각", "균형", "새로운", "바꿔서 생각"]),
]

# 감정 태그 색상 매핑
EMOTION_COLORS = {
    "불안":   ("#fff3cd", "#856404"),
    "우울":   ("#d1ecf1", "#0c5460"),
    "무기력": ("#e2e3e5", "#383d41"),
    "분노":   ("#f8d7da", "#721c24"),
    "슬픔":   ("#cce5ff", "#004085"),
    "외로움": ("#d4edda", "#155724"),
    "두려움": ("#ffeeba", "#856404"),
    "자기비판":("#f5c6cb", "#721c24"),
    "절망":   ("#d6d8d9", "#1b1e21"),
    "피로":   ("#e2e3e5", "#383d41"),
}

# ── RAG 검색기 (캐시로 한 번만 초기화) ──────────────────────────────────────
@st.cache_resource
def load_rag():
    searcher = HybridSearcher()
    searcher.preload()
    return searcher


SKIP_RAG_KEYWORDS = {"안녕", "hi", "hello", "ㅎㅇ", "ㅋㅋ", "ㅎㅎ", "응", "아", "네",
                     "ㅇㅇ", "고마워", "감사", "알겠어", "ㅇㅋ", "ok", "okay"}

def needs_rag(text: str) -> bool:
    text = text.strip()
    if len(text) < 10:
        return False
    if text.lower() in SKIP_RAG_KEYWORDS:
        return False
    return True


def search_cbt_docs(query, k=3):
    try:
        searcher = load_rag()
        raw = searcher.search(query, k=k, fetch_k=k * 3)
        return [
            {
                "content": doc["content"][:400],
                "source":  doc.get("source", ""),
                "score":   doc.get("ce_score", doc.get("rrf_score", 0)),
            }
            for doc in raw
        ]
    except Exception:
        logger.exception("CBT RAG 검색 오류")
        return []


# ── 감정 태그 파싱 ──────────────────────────────────────
EMOTION_TAG_PATTERN = re.compile(
    r'---EMOTION_TAGS---\s*\n(.*?)(?:\n---|$)', re.DOTALL
)

def parse_emotion_tags(text: str) -> tuple[str, list[str]]:
    """
    응답 텍스트에서 ---EMOTION_TAGS--- 블록을 파싱해
    (깨끗한 텍스트, 태그 리스트) 반환.
    """
    m = EMOTION_TAG_PATTERN.search(text)
    if not m:
        return text.strip(), []

    tags_raw = m.group(1).strip()
    # JSON 배열 or 쉼표 분리
    try:
        tags = json.loads(tags_raw)
        if not isinstance(tags, list):
            raise ValueError
    except Exception:
        tags = [t.strip().strip('"\'') for t in tags_raw.split(",") if t.strip()]

    clean = text[:m.start()].strip()
    valid_tags = list(EMOTION_COLORS.keys())
    tags = [t for t in tags if t in valid_tags]
    return clean, tags


def render_emotion_chips(tags: list[str]):
    """감정 태그를 컬러 칩으로 렌더링."""
    if not tags:
        return
    chips = ""
    for tag in tags:
        bg, fg = EMOTION_COLORS.get(tag, ("#e8f4f8", "#2c7da0"))
        chips += (
            f'<span style="display:inline-block;padding:2px 10px;border-radius:12px;'
            f'font-size:0.8rem;margin:2px;background:{bg};color:{fg};'
            f'border:1px solid {fg}40;">{tag}</span>'
        )
    st.markdown(chips, unsafe_allow_html=True)


# ── 사고 기록지 진행 상황 감지 ──────────────────────────────────────
def detect_thought_record_step(messages: list[dict]) -> int:
    """
    대화 내용을 분석해 사고 기록지의 현재 진행 단계(0~6)를 반환.
    """
    all_text = " ".join(m["content"] for m in messages).lower()
    completed = 0
    for _, keywords in THOUGHT_RECORD_STEPS:
        if any(kw in all_text for kw in keywords):
            completed += 1
        else:
            break
    return completed


def render_thought_record_progress(step: int):
    """사고 기록지 6단계 진행 표시."""
    labels = [s[0] for s in THOUGHT_RECORD_STEPS]
    cols = st.columns(6)
    for i, (col, label) in enumerate(zip(cols, labels)):
        with col:
            if i < step:
                st.markdown(f"✅ **{label}**")
            elif i == step:
                st.markdown(f"🔄 **{label}**")
            else:
                st.markdown(f"⬜ {label}")


# ── 시스템 프롬프트 ──────────────────────────────────────
def build_system_prompt(
    today_diary,
    mode_name: str,
    mode_instruction: str,
    rag_docs: list,
    rumination_level: int = 0,
    turn_count: int = 0,
    analysis_context: dict | None = None,
):
    u = USER_PROFILE

    diary_summary = "오늘 일기 없음"
    if today_diary:
        score = calc_stability_score(today_diary)
        label, emoji = stability_label(score)
        diary_summary = (
            f"기분 {today_diary['mood']}점 | 스트레스 {today_diary['stress']}점 | "
            f"수면 {today_diary['sleep']['hours']}시간 | "
            f"아침약 {today_diary['medication']['morning']['status']} | "
            f"안정점수 {score}점 {emoji} {label}"
        )
        if today_diary.get("diary"):
            diary_summary += f"\n일기 내용: {today_diary['diary'][:200]}"

    rag_context = ""
    if rag_docs:
        rag_context = "\n\n[참고 CBT 문서]\n" + "\n\n".join(
            f"[{r['source']}]\n{r['content']}" for r in rag_docs
        )

    # ── 분석 연계 컨텍스트 ──────────────────────────────────────
    analysis_section = ""
    if analysis_context:
        analysis_section = (
            f"\n[📊 Claude 분석 결과 — 이 대화의 배경 컨텍스트]\n"
            f"기간: {analysis_context['period']} ({analysis_context['days']}일)\n"
            f"안정 점수: {analysis_context['avg_score']}점 {analysis_context['score_label']}\n\n"
            f"분석 요약 (앞 800자):\n{analysis_context['analysis_text'][:800]}\n"
            f"---\n"
            f"이 분석을 배경 지식으로 사용해. 분석 내용을 직접 읊지 말고 "
            f"사용자의 말 속에서 자연스럽게 연결해줘.\n"
        )

    valid_emotions = ", ".join(EMOTION_COLORS.keys())

    # ── 반추 감지 신호 ──────────────────────────────────────
    rumination_instruction = ""
    if rumination_level == 2:
        rumination_instruction = """
[⚠️ 반추 패턴 감지됨 — 지금 당장 개입해]
사용자가 같은 부정적 자기서사("난 안 돼", "어차피", "소용없어" 등)를
최근 메시지에서 3회 이상 반복했어.
→ 지금은 공감보다 패턴 지적이 더 중요해.
다음 순서로 응답해:
1. 공감 1문장 (짧게)
2. "지금 비슷한 생각이 계속 돌고 있는 것 같아. 이 생각이 사실인지 같이 확인해볼게."
3. 증거 탐색 질문 1개로 전환. 예: "지금까지 완전히 실패만 했던 건 아닐 텐데, 최근에 작게라도 해낸 일 하나만 떠올려볼 수 있어?"
절대 "맞아, 정말 힘들겠다"로만 끝내지 마.
"""
    elif rumination_level == 1:
        rumination_instruction = """
[⚡ 반추 패턴 주의]
부정 자기서사가 반복되고 있어. 공감은 유지하되,
이번 응답에서는 슬쩍 "그 생각이 100% 사실인지" 확인하는 질문을 한 개 넣어봐.
"""

    # ── 행동 과제 트리거 ──────────────────────────────────────
    action_trigger = ""
    if turn_count >= 8:
        action_trigger = """
[🎯 행동 과제 트리거]
대화가 충분히 진행됐어. 이번 응답에서 통찰이나 재구성이 나왔다면,
반드시 이렇게 마무리해:
"이번 주에 시도해볼 수 있는 가장 작은 행동 하나만 같이 정해볼까?"
과제 형식: 언제/어디서/무엇을/얼마나. 추상적 제안 금지.
예) "내일 저녁 10분 산책" / "자기 전에 잘된 일 1개 적기"
"""
    elif turn_count >= 5:
        action_trigger = """
[💡 행동 연결 힌트]
인지 탐색이 어느 정도 됐으면, 대화 말미에 작은 행동으로 연결하는 질문을 준비해.
아직 강요하지는 말고, 자연스러운 흐름이 보이면 넣어봐.
"""

    return f"""너는 CBT(인지행동치료) 기반 감정 코칭 보조 도구야.
실제 치료사나 정신과 상담을 대체하지 않아. 이 점을 항상 염두에 둬.

[나에 대해]
이름: {u['name']}, {u['age']}세
{u['about']}

[오늘 상태]
{diary_summary}
{analysis_section}
[현재 모드: {mode_name}]
{mode_instruction}

[대화 규칙]
- 반말로, 친근하고 따뜻하게 대화해
- 한 번에 질문 하나만 해. 여러 질문을 한꺼번에 던지지 마
- 진단하거나 성격을 단정짓지 마
- 공감은 중요하지만, 공감만 하는 루프에 갇히지 마. 위로는 1~2회면 충분해
- 인지 왜곡(재앙화·흑백논리·과잉일반화·자기비난)을 감지하면 이름 붙여주고 증거 탐색으로 전환해
- 위기 신호(자해·자살 언급) 감지 시 즉시 1393(자살예방상담전화) 안내 후 대화 중단
- 치료사/주치의 상담을 대체할 수 없음을 10턴마다 자연스럽게 상기시켜
{rumination_instruction}{action_trigger}
[감정 태그 규칙]
응답 마지막에 반드시 아래 형식으로 사용자가 표현한 감정 태그를 추가해.
후보 감정: {valid_emotions}
형식 (감지된 감정만, 없으면 빈 배열):
---EMOTION_TAGS---
["감정1", "감정2"]
{rag_context}"""


# ── 세션 제목 자동 생성 ──────────────────────────────────────
def generate_session_title(first_user_message):
    try:
        resp = call_claude(
            messages=[{
                "role": "user",
                "content": f"다음 문장을 10자 이내 제목으로 요약해. 제목만 출력해:\n{first_user_message[:200]}"
            }],
            max_tokens=30,
            timeout=15.0,
        )
        return resp.text.strip()
    except RuntimeError:
        return first_user_message[:20]


# ── 세션 요약 생성 ──────────────────────────────────────
def generate_session_summary(messages: list[dict]) -> str:
    if len(messages) < 4:
        return "대화가 너무 짧아서 요약할 내용이 없어."

    conversation = "\n".join(
        f"[{'나' if m['role'] == 'user' else '챗봇'}] {m['content'][:200]}"
        for m in messages[-30:]   # 최근 30개 메시지
    )
    prompt = f"""아래 CBT 상담 대화를 4가지 항목으로 구조화해서 요약해줘.
반말로, 간결하게.

[대화]
{conversation}

형식:
**주요 고민**: (1~2문장)
**탐색된 패턴**: (핵심 자동사고·인지 왜곡 패턴·감정 흐름. 없으면 "탐색 안 됨")
**재구성 시도**: (대안 사고나 새로운 관점이 나왔으면 요약. 없으면 "없음")
**행동 과제**: (대화에서 합의된 구체적 행동 1가지. 형식: 언제/무엇. 없으면 "없음")

행동 과제는 반드시 구체적으로 써. "뭔가 해보기"(X) → "내일 저녁 10분 산책"(O)"""

    try:
        resp = call_claude(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            timeout=30.0,
        )
        return resp.text.strip()
    except RuntimeError:
        return "요약 생성에 실패했어. 나중에 다시 시도해줘."


# ── 사이드바 ──────────────────────────────────────
with st.sidebar:
    st.markdown("### 🧠 CBT 챗봇")

    mode_name = st.selectbox("CBT 모드", list(CBT_MODES.keys()))

    st.markdown("---")

    if st.button("➕ 새 대화 시작", width="stretch"):
        new_id = create_cbt_session(date.today())
        if new_id:
            st.session_state.cbt_session_id = new_id
            st.session_state.cbt_messages = []
            st.session_state.pop("cbt_summary", None)
            st.session_state.pop("cbt_emotion_tags", None)
            # 새 대화 시작 시 분석 연계 컨텍스트 초기화
            st.session_state.pop("cbt_from_analysis", None)
            st.rerun()

    # 세션 요약 버튼
    if "cbt_session_id" in st.session_state:
        msgs = st.session_state.get("cbt_messages", [])
        if len(msgs) >= 4:
            if st.button("📝 이 대화 요약", width="stretch"):
                with st.spinner("요약 생성 중..."):
                    summary = generate_session_summary(msgs)
                    save_cbt_summary(st.session_state.cbt_session_id, summary)
                    st.session_state.cbt_summary = summary

        saved_summary = st.session_state.get("cbt_summary") or load_cbt_summary(
            st.session_state.get("cbt_session_id", -1)
        )
        if saved_summary:
            with st.expander("📋 대화 요약", expanded=False):
                st.markdown(saved_summary)

    st.markdown("---")

    # 이전 세션 목록
    st.markdown("#### 📋 이전 대화")
    sessions = load_cbt_sessions(limit=20)
    if sessions:
        for s in sessions:
            col_btn, col_del = st.columns([5, 1])
            with col_btn:
                label = f"{s['date']} {s['title']}"
                if st.button(label, key=f"ses_{s['id']}", width="stretch"):
                    st.session_state.cbt_session_id = s["id"]
                    st.session_state.cbt_messages = load_cbt_messages(s["id"])
                    st.session_state.cbt_emotion_tags = s.get("emotion_tags", [])
                    st.session_state.pop("cbt_summary", None)
                    # 이전 세션 불러올 때 분석 연계 컨텍스트 초기화
                    st.session_state.pop("cbt_from_analysis", None)
                    st.rerun()
            with col_del:
                if st.button("🗑️", key=f"del_{s['id']}"):
                    delete_cbt_session(s["id"])
                    if st.session_state.get("cbt_session_id") == s["id"]:
                        del st.session_state["cbt_session_id"]
                        st.session_state.cbt_messages = []
                        st.session_state.pop("cbt_emotion_tags", None)
                        st.session_state.pop("cbt_summary", None)
                    st.rerun()
    else:
        st.caption("아직 대화가 없어.")

    st.markdown("---")
    today_diary = load_diary_db(date.today().strftime("%Y-%m-%d"))
    if today_diary:
        score = calc_stability_score(today_diary)
        label, emoji = stability_label(score)
        st.markdown("#### 오늘 상태")
        st.markdown(f"기분 **{today_diary['mood']}점** | 스트레스 **{today_diary['stress']}점**")
        st.markdown(f"수면 **{today_diary['sleep']['hours']}시간** | {emoji} **{label}**")
    else:
        st.caption("오늘 일기를 먼저 써줘!")


# ── 메인 ──────────────────────────────────────
st.title("🧠 CBT 챗봇")
st.caption("인지행동치료 기반 감정 코칭 보조 도구 | 전문 치료사/정신과 상담을 대체하지 않습니다")

# ── 분석 연동 처리 ──────────────────────────────────────────────────────────
# Claude분석 페이지에서 "CBT로 이어가기" 버튼을 눌렀을 때
# st.session_state["cbt_from_analysis"]에 분석 결과가 담겨서 넘어옴
_analysis_ctx: dict | None = st.session_state.get("cbt_from_analysis")

# 분석에서 넘어온 경우 → 세션 자동 생성 (사이드바 "새 대화 시작" 없이도 시작)
if _analysis_ctx and "cbt_session_id" not in st.session_state:
    _new_id = create_cbt_session(date.today())
    if _new_id:
        st.session_state.cbt_session_id   = _new_id
        st.session_state.cbt_messages     = []
        st.session_state.cbt_emotion_tags = []
        update_cbt_session_title(_new_id, f"분석연계: {_analysis_ctx.get('period', '')}")

# 분석 배너 표시 (세션이 살아있는 동안 계속 보여줌)
if _analysis_ctx:
    st.info(
        f"📊 **분석 연계 상담** | {_analysis_ctx['period']} ({_analysis_ctx['days']}일) "
        f"| 안정점수 {_analysis_ctx['avg_score']}점 {_analysis_ctx['score_label']}"
    )
    with st.expander("📋 분석 내용 전체 보기"):
        st.markdown(_analysis_ctx["analysis_text"])
    st.markdown("---")

if "cbt_session_id" not in st.session_state:
    st.info("왼쪽 사이드바에서 **새 대화 시작** 버튼을 눌러줘!")
    st.stop()

if "cbt_messages" not in st.session_state:
    st.session_state.cbt_messages = load_cbt_messages(st.session_state.cbt_session_id)

if "cbt_emotion_tags" not in st.session_state:
    st.session_state.cbt_emotion_tags = load_cbt_emotion_tags(st.session_state.cbt_session_id)

# ── 분석 연계: 첫 메시지 자동 생성 ─────────────────────────────────────────────
# 조건: 분석에서 넘어왔고 + 메시지가 없는 새 세션
if _analysis_ctx and not st.session_state.get("cbt_messages"):
    with st.spinner("분석 결과를 바탕으로 상담을 준비 중이야..."):
        _sys = build_system_prompt(
            today_diary=today_diary,
            mode_name=mode_name,
            mode_instruction=CBT_MODES[mode_name],
            rag_docs=[],
            analysis_context=_analysis_ctx,
        )
        _intro_prompt = (
            f"분석 기간 {_analysis_ctx['period']}의 일기 분석 결과를 읽었어. "
            f"CBT 상담의 첫 인사를 해줘. "
            f"분석에서 눈에 띈 패턴 하나를 자연스럽게 언급하고, "
            f"오늘 어떤 이야기를 나누고 싶은지 부드럽게 물어봐. "
            f"반말로, 따뜻하게, 2~3문장으로만."
        )
        try:
            _resp = call_claude(
                messages=[{"role": "user", "content": _intro_prompt}],
                system=_sys,
                max_tokens=250,
                timeout=30.0,
            )
            _first_answer, _first_tags = parse_emotion_tags(_resp.text)
        except RuntimeError:
            _first_answer = (
                f"안녕! {_analysis_ctx['period']} 분석 같이 봤어. "
                f"이 기간에 가장 마음에 걸렸던 게 뭐야?"
            )
            _first_tags = []

    save_cbt_message(st.session_state.cbt_session_id, "assistant", _first_answer)
    st.session_state.cbt_messages = [{"role": "assistant", "content": _first_answer}]
    if _first_tags:
        save_cbt_emotion_tags(st.session_state.cbt_session_id, _first_tags)
        st.session_state.cbt_emotion_tags = _first_tags
    st.rerun()

# ── 사고 기록지 진행 상황 ──────────────────────────────────────
if mode_name == "사고 기록지" and st.session_state.cbt_messages:
    step = detect_thought_record_step(st.session_state.cbt_messages)
    st.markdown(f"**사고 기록지 진행 ({step}/6단계)**")
    render_thought_record_progress(step)
    st.markdown("---")

# ── 반추 감지 상태 표시 ──────────────────────────────────────
if st.session_state.cbt_messages:
    r_level = detect_rumination(st.session_state.cbt_messages)
    if r_level == 2:
        st.warning("⚠️ 같은 부정적 생각이 반복되고 있어. 챗봇이 흐름을 바꾸려 시도 중이야.")
    elif r_level == 1:
        st.info("💡 비슷한 생각이 반복되는 것 같아. 조금 다른 각도에서 살펴볼까?")

# ── 감정 태그 표시 ──────────────────────────────────────
if st.session_state.cbt_emotion_tags:
    st.markdown("**이 대화의 감정:**")
    render_emotion_chips(st.session_state.cbt_emotion_tags)
    st.markdown("")

# ── 대화 이력 ──────────────────────────────────────
for msg in st.session_state.cbt_messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ── 입력창 ──────────────────────────────────────
user_input = st.chat_input("무슨 생각이 들어? 자유롭게 말해줘.")

if user_input:
    with st.chat_message("user"):
        st.markdown(user_input)
    save_cbt_message(st.session_state.cbt_session_id, "user", user_input)
    st.session_state.cbt_messages.append({"role": "user", "content": user_input})

    if len(st.session_state.cbt_messages) == 1:
        title = generate_session_title(user_input)
        update_cbt_session_title(st.session_state.cbt_session_id, title)

    rag_docs = search_cbt_docs(user_input, k=3) if needs_rag(user_input) else []

    # 반추 수준 & 대화 턴 수 계산 (시스템 프롬프트 동적 조정)
    rumination_level = detect_rumination(st.session_state.cbt_messages)
    turn_count = sum(1 for m in st.session_state.cbt_messages if m["role"] == "user")

    system_prompt = build_system_prompt(
        today_diary=today_diary,
        mode_name=mode_name,
        mode_instruction=CBT_MODES[mode_name],
        rag_docs=rag_docs,
        rumination_level=rumination_level,
        turn_count=turn_count,
        analysis_context=_analysis_ctx,   # 분석 연계 시 컨텍스트 유지
    )

    # Claude API 규칙: 첫 메시지는 반드시 user 역할이어야 함.
    # 분석 연계 시 assistant 인트로 메시지가 맨 앞에 오면 BadRequestError 발생.
    # → 앞쪽의 연속된 assistant 메시지를 건너뛰고 첫 user 메시지부터 전달.
    _history_raw = [
        {"role": m["role"], "content": m["content"]}
        for m in st.session_state.cbt_messages
    ]
    _first_user = next(
        (i for i, m in enumerate(_history_raw) if m["role"] == "user"),
        len(_history_raw),
    )
    history = _history_raw[_first_user:]

    with st.chat_message("assistant"):
        with st.spinner(""):
            t0 = time.time()

            # ── 레이어 1: API 호출 (네트워크/인증 실패만 여기서 처리) ──────────
            # [설계 이유]
            # 이전 코드는 API 호출 + 파싱 + 로깅을 하나의 try 블록으로 묶어,
            # 파싱 실패 시에도 "연결이 안 됐어" 메시지가 뜨며
            # 실제로는 성공한 Claude 응답이 통째로 사라지는 문제가 있었음.
            # → API / 파싱 / 로깅을 독립된 레이어로 분리.
            try:
                response = call_claude(
                    messages=history,
                    system=system_prompt,
                    max_tokens=1100,   # 응답 + EMOTION_TAGS 블록 여유
                    timeout=60.0,
                )
                duration = time.time() - t0
                api_ok = True
            except RuntimeError:
                duration = time.time() - t0
                logger.error("CBT Claude API 오류 (retry 소진)")
                api_ok = False
                answer = "지금 잠깐 연결이 안 됐어. 다시 시도해줘."
                new_tags = []

            if api_ok:
                # ── 레이어 2: 파싱 (실패해도 원문 텍스트는 반드시 살림) ─────────
                try:
                    answer, new_tags = parse_emotion_tags(response.text)
                except Exception:
                    logger.exception("감정 태그 파싱 오류 — 원문 텍스트로 폴백")
                    answer = response.text   # 파싱 실패해도 Claude 응답 본문은 보존
                    new_tags = []

                # ── 레이어 3: 로깅 (실패해도 UX에 영향 없어야 함) ────────────────
                try:
                    log_api_call(
                        page="CBT챗봇",
                        query_summary=user_input[:100],
                        rag_docs_count=len(rag_docs),
                        duration_sec=duration,
                        input_tokens=response.input_tokens,
                        output_tokens=response.output_tokens,
                    )
                    logger.info("CBT 응답: %.1fs | 토큰 %d+%d | 감정 태그: %s",
                                duration, response.input_tokens, response.output_tokens, new_tags)
                except Exception:
                    logger.exception("CBT API 로그 기록 실패 (UX 영향 없음)")

            st.markdown(answer)

            # 감정 칩 인라인 표시
            if new_tags:
                render_emotion_chips(new_tags)

    # 저장
    save_cbt_message(st.session_state.cbt_session_id, "assistant", answer)
    st.session_state.cbt_messages.append({"role": "assistant", "content": answer})

    # 감정 태그 누적
    if new_tags:
        save_cbt_emotion_tags(st.session_state.cbt_session_id, new_tags)
        all_tags = st.session_state.get("cbt_emotion_tags", [])
        merged = list(dict.fromkeys(all_tags + new_tags))
        st.session_state.cbt_emotion_tags = merged

    # 참고 문서 표시
    if rag_docs:
        with st.expander("📚 참고한 CBT 문서"):
            for r in rag_docs:
                st.caption(f"📄 {r['source']} (점수: {r['score']:.2f})")
