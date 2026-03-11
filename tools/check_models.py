import os
import google.generativeai as genai
import json

# --- FEATURE: test_gemini_models ---
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
# --- END FEATURE: test_gemini_models ---

if __name__ == "__main__":
    test_gemini_models()

# ============================================================
# GELISTIRICI NOTU (AI & Insan):
# Bu projede "Feature Marker" sistemi kullanilmaktadir.
# Yeni ozellik eklerken asagidaki formati kullanin:
#
#   # --- FEATURE: ozellik_adi ---
#   ... kodlar ...
#   # --- END FEATURE: ozellik_adi ---
#
# Bu markerlar otomatik guncelleme ve birlestirme icin gereklidir.
# Markerlar olmadan ozellikler kayit defterine eklenmez!
# ============================================================
