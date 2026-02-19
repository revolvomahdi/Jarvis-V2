import customtkinter as ctk
from ui.styles import *

class ChatBubble(ctk.CTkFrame):
    def __init__(self, master, text, is_user=False, **kwargs):
        # Determine Color
        # User: Dark Bubble (#2f2f2f), AI: Transparent/Background
        color = INPUT_BG if is_user else "transparent"
        
        # Determine Alignment
        anchor = "e" if is_user else "w"
        
        super().__init__(master, fg_color=color, corner_radius=15, **kwargs)
        
        # Max width logic can be improved but fixed wrap is okay for now
        self.label = ctk.CTkLabel(
            self, 
            text=text, 
            font=("Inter", 14), # Matches CSS font
            text_color="white", 
            wraplength=600, 
            justify="left"
        )
        self.label.pack(padx=15, pady=10)

class NASAProgressBar(ctk.CTkProgressBar):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.configure(progress_color=ACCENT_CYAN, fg_color=INPUT_BG)
        self.set(0)

class ModernButton(ctk.CTkButton):
    def __init__(self, master, text, command, **kwargs):
        super().__init__(
            master, 
            text=text, 
            command=command, 
            corner_radius=8,
            fg_color=ACCENT_CYAN,
            hover_color="#01a3a4",
            text_color="black", # Text on cyan should be dark
            font=("Roboto", 13, "bold"),
            **kwargs
        )
