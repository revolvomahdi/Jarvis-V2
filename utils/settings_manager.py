import json
import os

class SettingsManager:
    def __init__(self, config_path="config.json", keys_path="api_keys.json"):
        self.config_path = config_path
        self.keys_path = keys_path
        self.default_config = {
            "language": "tr",
            "theme_color": "#00d2d3",
            "engine_mode": "api",
            "api_mode": "pro",
            "audio_enabled": False, # NEW SETTING: Default OFF
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

    def _load_keys(self):
        """API anahtarlarini ayri dosyadan yukler."""
        if not os.path.exists(self.keys_path):
            return {"api_key": "", "gemini_api_key": "", "elevenlabs_voice_id": ""}
        try:
            with open(self.keys_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {"api_key": "", "gemini_api_key": "", "elevenlabs_voice_id": ""}

    def _save_keys(self, keys_dict):
        """API anahtarlarini dosyaya kaydeder."""
        try:
            with open(self.keys_path, "w", encoding="utf-8") as f:
                json.dump(keys_dict, f, indent=4)
        except Exception as e:
            print(f"Keys save error: {e}")

    def save_config(self):
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            print(f"Config save error: {e}")

    def get(self, key, default=None):
        keys_fields = ["api_key", "gemini_api_key", "elevenlabs_voice_id"]
        if key in keys_fields:
            keys = self._load_keys()
            return keys.get(key, default)
        return self.config.get(key, default)

    def set(self, key, value):
        keys_fields = ["api_key", "gemini_api_key", "elevenlabs_voice_id"]
        if key in keys_fields:
            keys = self._load_keys()
            keys[key] = value
            self._save_keys(keys)
        else:
            self.config[key] = value
            self.save_config()
