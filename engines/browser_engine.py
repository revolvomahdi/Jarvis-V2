"""
Browser Engine - Playwright tabanli universal tarayici kontrol motoru.
Chromium, Firefox, WebKit destekler.
Sahte imlec koordinatlari overlay'e bildirilir.
"""

import os
import sys
import json
import time
import subprocess
import threading

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


def ensure_playwright_installed():
    """Playwright ve tarayici binary'lerini otomatik yukler."""
    global PLAYWRIGHT_AVAILABLE
    
    if PLAYWRIGHT_AVAILABLE:
        # Binary kontrol
        try:
            from playwright.sync_api import sync_playwright
            pw = sync_playwright().start()
            br = pw.chromium.launch(headless=True)
            br.close()
            pw.stop()
            return True
        except Exception:
            pass
    
    print("[BROWSER] Playwright kuruluyor...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "playwright", "-q"])
        subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"])
        
        # Reload module
        import importlib
        if "playwright" in sys.modules:
            importlib.reload(sys.modules["playwright"])
        from playwright.sync_api import sync_playwright
        PLAYWRIGHT_AVAILABLE = True
        print("[BROWSER] Playwright basariyla kuruldu.")
        return True
    except Exception as e:
        print(f"[BROWSER] Playwright kurulum hatasi: {e}")
        return False


class BrowserEngine:
    """Playwright tabanli tarayici kontrol motoru."""
    
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.is_active = False
        self.overlay = None  # BrowserOverlay referansi
        self._lock = threading.Lock()
    
    def set_overlay(self, overlay):
        """Overlay referansini ayarla."""
        self.overlay = overlay
    
    def launch(self, browser_type="chromium", headless=False):
        """Tarayiciyi baslat."""
        if not PLAYWRIGHT_AVAILABLE:
            if not ensure_playwright_installed():
                raise RuntimeError("Playwright yuklenemedi!")
        
        from playwright.sync_api import sync_playwright
        
        with self._lock:
            if self.is_active:
                return True
            
            self.playwright = sync_playwright().start()
            
            # Tarayici secimi
            if browser_type == "firefox":
                launcher = self.playwright.firefox
            elif browser_type == "webkit":
                launcher = self.playwright.webkit
            else:
                launcher = self.playwright.chromium
            
            self.browser = launcher.launch(
                headless=headless,
                args=[
                    "--start-maximized",
                    "--disable-blink-features=AutomationControlled",
                ]
            )
            
            self.context = self.browser.new_context(
                viewport=None,  # Tam ekran
                no_viewport=True,
            )
            
            self.page = self.context.new_page()
            self.is_active = True
            
            # Overlay'i aktif et
            if self.overlay:
                self.overlay.show()
            
            print("[BROWSER] Tarayici baslatildi.")
            return True
    
    def goto(self, url):
        """Sayfaya git."""
        if not self.is_active:
            self.launch()
        
        # URL duzeltme
        if not url.startswith("http"):
            url = "https://" + url
        
        self.page.goto(url, wait_until="domcontentloaded", timeout=15000)
        time.sleep(0.5)
        return True
    
    def get_element_position(self, selector):
        """Elementin ekran koordinatlarini dondur."""
        try:
            element = self.page.wait_for_selector(selector, timeout=5000)
            if element:
                box = element.bounding_box()
                if box:
                    # Merkez koordinat
                    x = box["x"] + box["width"] / 2
                    y = box["y"] + box["height"] / 2
                    return (int(x), int(y))
        except Exception as e:
            print(f"[BROWSER] Element bulunamadi: {selector} -> {e}")
        return None
    
    def _move_cursor_to(self, x, y):
        """Sahte imleci hedefe hareket ettir."""
        if self.overlay:
            self.overlay.smooth_move(x, y)
    
    def _click_animation(self):
        """Tiklama animasyonu goster."""
        if self.overlay:
            self.overlay.click_pulse()
    
    def click(self, selector):
        """Elemente tikla — sahte imlec ile gorsel efekt."""
        if not self.is_active:
            return False
        
        pos = self.get_element_position(selector)
        if pos:
            self._move_cursor_to(pos[0], pos[1])
            self._click_animation()
        
        try:
            self.page.click(selector, timeout=5000)
            time.sleep(0.3)
            return True
        except Exception as e:
            print(f"[BROWSER] Click hatasi: {e}")
            return False
    
    def type_text(self, selector, text, delay=50):
        """Elemente yazi yaz — sahte imlec hedefe gider, karakter karakter yazar."""
        if not self.is_active:
            return False
        
        pos = self.get_element_position(selector)
        if pos:
            self._move_cursor_to(pos[0], pos[1])
            self._click_animation()
        
        try:
            self.page.click(selector, timeout=5000)
            time.sleep(0.2)
            self.page.type(selector, text, delay=delay)
            return True
        except Exception as e:
            print(f"[BROWSER] Type hatasi: {e}")
            return False
    
    def press_key(self, key):
        """Tus bas (Enter, Tab, Escape vb.)."""
        if not self.is_active:
            return False
        try:
            self.page.keyboard.press(key)
            time.sleep(0.3)
            return True
        except Exception as e:
            print(f"[BROWSER] Key press hatasi: {e}")
            return False
    
    def scroll(self, direction="down", amount=300):
        """Sayfa scroll."""
        if not self.is_active:
            return False
        try:
            delta = amount if direction == "down" else -amount
            self.page.mouse.wheel(0, delta)
            time.sleep(0.3)
            return True
        except Exception as e:
            print(f"[BROWSER] Scroll hatasi: {e}")
            return False
    
    def screenshot(self):
        """Ekran goruntusu al — PIL Image dondurur."""
        if not self.is_active:
            return None
        try:
            screenshot_bytes = self.page.screenshot(type="jpeg", quality=70)
            from PIL import Image
            import io
            return Image.open(io.BytesIO(screenshot_bytes))
        except Exception as e:
            print(f"[BROWSER] Screenshot hatasi: {e}")
            return None
    
    def screenshot_base64(self):
        """Screenshot'i base64 olarak dondur (LLM'e gondermek icin)."""
        if not self.is_active:
            return None
        try:
            import base64
            screenshot_bytes = self.page.screenshot(type="jpeg", quality=60)
            return base64.b64encode(screenshot_bytes).decode("utf-8")
        except Exception:
            return None
    
    def get_page_content(self):
        """Sayfa metnini al (ozet icin)."""
        if not self.is_active:
            return ""
        try:
            return self.page.inner_text("body")[:3000]
        except:
            return ""
    
    def get_page_title(self):
        """Sayfa basligini al."""
        if not self.is_active:
            return ""
        try:
            return self.page.title()
        except:
            return ""
    
    def get_current_url(self):
        """Mevcut URL."""
        if not self.is_active:
            return ""
        try:
            return self.page.url
        except:
            return ""
    
    def wait(self, seconds=1):
        """Bekle."""
        time.sleep(seconds)
    
    def execute_plan(self, actions):
        """
        JSON aksiyon listesini sirayla calistir.
        Her aksiyon: {"action": "goto|click|type|press|scroll|wait|screenshot_check", ...}
        Dondurulen: {"success": True/False, "steps_completed": N, "error": str}
        """
        results = []
        
        for i, action in enumerate(actions):
            act = action.get("action", "")
            success = False
            error = ""
            
            try:
                if act == "goto":
                    success = self.goto(action.get("url", ""))
                
                elif act == "click":
                    success = self.click(action.get("selector", ""))
                
                elif act == "type":
                    sel = action.get("selector", "")
                    text = action.get("text", "")
                    success = self.type_text(sel, text)
                
                elif act == "press":
                    success = self.press_key(action.get("key", "Enter"))
                
                elif act == "scroll":
                    direction = action.get("direction", "down")
                    amount = action.get("amount", 300)
                    success = self.scroll(direction, amount)
                
                elif act == "wait":
                    self.wait(action.get("seconds", 1))
                    success = True
                
                elif act == "screenshot_check":
                    # Bu adim disaridan islenir (vision model)
                    success = True
                
                else:
                    error = f"Bilinmeyen aksiyon: {act}"
                
            except Exception as e:
                error = str(e)
            
            results.append({
                "step": i,
                "action": act,
                "success": success,
                "error": error
            })
            
            if not success and error:
                print(f"[BROWSER] Adim {i} basarisiz: {act} -> {error}")
                # Devam et, durma
        
        return {
            "success": all(r["success"] for r in results),
            "steps_completed": len([r for r in results if r["success"]]),
            "total_steps": len(actions),
            "results": results
        }
    
    def close(self):
        """Tarayiciyi kapat."""
        with self._lock:
            if self.overlay:
                self.overlay.hide()
            
            try:
                if self.page:
                    self.page.close()
                if self.context:
                    self.context.close()
                if self.browser:
                    self.browser.close()
                if self.playwright:
                    self.playwright.stop()
            except:
                pass
            
            self.page = None
            self.context = None
            self.browser = None
            self.playwright = None
            self.is_active = False
            print("[BROWSER] Tarayici kapatildi.")
