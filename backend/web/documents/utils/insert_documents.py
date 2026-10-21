
import os

import lancedb
from langchain_community.document_loaders import TextLoader
from langchain_community.vectorstores import LanceDB
from langchain_text_splitters import TextSplitter, RecursiveCharacterTextSplitter

from web.documents.utils.custom_embeddings import CustomEmbeddings


def insert_documents():
    source_path = os.getenv('KNOWLEDGE_SOURCE_PATH', './web/documents/data.txt')
    table_name = os.getenv('KNOWLEDGE_TABLE_NAME', 'my_knowledge_base')
    loader = TextLoader(source_path, encoding='utf-8')
    documents = loader.load()
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=500,chunk_overlap=50)
    texts = text_splitter.split_documents(documents)
    print(f'已切分成{len(texts)}个片段')

    embeddings = CustomEmbeddings()
    db = lancedb.connect('./web/documents/lancedb_storage')
    vector_db = LanceDB.from_documents(
        documents=texts,
        embedding=embeddings,
        connection=db,
        table_name=table_name,
        mode = 'overwrite'
    )

    print(f'已插入{vector_db._table.count_rows()}行数据')
