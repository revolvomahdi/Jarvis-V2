"""
Local Voice Manager — Edge-TTS (TTS, Turkce) + Faster-Whisper (STT, Turkce)
Edge-TTS: Microsoft Edge sesleri, mukemmel Turkce destegiyle.
Faster-Whisper: Yerel STT, Turkce dahil 90+ dil.
"""

import os
import time
import asyncio
import threading
import soundfile as sf

# --- FEATURE: local_voice_manager ---
class LocalVoiceManager:
    """Yerel ses motoru: Edge-TTS (Turkce) + Faster-Whisper STT (Turkce)."""
    
    def __init__(self):
        self._stt_model = None
        self._stt_lock = threading.Lock()
        self._tts_lock = threading.Lock()
        self._stt_loading = False
        
        # TTS ayarlari (Edge-TTS Turkce sesler)
        # Erkek: tr-TR-AhmetNeural
        # Kadin: tr-TR-EmelNeural  
        self.tts_voice = "tr-TR-AhmetNeural"
        self.tts_rate = "-5%"   # Konusma hizi: biraz yavaslatarak dogallastir
        self.tts_pitch = "+5%"  # Ton: biraz canli/sicak ton
        
        # STT ayarlari (Faster-Whisper)
        self.stt_model_size = "medium"  # medium: Turkce icin en iyi denge (base cok yetersiz)
        self.stt_language = "tr"  # Turkce
        self.stt_initial_prompt = "Bu bir Türkçe konuşmadır. Merhaba, nasılsınız?"  # Turkce baglam
        
        # Ses dosyalari icin temp klasor
        self.temp_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "temp_audio")
        os.makedirs(self.temp_dir, exist_ok=True)
    
    # ==================== TTS (Edge-TTS) ====================
    
    def speak(self, text: str) -> str:
        """
        TTS: Metni ses dosyasina cevir (Edge-TTS, Turkce).
        
        Returns:
            Olusturulan MP3 dosyasinin yolu
        """
        if not text or not text.strip():
            return ""
        
        with self._tts_lock:
            try:
                clean_text = self._clean_text_for_tts(text)
                if not clean_text:
                    return ""
                
                filename = f"tts_{int(time.time() * 1000)}.mp3"
                filepath = os.path.join(self.temp_dir, filename)
                
                # Edge-TTS async calistir
                loop = None
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_closed():
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                
                loop.run_until_complete(self._generate_tts(clean_text, filepath))
                
                if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
                    return filepath
                return ""
                
            except Exception as e:
                print(f"[TTS] Edge-TTS hatasi: {e}")
                return ""
    
    async def _generate_tts(self, text: str, filepath: str):
        """Edge-TTS ile ses uret (native parametreler ile dogal ses)."""
        import edge_tts
        
        # Edge-TTS native parametreleri kullan (manuel SSML yok)
        # Edge-TTS kendi icinde SSML olusturur, disaridan sarmalarsak
        # cift katmanli SSML olur ve sonda garip sesler cikar.
        communicate = edge_tts.Communicate(
            text=text,
            voice=self.tts_voice,
            rate=self.tts_rate,
            pitch=self.tts_pitch
        )
        await communicate.save(filepath)
    
    def speak_and_play(self, text: str):
        """TTS + otomatik oynatma (arka plan thread'inde)."""
        if not text:
            return
        threading.Thread(target=self._speak_play_thread, args=(text,), daemon=True).start()
    
    def _speak_play_thread(self, text: str):
        """Arka planda ses uret ve oynat."""
        filepath = self.speak(text)
        if not filepath:
            return
        
        try:
            import pygame
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            
            pygame.mixer.music.load(filepath)
            pygame.mixer.music.play()
            
            while pygame.mixer.music.get_busy():
                time.sleep(0.1)
            
            pygame.mixer.music.unload()
        except ImportError:
            try:
                import winsound
                winsound.PlaySound(filepath, winsound.SND_FILENAME)
            except:
                print("[TTS] Ses oynatma icin pygame veya winsound gerekli")
        except Exception as e:
            print(f"[TTS] Oynatma hatasi: {e}")
        finally:
            try:
                if os.path.exists(filepath):
                    os.remove(filepath)
            except:
                pass
    
    # ==================== STT (Faster-Whisper) ====================
    
    def _load_stt(self):
        """Faster-Whisper STT modelini lazy-load et."""
        if self._stt_model is not None:
            return
        if self._stt_loading:
            return
        
        self._stt_loading = True
        try:
            print(f"[YEREL SES] Whisper STT modeli yukleniyor ({self.stt_model_size})...")
            from faster_whisper import WhisperModel
            self._stt_model = WhisperModel(
                self.stt_model_size, 
                device="cpu",
                compute_type="int8"
            )
            print("[YEREL SES] Whisper STT modeli hazir!")
        except Exception as e:
            print(f"[YEREL SES] Whisper STT yuklenemedi: {e}")
            self._stt_model = None
        finally:
            self._stt_loading = False
    
    def transcribe(self, audio_path: str) -> str:
        """
        STT: Ses dosyasini metne cevir (Turkce).
        """
        with self._stt_lock:
            self._load_stt()
            
            if self._stt_model is None:
                return "[Hata: Whisper STT modeli yuklenemedi]"
            
            try:
                segments, info = self._stt_model.transcribe(
                    audio_path,
                    language=self.stt_language,
                    beam_size=7,
                    best_of=3,
                    temperature=0.0,
                    condition_on_previous_text=True,
                    word_timestamps=True,
                    vad_filter=True,
                    vad_parameters=dict(
                        min_silence_duration_ms=300,
                        speech_pad_ms=200,
                    ),
                    no_speech_threshold=0.5,
                    initial_prompt=self.stt_initial_prompt,
                )
                
                text_parts = []
                for segment in segments:
                    text_parts.append(segment.text.strip())
                
                result = " ".join(text_parts).strip()
                
                if result:
                    try:
                        print(f"[STT] Algilanan: '{result[:80]}'")
                    except:
                        pass
                
                return result if result else ""
                
            except Exception as e:
                print(f"[STT] Transkripsiyon hatasi: {e}")
                return f"[Hata: {str(e)}]"
    
    # ==================== YARDIMCI ====================
    
    def _escape_xml(self, text: str) -> str:
        """XML/SSML icin ozel karakterleri escape et."""
        text = text.replace('&', '&amp;')
        text = text.replace('<', '&lt;')
        text = text.replace('>', '&gt;')
        text = text.replace('"', '&quot;')
        text = text.replace("'", '&apos;')
        return text
    
    def _build_ssml(self, text: str) -> str:
        """SSML prosody ile dogal konusma metni olustur."""
        import re
        
        # XML escape uygula
        escaped_text = self._escape_xml(text)
        
        # Cumleleri ayir ve aralarinda duraklama ekle
        sentences = re.split(r'(?<=[.!?;:])(\s+)', escaped_text)
        
        ssml_parts = []
        for part in sentences:
            part = part.strip()
            if not part:
                continue
            if part in ('.', '!', '?', ';', ':'):
                continue
            ssml_parts.append(part)
        
        # Her cumle arasina duraklama ekle
        body = f' <break time="350ms"/> '.join(ssml_parts)
        
        ssml = (
            f'<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="tr-TR">'
            f'<voice name="{self.tts_voice}">'
            f'<prosody rate="{self.tts_rate}" pitch="{self.tts_pitch}">'
            f'{body}'
            f'</prosody></voice></speak>'
        )
        return ssml
    
    def _clean_text_for_tts(self, text: str) -> str:
        """TTS icin metni temizle."""
        import re
        
        # Kod bloklarini kaldir
        clean = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
        clean = re.sub(r'`[^`]+`', '', clean)  # inline code kaldir
        # Bilgi etiketlerini kaldir
        clean = re.sub(r'\[Hiz:.*?\|.*?Sure:.*?\]', '', clean)
        # Resim linklerini kaldir
        clean = re.sub(r'!\[.*?\]\(.*?\)', '', clean)
        # URL'leri kaldir
        clean = re.sub(r'https?://\S+', '', clean)
        # Markdown isaret karakterlerini kaldir
        clean = clean.replace('*', '').replace('#', '').replace('`', '')
        # Emoji ve ozel unicode karakterleri kaldir
        clean = re.sub(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F900-\U0001F9FF\U00002702-\U000027B0]', '', clean)
        # Fazla satir sonlarini duzenle
        clean = re.sub(r'\n{2,}', '. ', clean)
        clean = re.sub(r'\n', ' ', clean)
        clean = re.sub(r'\s{2,}', ' ', clean)
        clean = clean.strip()
        
        # Cok uzun metinleri cumle sonunda kes
        if len(clean) > 1500:
            cut = clean[:1500]
            last_period = max(cut.rfind('.'), cut.rfind('!'), cut.rfind('?'))
            if last_period > 1000:
                clean = cut[:last_period + 1]
            else:
                clean = cut + "."
        
        return clean
    
    def cleanup_temp(self):
        """Eski temp ses dosyalarini temizle."""
        try:
            now = time.time()
            for f in os.listdir(self.temp_dir):
                fpath = os.path.join(self.temp_dir, f)
                if os.path.isfile(fpath) and (now - os.path.getmtime(fpath)) > 300:
                    os.remove(fpath)
        except:
            pass
# --- END FEATURE: local_voice_manager ---

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
