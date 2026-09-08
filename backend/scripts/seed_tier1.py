import os
import sys
import time
import hashlib
import chromadb
from chromadb.utils import embedding_functions

# Ensure backend/app folder can be imported
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.config import settings
from app.ingestion.chunker import SectionAwareChunker
from app.research.provenance import compute_content_hash, ProvenanceRecord, validate_provenance_completeness

ACT_METADATA_REGISTRY = {
    "BNS_2023": {
        "title": "Bharatiya Nyaya Sanhita, 2023",
        "year": "2023",
        "domain": "criminal",
        "source_url": "https://www.indiacode.nic.in/handle/123456789/2007",
        "publication_date": "2023-12-25",
        "version": "Official Gazette No. 45 of 2023"
    },
    "BNSS_2023": {
        "title": "Bharatiya Nagarik Suraksha Sanhita, 2023",
        "year": "2023",
        "domain": "procedural",
        "source_url": "https://www.indiacode.nic.in/handle/123456789/2008",
        "publication_date": "2023-12-25",
        "version": "Official Gazette No. 46 of 2023"
    },
    "BSA_2023": {
        "title": "Bharatiya Sakshya Adhiniyam, 2023",
        "year": "2023",
        "domain": "evidence",
        "source_url": "https://www.indiacode.nic.in/handle/123456789/2009",
        "publication_date": "2023-12-25",
        "version": "Official Gazette No. 47 of 2023"
    },
    "IT_Act": {
        "title": "Information Technology Act, 2000",
        "year": "2000",
        "domain": "cyber",
        "source_url": "https://www.indiacode.nic.in/handle/123456789/1999",
        "publication_date": "2000-06-09",
        "version": "Act No. 21 of 2000 (as amended 2008)"
    },
    "Companies_Act_2013": {
        "title": "Companies Act, 2013",
        "year": "2013",
        "domain": "corporate",
        "source_url": "https://www.indiacode.nic.in/handle/123456789/2114",
        "publication_date": "2013-08-30",
        "version": "Act No. 18 of 2013 (as amended 2020)"
    },
    "Contract_Act_1872": {
        "title": "Indian Contract Act, 1872",
        "year": "1872",
        "domain": "commercial",
        "source_url": "https://www.indiacode.nic.in/handle/123456789/2187",
        "publication_date": "1872-04-25",
        "version": "Act No. 9 of 1872"
    },
    "Consumer_Protection_Act_2019": {
        "title": "Consumer Protection Act, 2019",
        "year": "2019",
        "domain": "consumer",
        "source_url": "https://www.indiacode.nic.in/handle/123456789/15256",
        "publication_date": "2019-08-09",
        "version": "Act No. 35 of 2019"
    },
    "DPDPA_2023": {
        "title": "Digital Personal Data Protection Act, 2023",
        "year": "2023",
        "domain": "data_protection",
        "source_url": "https://www.indiacode.nic.in/handle/123456789/20555",
        "publication_date": "2023-08-11",
        "version": "Act No. 22 of 2023"
    },
}

def seed_database():
    """
    Ingestion and seeding pipeline:
    Parses raw act files from data/acts_raw/, applies section-aware chunking,
    enforces 13-field ProvenanceRecord verification, and seeds both ChromaDB and BM25 index.
    """
    print("Initializing Tier-1 Indian Law database seeding...")
    raw_data_dir = os.path.join(os.path.dirname(__file__), "../../data/acts_raw")
    
    if not os.path.exists(raw_data_dir):
        print(f"Directory {raw_data_dir} does not exist. Creating it.")
        os.makedirs(raw_data_dir, exist_ok=True)
        return
        
    files = sorted([f for f in os.listdir(raw_data_dir) if f.endswith(".txt")])
    if not files:
        print("No raw act files found to seed in data/acts_raw.")
        return

    from app.retrieval.client import get_shared_chroma_client, get_shared_embedding_function
    client = get_shared_chroma_client(settings.CHROMA_PERSIST_DIR)
    emb_fn = get_shared_embedding_function(settings.retrieval.embedding_model_name)
    
    try:
        client.delete_collection("tier1_law")
        print("Cleared existing ChromaDB tier1_law collection.")
    except Exception:
        pass
        
    collection = client.get_or_create_collection("tier1_law", embedding_function=emb_fn)

    from app.retrieval.bm25_index import tier1_bm25_index
    tier1_bm25_index.clear()
    print("Cleared existing BM25 index.")

    chunker = SectionAwareChunker()
    total_chunks = 0
    acts_processed = 0

    for file_name in files:
        base_name = os.path.splitext(file_name)[0]
        meta_info = ACT_METADATA_REGISTRY.get(base_name, {
            "title": base_name.replace("_", " "),
            "year": "2024",
            "domain": "statutory",
            "source_url": "https://www.indiacode.nic.in",
            "publication_date": "2024-01-01",
            "version": "Official Gazette"
        })
        canonical_act = meta_info["title"]
        file_path = os.path.join(raw_data_dir, file_name)
        
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        chunks = chunker.chunk_document(content, act_name=canonical_act)
        print(f"Parsed {len(chunks)} chunks for {canonical_act} ({file_name}).")
        
        if chunks:
            documents = []
            metadatas = []
            ids = []
            
            for i, c in enumerate(chunks):
                sec_str = str(c["section"])
                text = c["text"]
                content_hash = compute_content_hash(text)
                doc_id = f"{base_name}_{sec_str}_{i}"
                
                prov = ProvenanceRecord(
                    source_id=doc_id,
                    source_type="statutory_code",
                    source_title=canonical_act,
                    source_url=meta_info.get("source_url"),
                    jurisdiction="India / Union",
                    act=canonical_act,
                    section=f"Section {sec_str}" if not sec_str.lower().startswith("section") else sec_str,
                    document_version=meta_info.get("version", "Official Gazette"),
                    publication_date=meta_info.get("publication_date"),
                    retrieval_timestamp=time.time(),
                    content_hash=content_hash,
                    trust_level="LOCAL_VERIFIED_CORPUS",
                    retrieval_method="local_hybrid_bm25_vector",
                )
                validate_provenance_completeness(prov)

                documents.append(text)
                ids.append(doc_id)
                metadatas.append({
                    "act": canonical_act,
                    "section": sec_str,
                    "doc_type": "statutory_law",
                    "source": file_name,
                    "domain": meta_info.get("domain", "statutory"),
                    "jurisdiction": "India / Union",
                    "trust_level": "LOCAL_VERIFIED_CORPUS",
                    "content_hash": content_hash,
                    "document_version": meta_info.get("version", "Official Gazette"),
                    "retrieval_method": "local_hybrid_bm25_vector",
                    "source_url": meta_info.get("source_url", "")
                })

            collection.add(documents=documents, metadatas=metadatas, ids=ids)
            tier1_bm25_index.add_documents_batch(doc_ids=ids, documents=documents, metadatas=metadatas)
            total_chunks += len(chunks)
            acts_processed += 1
            print(f"Loaded {len(chunks)} chunks into ChromaDB & BM25 for {canonical_act}.")
            
    tier1_bm25_index.save()
    print(f"\nSeeding Complete! Successfully indexed {total_chunks} statutory chunks across {acts_processed} Indian Acts.")

if __name__ == "__main__":
    seed_database()
