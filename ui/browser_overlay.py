"""
Browser Overlay - Seffaf Win32 penceresi uzerinde:
- Sahte AI imleci (siyah, beyaz dis hat, buyuk)
- Mavi gradient cerceve (tarayici etrafinda)
- Bezier curve ile smooth hareket
- Tiklama pulse efekti
"""

import threading
import time
import math
import sys

# Windows-only overlay
if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes
    import ctypes.wintypes
    
    # Win32 constants
    WS_EX_LAYERED = 0x80000
    WS_EX_TRANSPARENT = 0x20
    WS_EX_TOPMOST = 0x8
    WS_EX_TOOLWINDOW = 0x80
    WS_POPUP = 0x80000000
    WS_VISIBLE = 0x10000000
    LWA_COLORKEY = 0x1
    LWA_ALPHA = 0x2
    GWL_EXSTYLE = -20
    SW_SHOW = 5
    SW_HIDE = 0
    
    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32
    kernel32 = ctypes.windll.kernel32


def bezier_points(start, end, steps=30):
    """
    Bezier curve ile iki nokta arasi yumusak hareket.
    Control point: ortanin biraz ustunde (dogal hareket icin).
    """
    sx, sy = start
    ex, ey = end
    
    # Control point — hafif kavisli yol
    cx = (sx + ex) / 2 + (ey - sy) * 0.1
    cy = (sy + ey) / 2 - abs(ex - sx) * 0.1
    
    points = []
    for i in range(steps + 1):
        t = i / steps
        # Ease-in-out
        t = t * t * (3 - 2 * t)
        
        x = (1 - t) ** 2 * sx + 2 * (1 - t) * t * cx + t ** 2 * ex
        y = (1 - t) ** 2 * sy + 2 * (1 - t) * t * cy + t ** 2 * ey
        points.append((int(x), int(y)))
    
    return points


class BrowserOverlay:
    """
    Seffaf overlay — sahte AI imleci ve mavi cerceve gosterir.
    Ayri thread'de calisir, ana programi bloklamaz.
    """
    
    def __init__(self):
        self.cursor_x = 400
        self.cursor_y = 400
        self.target_x = 400
        self.target_y = 400
        self.visible = False
        self.click_pulse_active = False
        self.click_pulse_size = 0
        self.border_opacity = 200
        self.border_phase = 0
        
        # Thread-safe
        self._lock = threading.Lock()
        self._thread = None
        self._running = False
        
        # Overlay penceresi (tkinter fallback)
        self._canvas = None
        self._root = None
        self._use_tkinter = True  # Daha stabil
    
    def show(self):
        """Overlay'i goster — ayri thread'de."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_overlay, daemon=True)
        self._thread.start()
    
    def hide(self):
        """Overlay'i gizle."""
        self._running = False
        self.visible = False
        if self._root:
            try:
                self._root.after(0, self._root.destroy)
            except:
                pass
    
    def smooth_move(self, target_x, target_y):
        """Imleci hedefe bezier curve ile hareket ettir."""
        with self._lock:
            start = (self.cursor_x, self.cursor_y)
            end = (target_x, target_y)
        
        points = bezier_points(start, end, steps=25)
        
        for px, py in points:
            with self._lock:
                self.cursor_x = px
                self.cursor_y = py
            time.sleep(0.016)  # ~60fps
        
        with self._lock:
            self.cursor_x = target_x
            self.cursor_y = target_y
    
    def click_pulse(self):
        """Tiklama pulse efekti — imlec kucukup buyur."""
        self.click_pulse_active = True
        self.click_pulse_size = 0
        
        # Pulse animasyonu
        for i in range(10):
            self.click_pulse_size = int(8 * math.sin(i * math.pi / 10))
            time.sleep(0.025)
        
        self.click_pulse_active = False
        self.click_pulse_size = 0
    
    def _run_overlay(self):
        """Overlay ana dongusu — tkinter ile seffaf pencere."""
        try:
            import tkinter as tk
        except ImportError:
            print("[OVERLAY] tkinter bulunamadi, overlay devre disi.")
            self._running = False
            return
        
        self._root = tk.Tk()
        self._root.title("AI_Overlay")
        
        # Tam ekran + seffaf
        screen_w = self._root.winfo_screenwidth()
        screen_h = self._root.winfo_screenheight()
        self._root.geometry(f"{screen_w}x{screen_h}+0+0")
        self._root.overrideredirect(True)
        self._root.attributes("-topmost", True)
        self._root.attributes("-transparentcolor", "#010101")
        self._root.config(bg="#010101")
        
        # Mouse tiklama gecirgen (click-through)
        if sys.platform == "win32":
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            # Pencere handle'ini bul
            self._root.update_idletasks()
            hwnd = int(self._root.frame(), 16)
            try:
                ex_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
                user32.SetWindowLongW(hwnd, GWL_EXSTYLE, 
                    ex_style | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOPMOST)
            except:
                pass
        
        self._canvas = tk.Canvas(
            self._root, 
            width=screen_w, 
            height=screen_h, 
            bg="#010101", 
            highlightthickness=0
        )
        self._canvas.pack()
        
        self.visible = True
        self._draw_loop()
        
        try:
            self._root.mainloop()
        except:
            pass
    
    def _draw_loop(self):
        """Her karede imlec ve cerceve ciz."""
        if not self._running or not self._canvas:
            return
        
        canvas = self._canvas
        canvas.delete("all")
        
        with self._lock:
            cx, cy = self.cursor_x, self.cursor_y
        
        # --- AI IMLEC ---
        # Boyut (normal imleçten 1.5x buyuk)
        size = 20
        if self.click_pulse_active:
            size = 20 - self.click_pulse_size
        
        # Ok seklinde imlec (pointer)
        # Ana govde — siyah dolu
        points_cursor = [
            cx, cy,                         # Uc nokta
            cx + size * 0.35, cy + size,    # Sag alt
            cx + size * 0.12, cy + size * 0.7,  # Ic kirilma
            cx + size * 0.5, cy + size * 1.2,   # Sag uzanti
            cx + size * 0.35, cy + size * 1.3,  # Sag uzanti alt
            cx + size * 0.05, cy + size * 0.85, # Ic kirilma 2
            cx - size * 0.1, cy + size * 0.95,  # Sol alt
        ]
        
        # Beyaz dis hat (3px)
        canvas.create_polygon(
            points_cursor,
            fill="black",
            outline="white",
            width=2,
            smooth=False
        )
        
        # Tiklama efekti — daire
        if self.click_pulse_active and self.click_pulse_size > 0:
            r = self.click_pulse_size + 10
            canvas.create_oval(
                cx - r, cy - r, cx + r, cy + r,
                outline="#00AAFF",
                width=2
            )
        
        # --- MAVI CERCEVE (tarayici etrafinda) ---
        self.border_phase = (self.border_phase + 2) % 360
        
        # Ekranin kenarlarinda gradient mavi hat
        sw = canvas.winfo_width()
        sh = canvas.winfo_height()
        border_w = 3
        
        # Ust
        for i in range(border_w):
            alpha_hex = self._gradient_color(i, border_w)
            canvas.create_line(0, i, sw, i, fill=alpha_hex, width=1)
        # Alt
        for i in range(border_w):
            alpha_hex = self._gradient_color(i, border_w)
            canvas.create_line(0, sh - i, sw, sh - i, fill=alpha_hex, width=1)
        # Sol
        for i in range(border_w):
            alpha_hex = self._gradient_color(i, border_w)
            canvas.create_line(i, 0, i, sh, fill=alpha_hex, width=1)
        # Sag
        for i in range(border_w):
            alpha_hex = self._gradient_color(i, border_w)
            canvas.create_line(sw - i, 0, sw - i, sh, fill=alpha_hex, width=1)
        
        # Sonraki kare — ~30fps
        if self._running:
            self._root.after(33, self._draw_loop)
    
    def _gradient_color(self, index, total):
        """Animasyonlu mavi gradient renk uret."""
        phase = self.border_phase + index * 30
        r = int(0 + 30 * math.sin(math.radians(phase)))
        g = int(100 + 50 * math.sin(math.radians(phase + 120)))
        b = int(200 + 55 * math.sin(math.radians(phase + 240)))
        
        r = max(0, min(255, r))
        g = max(0, min(255, g))
        b = max(0, min(255, b))
        
        return f"#{r:02x}{g:02x}{b:02x}"
