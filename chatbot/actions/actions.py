# -*- coding: utf-8 -*-
import os
from typing import Any, Text, Dict, List
from dotenv import load_dotenv

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher

from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from langchain_core.prompts import PromptTemplate
from pinecone import Pinecone

# Load environment variables
load_dotenv()

import itertools

# Langchain/Google SDK expects GOOGLE_API_KEY — map from GEMINI_API_KEY if needed
if os.getenv("GEMINI_API_KEY") and not os.getenv("GOOGLE_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]

# Extract all GEMINI_API_KEYs from environment for rotation
gemini_keys = [v.strip() for k, v in os.environ.items() if k.startswith("GEMINI_API_KEY") and v.strip()]
if not gemini_keys:
    gemini_keys = [os.environ.get("GOOGLE_API_KEY")]

key_cycle = itertools.cycle(gemini_keys)

def invoke_with_rotation(prompt_text: str, temperature: float = 0.5, max_tokens: int = 4096):
    """Invokes Gemini LLM, automatically rotating API keys on Quota/503 errors."""
    attempts = 0
    max_attempts = len(gemini_keys)
    while attempts < max_attempts:
        current_key = next(key_cycle)
        # Sync to environment to ensure all sub-components see the active key
        os.environ["GEMINI_API_KEY"] = current_key
        os.environ["GOOGLE_API_KEY"] = current_key
        
        llm = ChatGoogleGenerativeAI(
            model="gemini-3.1-flash-lite-preview",
            temperature=temperature,
            max_output_tokens=max_tokens,
            google_api_key=current_key,
            max_retries=0
        )
        try:
            return llm.invoke(prompt_text)
        except Exception as e:
            err_str = str(e).lower()
            if "429" in err_str or "503" in err_str or "exhausted" in err_str or "quota" in err_str:
                attempts += 1
                print(f"[WARNING] API Key hit limit (429/503). Rotating to next key... (Attempt {attempts}/{max_attempts})")
                if attempts >= max_attempts:
                    raise e
            else:
                raise e


# ---------------------------------------------------------------------------
# Action: Chitchat / Greetings
# Handles normal conversational messages: greetings, farewells, small talk.
# The LLM stays in character as the SOICT assistant and responds in Vietnamese.
# ---------------------------------------------------------------------------
class ActionChitchat(Action):
    def name(self) -> Text:
        return "action_chitchat"

    def __init__(self):
        super().__init__()
        self.prompt = PromptTemplate(
            template="""Bạn là một trợ lý ảo thân thiện, nhiệt tình của Trường Công nghệ Thông tin và Truyền thông (SOICT) - Đại học Bách Khoa Hà Nội.
Nhiệm vụ của bạn là hỗ trợ sinh viên, phụ huynh về thông tin tuyển sinh và các chương trình đào tạo của SOICT.
Hãy trả lời tin nhắn sau một cách tự nhiên, thân thiện và hoàn toàn bằng tiếng Việt.
Nếu người dùng chào hỏi, hãy chào lại và giới thiệu ngắn gọn bạn có thể giúp gì.
Nếu người dùng nói tạm biệt, hãy chúc họ một ngày tốt lành.

Tin nhắn của người dùng: {message}
""",
            input_variables=["message"],
        )

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        user_message = tracker.latest_message.get("text", "")
        try:
            formatted_prompt = self.prompt.format(message=user_message)
            response = invoke_with_rotation(formatted_prompt, temperature=0.7, max_tokens=1000)
            dispatcher.utter_message(text=response.content)
        except Exception as e:
            dispatcher.utter_message(text="Xin chào! Tôi là trợ lý ảo của SOICT - HUST. Tôi có thể giúp bạn tìm hiểu về các chương trình đào tạo và tuyển sinh. Bạn có câu hỏi gì không?")
            print(f"[ERROR] Chitchat action failed: {e}")
        return []


# ---------------------------------------------------------------------------
# Action: Search Knowledge Base (RAG)
# Retrieves relevant chunks from Pinecone and synthesizes an answer using Gemini.
# ---------------------------------------------------------------------------
class ActionSearchKnowledgeBase(Action):
    def name(self) -> Text:
        return "action_search_knowledge_base"

    def __init__(self):
        super().__init__()
        
        # Load lại dotenv để đảm bảo lấy key mới nhất trong trường hợp thay đổi file .env mà không restart server hoàn toàn
        load_dotenv(override=True)
        
        # Check các biến môi trường
        has_gemini = False
        # Duyệt qua env để tìm GEMINI_API_KEY
        for k, v in os.environ.items():
            if k.startswith("GEMINI_API_KEY") and v.strip():
                has_gemini = True
                # Set luôn GOOGLE_API_KEY nếu chưa có
                if not os.getenv("GOOGLE_API_KEY"):
                    os.environ["GOOGLE_API_KEY"] = v.strip()
                break
        
        # Nếu chưa tìm thấy trong env, kiểm tra lại GOOGLE_API_KEY cũ
        if not has_gemini and os.getenv("GOOGLE_API_KEY"):
            has_gemini = True

        self.is_ready = bool(has_gemini and os.getenv("PINECONE_API_KEY"))
        
        if self.is_ready:
            # Initialize Gemini embeddings (must match model used in build_vectordb.py)
            self.embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")

            # Connect to Pinecone
            self.pc = Pinecone()
            self.index_name = "soict-admission-rag"
            self.vector_store = PineconeVectorStore(
                index_name=self.index_name,
                embedding=self.embeddings,
            )

            # RAG Prompt: strict Vietnamese, grounded in context
            self.prompt = PromptTemplate(
                template="""Bạn là một trợ lý ảo thân thiện và chuyên nghiệp của Trường CNTT&TT (SOICT) - Đại học Bách Khoa Hà Nội.
Hãy sử dụng ngữ cảnh (Context) được cung cấp dưới đây để trả lời câu hỏi của người dùng một cách chính xác, đầy đủ và hữu ích.
Trả lời hoàn toàn bằng tiếng Việt. Không trả lời bằng tiếng Anh.
Nếu ngữ cảnh không chứa đủ thông tin, hãy nói thành thật và gợi ý người dùng liên hệ Ban Đào tạo SOICT qua email: soict@hust.edu.vn.
KHÔNG được tự bịa thêm thông tin ngoài ngữ cảnh.

----------------
NGỮ CẢNH (Context):
{context}

----------------
CÂU HỎI (Question):
{question}

TRẢ LỜI:""",
                input_variables=["context", "question"],
            )

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        if not self.is_ready:
            dispatcher.utter_message(
                text="Xin lỗi, hệ thống chưa được kết nối API (thiếu GOOGLE_API_KEY hoặc PINECONE_API_KEY)."
            )
            return []

        user_query = tracker.latest_message.get("text", "")
        if not user_query:
            dispatcher.utter_message(text="Xin lỗi, tôi không nhận được câu hỏi từ bạn.")
            return []

        try:
            # 1. Retrieve top-6 most relevant chunks from Pinecone
            docs = self.vector_store.similarity_search(user_query, k=6)

            if not docs:
                dispatcher.utter_message(
                    text="Xin lỗi, tôi không tìm thấy thông tin liên quan trong tài liệu của SOICT. "
                         "Bạn vui lòng liên hệ Ban Đào tạo qua email soict@hust.edu.vn để được hỗ trợ."
                )
                return []

            # 2. Merge chunks into a context block
            context_text = "\n\n".join([doc.page_content for doc in docs])

            # --- DEBUG LOGGING ---
            print("\n" + "="*50)
            print(f"[DEBUG] USER QUERY: {user_query}")
            print(f"[DEBUG] RETRIEVED {len(docs)} CHUNKS FROM PINECONE.")
            print("="*50 + "\n")

            # 3. Ask Gemini to synthesize the final answer
            formatted_prompt = self.prompt.format(context=context_text, question=user_query)
            
            # --- DEBUG LOGGING ---
            print("[DEBUG] PROMPT SENT TO GEMINI:\n")
            print(formatted_prompt)
            print("\n" + "="*50)

            response = invoke_with_rotation(formatted_prompt, temperature=0.2, max_tokens=4096)

            # --- DEBUG LOGGING ---
            print("[DEBUG] GEMINI FULL RESPONSE:\n")
            print(response.content)
            print("\n" + "="*50 + "\n")

            dispatcher.utter_message(text=response.content)

        except Exception as e:
            dispatcher.utter_message(
                text="Đã có lỗi xảy ra khi tìm kiếm thông tin. Vui lòng thử lại sau hoặc liên hệ soict@hust.edu.vn."
            )
            print(f"[ERROR] RAG Pipeline failed: {e}")

        return []
