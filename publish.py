"""
PUBLISH.PY - Manifest Olusturucu
=================================
Proje dosyalarini tarar, hash hesaplar ve manifest.json'u gunceller.
Degisiklik yaptiktan sonra, GitHub'a push etmeden once bunu calistirin.

Kullanim:
    python publish.py
"""

import os
import sys
import json
import hashlib
import time

# --- YAPILANDIRMA ---
MANIFEST_FILE = "manifest.json"
PROJECT_NAME = "Yapay Zeka Asistani v2"
# GitHub raw URL - repoyu olusturduktan sonra guncelleyin
# Ornek: https://raw.githubusercontent.com/KULLANICI/REPO/main/
BASE_URL = "BURAYA_GITHUB_RAW_URL_YAZIN"

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
    "updater.py",
    "updater.bat",
    "manifest.json",
    # Manifest ve updater kendini guncellemez
]

# Sadece bu uzantilari tara (guvenlik icin)
ALLOWED_EXTENSIONS = [
    ".py", ".txt", ".json", ".bat", ".html", ".css", ".js",
    ".md", ".yaml", ".yml", ".toml", ".cfg", ".ini", ".env",
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico",
]


def should_exclude(filepath):
    """Dosyanin exclude listesinde olup olmadigini kontrol eder."""
    normalized = filepath.replace("\\", "/")
    for pattern in EXCLUDE_PATTERNS:
        pattern_normalized = pattern.replace("\\", "/")
        if pattern_normalized.endswith("/"):
            # Klasor pattern'i
            if normalized.startswith(pattern_normalized) or ("/" + pattern_normalized) in ("/" + normalized):
                return True
        else:
            # Dosya pattern'i
            if normalized == pattern_normalized or normalized.endswith("/" + pattern_normalized):
                return True
    return False


def calculate_hash(filepath):
    """Dosyanin SHA256 hash degerini hesaplar."""
    sha256 = hashlib.sha256()
    try:
        with open(filepath, "rb") as f:
            while True:
                chunk = f.read(8192)
                if not chunk:
                    break
                sha256.update(chunk)
        return sha256.hexdigest()
    except (IOError, OSError) as e:
        print(f"  [!] Hash hesaplanamadi: {filepath} - {e}")
        return None


def scan_project(project_dir):
    """Proje klasorundeki tum dosyalari tarar."""
    files = {}
    for root, dirs, filenames in os.walk(project_dir):
        # Exclude olan klasorleri atla
        dirs[:] = [d for d in dirs if not should_exclude(
            os.path.relpath(os.path.join(root, d), project_dir) + "/"
        )]

        for filename in filenames:
            full_path = os.path.join(root, filename)
            rel_path = os.path.relpath(full_path, project_dir).replace("\\", "/")

            if should_exclude(rel_path):
                continue

            # Uzanti kontrolu
            _, ext = os.path.splitext(filename)
            if ext.lower() not in ALLOWED_EXTENSIONS:
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


def publish():
    """Ana publish fonksiyonu."""
    project_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(project_dir)

    print("=" * 60)
    print(f"  PUBLISH - Manifest Olusturucu")
    print(f"  Proje: {PROJECT_NAME}")
    print("=" * 60)

    if BASE_URL == "BURAYA_GITHUB_RAW_URL_YAZIN":
        print("\n[UYARI] BASE_URL henuz ayarlanmamis!")
        print("publish.py dosyasinda BASE_URL degerini GitHub raw URL'niz ile degistirin.")
        print("Ornek: https://raw.githubusercontent.com/KULLANICI/REPO/main/")
        print("\nManifest yine de olusturulacak, ancak updater calistiramaz.\n")

    # Mevcut manifest'i yukle
    existing = load_existing_manifest()
    existing_files = existing.get("files", {}) if existing else {}
    current_manifest_version = existing.get("manifest_version", 10000) if existing else 10000

    # Projeyi tara
    print("\n[*] Proje dosyalari taraniyor...")
    scanned_files = scan_project(project_dir)

    # Degisiklikleri karsilastir
    new_files = {}
    stats = {"unchanged": 0, "updated": 0, "new": 0, "removed": 0}

    for rel_path, file_hash in sorted(scanned_files.items()):
        if rel_path in existing_files:
            old_hash = existing_files[rel_path].get("hash", "")
            old_version = existing_files[rel_path].get("version", 10000)

            if old_hash == file_hash:
                # Degismemis
                new_files[rel_path] = {"version": old_version, "hash": file_hash}
                stats["unchanged"] += 1
                print(f"  [ ] {rel_path} (v{old_version})")
            else:
                # Degismis - versiyon artir
                new_version = old_version + 1
                new_files[rel_path] = {"version": new_version, "hash": file_hash}
                stats["updated"] += 1
                print(f"  [~] {rel_path} (v{old_version} -> v{new_version})")
        else:
            # Yeni dosya
            new_files[rel_path] = {"version": 10001, "hash": file_hash}
            stats["new"] += 1
            print(f"  [+] {rel_path} (v10001 - YENI)")

    # Silinen dosyalari tespit et
    for rel_path in existing_files:
        if rel_path not in scanned_files:
            stats["removed"] += 1
            print(f"  [-] {rel_path} (SILINDI)")

    # Manifest'i olustur
    new_manifest_version = current_manifest_version + 1 if (stats["updated"] + stats["new"] + stats["removed"]) > 0 else current_manifest_version

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

    # Kaydet
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
    print("=" * 60)

    if stats["updated"] + stats["new"] + stats["removed"] > 0:
        print("\n[OK] manifest.json guncellendi!")
        print("[!] Simdi GitHub'a push edin:")
        print("    git add .")
        print('    git commit -m "Guncelleme v{}"'.format(new_manifest_version))
        print("    git push")
    else:
        print("\n[OK] Degisiklik yok, manifest ayni kaldi.")


if __name__ == "__main__":
    publish()
