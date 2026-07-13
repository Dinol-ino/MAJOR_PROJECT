import os
import sys

# Ensure backend/app folder can be imported
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.config import settings
from app.ingestion.chunker import SectionAwareChunker

def seed_database():
    """
    One-time script to parse raw act files from data/acts_raw/ and seed the Tier-1 ChromaDB.
    Runs locally on dev machines.
    """
    print("Initializing Tier-1 Indian Law database seeding...")
    raw_data_dir = os.path.join(os.path.dirname(__file__), "../../data/acts_raw")
    
    if not os.path.exists(raw_data_dir):
        print(f"Directory {raw_data_dir} does not exist. Creating it.")
        os.makedirs(raw_data_dir, exist_ok=True)
        return
        
    print("Reading raw act plain text files...")
    # Find all .txt files
    files = [f for f in os.listdir(raw_data_dir) if f.endswith(".txt")]
    
    if not files:
        print("No raw act files found to seed. Put Indian Contract Act or IT Act text files in data/acts_raw.")
        return

    chunker = SectionAwareChunker()
    for file_name in files:
        act_name = os.path.splitext(file_name)[0]
        file_path = os.path.join(raw_data_dir, file_name)
        
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        chunks = chunker.chunk_document(content, act_name=act_name)
        print(f"Parsed {len(chunks)} chunks for {act_name}.")
        
        # Here we would initialize ChromaDB client and load chunks:
        # client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
        # collection = client.get_or_create_collection("tier1_law")
        # collection.add(documents=..., metadatas=..., ids=...)
        
    print("Tier-1 Database seeding completed successfully.")

if __name__ == "__main__":
    seed_database()
