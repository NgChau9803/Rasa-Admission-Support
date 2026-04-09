# -*- coding: utf-8 -*-
from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet
from langchain_core.prompts import PromptTemplate

# Import our refactored services
from actions.llm_service import llm_service
from actions.knowledge_service import kb_service

# ---------------------------------------------------------------------------
# Action: Chitchat / Greetings
# Handles normal conversational messages: greetings, farewells, small talk.
# ---------------------------------------------------------------------------
class ActionChitchat(Action):
    def name(self) -> Text:
        return "action_chitchat"

    def __init__(self):
        super().__init__()
        self.prompt = PromptTemplate(
            template="""{status_instruction}
Bạn là một trợ lý ảo thân thiện, nhiệt tình của Trường Công nghệ Thông tin và Truyền thông (SOICT) - Đại học Bách Khoa Hà Nội.
Nhiệm vụ của bạn là hỗ trợ sinh viên, phụ huynh về thông tin tuyển sinh và các chương trình đào tạo của SOICT.
Hãy trả lời tin nhắn sau một cách tự nhiên, thân thiện và hoàn toàn bằng tiếng Việt.

Tin nhắn của người dùng: {message}
""",
            input_variables=["message", "status_instruction"],
        )

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            _domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        user_message = tracker.latest_message.get("text", "")
        
        # Determine if we should greet based on session state
        is_greeted = tracker.get_slot("greeted")
        status_instruction = (
            "Cuộc hội thoại đang tiếp diễn. Hãy đi thẳng vào câu trả lời, ĐỪNG giới thiệu lại bản thân."
            if is_greeted else 
            "Đây là tin nhắn đầu tiên, hãy chào hỏi thân thiện và giới thiệu bạn là trợ lý của SOICT."
        )

        try:
            formatted_prompt = self.prompt.format(
                message=user_message, 
                status_instruction=status_instruction
            )
            response = llm_service.invoke(formatted_prompt, temperature=0.7, max_tokens=1000)
            dispatcher.utter_message(text=response.content)
        except Exception as e:
            dispatcher.utter_message(text="Xin chào! Tôi có thể giúp gì cho bạn?")
            print(f"[ERROR] Chitchat action failed: {e}")
            
        return [SlotSet("greeted", True)]


# ---------------------------------------------------------------------------
# Action: Search Knowledge Base (RAG)
# Retrieves relevant chunks from Pinecone and synthesizes an answer using Gemini.
# ---------------------------------------------------------------------------
class ActionSearchKnowledgeBase(Action):
    def name(self) -> Text:
        return "action_search_knowledge_base"

    def __init__(self):
        super().__init__()
        
        # RAG Prompt: strict Vietnamese, grounded in context
        self.prompt = PromptTemplate(
            template="""{status_instruction}
Bạn là một trợ lý ảo thân thiện và chuyên nghiệp của Trường CNTT&TT (SOICT) - Đại học Bách Khoa Hà Nội.
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
            input_variables=["context", "question", "status_instruction"],
        )

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            _domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        if not kb_service.is_ready:
            dispatcher.utter_message(
                text="Xin lỗi, hệ thống chưa được kết nối API (thiếu GOOGLE_API_KEY hoặc PINECONE_API_KEY)."
            )
            return []

        user_query = tracker.latest_message.get("text", "")
        if not user_query:
            dispatcher.utter_message(text="Xin lỗi, tôi không nhận được câu hỏi từ bạn.")
            return []

        # Determine if we should greet based on session state
        is_greeted = tracker.get_slot("greeted")
        status_instruction = (
            "Cuộc hội thoại đang tiếp diễn. Hãy đi thẳng vào câu trả lời, ĐỪNG giới thiệu lại bản thân."
            if is_greeted else 
            "Đây là tin nhắn đầu tiên, hãy chào hỏi thân thiện và giới thiệu bạn là trợ lý của SOICT."
        )

        try:
            # 1. Retrieve top-6 most relevant chunks from Pinecone via service
            chunks = kb_service.search(user_query, top_k=6)

            if not chunks:
                dispatcher.utter_message(
                    text="Xin lỗi, tôi không tìm thấy thông tin liên quan trong tài liệu của SOICT. "
                         "Bạn vui lòng liên hệ Ban Đào tạo qua email soict@hust.edu.vn để được hỗ trợ."
                )
                return []

            # 2. Merge chunks into a context block
            context_text = "\n\n".join(chunks)

            # ... (DEBUG logging omitted for brevity in search block)

            # 3. Ask Gemini to synthesize the final answer
            formatted_prompt = self.prompt.format(
                context=context_text, 
                question=user_query,
                status_instruction=status_instruction
            )
            
            # --- DEBUG LOGGING ---
            print("[DEBUG] PROMPT SENT TO GEMINI:\n")
            print(formatted_prompt)
            print("\n" + "="*50)

            response = llm_service.invoke(formatted_prompt, temperature=0.2, max_tokens=4096)
            dispatcher.utter_message(text=response.content)

        except Exception as e:
            dispatcher.utter_message(
                text="Đã có lỗi xảy ra khi tìm kiếm thông tin. Vui lòng thử lại sau hoặc liên hệ soict@hust.edu.vn."
            )
            print(f"[ERROR] RAG Pipeline failed: {e}")

        return [SlotSet("greeted", True)]
