
import sys
import os

# Update path to include parent directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from engines.local_brain import LocalBrain

def test_routing():
    brain = LocalBrain()
    
    test_cases = [
        # === SYSTEM ===
        ("Masaüstünde yeni klasör oluştur", "SYSTEM"),
        ("Spotify'ı aç", "SYSTEM"),
        ("Chrome'u kapat", "SYSTEM"),
        ("Dosya oluştur", "SYSTEM"),
        ("Hesap makinesini aç", "SYSTEM"),
        ("Sesi aç", "SYSTEM"),
        ("Bilgisayarı kapat", "SYSTEM"),
        
        # === IMAGE ===
        ("Bana bir kedi resmi çiz", "IMAGE"),
        ("Güneş batışı görseli oluştur", "IMAGE"),
        ("Resim çiz", "IMAGE"),
        ("Logo tasarla", "IMAGE"),
        
        # === CHAT (dikkat: site/uygulama ismi olmasina ragmen CHAT!) ===
        ("Nasılsın", "CHAT"),
        ("Merhaba", "CHAT"),
        ("YouTube kaç yılında kuruldu", "CHAT"),
        ("Spotify nedir", "CHAT"),
        ("Google ne zaman kuruldu", "CHAT"),
        ("RAM ne işe yarar", "CHAT"),
        ("Film önerisi ver", "CHAT"),
        ("Yapay zeka nedir", "CHAT"),
        ("Einstein kimdir", "CHAT"),
        
        # === BROWSER (site ICINDE ISLEM yapma) ===
        ("YouTube'da müzik aç", "BROWSER"),
        ("Amazonda telefon ara", "BROWSER"),
        ("Google'da hava durumu ara", "BROWSER"),
        ("Instagrama gir", "BROWSER"),
        
        # === CODING ===
        ("Bana python kodu yaz", "CODING"),
        ("HTML sayfası oluştur", "CODING"),
        
        # === MATH ===
        ("500 artı 200", "MATH"),
        ("Karekök 144", "MATH"),
        
        # === SEARCH (guncel veri gerektiren) ===
        ("Hava nasıl", "SEARCH"),
        ("Dolar kaç TL", "SEARCH"),
        ("Galatasaray maç skoru", "SEARCH"),
        ("Deprem mi oldu", "SEARCH"),
        
        # === SYSTEM_REPORT ===
        ("Sistem durumu ne", "SYSTEM_REPORT"),
        ("RAM ne kadar dolu", "SYSTEM_REPORT"),
        ("Ne kasıyor", "SYSTEM_REPORT"),
        ("Diskimi ne dolduruyor", "SYSTEM_REPORT"),
    ]
    
    print("=" * 60)
    print(" ROUTING TEST")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    for prompt, expected in test_cases:
        intent = brain._consult_commander(prompt)
        if expected in intent:
            status = "[PASS]"
            passed += 1
        else:
            status = f"[FAIL] (Got: {intent})"
            failed += 1
        print(f"  {status}  '{prompt}' -> Beklenen: {expected}")
    
    print("=" * 60)
    print(f" Sonuc: {passed}/{passed+failed} BASARILI ({failed} HATA)")
    print("=" * 60)

if __name__ == "__main__":
    test_routing()
