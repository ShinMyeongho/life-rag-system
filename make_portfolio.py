"""
포트폴리오 PDF 생성 스크립트
실행: python make_portfolio.py
"""
from reportlab.lib.pagesizes import A4
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, KeepTogether
)
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ── 폰트 ─────────────────────────────────────────────────────
pdfmetrics.registerFont(TTFont('Mg',  'C:/Windows/Fonts/malgun.ttf'))
pdfmetrics.registerFont(TTFont('MgB', 'C:/Windows/Fonts/malgunbd.ttf'))

# ── 색상 ─────────────────────────────────────────────────────
NAVY  = colors.HexColor('#1e3a5f')
BLUE  = colors.HexColor('#2d6a9f')
GOLD  = colors.HexColor('#b8860b')
SKY   = colors.HexColor('#aad4f5')
LGRAY = colors.HexColor('#f0f4f8')
MGRAY = colors.HexColor('#cccccc')
DGRAY = colors.HexColor('#555555')
WHITE = colors.white

# ── 스타일 헬퍼 ──────────────────────────────────────────────
def S(name, size=10, color=colors.black, bold=False,
      align=TA_LEFT, sb=0, sa=5, leading=None):
    return ParagraphStyle(
        name,
        fontName='MgB' if bold else 'Mg',
        fontSize=size,
        textColor=color,
        alignment=align,
        spaceBefore=sb,
        spaceAfter=sa,
        leading=leading or round(size * 1.5),
    )

# ── 공통 스타일 ───────────────────────────────────────────────
H1   = S('h1',   18, NAVY, True,  sb=14, sa=6)
H2   = S('h2',   12, BLUE, True,  sb=10, sa=4)
BODY = S('body', 10, colors.black, leading=17, sa=4)
SM   = S('sm',    9, DGRAY, leading=14, sa=3)

# ── 문서 설정 ─────────────────────────────────────────────────
OUT = 'C:/Users/Lenovo/Desktop/study/DIARY/portfolio_diary.pdf'
doc = SimpleDocTemplate(
    OUT, pagesize=A4,
    rightMargin=2*cm, leftMargin=2*cm,
    topMargin=1.5*cm, bottomMargin=1.5*cm,
)
W = A4[0] - 4*cm
story = []

# ─────────────────────────────────────────────────────────────
# 헬퍼: 배경색 박스
# ─────────────────────────────────────────────────────────────
def colored_box(items, bg=LGRAY, pad=10):
    t = Table([[item] for item in items], colWidths=[W])
    t.setStyle(TableStyle([
        ('BACKGROUND',    (0,0), (-1,-1), bg),
        ('TOPPADDING',    (0,0), (-1,-1), pad),
        ('BOTTOMPADDING', (0,0), (-1,-1), pad),
        ('LEFTPADDING',   (0,0), (-1,-1), pad + 4),
        ('RIGHTPADDING',  (0,0), (-1,-1), pad + 4),
    ]))
    return t

def two_col_table(rows, w1=0.25, style_extra=None):
    t = Table(rows, colWidths=[W * w1, W * (1 - w1)])
    base = [
        ('FONTNAME',      (0,0), (0,-1), 'MgB'),
        ('FONTNAME',      (1,0), (1,-1), 'Mg'),
        ('FONTSIZE',      (0,0), (-1,-1), 9),
        ('TEXTCOLOR',     (0,0), (0,-1), BLUE),
        ('ROWBACKGROUNDS',(0,0), (-1,-1), [WHITE, LGRAY]),
        ('TOPPADDING',    (0,0), (-1,-1), 7),
        ('BOTTOMPADDING', (0,0), (-1,-1), 7),
        ('LEFTPADDING',   (0,0), (-1,-1), 10),
        ('RIGHTPADDING',  (0,0), (-1,-1), 10),
        ('LINEBELOW',     (0,0), (-1,-2), 0.3, MGRAY),
    ]
    if style_extra:
        base += style_extra
    t.setStyle(TableStyle(base))
    return t

def header_table(rows, col_widths):
    t = Table(rows, colWidths=col_widths)
    t.setStyle(TableStyle([
        ('BACKGROUND',    (0,0), (-1,0), NAVY),
        ('TEXTCOLOR',     (0,0), (-1,0), WHITE),
        ('FONTNAME',      (0,0), (-1,0), 'MgB'),
        ('FONTNAME',      (0,1), (-1,-1), 'Mg'),
        ('FONTSIZE',      (0,0), (-1,-1), 9),
        ('ROWBACKGROUNDS',(0,1), (-1,-1), [WHITE, LGRAY]),
        ('GRID',          (0,0), (-1,-1), 0.3, MGRAY),
        ('TOPPADDING',    (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING',   (0,0), (-1,-1), 8),
        ('RIGHTPADDING',  (0,0), (-1,-1), 8),
        ('VALIGN',        (0,0), (-1,-1), 'MIDDLE'),
    ]))
    return t

# ═════════════════════════════════════════════════════════════
# PAGE 1  커버
# ═════════════════════════════════════════════════════════════
cover_rows = [
    [Spacer(1, 1.5*cm)],
    [Paragraph('나의 일기장', S('ct', 34, WHITE, True, TA_CENTER, leading=42))],
    [Paragraph('개인 자기관리 웹 애플리케이션', S('cs', 14, SKY, align=TA_CENTER, sb=6, sa=8))],
    [Paragraph(
        '일상 기록  &rarr;  생활 데이터  &rarr;  AI 분석',
        S('ca', 11, GOLD, True, TA_CENTER, sa=16),
    )],
    [Table(
        [[Paragraph('Claude AI', S('tag', 9, WHITE, True, TA_CENTER)),
          Paragraph('MySQL', S('tag', 9, WHITE, True, TA_CENTER)),
          Paragraph('Hybrid RAG', S('tag', 9, WHITE, True, TA_CENTER)),
          Paragraph('Streamlit', S('tag', 9, WHITE, True, TA_CENTER))]],
        colWidths=[W/4]*4,
        style=TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), BLUE),
            ('TOPPADDING', (0,0), (-1,-1), 7),
            ('BOTTOMPADDING', (0,0), (-1,-1), 7),
            ('INNERGRID', (0,0), (-1,-1), 0.5, NAVY),
            ('BOX', (0,0), (-1,-1), 0.5, NAVY),
        ])
    )],
    [Spacer(1, 1*cm)],
    [Paragraph('신명호', S('nm', 13, WHITE, True, TA_CENTER, sb=10, sa=4))],
    [Paragraph('2025', S('yr', 10, SKY, align=TA_CENTER, sa=20))],
]
cover = Table(cover_rows, colWidths=[W])
cover.setStyle(TableStyle([
    ('BACKGROUND', (0,0), (-1,-1), NAVY),
    ('TOPPADDING', (0,0), (-1,-1), 10),
    ('BOTTOMPADDING', (0,0), (-1,-1), 10),
    ('LEFTPADDING', (0,0), (-1,-1), 24),
    ('RIGHTPADDING', (0,0), (-1,-1), 24),
]))
story.append(cover)
story.append(PageBreak())

# ═════════════════════════════════════════════════════════════
# PAGE 2  프로젝트 개요 & 기능
# ═════════════════════════════════════════════════════════════
story.append(Paragraph('프로젝트 개요', H1))
story.append(HRFlowable(width='100%', color=NAVY, thickness=1.5))
story.append(Spacer(1, 6))

story.append(Paragraph('기획 배경', H2))
story.append(Paragraph(
    '수면·감정·식사·운동·재정처럼 내 삶과 직결된 데이터를 한곳에 모아 '
    'AI가 분석해주는 도구가 필요했습니다. '
    '시중 앱은 기능이 분산되어 개인화가 부족해서, 직접 설계·구현·운영하기로 했습니다.',
    BODY,
))
story.append(Spacer(1, 4))

goals = [
    ['기록한다', '매일 일기 + 수면·식사·운동·기분 등 생활 지표를 DB에 저장'],
    ['분석한다', 'AI가 전문 자료(CBT·수면·재정)를 참고해 맞춤 리포트 생성'],
    ['관리한다', '목표 달성률, 가계부, CBT 챗봇을 한 앱에서 통합 관리'],
]
story.append(two_col_table(
    [[Paragraph(a, S('ga', 10, WHITE, True, TA_CENTER)),
      Paragraph(b, S('gb', 10, NAVY))] for a, b in goals],
    w1=0.20,
    style_extra=[
        ('BACKGROUND', (0,0), (0,-1), BLUE),
        ('BACKGROUND', (1,0), (1,-1), LGRAY),
        ('TEXTCOLOR',  (0,0), (0,-1), WHITE),
        ('TEXTCOLOR',  (1,0), (1,-1), NAVY),
    ],
))
story.append(Spacer(1, 10))

story.append(Paragraph('앱 구성 (10개 화면)', H2))
menu = [
    ['화면', '역할', '주요 기능'],
    ['홈', '대시보드', '7일 안정점수 그래프 · 오늘 상태 · 목표 현황 · 대출 현황'],
    ['일기 쓰기', '일상 기록', '기분 · 스트레스 · 수면 · 식사 · 운동 · 음주 · 투약 · 자유 일기'],
    ['일기 보기', '기록 열람', '날짜별 조회 · 안정점수 확인 · 월간 캘린더'],
    ['Claude 분석', 'AI 리포트', '선택 기간 데이터 + RAG 검색 → Claude 맞춤 분석 리포트'],
    ['목표 관리', '목표 추적', '월간·주간 목표 설정 · 달성률 시각화'],
    ['가계부', '재정 관리', '대출 상환 진행률 · 수입·지출 통합 관리'],
    ['CBT 챗봇', '심리 지원', '인지행동치료 기반 AI 챗봇 · 감정 태그 · 사고기록지 6단계'],
    ['트렌드', '패턴 분석', '기간별 안정점수 · 기분 · 수면 추이 그래프'],
    ['로그', 'API 이력', 'AI 호출 기록 · 토큰 사용량 · 응답 시간'],
    ['백업', '데이터 보호', 'DB 백업 및 복원'],
]
story.append(header_table(menu, [W*0.16, W*0.16, W*0.68]))
story.append(PageBreak())

# ═════════════════════════════════════════════════════════════
# PAGE 3  핵심 기술 구현
# ═════════════════════════════════════════════════════════════
story.append(Paragraph('핵심 기술 구현', H1))
story.append(HRFlowable(width='100%', color=NAVY, thickness=1.5))
story.append(Spacer(1, 6))

# ── Hybrid RAG
story.append(Paragraph('Hybrid RAG — AI 분석 엔진', H2))
story.append(Paragraph(
    'Claude API에 단순히 질문하는 방식 대신, CBT·수면·재정 전문 자료를 직접 검색해 '
    '근거 문서를 함께 제공함으로써 hallucination을 줄이고 신뢰도 높은 분석을 생성합니다.',
    BODY,
))
story.append(Spacer(1, 4))

rag_pipeline = [
    ['1  이중 검색',  'FAISS 벡터 검색(의미 기반) + BM25 키워드 검색 병렬 실행'],
    ['2  RRF 병합',   'Reciprocal Rank Fusion으로 두 결과 통합 (가중치 0.6 / 0.4)'],
    ['3  리랭킹',     'Cross-encoder(mmarco 한국어 지원)로 최종 5개 문서 선별'],
    ['4  분석 생성',  'Claude API가 선별 문서 + 내 생활 데이터로 맞춤 리포트 작성'],
]
story.append(two_col_table(
    [[Paragraph(a, S('ra', 9, WHITE, True, TA_CENTER)),
      Paragraph(b, S('rb', 9, NAVY))] for a, b in rag_pipeline],
    w1=0.22,
    style_extra=[
        ('BACKGROUND', (0,0), (0,-1), BLUE),
        ('BACKGROUND', (1,0), (1,-1), LGRAY),
        ('TEXTCOLOR',  (0,0), (0,-1), WHITE),
    ],
))
story.append(Spacer(1, 8))

# ── 안정점수
story.append(Paragraph('안정점수 — 내 상태를 숫자로', H2))
story.append(Paragraph(
    '수면·투약·식사·운동·음주·스트레스 6가지 지표를 가중 합산해 0~100점으로 계산합니다. '
    '매일 점수가 누적되면 트렌드 화면에서 내 상태 변화를 그래프로 확인할 수 있습니다.',
    BODY,
))
story.append(Spacer(1, 8))

# ── CBT 챗봇
story.append(Paragraph('CBT 챗봇 — 심리 지원 도구', H2))
story.append(Paragraph(
    '인지행동치료(CBT) 기반으로 Claude와 대화하며 감정을 정리합니다. '
    '감정 태그 자동 추출, 사고기록지 6단계 안내, 세션 요약 자동 생성을 지원합니다.',
    BODY,
))
story.append(Spacer(1, 8))

# ── 기술 스택
story.append(Paragraph('기술 스택', H2))
stack = [
    ['분류', '기술', '역할'],
    ['UI',          'Streamlit',                '웹 인터페이스 · 데이터 시각화'],
    ['데이터베이스', 'MySQL 8.0',               '생활 데이터 정형화 저장 (upsert 패턴)'],
    ['AI 분석',      'Claude API',              '생활 패턴 분석 리포트 생성'],
    ['벡터 검색',    'FAISS + LangChain',       '전문 문서 의미 기반 검색'],
    ['키워드 검색',  'BM25Okapi',               '벡터 검색의 키워드 약점 보완'],
    ['임베딩',       'ko-sroberta-multitask',   '한국어 특화 문장 임베딩 모델'],
    ['리랭킹',       'mmarco Cross-encoder',    '한국어 지원 검색 결과 재정렬'],
    ['운영·모니터링', 'JSONL 로거',             'API 호출 이력 · 토큰 · 지연시간 기록'],
    ['테스트',       'pytest',                  '단위 테스트 127개'],
]
story.append(header_table(stack, [W*0.20, W*0.28, W*0.52]))
story.append(PageBreak())

# ═════════════════════════════════════════════════════════════
# PAGE 4  역량 & 마무리
# ═════════════════════════════════════════════════════════════
story.append(Paragraph('역량 & 배운 점', H1))
story.append(HRFlowable(width='100%', color=NAVY, thickness=1.5))
story.append(Spacer(1, 8))

# 정량 지표 카드 4개
def metric_card(value, label):
    return Table(
        [[Paragraph(value, S('mv', 22, NAVY, True, TA_CENTER, leading=26))],
         [Paragraph(label, S('ml', 9, DGRAY, align=TA_CENTER))]],
        colWidths=[W/4 - 4],
        style=TableStyle([
            ('BACKGROUND',    (0,0), (-1,-1), LGRAY),
            ('TOPPADDING',    (0,0), (-1,-1), 10),
            ('BOTTOMPADDING', (0,0), (-1,-1), 10),
            ('LEFTPADDING',   (0,0), (-1,-1), 4),
            ('RIGHTPADDING',  (0,0), (-1,-1), 4),
            ('BOX',           (0,0), (-1,-1), 0.5, MGRAY),
        ])
    )

metrics_row = Table(
    [[metric_card('10개', '앱 화면'),
      metric_card('127개', '단위 테스트'),
      metric_card('4단계', 'RAG 파이프라인'),
      metric_card('6가지', '안정점수 지표')]],
    colWidths=[W/4]*4,
)
story.append(metrics_row)
story.append(Spacer(1, 12))

# 역량 테이블
story.append(Paragraph('이 프로젝트로 쌓은 역량', H2))
skills = [
    ['데이터 설계',   'DB 스키마 설계, upsert 패턴, 날짜 기반 데이터 집계'],
    ['AI 통합',       'Claude API 연동, RAG 파이프라인 설계, 프롬프트 엔지니어링'],
    ['검색 시스템',   '벡터+키워드 하이브리드 검색 구성, 리랭킹 적용'],
    ['운영 안정성',   'retry 로직(지수 백오프), JSONL 로깅, API 비용 추적'],
    ['코드 품질',     '기능별 모듈 분리, 단위 테스트 127개, 순수 함수 우선 설계'],
    ['기획·UX',       '사용자(나 자신)의 관점으로 직접 기획·디자인·반복 개선'],
]
story.append(two_col_table(
    [[Paragraph(a, S('sa', 9, WHITE, True, TA_CENTER)),
      Paragraph(b, S('sb', 9, NAVY))] for a, b in skills],
    w1=0.20,
    style_extra=[
        ('BACKGROUND', (0,0), (0,-1), BLUE),
        ('BACKGROUND', (1,0), (1,-1), LGRAY),
        ('TEXTCOLOR',  (0,0), (0,-1), WHITE),
    ],
))
story.append(Spacer(1, 14))

# 마무리 인용 박스
closing = Table([[
    Paragraph(
        '"단순히 앱을 쓰는 것을 넘어, 내 데이터를 직접 설계하고 AI가 분석하는 '
        '구조 전체를 경험했습니다.<br/>'
        '기획 &rarr; 데이터 모델링 &rarr; AI 파이프라인 &rarr; 운영까지, '
        '하나의 제품을 처음부터 끝까지 만들었습니다."',
        S('cl', 11, NAVY, align=TA_CENTER, leading=19),
    )
]], colWidths=[W])
closing.setStyle(TableStyle([
    ('BACKGROUND',    (0,0), (-1,-1), LGRAY),
    ('TOPPADDING',    (0,0), (-1,-1), 18),
    ('BOTTOMPADDING', (0,0), (-1,-1), 18),
    ('LEFTPADDING',   (0,0), (-1,-1), 24),
    ('RIGHTPADDING',  (0,0), (-1,-1), 24),
    ('BOX',           (0,0), (-1,-1), 2, NAVY),
]))
story.append(closing)

# ── Build ─────────────────────────────────────────────────────
doc.build(story)
print(f"완료: {OUT}")
