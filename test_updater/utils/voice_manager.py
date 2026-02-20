import os
import re
import threading
import time
import pygame
from dotenv import load_dotenv
from elevenlabs import generate, stream, set_api_key

# Load Environment Variables
load_dotenv()

class VoiceManager:
    def __init__(self):
        self.api_key = os.getenv("ELEVENLABS_API_KEY")
        self.voice_id = os.getenv("ELEVENLABS_VOICE_ID", "Rachel") # Default voice
        self.enabled = False
        
        if self.api_key:
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

    def speak(self, text):
        if not self.enabled or not self.api_key:
            return

        # Clean text for TTS
        # 1. Remove Code Blocks
        clean_text = re.sub(r'```.*?```', ' Kod örneği ekranda mevcuttur. ', text, flags=re.DOTALL)
        
        # 2. Remove System Stats like [Hiz: ... | Sure: ...]
        clean_text = re.sub(r'\[Hiz:.*?\|.*?Sure:.*?\]', '', clean_text)
        
        # 3. Remove Image Markdown
        clean_text = re.sub(r'!\[.*?\]\(.*?\)', ' Görsel oluşturuldu. ', clean_text)
        
        # 4. Remove excessive symbols
        clean_text = clean_text.replace('*', '').replace('#', '').strip()
        
        if not clean_text: return

        # Threaded playback to avoid blocking UI
        threading.Thread(target=self._play_stream, args=(clean_text,), daemon=True).start()

    def _play_stream(self, text):
        try:
            # WINDOWS FIX: 
            # ElevenLabs 'stream=True' requires MPV. 
            # If MPV is missing, we use 'stream=False' (download bytes) and play with Pygame.
            
            try:
                # 1. Try Streaming (preferred for speed)
                audio_stream = generate(
                    text=text,
                    voice=self.voice_id,
                    model="eleven_multilingual_v2",
                    stream=True
                )
                stream(audio_stream)
                
            except Exception as stream_error:
                # print(f"Streaming Failed (likely MPV missing), falling back to download: {stream_error}")
                
                # 2. Fallback: Download Bytes & Pygame
                audio_bytes = generate(
                    text=text,
                    voice=self.voice_id,
                    model="eleven_multilingual_v2"
                )
                
                temp_file = f"temp_voice_{int(time.time())}.mp3"
                with open(temp_file, "wb") as f:
                    f.write(audio_bytes)
                    
                if not pygame.mixer.get_init():
                    pygame.mixer.init()
                    
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
