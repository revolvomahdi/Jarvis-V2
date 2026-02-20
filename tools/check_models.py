import os
import google.generativeai as genai
import json

def test_gemini_models():
    # Load key from config
    try:
        with open("config.json", "r") as f:
            cfg = json.load(f)
        key = cfg.get("gemini_api_key")
        if not key:
            print("❌ No API Key in config.json")
            return
        
        genai.configure(api_key=key)
        print("🔍 Scanning Gemini Models...")
        
        models = []
        for m in genai.list_models():
            if "gemini" in m.name:
                models.append(m.name)
        
        print(f"Found {len(models)} models:")
        for m in models:
            print(f" - {m}")
            
        print("\n--- Simulation: Best Model Selection ---")
        candidates = sorted(models, reverse=True)
        best = candidates[0] if candidates else "None"
        print(f"Algorithm would pick: {best}")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_gemini_models()
