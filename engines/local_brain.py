
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

# --- FEATURE: local_brain ---
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
                "chat": "qwen3.5:9b",
                "system_engineer": "qwen3-coder:4b",
                "lead_dev": "qwen3-coder:7b",
                "vision": "moondream",
                "analyst": "llama3.1:8b",
                "math": "qwen3-math:1.5b",
                "painter": "qwen3.5:9b" # Using chat model to refine prompt
            }

    def process_request(self, prompt: str, history=None, progress_callback=None, memory_context=None):
        """
        Main entry point for Local Brain.
        KOMUTAN (phi4-mini) analyzes intent with massive training prompt.
        """
        try:
            print(f"MERKEZ: Istek alindi -> '{prompt}'")
        except: pass
        
        # Sohbet baglamini komutana da ver ki takip sorularini anlasin
        # Ornek: "galatasaray bu sezon kac gol atti" -> SEARCH
        #        "peki kac gol yedi" -> SEARCH (cunku onceki soru galatasaray hakkindaydi)
        context_hint = ""
        if history and len(history) >= 2:
            # Son 3 mesaji komutana baglamsal ipucu olarak ver
            recent_msgs = history[-4:-1]  # son mesaj haric (o zaten prompt)
            if recent_msgs:
                context_lines = []
                for m in recent_msgs:
                    role_label = "Kullanici" if m.get('role') == 'user' else "Asistan"
                    text_preview = m.get('text', '')[:100]
                    context_lines.append(f"{role_label}: {text_preview}")
                context_hint = "\n".join(context_lines)
        
        # KOMUTAN (TEK YETKILI ROUTER)
        intent = self._consult_commander(prompt, context_hint=context_hint)
        try: print(f"KOMUTAN ANALIZI: {intent}")
        except: pass
        
        # ROUTING — tum ajanlara history gonderiyoruz
        if intent == "IMAGE":
            return self._agent_image_department(prompt, progress_callback=progress_callback)
        elif intent == "BROWSER":
            return self._agent_browser(prompt)
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
            return self._agent_chat(prompt, history=history, memory_context=memory_context)

    
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

    def _consult_commander(self, prompt, context_hint=""):
        """
        Uses phi4-mini to classify intent.
        Output expected: STRICTLY ONE WORD INTENT
        """
        commander_model = self.agents.get("commander", "phi4-mini")
        
        sys_prompt = (
            "SEN BIR SINIFLANDIRICI ROBOTSUN. GOREVIN: Kullanicinin istegini analiz edip KATEGORILERDEN SADECE BIRINI SECMEK.\n"
            "\n"
            "KATEGORILER:\n"
            "- BROWSER = Web sitesinde ISLEM yapmak (arama, tiklama, video izleme, alisveris). 'X'da Y ara' = BROWSER.\n"
            "- SYSTEM = Masaustu uygulamasi ACMAK/KAPATMAK, dosya/klasor islemleri, SES/PARLAKLIK ayari, bilgisayar kapat/yeniden baslat.\n"
            "- SYSTEM_REPORT = Bilgisayarin MEVCUT DURUMUNU sorgulamak (CPU, RAM kullanimi, disk dolulugu, pil, sicaklik, kasiyor, yavasliyor).\n"
            "- IMAGE = Resim/gorsel URETMEK (cizim, logo, illustrasyon).\n"
            "- CODING = Kod/script/program YAZMAK veya DUZELTMEK. 'kod yaz', 'script yaz', 'program yap' = CODING.\n"
            "- VISION = Ekrani GORMEK/okumak.\n"
            "- MATH = Matematiksel HESAPLAMA. Sayi + islem iceren ifadeler (arti, eksi, carpi, bolu, karekok, yuzde).\n"
            "- SEARCH = Internette GUNCEL bilgi aramak (hava durumu, doviz kuru, fiyat, mac skoru, haber, deprem).\n"
            "- CHAT = SOHBET, genel kultur, tavsiye, oneri, tanim. Internete gerek OLMAYAN her sey.\n"
            "\n"
            "!!! SADECE TEK KELIME YAZ !!!\n"
            "\n"
            "=== KRITIK KURALLAR (SIRASINA DIKKAT ET) ===\n"
            "\n"
            "KURAL 1 - SAYI + ISLEM = MATH:\n"
            "Eger mesajda SAYI ve ISLEM varsa (arti, eksi, carpi, bolu, karekok, yuzde, kac eder) -> MATH\n"
            "\"500 arti 200\" -> MATH (SEARCH degil!)\n"
            "\"100 bolu 5\" -> MATH (SEARCH degil!)\n"
            "\n"
            "KURAL 2 - KOD/SCRIPT/PROGRAM YAZMA = CODING:\n"
            "Eger 'kod yaz', 'script yaz', 'program yap', 'fonksiyon yaz', 'kodu duzelt' gibi ifade varsa -> CODING\n"
            "\"Python kodu yaz\" -> CODING (SEARCH degil!)\n"
            "\"Bana python kodu yaz\" -> CODING (SEARCH degil!)\n"
            "\n"
            "KURAL 3 - BILGISAYAR DURUMU = SYSTEM_REPORT:\n"
            "Eger mesaj bilgisayarin MEVCUT durumunu soruyorsa (RAM dolu mu, CPU kac, sistem durumu, ne kasiyor, disk dolulugu) -> SYSTEM_REPORT\n"
            "\"Sistem durumu ne\" -> SYSTEM_REPORT (CHAT degil!)\n"
            "\"RAM ne kadar dolu\" -> SYSTEM_REPORT (SEARCH degil!)\n"
            "\"PC nasil\" -> SYSTEM_REPORT\n"
            "\n"
            "KURAL 4 - SES/PARLAKLIK/KAPAMA = SYSTEM:\n"
            "Eger mesaj ses, parlaklik, WiFi, Bluetooth, bilgisayar kapatma/yeniden baslatma ile ilgiliyse -> SYSTEM\n"
            "\"Sesi ac\" -> SYSTEM (CHAT degil!)\n"
            "\"Sesi kis\" -> SYSTEM\n"
            "\"Parlaklik arttir\" -> SYSTEM\n"
            "\n"
            "KURAL 5 - SITEDE ISLEM YAPMA = BROWSER:\n"
            "Eger mesajda 'X'da/X'ta + bir islem' varsa (orn: Google'da ara, YouTube'da izle) -> BROWSER\n"
            "\"Google'da hava durumu ara\" -> BROWSER (SEARCH degil! Cunku Google'da ISLEM yapmak istiyor)\n"
            "\"YouTube'da muzik ac\" -> BROWSER\n"
            "\n"
            "KURAL 6 - TANIM/ONERI/TAVSIYE = CHAT:\n"
            "Eger mesaj 'X nedir', 'X ne ise yarar', 'oneri ver', 'tavsiye' iceriyorsa -> CHAT\n"
            "\"Spotify nedir\" -> CHAT (SEARCH degil!)\n"
            "\"Film onerisi ver\" -> CHAT (SEARCH degil!)\n"
            "\"RAM ne ise yarar\" -> CHAT (MATH degil! SEARCH degil!)\n"
            "\n"
            "KURAL 7 - SEARCH SADECE GUNCEL VERI ICIN:\n"
            "SEARCH sadece su durumlarda: hava durumu, doviz kuru, canli mac skoru, guncel haber, deprem, fiyat\n"
            "Tanim sorusu SEARCH DEGILDIR. Oneri SEARCH DEGILDIR. Kod yazma SEARCH DEGILDIR. Hesaplama SEARCH DEGILDIR.\n"
            "\n"
            "=== ORNEKLER ===\n"
            "\n"
            "BROWSER:\n"
            "\"YouTube'da muzik ac\" -> BROWSER\n"
            "\"Amazonda telefon ara\" -> BROWSER\n"
            "\"Google'da hava durumu ara\" -> BROWSER\n"
            "\"Google'da X ara\" -> BROWSER\n"
            "\"Instagrama gir\" -> BROWSER\n"
            "\"Gmail'i ac\" -> BROWSER\n"
            "\"WhatsApp Web ac\" -> BROWSER\n"
            "\n"
            "SYSTEM:\n"
            "\"Spotify ac\" -> SYSTEM\n"
            "\"Chrome'u kapat\" -> SYSTEM\n"
            "\"Masaustune klasor olustur\" -> SYSTEM\n"
            "\"Dosya sil\" -> SYSTEM\n"
            "\"Sesi ac\" -> SYSTEM\n"
            "\"Sesi kis\" -> SYSTEM\n"
            "\"Bilgisayari kapat\" -> SYSTEM\n"
            "\"Bilgisayari yeniden baslat\" -> SYSTEM\n"
            "\"WiFi kapat\" -> SYSTEM\n"
            "\n"
            "SYSTEM_REPORT:\n"
            "\"Sistem durumu ne\" -> SYSTEM_REPORT\n"
            "\"PC durumu\" -> SYSTEM_REPORT\n"
            "\"RAM ne kadar dolu\" -> SYSTEM_REPORT\n"
            "\"Ne kasiyor\" -> SYSTEM_REPORT\n"
            "\"Diskimi ne dolduruyor\" -> SYSTEM_REPORT\n"
            "\"Oyun modu\" -> SYSTEM_REPORT\n"
            "\"RAM temizle\" -> SYSTEM_REPORT\n"
            "\"CPU yuzde kac\" -> SYSTEM_REPORT\n"
            "\n"
            "SEARCH:\n"
            "\"Hava nasil\" -> SEARCH\n"
            "\"Dolar kac TL\" -> SEARCH\n"
            "\"Galatasaray mac skoru\" -> SEARCH\n"
            "\"Guncel haberler\" -> SEARCH\n"
            "\"Deprem mi oldu\" -> SEARCH\n"
            "\"Benzin fiyati\" -> SEARCH\n"
            "\n"
            "IMAGE:\n"
            "\"Kedi resmi ciz\" -> IMAGE\n"
            "\"Logo tasarla\" -> IMAGE\n"
            "\"Gorsel olustur\" -> IMAGE\n"
            "\n"
            "CODING:\n"
            "\"Python kodu yaz\" -> CODING\n"
            "\"Bana python kodu yaz\" -> CODING\n"
            "\"Bu kodu duzelt\" -> CODING\n"
            "\"HTML sayfasi olustur\" -> CODING\n"
            "\"Script yaz\" -> CODING\n"
            "\n"
            "MATH:\n"
            "\"5 arti 3 kac\" -> MATH\n"
            "\"500 arti 200\" -> MATH\n"
            "\"Karekok 144\" -> MATH\n"
            "\"Yuzde hesapla\" -> MATH\n"
            "\"100 bolu 7\" -> MATH\n"
            "\n"
            "VISION:\n"
            "\"Ekrana bak\" -> VISION\n"
            "\"Ne goruyorsun\" -> VISION\n"
            "\n"
            "CHAT:\n"
            "\"Nasilsin\" -> CHAT\n"
            "\"Merhaba\" -> CHAT\n"
            "\"YouTube kac yilinda kuruldu\" -> CHAT\n"
            "\"Spotify nedir\" -> CHAT\n"
            "\"Film onerisi ver\" -> CHAT\n"
            "\"RAM ne ise yarar\" -> CHAT\n"
            "\"Yapay zeka nedir\" -> CHAT\n"
            "\"Einstein kimdir\" -> CHAT\n"
            "\"Tavsiye ver\" -> CHAT\n"
            "\"Laptop onerisi\" -> CHAT\n"
            "\n"
            "!!! SADECE TEK KELIME YAZ !!!\n"
            "Gecerli ciktilar: BROWSER, SYSTEM, SYSTEM_REPORT, IMAGE, CODING, VISION, MATH, SEARCH, CHAT"
        )
        
        try:
            # Takip sorularini anlamak icin onceki sohbet baglamini ekle
            user_msg = prompt
            if context_hint:
                user_msg = f"[ONCEKI SOHBET BAGLAMI]:\n{context_hint}\n\n[YENI MESAJ]: {prompt}"
            
            response = ollama.chat(model=commander_model, messages=[
                {'role': 'system', 'content': sys_prompt},
                {'role': 'user', 'content': user_msg}
            ])
            content = response['message']['content'].upper().strip()
            
            # Strip reasoning tags from phi4-mini-reasoning (e.g. <THINK>...</THINK>)
            content = re.sub(r'<THINK>.*?</THINK>', '', content, flags=re.DOTALL | re.IGNORECASE).strip()
            # Ek temizlik: satir sonu, fazla bosluk, noktalama
            content = re.sub(r'[\n\r\t.,;:!?]', ' ', content).strip()
            content = re.sub(r'\s+', ' ', content)
            
            # Bilinen keyword'lerden ilkini bul (SYSTEM_REPORT, SYSTEM sirasi onemli!)
            valid_keywords = ["BROWSER", "SYSTEM_REPORT", "SYSTEM", "IMAGE", "CODING", "VISION", "MATH", "SEARCH", "CHAT"]
            for keyword in valid_keywords:
                if keyword in content:
                    return keyword
            
            return "CHAT" # Default if unrecognized
        except:
            return "CHAT" # Fallback

    def _agent_browser(self, prompt):
        """BROWSER Agent: Tarayici kontrolu."""
        try:
            import concurrent.futures
            
            def run_browser_task():
                from engines.browser_agent import BrowserAgent
                from engines.browser_engine import BrowserEngine
                from ui.browser_overlay import BrowserOverlay
                
                agent = BrowserAgent()
                engine = BrowserEngine()
                overlay = BrowserOverlay()
                engine.set_overlay(overlay)
                
                # Plan olustur
                plan = agent.create_plan(prompt)
                if not plan:
                    return "Tarayici plani olusturulamadi. Lutfen istegi daha net belirtin."
                
                # Tarayiciyi baslat ve plani calistir
                engine.launch()
                result = engine.execute_plan(plan)
                
                # Sonucu raporla
                page_title = engine.get_page_title()
                current_url = engine.get_current_url()
                
                steps_ok = result['steps_completed']
                steps_total = result['total_steps']
                
                if result['success']:
                    report = f"**Tarayici Gorevi Tamamlandi**\n"
                    report += f"- Sayfa: {page_title}\n"
                    report += f"- URL: {current_url}\n"
                    report += f"- Adimlar: {steps_ok}/{steps_total} basarili"
                else:
                    # Basarisiz adimlar varsa screenshot al ve replan dene
                    report = f"**Tarayici Gorevi Kismi Basarili**\n"
                    report += f"- {steps_ok}/{steps_total} adim tamamlandi\n"
                    
                    # Hatalari listele
                    for r in result['results']:
                        if not r['success'] and r['error']:
                            report += f"- Adim {r['step']}: {r['error']}\n"
                    
                    report += f"\nSayfa: {page_title} ({current_url})"
                
                # NOT: Tarayiciyi acik birak — kullanici kapatmak isterse soyleyecek
                return report

            # Playwright Sync API cannot block an existing asyncio loop.
            # Running the entire task inside a fresh thread solves it.
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(run_browser_task)
                return future.result()
            
        except Exception as e:
            return f"Tarayici kontrol hatasi: {str(e)}"

    def _agent_image_department(self, prompt, progress_callback=None):
        """Image generation has been disabled"""
        return "Görsel oluşturma özelliği şu an devre dışı bırakılmıştır."

    def _format_search_results(self, results, user_search):
        """Ollama web_search/web_fetch sonuclarini okunabilir formata cevir."""
        from ollama import WebSearchResponse, WebFetchResponse
        output = []
        if isinstance(results, WebSearchResponse):
            output.append(f'Arama sonuclari: "{user_search}":')
            for result in results.results:
                output.append(f'{result.title}' if result.title else f'{result.content}')
                output.append(f'   URL: {result.url}')
                output.append(f'   Icerik: {result.content}')
                output.append('')
            return '\n'.join(output).rstrip()
        elif isinstance(results, WebFetchResponse):
            output.append(f'Sayfa icerigi: "{user_search}":')
            output.extend([
                f'Baslik: {results.title}',
                f'URL: {user_search}' if user_search else '',
                f'Icerik: {results.content}',
            ])
            if results.links:
                output.append(f'Linkler: {", ".join(results.links[:10])}')
            output.append('')
            return '\n'.join(output).rstrip()
        return str(results)

    def _agent_search(self, prompt, history=None):
        """
        SEARCH Agent: Güncel/gerçek bilgi gerektiren sorular için.
        Ollama resmi web-search örneğine dayalı (think=True, tool-calling).
        """
        from ollama import chat, web_search, web_fetch
        from datetime import datetime
        
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
        
        # ===== OLLAMA TOOL-CALLING SEARCH AGENT =====
        try:
            print(f"OLLAMA SEARCH AGENT devrede... Sorgu: '{prompt}'")
        except: pass
        
        available_tools = {'web_search': web_search, 'web_fetch': web_fetch}
        
        sys_prompt = (
            f"Sen JARVIS'sin. Kullanıcıya GÜNCEL ve DOĞRU bilgi veren bir arama asistanısın. "
            f"Sana verilen araçları (web_search, web_fetch) kullanarak internetten bilgi bul. "
            f"HER ZAMAN önce web_search aracını kullanarak arama yap. "
            f"Bugünün tarihi: {tarih_str}, Saat: {saat_str}. "
            f"ASLA bilgi uydurmak yok. "
            f"Kullanıcıya 'Efendim' diye hitap et. Türkçe cevap ver.\n"
            f"\n"
            f"CEVAP KURALLARI:\n"
            f"- SADECE sorulan şeye cevap ver. Uzun açıklama yapma.\n"
            f"- Maç skoru soruluyorsa: skor, tarih, stad yeterli. Gol listesi, detay VERME.\n"
            f"- Fiyat soruluyorsa: sadece fiyatı ver.\n"
            f"- Hava durumu soruluyorsa: sadece derece ve durum ver.\n"
            f"- Eğer kullanıcı isterse detay verebileceğini kısaca belirt. Örnek: 'Detayları ister misiniz efendim?'\n"
            f"- Cevap MAKSIMUM 3-4 satır olsun. Paragraf yazma.\n"
        )
        
        # Mesaj geçmişini oluştur
        messages = [{'role': 'system', 'content': sys_prompt}]
        
        # Takip sorulari icin onceki sohbet baglamini ekle
        if history and len(history) > 0:
            recent = history[-6:]
            for m in recent:
                role = 'user' if m['role'] == 'user' else 'assistant'
                messages.append({'role': role, 'content': m['text']})
        
        # Eğer son mesaj zaten prompt değilse ekle
        if not messages or messages[-1].get('content') != prompt:
            messages.append({'role': 'user', 'content': prompt})
        
        try:
            # Tool-calling agent loop (max 5 iterasyon)
            max_iterations = 5
            for i in range(max_iterations):
                response = chat(
                    model=model,
                    messages=messages,
                    tools=[web_search, web_fetch],
                    think=True
                )
                
                # Thinking varsa logla
                if hasattr(response.message, 'thinking') and response.message.thinking:
                    try:
                        print(f"SEARCH AGENT dusunuyor (iterasyon {i+1})...")
                    except: pass
                
                if response.message.content:
                    try:
                        print(f"SEARCH AGENT cevap verdi (iterasyon {i+1})")
                    except: pass
                
                messages.append(response.message)
                
                # Tool call varsa isle
                if response.message.tool_calls:
                    try:
                        print(f"SEARCH AGENT tool call (iterasyon {i+1}): {[tc.function.name for tc in response.message.tool_calls]}")
                    except: pass
                    
                    for tool_call in response.message.tool_calls:
                        function_to_call = available_tools.get(tool_call.function.name)
                        if function_to_call:
                            args = tool_call.function.arguments
                            result = function_to_call(**args)
                            
                            # Sonuclari formatla (resmi ornekteki gibi)
                            user_search = args.get('query', '') or args.get('url', '')
                            formatted = self._format_search_results(result, user_search)
                            
                            try:
                                print(f"Tool sonucu ({tool_call.function.name}): {formatted[:200]}...")
                            except: pass
                            
                            # ~2000 token siniri (resmi ornekteki gibi)
                            messages.append({
                                'role': 'tool',
                                'content': formatted[:2000 * 4],
                                'tool_name': tool_call.function.name
                            })
                        else:
                            messages.append({
                                'role': 'tool',
                                'content': f'Tool {tool_call.function.name} bulunamadi',
                                'tool_name': tool_call.function.name
                            })
                else:
                    # Tool call yoksa donguden cik
                    break
            
            # Son mesajdan cevabı al
            final_content = response.message.content if response.message.content else ""
            
            if not final_content:
                return "Arama sonuçlarını işleyemedim efendim. Lütfen sorunuzu farklı şekilde sorun."
            
            return final_content
            
        except Exception as e:
            error_msg = str(e)
            try:
                print(f"SEARCH AGENT Hata: {error_msg}")
            except: pass
            
            # API key hatası için özel mesaj
            if "api_key" in error_msg.lower() or "unauthorized" in error_msg.lower() or "401" in error_msg:
                return ("Arama yapılamadı: Ollama API anahtarı ayarlanmamış. "
                        "Lütfen OLLAMA_API_KEY ortam değişkenini ayarlayın. "
                        "Anahtar almak için: https://ollama.com/settings/keys")
            
            return f"Arama sırasında hata oluştu: {error_msg}"

    def _agent_chat(self, prompt, history=None, memory_context=None):
        # Fallback to llama3.1 if gemma2 is not assigned
        model = self.agents.get("chat", "llama3.1:8b") 
        lang = self.settings.get("language", "tr")

        try:
            print(f"SOHBET ({model}) devrede... Lang: {lang}")
        except: pass
        
        sys_context = ""
        if memory_context:
            if lang == "en":
                sys_context = f"\n[USER MEMORY]: {memory_context}\n"
            else:
                sys_context = f"\n[HAFIZA BİLGİSİ]: {memory_context}\n"
        
        # 1. Base Prompt Selection
        if lang == "en":
            sys_prompt = f"""
            You are JARVIS, KKSVSİGB's AI.
            - Address the user as "Sir".
            - Be concise, intelligent, and helpful.
            {sys_context}
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
                f"{sys_context}\n"
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
        
        # Basit sohbet — web search KULLANILMAZ (guncel veri icin SEARCH agenti var)
        try:
            res = ollama.chat(model=model, messages=messages)
            
            try:
                print(f"SOHBET cevap verdi")
            except: pass
            
            final_content = res.message.content if res.message.content else ""
            if not final_content:
                return "Cevap üretilemedi efendim. Lütfen tekrar deneyin."
            
            # Stats footer ekle
            try:
                total_ns = res.get('total_duration', 0) if isinstance(res, dict) else getattr(res, 'total_duration', 0)
                eval_count = res.get('eval_count', 0) if isinstance(res, dict) else getattr(res, 'eval_count', 0)
                eval_ns = res.get('eval_duration', 0) if isinstance(res, dict) else getattr(res, 'eval_duration', 0)
                
                tps_str = "N/A"
                time_str = "N/A"
                if total_ns and total_ns > 0:
                    time_str = f"{total_ns / 1e9:.2f} s"
                if eval_ns and eval_ns > 0 and eval_count and eval_count > 0:
                    tps = eval_count / (eval_ns / 1e9)
                    tps_str = f"{tps:.2f} t/s"
                
                stats = f"\n\n------------\n[Hiz: {tps_str} | Sure: {time_str}]"
                return final_content + stats
            except:
                return final_content
                
        except Exception as e:
            try:
                print(f"SOHBET Hata: {e}")
            except: pass
            return f"Sohbet sırasında hata oluştu: {str(e)}"

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
        
        # Qwen3-Math: Matematik icin ozel egitilmis model
        model = self.agents.get("math", "qwen3-math:1.5b")
        
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
# --- END FEATURE: local_brain ---

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
