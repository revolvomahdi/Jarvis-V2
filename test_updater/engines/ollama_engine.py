import ollama
from .base import BaseEngine

class OllamaEngine(BaseEngine):
    def __init__(self, model_name="llama3"):
        self.model_name = model_name

    def set_model(self, model_name):
        self.model_name = model_name

    def check_installed(self):
        try:
            ollama.list()
            return True
        except:
            return False

    def list_models(self):
        try:
            models = ollama.list()
            return [m['name'] for m in models['models']]
        except:
            return []

    def generate_response(self, prompt, system_instruction=None, history=[], images=[]):
        messages = []
        if system_instruction:
            messages.append({'role': 'system', 'content': system_instruction})
        
        # Add history if format matches
        # (Assuming history is list of strings or dicts, need to standardize. 
        # For now, let's assume history is handled by manager or passed as context string)
        
        msg_payload = {'role': 'user', 'content': prompt}
        if images:
            # Ollama expects path or bytes? It handles bytes if using python library usually, 
            # or paths. The library documentation says 'images': [path_or_bytes]
            # We will pass bytes to be safe if we loaded them, or paths.
            msg_payload['images'] = images

        messages.append(msg_payload)

        try:
            response = ollama.chat(model=self.model_name, messages=messages)
        except Exception as e: 
            # Auto-pull if missing? Maybe too aggressive.
            return f"Ollama Error: {e}"

        return response['message']['content']

    def generate_stream(self, prompt, system_instruction=None, history=[], images=[]):
        # Implementation for stream if needed
        pass
