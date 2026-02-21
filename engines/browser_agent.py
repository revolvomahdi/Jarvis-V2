"""
Browser Agent - LLM tabanli tarayici gorev planlayici.
Kullanicinin dogal dil komutlarini Playwright aksiyon planlarina cevirir.
Iki model kullanir: Planlayici (kod modeli) + Gorucu (vision modeli).
"""

import json
import re
import ollama
import base64
from utils.settings_manager import SettingsManager


class BrowserAgent:
    """Kullanici istegini tarayici aksiyonlarina ceviren LLM agent."""
    
    def __init__(self):
        self.settings = SettingsManager()
        agents = self.settings.get("local_agents", {})
        self.planner_model = agents.get("browser_planner", "qwen2.5-coder:7b")
        self.vision_model = agents.get("browser_vision", "llava:v1.6")
    
    def create_plan(self, user_request, current_url="", page_title=""):
        """
        Kullanici isteginden JSON aksiyon plani uret.
        
        Return: list of action dicts
        """
        context = ""
        if current_url:
            context += f"\nSu an acik sayfa: {current_url}"
        if page_title:
            context += f"\nSayfa basligi: {page_title}"
        
        prompt = f"""Sen bir tarayici otomasyon planlaycisisin. Kullanicinin istegini Playwright aksiyonlarina cevirmelisin.

KULLANICI ISTEGI: "{user_request}"{context}

KULLANABILICEGIN AKSIYONLAR:
- {{"action": "goto", "url": "https://..."}} - Sayfaya git
- {{"action": "click", "selector": "CSS_SELECTOR"}} - Elemente tikla
- {{"action": "type", "selector": "CSS_SELECTOR", "text": "..."}} - Yazi yaz
- {{"action": "press", "key": "Enter|Tab|Escape"}} - Tus bas
- {{"action": "scroll", "direction": "down|up", "amount": 300}} - Scroll
- {{"action": "wait", "seconds": 2}} - Bekle
- {{"action": "screenshot_check"}} - Ekran goruntusu al ve kontrol et

KURALLAR:
1. Sadece JSON array dondur, baska hicbir sey yazma
2. CSS selector'lar gercekci olsun
3. Sayfanin yuklenmesi icin wait ekle
4. Her adim basit ve net olsun

BILINEN SITELER VE SELECTORLER:
- YouTube: arama = "input#search", arama butonu = "button#search-icon-legacy", ilk video = "ytd-video-renderer a#video-title"
- Google: arama = "textarea[name='q']", arama butonu = "input[name='btnK']"
- Wikipedia: arama = "input#searchInput", arama butonu = "button.cdx-button"
- X/Twitter: arama = "input[data-testid='SearchBox_Search_Input']"
- Amazon: arama = "input#twotabsearchtextbox", arama butonu = "input#nav-search-submit-button"

CEVAP (SADECE JSON ARRAY):"""

        try:
            response = ollama.chat(
                model=self.planner_model,
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": 0.1, "num_predict": 1024}
            )
            
            raw = response["message"]["content"].strip()
            plan = self._extract_json(raw)
            
            if plan:
                print(f"[BROWSER AGENT] Plan olusturuldu: {len(plan)} adim")
                return plan
            else:
                print(f"[BROWSER AGENT] JSON parse hatasi, raw: {raw[:200]}")
                return self._fallback_plan(user_request)
            
        except Exception as e:
            print(f"[BROWSER AGENT] Planlama hatasi: {e}")
            return self._fallback_plan(user_request)
    
    def analyze_screenshot(self, screenshot_base64, question="Bu sayfada ne goruyorsun? Kullanici ne yapmali?"):
        """
        Vision modeli ile screenshot analiz et.
        
        Return: str (analiz sonucu)
        """
        try:
            response = ollama.chat(
                model=self.vision_model,
                messages=[{
                    "role": "user",
                    "content": question,
                    "images": [screenshot_base64]
                }],
                options={"temperature": 0.3, "num_predict": 512}
            )
            return response["message"]["content"].strip()
        except Exception as e:
            print(f"[BROWSER AGENT] Vision hatasi: {e}")
            return ""
    
    def replan_from_error(self, original_request, error_info, screenshot_base64=None):
        """
        Basarisiz bir adimdan sonra yeni plan olustur.
        Opsiyonel olarak screenshot ile gorucu modeli kullanir.
        """
        context = f"Orijinal istek: {original_request}\nHata: {error_info}"
        
        if screenshot_base64:
            vision_analysis = self.analyze_screenshot(
                screenshot_base64, 
                f"Tarayicida su islemi yapmaya calisiyorum: '{original_request}'. Bu ekran goruntusune gore hangi elemente tiklamaliyim veya ne yapmaliyim?"
            )
            context += f"\nEkran analizi: {vision_analysis}"
        
        prompt = f"""Tarayici otomasyon plani basarisiz oldu. Yeni plan olustur.

{context}

Sadece JSON array dondur:"""

        try:
            response = ollama.chat(
                model=self.planner_model,
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": 0.2, "num_predict": 1024}
            )
            raw = response["message"]["content"].strip()
            return self._extract_json(raw) or []
        except:
            return []
    
    def _extract_json(self, text):
        """Metinden JSON array'i cikar."""
        # Direkt JSON dene
        try:
            result = json.loads(text)
            if isinstance(result, list):
                return result
        except:
            pass
        
        # ```json ... ``` blogu ara
        match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
        if match:
            try:
                result = json.loads(match.group(1))
                if isinstance(result, list):
                    return result
            except:
                pass
        
        # [ ... ] blogu ara
        match = re.search(r'\[.*\]', text, re.DOTALL)
        if match:
            try:
                result = json.loads(match.group(0))
                if isinstance(result, list):
                    return result
            except:
                pass
        
        return None
    
    def _fallback_plan(self, user_request):
        """LLM basarisiz olursa basit kural tabanli plan."""
        req = user_request.lower()
        plan = []
        
        # YouTube
        if "youtube" in req:
            plan.append({"action": "goto", "url": "https://www.youtube.com"})
            plan.append({"action": "wait", "seconds": 2})
            
            # Arama kelimesini cikar
            search_term = self._extract_search_term(req, "youtube")
            if search_term:
                plan.append({"action": "click", "selector": "input#search"})
                plan.append({"action": "type", "selector": "input#search", "text": search_term})
                plan.append({"action": "press", "key": "Enter"})
                plan.append({"action": "wait", "seconds": 2})
                plan.append({"action": "click", "selector": "ytd-video-renderer a#video-title"})
        
        # Google
        elif "google" in req:
            plan.append({"action": "goto", "url": "https://www.google.com"})
            plan.append({"action": "wait", "seconds": 1})
            
            search_term = self._extract_search_term(req, "google")
            if search_term:
                plan.append({"action": "click", "selector": "textarea[name='q']"})
                plan.append({"action": "type", "selector": "textarea[name='q']", "text": search_term})
                plan.append({"action": "press", "key": "Enter"})
        
        # Genel URL
        elif any(x in req for x in ["gir", "git", "ac"]):
            # URL cikar
            url_match = re.search(r'([\w]+\.[\w]+(?:\.[\w]+)*)', req)
            if url_match:
                url = url_match.group(1)
                if not url.startswith("http"):
                    url = "https://" + url
                plan.append({"action": "goto", "url": url})
                plan.append({"action": "wait", "seconds": 2})
        
        if not plan:
            # En basit fallback — Google'da ara
            plan.append({"action": "goto", "url": f"https://www.google.com/search?q={user_request}"})
            plan.append({"action": "wait", "seconds": 2})
        
        return plan
    
    def _extract_search_term(self, text, site_name):
        """Arama terimini cikar: 'YouTube'da X ara' → 'X'"""
        # "da/de/ta/te" ile ayirma
        patterns = [
            rf"{site_name}['\u2019]?(?:da|de|ta|te)\s+(.+?)(?:\s+ara|\s+bul|\s+ac|\s+izle|\s+dinle|$)",
            rf"{site_name}['\u2019]?(?:da|de|ta|te)\s+(.+)",
            rf"(.+?)\s+{site_name}",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                term = match.group(1).strip()
                # Gereksiz kelimeleri temizle
                for noise in ["ara", "bul", "ac", "izle", "dinle", "git", "gir", "bak"]:
                    term = term.replace(noise, "").strip()
                if term:
                    return term
        
        return None
