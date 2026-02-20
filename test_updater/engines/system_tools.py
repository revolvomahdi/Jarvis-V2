import os
import shutil
import subprocess
import pyautogui
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime
from duckduckgo_search import DDGS

class SystemManager:
    def __init__(self):
        self.user_profile = os.path.expanduser("~")
        self.onedrive = os.path.join(self.user_profile, "OneDrive")
        self.has_onedrive = os.path.exists(self.onedrive)
        self.default_path = os.path.join(self.onedrive, "Desktop") if self.has_onedrive else os.path.join(self.user_profile, "Desktop")
        self.context_path = self.default_path
        self.last_created_path = None 

    def get_path(self, keyword):
        k = keyword.lower()
        if "belge" in k or "doc" in k: return os.path.join(self.onedrive, "Documents") if self.has_onedrive else os.path.join(self.user_profile, "Documents")
        elif "resim" in k or "pic" in k: return os.path.join(self.onedrive, "Pictures") if self.has_onedrive else os.path.join(self.user_profile, "Pictures")
        elif "indir" in k or "down" in k: return os.path.join(self.user_profile, "Downloads")
        elif "masaüst" in k: return self.default_path
        else: return self.default_path

    def resolve_path(self, message):
        message = message.lower()
        # Disk detection
        disk = re.search(r'\b([a-z]):', message)
        if disk:
            drive = disk.group(1).upper()
            path = f"{drive}:\\"
            if os.path.exists(path):
                self.context_path = path
                return path
        
        path = self.context_path
        if "belge" in message: path = self.get_path("belge")
        elif "resim" in message: path = self.get_path("resim")
        elif "indir" in message: path = self.get_path("indir")
        elif "masaüst" in message: path = self.get_path("masaüst")
        
        self.context_path = path
        return path

class WebTools:
    def __init__(self):
        self.blacklist = [
            "facebook.com", "instagram.com", "twitter.com", "pinterest", 
            "google.com/store", "apps.apple.com", "youtube.com", "tiktok.com"
        ]

    def read_url(self, url):
        if any(b in url for b in self.blacklist): return ""
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(url, headers=headers, timeout=4)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                # Try to get main content
                paragraphs = soup.find_all('p')
                text = " ".join([p.get_text() for p in paragraphs])
                return text[:5000] # Limit content
            return ""
        except: return ""

    def search(self, query):
        results = []
        try:
            with DDGS() as ddgs:
                # Get more results for better context
                for r in ddgs.text(query, region="tr-tr", timelimit="y", max_results=5):
                    results.append(r)
        except Exception as e:
            print(f"Search Error: {e}")
        return results

class ScreenTools:
    @staticmethod
    def take_screenshot(path="screen_analysis.jpg"):
        try:
            full_path = os.path.join(os.getcwd(), path)
            pyautogui.screenshot().save(full_path)
            return full_path
        except Exception as e:
            print(f"Screenshot error: {e}")
            return None
