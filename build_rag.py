import os
from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from utils import get_db_connection

load_dotenv()

FAISS_INDEX_DIR = "faiss_index"

print("📦 DB에서 문서 로딩 중...")
conn = get_db_connection()
with conn.cursor() as cursor:
    cursor.execute("""
        SELECT filename, category, refined_text, original_korean
        FROM rag_documents
        WHERE refined_text IS NOT NULL
        AND refined_text != ''
    """)
    rows = cursor.fetchall()
conn.close()

print(f"총 {len(rows)}개 행 로드 완료")

MIN_CONTENT_LEN = 30
SKIP_STRINGS = {"내용없음", "내용 없음", "no content", "n/a"}

def is_valid_content(text: str) -> bool:
    if not text or len(text.strip()) < MIN_CONTENT_LEN:
        return False
    return text.strip().lower() not in SKIP_STRINGS

documents = []
skipped = 0
for row in rows:
    # refined_text: Claude가 핵심만 추출한 한국어 정제본 → 주 Document
    if is_valid_content(row["refined_text"]):
        documents.append(Document(
            page_content=row["refined_text"],
            metadata={"source": row["filename"], "category": row["category"], "doc_type": "refined"}
        ))
    else:
        skipped += 1

    # original_korean: 원문 전체 한국어 번역본 → 보조 Document (translate_rag.py 결과)
    if is_valid_content(row.get("original_korean", "")):
        documents.append(Document(
            page_content=row["original_korean"],
            metadata={"source": row["filename"], "category": row["category"], "doc_type": "translated"}
        ))

if skipped:
    print(f"  ⚠️ {skipped}개 빈/짧은 문서 제외됨")

print("\n🔢 임베딩 생성 중...")
embeddings = HuggingFaceEmbeddings(
    model_name="jhgan/ko-sroberta-multitask",
    model_kwargs={"device": "cpu"}
)

print("\n💾 FAISS 벡터 저장 중...")
vectorstore = FAISS.from_documents(documents, embeddings)
vectorstore.save_local(FAISS_INDEX_DIR)

print(f"\n🎉 완료! {len(documents)}개 Document 벡터화됐어! (refined + translated 포함)")