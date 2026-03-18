import os
import time
import threading
import queue
import asyncio
import io
import pyaudio
import wave
import speech_recognition as sr
import edge_tts
import pyttsx3 # Fallback TTS

# --- CONFIG ---
TTS_VOICE = "tr-TR-AhmetNeural" # or tr-TR-EmelNeural
TTS_RATE = "-5%"    # Biraz yavaslatarak dogallastir
TTS_PITCH = "+5%"   # Biraz canli ton
WHISPER_MODEL_SIZE = "medium" # medium: Turkce icin en iyi denge
STT_INITIAL_PROMPT = "Bu bir Türkçe konuşmadır. Merhaba, nasılsınız?"

# --- FEATURE: jarvis_voice ---
class JarvisVoice:
    def __init__(self):
        self.r = sr.Recognizer()
        
        # Audio Queue for TTS
        self.speech_queue = queue.Queue()
        self.is_running = True
        
        # Whisper Model
        self.whisper_model = None
        self.model_loaded = False
        
        # Recording State
        self.is_recording = False
        self.frames = []
        self.audio_format = pyaudio.paInt16
        self.channels = 1
        self.rate = 16000
        self.chunk = 1024
        self.p = pyaudio.PyAudio()
        
        # Fallback Engine
        try:
            self.engine = pyttsx3.init()
            self.engine.setProperty('rate', 160)
        except: self.engine = None

        # Start TTS Worker
        self.worker_thread = threading.Thread(target=self._speech_worker_entry, daemon=True)
        self.worker_thread.start()

    def load_premium_models(self):
        """Loads Whisper Model"""
        try:
            print("[INFO] Jarvis: Loading Whisper (Deep Learning STT)...")
            import whisper
            # Force CPU usage if GPU VRAM is low or not configured, but ideally let torch decide
            self.whisper_model = whisper.load_model(WHISPER_MODEL_SIZE)
            self.model_loaded = True
            print(f"[OK] Jarvis: Whisper ({WHISPER_MODEL_SIZE}) Loaded.")
        except Exception as e:
            print(f"[ERR] Whisper Load Failed: {e}")
            self.model_loaded = False

    def _speech_worker_entry(self):
        """Asyncio loop runner for Edge TTS which is async"""
        # Create a new loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self._speech_worker_async())

    def _clean_text_for_tts(self, text: str) -> str:
        """TTS icin metni temizle: markdown, kod bloklari, URL vs. kaldir."""
        import re
        # Kod bloklarini kaldir
        clean = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
        clean = re.sub(r'`[^`]+`', '', clean)
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
        # Fazla bosluk ve satir sonlarini duzenle
        clean = re.sub(r'\n{2,}', '. ', clean)
        clean = re.sub(r'\n', ' ', clean)
        clean = re.sub(r'\s{2,}', ' ', clean)
        clean = clean.strip()
        # Cok uzun metinleri kısalt (Edge-TTS uzun metinlerde bozulur)
        if len(clean) > 1500:
            # Cumle sonunda kes
            cut = clean[:1500]
            last_period = max(cut.rfind('.'), cut.rfind('!'), cut.rfind('?'))
            if last_period > 1000:
                clean = cut[:last_period + 1]
            else:
                clean = cut + "."
        return clean

    def _escape_xml(self, text: str) -> str:
        """XML/SSML icin ozel karakterleri escape et."""
        text = text.replace('&', '&amp;')
        text = text.replace('<', '&lt;')
        text = text.replace('>', '&gt;')
        text = text.replace('"', '&quot;')
        text = text.replace("'", '&apos;')
        return text

    async def _speech_worker_async(self):
        """Processes TTS queue using Edge TTS"""
        while self.is_running:
            try:
                # Poll the queue
                if not self.speech_queue.empty():
                    text = self.speech_queue.get()
                    if text:
                        # Metni TTS icin temizle
                        clean_text = self._clean_text_for_tts(text)
                        if not clean_text:
                            print("[TTS] Temizlenen metin bos, atlaniyor.")
                            self.speech_queue.task_done()
                            continue
                        
                        print(f"[SAY] {clean_text[:100]}..." if len(clean_text) > 100 else f"[SAY] {clean_text}")
                        # Try Online EdgeTTS First
                        success = False
                        try:
                            output_file = "temp_speech.mp3"
                            # Ensure clean state
                            if os.path.exists(output_file): os.remove(output_file)
                            
                            # Edge-TTS native parametreleri kullan (manuel SSML yok)
                            # Edge-TTS kendi icinde SSML olusturur, biz disaridan sarmalarsak
                            # cift katmanli SSML olur ve sonda garip sesler cikar.
                            communicate = edge_tts.Communicate(
                                text=clean_text,
                                voice=TTS_VOICE,
                                rate=TTS_RATE,
                                pitch=TTS_PITCH
                            )
                            await communicate.save(output_file)
                            
                            # Verify file exists and has size
                            if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                                self._play_audio(output_file)
                                success = True
                                if os.path.exists(output_file): os.remove(output_file)
                            else:
                                print("[TTS ERR] File generated but empty or missing.")
                        except Exception as e:
                            print(f"[TTS ERR] EdgeTTS Failed: {e}")
                            
                        # Fallback to Offline TTS if Failed
                        if not success:
                            print("[TTS] Switching to Offline Fallback...")
                            self._speak_fallback(clean_text)
                    
                    self.speech_queue.task_done()
                else:
                    await asyncio.sleep(0.1)
            except Exception as e:
                print(f"[WORKER ERR] {e}")
                await asyncio.sleep(1)

    def _speak_fallback(self, text):
        """Uses pyttsx3"""
        if self.engine:
            try:
                self.engine.say(text)
                self.engine.runAndWait()
            except Exception as e:
                print(f"[FALLBACK ERR] {e}")

    def _play_audio(self, file_path):
        """Plays audio using pygame (better for mp3) or os default"""
        try:
            # Using PyGame for better control if available, else os command
            import pygame
            pygame.mixer.init()
            pygame.mixer.music.load(file_path)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                time.sleep(0.1)
            pygame.mixer.quit()
        except ImportError:
            # Fallback to system player
            os.system(f'start /min /wait "" "{file_path}"')
        except Exception as e:
            print(f"[PLAY ERR] {e}")

    def speak(self, text):
        """Adds text to the speech queue."""
        if not text: return
        self.speech_queue.put(text)

    # --- PUSH TO TALK METHODS --- (No changes needed here)
    def start_recording(self):
        """Starts recording audio stream"""
        if self.is_recording: return
        print("[MIC] Recording Started...")
        self.is_recording = True
        self.frames = []
        threading.Thread(target=self._record_loop, daemon=True).start()

    def _record_loop(self):
        try:
            stream = self.p.open(format=self.audio_format,
                                 channels=self.channels,
                                 rate=self.rate,
                                 input=True,
                                 frames_per_buffer=self.chunk)
            while self.is_recording:
                data = stream.read(self.chunk)
                self.frames.append(data)
            
            stream.stop_stream()
            stream.close()
        except Exception as e:
            print(f"[MIC ERR] {e}")
            self.is_recording = False

    def stop_recording(self):
        """Stops recording and returns transcribed text"""
        print("[MIC] Recording Stopped. Transcribing...")
        self.is_recording = False
        time.sleep(0.2) # Wait for thread to finish
        
        if not self.frames: return ""
        
        # Save to WAV
        filename = "temp_input.wav"
        try:
            wf = wave.open(filename, 'wb')
            wf.setnchannels(self.channels)
            wf.setsampwidth(self.p.get_sample_size(self.audio_format))
            wf.setframerate(self.rate)
            wf.writeframes(b''.join(self.frames))
            wf.close()
            
            # Transcribe
            return self._transcribe_file(filename)
        except Exception as e:
            print(f"[SAVE ERR] {e}")
            return ""

    def _transcribe_file(self, filename):
        if self.model_loaded and self.whisper_model:
            try:
                # Use slightly more timeout/patience?
                result = self.whisper_model.transcribe(
                    filename, 
                    fp16=False, 
                    language='tr',
                    initial_prompt=STT_INITIAL_PROMPT,
                    temperature=0.0,
                    beam_size=7,
                    best_of=3,
                    condition_on_previous_text=True,
                    no_speech_threshold=0.5,
                )
                text = result['text'].strip()
                if os.path.exists(filename): os.remove(filename)
                return text
            except Exception as e:
                print(f"[STT ERR] Whisper Failed: {e}")
                return ""
        else:
            # Fallback
            try:
                with sr.AudioFile(filename) as source:
                    audio = self.r.record(source)
                    return self.r.recognize_google(audio, language="tr-TR")
            except Exception as e:
                print(f"[STT ERR] Google Failed: {e}")
                return ""

    def listen(self):
        # Legacy method (not used in Push-to-Talk)
        pass
# --- END FEATURE: jarvis_voice ---


if __name__ == "__main__":
    # Test
    voice = JarvisVoice()
    voice.speak("Sistem testi bir iki üç.")
    time.sleep(5) # Wait for thread

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
