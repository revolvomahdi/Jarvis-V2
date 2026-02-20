
import sys
import os

# Update path to include parent directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from engines.local_brain import LocalBrain

def test_routing():
    brain = LocalBrain()
    
    test_cases = [
        ("Masaüstünde yeni klasör oluştur", "SYSTEM"),
        ("Bana bir kedi resmi çiz", "IMAGE"),
        ("Güneş batışı görseli oluştur", "IMAGE"),
        ("Spotify'ı aç", "SYSTEM"),
        ("Nasılsın", "CHAT"),
        ("Bana python kodu yaz", "CODING"),
        ("500 artı 200", "MATH"),
        ("Dosya oluştur", "SYSTEM"), # Critical fail case previously
        ("Resim çiz", "IMAGE")
    ]
    
    print("--- ROUTING TEST START ---")
    
    for prompt, expected in test_cases:
        intent = brain._consult_commander(prompt)
        status = "[PASS]" if expected in intent else f"[FAIL] (Got: {intent})"
        print(f"Prompt: '{prompt}' -> {status}")
        
    print("--- ROUTING TEST END ---")

if __name__ == "__main__":
    test_routing()
