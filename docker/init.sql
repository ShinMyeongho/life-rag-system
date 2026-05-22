-- ────────────────────────────────────────────────────────────────
-- docker/init.sql
-- MySQL 8.0 초기 스키마
-- Docker 컨테이너 최초 기동 시 자동 실행됨
-- (docker-entrypoint-initdb.d 마운트)
-- ────────────────────────────────────────────────────────────────

CREATE DATABASE IF NOT EXISTS diary_db
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE diary_db;

-- ── 일기 ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS diary (
    date               DATE         NOT NULL PRIMARY KEY,
    mood               TINYINT      NOT NULL DEFAULT 5,
    stress             TINYINT      NOT NULL DEFAULT 5,
    sleep_start        TIME,
    sleep_end          TIME,
    sleep_hours        FLOAT,
    med_morning        VARCHAR(20),
    med_morning_reason TEXT,
    med_night          VARCHAR(20),
    med_night_reason   TEXT,
    med_prn            VARCHAR(20),
    med_prn_reason     TEXT,
    meal_morning       TINYINT(1)   DEFAULT 0,
    meal_morning_menu  TEXT,
    meal_lunch         TINYINT(1)   DEFAULT 0,
    meal_lunch_menu    TEXT,
    meal_dinner        TINYINT(1)   DEFAULT 0,
    meal_dinner_menu   TEXT,
    exercise           VARCHAR(20),
    exercise_detail    TEXT,
    exercise_reason    TEXT,
    drinking           VARCHAR(20),
    drinking_with      TEXT,
    drinking_amount    TEXT,
    weekly_checks      TEXT,        -- JSON string
    good_thing         TEXT,
    diary_text         TEXT,
    updated_at         DATETIME     DEFAULT CURRENT_TIMESTAMP
                                    ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ── 목표 ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS monthly_goals (
    ym         VARCHAR(7)  NOT NULL PRIMARY KEY,  -- 'YYYY-MM'
    goals      TEXT,                               -- JSON array
    updated_at DATETIME    DEFAULT CURRENT_TIMESTAMP
                           ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS weekly_goals (
    yw         VARCHAR(7)  NOT NULL PRIMARY KEY,  -- 'YYYY-WW'
    goals      TEXT,                               -- JSON array
    updated_at DATETIME    DEFAULT CURRENT_TIMESTAMP
                           ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ── 재정 ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS loans (
    id             INT          NOT NULL AUTO_INCREMENT PRIMARY KEY,
    name           VARCHAR(100) NOT NULL UNIQUE,
    original       BIGINT       NOT NULL DEFAULT 0,
    current_amount BIGINT       NOT NULL DEFAULT 0,
    monthly        BIGINT       NOT NULL DEFAULT 0,
    start_month    VARCHAR(7),                      -- 'YYYY-MM'
    updated_at     DATETIME     DEFAULT CURRENT_TIMESTAMP
                                ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS fixed_expenses (
    id         INT          NOT NULL AUTO_INCREMENT PRIMARY KEY,
    name       VARCHAR(100) NOT NULL UNIQUE,
    amount     BIGINT       NOT NULL DEFAULT 0,
    updated_at DATETIME     DEFAULT CURRENT_TIMESTAMP
                            ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS income (
    id         INT      NOT NULL AUTO_INCREMENT PRIMARY KEY,
    monthly    BIGINT   NOT NULL DEFAULT 0,
    memo       TEXT,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                        ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS ledger (
    id         INT          NOT NULL AUTO_INCREMENT PRIMARY KEY,
    date       DATE         NOT NULL,
    type       VARCHAR(20)  NOT NULL,   -- '수입' | '지출'
    amount     BIGINT       NOT NULL DEFAULT 0,
    category   VARCHAR(100),
    memo       TEXT,
    created_at DATETIME     DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX idx_ledger_date ON ledger (date);


-- ── CBT ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS cbt_sessions (
    id           INT          NOT NULL AUTO_INCREMENT PRIMARY KEY,
    date         DATE,
    title        VARCHAR(200) DEFAULT '새 대화',
    emotion_tags TEXT,        -- JSON array
    summary      TEXT,
    created_at   DATETIME     DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS cbt_messages (
    id         INT         NOT NULL AUTO_INCREMENT PRIMARY KEY,
    session_id INT         NOT NULL,
    role       VARCHAR(20) NOT NULL,   -- 'user' | 'assistant'
    content    TEXT,
    created_at DATETIME    DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES cbt_sessions(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX idx_cbt_messages_session ON cbt_messages (session_id);


-- ── RAG 문서 ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS rag_documents (
    id               INT           NOT NULL AUTO_INCREMENT PRIMARY KEY,
    filename         VARCHAR(500),
    category         VARCHAR(100),
    refined_text     LONGTEXT,     -- Claude가 정제한 한국어 요약
    original_korean  LONGTEXT,     -- 원문 한국어 번역 (translate_rag.py 결과)
    created_at       DATETIME      DEFAULT CURRENT_TIMESTAMP,
    updated_at       DATETIME      DEFAULT CURRENT_TIMESTAMP
                                   ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_filename (filename(255))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
