import json
import os

class SettingsManager:
    def __init__(self, config_path="config.json"):
        self.config_path = config_path
        self.default_config = {
            "language": "tr",
            "theme_color": "#00d2d3",
            "engine_mode": "api",
            "api_mode": "pro",
            "gemini_api_key": "",
            "audio_enabled": False, # NEW SETTING: Default OFF
            "elevenlabs_voice_id": "", # NEW SETTING: Default Empty (uses .env fallback)
            "local_models": {
                "chat": "llama3",
                "code": "qwen2.5-coder",
                "vision": "llava"
            }
        }
        self.config = self.load_config()

    def load_config(self):
        if not os.path.exists(self.config_path):
            return self.default_config
        
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                for key, value in self.default_config.items():
                    if key not in loaded:
                        loaded[key] = value
                return loaded
        except:
            return self.default_config

    def save_config(self):
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            print(f"Config save error: {e}")

    def get(self, key, default=None):
        return self.config.get(key, default)

    def set(self, key, value):
        self.config[key] = value
        self.save_config()
