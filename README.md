# 📔 나의 일기장

> 생활 데이터를 기록하면 Claude가 전문 문서(CBT·수면·재정)를 근거로 분석해주는 개인용 웹 애플리케이션입니다.  
> 하이브리드 검색(FAISS + BM25 + Cross-encoder)과 한국어 임베딩을 직접 구성했고, pytest 127개로 검증했습니다.

---

## 만든 이유

수면·감정·재정·목표처럼 내 삶과 직결된 데이터를 한곳에 모아 AI가 분석해주는 도구가 필요했습니다.  
시중 앱은 기능이 분산되고 개인화가 부족해서, 직접 내게 맞는 앱을 설계하고 만들기로 했습니다.

기획부터 배포까지 혼자 진행하면서 데이터 모델링, RAG 검색 파이프라인, 테스트 작성을 직접 다뤘습니다.
실무에서 RAG를 다루기 전에, 검색 계층을 직접 만들어 본 프로젝트입니다.

---

## 만들면서 부딪힌 것들

- **테이블 구조를 여러 번 갈아엎었습니다** → 그 과정에서 upsert 패턴으로 정리했습니다
- **단순 AI 호출로는 근거 없는 답이 나왔습니다** → 문서를 검색해 근거와 함께 답하도록 RAG 검색 계층을 따로 구현했습니다
- **테스트 없이 기능을 늘리다 버그가 쌓였습니다** → pytest 단위 테스트 127개를 작성해 회귀를 막았습니다
- **환경 차이로 실행이 깨졌습니다** → Docker로 환경을 통일하고 `.env`와 `user_config.py`를 분리해 개인정보를 격리했습니다

---

## 어떤 앱인가요?

매일 일기를 쓰면 내 생활 패턴이 데이터로 쌓입니다.  
AI가 그 데이터를 읽고, 전문 자료(CBT·수면·재정)를 바탕으로 맞춤 분석을 해줍니다.  
목표를 세우고, 가계부를 정리하고, 내 흐름을 트렌드로 확인할 수 있습니다.

<details>
<summary><b>기능 한눈에 보기</b> (펼치기)</summary>

### ✏️ 일기 쓰기
매일 기분, 스트레스, 수면 시간, 식사, 운동, 음주, 투약을 기록합니다.  
자유 형식으로 일기도 쓸 수 있고, 이번 주 목표 달성 여부도 함께 체크합니다.

### 📖 일기 보기
날짜별로 일기를 열람하고, 안정점수(0~100)를 확인합니다.  
안정점수는 수면·투약·식사·운동·음주·스트레스를 종합해 자동 계산됩니다.

### 🤖 Claude 분석
선택한 기간의 생활 데이터를 Claude AI가 분석해서 리포트를 만들어줍니다.  
단순한 AI 응답이 아니라, CBT·수면·재정 전문 문서를 참고해서 답해줍니다.

### 🎯 목표 관리
월간·주간 목표를 설정하고 달성률을 추적합니다.  
일기 쓸 때 오늘 목표를 체크하면 홈 화면에서 진행률을 바로 볼 수 있습니다.

### 💰 가계부
대출 현황·상환 진행률, 수입·고정지출·변동지출을 관리합니다.

### 🧠 CBT 챗봇
인지행동치료(CBT) 기반 AI 챗봇입니다.  
감정을 털어놓으면 사고기록지 6단계를 안내해주고, 대화 후 요약을 남겨줍니다.

### 📈 트렌드
기간별 안정점수·기분·수면 추이를 그래프로 확인합니다.

### 💾 백업
내 데이터를 백업하고 복원합니다.

</details>

---

## 기술 스택

| 분류 | 기술 |
|------|------|
| UI | Streamlit |
| 데이터베이스 | MySQL 8.0 |
| AI 분석 | Claude API |
| 검색 엔진 | Hybrid RAG (FAISS + BM25 + Cross-encoder) |
| 한국어 임베딩 | ko-sroberta-multitask |
| 컨테이너 | Docker / docker-compose |
| 테스트 | pytest (127개) |

---

## 실행 방법

### 방법 1: Docker (권장)

```bash
# .env 파일 생성
cp .env.docker.example .env
# user_config.py 생성 (개인 설정)
cp user_config.example.py user_config.py

# 앱 실행
docker compose up -d
```

브라우저에서 `http://localhost:8501` 접속

### 방법 2: 로컬 직접 실행

#### 1. 패키지 설치

```bash
pip install -r requirements.txt
```

#### 2. 환경 변수 설정 (`.env` 파일 생성)

```
ANTHROPIC_API_KEY=your_key
GEMINI_API_KEY=your_key
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=diary_db
```

#### 3. 사용자 프로필 설정

```bash
cp user_config.example.py user_config.py
# user_config.py 내용 수정 (gitignore 등록되어 있어 업로드 안 됨)
```

#### 4. Claude 분석용 RAG 빌드 (처음 한 번만)

```bash
python refine_rag.py      # 문서 정제
python build_rag.py       # 검색 인덱스 생성
```

#### 5. 앱 실행

```bash
streamlit run app.py
```

---
