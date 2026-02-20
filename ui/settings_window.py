import customtkinter as ctk
import threading
import ollama
from ui.components import NASAProgressBar, ModernButton
from ui.styles import *
from utils.settings_manager import SettingsManager
from utils.localization import Localizer

class SettingsWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("NASA AI - CONFIG")
        self.geometry("700x650")
        self.configure(fg_color="#181818")
        self.resizable(False, False)
        
        # Make modal/topmost
        self.transient(parent)
        self.grab_set()
        self.focus_force()
        self.attributes("-topmost", True)
        
        self.settings = SettingsManager()
        self.localizer = Localizer(self.settings.get("language"))
        
        # Tabs
        self.tabview = ctk.CTkTabview(self, width=660, height=600, fg_color="#1e1e1e")
        self.tabview.pack(padx=20, pady=20)
        
        self.tab_gen = self.tabview.add(self._t("ui.settings.tab_general"))
        self.tab_mod = self.tabview.add(self._t("ui.settings.tab_models"))
        
        self._build_general_tab()
        self._build_models_tab()

    def _t(self, key):
        text = self.localizer.get(key)
        return text if text else key
        
    def _build_general_tab(self):
        # API Key
        ctk.CTkLabel(self.tab_gen, text=self._t("ui.settings.api_key"), font=("Roboto", 14, "bold"), text_color="white").pack(pady=(20,5), anchor="w", padx=20)
        self.entry_apikey = ctk.CTkEntry(self.tab_gen, width=400, height=35, placeholder_text="AIza...")
        self.entry_apikey.insert(0, self.settings.get("gemini_api_key", ""))
        self.entry_apikey.pack(pady=5, padx=20, anchor="w")
        
        # Audio Toggle
        self.var_audio = ctk.BooleanVar(value=self.settings.get("audio_enabled", True))
        self.switch_audio = ctk.CTkSwitch(
            self.tab_gen, 
            text=self._t("ui.settings.audio_toggle"), # Localized
            variable=self.var_audio, 
            onvalue=True, 
            offvalue=False,
            progress_color=ACCENT_CYAN,
            font=("Roboto", 13)
        )
        self.switch_audio.pack(pady=25, padx=20, anchor="w")
        
        # Language
        ctk.CTkLabel(self.tab_gen, text=self._t("ui.settings.language"), font=("Roboto", 14, "bold"), text_color="white").pack(pady=(10,5), anchor="w", padx=20)
        self.combo_lang = ctk.CTkOptionMenu(self.tab_gen, values=["tr", "en"], fg_color="#2d3436", button_color=ACCENT_CYAN)
        self.combo_lang.set(self.settings.get("language", "tr"))
        self.combo_lang.pack(pady=5, padx=20, anchor="w")
        
        # Save Button
        ModernButton(self.tab_gen, text=self._t("ui.settings.btn_save"), command=self.save_settings).pack(pady=50, padx=20, fill="x")
        
    def _build_models_tab(self):
        # Engine Mode
        ctk.CTkLabel(self.tab_mod, text=self._t("ui.settings.engine_mode"), font=("Roboto", 14, "bold"), text_color="white").pack(pady=(20,10), anchor="w", padx=20)
        
        self.var_engine = ctk.StringVar(value=self.settings.get("engine_mode", "api"))
        
        ctk.CTkRadioButton(self.tab_mod, text=self._t("ui.settings.engine_api"), variable=self.var_engine, value="api", font=("Roboto", 12)).pack(pady=5, padx=20, anchor="w")
        ctk.CTkRadioButton(self.tab_mod, text=self._t("ui.settings.engine_local"), variable=self.var_engine, value="local", font=("Roboto", 12)).pack(pady=5, padx=20, anchor="w")
        
        # Divider
        ctk.CTkFrame(self.tab_mod, height=2, fg_color="#333").pack(fill="x", padx=20, pady=20)
        
        # Local Models Config
        ctk.CTkLabel(self.tab_mod, text="Ollama (Local AI)", font=("Roboto", 14, "bold"), text_color="white").pack(pady=(0,10), anchor="w", padx=20)
        
        # Check Status
        self.lbl_ollama_status = ctk.CTkLabel(self.tab_mod, text="Status: Unknown", font=("Roboto", 12))
        self.lbl_ollama_status.pack(padx=20, anchor="w")
        
        ctk.CTkButton(
            self.tab_mod, 
            text=self._t("ui.settings.ollama_check"), 
            height=28, 
            width=120,
            fg_color="#444", 
            command=self.check_ollama
        ).pack(padx=20, anchor="w", pady=10)
        
        # Download Section
        ctk.CTkLabel(self.tab_mod, text=self._t("ui.settings.ollama_placeholder"), font=("Roboto", 12)).pack(pady=(15,5), anchor="w", padx=20)
        
        row_frame = ctk.CTkFrame(self.tab_mod, fg_color="transparent")
        row_frame.pack(fill="x", padx=20, pady=5)
        
        self.entry_model = ctk.CTkEntry(row_frame, width=250, placeholder_text="llama3")
        self.entry_model.insert(0, self.settings.get("local_models", {}).get("chat", "llama3"))
        self.entry_model.pack(side="left")
        
        ctk.CTkButton(
            row_frame, 
            text=self._t("ui.settings.ollama_pull"), 
            width=130, 
            fg_color=ACCENT_CYAN,
            text_color="white",
            command=self.pull_model
        ).pack(side="left", padx=10)
        
        # Progress Bar
        self.progress_bar = NASAProgressBar(self.tab_mod)
        self.progress_bar.pack(fill="x", padx=20, pady=(20, 5))
        self.progress_bar.set(0)
        
        self.lbl_progress = ctk.CTkLabel(self.tab_mod, text="")
        self.lbl_progress.pack(pady=5)

    def check_ollama(self):
        try:
            ollama.list()
            self.lbl_ollama_status.configure(text="Status: ✅ Ollama Online", text_color="#2ecc71")
        except:
            self.lbl_ollama_status.configure(text="Status: ❌ Offline / Not Installed", text_color="#e74c3c")

    def pull_model(self):
        model_name = self.entry_model.get().strip()
        if not model_name: return
        
        self.progress_bar.set(0)
        self.lbl_progress.configure(text=f"Pulling {model_name}...")
        
        threading.Thread(target=self._pull_worker, args=(model_name,), daemon=True).start()
        
    def _pull_worker(self, model_name):
        try:
            for progress in ollama.pull(model_name, stream=True):
                status = progress.get('status', '')
                # Ollama returns explicit total/completed for download, but sometimes just status
                total = progress.get('total', 0)
                completed = progress.get('completed', 0)
                
                if total > 0:
                    val = completed / total
                    try:
                        self.progress_bar.set(val)
                        self.lbl_progress.configure(text=f"{status}: {int(val*100)}%")
                    except: pass
                else:
                    try:
                        self.lbl_progress.configure(text=status)
                    except: pass
            
            self.lbl_progress.configure(text="✅ Done!", text_color="#2ecc71")
            self.progress_bar.set(1)
        except Exception as e:
            self.lbl_progress.configure(text=f"Error: {e}", text_color="#e74c3c")

    def save_settings(self):
        new_key = self.entry_apikey.get().strip()
        new_lang = self.combo_lang.get()
        new_engine = self.var_engine.get()
        new_audio = self.var_audio.get()
        new_model = self.entry_model.get().strip()
        
        self.settings.set("gemini_api_key", new_key)
        self.settings.set("language", new_lang)
        self.settings.set("engine_mode", new_engine)
        self.settings.set("audio_enabled", new_audio)
        
        current_models = self.settings.get("local_models")
        if not current_models: current_models = {}
        current_models["chat"] = new_model
        self.settings.set("local_models", current_models)
        
        self.destroy()
