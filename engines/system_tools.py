import os
import shutil
import subprocess
import pyautogui
import requests
import re
import ollama
from datetime import datetime

# --- FEATURE: system_manager ---
class SystemManager:
    def __init__(self):
        self.user_profile = os.path.expanduser("~")
        self.onedrive = os.path.join(self.user_profile, "OneDrive")
        self.has_onedrive = os.path.exists(self.onedrive)
        self.default_path = os.path.join(self.onedrive, "Desktop") if self.has_onedrive else os.path.join(self.user_profile, "Desktop")
        self.context_path = self.default_path
        self.last_created_path = None 

    def get_path(self, keyword):
        k = keyword.lower()
        if "belge" in k or "doc" in k: return os.path.join(self.onedrive, "Documents") if self.has_onedrive else os.path.join(self.user_profile, "Documents")
        elif "resim" in k or "pic" in k: return os.path.join(self.onedrive, "Pictures") if self.has_onedrive else os.path.join(self.user_profile, "Pictures")
        elif "indir" in k or "down" in k: return os.path.join(self.user_profile, "Downloads")
        elif "masaüst" in k: return self.default_path
        else: return self.default_path

    def resolve_path(self, message):
        message = message.lower()
        # Disk detection
        disk = re.search(r'\b([a-z]):', message)
        if disk:
            drive = disk.group(1).upper()
            path = f"{drive}:\\"
            if os.path.exists(path):
                self.context_path = path
                return path
        
        path = self.context_path
        if "belge" in message: path = self.get_path("belge")
        elif "resim" in message: path = self.get_path("resim")
        elif "indir" in message: path = self.get_path("indir")
        elif "masaüst" in message: path = self.get_path("masaüst")
        
        self.context_path = path
        return path

class WebTools:
    """Ollama Web Search API ile arama yapar."""
    def __init__(self):
        pass

    def read_url(self, url):
        """Ollama web_fetch ile sayfa icerigini oku."""
        try:
            result = ollama.web_fetch(url)
            content = result.get('content', '') if isinstance(result, dict) else getattr(result, 'content', '')
            return content[:5000] if content else ""
        except Exception as e:
            print(f"Web Fetch Error: {e}")
            return ""

    def search(self, query):
        """Ollama web_search ile arama yap. Sonuclari eski formata uyumlu dondurur."""
        results = []
        try:
            response = ollama.web_search(query)
            # response.results veya response['results'] olabilir
            raw_results = []
            if isinstance(response, dict):
                raw_results = response.get('results', [])
            elif hasattr(response, 'results'):
                raw_results = response.results
            
            for r in raw_results[:5]:
                if isinstance(r, dict):
                    results.append({
                        'title': r.get('title', ''),
                        'body': r.get('content', ''),
                        'href': r.get('url', '')
                    })
                else:
                    # WebSearchResult object
                    results.append({
                        'title': getattr(r, 'title', ''),
                        'body': getattr(r, 'content', ''),
                        'href': getattr(r, 'url', '')
                    })
        except Exception as e:
            print(f"Ollama Web Search Error: {e}")
        return results

class ScreenTools:
    @staticmethod
    def take_screenshot(path="screen_analysis.jpg"):
        try:
            full_path = os.path.join(os.getcwd(), path)
            pyautogui.screenshot().save(full_path)
            return full_path
        except Exception as e:
            print(f"Screenshot error: {e}")
            return None
# --- END FEATURE: system_manager ---

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
