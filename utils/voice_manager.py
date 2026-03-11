import os
import re
import threading
import time

try:
    import pygame
except ImportError:
    pygame = None

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    from elevenlabs import generate, stream, set_api_key
    ELEVENLABS_AVAILABLE = True
except ImportError:
    ELEVENLABS_AVAILABLE = False

# --- FEATURE: voice_manager ---
class VoiceManager:
    """
    Dual-mode ses yoneticisi:
    - voice_mode='api'   -> ElevenLabs API (cloud)
    - voice_mode='local' -> Kokoro-ONNX (yerel, internet gerektirmez)
    """
    
    def __init__(self):
        # API (ElevenLabs) ayarlari
        self.api_key = os.getenv("ELEVENLABS_API_KEY", "")
        self.voice_id = os.getenv("ELEVENLABS_VOICE_ID", "Rachel")
        self.enabled = False
        self.voice_mode = "api"  # "api" veya "local"
        
        # Local voice manager (lazy-loaded)
        self._local_voice = None
        
        if self.api_key and ELEVENLABS_AVAILABLE:
            try:
                set_api_key(self.api_key)
            except:
                print("ElevenLabs API Key Error")

    def set_enabled(self, enabled: bool):
        self.enabled = enabled

    def set_voice_id(self, voice_id: str):
        if voice_id and len(voice_id) > 5:
            self.voice_id = voice_id
            print(f"Voice ID Updated: {voice_id}")

    def set_voice_mode(self, mode: str):
        """Ses motoru modunu degistir: 'api' veya 'local'."""
        if mode in ("api", "local"):
            self.voice_mode = mode
            print(f"Voice Mode: {mode.upper()}")

    def _get_local_voice(self):
        """Local voice manager'i lazy-load et."""
        if self._local_voice is None:
            try:
                from utils.local_voice_manager import LocalVoiceManager
                self._local_voice = LocalVoiceManager()
            except Exception as e:
                print(f"Local Voice Manager yuklenemedi: {e}")
        return self._local_voice

    def speak(self, text):
        """Metni seslendir — mode'a gore API veya yerel."""
        if not self.enabled:
            return
        
        if self.voice_mode == "local":
            self._speak_local(text)
        else:
            self._speak_api(text)

    def _speak_local(self, text):
        """Kokoro-ONNX ile yerel TTS."""
        local = self._get_local_voice()
        if local:
            local.speak_and_play(text)

    def _speak_api(self, text):
        """ElevenLabs API ile TTS."""
        if not self.api_key or not ELEVENLABS_AVAILABLE:
            return

        # Metni temizle
        clean_text = re.sub(r'```.*?```', ' Kod ornegi ekranda mevcuttur. ', text, flags=re.DOTALL)
        clean_text = re.sub(r'\[Hiz:.*?\|.*?Sure:.*?\]', '', clean_text)
        clean_text = re.sub(r'!\[.*?\]\(.*?\)', ' Gorsel olusturuldu. ', clean_text)
        clean_text = clean_text.replace('*', '').replace('#', '').strip()
        
        if not clean_text:
            return

        threading.Thread(target=self._play_stream_api, args=(clean_text,), daemon=True).start()

    def _play_stream_api(self, text):
        """ElevenLabs API streaming/fallback."""
        try:
            try:
                audio_stream = generate(
                    text=text,
                    voice=self.voice_id,
                    model="eleven_multilingual_v2",
                    stream=True
                )
                stream(audio_stream)
                
            except Exception:
                audio_bytes = generate(
                    text=text,
                    voice=self.voice_id,
                    model="eleven_multilingual_v2"
                )
                
                temp_file = f"temp_voice_{int(time.time())}.mp3"
                with open(temp_file, "wb") as f:
                    f.write(audio_bytes)
                
                if pygame and not pygame.mixer.get_init():
                    pygame.mixer.init()
                
                if pygame:
                    pygame.mixer.music.load(temp_file)
                    pygame.mixer.music.play()
                    
                    while pygame.mixer.music.get_busy():
                        time.sleep(0.1)
                    
                    pygame.mixer.music.unload()
                
                if os.path.exists(temp_file):
                    try: os.remove(temp_file)
                    except: pass

        except Exception as e:
            print(f"ElevenLabs TTS Error: {e}")
# --- END FEATURE: voice_manager ---

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
