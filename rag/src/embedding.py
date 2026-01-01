import os
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from rag.src.chunking import split_docs
from tqdm import tqdm

model_dir = r"C:\Users\Administrator\Desktop\financial agent\rag\AI-ModelScope\m3e-base"

embeddings = HuggingFaceEmbeddings(model_name=model_dir)

persist_directory = "rag/src/data_base/vector_db/chroma"
os.makedirs(persist_directory, exist_ok=True)

vectordb = Chroma(
    embedding_function=embeddings,
    persist_directory=persist_directory
)

CHUNKS = split_docs[:20000]
BATCH_SIZE = 50

for i in tqdm(range(0, len(CHUNKS), BATCH_SIZE), desc="向量化并存入 Chroma"):
    batch = CHUNKS[i:i + BATCH_SIZE]
    vectordb.add_documents(batch)

