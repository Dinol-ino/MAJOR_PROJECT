from typing import Any, Dict, List

import chromadb
from rank_bm25 import BM25Okapi

from app.ingestion.chunker import SectionAwareChunker
from app.retrieval.embeddings import build_embedding_function
from app.retrieval.hybrid_rank import fuse_bm25_dense


class Tier2UserRetrieval:
    def __init__(self, persist_dir: str, embedding_function: Any | None = None):
        self.persist_dir = persist_dir
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.emb_fn = embedding_function or build_embedding_function()
        self.collection = self.client.get_or_create_collection(
            name="tier2_user",
            embedding_function=self.emb_fn,
        )

    def add_documents(self, session_id: str, filename: str, text: str) -> int:
        chunker = SectionAwareChunker(default_act_name=filename)
        chunks = chunker.chunk_document(text)

        if not chunks:
            return 0

        documents = [chunk["text"] for chunk in chunks]
        metadatas = [
            {"act": chunk["act"], "section": str(chunk["section"]), "session_id": session_id}
            for chunk in chunks
        ]
        ids = [f"{session_id}_{filename}_{index}" for index in range(len(chunks))]

        self.collection.add(documents=documents, metadatas=metadatas, ids=ids)
        return len(chunks)

    def query(self, session_id: str, text: str, top_k: int = 3) -> List[Dict[str, Any]]:
        count = self.collection.count()
        if count == 0:
            return []

        dense_results = self.collection.query(
            query_texts=[text],
            where={"session_id": session_id},
            n_results=min(top_k * 2, count),
        )

        dense_docs = []
        if dense_results and dense_results["documents"] and dense_results["documents"][0]:
            docs = dense_results["documents"][0]
            metas = dense_results["metadatas"][0]
            distances = dense_results["distances"][0] if "distances" in dense_results and dense_results["distances"] else [0.0] * len(docs)
            for i in range(len(docs)):
                dense_docs.append(
                    {
                        "act": metas[i]["act"],
                        "section": metas[i]["section"],
                        "text": docs[i],
                        "score": 1.0 - distances[i],
                    }
                )

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
                bm25_docs.append(
                    {
                        "act": metas[i]["act"],
                        "section": metas[i]["section"],
                        "text": documents[i],
                        "score": score,
                    }
                )
        bm25_docs = sorted(bm25_docs, key=lambda item: item["score"], reverse=True)

        return fuse_bm25_dense(bm25_docs, dense_docs, top_k=top_k)
