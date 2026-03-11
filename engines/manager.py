from .gemini_engine import GeminiEngine
from .ollama_engine import OllamaEngine
from .local_brain import LocalBrain
from .system_tools import SystemManager, WebTools, ScreenTools
# Image generation disabled - no longer importing ImageGenerator
# from .image_generator import ImageGenerator
from utils.settings_manager import SettingsManager
from utils.voice_manager import VoiceManager
from engines.task_manager import TaskManager
from PIL import Image
import threading
import time

from utils.memory_manager import MemoryManager

# --- FEATURE: engine_manager ---
class EngineManager:
    def __init__(self):
        self.settings = SettingsManager()
        self.sys_manager = SystemManager()
        self.web_tools = WebTools()
        
        # Audio Manager (ElevenLabs)
        self.voice = VoiceManager()
        # Initial setting load
        self.voice.set_enabled(self.settings.get("audio_enabled", False))
        
        saved_voice_id = self.settings.get("elevenlabs_voice_id")
        if saved_voice_id:
            self.voice.set_voice_id(saved_voice_id)
        
        # System Engineer Task Manager
        self.task_manager = TaskManager()
        
        self.memory = MemoryManager()
        
        # Init Engines
        self.gemini = GeminiEngine(self.settings.get("gemini_api_key"), self.settings.get("api_mode"))
        self.ollama = OllamaEngine(self.settings.get("local_models")["chat"])
        self.local_brain = LocalBrain() # Multi-Agent Brain
        
        # Internal mode state (defaults to settings, but can be overridden at runtime)
        self.mode = self.settings.get("engine_mode")

    def set_execution_mode(self, mode: str):
        """Sets the execution mode (api/local) dynamically without saving to config permanently yet.
           Server endpoint should handle persistence."""
        if mode in ["api", "local", "cloud"]:
            # Standardize 'cloud' to 'api' internally
            if mode == "cloud": mode = "api"
            
            self.mode = mode
            print(f"Engine Switched to: {mode.upper()}")


    def get_active_engine(self):
        # self.mode is now the source of truth for the session
        if self.mode == "api":
            if self.gemini.api_key != self.settings.get("gemini_api_key"):
                self.gemini.api_key = self.settings.get("gemini_api_key")
                self.gemini.set_mode(self.settings.get("api_mode"))
            return self.gemini
        else:
            return self.ollama

    def get_model_name(self):
        engine = self.get_active_engine()
        if self.mode == "api":
            # Just accessing the internal name if possible
            current = engine.current_active_model if hasattr(engine, 'current_active_model') else "Gemini"
            # color = "🟢" if "flash-preview" in current or "3" in current else "🟡"
            return f"{current}"
        else:
            return f"{engine.model_name}"

    def speak(self, text):
        # 1. Check if Audio is Enabled in Settings (Already handled inside VoiceManager, but double check here to filter empty text)
        if self.settings.get("audio_enabled", False):
            self.voice.speak(text)
        else:
            pass # Muted

    def chat_mode(self, message, history=None, progress_callback=None):
        # 0. Intercept System Commands (Global Access)
        msg_lower = message.lower()
        
        # BROWSER Interception — tarayici kontrolu her modda LocalBrain'e yonlendirilir
        browser_keywords = [
            "youtube'da", "youtube'a", "youtube'u", "youtubeu", "youtube'dan",
            "google'da", "google'a", "google'u", "googleu", "google'dan",
            "amazon'da", "amazon'u", "amazonu", "amazon'a", "amazon'dan",
            "instagram'a", "instagram'ı", "instagramı", "instagram'dan",
            "twitter'a", "twitter'ı", "twitterı", "twitter'dan",
            "wikipedia'da", "reddit'e", "tarayıcıda", "tarayicida", "web sitesine",
            "gmail", "whatsapp web", "amazonda", "youtubeda", 
            "googleda", "twitterda", "instagramda", "wikipediada",
            "netflix'te", "netflixte", "netflix'i"
        ]
        if any(x in msg_lower for x in browser_keywords):
            try:
                return self.local_brain._agent_browser(message)
            except Exception as e:
                print(f"Browser intercept error: {e}")
                # Fallback to normal chat if browser fails
        
        # System Status Keywords
        if any(x in msg_lower for x in ["sistem durum", "pc durum", "sistem rapor", "kaynaklar"]):
            return self.work_mode(message) # Delegate to work mode logic
            
        # Optimization Keywords
        if any(x in msg_lower for x in ["ram temizle", "oyun modu", "hızlandır"]):
            return self.work_mode(message)
            
        # Resource Hog Keywords
        if any(x in msg_lower for x in ["ne kasıyor", "ram sömüren", "işlemci sömüren"]):
            return self.work_mode(message)
            
        # Disk Usage Interception
        if any(x in msg_lower for x in ["diskini ne dolduruyor", "en büyük dosyalar", "yer kaplayanlar", "hafıza nerede"]):
            return self.work_mode(message)
            
        # Scan Input for Memory
        # (This is a simplified approach, ideally handled async)
        
        # Retrieval
        memory_context = self.memory.get_context()
        sys_context = ""
        if memory_context:
            sys_context = f"\n[HAFIZA BİLGİSİ]: {memory_context}\n"
        
        response = ""
        
        # Use LocalBrain if mode is local
        if self.mode == "local":
            try:
                # Hafiza bilgisi artik sadece chat ajaninda enjekte ediliyor.
                # Komutana gereksiz hafiza bilgisi gondermek sınıflandırmayı bozuyor.
                response = self.local_brain.process_request(message, history=history, progress_callback=progress_callback, memory_context=memory_context)
                
                # Check for empty response
                if not response:
                    response = "Üzgünüm, yerel beyinden boş cevap döndü."

                # Save
                self.memory.remember(message, response)
            except Exception as e:
                print(f"Manager Local Error: {e}")
                response = f"Genel Merkez Hatasi: {e}"
        else:
            # Cloud (Gemini) — Gelişmiş Kişiselleştirme
            try:
                engine = self.get_active_engine()
                
                # Gelişmiş profil context'i al
                cloud_profile = self.memory.get_cloud_context()
                if cloud_profile:
                    sys_context = f"\n{cloud_profile}\n"
                
                sys = (
                    "Sen JARVIS'sin. Kullanıcıya 'Efendim' diye hitap et. "
                    "Yardımcı, zeki ve kısa cevaplar ver. "
                    "Kullanıcı hakkında bildiklerini doğal şekilde kullan — "
                    "adını bil, tercihlerini hatırla, kişiye özel cevaplar ver. "
                    f"{sys_context}"
                )
                
                # Gemini'ye geçmiş mesajları da gönder
                gemini_history = []
                if history:
                    for msg in history[:-1]:  # Son mesaj hariç (o zaten prompt olarak gidecek)
                        role = 'user' if msg['role'] == 'user' else 'model'
                        gemini_history.append({'role': role, 'parts': [{'text': msg['text']}]})
                
                response = engine.generate_response(message, system_instruction=sys, history=gemini_history)
                
                # Arka planda kişisel bilgi çıkarımı (cevabı geciktirmez)
                if hasattr(engine, 'client') and engine.client:
                    self.memory.remember_cloud(
                        message, response, 
                        engine.client, 
                        engine.current_active_model
                    )
                
                # Eski yerel hafıza da kaydetsin (geriye uyumluluk)
                self.memory.remember(message, response)
            except Exception as e:
                response = f"Cloud Error: {e}"
        
        # --- TTS INTEGRATION ---
        # Only speak if valid response
        if response and isinstance(response, str):
            self.speak(response)
            
        return response



    def research_mode(self, message):
        engine = self.get_active_engine()
        query = message.replace("/a", "").replace("araştır", "").strip()

        if self.mode == "api":
            response = engine.generate_response(
                f"Araştır ve detaylı bilgi ver: {query}", 
                system_instruction="Sen bir araştırmacısın. Güncel verileri kullan.",
                use_search=True
            )
            return response
        else:
            results = self.web_tools.search(query)
            if not results: return "Internetten veri alinamadi."
            
            context = ""
            for i, r in enumerate(results[:3]):
                raw = self.web_tools.read_url(r['href'])
                if raw: context += f"\nKAYNAK {i+1}: {r['title']}\n{raw[:1000]}\n"
            
            prompt = f"SORU: {query}\nVERİLER: {context}\n\nBu verilere göre soruyu cevapla:"
            return engine.generate_response(prompt)

    def vision_mode(self, message):
        engine = self.get_active_engine()
        path = ScreenTools.take_screenshot()
        if not path: return "Ekran alınamadı."
        try:
            img = Image.open(path)
            return engine.generate_response(message or "Ne görüyorsun?", images=[img])
        except Exception as e:
            return f"Vision Hata: {e}"

    def work_mode(self, message):
        msg = message.lower()
        
        # 1. System Status
        if any(x in msg for x in ["sistem durum", "pc durum", "sistem rapor", "kaynaklar"]):
            status = self.task_manager.get_system_status()
            
            disks_str = "\n".join([f"- 💾 {d}" for d in status.get('disks', [])])
            if not disks_str: disks_str = "- Disk verisi alınamadı"

            report = (f"💻 **Sistem Durumu:**\n"
                      f"- 🕒 Sistem Açık: {status.get('uptime', 'N/A')}\n"
                      f"- 🔥 CPU: %{status['cpu_percent']} (Sıcaklık: {status.get('cpu_temp', 'N/A')})\n"
                      f"- 🎮 GPU: {status.get('gpu', 'N/A')}\n"
                      f"- 🧠 RAM: %{status['ram_percent']} ({status['ram_used_gb']} GB / {status['ram_total_gb']} GB)\n"
                      f"- 🔋 Pil: {status['battery']}\n"
                      f"\n**Disk Durumu:**\n{disks_str}")
            return report

        # 2. Resource Hogs
        if any(x in msg for x in ["ram sömüren", "uygulama listesi", "ne kasıyor", "işlemci sömüren"]):
            hogs = self.task_manager.get_resource_hogs()
            report = "🛑 **Kaynak Canavarları (Top 5):**\n"
            for p in hogs:
                report += f"- **{p['name']}**: {p['memory_mb']} MB RAM | %{p['cpu_percent']} CPU\n"
            return report

        # 3. Game Mode / Optimize
        if any(x in msg for x in ["oyun modu", "ram temizle", "hızlandır"]):
            opt = self.task_manager.optimize_performance()
            if not opt['candidates']:
                return "✅ Sistem zaten optimize durumda. Gereksiz büyük uygulama bulunamadı."
            
            report = f"🚀 **Oyun Modu Önerisi:**\nŞu uygulamalar kapatılarak yaklaşık **{opt['total_potential_freed_mb']} MB** RAM kazanılabilir:\n"
            for p in opt['candidates']:
                report += f"- {p['name']} ({p['memory_mb']} MB)\n"
            report += "\nKapatmak için 'Onaylıyorum' veya 'Hepsini kapat' demen yeterli."
            return report

        # 4. Disk Usage Analysis
        if any(x in msg for x in ["diskini ne dolduruyor", "en büyük dosyalar", "yer kaplayanlar", "ne yer kaplıyor"]):
            usage = self.task_manager.analyze_disk_usage()
            if not usage:
                 return "⚠️ Kullanıcı profili klasörlerinde kayda değer (%100 MB üstü) büyük boyutlu klasör bulunamadı."
            
            report = "💾 **Disk Kullanım Analizi (Kullanıcı Klasörleri):**\n"
            for item in usage:
                icon = "📁"
                if "Temp" in item['path']: icon = "🗑️"
                elif "Downloads" in item['path']: icon = "⬇️"
                
                report += f"- {icon} **{item['path']}**: {item['size_gb']} GB\n"
            return report
            
        # 5. Kill Process (Direct)
        if "kapat" in msg and ("chrome" in msg or "discord" in msg or "spotify" in msg or ".exe" in msg):
            # Simple extraction strategy
            target = ""
            if "chrome" in msg: target = "chrome.exe"
            elif "discord" in msg: target = "discord.exe"
            elif "spotify" in msg: target = "spotify.exe"
            
            if target:
                res = self.task_manager.kill_process(target)
                return res['message']

        if "youtube" in msg:
            import webbrowser
            query = message.lower().replace('youtube', '').strip()
            if query:
                webbrowser.open(f"https://www.youtube.com/results?search_query={query}")
            else:
                webbrowser.open("https://www.youtube.com")
            return "YouTube varsayılan tarayıcıda açılıyor..."
            
        return self.chat_mode(message)
# --- END FEATURE: engine_manager ---

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
