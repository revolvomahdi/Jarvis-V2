"""
PUBLISH.PY - Manifest Olusturucu + Diff Ureticisi + Ozellik Tarayici
=====================================================================
Proje dosyalarini tarar, hash hesaplar, diff uretir ve manifest.json'u gunceller.
Ayrica feature marker'lari tarayip feature_registry.json'u olusturur.
Degisiklik yaptiktan sonra, GitHub'a push etmeden once bunu calistirin.

Kullanim:
    python publish.py
"""

import os
import sys
import json
import hashlib
import time
import re
import difflib

# requests kutuphanesi yoksa kur
try:
    import requests
except ImportError:
    print("[*] 'requests' kutuphanesi kuruluyor...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "-q"])
    import requests

# --- YAPILANDIRMA ---
MANIFEST_FILE = "manifest.json"
FEATURE_REGISTRY_FILE = "feature_registry.json"
DIFFS_DIR = "diffs"
PROJECT_NAME = "Yapay Zeka Asistani v2"
BASE_URL = "https://raw.githubusercontent.com/revolvomahdi/Jarvis-V2/main/"

# Guncelleme disinda tutulacak dosya/klasorler
EXCLUDE_PATTERNS = [
    ".venv/",
    ".venv\\",
    "__pycache__/",
    "__pycache__\\",
    "old/",
    "old\\",
    "data/chat_history.json",
    "data\\chat_history.json",
    "data/long_memory.json",
    "data\\long_memory.json",
    "data/user_profile.json",
    "data\\user_profile.json",
    "data/archives/",
    "data\\archives\\",
    ".git/",
    ".git\\",
    "desktop.ini",
    ".gitattributes",
    "updater.py",
    "updater.bat",
    "manifest.json",
    "api_keys.json",
    "test_updater/",
    "test_updater\\",
    "tests/",
    "tests\\",
    "data/temp_audio/",
    "data\\temp_audio\\",
    "data/models/",
    "data\\models\\",
    "diffs/",
    "diffs\\",
    "feature_registry.json",
]

# Sadece bu uzantilari tara
ALLOWED_EXTENSIONS = [
    ".py", ".txt", ".json", ".bat", ".html", ".css", ".js",
    ".md", ".yaml", ".yml", ".toml", ".cfg", ".ini", ".env",
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico",
    ".mp3", ".wav", ".ogg",
]

ALLOWED_DOTFILES = [".env", ".gitignore"]

# Binary dosya uzantilari
BINARY_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico",
    ".mp3", ".wav", ".ogg",
    ".zip", ".tar", ".gz", ".bz2",
    ".pdf", ".exe", ".dll",
}

# Feature marker pattern
FEATURE_START_PATTERN = re.compile(r"^#\s*---\s*FEATURE:\s*(\S+)\s*---\s*$")
FEATURE_END_PATTERN = re.compile(r"^#\s*---\s*END\s+FEATURE:\s*(\S+)\s*---\s*$")


# --- FEATURE: should_exclude ---
def should_exclude(filepath):
    """Dosyanin exclude listesinde olup olmadigini kontrol eder."""
    normalized = filepath.replace("\\", "/")
    for pattern in EXCLUDE_PATTERNS:
        pattern_normalized = pattern.replace("\\", "/")
        if pattern_normalized.endswith("/"):
            if normalized.startswith(pattern_normalized) or ("/" + pattern_normalized) in ("/" + normalized):
                return True
        else:
            if normalized == pattern_normalized or normalized.endswith("/" + pattern_normalized):
                return True
    return False


def is_binary_file(filepath):
    """Dosyanin binary olup olmadigini kontrol eder."""
    _, ext = os.path.splitext(filepath)
    return ext.lower() in BINARY_EXTENSIONS


def calculate_hash(filepath):
    """Dosyanin SHA256 hash degerini hesaplar.
    Text dosyalarda satir sonlarini normalize eder (CRLF -> LF)."""
    sha256 = hashlib.sha256()
    try:
        if is_binary_file(filepath):
            with open(filepath, "rb") as f:
                while True:
                    chunk = f.read(8192)
                    if not chunk:
                        break
                    sha256.update(chunk)
        else:
            with open(filepath, "rb") as f:
                content = f.read()
            content = content.replace(b"\r\n", b"\n")
            sha256.update(content)
        return sha256.hexdigest()
    except (IOError, OSError) as e:
        print(f"  [!] Hash hesaplanamadi: {filepath} - {e}")
        return None


def calculate_content_hash(content):
    """String icerigin SHA256 hash degerini hesaplar."""
    if isinstance(content, str):
        content = content.encode("utf-8")
    content = content.replace(b"\r\n", b"\n")
    return hashlib.sha256(content).hexdigest()


def scan_project(project_dir):
    """Proje klasorundeki tum dosyalari tarar."""
    files = {}
    for root, dirs, filenames in os.walk(project_dir):
        dirs[:] = [d for d in dirs if not should_exclude(
            os.path.relpath(os.path.join(root, d), project_dir) + "/"
        )]

        for filename in filenames:
            full_path = os.path.join(root, filename)
            rel_path = os.path.relpath(full_path, project_dir).replace("\\", "/")

            if should_exclude(rel_path):
                continue

            _, ext = os.path.splitext(filename)
            if ext.lower() not in ALLOWED_EXTENSIONS and filename not in ALLOWED_DOTFILES:
                continue

            file_hash = calculate_hash(full_path)
            if file_hash:
                files[rel_path] = file_hash

    return files


def load_existing_manifest():
    """Mevcut manifest dosyasini yukler."""
    if os.path.exists(MANIFEST_FILE):
        try:
            with open(MANIFEST_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return None
# --- END FEATURE: should_exclude ---


# ============================================================
# DIFF URETIMI
# ============================================================

# --- FEATURE: fetch_old_file_from_github ---
def fetch_old_file_from_github(rel_path, base_url):
    """GitHub'dan dosyanin eski versiyonunu indirir."""
    file_url = base_url.rstrip("/") + "/" + rel_path.replace("\\", "/")
    try:
        response = requests.get(file_url, timeout=15)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException:
        return None


def generate_diff(old_content, new_content, rel_path):
    """Iki icerik arasindaki diff'i unified format olarak uretir.
    Satir sonlarini normalize eder."""
    old_lines = old_content.replace("\r\n", "\n").splitlines()
    new_lines = new_content.replace("\r\n", "\n").splitlines()

    diff = list(difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile=f"a/{rel_path}",
        tofile=f"b/{rel_path}",
        lineterm=""
    ))

    if not diff:
        return None

    return "\n".join(diff)


def save_diff(project_dir, rel_path, diff_content):
    """Diff dosyasini diffs/ klasorune kaydeder."""
    diff_rel_path = rel_path + ".diff"
    diff_full_path = os.path.join(project_dir, DIFFS_DIR, diff_rel_path.replace("/", os.sep))

    diff_dir = os.path.dirname(diff_full_path)
    if not os.path.exists(diff_dir):
        os.makedirs(diff_dir, exist_ok=True)

    with open(diff_full_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(diff_content)

    return diff_rel_path
# --- END FEATURE: fetch_old_file_from_github ---


# ============================================================
# OZELLIK (FEATURE) TARAMA
# ============================================================

# --- FEATURE: scan_features_in_file ---
def scan_features_in_file(filepath):
    """Dosyadaki feature marker'lari tarar ve ozellik listesi dondurur."""
    features = []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except (IOError, OSError, UnicodeDecodeError):
        return features

    current_feature = None
    feature_lines = []
    feature_start_line = -1

    for i, line in enumerate(lines):
        stripped = line.strip()

        start_match = FEATURE_START_PATTERN.match(stripped)
        if start_match:
            feature_id = start_match.group(1)
            current_feature = feature_id
            feature_lines = [line]
            feature_start_line = i + 1  # 1-indexed
            continue

        if current_feature:
            feature_lines.append(line)
            end_match = FEATURE_END_PATTERN.match(stripped)
            if end_match and end_match.group(1) == current_feature:
                # Ozellik tamamlandi
                feature_content = "".join(feature_lines)
                feature_hash = calculate_content_hash(feature_content)

                features.append({
                    "id": current_feature,
                    "start_line": feature_start_line,
                    "end_line": i + 1,  # 1-indexed
                    "hash": feature_hash,
                    "line_count": len(feature_lines),
                })

                current_feature = None
                feature_lines = []

    return features


def scan_all_features(project_dir):
    """Tum projedeki feature marker'lari tarar."""
    registry = {"version": 1, "files": {}}

    for root, dirs, filenames in os.walk(project_dir):
        dirs[:] = [d for d in dirs if not should_exclude(
            os.path.relpath(os.path.join(root, d), project_dir) + "/"
        )]

        for filename in filenames:
            if not filename.endswith(".py"):
                continue

            full_path = os.path.join(root, filename)
            rel_path = os.path.relpath(full_path, project_dir).replace("\\", "/")

            if should_exclude(rel_path):
                continue

            features = scan_features_in_file(full_path)
            if features:
                registry["files"][rel_path] = {"features": features}

    return registry


def save_feature_registry(registry):
    """Feature registry'yi dosyaya kaydeder."""
    with open(FEATURE_REGISTRY_FILE, "w", encoding="utf-8") as f:
        json.dump(registry, f, indent=2, ensure_ascii=False)
# --- END FEATURE: scan_features_in_file ---


# ============================================================
# ANA PUBLISH FONKSIYONU
# ============================================================

# --- FEATURE: publish ---
def publish():
    """Ana publish fonksiyonu."""
    project_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(project_dir)

    print("=" * 60)
    print(f"  PUBLISH - Manifest & Diff & Feature Olusturucu")
    print(f"  Proje: {PROJECT_NAME}")
    print("=" * 60)

    if BASE_URL == "BURAYA_GITHUB_RAW_URL_YAZIN":
        print("\n[UYARI] BASE_URL henuz ayarlanmamis!")
        print("publish.py dosyasinda BASE_URL degerini GitHub raw URL'niz ile degistirin.")

    # Mevcut manifest'i yukle
    existing = load_existing_manifest()
    existing_files = existing.get("files", {}) if existing else {}
    current_manifest_version = existing.get("manifest_version", 10000) if existing else 10000

    # Projeyi tara
    print("\n[*] Proje dosyalari taraniyor...")
    scanned_files = scan_project(project_dir)

    # Eski diffs klasorunu temizle
    diffs_path = os.path.join(project_dir, DIFFS_DIR)
    if os.path.exists(diffs_path):
        import shutil
        shutil.rmtree(diffs_path)
    os.makedirs(diffs_path, exist_ok=True)

    # Degisiklikleri karsilastir
    new_files = {}
    stats = {"unchanged": 0, "updated": 0, "new": 0, "removed": 0, "diff_generated": 0}

    for rel_path, file_hash in sorted(scanned_files.items()):
        if rel_path in existing_files:
            old_hash = existing_files[rel_path].get("hash", "")
            old_version = existing_files[rel_path].get("version", 10000)

            if old_hash == file_hash:
                # Degismemis
                new_files[rel_path] = {
                    "version": old_version,
                    "hash": file_hash,
                    "has_diff": False,
                }
                stats["unchanged"] += 1
                print(f"  [ ] {rel_path} (v{old_version})")
            else:
                # Degismis - versiyon artir
                new_version = old_version + 1
                file_info = {
                    "version": new_version,
                    "hash": file_hash,
                    "has_diff": False,
                }

                # Diff olustur (sadece text dosyalar icin)
                if not is_binary_file(rel_path):
                    full_path = os.path.join(project_dir, rel_path.replace("/", os.sep))
                    try:
                        with open(full_path, "r", encoding="utf-8") as f:
                            new_content = f.read()
                    except (IOError, UnicodeDecodeError):
                        new_content = None

                    if new_content:
                        old_content = fetch_old_file_from_github(rel_path, BASE_URL)
                        if old_content:
                            diff = generate_diff(old_content, new_content, rel_path)
                            if diff:
                                diff_rel = save_diff(project_dir, rel_path, diff)
                                diff_hash = calculate_content_hash(diff)
                                file_info["has_diff"] = True
                                file_info["diff_path"] = diff_rel
                                file_info["diff_hash"] = diff_hash
                                stats["diff_generated"] += 1
                                print(f"  [~] {rel_path} (v{old_version} -> v{new_version}) [DIFF URETILDI]")
                            else:
                                print(f"  [~] {rel_path} (v{old_version} -> v{new_version}) [diff bos]")
                        else:
                            print(f"  [~] {rel_path} (v{old_version} -> v{new_version}) [GitHub'dan cekilemedi]")
                    else:
                        print(f"  [~] {rel_path} (v{old_version} -> v{new_version})")
                else:
                    print(f"  [~] {rel_path} (v{old_version} -> v{new_version}) [binary]")

                new_files[rel_path] = file_info
                stats["updated"] += 1
        else:
            # Yeni dosya
            new_files[rel_path] = {"version": 10001, "hash": file_hash, "has_diff": False}
            stats["new"] += 1
            print(f"  [+] {rel_path} (v10001 - YENI)")

    # Silinen dosyalari tespit et
    for rel_path in existing_files:
        if rel_path not in scanned_files:
            stats["removed"] += 1
            print(f"  [-] {rel_path} (SILINDI)")

    # --- Feature Registry Tarama ---
    print("\n[*] Feature marker'lar taraniyor...")
    feature_registry = scan_all_features(project_dir)
    feature_count = sum(
        len(fdata["features"])
        for fdata in feature_registry["files"].values()
    )
    print(f"  [OK] {len(feature_registry['files'])} dosyada {feature_count} ozellik bulundu.")
    save_feature_registry(feature_registry)
    print(f"  [OK] {FEATURE_REGISTRY_FILE} guncellendi.")

    # Manifest'i olustur
    has_changes = (stats["updated"] + stats["new"] + stats["removed"]) > 0
    new_manifest_version = current_manifest_version + 1 if has_changes else current_manifest_version

    manifest = {
        "project_name": PROJECT_NAME,
        "manifest_version": new_manifest_version,
        "base_url": BASE_URL,
        "last_updated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "files": new_files,
        "exclude": [
            ".venv/",
            "__pycache__/",
            "old/",
            "data/chat_history.json",
            "data/long_memory.json",
            "data/user_profile.json",
            "data/archives/",
        ],
    }

    with open(MANIFEST_FILE, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    # Ozet
    print("\n" + "=" * 60)
    print(f"  SONUC")
    print(f"  Manifest Versiyonu: v{new_manifest_version}")
    print(f"  Toplam Dosya: {len(new_files)}")
    print(f"  Degismemis: {stats['unchanged']}")
    print(f"  Guncellenen: {stats['updated']}")
    print(f"  Yeni Eklenen: {stats['new']}")
    print(f"  Silinen: {stats['removed']}")
    print(f"  Diff Uretilen: {stats['diff_generated']}")
    print(f"  Feature Sayisi: {feature_count}")
    print("=" * 60)

    if has_changes:
        print("\n[OK] manifest.json guncellendi!")
        print("[!] Simdi GitHub'a push edin:")
        print("    git add .")
        print('    git commit -m "Guncelleme v{}"'.format(new_manifest_version))
        print("    git push")
    else:
        print("\n[OK] Degisiklik yok, manifest ayni kaldi.")
# --- END FEATURE: publish ---


if __name__ == "__main__":
    publish()

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
