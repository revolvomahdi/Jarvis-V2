"""
TEST_UPDATER.PY - Guncelleme Sistemi Kapsamli Test Dosyasi
============================================================
Diff uretme, diff uygulama, feature tarama, feature birlestirme
ve cakisma tespiti icin derin testler.

Kullanim:
    python -m pytest tests/test_updater.py -v
    veya
    python tests/test_updater.py
"""

import os
import sys
import json
import shutil
import tempfile
import hashlib

# Parent dir'i path'e ekle
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from publish import (
    generate_diff,
    scan_features_in_file,
    scan_all_features,
    calculate_content_hash,
    calculate_hash,
    save_diff,
    DIFFS_DIR,
)
from updater import (
    apply_unified_diff,
    FeatureMerger,
    calculate_content_hash as updater_calc_hash,
)


# ============================================================
# TEST YARDIMCI FONKSIYONLARI
# ============================================================

class TestResult:
    """Test sonuclarini takip eder."""
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def ok(self, test_name):
        self.passed += 1
        print(f"  {GREEN}[PASS]{RESET} {test_name}")

    def fail(self, test_name, reason=""):
        self.failed += 1
        self.errors.append((test_name, reason))
        print(f"  {RED}[FAIL]{RESET} {test_name}")
        if reason:
            print(f"         {RED}{reason}{RESET}")

    def summary(self):
        total = self.passed + self.failed
        print(f"\n{'=' * 60}")
        if self.failed == 0:
            print(f"  {GREEN}TUM TESTLER GECTI! {self.passed}/{total}{RESET}")
        else:
            print(f"  {RED}BASARISIZ: {self.failed}/{total}{RESET}")
            for name, reason in self.errors:
                print(f"    - {name}: {reason}")
        print(f"{'=' * 60}")
        return self.failed == 0


# Renk kodlari
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"

if sys.platform == "win32":
    os.system("")


# ============================================================
# TEST VERISI OLUSTURMA
# ============================================================

SAMPLE_FILE_V1 = '''"""
Ornek Dosya - Versiyon 1
"""
import os
import sys
import json

# --- FEATURE: config_loader ---
def load_config(path):
    """Konfigurasyonu yukler."""
    with open(path, "r") as f:
        return json.load(f)
# --- END FEATURE: config_loader ---

# --- FEATURE: file_utils ---
def read_file(path):
    """Dosya okur."""
    with open(path, "r") as f:
        return f.read()

def write_file(path, content):
    """Dosya yazar."""
    with open(path, "w") as f:
        f.write(content)
# --- END FEATURE: file_utils ---

# --- FEATURE: main_logic ---
def main():
    """Ana fonksiyon."""
    config = load_config("config.json")
    print("Program baslatildi")
    print("Versiyon: 1.0")
# --- END FEATURE: main_logic ---

if __name__ == "__main__":
    main()

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
# ============================================================
'''

SAMPLE_FILE_V2 = '''"""
Ornek Dosya - Versiyon 2
"""
import os
import sys
import json
import logging

# --- FEATURE: config_loader ---
def load_config(path):
    """Konfigurasyonu yukler. (Gelistirilmis)"""
    if not os.path.exists(path):
        return {}
    with open(path, "r") as f:
        return json.load(f)
# --- END FEATURE: config_loader ---

# --- FEATURE: file_utils ---
def read_file(path):
    """Dosya okur."""
    with open(path, "r") as f:
        return f.read()

def write_file(path, content):
    """Dosya yazar."""
    with open(path, "w") as f:
        f.write(content)
# --- END FEATURE: file_utils ---

# --- FEATURE: logging_setup ---
def setup_logging():
    """Logging yapilandirmasi."""
    logging.basicConfig(level=logging.INFO)
    return logging.getLogger(__name__)
# --- END FEATURE: logging_setup ---

# --- FEATURE: main_logic ---
def main():
    """Ana fonksiyon. (Gelistirilmis)"""
    logger = setup_logging()
    config = load_config("config.json")
    logger.info("Program baslatildi")
    logger.info("Versiyon: 2.0")
# --- END FEATURE: main_logic ---

if __name__ == "__main__":
    main()

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
# ============================================================
'''

# Kullanicinin yerel versiyonu: V1 + kendi eklediği özellik
SAMPLE_FILE_LOCAL = '''"""
Ornek Dosya - Versiyon 1
"""
import os
import sys
import json

# --- FEATURE: config_loader ---
def load_config(path):
    """Konfigurasyonu yukler."""
    with open(path, "r") as f:
        return json.load(f)
# --- END FEATURE: config_loader ---

# --- FEATURE: file_utils ---
def read_file(path):
    """Dosya okur."""
    with open(path, "r") as f:
        return f.read()

def write_file(path, content):
    """Dosya yazar."""
    with open(path, "w") as f:
        f.write(content)
# --- END FEATURE: file_utils ---

# --- FEATURE: my_custom_feature ---
def custom_function():
    """Kullanicinin kendi eklediği ozellik."""
    print("Bu benim ozelligim!")
    return True
# --- END FEATURE: my_custom_feature ---

# --- FEATURE: main_logic ---
def main():
    """Ana fonksiyon."""
    config = load_config("config.json")
    print("Program baslatildi")
    print("Versiyon: 1.0")
# --- END FEATURE: main_logic ---

if __name__ == "__main__":
    main()

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
# ============================================================
'''

# Buyuk dosya testi icin
LARGE_FILE_TEMPLATE = '''"""
Buyuk Test Dosyasi - {num_features} ozellik icerir
"""
import os
import sys
import json
import hashlib
import time
import re
import logging

'''

def generate_large_file(num_features=20, lines_per_feature=30):
    """Test icin buyuk bir dosya olusturur."""
    content = LARGE_FILE_TEMPLATE.format(num_features=num_features)

    for i in range(num_features):
        content += f"\n# --- FEATURE: feature_{i:03d} ---\n"
        content += f"class Feature{i:03d}:\n"
        content += f'    """Ozellik {i} - Otomatik olusturuldu."""\n\n'

        for j in range(lines_per_feature):
            content += f"    def method_{j}(self, param_{j}):\n"
            content += f'        """Method {j} of Feature {i}."""\n'
            content += f"        result = param_{j} * {j + 1}\n"
            content += f"        return result\n\n"

        content += f"# --- END FEATURE: feature_{i:03d} ---\n"

    content += '''
if __name__ == "__main__":
    pass

# ============================================================
# GELISTIRICI NOTU (AI & Insan):
# Bu projede "Feature Marker" sistemi kullanilmaktadir.
# ============================================================
'''
    return content


# ============================================================
# TESTLER
# ============================================================

def test_diff_generation(results):
    """Diff uretme testleri."""
    print(f"\n{CYAN}{BOLD}--- DIFF URETME TESTLERI ---{RESET}")

    # Test 1: Basit tek satir degisikligi
    old = "satir 1\nsatir 2\nsatir 3\n"
    new = "satir 1\nsatir 2 degisti\nsatir 3\n"
    diff = generate_diff(old, new, "test.py")
    if diff and "satir 2 degisti" in diff and "-satir 2" in diff:
        results.ok("Tek satir degisikligi diff uretme")
    else:
        results.fail("Tek satir degisikligi diff uretme", f"Diff: {diff}")

    # Test 2: Coklu satir degisikligi
    old = "a\nb\nc\nd\ne\nf\n"
    new = "a\nX\nc\nd\nY\nf\n"
    diff = generate_diff(old, new, "multi.py")
    if diff and "+X" in diff and "+Y" in diff:
        results.ok("Coklu satir degisikligi diff uretme")
    else:
        results.fail("Coklu satir degisikligi diff uretme", f"Diff: {diff}")

    # Test 3: Satir ekleme
    old = "satir 1\nsatir 2\n"
    new = "satir 1\nyeni satir\nsatir 2\n"
    diff = generate_diff(old, new, "add.py")
    if diff and "+yeni satir" in diff:
        results.ok("Satir ekleme diff uretme")
    else:
        results.fail("Satir ekleme diff uretme", f"Diff: {diff}")

    # Test 4: Satir silme
    old = "satir 1\nsilinecek\nsatir 2\n"
    new = "satir 1\nsatir 2\n"
    diff = generate_diff(old, new, "delete.py")
    if diff and "-silinecek" in diff:
        results.ok("Satir silme diff uretme")
    else:
        results.fail("Satir silme diff uretme", f"Diff: {diff}")

    # Test 5: Degisiklik yok
    content = "ayni icerik\n"
    diff = generate_diff(content, content, "same.py")
    if diff is None:
        results.ok("Degisiklik yok -> None donmesi")
    else:
        results.fail("Degisiklik yok -> None donmesi", f"Diff: {diff}")

    # Test 6: CRLF normalizasyonu
    old = "satir 1\r\nsatir 2\r\n"
    new = "satir 1\nsatir 2 degisti\n"
    diff = generate_diff(old, new, "crlf.py")
    if diff and "degisti" in diff:
        results.ok("CRLF normalizasyonu")
    else:
        results.fail("CRLF normalizasyonu", f"Diff: {diff}")

    # Test 7: Buyuk dosya diff uretme
    large_v1 = generate_large_file(20, 5)
    large_v2 = large_v1.replace("method_0", "improved_method_0")
    diff = generate_diff(large_v1, large_v2, "large.py")
    if diff and "improved_method_0" in diff:
        results.ok(f"Buyuk dosya diff ({len(large_v1)} karakter)")
    else:
        results.fail(f"Buyuk dosya diff ({len(large_v1)} karakter)")

    # Test 8: V1 -> V2 gercekci diff
    diff = generate_diff(SAMPLE_FILE_V1, SAMPLE_FILE_V2, "sample.py")
    if diff and "logging" in diff and "logging_setup" in diff:
        results.ok("V1 -> V2 gercekci diff uretme")
    else:
        results.fail("V1 -> V2 gercekci diff uretme")


def test_diff_application(results):
    """Diff uygulama (patch) testleri."""
    print(f"\n{CYAN}{BOLD}--- DIFF UYGULAMA TESTLERI ---{RESET}")

    # Test 1: Basit tek satir patch
    old = "satir 1\nsatir 2\nsatir 3\n"
    new = "satir 1\nsatir 2 degisti\nsatir 3\n"
    diff = generate_diff(old, new, "test.py")
    patched, success = apply_unified_diff(old, diff)
    if success and "satir 2 degisti" in patched:
        results.ok("Basit tek satir patch")
    else:
        results.fail("Basit tek satir patch", f"Success: {success}, Patched: {patched[:100]}")

    # Test 2: Coklu hunk patch
    old = "a\nb\nc\nd\ne\nf\ng\nh\ni\nj\n"
    new = "a\nX\nc\nd\ne\nf\ng\nY\ni\nj\n"
    diff = generate_diff(old, new, "multi.py")
    patched, success = apply_unified_diff(old, diff)
    if success and "X" in patched and "Y" in patched and "b" not in patched.split("\n"):
        results.ok("Coklu hunk patch")
    else:
        results.fail("Coklu hunk patch", f"Success: {success}")

    # Test 3: Satir ekleme patch
    old = "satir 1\nsatir 2\n"
    new = "satir 1\nyeni satir\nsatir 2\n"
    diff = generate_diff(old, new, "add.py")
    patched, success = apply_unified_diff(old, diff)
    if success and "yeni satir" in patched:
        results.ok("Satir ekleme patch")
    else:
        results.fail("Satir ekleme patch", f"Patched: {patched}")

    # Test 4: Satir silme patch
    old = "satir 1\nsilinecek\nsatir 2\n"
    new = "satir 1\nsatir 2\n"
    diff = generate_diff(old, new, "del.py")
    patched, success = apply_unified_diff(old, diff)
    if success and "silinecek" not in patched:
        results.ok("Satir silme patch")
    else:
        results.fail("Satir silme patch", f"Patched: {patched}")

    # Test 5: Buyuk dosya patch
    large_v1 = generate_large_file(15, 5)
    large_v2 = large_v1.replace("method_0", "upgraded_method_0")
    large_v2 = large_v2.replace("Feature 5", "Feature 5 UPGRADED")
    diff = generate_diff(large_v1, large_v2, "large.py")
    patched, success = apply_unified_diff(large_v1, diff)
    if success and "upgraded_method_0" in patched:
        results.ok(f"Buyuk dosya patch ({len(large_v1)} karakter)")
    else:
        results.fail(f"Buyuk dosya patch ({len(large_v1)} karakter)")

    # Test 6: V1 -> V2 gercekci patch
    diff = generate_diff(SAMPLE_FILE_V1, SAMPLE_FILE_V2, "sample.py")
    patched, success = apply_unified_diff(SAMPLE_FILE_V1, diff)
    if success and "logging" in patched and "setup_logging" in patched and "Versiyon: 2.0" in patched:
        results.ok("V1 -> V2 gercekci patch")
    else:
        results.fail("V1 -> V2 gercekci patch", f"Success: {success}")

    # Test 7: Bozuk diff -> basarisiz
    _, success = apply_unified_diff("test", "bu gecerli bir diff degil")
    if not success:
        results.ok("Bozuk diff -> basarisiz donme")
    else:
        results.fail("Bozuk diff -> basarisiz donme")

    # Test 8: Roundtrip testi - diff uret, uygula, hash kontrol et
    for name, v1, v2 in [
        ("kucuk", "a\nb\nc\n", "a\nX\nc\n"),
        ("orta", SAMPLE_FILE_V1, SAMPLE_FILE_V2),
        ("buyuk", generate_large_file(10, 3), generate_large_file(10, 3).replace("method_1", "new_method_1")),
    ]:
        diff = generate_diff(v1, v2, f"{name}.py")
        if diff:
            patched, success = apply_unified_diff(v1, diff)
            v2_normalized = v2.replace("\r\n", "\n")
            patched_normalized = patched.replace("\r\n", "\n")
            if success and calculate_content_hash(patched_normalized) == calculate_content_hash(v2_normalized):
                results.ok(f"Roundtrip testi ({name})")
            else:
                results.fail(f"Roundtrip testi ({name})", "Hash eslesmedi")
        else:
            results.fail(f"Roundtrip testi ({name})", "Diff uretilemedi")


def test_feature_scanning(results):
    """Feature marker tarama testleri."""
    print(f"\n{CYAN}{BOLD}--- FEATURE TARAMA TESTLERI ---{RESET}")

    # Gecici dosya olustur
    tmpdir = tempfile.mkdtemp()
    test_file = os.path.join(tmpdir, "test_features.py")

    try:
        # Test 1: Basit feature tarama
        with open(test_file, "w", encoding="utf-8") as f:
            f.write(SAMPLE_FILE_V1)

        features = scan_features_in_file(test_file)
        feature_ids = [f["id"] for f in features]
        if set(feature_ids) == {"config_loader", "file_utils", "main_logic"}:
            results.ok("V1 dosyada 3 feature bulma")
        else:
            results.fail("V1 dosyada 3 feature bulma", f"Bulunan: {feature_ids}")

        # Test 2: V2 dosyada 4 feature
        with open(test_file, "w", encoding="utf-8") as f:
            f.write(SAMPLE_FILE_V2)

        features = scan_features_in_file(test_file)
        feature_ids = [f["id"] for f in features]
        if set(feature_ids) == {"config_loader", "file_utils", "logging_setup", "main_logic"}:
            results.ok("V2 dosyada 4 feature bulma")
        else:
            results.fail("V2 dosyada 4 feature bulma", f"Bulunan: {feature_ids}")

        # Test 3: Yerel dosyada custom feature
        with open(test_file, "w", encoding="utf-8") as f:
            f.write(SAMPLE_FILE_LOCAL)

        features = scan_features_in_file(test_file)
        feature_ids = [f["id"] for f in features]
        if "my_custom_feature" in feature_ids:
            results.ok("Custom feature tespiti")
        else:
            results.fail("Custom feature tespiti", f"Bulunan: {feature_ids}")

        # Test 4: Buyuk dosyada feature tarama
        large_content = generate_large_file(20, 5)
        with open(test_file, "w", encoding="utf-8") as f:
            f.write(large_content)

        features = scan_features_in_file(test_file)
        if len(features) == 20:
            results.ok(f"Buyuk dosyada 20 feature bulma")
        else:
            results.fail(f"Buyuk dosyada 20 feature bulma", f"Bulunan: {len(features)}")

        # Test 5: Feature hash'lerinin tekrarlanabilir olmasi
        features1 = scan_features_in_file(test_file)
        features2 = scan_features_in_file(test_file)
        hashes_match = all(
            f1["hash"] == f2["hash"]
            for f1, f2 in zip(features1, features2)
        )
        if hashes_match:
            results.ok("Feature hash tekrarlanabilirligi")
        else:
            results.fail("Feature hash tekrarlanabilirligi")

        # Test 6: Bos dosya -> 0 feature
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("# Bu dosyada feature yok\nprint('merhaba')\n")

        features = scan_features_in_file(test_file)
        if len(features) == 0:
            results.ok("Bos dosya -> 0 feature")
        else:
            results.fail("Bos dosya -> 0 feature", f"Bulunan: {len(features)}")

        # Test 7: Yanlis formatli marker -> atlanmasi
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("# --- FEATURE: test_feat ---\ndef f(): pass\n# bu END degil\n")

        features = scan_features_in_file(test_file)
        if len(features) == 0:
            results.ok("Kapanmamis feature -> atlanma")
        else:
            results.fail("Kapanmamis feature -> atlanma", f"Bulunan: {len(features)}")

        # Test 8: Proje tarama (scan_all_features)
        sub_dir = os.path.join(tmpdir, "engines")
        os.makedirs(sub_dir, exist_ok=True)

        with open(os.path.join(tmpdir, "main.py"), "w", encoding="utf-8") as f:
            f.write("# --- FEATURE: app_start ---\ndef start(): pass\n# --- END FEATURE: app_start ---\n")

        with open(os.path.join(sub_dir, "engine.py"), "w", encoding="utf-8") as f:
            f.write("# --- FEATURE: engine_core ---\ndef run(): pass\n# --- END FEATURE: engine_core ---\n")

        registry = scan_all_features(tmpdir)
        file_count = len(registry["files"])
        if file_count >= 2:
            results.ok(f"Proje geneli tarama ({file_count} dosya)")
        else:
            results.fail(f"Proje geneli tarama", f"Bulunan: {file_count} dosya")

    finally:
        shutil.rmtree(tmpdir)


def test_feature_merging(results):
    """Feature birlestirme testleri."""
    print(f"\n{CYAN}{BOLD}--- FEATURE BIRLESTIRME TESTLERI ---{RESET}")
    merger = FeatureMerger()

    # Test 1: Uzaktan yeni feature ekleme (config_loader ve main_logic degismis = 2 cakisma beklenir)
    merged, conflicts, added = merger.merge_features(SAMPLE_FILE_V1, SAMPLE_FILE_V2, auto_resolve="add")
    if "logging_setup" in added and len(conflicts) == 2:
        results.ok("Yeni feature ekleme (logging_setup) + 2 cakisma")
    else:
        results.fail("Yeni feature ekleme (logging_setup) + 2 cakisma", f"Added: {added}, Conflicts: {len(conflicts)}")

    # Test 2: Birlestirilmis dosyada yeni feature var mi
    if "setup_logging" in merged:
        results.ok("Birlestirilmis dosyada yeni feature kodu mevcut")
    else:
        results.fail("Birlestirilmis dosyada yeni feature kodu mevcut")

    # Test 3: Yerel ozelligin korunmasi
    merged, conflicts, added = merger.merge_features(SAMPLE_FILE_LOCAL, SAMPLE_FILE_V2, auto_resolve="add")
    if "custom_function" in merged:
        results.ok("Yerel ozelligin korunmasi (my_custom_feature)")
    else:
        results.fail("Yerel ozelligin korunmasi (my_custom_feature)")

    # Test 4: Yeni ozellik eklenmesi + yerel korunmasi ayni anda
    if "logging_setup" in added and "custom_function" in merged and "setup_logging" in merged:
        results.ok("Ekleme + koruma ayni anda")
    else:
        results.fail("Ekleme + koruma ayni anda", f"Added: {added}")

    # Test 5: Cakisma tespiti (ayni feature farkli hash)
    # V1'deki config_loader ile V2'deki config_loader farkli
    local_features = merger.extract_features_from_content(SAMPLE_FILE_V1)
    remote_features = merger.extract_features_from_content(SAMPLE_FILE_V2)

    config_loader_local_hash = local_features.get("config_loader", {}).get("hash", "")
    config_loader_remote_hash = remote_features.get("config_loader", {}).get("hash", "")

    if config_loader_local_hash != config_loader_remote_hash:
        results.ok("Cakisma tespiti: config_loader farkli hash")
    else:
        results.fail("Cakisma tespiti: config_loader farkli hash")

    # Test 6: Cakisma sayisi (V1 local, V2 remote)
    # config_loader ve main_logic degismis, file_utils ayni kalmis
    _, conflicts, _ = merger.merge_features(SAMPLE_FILE_V1, SAMPLE_FILE_V2, auto_resolve="add")
    conflict_ids = [c["feature_id"] for c in conflicts]
    if "config_loader" in conflict_ids and "main_logic" in conflict_ids:
        results.ok(f"Cakisma tespiti: {len(conflicts)} cakisma ({', '.join(conflict_ids)})")
    else:
        results.fail(f"Cakisma tespiti", f"Beklenen: config_loader+main_logic, Bulunan: {conflict_ids}")

    # Test 7: Feature extraction dogrulugu
    features = merger.extract_features_from_content(SAMPLE_FILE_V1)
    if len(features) == 3 and all(
        k in features for k in ["config_loader", "file_utils", "main_logic"]
    ):
        results.ok("Feature extraction (V1: 3 ozellik)")
    else:
        results.fail("Feature extraction (V1: 3 ozellik)", f"Bulunan: {list(features.keys())}")

    features = merger.extract_features_from_content(SAMPLE_FILE_V2)
    if len(features) == 4 and "logging_setup" in features:
        results.ok("Feature extraction (V2: 4 ozellik)")
    else:
        results.fail("Feature extraction (V2: 4 ozellik)", f"Bulunan: {list(features.keys())}")

    # Test 8: Buyuk dosyada merge
    large_v1 = generate_large_file(10, 3)
    large_v2 = generate_large_file(12, 3)  # 2 yeni feature
    merged, conflicts, added = merger.merge_features(large_v1, large_v2, auto_resolve="add")
    if len(added) == 2:
        results.ok(f"Buyuk dosya merge (2 yeni ozellik eklendi)")
    else:
        results.fail(f"Buyuk dosya merge", f"Eklenen: {len(added)}")

    # Test 9: Ayni dosya - 0 cakisma, 0 ekleme
    merged, conflicts, added = merger.merge_features(SAMPLE_FILE_V1, SAMPLE_FILE_V1, auto_resolve="add")
    if len(conflicts) == 0 and len(added) == 0:
        results.ok("Ayni dosya -> 0 cakisma, 0 ekleme")
    else:
        results.fail("Ayni dosya -> 0 cakisma, 0 ekleme", f"Conflicts: {len(conflicts)}, Added: {len(added)}")

    # Test 10: Conflict resolution - "local" secimi
    test_conflict = {
        "feature_id": "test_feat",
        "local_content": "# --- FEATURE: test_feat ---\ndef local(): pass\n# --- END FEATURE: test_feat ---",
        "remote_content": "# --- FEATURE: test_feat ---\ndef remote(): pass\n# --- END FEATURE: test_feat ---",
    }
    content_with_local = "once\n# --- FEATURE: test_feat ---\ndef local(): pass\n# --- END FEATURE: test_feat ---\nsonra"
    resolved = merger.apply_conflict_resolution(content_with_local, test_conflict, "local")
    if "def local()" in resolved and "def remote()" not in resolved:
        results.ok("Conflict resolution: local secimi")
    else:
        results.fail("Conflict resolution: local secimi")

    # Test 11: Conflict resolution - "remote" secimi
    resolved = merger.apply_conflict_resolution(content_with_local, test_conflict, "remote")
    if "def remote()" in resolved:
        results.ok("Conflict resolution: remote secimi")
    else:
        results.fail("Conflict resolution: remote secimi")

    # Test 12: Conflict resolution - "both" secimi
    resolved = merger.apply_conflict_resolution(content_with_local, test_conflict, "both")
    if "YEREL VERSIYON" in resolved and "UZAK VERSIYON" in resolved:
        results.ok("Conflict resolution: both secimi")
    else:
        results.fail("Conflict resolution: both secimi")


def test_hash_functions(results):
    """Hash fonksiyonlari testleri."""
    print(f"\n{CYAN}{BOLD}--- HASH FONKSIYONLARI TESTLERI ---{RESET}")

    # Test 1: Ayni icerik -> ayni hash
    h1 = calculate_content_hash("test icerik")
    h2 = calculate_content_hash("test icerik")
    if h1 == h2:
        results.ok("Ayni icerik -> ayni hash")
    else:
        results.fail("Ayni icerik -> ayni hash")

    # Test 2: Farkli icerik -> farkli hash
    h1 = calculate_content_hash("icerik A")
    h2 = calculate_content_hash("icerik B")
    if h1 != h2:
        results.ok("Farkli icerik -> farkli hash")
    else:
        results.fail("Farkli icerik -> farkli hash")

    # Test 3: CRLF normalizasyonu
    h1 = calculate_content_hash("satir 1\r\nsatir 2\r\n")
    h2 = calculate_content_hash("satir 1\nsatir 2\n")
    if h1 == h2:
        results.ok("CRLF normalizasyonu hash")
    else:
        results.fail("CRLF normalizasyonu hash")

    # Test 4: Dosya hash testi
    tmpdir = tempfile.mkdtemp()
    try:
        test_file = os.path.join(tmpdir, "hash_test.py")
        with open(test_file, "w", encoding="utf-8", newline="\n") as f:
            f.write("print('merhaba')\n")
        h = calculate_hash(test_file)
        if h and len(h) == 64:  # SHA256 hex = 64 karakter
            results.ok("Dosya hash uzunlugu (SHA256)")
        else:
            results.fail("Dosya hash uzunlugu (SHA256)", f"Hash: {h}")
    finally:
        shutil.rmtree(tmpdir)


def test_diff_save_and_load(results):
    """Diff dosyasi kaydetme ve yukleme testleri."""
    print(f"\n{CYAN}{BOLD}--- DIFF KAYDETME TESTLERI ---{RESET}")

    tmpdir = tempfile.mkdtemp()
    try:
        # Test 1: Basit diff kaydetme
        diff_content = "--- a/test.py\n+++ b/test.py\n@@ -1,3 +1,3 @@\n eski\n-satir 2\n+satir 2 yeni\n son\n"
        diff_rel = save_diff(tmpdir, "test.py", diff_content)
        diff_full = os.path.join(tmpdir, DIFFS_DIR, diff_rel.replace("/", os.sep))
        if os.path.exists(diff_full):
            results.ok("Diff dosyasi kaydetme")
        else:
            results.fail("Diff dosyasi kaydetme")

        # Test 2: Ic ice dizin diff kaydetme
        diff_rel = save_diff(tmpdir, "engines/local_brain.py", diff_content)
        diff_full = os.path.join(tmpdir, DIFFS_DIR, diff_rel.replace("/", os.sep))
        if os.path.exists(diff_full):
            results.ok("Ic ice dizin diff kaydetme")
        else:
            results.fail("Ic ice dizin diff kaydetme")

        # Test 3: Kaydedilen diff iceriginin dogrulugu
        with open(diff_full, "r", encoding="utf-8") as f:
            loaded = f.read()
        if loaded == diff_content:
            results.ok("Diff icerik dogrulugu")
        else:
            results.fail("Diff icerik dogrulugu")

    finally:
        shutil.rmtree(tmpdir)


def test_edge_cases(results):
    """Kenar durum testleri."""
    print(f"\n{CYAN}{BOLD}--- KENAR DURUM TESTLERI ---{RESET}")

    merger = FeatureMerger()

    # Test 1: Bos dosya merge
    merged, conflicts, added = merger.merge_features("", SAMPLE_FILE_V1, auto_resolve="add")
    if len(added) == 3:
        results.ok("Bos dosya + V1 = 3 ozellik ekleme")
    else:
        results.fail("Bos dosya + V1 = 3 ozellik ekleme", f"Added: {len(added)}")

    # Test 2: Feature'siz dosya merge
    no_features = "import os\nprint('merhaba')\n"
    merged, conflicts, added = merger.merge_features(no_features, SAMPLE_FILE_V1, auto_resolve="add")
    if len(added) == 3:
        results.ok("Feature'siz dosya + V1 = 3 ozellik ekleme")
    else:
        results.fail("Feature'siz dosya + V1 = 3 ozellik ekleme", f"Added: {len(added)}")

    # Test 3: Cok buyuk diff
    lines_v1 = [f"satir_{i}\n" for i in range(500)]
    lines_v2 = list(lines_v1)
    lines_v2[50] = "degisen_satir_50\n"
    lines_v2[250] = "degisen_satir_250\n"
    lines_v2[450] = "degisen_satir_450\n"

    diff = generate_diff("".join(lines_v1), "".join(lines_v2), "big.py")
    patched, success = apply_unified_diff("".join(lines_v1), diff)
    if success and "degisen_satir_50" in patched and "degisen_satir_250" in patched:
        results.ok("500 satirlik dosyada 3 farkli noktada degisiklik")
    else:
        results.fail("500 satirlik dosyada 3 farkli noktada degisiklik")

    # Test 4: Feature insert position - imports sonrasi
    lines = ["import os", "import sys", "", "def main():", "    pass"]
    pos = merger.find_insert_position(lines, position_after="imports")
    if pos in (3, 4):  # import blogundan sonra (bos satir durumuna gore)
        results.ok(f"Insert position: imports sonrasi (pos={pos})")
    else:
        results.fail("Insert position: imports sonrasi", f"Position: {pos}")

    # Test 5: Unicode icerik
    unicode_content = "# --- FEATURE: turkce ---\ndef selamla():\n    print('Merhaba Dünya! Şçöü')\n# --- END FEATURE: turkce ---\n"
    features = merger.extract_features_from_content(unicode_content)
    if "turkce" in features:
        results.ok("Unicode icerikli feature")
    else:
        results.fail("Unicode icerikli feature")


def test_duplicate_detection(results):
    """Farkli isim ayni ozellik (duplicate) tespiti testleri."""
    print(f"\n{CYAN}{BOLD}--- DUPLICATE TESPIT TESTLERI ---{RESET}")
    merger = FeatureMerger()

    # Test 1: Ayni kod, farkli isim -> duplicate
    local_with_custom = '''
# --- FEATURE: dosya_okuyucu ---
def read_file(path):
    """Dosya okur."""
    with open(path, "r") as f:
        return f.read()
# --- END FEATURE: dosya_okuyucu ---
'''
    remote_with_different_name = '''
# --- FEATURE: file_reader ---
def read_file(path):
    """Dosya okur."""
    with open(path, "r") as f:
        return f.read()
# --- END FEATURE: file_reader ---
'''
    local_feats = merger.extract_features_from_content(local_with_custom)
    remote_feats = merger.extract_features_from_content(remote_with_different_name)
    dups = merger.detect_duplicates(local_feats, remote_feats, threshold=0.65)
    if len(dups) == 1 and dups[0]["local_id"] == "dosya_okuyucu" and dups[0]["remote_id"] == "file_reader":
        results.ok("Ayni kod farkli isim -> duplicate tespiti")
    else:
        results.fail("Ayni kod farkli isim -> duplicate tespiti", f"Dups: {len(dups)}")

    # Test 2: Tamamen farkli kod -> duplicate degil
    local_a = '''
# --- FEATURE: math_ops ---
def add(a, b):
    return a + b
def subtract(a, b):
    return a - b
# --- END FEATURE: math_ops ---
'''
    remote_b = '''
# --- FEATURE: string_ops ---
def uppercase(s):
    return s.upper()
def lowercase(s):
    return s.lower()
# --- END FEATURE: string_ops ---
'''
    local_feats = merger.extract_features_from_content(local_a)
    remote_feats = merger.extract_features_from_content(remote_b)
    dups = merger.detect_duplicates(local_feats, remote_feats, threshold=0.65)
    if len(dups) == 0:
        results.ok("Tamamen farkli kod -> duplicate degil")
    else:
        results.fail("Tamamen farkli kod -> duplicate degil", f"Dups: {len(dups)}")

    # Test 3: Benzerlik yuzdesi dogrulugu
    similarity = merger.calculate_similarity(
        "# --- FEATURE: a ---\ndef func(): pass\n# --- END FEATURE: a ---",
        "# --- FEATURE: b ---\ndef func(): pass\n# --- END FEATURE: b ---"
    )
    if similarity > 0.8:
        results.ok(f"Ayni kod benzerlik yuzdesi: %{similarity * 100:.0f}")
    else:
        results.fail(f"Ayni kod benzerlik yuzdesi", f"%{similarity * 100:.0f}")

    # Test 4: Fonksiyon adi eslesmesi
    names = merger._extract_function_names("def hello():\n    pass\ndef world():\n    pass\nclass MyClass:\n    pass")
    if names == {"hello", "world", "MyClass"}:
        results.ok("Fonksiyon/sinif adi cikarma")
    else:
        results.fail("Fonksiyon/sinif adi cikarma", f"Bulunan: {names}")

    # Test 5: Esik degeri (threshold) testi
    slightly_different_local = '''
# --- FEATURE: config_read ---
def load_config(path):
    """Config dosyasini yukler."""
    with open(path, "r") as f:
        data = json.load(f)
    return data
# --- END FEATURE: config_read ---
'''
    slightly_different_remote = '''
# --- FEATURE: config_loader ---
def load_config(filepath):
    """Config dosyasini yukler."""
    with open(filepath, "r") as f:
        data = json.load(f)
    return data
# --- END FEATURE: config_loader ---
'''
    local_feats = merger.extract_features_from_content(slightly_different_local)
    remote_feats = merger.extract_features_from_content(slightly_different_remote)
    dups = merger.detect_duplicates(local_feats, remote_feats, threshold=0.65)
    if len(dups) == 1:
        results.ok(f"Kucuk farkla duplicate tespiti (%{dups[0]['similarity'] * 100:.0f})")
    else:
        results.fail("Kucuk farkla duplicate tespiti", f"Dups: {len(dups)}")

    # Test 6: Buyuk dosyada duplicate tespiti
    # feature_000 ile ayni kodu farkli isimle ekle
    large_local = generate_large_file(5, 3)
    large_remote = large_local.replace("feature_000", "ozellik_sifir")
    local_feats = merger.extract_features_from_content(large_local)
    remote_feats = merger.extract_features_from_content(large_remote)
    dups = merger.detect_duplicates(local_feats, remote_feats, threshold=0.65)
    # feature_000 ve ozellik_sifir eslesecek + diger 4 feature de eslesecek
    if len(dups) >= 1:
        results.ok(f"Buyuk dosyada duplicate tespiti ({len(dups)} dup)")
    else:
        results.fail("Buyuk dosyada duplicate tespiti")

    # Test 7: Ayni ID -> duplicate sayilmamasi
    same_content = SAMPLE_FILE_V1
    local_feats = merger.extract_features_from_content(same_content)
    remote_feats = merger.extract_features_from_content(same_content)
    dups = merger.detect_duplicates(local_feats, remote_feats, threshold=0.65)
    if len(dups) == 0:
        results.ok("Ayni ID -> duplicate sayilmamasi")
    else:
        results.fail("Ayni ID -> duplicate sayilmamasi", f"Dups: {len(dups)}")


def test_real_file_copy(results):
    """Gercek proje dosyasi kopyasi ile test."""
    print(f"\n{CYAN}{BOLD}--- GERCEK DOSYA KOPYASI TESTLERI ---{RESET}")

    project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    local_brain_path = os.path.join(project_dir, "engines", "local_brain.py")

    if not os.path.exists(local_brain_path):
        results.fail("Gercek dosya testi", "local_brain.py bulunamadi")
        return

    try:
        with open(local_brain_path, "r", encoding="utf-8") as f:
            original_content = f.read()
    except (IOError, UnicodeDecodeError) as e:
        results.fail("Gercek dosya testi", f"Dosya okunamadi: {e}")
        return

    line_count = len(original_content.split("\n"))
    print(f"  {DIM}local_brain.py: {line_count} satir, {len(original_content)} karakter{RESET}")

    # Test 1: Buyuk dosyada diff
    modified = original_content.replace(
        "class LocalBrain",
        "# MODIFIED BY TEST\nclass LocalBrain"
    )
    diff = generate_diff(original_content, modified, "engines/local_brain.py")
    if diff and "MODIFIED BY TEST" in diff:
        results.ok(f"local_brain.py diff uretme ({line_count} satir)")
    else:
        results.fail(f"local_brain.py diff uretme ({line_count} satir)")

    # Test 2: Buyuk dosyada patch
    if diff:
        patched, success = apply_unified_diff(original_content, diff)
        if success and "MODIFIED BY TEST" in patched:
            results.ok(f"local_brain.py patch uygulama ({line_count} satir)")
        else:
            results.fail(f"local_brain.py patch uygulama ({line_count} satir)")

    # Test 3: Roundtrip hash dogrulama
    if diff:
        patched, success = apply_unified_diff(original_content, diff)
        if success:
            expected_hash = calculate_content_hash(modified)
            actual_hash = calculate_content_hash(patched)
            if expected_hash == actual_hash:
                results.ok(f"local_brain.py roundtrip hash dogrulama")
            else:
                results.fail(f"local_brain.py roundtrip hash dogrulama")
        else:
            results.fail(f"local_brain.py roundtrip hash dogrulama", "Patch basarisiz")


# ============================================================
# ANA TEST CALISTIRICISI
# ============================================================

def main():
    """Tum testleri calistir."""
    print(f"\n{CYAN}{BOLD}")
    print("=" * 60)
    print("   GUNCELLEME SISTEMI - KAPSAMLI TEST PAKETI")
    print("=" * 60)
    print(f"{RESET}")

    results = TestResult()

    test_hash_functions(results)
    test_diff_generation(results)
    test_diff_application(results)
    test_diff_save_and_load(results)
    test_feature_scanning(results)
    test_feature_merging(results)
    test_duplicate_detection(results)
    test_edge_cases(results)
    test_real_file_copy(results)

    success = results.summary()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
