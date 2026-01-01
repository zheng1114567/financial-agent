import os.path

from tqdm import tqdm
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from rag.data.data import saved_files

def get_text(file_lst):
    docs = []
    for one_doc in tqdm(file_lst, desc="Loading documents"):
        _, ext = os.path.splitext(one_doc)
        if ext.lower() == ".txt":
            try:
                loader = TextLoader(one_doc)
                docs.extend(loader.load())
            except Exception as e:
                print(f"加载失败 {one_doc}: {e}")
        else:
            print(f"跳过非TXT文件: {one_doc}")
    return docs

file_lst = saved_files
documents = get_text(file_lst)

text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=350,
    chunk_overlap=150
)
split_docs = text_splitter.split_documents(documents)
for doc in split_docs:
    filename = os.path.basename(doc.metadata["source"])
    doc.page_content = f"[来源: {filename}] {doc.page_content}"


