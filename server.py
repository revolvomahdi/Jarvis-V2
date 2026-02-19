import os
import uvicorn
import subprocess
import socket
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles # Added
from engines.manager import EngineManager

import sys
# Force UTF-8 for console output to support all languages/emojis
sys.stdout.reconfigure(encoding='utf-8')

import json
import glob
import json
import glob
import threading
from datetime import datetime

app = FastAPI()
beyin = EngineManager()

HISTORY_FILE = "data/chat_history.json"

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except: return []
    return []

def save_message(role, text):
    history = load_history()
    history.append({
        "role": role,
        "text": text,
        "timestamp": datetime.now().isoformat()
    })
    # Keep last 50 messages
    if len(history) > 50: history = history[-50:]
    
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

def archive_current_chat():
    if not os.path.exists(HISTORY_FILE): return
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not data: return # Empty
            
            # Create summary or title from first message
            summary = "New Chat"
            if len(data) > 0:
                summary = data[0].get("text", "")[:20].replace(" ", "_").replace(":", "")
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"data/archives/chat_{timestamp}_{summary}.json"
            
            # Ensure archives dir exists
            if not os.path.exists("data/archives"): os.makedirs("data/archives")
            
            with open(filename, "w", encoding="utf-8") as f_out:
                json.dump(data, f_out, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Archive Error: {e}")


# Mount Static Files (CSS, JS, Images)
# Allows serving files from web/static at /static URL path
if not os.path.exists("web/static"):
    os.makedirs("web/static")
app.mount("/static", StaticFiles(directory="web/static"), name="static")

# Check for templates folder
if not os.path.exists("templates"):
    os.makedirs("templates")
    # basic template if missing
    with open("templates/index.html", "w") as f:
        f.write("<h1>JARVIS AI STUDIO</h1>")

templates = Jinja2Templates(directory="templates")

def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try: s.connect(('10.255.255.255', 1)); IP = s.getsockname()[0]
    except: IP = '127.0.0.1'
    finally: s.close()
    return IP

@app.get("/", response_class=HTMLResponse)
async def anasayfa(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/favicon.ico")
async def favicon():
    return HTMLResponse("") # Dummy response to silence 404

@app.get("/get_history")
async def get_history():
    return load_history()

@app.get("/get_archives")
async def get_archives():
    try:
        if not os.path.exists("data/archives"): return []
        files = glob.glob("data/archives/*.json")
        # specific sort by date?
        files.sort(key=os.path.getmtime, reverse=True)
        # return list of {filename, title}
        results = []
        for f in files:
            # chat_20260211_220000_Hello_World.json
            basename = os.path.basename(f)
            # title is usually the part after timestamp
            # simple parsing
            results.append({"filename": basename, "path": f})
        return results
    except: return []

@app.post("/new_chat")
async def new_chat():
    # Archive first
    archive_current_chat()
    # Clear
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump([], f)
    return {"status": "ok"}

@app.post("/load_chat")
async def load_chat(filename: str = Form(...)):
    # Archive current first? Maybe user wants to save current state before switching.
    # For simplicity, we auto-archive current if it has data.
    archive_current_chat()
    
    target_path = os.path.join("data/archives", filename)
    if os.path.exists(target_path):
        with open(target_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # Overwrite active history
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return {"status": "loaded"}
    return {"status": "error"}

@app.post("/delete_chat")
async def delete_chat(filename: str = Form(...)):
    try:
        target_path = os.path.join("data/archives", filename)
        if os.path.exists(target_path):
            os.remove(target_path)
            return {"status": "deleted"}
        return {"status": "not_found"}
    except Exception as e:
        return {"status": f"error: {e}"}

@app.get("/get_settings")
async def get_settings():
    from utils.settings_manager import SettingsManager
    return SettingsManager().config

@app.post("/save_settings")
async def save_settings(
    theme: str = Form(...),
    language: str = Form(...),
    model: str = Form(...), # cloud vs local
    voice: str = Form("false"), # Voice Toggle
    voice_id: str = Form("") # New: Voice ID
):
    from utils.settings_manager import SettingsManager
    sm = SettingsManager()
    sm.set("theme", theme)
    sm.set("language", language)
    sm.set("engine_mode", model)
    
    # Parse voice boolean
    voice_bool = (voice.lower() == 'true')
    sm.set("audio_enabled", voice_bool)
    
    if voice_id:
        sm.set("elevenlabs_voice_id", voice_id)
    
    # Apply changes immediately where possible
    beyin.set_execution_mode(model)
    if hasattr(beyin, 'voice'):
        beyin.voice.set_enabled(voice_bool)
        if voice_id:
            beyin.voice.set_voice_id(voice_id)
        
    return {"status": "saved"}

# Global Progress State
CURRENT_PROGRESS = {"status": "idle", "percent": 0, "message": ""}

def update_progress_callback(percent, message=""):
    global CURRENT_PROGRESS
    CURRENT_PROGRESS["status"] = "generating" if percent < 100 else "idle"
    CURRENT_PROGRESS["percent"] = percent
    CURRENT_PROGRESS["message"] = message

@app.get("/get_progress")
async def get_progress():
    return CURRENT_PROGRESS

@app.post("/save_generated_image")
async def save_gen_image(image_url: str = Form(...)):
    """Opens a save dialog on the server side (Desktop App) to save the image."""
    try:
        import shutil
        import tkinter as tk
        from tkinter import filedialog
        
        # Clean URL to get local path
        # URL is like /static/generated_images/gen_....jpg
        if image_url.startswith("/"): image_url = image_url[1:]
        local_path = image_url.replace("/", os.sep)
        
        if not os.path.exists(local_path):
            # Fallback for web paths
            local_path = os.path.join("web", "static", "generated_images", os.path.basename(image_url))

        if not os.path.exists(local_path):
            return {"status": "error", "message": "File not found locally."}

        # Open Save Dialog
        root = tk.Tk()
        root.withdraw() # Hide main window
        root.attributes('-topmost', True) # Bring to front
        
        file_path = filedialog.asksaveasfilename(
            defaultextension=".jpg",
            filetypes=[("JPEG", "*.jpg"), ("PNG", "*.png"), ("All Files", "*.*")],
            initialfile=os.path.basename(local_path),
            title="Resmi Kaydet"
        )
        root.destroy()
        
        if file_path:
            shutil.copy2(local_path, file_path)
            return {"status": "ok", "path": file_path}
        else:
            return {"status": "cancelled"}
            
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/chat")
async def chat_yap(mesaj: str = Form(...), mod: str = Form(...)):
    try:
        print(f"Mobil: {mesaj} | Mod: {mod}")
    except:
        print(f"Mobil: {mesaj.encode('utf-8', 'ignore')} | Mod: {mod}")
        
    save_message("user", mesaj)
    
    # Konuşma geçmişini yükle (son user mesajı dahil)
    history = load_history()
    
    # Reset Progress
    global CURRENT_PROGRESS
    CURRENT_PROGRESS = {"status": "idle", "percent": 0, "message": "İşleniyor..."}
    
    try:
        if mod == "sohbet": 
            # Pass callback if supported
            cevap = beyin.chat_mode(mesaj, history=history, progress_callback=update_progress_callback)
        elif mod == "is": cevap = beyin.work_mode(mesaj)
        elif mod == "arastirma": cevap = beyin.research_mode(mesaj)
        else: cevap = beyin.chat_mode(mesaj, history=history, progress_callback=update_progress_callback)
        
        # FINAL SAFETY CHECK
        if cevap is None: cevap = "Üzgünüm, boş cevap döndü."
        if not isinstance(cevap, str): cevap = str(cevap)
            
    except Exception as e:
        print(f"Server Chat Error: {e}")
        cevap = f"Teknik bir hata oluştu: {e}"
        
    save_message("ai", cevap)
    return {"cevap": cevap}


@app.get("/system/test_agents")
async def test_agents_endpoint():
    try:
        # Check Mode
        if beyin.mode == "api":
             res = beyin.gemini.test_connection()
             return [{
                 "agent": "GEMINI CLOUD",
                 "model": res.get("model", "Unknown"),
                 "status": res.get("status", "FAIL"),
                 "msg": res.get("msg", ""),
                 "time": res.get("time", ""),
                 "response": res.get("response", "")
             }]
        else:
            # Local Mode
            report = beyin.local_brain.test_agents()
            return report
            
    except Exception as e:
        return [{"agent": "SERVER ERROR", "status": "FAIL", "msg": str(e)}]


@app.post("/unlock")
async def kilit_ac():
    print("KILIT ACILIYOR (TASK SCHEDULER MODE)...")
    komut = 'schtasks /Run /TN "NASA_Unlock"'
    try:
        subprocess.Popen(komut, shell=True)
        return {"durum": "Kilit Acma Sinyali Gonderildi"}
    except Exception as e:
        return {"durum": f"Hata: {e}"}

@app.post("/set_model")
async def model_degis(mod: str = Form(...)):
    try:
        print(f"Model Değişiyor: {mod}")
    except: pass
    if mod == "cloud":
        beyin.set_execution_mode("api")
        return {"current": "Seyit 3.0 (Cloud)"}
    else:
        beyin.set_execution_mode("local") 
        return {"current": "Yerel (Ollama)"}

@app.post("/media")
async def medya_kontrol(komut: str = Form(...)):
    if komut == "playpause":
        # Simulate Media Key
        vbs = 'Set WshShell = CreateObject("WScript.Shell") : WshShell.SendKeys(chr(178))'
        subprocess.call(['cscript', '//nologo', '//E:vbscript', '/c', vbs], shell=True)
    return {"durum": "Medya"}

@app.post("/system/restart")
async def restart_system():
    print("UYGULAMA YENİDEN BAŞLATILIYOR...")
    
    # Trigger restart in a separate thread/process to allow response to return
    def restart_process():
        import time
        import sys
        
        # Wait a moment for response to send
        time.sleep(1)
        
        # Reload
        python = sys.executable
        os.execl(python, python, *sys.argv)
        
    threading.Thread(target=restart_process).start()
    return {"status": "restarting"}

if __name__ == "__main__":
    ip = get_ip()
    print(f"\nNASA MOBIL SERVER (v0.4 Hybrid) BASLATILDI")
    print(f"http://{ip}:8000")
    print(f"Bu pencereyi kapatmayin.\n")
    uvicorn.run(app, host="0.0.0.0", port=8000)