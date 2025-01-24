from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.vectorstores import FAISS
import os
from dotenv import load_dotenv


load_dotenv()
api_key = os.getenv("openai_key")

llm = ChatOpenAI(
    api_key=api_key,
    model='gpt-4',
    temperature=0
)

def diritti_rag(user_input):
        
    loader = PyPDFLoader(r'guida_dipendente.pdf')
    text_doc = loader.load()

    splitter = RecursiveCharacterTextSplitter(
        separators=["\n\n", "\n", ". ", " ", ""],
        chunk_size=1000,
        chunk_overlap=200,
        length_function=len,
        keep_separator=True
    )

    docs = splitter.split_documents(text_doc)

    embeddings = OpenAIEmbeddings(
        api_key=api_key,
        model="text-embedding-3-small"
    )

    vector_db = FAISS.from_documents(
        docs,
        embeddings,
        distance_strategy="MAX_INNER_PRODUCT"
    )
    
    retriever = vector_db.as_retriever(
            search_type='similarity',
            search_kwargs={
                'k': 5,              # Ridotto per maggiore precisione
                'fetch_k': 8,        # Ridotto per efficienza
                'lambda_mult': 0.9   # Bilanciamento tra rilevanza e diversità
                }
        )
    
    relevant_docs = retriever.invoke(user_input)
    
    # Estrai contenuti e metadati separatamente
    contexts = [doc.page_content for doc in relevant_docs]
    sources = [doc.metadata for doc in relevant_docs]
    
    return {
        "contexts": contexts,                    # Lista dei singoli chunk di testo
        "sources": sources,                      # Lista dei metadati per ogni chunk
        "combined_context": "\n\n".join(contexts) # Tutto il testo concatenato
    }
    