from abc import ABC, abstractmethod

# --- FEATURE: base_engine ---
class BaseEngine(ABC):
    @abstractmethod
    def generate_response(self, prompt, system_instruction=None, history=[], images=[]):
        pass

    @abstractmethod
    def generate_stream(self, prompt, system_instruction=None, history=[], images=[]):
        pass
# --- END FEATURE: base_engine ---

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
