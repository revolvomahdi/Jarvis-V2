import customtkinter as ctk
import threading
import sys
import os

sys.path.append(os.getcwd())
from engines.manager import EngineManager

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class MiniAsistan(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        # Window setup
        self.overrideredirect(True)
        self.attributes('-topmost', True) 
        self.attributes('-alpha', 0.90)
        self.geometry("500x140")
        self.configure(fg_color="#181818")
        
        self.brain = EngineManager()

        # Dragging
        self.bind("<ButtonPress-1>", self.start_move)
        self.bind("<ButtonRelease-1>", self.stop_move)
        self.bind("<B1-Motion>", self.do_move)

        # UI
        self.top = ctk.CTkFrame(self, height=24, fg_color="#222")
        self.top.pack(fill="x")
        
        ctk.CTkLabel(self.top, text="NASA AI Mini", font=("Arial", 10, "bold"), text_color="gray").pack(side="left", padx=10)
        ctk.CTkButton(self.top, text="X", width=20, height=20, fg_color="transparent", hover_color="red", command=self.destroy).pack(side="right")

        self.lbl_res = ctk.CTkLabel(self, text="...", font=("Consolas", 12), text_color="#00d2d3", wraplength=480, justify="left")
        self.lbl_res.pack(pady=5, padx=10, fill="x")

        self.entry = ctk.CTkEntry(self, placeholder_text="Command...", border_width=0, fg_color="#333", text_color="white")
        self.entry.pack(side="bottom", fill="x", padx=10, pady=10)
        self.entry.bind("<Return>", self.on_send)

    def start_move(self, event): self.x = event.x; self.y = event.y
    def stop_move(self, event): self.x = None; self.y = None
    def do_move(self, event):
        x = self.winfo_x() + event.x - self.x
        y = self.winfo_y() + event.y - self.y
        self.geometry(f"+{x}+{y}")

    def on_send(self, event=None):
        msg = self.entry.get()
        if not msg: return
        self.entry.delete(0, "end")
        self.lbl_res.configure(text="Processing...", text_color="orange")
        threading.Thread(target=self.process, args=(msg,)).start()

    def process(self, msg):
        try:
            # Detect mode by prefix
            if msg.startswith("/a"): res = self.brain.research_mode(msg)
            elif msg.startswith("/s"): res = self.brain.chat_mode(msg)
            else: res = self.brain.work_mode(msg) # Default working mode for mini
            
            # Truncate
            disp = res[:200] + "..." if len(res) > 200 else res
            self.lbl_res.configure(text=disp, text_color="white")
        except Exception as e:
            self.lbl_res.configure(text=f"Error: {e}", text_color="red")

if __name__ == "__main__":
    app = MiniAsistan()
    app.mainloop()