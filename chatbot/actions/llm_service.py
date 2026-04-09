# -*- coding: utf-8 -*-
import os
import itertools
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

class LLMService:
    """Service class to handle LLM invocation and API key rotation."""
    
    def __init__(self):
        # Ensure latest env is loaded
        load_dotenv(override=True)
        
        self.google_keys = self._get_api_keys()
        self.key_cycle = itertools.cycle(self.google_keys) if self.google_keys else None
        
        # Ensure the primary key is available in the standard environment variables
        if self.google_keys and not os.getenv("GOOGLE_API_KEY"):
            os.environ["GOOGLE_API_KEY"] = self.google_keys[0]
            os.environ["GEMINI_API_KEY"] = self.google_keys[0]

    def _get_api_keys(self) -> list:
        """Extract all GOOGLE_API_KEYs from environment for rotation."""
        keys = [v.strip() for k, v in os.environ.items() if k.startswith("GOOGLE_API_KEY") and v.strip()]
        return keys

    def has_keys(self) -> bool:
        """Check if any API keys are available."""
        return bool(self.google_keys)

    def invoke(self, prompt_text: str, temperature: float = 0.5, max_tokens: int = 4096, model: str = "gemini-3.1-flash-lite-preview"):
        """Invokes Gemini LLM, automatically rotating API keys on Quota/503 errors."""
        if not self.has_keys():
            raise ValueError("No Gemini API keys configured.")
            
        attempts = 0
        max_attempts = len(self.google_keys)
        
        while attempts < max_attempts:
            current_key = next(self.key_cycle)
            
            # Sync to environment to ensure all sub-components see the active key
            os.environ["GOOGLE_API_KEY"] = current_key
            os.environ["GEMINI_API_KEY"] = current_key
            
            llm = ChatGoogleGenerativeAI(
                model=model,
                temperature=temperature,
                max_output_tokens=max_tokens,
                google_api_key=current_key,
                max_retries=0
            )
            
            try:
                return llm.invoke(prompt_text)
            except Exception as e:
                err_str = str(e).lower()
                if any(err in err_str for err in ["429", "503", "exhausted", "quota"]):
                    attempts += 1
                    print(f"[WARNING] API Key hit limit (429/503). Rotating to next key... (Attempt {attempts}/{max_attempts})")
                    if attempts >= max_attempts:
                        raise e
                else:
                    raise e

# Create a singleton instance
llm_service = LLMService()
