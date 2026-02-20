"""
UPDATER.PY - Otomatik Guncelleme Sistemi
==========================================
Uzak sunucudan (GitHub) manifest'i ceker, yerel dosyalarla karsilastirir
ve degisen/yeni dosyalari otomatik indirir.

Kullanim:
    python updater.py
    veya cift tikla: updater.bat
"""

import os
import sys
import json
import hashlib
import shutil
import subprocess
import time

# requests kutuphanesi yoksa kur
try:
    import requests
except ImportError:
    print("[*] 'requests' kutuphanesi kuruluyor...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "-q"])
    import requests

# --- YAPILANDIRMA ---
MANIFEST_FILE = "manifest.json"
BACKUP_DIR = ".update_backup"

# Windows konsol renk destegi
if sys.platform == "win32":
    os.system("")  # ANSI escape kodlarini aktif et


class Colors:
    """Konsol renk kodlari."""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    DIM = "\033[2m"


def print_header():
    """Baslik yazdir."""
    print(f"\n{Colors.CYAN}{Colors.BOLD}")
    print("=" * 60)
    print("   OTOMATIK GUNCELLEME SISTEMI")
    print("   Yapay Zeka Asistani v2")
    print("=" * 60)
    print(f"{Colors.RESET}")


def print_status(icon, message, color=Colors.RESET):
    """Formatli durum mesaji yazdir."""
    print(f"  {color}{icon}{Colors.RESET} {message}")


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
    except (IOError, OSError):
        return None


def load_local_manifest():
    """Yerel manifest dosyasini yukler."""
    if os.path.exists(MANIFEST_FILE):
        try:
            with open(MANIFEST_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return None


def fetch_remote_manifest(base_url):
    """Uzak sunucudan manifest'i indirir."""
    manifest_url = base_url.rstrip("/") + "/manifest.json"
    try:
        response = requests.get(manifest_url, timeout=15)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print_status("[X]", f"Manifest indirilemedi: {e}", Colors.RED)
        return None
    except json.JSONDecodeError:
        print_status("[X]", "Manifest dosyasi bozuk!", Colors.RED)
        return None


def download_file(base_url, rel_path, dest_path):
    """Tek bir dosyayi uzak sunucudan indirir."""
    file_url = base_url.rstrip("/") + "/" + rel_path.replace("\\", "/")
    try:
        response = requests.get(file_url, timeout=30, stream=True)
        response.raise_for_status()

        # Klasoru olustur
        dest_dir = os.path.dirname(dest_path)
        if dest_dir and not os.path.exists(dest_dir):
            os.makedirs(dest_dir, exist_ok=True)

        # Dosyayi yaz
        with open(dest_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        return True
    except requests.exceptions.RequestException as e:
        print_status("[X]", f"Indirme hatasi: {rel_path} - {e}", Colors.RED)
        return False


def backup_file(project_dir, rel_path):
    """Dosyayi yedekler."""
    src = os.path.join(project_dir, rel_path)
    if os.path.exists(src):
        backup_path = os.path.join(project_dir, BACKUP_DIR, rel_path)
        backup_dir = os.path.dirname(backup_path)
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir, exist_ok=True)
        shutil.copy2(src, backup_path)


def update():
    """Ana guncelleme fonksiyonu."""
    project_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(project_dir)

    print_header()

    # --- Adim 1: Yerel manifest'i oku ---
    print(f"\n{Colors.BOLD}[1/4] Yerel manifest okunuyor...{Colors.RESET}")
    local_manifest = load_local_manifest()

    if local_manifest is None:
        print_status("[!]", "Yerel manifest bulunamadi. Ilk kurulum olarak devam ediliyor.", Colors.YELLOW)
        local_manifest = {"files": {}, "manifest_version": 0}

    local_files = local_manifest.get("files", {})
    local_version = local_manifest.get("manifest_version", 0)

    # base_url'i yerel manifest'ten veya varsayilandan al
    base_url = local_manifest.get("base_url", "")

    if not base_url or base_url == "BURAYA_GITHUB_RAW_URL_YAZIN":
        print_status("[X]", "base_url ayarlanmamis!", Colors.RED)
        print(f"\n  {Colors.YELLOW}manifest.json dosyasindaki 'base_url' degerini ayarlayin.{Colors.RESET}")
        print(f"  {Colors.DIM}Ornek: https://raw.githubusercontent.com/KULLANICI/REPO/main/{Colors.RESET}")
        input("\nCikmak icin Enter'a basin...")
        return

    print_status("[OK]", f"Yerel manifest versiyonu: v{local_version}", Colors.GREEN)

    # --- Adim 2: Uzak manifest'i indir ---
    print(f"\n{Colors.BOLD}[2/4] Uzak manifest indiriliyor...{Colors.RESET}")
    print_status("[*]", f"Kaynak: {base_url}", Colors.DIM)

    remote_manifest = fetch_remote_manifest(base_url)
    if remote_manifest is None:
        print(f"\n{Colors.RED}Guncelleme basarisiz! Sunucuya ulasilamadi.{Colors.RESET}")
        input("\nCikmak icin Enter'a basin...")
        return

    remote_files = remote_manifest.get("files", {})
    remote_version = remote_manifest.get("manifest_version", 0)

    print_status("[OK]", f"Uzak manifest versiyonu: v{remote_version}", Colors.GREEN)

    if remote_version <= local_version:
        print(f"\n{Colors.GREEN}{Colors.BOLD}  Program zaten guncel! (v{local_version}){Colors.RESET}")
        input("\nCikmak icin Enter'a basin...")
        return

    # --- Adim 3: Dosyalari karsilastir ve guncelle ---
    print(f"\n{Colors.BOLD}[3/4] Dosyalar kontrol ediliyor...{Colors.RESET}")

    stats = {"downloaded": 0, "skipped": 0, "failed": 0, "new": 0}
    requirements_changed = False

    # Yedek klasorunu temizle
    backup_path = os.path.join(project_dir, BACKUP_DIR)
    if os.path.exists(backup_path):
        shutil.rmtree(backup_path)

    for rel_path, remote_info in sorted(remote_files.items()):
        remote_version_num = remote_info.get("version", 0)
        remote_hash = remote_info.get("hash", "")

        local_info = local_files.get(rel_path, None)
        local_version_num = local_info.get("version", 0) if local_info else 0

        dest_path = os.path.join(project_dir, rel_path.replace("/", os.sep))

        needs_update = False

        if local_info is None:
            # Dosya yerelde yok - kontrol et belki dosya var ama manifest'te kayitli degil
            if os.path.exists(dest_path):
                current_hash = calculate_hash(dest_path)
                if current_hash == remote_hash:
                    # Dosya ayni, sadece manifest'i guncelle
                    print_status("[ ]", f"{rel_path} (zaten mevcut, hash esit)", Colors.DIM)
                    stats["skipped"] += 1
                    continue
                else:
                    needs_update = True
                    print_status("[+]", f"{rel_path} (manifest'te yok, hash farkli -> guncelleniyor)", Colors.YELLOW)
            else:
                needs_update = True
                print_status("[+]", f"{rel_path} (YENI DOSYA -> indiriliyor)", Colors.CYAN)
                stats["new"] += 1
        elif remote_version_num > local_version_num:
            # Versiyon daha yuksek - guncelle
            needs_update = True
            print_status("[~]", f"{rel_path} (v{local_version_num} -> v{remote_version_num})", Colors.YELLOW)
        else:
            # Versiyon ayni - hash kontrolu
            if os.path.exists(dest_path):
                current_hash = calculate_hash(dest_path)
                if current_hash != remote_hash:
                    needs_update = True
                    print_status("[~]", f"{rel_path} (hash farkli -> guncelleniyor)", Colors.YELLOW)
                else:
                    print_status("[ ]", f"{rel_path} (v{local_version_num} - guncel)", Colors.DIM)
                    stats["skipped"] += 1
                    continue
            else:
                needs_update = True
                print_status("[+]", f"{rel_path} (dosya eksik -> indiriliyor)", Colors.CYAN)

        if needs_update:
            # Yedekle
            backup_file(project_dir, rel_path)

            # Indir
            if download_file(base_url, rel_path, dest_path):
                # Hash dogrula
                downloaded_hash = calculate_hash(dest_path)
                if downloaded_hash == remote_hash:
                    print_status("  OK", "Basariyla indirildi ve dogrulandi", Colors.GREEN)
                    stats["downloaded"] += 1

                    if rel_path == "requirements.txt":
                        requirements_changed = True
                else:
                    print_status("  !!", "Hash uyusmuyor! Yedekten geri yukleniyor...", Colors.RED)
                    # Yedekten geri yukle
                    backup_src = os.path.join(project_dir, BACKUP_DIR, rel_path)
                    if os.path.exists(backup_src):
                        shutil.copy2(backup_src, dest_path)
                    stats["failed"] += 1
            else:
                stats["failed"] += 1

    # --- Adim 4: requirements.txt degistiyse pip install ---
    print(f"\n{Colors.BOLD}[4/4] Son islemler...{Colors.RESET}")

    if requirements_changed:
        print_status("[*]", "requirements.txt degisti! Gereksinimler kuruluyor...", Colors.YELLOW)
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "-r", "requirements.txt", "-q"],
                check=True,
                timeout=300,
            )
            print_status("[OK]", "Gereksinimler basariyla kuruldu!", Colors.GREEN)
        except subprocess.CalledProcessError:
            print_status("[X]", "Gereksinimler kurulurken hata olustu!", Colors.RED)
            print_status("  ", "Manuel olarak calistirin: pip install -r requirements.txt", Colors.YELLOW)
        except subprocess.TimeoutExpired:
            print_status("[X]", "Gereksinim kurulumu zaman asimina ugradi!", Colors.RED)
    else:
        print_status("[OK]", "requirements.txt degismedi, gereksinim kurulumu atlanildi.", Colors.GREEN)

    # Yerel manifest'i guncelle
    with open(MANIFEST_FILE, "w", encoding="utf-8") as f:
        json.dump(remote_manifest, f, indent=2, ensure_ascii=False)
    print_status("[OK]", "Yerel manifest guncellendi.", Colors.GREEN)

    # Yedekleri temizle (basarili guncelleme)
    if stats["failed"] == 0 and os.path.exists(backup_path):
        shutil.rmtree(backup_path)

    # --- Ozet ---
    print(f"\n{Colors.CYAN}{'=' * 60}{Colors.RESET}")
    total = stats["downloaded"] + stats["new"]
    if stats["failed"] > 0:
        color = Colors.YELLOW
        icon = "[!]"
    elif total > 0:
        color = Colors.GREEN
        icon = "[OK]"
    else:
        color = Colors.GREEN
        icon = "[OK]"

    print(f"  {color}{Colors.BOLD}GUNCELLEME TAMAMLANDI{Colors.RESET}")
    print(f"  Manifest: v{local_version} -> v{remote_version}")
    print(f"  Guncellenen: {Colors.YELLOW}{stats['downloaded']}{Colors.RESET} dosya")
    print(f"  Yeni Eklenen: {Colors.CYAN}{stats['new']}{Colors.RESET} dosya")
    print(f"  Atlanan (guncel): {Colors.DIM}{stats['skipped']}{Colors.RESET} dosya")

    if stats["failed"] > 0:
        print(f"  {Colors.RED}Basarisiz: {stats['failed']} dosya{Colors.RESET}")
        print(f"  {Colors.YELLOW}Yedekler .update_backup/ klasorunde saklanmaktadir.{Colors.RESET}")

    print(f"{Colors.CYAN}{'=' * 60}{Colors.RESET}")
    input("\nCikmak icin Enter'a basin...")


if __name__ == "__main__":
    update()
