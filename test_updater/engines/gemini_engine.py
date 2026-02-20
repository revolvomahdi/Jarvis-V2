from google import genai
from google.genai import types
from .base import BaseEngine
import time

class GeminiEngine(BaseEngine):
    def __init__(self, api_key, model_mode="flash"):
        self.api_key = api_key
        
        # --- MODEL CONFIGURATION ---
        self.primary_model_name = "gemini-3-flash-preview"
        self.fallback_model_name = "gemini-2.5-flash-lite"
        
        self.current_active_model = self.primary_model_name

        if api_key:
            self.client = genai.Client(api_key=api_key)

    def get_model_name(self):
        return self.current_active_model

    def test_connection(self):
        """Simple ping to test API Key and Model Access"""
        if not self.api_key: return {"status": "FAIL", "msg": "API Key Eksik"}
        
        try:
            start = time.time()
            # Simple gen
            chat = self.client.chats.create(model=self.primary_model_name)
            response = chat.send_message("Hello")
            duration = time.time() - start
            
            return {
                "status": "OK",
                "model": self.primary_model_name,
                "time": f"{duration:.2f}s",
                "response": response.text[:20]
            }
        except Exception as e:
            return {"status": "FAIL", "msg": str(e)}

    def generate_response(self, prompt, system_instruction=None, history=[], images=[], use_search=False):
        if not self.api_key:
            return "⚠️ API Anahtarı Eksik."

        # Try Primary Model
        try:
            return self._try_generate(self.primary_model_name, prompt, system_instruction, history, images, use_search)
        except Exception as e:
            error_str = str(e)
            print(f"⚠️ Primary Model Error ({self.primary_model_name}): {error_str}")
            
            # Catch 'Invalid operation' (Empty response), Quota (429), or any other crash
            # Switch to Fallback
            print(f"🔄 Switching to Fallback: {self.fallback_model_name}")
            self.current_active_model = self.fallback_model_name
            try:
                return self._try_generate(self.fallback_model_name, prompt, system_instruction, history, images, use_search)
            except Exception as e2:
                return f"❌ All Models Failed. Error: {e2}\nPrimary: {error_str}"

    def _try_generate(self, model_name, prompt, system_instruction, history, images, use_search):
        self.current_active_model = model_name
        
        # 1. Safety Constants (New API uses different structure)
        safety_settings = [
            types.SafetySetting(
                category='HARM_CATEGORY_HARASSMENT',
                threshold='BLOCK_NONE'
            ),
            types.SafetySetting(
                category='HARM_CATEGORY_HATE_SPEECH',
                threshold='BLOCK_NONE'
            ),
            types.SafetySetting(
                category='HARM_CATEGORY_SEXUALLY_EXPLICIT',
                threshold='BLOCK_NONE'
            ),
            types.SafetySetting(
                category='HARM_CATEGORY_DANGEROUS_CONTENT',
                threshold='BLOCK_NONE'
            ),
        ]

        # 2. Tools
        tools = []
        if use_search:
            try: 
                tools = [types.Tool(google_search={})]
            except: 
                pass

        # 3. Generate Config
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            safety_settings=safety_settings,
            tools=tools if tools else None
        )
        
        # 4. Build content (konuşma geçmişi + mevcut mesaj)
        contents = []
        
        # Geçmiş mesajları ekle
        if history:
            for msg in history:
                contents.append(types.Content(
                    role=msg['role'],
                    parts=[types.Part.from_text(text=msg['parts'][0]['text'])]
                ))
        
        # Mevcut mesajı ekle
        current_parts = []
        if images:
            for img in images:
                current_parts.append(types.Part.from_image(img))
        current_parts.append(types.Part.from_text(text=prompt))
        contents.append(types.Content(role='user', parts=current_parts))

        # 5. Generate
        response = self.client.models.generate_content(
            model=model_name,
            contents=contents,
            config=config
        )
        
        # 6. Safe Text Extraction (thought_signature filtreleme)
        # response.text kullanmıyoruz çünkü thought_signature parçalarında uyarı veriyor
        if response.candidates and len(response.candidates) > 0:
            cand = response.candidates[0]
            if cand.content and cand.content.parts and len(cand.content.parts) > 0:
                # Sadece text tipindeki parçaları al, thought_signature'ları atla
                text_parts = []
                for part in cand.content.parts:
                    if hasattr(part, 'text') and part.text:
                        text_parts.append(part.text)
                if text_parts:
                    return "\n".join(text_parts)
            
            # Check finish reason
            if hasattr(cand, 'finish_reason'):
                if 'SAFETY' in str(cand.finish_reason):
                    raise ValueError("Model Safety Filter Triggered")
                elif 'STOP' in str(cand.finish_reason):
                    raise ValueError("Empty response from model")
        
        raise ValueError("No valid text in response")

    def generate_stream(self, prompt, system_instruction=None, history=[], images=[]):
        pass
