import asyncio
import edge_tts
import pygame
import os

TEXT = "Merhaba, bu bir ses denemesidir."
VOICE = "tr-TR-AhmetNeural"
OUTPUT = "test.mp3"

# --- FEATURE: main ---
async def main():
    print(f"Generating audio with voice: {VOICE}")
    try:
        comm = edge_tts.Communicate(TEXT, VOICE)
        await comm.save(OUTPUT)
        print(f"Saved to {OUTPUT}")
    except Exception as e:
        print(f"Error generating TTS: {e}")
        return

    print("Playing audio...")
    try:
        pygame.mixer.init()
        pygame.mixer.music.load(OUTPUT)
        pygame.mixer.music.play()
        
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)
            
        pygame.mixer.quit()
        print("Playback finished.")
    except Exception as e:
        print(f"Error playing audio: {e}")
# --- END FEATURE: main ---

if __name__ == "__main__":
    asyncio.run(main())

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
