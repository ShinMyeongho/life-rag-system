# ────────────────────────────────────────────────────────────────
# Dockerfile  –  나의 일기장
#
# 빌드:  docker build -t diary-app .
# 실행:  docker compose up  (docker-compose.yml 참조)
#
# [레이어 캐시 전략]
#   1. 시스템 패키지        (거의 안 바뀜 → 최하단)
#   2. PyTorch CPU 빌드    (크고 느림 → 요건 변경 전까지 캐시 유지)
#   3. Python 의존성       (requirements.txt 변경 시만 재빌드)
#   4. 앱 소스 코드         (자주 바뀜 → 최상단)
# ────────────────────────────────────────────────────────────────

FROM python:3.11-slim

# 메타데이터
LABEL maintainer="personal-diary-app"
LABEL description="Streamlit + MySQL + Hybrid RAG personal diary"

# ── 1. 시스템 의존성 ──────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
        # C 확장 빌드 (faiss-cpu, numpy 등)
        gcc \
        g++ \
        # MySQL 클라이언트 헤더 (PyMySQL은 pure-python이라 불필요하지만
        # mysqlclient fallback 시 필요할 수 있음)
        default-libmysqlclient-dev \
        # 네트워크 유틸 (healthcheck, 디버깅)
        curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# ── 2. 작업 디렉토리 ──────────────────────────────────────────
WORKDIR /app

# ── 3. PyTorch CPU 빌드 (별도 레이어) ────────────────────────
# GPU 드라이버 없는 서버/컨테이너 환경에서 이미지 크기를 줄이기 위해
# PyTorch 공식 CPU 전용 wheel을 먼저 설치.
# requirements.txt에서는 torch를 제외했음.
#
# [선택 근거]
#   - GPU 빌드: ~8 GB  /  CPU 빌드: ~1.5 GB
#   - 이 앱은 sentence-transformers 추론만 수행 → CPU로 충분
RUN pip install --no-cache-dir \
    torch==2.11.0 \
    --index-url https://download.pytorch.org/whl/cpu

# ── 4. Python 의존성 ──────────────────────────────────────────
# requirements.txt만 먼저 COPY → 소스 변경 시 이 레이어는 캐시 유지
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── 5. 앱 소스 코드 COPY ──────────────────────────────────────
# .dockerignore로 민감 파일(user_config.py, .env, data/, faiss_index/ 등) 제외
COPY . .

# ── 6. 런타임 디렉토리 생성 ───────────────────────────────────
# 볼륨 마운트 전 디렉토리 존재 보장
RUN mkdir -p \
        data/goals \
        data/pending \
        data/retrospects \
        faiss_index \
        logs \
        rag_docs

# ── 7. Streamlit 설정 ─────────────────────────────────────────
# 브라우저 자동 열기 끄기, CORS 허용, 통계 수집 비활성화
RUN mkdir -p /root/.streamlit && cat > /root/.streamlit/config.toml <<'EOF'
[server]
headless = true
address = "0.0.0.0"
port = 8501
enableCORS = false
enableXsrfProtection = false

[browser]
gatherUsageStats = false

[theme]
base = "dark"
EOF

# ── 8. 포트 노출 ──────────────────────────────────────────────
EXPOSE 8501

# ── 9. 헬스체크 ───────────────────────────────────────────────
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

# ── 10. 진입점 ────────────────────────────────────────────────
CMD ["streamlit", "run", "app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0"]
