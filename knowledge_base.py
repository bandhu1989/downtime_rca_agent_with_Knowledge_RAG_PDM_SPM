"""Local RAG knowledge base for the Downtime Investigator PoC."""
from pathlib import Path
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

ROOT = Path(__file__).resolve().parent
DOCS = ROOT / "knowledge_base"
VECTOR_DIR = ROOT / "data" / "maintenance_chroma"
COLLECTION = "maintenance_sop_manuals"

def build_or_refresh_index():
    documents = []
    for path in sorted(DOCS.glob("*.md")):
        documents.append(Document(
            page_content=path.read_text(encoding="utf-8"),
            metadata={
                "source": path.name,
                "status": "SIMULATED_NOT_APPROVED",
                "revision": "0.1"
            }
        ))
    if not documents:
        raise FileNotFoundError(f"No Markdown documents in {DOCS}")
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=850, chunk_overlap=140,
        separators=["\n## ", "\n### ", "\n\n", "\n", " ", ""]
    )
    chunks = splitter.split_documents(documents)
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    store = Chroma(
        collection_name=COLLECTION,
        embedding_function=embeddings,
        persist_directory=str(VECTOR_DIR)
    )
    store.reset_collection()
    store.add_documents(chunks)
    return {"documents": len(documents), "chunks": len(chunks)}

def search_maintenance_knowledge(query: str, k: int = 4):
    if not VECTOR_DIR.exists():
        raise RuntimeError("Index not found. Run python build_knowledge_index.py")
    store = Chroma(
        collection_name=COLLECTION,
        embedding_function=OpenAIEmbeddings(model="text-embedding-3-small"),
        persist_directory=str(VECTOR_DIR)
    )
    hits = store.similarity_search(query, k=k)
    return [{
        "content": d.page_content,
        "source": d.metadata.get("source", "unknown"),
        "status": d.metadata.get("status", "unknown"),
        "revision": d.metadata.get("revision", "unknown")
    } for d in hits]
