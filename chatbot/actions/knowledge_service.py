# -*- coding: utf-8 -*-
import os
from typing import List, Optional
from dotenv import load_dotenv

from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from pinecone import Pinecone

class KnowledgeBaseService:
    """Service to handle interactions with the Vector Database (Pinecone) and Embeddings."""

    def __init__(self, index_name: str = "soict-admission-rag", embedding_model: str = "models/gemini-embedding-001"):
        load_dotenv(override=True)
        self.index_name = index_name
        self.embedding_model = embedding_model
        
        self.is_ready = self._check_dependencies()
        if self.is_ready:
            self.embeddings = GoogleGenerativeAIEmbeddings(model=self.embedding_model)
            self.pc = Pinecone()
            self.vector_store = PineconeVectorStore(
                index_name=self.index_name,
                embedding=self.embeddings,
            )

    def _check_dependencies(self) -> bool:
        """Check if all required API keys are present."""
        has_google = False
        for k, v in os.environ.items():
            if k.startswith("GOOGLE_API_KEY") and v.strip():
                has_google = True
                if not os.getenv("GOOGLE_API_KEY"):
                    os.environ["GOOGLE_API_KEY"] = v.strip()
                if not os.getenv("GEMINI_API_KEY"):
                    os.environ["GEMINI_API_KEY"] = v.strip()
                break
        return bool(has_google and os.getenv("PINECONE_API_KEY"))

    def search(self, query: str, top_k: int = 6) -> Optional[List[str]]:
        """
        Search the knowledge base for relevant chunks.
        
        Args:
            query: The user's search query.
            top_k: Number of relevant chunks to retrieve.
            
        Returns:
            A list of string contents if found, otherwise None.
        """
        if not self.is_ready:
            return None
            
        docs = self.vector_store.similarity_search(query, k=top_k)
        
        if not docs:
            return None
            
        # Return a list of text contents instead of LangChain Document objects
        return [doc.page_content for doc in docs]

# Create a singleton instance
kb_service = KnowledgeBaseService()
