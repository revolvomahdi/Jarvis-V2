
import ollama
import json
import os
import subprocess
import re
import time
from utils.settings_manager import SettingsManager
from engines.task_manager import TaskManager 


# Image generation disabled
# from engines.image_generator import ImageGenerator

class LocalBrain:
    def __init__(self):
        self.settings = SettingsManager()
        self.agents = self.settings.get("local_agents", {})
        
        # Image generation disabled
        self.painter = None
        
        # Default safety fallback
        if not self.agents:
            self.agents = {
                "commander": "phi4-mini",
                "chat": "gemma2:9b",
                "system_engineer": "qwen2.5-coder:7b",
                "lead_dev": "deepseek-coder:6.7b",
                "vision": "llava:v1.6",
                "analyst": "llama3.1:8b",
                "math": "qwen2.5-math:1.5b",
                "painter": "gemma2:9b" # Using chat model to refine prompt
            }

    def process_request(self, prompt: str, history=None, progress_callback=None):
        """
        Main entry point for Local Brain.
        KOMUTAN (phi4-mini) analyzes intent with massive training prompt.
        """
        try:
            print(f"MERKEZ: İstek alındı -> '{prompt}'")
        except: pass
        
        # KOMUTAN (TEK YETKİLİ ROUTER)
        intent = self._consult_commander(prompt)
        try: print(f"KOMUTAN ANALİZİ: {intent}")
        except: pass
        
        # ROUTING
        if intent == "IMAGE":
            return self._agent_image_department(prompt, progress_callback=progress_callback)
        elif intent == "SYSTEM_REPORT":
            return self._agent_system_report(prompt)
        elif intent == "SYSTEM":
            return self._agent_system(prompt)
        elif intent == "CODING":
            return self._agent_coding(prompt)
        elif intent == "VISION":
            return self._agent_vision(prompt) 
        elif intent == "ANALYSIS":
            return self._agent_analyst(prompt)
        elif intent == "MATH":
            return self._agent_math(prompt)
        elif intent == "SEARCH":
            return self._agent_search(prompt, history=history)
        else:
            return self._agent_chat(prompt, history=history)

    
    def test_agents(self):
        """Test All Local Agents One by One"""
        results = []
        
        # Test basic connection first
        try:
            ollama.list()
        except Exception as e:
            return [{"agent": "OLLAMA BAĞLANTISI", "model": "localhost:11434", "status": "FAIL", "msg": str(e)}]

        for role, model in self.agents.items():
            if role == "painter": continue # Skip disabled
            
            print(f"Testing {role} ({model})...")
            start = time.time()
            try:
                # Simple ping
                res = ollama.chat(model=model, messages=[{'role': 'user', 'content': 'hi'}])
                duration = time.time() - start
                
                content = res['message']['content'][:20].replace("\n", " ") # Trim response
                results.append({
                    "agent": role.upper(), 
                    "model": model, 
                    "status": "OK", 
                    "time": f"{duration:.2f}s",
                    "response": content
                })
            except Exception as e:
                results.append({
                    "agent": role.upper(), 
                    "model": model, 
                    "status": "FAIL", 
                    "time": "N/A",
                    "response": str(e)
                })
                
        return results

    def _consult_commander(self, prompt):
        """
        Uses phi4-mini to classify intent.
        Output expected: STRICTLY ONE WORD INTENT
        """
        commander_model = self.agents.get("commander", "phi4-mini")
        
        sys_prompt = (
            "SEN BİR SINIFLANDIRICI ROBOTSUN. GÖREVİN: Kullanıcının isteğini analiz edip KATEGORİLERDEN SADECE BİRİNİ SEÇMEK.\n"
            "\n"
            "KATEGORİLER:\n"
            "- SYSTEM = Bilgisayarda İŞLEM yapmak. Uygulama açmak/kapatmak, dosya oluşturmak/silmek, web sitesi açmak, ses/parlaklık ayarı, temizlik.\n"
            "- SYSTEM_REPORT = Bilgisayar durumunu SORGULAMAK. CPU/RAM/GPU/Disk kullanımı, sıcaklık, pil, kaynak tüketimi.\n"
            "- IMAGE = Resim/görsel ÜRETMEK. Çizim, logo, illüstrasyon.\n"
            "- CODING = Kod/script YAZMAK. Programlama, debugging.\n"
            "- VISION = Ekranı GÖRMEK/okumak. Ekran görüntüsü analizi.\n"
            "- MATH = Matematiksel HESAPLAMA yapmak.\n"
            "- SEARCH = GÜNCEL/GERÇEK bilgi gerektiren sorular. Hava durumu, döviz kuru, fiyat, tarih/saat, konum, yol tarifi, güncel haberler, canlı sonuçlar, nüfus, deprem bilgisi.\n"
            "- CHAT = SOHBET, genel kültür, kişisel soru, tavsiye. GÜNCEL VERİ gerektirmeyen her şey.\n"
            "\n"
            "KRİTİK KURAL: ÇIKTIN SADECE TEK KELİME OLMALI!\n"
            "\n"
            "EN ÖNEMLİ KURAL - BAĞLAM ANLAMA:\n"
            "Bir uygulama ismi geçmesi her zaman SYSTEM demek DEĞİLDİR!\n"
            "- Uygulamayı AÇMAK/KAPATMAK istiyorsa -> SYSTEM\n"
            "- Uygulama HAKKINDA genel BİLGİ soruyorsa -> CHAT\n"
            "- Uygulamanın KAYNAK tüketimini soruyorsa -> SYSTEM_REPORT\n"
            "\n"
            "CHAT vs SEARCH AYIRIMI:\n"
            "- Cevap zamanla DEĞİŞEBİLİR (fiyat, hava, skor, güncel olay) -> SEARCH\n"
            "- Cevap HER ZAMAN AYNI (genel kültür, tanım, tarihsel bilgi) -> CHAT\n"
            "- Sohbet, selamlaşma, tavsiye, fikir -> CHAT\n"
            "\n"
            "SEARCH TETİKLEYİCİ KELİMELER (bunlar varsa BÜYÜK ihtimalle SEARCH):\n"
            "- maç, skor, lig, puan, turnuva, şampiyon -> SEARCH\n"
            "- fiyat, kaç TL, kaç lira, kaç dolar, kur -> SEARCH\n"
            "- hava, derece, sıcaklık, yağmur -> SEARCH\n"
            "- ne zaman, hangi gün, kaçta, tarih -> SEARCH\n"
            "- deprem, haber, son dakika, gündem -> SEARCH\n"
            "- trafik, yol, konum, nerede -> SEARCH\n"
            "AMA: 'X nedir', 'X kimdir', 'X ne işe yarar' gibi tanım soruları -> CHAT\n"
            "\n"
            "=== SYSTEM (İŞLEM YAPMA) ÖRNEKLERİ ===\n"
            "\"YouTube aç\" -> SYSTEM\n"
            "\"YouTube'u aç\" -> SYSTEM\n"
            "\"YouTube'da müzik aç\" -> SYSTEM\n"
            "\"Spotify aç\" -> SYSTEM\n"
            "\"Chrome'u kapat\" -> SYSTEM\n"
            "\"Discord'u başlat\" -> SYSTEM\n"
            "\"WhatsApp aç\" -> SYSTEM\n"
            "\"Instagram'ı aç\" -> SYSTEM\n"
            "\"Twitter'ı aç\" -> SYSTEM\n"
            "\"Telegram'ı aç\" -> SYSTEM\n"
            "\"Hesap makinesini aç\" -> SYSTEM\n"
            "\"Not defterini aç\" -> SYSTEM\n"
            "\"Paint'i aç\" -> SYSTEM\n"
            "\"Dosya gezginini aç\" -> SYSTEM\n"
            "\"Ayarları aç\" -> SYSTEM\n"
            "\"Görev yöneticisini aç\" -> SYSTEM\n"
            "\"Kontrol panelini aç\" -> SYSTEM\n"
            "\"Tarayıcıyı aç\" -> SYSTEM\n"
            "\"Klasör oluştur\" -> SYSTEM\n"
            "\"Masaüstüne klasör oluştur\" -> SYSTEM\n"
            "\"Dosya sil\" -> SYSTEM\n"
            "\"Temp klasörünü temizle\" -> SYSTEM\n"
            "\"Geri dönüşüm kutusunu boşalt\" -> SYSTEM\n"
            "\"Bilgisayarı kapat\" -> SYSTEM\n"
            "\"Bilgisayarı yeniden başlat\" -> SYSTEM\n"
            "\"Ses aç\" -> SYSTEM\n"
            "\"Sesi kıs\" -> SYSTEM\n"
            "\"Parlaklığı arttır\" -> SYSTEM\n"
            "\"WiFi'yi kapat\" -> SYSTEM\n"
            "\"Bluetooth aç\" -> SYSTEM\n"
            "\"Google'da ara\" -> SYSTEM\n"
            "\"Müzik çal\" -> SYSTEM\n"
            "\"Uyku moduna geç\" -> SYSTEM\n"
            "\"Yeni Word belgesi oluştur\" -> SYSTEM\n"
            "\n"
            "=== SYSTEM_REPORT (DURUM SORGU) ÖRNEKLERİ ===\n"
            "\"Sistem durumu ne\" -> SYSTEM_REPORT\n"
            "\"PC durumu\" -> SYSTEM_REPORT\n"
            "\"RAM ne kadar dolu\" -> SYSTEM_REPORT\n"
            "\"CPU yüzde kaç\" -> SYSTEM_REPORT\n"
            "\"Ne kasıyor\" -> SYSTEM_REPORT\n"
            "\"Bilgisayar neden yavaş\" -> SYSTEM_REPORT\n"
            "\"Hangi uygulama RAM yiyor\" -> SYSTEM_REPORT\n"
            "\"C diskini ne dolduruyor\" -> SYSTEM_REPORT\n"
            "\"Bilgisayarımda C diskini en çok ne dolduruyor\" -> SYSTEM_REPORT\n"
            "\"Disk ne kadar dolu\" -> SYSTEM_REPORT\n"
            "\"RAM sömüren uygulamalar\" -> SYSTEM_REPORT\n"
            "\"Pil durumu\" -> SYSTEM_REPORT\n"
            "\"Oyun modu\" -> SYSTEM_REPORT\n"
            "\"RAM temizle\" -> SYSTEM_REPORT\n"
            "\"Diskimi ne dolduruyor\" -> SYSTEM_REPORT\n"
            "\"GPU sıcaklığı\" -> SYSTEM_REPORT\n"
            "\n"
            "=== IMAGE (GÖRSEL ÜRETME) ÖRNEKLERİ ===\n"
            "\"Kedi resmi çiz\" -> IMAGE\n"
            "\"Logo tasarla\" -> IMAGE\n"
            "\"Uzay gemisi çiz\" -> IMAGE\n"
            "\"Resim yap\" -> IMAGE\n"
            "\"Görsel oluştur\" -> IMAGE\n"
            "\"Avatar tasarla\" -> IMAGE\n"
            "\"Poster tasarla\" -> IMAGE\n"
            "\n"
            "=== CODING ÖRNEKLERİ ===\n"
            "\"Python kodu yaz\" -> CODING\n"
            "\"JavaScript fonksiyonu yaz\" -> CODING\n"
            "\"HTML sayfası oluştur\" -> CODING\n"
            "\"Bu kodu düzelt\" -> CODING\n"
            "\"SQL sorgusu yaz\" -> CODING\n"
            "\"Script hazırla\" -> CODING\n"
            "\n"
            "=== VISION ÖRNEKLERİ ===\n"
            "\"Ekrana bak\" -> VISION\n"
            "\"Ne görüyorsun\" -> VISION\n"
            "\"Ekrandakini analiz et\" -> VISION\n"
            "\n"
            "=== MATH ÖRNEKLERİ ===\n"
            "\"5 artı 3 kaç\" -> MATH\n"
            "\"Hesapla 100 bölü 7\" -> MATH\n"
            "\"Karekök 144\" -> MATH\n"
            "\"Yüzde hesapla\" -> MATH\n"
            "\"15'in karesi\" -> MATH\n"
            "\n"
            "=== SEARCH (GÜNCEL VERİ GEREKTİREN) ÖRNEKLERİ ===\n"
            "\"Hava nasıl\" -> SEARCH\n"
            "\"Hava durumu\" -> SEARCH\n"
            "\"Yarın hava nasıl olacak\" -> SEARCH\n"
            "\"İstanbul'da hava kaç derece\" -> SEARCH\n"
            "\"Bugün günlerden ne\" -> SEARCH\n"
            "\"Saat kaç\" -> SEARCH\n"
            "\"Bugün tarih ne\" -> SEARCH\n"
            "\"Dolar kaç TL\" -> SEARCH\n"
            "\"Euro kaç lira\" -> SEARCH\n"
            "\"Bitcoin kaç dolar\" -> SEARCH\n"
            "\"Altın fiyatı\" -> SEARCH\n"
            "\"Borsa ne durumda\" -> SEARCH\n"
            "\"İstanbul'dan Ankara'ya nasıl gidilir\" -> SEARCH\n"
            "\"En yakın hastane nerede\" -> SEARCH\n"
            "\"Yol tarifi ver\" -> SEARCH\n"
            "\"Trafik durumu\" -> SEARCH\n"
            "\"Son deprem nerede oldu\" -> SEARCH\n"
            "\"Güncel haberler\" -> SEARCH\n"
            "\"Bugün ne oldu\" -> SEARCH\n"
            "\"Galatasaray maç skoru\" -> SEARCH\n"
            "\"Süper Lig puan durumu\" -> SEARCH\n"
            "\"Türkiye nüfusu kaç\" -> SEARCH\n"
            "\"Benzin fiyatı\" -> SEARCH\n"
            "\"Elektrik fiyatı\" -> SEARCH\n"
            "\"iPhone 16 fiyatı\" -> SEARCH\n"
            "\"Netflix'te bu hafta ne var\" -> SEARCH\n"
            "\"Bugün hangi maçlar var\" -> SEARCH\n"
            "\"Seçim sonuçları\" -> SEARCH\n"
            "\"Deprem mi oldu\" -> SEARCH\n"
            "\"Son dakika haberleri\" -> SEARCH\n"
            "\"Galatasaray Juventus maçı hangi gün\" -> SEARCH\n"
            "\"Fenerbahçe maçı ne zaman\" -> SEARCH\n"
            "\"Beşiktaş maçı kaçta\" -> SEARCH\n"
            "\"Trabzonspor maç takvimi\" -> SEARCH\n"
            "\"Şampiyonlar Ligi maçları\" -> SEARCH\n"
            "\"Dünya Kupası ne zaman\" -> SEARCH\n"
            "\"X takımı Y takımı maçı\" -> SEARCH\n"
            "\"Maç sonucu\" -> SEARCH\n"
            "\"Lig sıralaması\" -> SEARCH\n"
            "\"Transfer haberleri\" -> SEARCH\n"
            "\"Konsere bilet fiyatı\" -> SEARCH\n"
            "\"X filmi ne zaman vizyona giriyor\" -> SEARCH\n"
            "\"Okullar ne zaman açılıyor\" -> SEARCH\n"
            "\"Bayram tatili ne zaman\" -> SEARCH\n"
            "\"Resmi tatil günleri\" -> SEARCH\n"
            "\n"
            "=== CHAT (SOHBET / GENEL BİLGİ) ÖRNEKLERİ ===\n"
            "\"Nasılsın\" -> CHAT\n"
            "\"Merhaba\" -> CHAT\n"
            "\"Selam\" -> CHAT\n"
            "\"Sen kimsin\" -> CHAT\n"
            "\"Adın ne\" -> CHAT\n"
            "\"Benim adım ne\" -> CHAT\n"
            "\"Teşekkürler\" -> CHAT\n"
            "\"Günaydın\" -> CHAT\n"
            "\"İyi geceler\" -> CHAT\n"
            "\"YouTube kaç yılında kuruldu\" -> CHAT\n"
            "\"YouTube'un sahibi kim\" -> CHAT\n"
            "\"Google ne zaman kuruldu\" -> CHAT\n"
            "\"Spotify nedir\" -> CHAT\n"
            "\"Discord nasıl çalışır\" -> CHAT\n"
            "\"Chrome nedir\" -> CHAT\n"
            "\"Python hangi yılda çıktı\" -> CHAT\n"
            "\"Yapay zeka nedir\" -> CHAT\n"
            "\"En iyi film hangisi\" -> CHAT\n"
            "\"Türkiye'nin başkenti\" -> CHAT\n"
            "\"Einstein kimdir\" -> CHAT\n"
            "\"Ne önerirsin\" -> CHAT\n"
            "\"Tavsiye ver\" -> CHAT\n"
            "\"Bir şaka anlat\" -> CHAT\n"
            "\"Hikaye anlat\" -> CHAT\n"
            "\"Hangi telefon iyi\" -> CHAT\n"
            "\"Laptop tavsiyesi\" -> CHAT\n"
            "\"Oyun önerisi\" -> CHAT\n"
            "\"Film önerisi\" -> CHAT\n"
            "\"RAM ne işe yarar\" -> CHAT\n"
            "\"CPU ne demek\" -> CHAT\n"
            "\"SSD ile HDD farkı\" -> CHAT\n"
            "\"Bitcoin nedir\" -> CHAT\n"
            "\"Neler yapabilirsin\" -> CHAT\n"
            "\"Kendini tanıt\" -> CHAT\n"
            "\"Windows 11 ne zaman çıktı\" -> CHAT\n"
            "\"Yemek tarifi ver\" -> CHAT\n"
            "\"Mars'a gitmek mümkün mü\" -> CHAT\n"
            "\n"
            "HATIRLATMA: SADECE TEK KELİME YAZ!\n"
            "Doğru çıktılar: SYSTEM, CHAT, IMAGE, CODING, VISION, MATH, SYSTEM_REPORT, SEARCH"
        )
        
        try:
            response = ollama.chat(model=commander_model, messages=[
                {'role': 'system', 'content': sys_prompt},
                {'role': 'user', 'content': prompt}
            ])
            content = response['message']['content'].upper().strip()
            
            # Strip reasoning tags from phi4-mini-reasoning (e.g. <THINK>...</THINK>)
            content = re.sub(r'<THINK>.*?</THINK>', '', content, flags=re.DOTALL).strip()
            
            # Clean up potential extra text (e.g. "INTENT: CHAT" -> "CHAT")
            for keyword in ["SYSTEM_REPORT", "SYSTEM", "IMAGE", "CODING", "VISION", "MATH", "SEARCH", "CHAT", "ANALYSIS"]:
                if keyword in content:
                    return keyword
            
            return "CHAT" # Default if unrecognized
        except:
            return "CHAT" # Fallback

    def _agent_image_department(self, prompt, progress_callback=None):
        """Image generation has been disabled"""
        return "Görsel oluşturma özelliği şu an devre dışı bırakılmıştır."

    def _agent_search(self, prompt, history=None):
        """
        SEARCH Agent: Güncel/gerçek bilgi gerektiren sorular için.
        1. Tarih/saat sorusu ise datetime ile cevapla
        2. Diğer sorular için DuckDuckGo ile ara
        3. Sonuçları LLM'e context olarak ver, gerçek veriye dayalı cevap üret
        """
        from engines.system_tools import WebTools
        from datetime import datetime
        import locale
        
        model = self.agents.get("chat", "llama3.1:8b")
        msg = prompt.lower()
        
        # ===== TARİH/SAAT SORULARI (İnternet gerektirmez) =====
        now = datetime.now()
        gunler = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
        aylar = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", 
                 "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
        
        gun_adi = gunler[now.weekday()]
        ay_adi = aylar[now.month - 1]
        tarih_str = f"{now.day} {ay_adi} {now.year}, {gun_adi}"
        saat_str = f"{now.strftime('%H:%M')}"
        
        if any(w in msg for w in ["saat kaç", "saat ne", "saati söyle"]):
            return f"Şu an saat **{saat_str}**, efendim."
        
        if any(w in msg for w in ["bugün günlerden ne", "hangi gün", "günlerden ne"]):
            return f"Bugün **{gun_adi}**, {tarih_str}."
        
        if any(w in msg for w in ["bugün tarih", "tarih ne", "tarih kaç"]):
            return f"Bugün **{tarih_str}**, saat {saat_str}."
        
        # ===== İNTERNET ARAŞTIRMASI (DuckDuckGo) =====
        try:
            print(f"ARAMA MOTORU devrede... Sorgu: '{prompt}'")
        except: pass
        
        web = WebTools()
        results = web.search(prompt)
        
        if not results:
            # Arama başarısız olursa direkt chat'e düş
            return self._agent_chat(prompt, history=history)
        
        # Context oluştur
        context = f"GÜNCEL TARİH: {tarih_str}, Saat: {saat_str}\n\n"
        context += "İNTERNETTEN BULUNAN GÜNCEL VERİLER:\n"
        for i, r in enumerate(results[:5]):
            context += f"\n--- KAYNAK {i+1}: {r.get('title', '')} ---\n"
            context += f"{r.get('body', r.get('snippet', ''))}\n"
            # İlk 2 kaynağın içeriğini de oku  
            if i < 2:
                url = r.get('href', '')
                if url:
                    page_content = web.read_url(url)
                    if page_content:
                        context += f"DETAY: {page_content[:800]}\n"
        
        # LLM'e context ile soru sor
        search_prompt = (
            f"KULLANICININ SORUSU: {prompt}\n\n"
            f"{context}\n\n"
            f"GÖREV: Yukarıdaki GÜNCEL İNTERNET VERİLERİNE dayanarak kullanıcının sorusunu "
            f"Türkçe olarak kısa ve net cevapla. SADECE verilen verilerdeki bilgileri kullan, "
            f"uydurma. Kaynak belirt. Eğer veri yetersizse bunu belirt."
        )
        
        sys_prompt = (
            "Sen JARVIS'sin. Kullanıcıya GÜNCEL ve DOĞRU bilgi veren bir arama asistanısın. "
            "Sana verilen internet arama sonuçlarına dayanarak cevap ver. "
            "ASLA bilgi uydurmak yok. Kısa, net ve bilgilendirici ol. "
            "Kullanıcıya 'Efendim' diye hitap et."
        )
        
        try:
            # Konuşma geçmişini ekle
            messages = [{'role': 'system', 'content': sys_prompt}]
            if history:
                for m in history[-10:]:
                    role = 'user' if m['role'] == 'user' else 'assistant'
                    messages.append({'role': role, 'content': m['text']})
                # Son mesaj zaten history'de var, ayrıca search_prompt'u ekle
                messages.append({'role': 'user', 'content': search_prompt})
            else:
                messages.append({'role': 'user', 'content': search_prompt})
            
            response = ollama.chat(model=model, messages=messages)
            return response['message']['content']
        except Exception as e:
            return f"Arama sırasında hata oluştu: {str(e)}"

    def _agent_chat(self, prompt, history=None):
        # Fallback to llama3.1 if gemma2 is not assigned
        model = self.agents.get("chat", "llama3.1:8b") 
        lang = self.settings.get("language", "tr")

        try:
            print(f"SOHBET ({model}) devrede... Lang: {lang}")
        except: pass
        
        # 1. Base Prompt Selection
        if lang == "en":
            sys_prompt = """
            You are JARVIS, KKSVSİGB's AI.
            - Address the user as "Sir".
            - Be concise, intelligent, and helpful.
            - NEVER state "I am JARVIS" at the start of your sentence.
            - Just answer the user's question directly and professionally.
            """
        else:
            sys_prompt = (
                "Sen JARVIS'sin. KKSVSİGB'nin yapay zeka asistanısın.\n"
                "\n"
                "KİMLİĞİN:\n"
                "- Adın JARVIS. KKSVSİGB organizasyonu için çalışıyorsun.\n"
                "- Zeki, profesyonel, sadık ve güvenilir bir yapay zeka asistanısın.\n"
                "- Kullanıcını 'Efendim' diye hitap et.\n"
                "\n"
                "DAVRANIS KURALLARI:\n"
                "1. ASLA cümleye 'Ben JARVIS'im' diyerek başlama.\n"
                "2. ASLA 'Yapay zeka olarak...' deme.\n"
                "3. Kısa, net ve öz cevaplar ver. Gereksiz uzatma.\n"
                "4. Laubali olma, profesyonel ol ama samimi de ol.\n"
                "5. Emoji kullanabilirsin ama abartma.\n"
                "6. Bilmediğin konuda UYDURMAK yerine 'Bu konuda kesin bilgim yok' de.\n"
                "7. Türkçe cevap ver, akıcı ve doğal ol.\n"
                "8. Kullanıcının adını biliyorsan kullan.\n"
                "\n"
                "CEVAP FORMATLARI:\n"
                "\n"
                "Selamlaşma soruları (Merhaba, Selam, Nasılsın):\n"
                "- Kısa ve samimi cevap ver. Örnek: 'İyiyim efendim, size nasıl yardımcı olabilirim?'\n"
                "- ASLA uzun paragraf yazma.\n"
                "\n"
                "Genel kültür soruları (X nedir, X kimdir, X ne zaman):\n"
                "- Kısa ama bilgilendirici cevap ver.\n"
                "- Tarihi bilgileri doğru ver.\n"
                "- Madde işaretleri kullan.\n"
                "\n"
                "Tavsiye/Öneri soruları (Film önerisi, Laptop tavsiyesi):\n"
                "- 3-5 madde halinde öner.\n"
                "- Her önerinin yanına kısa açıklama ekle.\n"
                "\n"
                "Tanım/Açıklama soruları (X ne işe yarar, X ile Y farkı):\n"
                "- Önce kısa tanım ver.\n"
                "- Sonra detay gerekirse madde halinde açıkla.\n"
                "\n"
                "Kişisel sorular (Adım ne, Beni tanıyor musun):\n"
                "- Hafızadaki bilgileri kullan.\n"
                "- Hafızada yoksa nazikçe 'Henüz bu bilgiyi kaydetmemişim efendim' de.\n"
                "\n"
                "Yeteneklerin hakkında sorular (Ne yapabilirsin, Neler biliyorsun):\n"
                "- Kısa liste halinde yeteneklerini say:\n"
                "  * Sistem yönetimi (dosya, klasör, uygulama açma/kapatma)\n"
                "  * Bilgi araştırma (internetten güncel veri çekme)\n"
                "  * Kod yazma ve düzenleme\n"
                "  * Matematiksel hesaplamalar\n"
                "  * Sistem durumu analizi\n"
                "  * Sohbet ve genel bilgi\n"
                "\n"
                "ÖRNEK DİYALOGLAR:\n"
                "Kullanıcı: 'Nasılsın'\n"
                "Sen: 'İyiyim efendim, teşekkür ederim! Size nasıl yardımcı olabilirim?'\n"
                "\n"
                "Kullanıcı: 'YouTube kaç yılında kuruldu'\n"
                "Sen: 'YouTube, 2005 yılında Chad Hurley, Steve Chen ve Jawed Karim tarafından kurulmuştur efendim. 2006 yılında Google tarafından satın alınmıştır.'\n"
                "\n"
                "Kullanıcı: 'Film önerisi ver'\n"
                "Sen: 'İşte birkaç öneri efendim:\n"
                "1. **Interstellar** - Uzay ve zaman üzerine muhteşem bir bilim kurgu\n"
                "2. **The Dark Knight** - En iyi süper kahraman filmlerinden\n"
                "3. **Inception** - Zihin büken bir başyapıt'\n"
                "\n"
                "Kullanıcı: 'RAM ne işe yarar'\n"
                "Sen: 'RAM (Random Access Memory), bilgisayarın geçici belleğidir efendim. Açık olan uygulamalar ve işlemler RAM üzerinde çalışır. RAM kapandığında içindeki veriler silinir. Daha fazla RAM = Aynı anda daha fazla uygulama çalıştırabilme.'\n"
            )
        
        # 2. Memory Injection
        try:
            from utils.memory_manager import MemoryManager
            mem = MemoryManager().get_context()
            if mem:
                header = "[USER INFO / HAFIZA]:" if lang == "tr" else "[USER INFO / MEMORY]:"
                sys_prompt += f"\n\n{header} {mem}"
        except: pass
        
        # 3. Konuşma geçmişini dahil et
        messages = [{'role': 'system', 'content': sys_prompt}]
        
        if history and len(history) > 0:
            # Son 10 mesajı al (token aşımını önle)
            recent = history[-10:]
            for m in recent:
                role = 'user' if m['role'] == 'user' else 'assistant'
                messages.append({'role': role, 'content': m['text']})
        else:
            # History yoksa sadece mevcut prompt'u gönder
            messages.append({'role': 'user', 'content': prompt})
        
        res = ollama.chat(model=model, messages=messages)
        return self._format_response(res)

    def _format_response(self, res):
        content = res['message']['content']
        try:
            # Debug: Print keys safely
            # print(f"DEBUG: Response Keys: {list(res.keys())}")
            
            total_ns = res.get('total_duration', 0)
            eval_count = res.get('eval_count', 0)
            eval_ns = res.get('eval_duration', 0)
            
            tps_str = "N/A"
            time_str = "N/A"

            if total_ns > 0:
                time_str = f"{total_ns / 1e9:.2f} s"
            
            if eval_ns > 0 and eval_count > 0:
                tps = eval_count / (eval_ns / 1e9)
                tps_str = f"{tps:.2f} t/s"
            
            # Simple text footer
            stats = f"\n\n------------\n[Hiz: {tps_str} | Sure: {time_str}]"
            return content + stats
            
        except Exception as e:
            print(f"Metrics Error: {e}")
            return content

    def _agent_system_report(self, prompt):
        tm = TaskManager()
        msg = prompt.lower()
        
        # Disk Check
        if any(w in msg for w in ["disk", "kaplayan", "dolduran", "yer", "hafıza"]):
            usage = tm.analyze_disk_usage()
            if not usage: return "⚠️ Kullanıcı profili klasörlerinde kayda değer büyük boyutlu klasör bulunamadı."
            
            report = "💾 **Disk Kullanım Analizi (Kullanıcı Klasörleri):**\n"
            for item in usage:
                icon = "📁"
                if "Temp" in item['path']: icon = "🗑️"
                elif "Downloads" in item['path']: icon = "⬇️"
                report += f"- {icon} **{item['path']}**: {item['size_gb']} GB\n"
            return report

        # Resource Hogs
        if any(w in msg for w in ["kasıyor", "sömüren", "yavaşlatan", "uygulama"]):
            hogs = tm.get_resource_hogs()
            report = "🛑 **Kaynak Canavarları (Top 5):**\n"
            for p in hogs:
                report += f"- **{p['name']}**: {p['memory_mb']} MB RAM | %{p['cpu_percent']} CPU\n"
            return report

        # Optimization
        if any(w in msg for w in ["temizle", "optimize", "hızlandır", "oyun modu"]):
            opt = tm.optimize_performance()
            if not opt['candidates']: return "✅ Sistem zaten optimize durumda."
            report = f"🚀 **Oyun Modu Önerisi:**\nŞu uygulamalar kapatılarak yaklaşık **{opt['total_potential_freed_mb']} MB** RAM kazanılabilir:\n"
            for p in opt['candidates']:
                report += f"- {p['name']} ({p['memory_mb']} MB)\n"
            report += "\nKapatmak için 'Onaylıyorum' veya 'Hepsini kapat' demen yeterli."
            return report
            
        # Default: Full Status Report
        status = tm.get_system_status()
        disks_str = "\n".join([f"- 💾 {d}" for d in status.get('disks', [])])
        if not disks_str: disks_str = "- Disk verisi alınamadı"

        report = (f"💻 **Sistem Durumu:**\n"
                  f"- 🕒 Sistem Açık: {status.get('uptime', 'N/A')}\n"
                  f"- 🔥 CPU: %{status['cpu_percent']} (Sıcaklık: {status.get('cpu_temp', 'N/A')})\n"
                  f"- 🎮 GPU: {status.get('gpu', 'N/A')}\n"
                  f"- 🧠 RAM: %{status['ram_percent']} ({status['ram_used_gb']} GB / {status['ram_total_gb']} GB)\n"
                  f"- 🔋 Pil: {status['battery']}\n"
                  f"\n**Disk Durumu:**\n{disks_str}")
        return report

    def _agent_system(self, prompt):
        model = self.agents.get("system_engineer", "qwen2.5-coder:7b")
        try:
            print(f"SİSTEM MÜHENDİSİ ({model}) devrede...")
        except: pass        
        
        # Detect Paths dynamically
        user_profile = os.path.expanduser("~")
        onedrive = os.path.join(user_profile, "OneDrive")
        
        # Determine actual Desktop path
        if os.path.exists(os.path.join(onedrive, "Desktop")):
            desktop_path = os.path.join(onedrive, "Desktop")
            docs_path = os.path.join(onedrive, "Documents")
        else:
            desktop_path = os.path.join(user_profile, "Desktop")
            docs_path = os.path.join(user_profile, "Documents")

        # Convert to PowerShell friendly format (no double backslashes needed for prompt text, but good for clarity)
        # We will tell the AI to use these specific paths.
        
        sys_prompt = (
            f"Sen JARVIS Sistem Kontrol Modülüsün.\n"
            f"Görevin: Kullanıcının isteğini yerine getirmek için TEK DOĞRU PowerShell komutunu oluşturmak.\n"
            f"\n"
            f"ÖNEMLİ YOL BİLGİLERİ:\n"
            f"- Masaüstü: \"{desktop_path}\"\n"
            f"- Belgelerim: \"{docs_path}\"\n"
            f"- Kullanıcı Dizini: \"{user_profile}\"\n"
            f"- Temp: \"$env:TEMP\"\n"
            f"- İndirilenler: \"{user_profile}\\Downloads\"\n"
            f"\n"
            f"KESİN KURALLAR:\n"
            f"1. Masaüstü dendiğinde: \"{desktop_path}\" kullan.\n"
            f"2. MUTLAKA ```powershell``` bloğu içinde komut yaz.\n"
            f"3. SİLME işlemi için SADECE Remove-Item kullan. ASLA Clear-Content kullanma.\n"
            f"4. Web sitesi açarken ASLA tarayıcı yolu yazma (chrome.exe gibi). Sadece Start-Process URL ver.\n"
            f"5. Emin olmadığın parametre EKLEME.\n"
            f"6. Kısa açıklama + komut bloğu formatında cevap ver.\n"
            f"\n"
            f"======= HAZIR KOMUT KÜTÜPHANESİ (BİREBİR KULLAN) =======\n"
            f"\n"
            f"--- WEB SİTELERİ AÇMA ---\n"
            f"\"YouTube aç\" -> Start-Process \"https://www.youtube.com\"\n"
            f"\"YouTube'da X ara\" -> Start-Process \"https://www.youtube.com/results?search_query=X\"\n"
            f"\"Google aç\" -> Start-Process \"https://www.google.com\"\n"
            f"\"Google'da X ara\" -> Start-Process \"https://www.google.com/search?q=X\"\n"
            f"\"Instagram aç\" -> Start-Process \"https://www.instagram.com\"\n"
            f"\"Twitter aç\" -> Start-Process \"https://x.com\"\n"
            f"\"WhatsApp Web aç\" -> Start-Process \"https://web.whatsapp.com\"\n"
            f"\"Gmail aç\" -> Start-Process \"https://mail.google.com\"\n"
            f"\"ChatGPT aç\" -> Start-Process \"https://chat.openai.com\"\n"
            f"\"Reddit aç\" -> Start-Process \"https://www.reddit.com\"\n"
            f"\"Wikipedia aç\" -> Start-Process \"https://tr.wikipedia.org\"\n"
            f"\"Haber sitesi aç\" -> Start-Process \"https://www.hurriyet.com.tr\"\n"
            f"\n"
            f"--- UYGULAMALAR AÇMA ---\n"
            f"\"Hesap makinesi\" -> Start-Process calc\n"
            f"\"Not defteri\" -> Start-Process notepad\n"
            f"\"Paint\" -> Start-Process mspaint\n"
            f"\"Dosya gezgini\" -> Start-Process explorer\n"
            f"\"Görev yöneticisi\" -> Start-Process taskmgr\n"
            f"\"Ayarlar\" -> Start-Process ms-settings:\n"
            f"\"Kontrol paneli\" -> Start-Process control\n"
            f"\"Komut satırı\" -> Start-Process cmd\n"
            f"\"PowerShell\" -> Start-Process powershell\n"
            f"\"Snipping Tool\" -> Start-Process SnippingTool\n"
            f"\"Word\" -> Start-Process winword\n"
            f"\"Excel\" -> Start-Process excel\n"
            f"\"Spotify\" -> Start-Process spotify\n"
            f"\"Discord\" -> Start-Process discord\n"
            f"\"Steam\" -> Start-Process steam\n"
            f"\"VS Code\" -> Start-Process code\n"
            f"\n"
            f"--- UYGULAMA KAPATMA ---\n"
            f"\"Chrome kapat\" -> Stop-Process -Name \"chrome\" -Force -ErrorAction SilentlyContinue\n"
            f"\"Firefox kapat\" -> Stop-Process -Name \"firefox\" -Force -ErrorAction SilentlyContinue\n"
            f"\"Discord kapat\" -> Stop-Process -Name \"Discord\" -Force -ErrorAction SilentlyContinue\n"
            f"\"Spotify kapat\" -> Stop-Process -Name \"Spotify\" -Force -ErrorAction SilentlyContinue\n"
            f"\"Tüm tarayıcıları kapat\" -> Stop-Process -Name \"chrome\",\"msedge\",\"firefox\" -Force -ErrorAction SilentlyContinue\n"
            f"\n"
            f"--- DOSYA/KLASÖR İŞLEMLERİ ---\n"
            f"\"Masaüstünde X klasörü oluştur\" -> New-Item -Path \"{desktop_path}\\X\" -ItemType Directory -Force\n"
            f"\"Masaüstünde X.txt dosyası oluştur\" -> New-Item -Path \"{desktop_path}\\X.txt\" -ItemType File -Force\n"
            f"\"X klasörünü sil\" -> Remove-Item -Path \"{desktop_path}\\X\" -Recurse -Force\n"
            f"\"X dosyasını sil\" -> Remove-Item -Path \"{desktop_path}\\X\" -Force\n"
            f"\"İndirilenler klasörünü aç\" -> Start-Process \"{user_profile}\\Downloads\"\n"
            f"\"Belgelerim'i aç\" -> Start-Process \"{docs_path}\"\n"
            f"\"Masaüstünü aç\" -> Start-Process \"{desktop_path}\"\n"
            f"\n"
            f"--- TEMİZLİK ---\n"
            f"\"Temp temizle\" -> Remove-Item -Path \"$env:TEMP\\*\" -Recurse -Force -ErrorAction SilentlyContinue\n"
            f"\"Geri dönüşüm kutusunu boşalt\" -> Clear-RecycleBin -Force -ErrorAction SilentlyContinue\n"
            f"\"İndirilenler temizle\" -> Remove-Item -Path \"{user_profile}\\Downloads\\*\" -Recurse -Force -ErrorAction SilentlyContinue\n"
            f"\n"
            f"--- SES/PARLAKLIK ---\n"
            f"\"Sesi kapat\" -> (New-Object -ComObject WScript.Shell).SendKeys([char]173)\n"
            f"\"Sesi aç\" -> (New-Object -ComObject WScript.Shell).SendKeys([char]175)\n"
            f"\"Sesi arttır\" -> (New-Object -ComObject WScript.Shell).SendKeys([char]175)\n"
            f"\"Sesi azalt\" -> (New-Object -ComObject WScript.Shell).SendKeys([char]174)\n"
            f"\n"
            f"--- SİSTEM İŞLEMLERİ ---\n"
            f"\"Bilgisayarı kapat\" -> Stop-Computer -Force\n"
            f"\"Yeniden başlat\" -> Restart-Computer -Force\n"
            f"\"Uyku modu\" -> rundll32.exe powrprof.dll,SetSuspendState 0,1,0\n"
            f"\"Ekranı kilitle\" -> rundll32.exe user32.dll,LockWorkStation\n"
            f"\"WiFi kapat\" -> netsh interface set interface \"Wi-Fi\" disable\n"
            f"\"WiFi aç\" -> netsh interface set interface \"Wi-Fi\" enable\n"
            f"\"IP adresimi göster\" -> Get-NetIPAddress -AddressFamily IPv4 | Select-Object IPAddress, InterfaceAlias\n"
            f"\"Tarih/Saat göster\" -> Get-Date -Format 'dd MMMM yyyy, dddd HH:mm:ss'\n"
        )
        
        res = ollama.chat(model=model, messages=[
            {'role': 'system', 'content': sys_prompt},
            {'role': 'user', 'content': prompt}
        ])
        
        content = res['message']['content']
        formatted_content = self._format_response(res)
        
        # Parse and Execute
        # Regex to find powershell code block
        cmd_match = re.search(r"```(powershell)?\s+(.*?)\s+```", content, re.DOTALL | re.IGNORECASE)
        
        execution_result = ""
        
        if cmd_match:
            # Group 2 captures the code content regardless of whether 'powershell' label exists
            command = cmd_match.group(2).strip()
            try:
                print(f"JARVIS SISTEM KOMUTU: {command}")
                
                process = subprocess.run(
                    ["powershell", "-Command", command], 
                    capture_output=True, 
                    text=True,
                    encoding='cp857', # Try Turkish command line encoding first, or 'utf-8' if chcp 65001
                    errors='replace', # CRITICAL: Prevent crash on weird characters
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                )
                
                output = process.stdout.strip()
                error = process.stderr.strip()
                
                if process.returncode == 0:
                    execution_result = f"\n\n✅ **İşlem Tamamlandı**"
                    if output: execution_result += f"\n```\n{output}\n```"
                else:
                    execution_result = f"\n\n⚠️ **Bir Sorun Oluştu**\n```\n{error}\n```"
                    
            except Exception as e:
                execution_result = f"\n\n❌ **Sistem Hatası:** {str(e)}"
        
        return f"**JARVIS System:**\n\n{formatted_content}{execution_result}"

    def _agent_coding(self, prompt):
        model = self.agents.get("lead_dev", "deepseek-coder:6.7b")
        try:
            print(f"BAŞ YAZILIMCI ({model}) devrede...")
        except: pass
        
        sys_prompt = (
            "Sen JARVIS Baş Yazılımcı Modülüsün. Üst düzey bir yazılım mühendisisin.\n"
            "\n"
            "KİMLİĞİN:\n"
            "- Adın JARVIS Code Engine.\n"
            "- 10+ yıl deneyimli bir senior developer gibi davran.\n"
            "- Temiz, okunabilir, optimize kod yaz.\n"
            "\n"
            "KESİN KURALLAR:\n"
            "1. Kod bloklarını MUTLAKA dil belirterek yaz: ```python, ```javascript, ```html vb.\n"
            "2. Her fonksiyona kısa docstring ekle.\n"
            "3. Değişken isimleri açıklayıcı olsun (x, y değil; user_name, total_count gibi).\n"
            "4. Hata yönetimi (try/except) ekle.\n"
            "5. Önce KISA açıklama, sonra kod.\n"
            "6. Gereksiz yere uzun kod yazma. En kısa ve temiz çözümü ver.\n"
            "7. Kullanıcı hangi dil istiyorsa o dilde yaz.\n"
            "8. Dil belirtmezse Python kullan.\n"
            "9. Türkçe açıklama yap.\n"
            "\n"
            "DİL TESPİTİ:\n"
            "- 'Python' veya 'py' geçiyorsa -> Python\n"
            "- 'JavaScript' veya 'JS' geçiyorsa -> JavaScript\n"
            "- 'HTML' geçiyorsa -> HTML/CSS/JS\n"
            "- 'C#' veya 'csharp' geçiyorsa -> C#\n"
            "- 'Java' geçiyorsa -> Java\n"
            "- 'C++' geçiyorsa -> C++\n"
            "- 'SQL' geçiyorsa -> SQL\n"
            "- 'Bash' veya 'Shell' geçiyorsa -> Bash\n"
            "- 'PowerShell' geçiyorsa -> PowerShell\n"
            "- 'React' geçiyorsa -> React JSX\n"
            "- Belirtilmemişse -> Python\n"
            "\n"
            "GÖREV TİPLERİ:\n"
            "\n"
            "Kod yazma istekleri (X kodu yaz, X programı yap):\n"
            "- Çalışan, eksiksiz kod ver.\n"
            "- Import'ları eklemeyi unutma.\n"
            "- Örnek kullanım ekle.\n"
            "\n"
            "Hata düzeltme (Bu kodu düzelt, hata veriyor):\n"
            "- Önce hatayı açıkla.\n"
            "- Sonra düzeltilmiş kodu ver.\n"
            "- Neyi neden değiştirdiğini belirt.\n"
            "\n"
            "Kod açıklama (Bu kod ne yapıyor, açıkla):\n"
            "- Satır satır veya blok blok açıkla.\n"
            "- Basit Türkçe kullan.\n"
            "\n"
            "Optimizasyon (Bu kodu optimize et, hızlandır):\n"
            "- Önceki ve sonraki versiyonu göster.\n"
            "- Neden daha iyi olduğunu açıkla.\n"
            "\n"
            "ÖRNEK CEVAPLAR:\n"
            "\n"
            "Kullanıcı: 'Python ile dosya okuma kodu yaz'\n"
            "Sen:\n"
            "İşte dosya okuma kodu:\n"
            "```python\n"
            "def read_file(filepath):\n"
            "    \"\"\"Dosyayı okur ve içeriğini döndürür.\"\"\"\n"
            "    try:\n"
            "        with open(filepath, 'r', encoding='utf-8') as f:\n"
            "            return f.read()\n"
            "    except FileNotFoundError:\n"
            "        return 'Dosya bulunamadı'\n"
            "    except Exception as e:\n"
            "        return f'Hata: {e}'\n"
            "\n"
            "# Kullanım\n"
            "icerik = read_file('dosya.txt')\n"
            "print(icerik)\n"
            "```\n"
            "\n"
            "Kullanıcı: 'Web scraping kodu'\n"
            "Sen:\n"
            "```python\n"
            "import requests\n"
            "from bs4 import BeautifulSoup\n"
            "\n"
            "def scrape_page(url):\n"
            "    \"\"\"Verilen URL'den sayfa içeriğini çeker.\"\"\"\n"
            "    response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})\n"
            "    soup = BeautifulSoup(response.text, 'html.parser')\n"
            "    return soup.get_text()\n"
            "```\n"
        )
        
        res = ollama.chat(model=model, messages=[
            {'role': 'system', 'content': sys_prompt},
            {'role': 'user', 'content': prompt}
        ])
        return f"**Baş Yazılımcı:**\n\n{self._format_response(res)}"
    
    def _agent_analyst(self, prompt):
        model = self.agents.get("analyst", "llama3.1:8b")
        try:
            print(f"ANALİST ({model}) devrede...")
        except: pass
        
        sys_prompt = (
            "Sen JARVIS Veri Analizi Modülüsün. Deneyimli bir veri analistisin.\n"
            "\n"
            "KİMLİĞİN:\n"
            "- Adın JARVIS Analyst.\n"
            "- Veri okuma, yorumlama ve raporlama konusunda uzmanısın.\n"
            "- Her zaman VERİYE DAYALI konuş. Tahmin değil, analiz yap.\n"
            "\n"
            "KESİN KURALLAR:\n"
            "1. Verileri tablolar ve maddeler halinde sun.\n"
            "2. Sayısal verileri analiz ederken YÜZDE, ORTALAMA, TREND belirt.\n"
            "3. Karşılaştırma yaparken avantaj/dezavantaj listesi çıkar.\n"
            "4. Türkçe cevap ver.\n"
            "5. Kısa ve öz ol, ama önemli detayı atlama.\n"
            "6. Grafikler yerine metin tabanlı görselleştirme kullan (tablo, bar).\n"
            "\n"
            "ANALİZ TİPLERİ:\n"
            "\n"
            "Karşılaştırma analizi (X vs Y, hangisi daha iyi):\n"
            "- Tablo formatında karşılaştır.\n"
            "- Her kritere puan ver.\n"
            "- Sonuçta net bir tavsiye ver.\n"
            "\n"
            "Veri yorumlama (Bu verileri analiz et):\n"
            "- Trendi belirle (yükseliş/düşüş/sabit).\n"
            "- Anomalileri bul.\n"
            "- Sonuç ve öneriler sun.\n"
            "\n"
            "SWOT Analizi:\n"
            "- Güçlü yönler, Zayıf yönler, Fırsatlar, Tehditler.\n"
            "- Her kategori için 3-5 madde.\n"
            "\n"
            "Maliyet analizi (Bu ne kadara mal olur):\n"
            "- Kalem kalem maliyet listesi.\n"
            "- Toplam ve alternatifler.\n"
            "\n"
            "ÖRNEK CEVAP:\n"
            "Kullanıcı: 'iPhone vs Samsung karşılaştır'\n"
            "Sen:\n"
            "| Kriter | iPhone 15 | Samsung S24 |\n"
            "|--------|-----------|-------------|\n"
            "| Kamera | 48MP, doğal renkler | 200MP, canlı renkler |\n"
            "| Performans | A17 Pro yonga | Snapdragon 8 Gen 3 |\n"
            "| Batarya | 3349 mAh | 4000 mAh |\n"
            "| Fiyat | Yüksek | Orta-Yüksek |\n"
            "**Sonuç:** Kamera ve batarya ömrü öncelikli ise Samsung, ekosistem ve uzun süreli güncelleme ise iPhone.\n"
        )
        
        res = ollama.chat(model=model, messages=[
            {'role': 'system', 'content': sys_prompt},
            {'role': 'user', 'content': prompt}
        ])
        return f"**Veri Analisti:**\n\n{self._format_response(res)}"

    def _agent_math(self, prompt):
        """
        Translates Natural Language to Python Expression -> Executes it.
        Example: "500 carpi 5" -> "500 * 5" -> 2500
        """
        import math
        
        # Use Commander or System Engineer for fast translation
        # qwen2.5:1.5b is fast enough for this simple task
        model = self.agents.get("commander", "qwen2.5:1.5b")
        
        sys_prompt = (
            "Görevin: Verilen Türkçe metni TEK BİR geçerli Python matematiksel ifadesine çevirmek.\n"
            "\n"
            "KESİN KURALLAR:\n"
            "1. SADECE matematiksel ifadeyi yaz. Hiçbir açıklama, yorum, metin ekleme.\n"
            "2. 'print' kullanma. Sadece ifade.\n"
            "3. math kütüphanesini 'math' olarak kullanabilirsin.\n"
            "4. Sonuç her zaman TEK SATIR olmalı.\n"
            "5. Çıktında SADECE Python ifadesi olsun, başka hiçbir şey olmasın.\n"
            "\n"
            "=== TEMEL İŞLEMLER ===\n"
            "\"5 artı 5\" -> 5 + 5\n"
            "\"10 eksi 3\" -> 10 - 3\n"
            "\"500 çarpı 5\" -> 500 * 5\n"
            "\"100 bölü 4\" -> 100 / 4\n"
            "\"7 kere 8\" -> 7 * 8\n"
            "\"15 artı 20\" -> 15 + 20\n"
            "\"1000 eksi 750\" -> 1000 - 750\n"
            "\n"
            "=== ÜS ALMA / KARE / KÜP ===\n"
            "\"5'in karesi\" -> 5 ** 2\n"
            "\"3'ün küpü\" -> 3 ** 3\n"
            "\"2 üzeri 10\" -> 2 ** 10\n"
            "\"15'in karesi\" -> 15 ** 2\n"
            "\"4'ün 5. kuvveti\" -> 4 ** 5\n"
            "\n"
            "=== KAREKÖK / KÖK ===\n"
            "\"100'ün karekökü\" -> math.sqrt(100)\n"
            "\"karekök 144\" -> math.sqrt(144)\n"
            "\"64'ün karekökü\" -> math.sqrt(64)\n"
            "\"27'nin küp kökü\" -> 27 ** (1/3)\n"
            "\n"
            "=== YÜZDE HESAPLAMA ===\n"
            "\"500'ün yüzde 20'si\" -> 500 * 20 / 100\n"
            "\"1000'in yüzde 15'i\" -> 1000 * 15 / 100\n"
            "\"yüzde 8 hesapla 250\" -> 250 * 8 / 100\n"
            "\"200'ün yüzde kaçı 50\" -> (50 / 200) * 100\n"
            "\n"
            "=== TRİGONOMETRİ ===\n"
            "\"sinüs 90 derece\" -> math.sin(math.radians(90))\n"
            "\"sinus 30\" -> math.sin(math.radians(30))\n"
            "\"kosinüs 60\" -> math.cos(math.radians(60))\n"
            "\"tanjant 45\" -> math.tan(math.radians(45))\n"
            "\n"
            "=== SABİTLER ===\n"
            "\"pi sayısı\" -> math.pi\n"
            "\"e sayısı\" -> math.e\n"
            "\"pi çarpı 2\" -> math.pi * 2\n"
            "\n"
            "=== MUTLAK DEĞER / YUVARLAMA ===\n"
            "\"-15'in mutlak değeri\" -> abs(-15)\n"
            "\"3.7'yi yuvarla\" -> round(3.7)\n"
            "\"pi'yi 4 basamağa yuvarla\" -> round(math.pi, 4)\n"
            "\n"
            "=== LOGARİTMA / FAKTÖRİYEL ===\n"
            "\"10'un logaritması\" -> math.log10(10)\n"
            "\"doğal logaritma 5\" -> math.log(5)\n"
            "\"5 faktöriyel\" -> math.factorial(5)\n"
            "\"10 faktöriyel\" -> math.factorial(10)\n"
            "\n"
            "=== KARMAŞIK İŞLEMLER ===\n"
            "\"5 artı 3 çarpı 2\" -> 5 + 3 * 2\n"
            "\"parantez 5 artı 3 parantez kapat çarpı 2\" -> (5 + 3) * 2\n"
            "\"100 bölü 5 artı 20\" -> 100 / 5 + 20\n"
            "\"bin çarpı bin\" -> 1000 * 1000\n"
            "\"bir milyon bölü 7\" -> 1000000 / 7\n"
        )
        
        try:
            # 1. Translate
            res = ollama.chat(model=model, messages=[
                {'role': 'system', 'content': sys_prompt},
                {'role': 'user', 'content': prompt}
            ])
            expr = res['message']['content'].strip().replace("`", "").replace("python", "")
            
            # Debug log
            try: print(f"MATH TRANSLATION: {prompt} -> {expr}")
            except: pass
            
            # 2. Execute
            safe_dict = {"__builtins__": None, "math": math, "abs": abs, "round": round, "min": min, "max": max, "pow": pow}
            result = eval(expr, safe_dict)
            
            # 3. Return (Standard text format, metrics handled by manager if added later, but here we return strict string)
            return f"{result}"
            
        except Exception as e:
            return f"Hesaplama Hatasi: {e}"

    def _agent_vision(self, prompt):
        # Vision usually requires image input. This handles text-only trigger for now.
        return "Gözcü Modu için lütfen bir resim yükleyin veya ekran görüntüsü modunu kullanın."
