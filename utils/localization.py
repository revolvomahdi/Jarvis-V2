import json
import os

class Localizer:
    def __init__(self, lang_code="tr"):
        self.lang_code = lang_code
        self.data = {}
        self.load_language(lang_code)

    def load_language(self, lang_code):
        file_path = f"data/{lang_code}.json"
        if not os.path.exists(file_path):
            file_path = "data/tr.json" # Fallback
            
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                self.data = json.load(f)
        except Exception as e:
            print(f"Localization error: {e}")
            self.data = {}

    def get(self, key_path):
        """
        key_path format: "ui.sidebar.title"
        """
        keys = key_path.split(".")
        val = self.data
        for k in keys:
            val = val.get(k)
            if val is None:
                return key_path # Return key if not found
        return val
