import os
from typing import List, Dict, Any
import chromadb
from chromadb.utils import embedding_functions
from rank_bm25 import BM25Okapi
from app.retrieval.hybrid_rank import fuse_bm25_dense
from app.ingestion.chunker import SectionAwareChunker

class Tier2UserRetrieval:
    def __init__(self, persist_dir: str):
        self.persist_dir = persist_dir
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.emb_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="BAAI/bge-small-en"
        )
        self.collection = self.client.get_or_create_collection(
            name="tier2_user", 
            embedding_function=self.emb_fn
        )

    def add_documents(self, session_id: str, filename: str, text: str) -> int:
        """
        Chunks the extracted PDF text and adds it to the ChromaDB Tier-2 collection,
        associating it with the given session_id.
        """
        chunker = SectionAwareChunker(default_act_name=filename)
        chunks = chunker.chunk_document(text)
        
        if not chunks:
            return 0
            
        documents = [c["text"] for c in chunks]
        metadatas = [
            {"act": c["act"], "section": str(c["section"]), "session_id": session_id}
            for c in chunks
        ]
        # Generate unique ids for each chunk
        ids = [f"{session_id}_{filename}_{i}" for i in range(len(chunks))]
        
        self.collection.add(documents=documents, metadatas=metadatas, ids=ids)
        return len(chunks)

    def query(self, session_id: str, text: str, top_k: int = 3) -> List[Dict[str, Any]]:
        # Count documents to check if collection has any documents
        count = self.collection.count()
        if count == 0:
            return []

        # 1. Dense query filtering by session_id
        dense_results = self.collection.query(
            query_texts=[text],
            where={"session_id": session_id},
            n_results=min(top_k * 2, count)
        )
        
        dense_docs = []
        if dense_results and dense_results["documents"] and dense_results["documents"][0]:
            docs = dense_results["documents"][0]
            metas = dense_results["metadatas"][0]
            distances = dense_results["distances"][0] if "distances" in dense_results and dense_results["distances"] else [0.0] * len(docs)
            for i in range(len(docs)):
                dense_docs.append({
                    "act": metas[i]["act"],
                    "section": metas[i]["section"],
                    "text": docs[i],
                    "score": 1.0 - distances[i]
                })

        # 2. Sparse (BM25) query filtering by session_id
        all_data = self.collection.get(where={"session_id": session_id})
        if not all_data or not all_data["documents"]:
            return dense_docs[:top_k]

        documents = all_data["documents"]
        metas = all_data["metadatas"]

        tokenized_corpus = [doc.lower().split() for doc in documents]
        bm25 = BM25Okapi(tokenized_corpus)
        tokenized_query = text.lower().split()
        scores = bm25.get_scores(tokenized_query)

        bm25_docs = []
        for i, score in enumerate(scores):
            if score > 0:
                bm25_docs.append({
                    "act": metas[i]["act"],
                    "section": metas[i]["section"],
                    "text": documents[i],
                    "score": score
                })
        bm25_docs = sorted(bm25_docs, key=lambda x: x["score"], reverse=True)

        # 3. Fuse rankings
        return fuse_bm25_dense(bm25_docs, dense_docs, top_k=top_k)

