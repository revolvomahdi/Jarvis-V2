import json
import os
import re
import threading

class MemoryManager:
    def __init__(self, directory="data"):
        self.directory = directory
        self.memory_file = os.path.join(directory, "long_memory.json")
        self.profile_file = os.path.join(directory, "user_profile.json")
        self.context_file = os.path.join(directory, "session_context.json")
        self.ensure_files()
        
    def ensure_files(self):
        if not os.path.exists(self.directory): os.makedirs(self.directory)
        if not os.path.exists(self.memory_file): 
            with open(self.memory_file, "w", encoding="utf-8") as f: json.dump({"facts": [], "summaries": []}, f)
        if not os.path.exists(self.profile_file):
            with open(self.profile_file, "w", encoding="utf-8") as f: 
                json.dump(self._empty_profile(), f, ensure_ascii=False, indent=2)

    def _empty_profile(self):
        return {
            "identity": {},      # ad, soyad, lakap, yas, cinsiyet
            "preferences": {},   # fav_team, fav_game, fav_color, fav_music
            "work": {},          # rol, sirket, projeler
            "tech": {},          # os, gpu, cpu, telefon
            "personality": {},   # mood, humor_style
            "location": {},      # sehir, ulke
            "notes": []          # serbest notlar
        }

    # =====================================================
    # ESKI YEREL SİSTEM (Geriye Uyumluluk)
    # =====================================================

    def save_important_detail(self, text):
        """Eski keyword-based kayit (yerel mod icin)"""
        keywords = ["adım", "ismim", "yasım", "severim", "nefret", "adres", "telefon", "proje"]
        if any(k in text.lower() for k in keywords):
            try:
                with open(self.memory_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                if text not in data["facts"]:
                    data["facts"].append(text)
                    if len(data["facts"]) > 50: data["facts"].pop(0)
                
                with open(self.memory_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            except Exception as e:
                print(f"Memory Save Error: {e}")

    def get_context(self):
        """Eski yerel hafiza context (geriye uyumlu)"""
        try:
            with open(self.memory_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return json.dumps(data["facts"], ensure_ascii=False)
        except: return ""

    def remember(self, user_msg, ai_reply):
        """Eski yerel kayit"""
        self.save_important_detail(user_msg)

    # =====================================================
    # YENİ CLOUD KİŞİSELLEŞTİRME SİSTEMİ
    # =====================================================

    def get_user_profile(self):
        """user_profile.json'u oku ve dondur"""
        try:
            with open(self.profile_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return self._empty_profile()

    def save_user_profile(self, profile):
        """user_profile.json'a kaydet"""
        try:
            with open(self.profile_file, "w", encoding="utf-8") as f:
                json.dump(profile, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Profile Save Error: {e}")

    def get_cloud_context(self):
        """
        Cloud system prompt'a enjekte edilecek kisisellestirilmis context.
        user_profile.json'dan dogal dilde ozet olusturur.
        """
        profile = self.get_user_profile()
        
        parts = []
        
        # Identity
        identity = profile.get("identity", {})
        if identity:
            id_parts = []
            if identity.get("name"): id_parts.append(f"Adi: {identity['name']}")
            if identity.get("nickname"): id_parts.append(f"Lakabi: {identity['nickname']}")
            if identity.get("age"): id_parts.append(f"Yasi: {identity['age']}")
            if identity.get("gender"): id_parts.append(f"Cinsiyet: {identity['gender']}")
            if id_parts: parts.append("KİMLİK: " + ", ".join(id_parts))
        
        # Preferences
        prefs = profile.get("preferences", {})
        if prefs:
            pref_items = [f"{k}: {v}" for k, v in prefs.items() if v]
            if pref_items: parts.append("TERCİHLER: " + ", ".join(pref_items))
        
        # Work
        work = profile.get("work", {})
        if work:
            work_items = [f"{k}: {v}" for k, v in work.items() if v]
            if work_items: parts.append("İŞ: " + ", ".join(work_items))
        
        # Tech
        tech = profile.get("tech", {})
        if tech:
            tech_items = [f"{k}: {v}" for k, v in tech.items() if v]
            if tech_items: parts.append("TEKNOLOJİ: " + ", ".join(tech_items))
        
        # Location
        loc = profile.get("location", {})
        if loc:
            loc_items = [f"{k}: {v}" for k, v in loc.items() if v]
            if loc_items: parts.append("KONUM: " + ", ".join(loc_items))
        
        # Personality
        pers = profile.get("personality", {})
        if pers:
            pers_items = [f"{k}: {v}" for k, v in pers.items() if v]
            if pers_items: parts.append("KİŞİLİK: " + ", ".join(pers_items))
        
        # Notes
        notes = profile.get("notes", [])
        if notes:
            parts.append("NOTLAR: " + " | ".join(notes[-5:]))  # Son 5 not
        
        if not parts:
            return ""
        
        return "[KULLANICI PROFİLİ]:\n" + "\n".join(parts)

    def remember_cloud(self, user_msg, ai_reply, gemini_client, model_name):
        """
        Arka planda Gemini'yi kullanarak konusmadan kisisel bilgi cikarir.
        Thread icinde calisir, ana cevabi geciktirmez.
        """
        def _extract_and_save():
            try:
                self._extract_personal_info(user_msg, ai_reply, gemini_client, model_name)
            except Exception as e:
                print(f"Cloud Memory Extract Error: {e}")
        
        t = threading.Thread(target=_extract_and_save, daemon=True)
        t.start()

    def _extract_personal_info(self, user_msg, ai_reply, gemini_client, model_name):
        """
        Gemini'yi kullanarak konusmadan kisisel bilgileri cikarir.
        Sadece GERCEK bilgi iceren mesajlarda calisir.
        """
        from google.genai import types
        
        # Hizli on-filtre: cok kisa veya soru olan mesajlari atla
        msg_lower = user_msg.lower().strip()
        if len(msg_lower) < 5:
            return
        
        # Soru kaliplari (bilgi icermez, soruyorlar)
        question_patterns = [
            "adım ne", "adımı", "beni tanıyor", "hatırlıyor mu", 
            "kim olduğumu", "ne biliyorsun", "neler biliyorsun",
            "nasılsın", "ne yapabilirsin", "merhaba", "selam",
            "ne zaman", "kaç", "nedir", "kimdir"
        ]
        if any(p in msg_lower for p in question_patterns) and len(msg_lower) < 40:
            return
        
        # Bilgi icerme potansiyeli olan anahtar kelimeler
        info_keywords = [
            "adım", "ismim", "benim adım", "ben ", "yaşım", "yaşında",
            "severim", "seviyorum", "tutuyorum", "takımım", "favori",
            "kullanıyorum", "çalışıyorum", "işim", "mesleğim",
            "bilgisayarım", "telefonum", "arabam",
            "oturuyorum", "yaşıyorum", "şehrım", "memleketim",
            "hobim", "ilgi", "nefret", "sevmem", "beğen",
            "projemiz", "projem", "okulumda", "üniversite",
            "doğum", "burçum", "kardeşim", "ailem",
            "öğrenci", "mühendis", "developer", "programcı",
            "windows", "linux", "mac", "iphone", "samsung", "android",
            "nvidia", "amd", "intel", "rtx", "gtx",
            "galatasaray", "fenerbahçe", "beşiktaş", "trabzonspor"
        ]
        
        if not any(k in msg_lower for k in info_keywords):
            return
        
        # Mevcut profili yukle
        current_profile = self.get_user_profile()
        
        extraction_prompt = (
            f"GÖREV: Aşağıdaki kullanıcı mesajından KİŞİSEL BİLGİ çıkar.\n"
            f"SADECE kesin bilgi çıkar. Tahmin yapma. Soru cümlesinden bilgi çıkarma.\n"
            f"\n"
            f"KULLANICI MESAJI: \"{user_msg}\"\n"
            f"AI CEVABI: \"{ai_reply[:200]}\"\n"
            f"\n"
            f"MEVCUT PROFİL: {json.dumps(current_profile, ensure_ascii=False)}\n"
            f"\n"
            f"ÇIKTI FORMATI: Sadece JSON döndür, başka hiçbir şey yazma.\n"
            f"Eğer yeni bilgi YOKSA sadece boş JSON döndür: {{}}\n"
            f"Eğer yeni bilgi varsa, SADECE yeni/güncellenen alanları döndür:\n"
            f'{{\n'
            f'  "identity": {{"name": "...", "age": "...", "nickname": "..."}},\n'
            f'  "preferences": {{"fav_team": "...", "fav_game": "...", "fav_food": "..."}},\n'
            f'  "work": {{"role": "...", "company": "...", "school": "..."}},\n'
            f'  "tech": {{"phone": "...", "gpu": "...", "os": "..."}},\n'
            f'  "location": {{"city": "...", "country": "..."}},\n'
            f'  "personality": {{"style": "..."}},\n'
            f'  "notes": ["serbest not"]\n'
            f'}}\n'
            f"\n"
            f"KURALLAR:\n"
            f"- Sadece KESIN bilgi çıkar\n"
            f"- Soru cümlelerinden bilgi çıkarma (örn: 'adım ne?' bilgi DEĞİLDİR)\n"
            f"- 'Benim adım Ahmet' → identity.name: 'Ahmet' (bu bilgidir)\n"
            f"- Mevcut profilde zaten bulunan bilgiyi tekrar ekleme\n"
            f"- Sadece JSON döndür, açıklama yazma"
        )
        
        try:
            config = types.GenerateContentConfig(
                system_instruction="Sen bir bilgi çıkarma motorusun. Sadece JSON döndür.",
                temperature=0.1  # Düşük sıcaklık = daha deterministik
            )
            
            response = gemini_client.models.generate_content(
                model=model_name,
                contents=extraction_prompt,
                config=config
            )
            
            # Response'dan text çıkar
            raw_text = ""
            if response.candidates and len(response.candidates) > 0:
                cand = response.candidates[0]
                if cand.content and cand.content.parts:
                    for part in cand.content.parts:
                        if hasattr(part, 'text') and part.text:
                            raw_text += part.text
            
            if not raw_text.strip():
                return
            
            # JSON parse et
            # Gemini bazen ```json ... ``` blogu icinde dondurur
            json_match = re.search(r'```(?:json)?\s*(.*?)\s*```', raw_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                json_str = raw_text.strip()
            
            extracted = json.loads(json_str)
            
            # Bos JSON = yeni bilgi yok
            if not extracted or extracted == {}:
                return
            
            # Mevcut profile merge et
            self._merge_profile(current_profile, extracted)
            self.save_user_profile(current_profile)
            
            try:
                print(f"CLOUD HAFIZA: Yeni bilgi kaydedildi -> {json.dumps(extracted, ensure_ascii=False)}")
            except: pass
            
        except json.JSONDecodeError:
            # JSON parse edilemedi, atla
            pass
        except Exception as e:
            print(f"Cloud Memory Extraction Error: {e}")

    def _merge_profile(self, current, new_data):
        """
        Yeni cikarilan veriyi mevcut profile akilli sekilde kaynastirir.
        Ustyazma yerine guncelleme yapar.
        """
        for category, values in new_data.items():
            if category not in current:
                current[category] = {} if category != "notes" else []
            
            if category == "notes":
                # Notes = liste, yenileri ekle (tekrar olmasin)
                if isinstance(values, list):
                    for note in values:
                        if note and note not in current["notes"]:
                            current["notes"].append(note)
                            # Max 20 not tut
                            if len(current["notes"]) > 20:
                                current["notes"].pop(0)
                elif isinstance(values, str) and values:
                    if values not in current["notes"]:
                        current["notes"].append(values)
            elif isinstance(values, dict):
                # Dict = mevcut alanlari guncelle, yenileri ekle
                for key, val in values.items():
                    if val and str(val).strip():
                        current[category][key] = val
            elif values:
                # Direkt deger (beklenmedik ama handle et)
                current[category] = values
