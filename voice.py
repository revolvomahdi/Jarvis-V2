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
WHISPER_MODEL_SIZE = "base" # tiny, base, small, medium, large

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

    async def _speech_worker_async(self):
        """Processes TTS queue using Edge TTS"""
        while self.is_running:
            try:
                # Poll the queue
                if not self.speech_queue.empty():
                    text = self.speech_queue.get()
                    if text:
                        print(f"[SAY] {text}")
                        # Try Online EdgeTTS First
                        success = False
                        try:
                            output_file = "temp_speech.mp3"
                            # Ensure clean state
                            if os.path.exists(output_file): os.remove(output_file)
                            
                            communicate = edge_tts.Communicate(text, TTS_VOICE)
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
                            self._speak_fallback(text)
                    
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
                result = self.whisper_model.transcribe(filename, fp16=False, language='tr')
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


if __name__ == "__main__":
    # Test
    voice = JarvisVoice()
    voice.speak("Sistem testi bir iki üç.")
    time.sleep(5) # Wait for thread

