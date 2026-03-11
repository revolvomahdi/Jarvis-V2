"""
UPDATER.PY - Otomatik Guncelleme Sistemi (Gelistirilmis)
==========================================================
Uzak sunucudan (GitHub) manifest'i ceker, yerel dosyalarla karsilastirir.
Yeni ozellikler:
  - Satir bazli diff guncelleme (fallback: tam dosya)
  - Ozellik birlestirme (Feature Merge) sistemi
  - Cakisma tespiti ve kullanici secimi

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
import re

# requests kutuphanesi yoksa kur
try:
    import requests
except ImportError:
    print("[*] 'requests' kutuphanesi kuruluyor...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "-q"])
    import requests

# --- YAPILANDIRMA ---
MANIFEST_FILE = "manifest.json"
FEATURE_REGISTRY_FILE = "feature_registry.json"
BACKUP_DIR = ".update_backup"
DIFFS_DIR = "diffs"
DEFAULT_BASE_URL = "https://raw.githubusercontent.com/revolvomahdi/Jarvis-V2/main/"

# Feature marker pattern
FEATURE_START_PATTERN = re.compile(r"^#\s*---\s*FEATURE:\s*(\S+)\s*---\s*$")
FEATURE_END_PATTERN = re.compile(r"^#\s*---\s*END\s+FEATURE:\s*(\S+)\s*---\s*$")

# Windows konsol renk destegi
if sys.platform == "win32":
    os.system("")  # ANSI escape kodlarini aktif et


# --- FEATURE: colors ---
class Colors:
    """Konsol renk kodlari."""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    MAGENTA = "\033[95m"
    DIM = "\033[2m"


def print_header():
    """Baslik yazdir."""
    print(f"\n{Colors.CYAN}{Colors.BOLD}")
    print("=" * 60)
    print("   OTOMATIK GUNCELLEME SISTEMI (v2.0)")
    print("   Yapay Zeka Asistani v2")
    print("   Diff + Feature Merge Destekli")
    print("=" * 60)
    print(f"{Colors.RESET}")


def print_status(icon, message, color=Colors.RESET):
    """Formatli durum mesaji yazdir."""
    print(f"  {color}{icon}{Colors.RESET} {message}")
# --- END FEATURE: colors ---


# Binary dosya uzantilari
BINARY_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico",
    ".mp3", ".wav", ".ogg",
    ".zip", ".tar", ".gz", ".bz2",
    ".pdf", ".exe", ".dll",
}


# --- FEATURE: is_binary_file ---
def is_binary_file(filepath):
    """Dosyanin binary olup olmadigini kontrol eder."""
    _, ext = os.path.splitext(filepath)
    return ext.lower() in BINARY_EXTENSIONS


def calculate_hash(filepath):
    """Dosyanin SHA256 hash degerini hesaplar."""
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
    except (IOError, OSError):
        return None


def calculate_content_hash(content):
    """String icerigin SHA256 hash degerini hesaplar."""
    if isinstance(content, str):
        content = content.encode("utf-8")
    content = content.replace(b"\r\n", b"\n")
    return hashlib.sha256(content).hexdigest()


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

        dest_dir = os.path.dirname(dest_path)
        if dest_dir and not os.path.exists(dest_dir):
            os.makedirs(dest_dir, exist_ok=True)

        with open(dest_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        return True
    except requests.exceptions.RequestException as e:
        print_status("[X]", f"Indirme hatasi: {rel_path} - {e}", Colors.RED)
        return False


def download_text_file(base_url, rel_path):
    """Uzak sunucudan text dosya indirir ve icerigini dondurur."""
    file_url = base_url.rstrip("/") + "/" + rel_path.replace("\\", "/")
    try:
        response = requests.get(file_url, timeout=30)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException:
        return None


def backup_file(project_dir, rel_path):
    """Dosyayi yedekler."""
    src = os.path.join(project_dir, rel_path)
    if os.path.exists(src):
        backup_path = os.path.join(project_dir, BACKUP_DIR, rel_path)
        backup_dir = os.path.dirname(backup_path)
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir, exist_ok=True)
        shutil.copy2(src, backup_path)
# --- END FEATURE: is_binary_file ---


# ============================================================
# DIFF UYGULAMA (PATCH)
# ============================================================

# --- FEATURE: apply_unified_diff ---
def apply_unified_diff(original_content, diff_content):
    """Unified diff formatindaki patch'i uygular.
    
    Returns:
        (patched_content, success) tuple
    """
    try:
        original_lines = original_content.replace("\r\n", "\n").split("\n")
        diff_lines = diff_content.replace("\r\n", "\n").split("\n")

        # Diff header'larini atla (--- ve +++ satirlari)
        diff_idx = 0
        while diff_idx < len(diff_lines) and not diff_lines[diff_idx].startswith("@@"):
            diff_idx += 1

        if diff_idx >= len(diff_lines):
            return original_content, False

        # Tum hunklari once parse et
        hunks = []
        while diff_idx < len(diff_lines):
            line = diff_lines[diff_idx]

            if not line.startswith("@@"):
                diff_idx += 1
                continue

            # Hunk header: @@ -old_start,old_count +new_start,new_count @@
            hunk_match = re.match(r"^@@\s*-(\d+)(?:,(\d+))?\s*\+(\d+)(?:,(\d+))?\s*@@", line)
            if not hunk_match:
                diff_idx += 1
                continue

            old_start = int(hunk_match.group(1)) - 1  # 0-indexed
            old_count = int(hunk_match.group(2)) if hunk_match.group(2) else 1

            # Hunk icerigini oku
            hunk_ops = []
            diff_idx += 1
            old_consumed = 0
            
            while diff_idx < len(diff_lines) and old_consumed < old_count:
                dline = diff_lines[diff_idx]
                
                # Yeni hunk veya diff baslangici -> bu hunk bitti
                if dline.startswith("@@"):
                    break
                
                if dline.startswith("\\"):
                    # "\ No newline at end of file" gibi satirlar
                    diff_idx += 1
                    continue
                elif dline.startswith("-"):
                    hunk_ops.append(("remove", dline[1:]))
                    old_consumed += 1
                elif dline.startswith("+"):
                    hunk_ops.append(("add", dline[1:]))
                elif dline.startswith(" "):
                    hunk_ops.append(("context", dline[1:]))
                    old_consumed += 1
                else:
                    # Bos satir veya context satiri (bazi diff formatlari bosluk koymaz)
                    # old_count'a bakilarak hunk sona erdigi anlasilir
                    hunk_ops.append(("context", dline))
                    old_consumed += 1
                
                diff_idx += 1
            
            # old_count tamamlandiktan sonra kalan + satirlarini da al
            while diff_idx < len(diff_lines):
                dline = diff_lines[diff_idx]
                if dline.startswith("+"):
                    hunk_ops.append(("add", dline[1:]))
                    diff_idx += 1
                elif dline.startswith("\\"):
                    diff_idx += 1
                else:
                    break

            hunks.append((old_start, hunk_ops))

        # Hunklari sirala ve uygula (sondan basa, offset sorunu olmasin)
        hunks.sort(key=lambda h: h[0], reverse=True)
        
        result_lines = list(original_lines)
        
        for old_start, hunk_ops in hunks:
            new_section = []
            remove_count = 0

            for op_type, op_content in hunk_ops:
                if op_type == "context":
                    new_section.append(op_content)
                    remove_count += 1
                elif op_type == "remove":
                    remove_count += 1
                elif op_type == "add":
                    new_section.append(op_content)

            result_lines[old_start:old_start + remove_count] = new_section

        return "\n".join(result_lines), True

    except Exception as e:
        return original_content, False


def download_and_apply_diff(base_url, rel_path, dest_path, diff_info):
    """Diff dosyasini indirir ve yerele uygular.
    
    Returns:
        True: diff basarili uygulandi
        False: diff uygulanamadi (fallback gerekli)
    """
    diff_path = diff_info.get("diff_path", "")
    if not diff_path:
        return False

    # Diff dosyasini indir
    diff_url = base_url.rstrip("/") + "/" + DIFFS_DIR + "/" + diff_path.replace("\\", "/")
    try:
        response = requests.get(diff_url, timeout=15)
        response.raise_for_status()
        diff_content = response.text
    except requests.exceptions.RequestException:
        print_status("  !!", "Diff dosyasi indirilemedi, tam dosya indirilecek.", Colors.YELLOW)
        return False

    # Diff hash kontrolu
    expected_hash = diff_info.get("diff_hash", "")
    if expected_hash:
        actual_hash = calculate_content_hash(diff_content)
        if actual_hash != expected_hash:
            print_status("  !!", "Diff hash uyusmuyor, tam dosya indirilecek.", Colors.YELLOW)
            return False

    # Yerel dosyayi oku
    if not os.path.exists(dest_path):
        return False

    try:
        with open(dest_path, "r", encoding="utf-8") as f:
            local_content = f.read()
    except (IOError, UnicodeDecodeError):
        return False

    # Diff'i uygula
    patched_content, success = apply_unified_diff(local_content, diff_content)

    if not success:
        print_status("  !!", "Diff uygulanamadi, tam dosya indirilecek.", Colors.YELLOW)
        return False

    # Patched dosyayi yaz
    try:
        with open(dest_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(patched_content)
        return True
    except IOError:
        return False
# --- END FEATURE: apply_unified_diff ---


# ============================================================
# FEATURE MERGE (OZELLIK BIRLESTIRME)
# ============================================================

# --- FEATURE: feature_merger ---
class FeatureMerger:
    """Ozellik birlestirme ve cakisma yonetimi."""

    @staticmethod
    def extract_features_from_content(content):
        """Dosya iceriginden feature marker'lari cikarir.
        
        Returns:
            dict: {feature_id: {"content": str, "hash": str, "start": int, "end": int}}
        """
        features = {}
        lines = content.replace("\r\n", "\n").split("\n")

        current_feature = None
        feature_lines = []
        feature_start = -1

        for i, line in enumerate(lines):
            stripped = line.strip()

            start_match = FEATURE_START_PATTERN.match(stripped)
            if start_match:
                current_feature = start_match.group(1)
                feature_lines = [line]
                feature_start = i
                continue

            if current_feature:
                feature_lines.append(line)
                end_match = FEATURE_END_PATTERN.match(stripped)
                if end_match and end_match.group(1) == current_feature:
                    feature_content = "\n".join(feature_lines)
                    feature_hash = calculate_content_hash(feature_content)

                    features[current_feature] = {
                        "content": feature_content,
                        "hash": feature_hash,
                        "start_line": feature_start,
                        "end_line": i,
                    }

                    current_feature = None
                    feature_lines = []

        return features

    @staticmethod
    def find_insert_position(lines, position_after=None, feature_registry_entry=None):
        """Yeni ozelligi eklemek icin uygun satir numarasini bulur.
        
        Strateji:
        1. position_after baska bir feature ise, o feature'in END marker'indan sonra
        2. position_after = "imports" ise, import blogunun sonrasi
        3. Hicbiri yoksa, dosya sonundaki AI notundan once
        """
        if position_after and position_after != "imports":
            # Belirtilen feature'dan sonra ekle
            for i, line in enumerate(lines):
                stripped = line.strip()
                end_match = FEATURE_END_PATTERN.match(stripped)
                if end_match and end_match.group(1) == position_after:
                    return i + 1

        if position_after == "imports":
            # Import blogunun sonunu bul
            last_import = -1
            for i, line in enumerate(lines):
                stripped = line.strip()
                if stripped.startswith("import ") or stripped.startswith("from "):
                    last_import = i
                elif last_import >= 0 and stripped and not stripped.startswith("#"):
                    return last_import + 2  # Import'lardan sonra bir bos satir birak
            if last_import >= 0:
                return last_import + 2

        # AI notundan once ekle (eger varsa)
        for i, line in enumerate(lines):
            if "GELISTIRICI NOTU (AI & Insan)" in line:
                return max(0, i - 1)

        # Dosyanin sonuna ekle
        return len(lines)

    @staticmethod
    def _extract_code_body(feature_content):
        """Feature iceriginden marker satirlarini cikarip saf kodu dondurur."""
        lines = feature_content.split("\n")
        # Marker satirlarini cikar
        code_lines = []
        for line in lines:
            stripped = line.strip()
            if FEATURE_START_PATTERN.match(stripped) or FEATURE_END_PATTERN.match(stripped):
                continue
            code_lines.append(line)
        return "\n".join(code_lines).strip()

    @staticmethod
    def _extract_function_names(code_body):
        """Kod blogundan fonksiyon ve sinif adlarini cikarir."""
        names = set()
        for line in code_body.split("\n"):
            stripped = line.strip()
            # def xxx( veya class xxx: veya class xxx(
            if stripped.startswith("def "):
                name = stripped[4:].split("(")[0].strip()
                if name:
                    names.add(name)
            elif stripped.startswith("class "):
                name = stripped[6:].split("(")[0].split(":")[0].strip()
                if name:
                    names.add(name)
        return names

    @staticmethod
    def calculate_similarity(code1, code2):
        """Iki kod blogu arasindaki benzerlik oranini hesaplar (0.0 - 1.0).
        
        Hem metin benzerligini hem fonksiyon adi eslesmesini dikkate alir.
        """
        import difflib
        
        body1 = FeatureMerger._extract_code_body(code1)
        body2 = FeatureMerger._extract_code_body(code2)
        
        if not body1 or not body2:
            return 0.0
        
        # 1. Metin benzerligi (SequenceMatcher)
        text_similarity = difflib.SequenceMatcher(None, body1, body2).ratio()
        
        # 2. Fonksiyon/sinif adi eslesmesi
        names1 = FeatureMerger._extract_function_names(body1)
        names2 = FeatureMerger._extract_function_names(body2)
        
        if names1 and names2:
            common = names1 & names2
            total = names1 | names2
            name_similarity = len(common) / len(total) if total else 0.0
        else:
            name_similarity = 0.0
        
        # Agirlikli ortalama: metin %60, isim %40
        # Eger fonksiyon isimleri eslesmiyorsa sadece metin benzerligine bak
        if names1 and names2:
            combined = (text_similarity * 0.6) + (name_similarity * 0.4)
        else:
            combined = text_similarity
        
        return combined

    @staticmethod
    def detect_duplicates(local_features, remote_features, threshold=0.65):
        """Farkli isimli ama ayni/cok benzer ozellikleri tespit eder.
        
        Args:
            local_features: {id: {content, hash, ...}}
            remote_features: {id: {content, hash, ...}}
            threshold: Benzerlik esigi (0.0-1.0)
        
        Returns:
            List of {local_id, remote_id, similarity, local_content, remote_content}
        """
        duplicates = []
        
        for remote_id, remote_feat in remote_features.items():
            # ID zaten ayni ise duplicate diye sayma (bu zaten conflict olabilir)
            if remote_id in local_features:
                continue
            
            for local_id, local_feat in local_features.items():
                if local_id == remote_id:
                    continue
                
                similarity = FeatureMerger.calculate_similarity(
                    local_feat["content"], remote_feat["content"]
                )
                
                if similarity >= threshold:
                    duplicates.append({
                        "local_id": local_id,
                        "remote_id": remote_id,
                        "similarity": similarity,
                        "local_content": local_feat["content"],
                        "remote_content": remote_feat["content"],
                    })
        
        return duplicates

    @staticmethod
    def resolve_duplicate_interactive(duplicate):
        """Duplicate tespit edildiginde kullaniciya sorur.
        
        Returns:
            "skip" | "add" | "replace" | "rename"
        """
        local_id = duplicate["local_id"]
        remote_id = duplicate["remote_id"]
        similarity = duplicate["similarity"]
        
        print(f"\n{Colors.MAGENTA}{Colors.BOLD}{'=' * 55}")
        print(f"  AYNI OZELLIK FARKLI ISIM TESPIT EDILDI!")
        print(f"  Benzerlik: %{similarity * 100:.0f}")
        print(f"{'=' * 55}{Colors.RESET}")
        
        print(f"\n  Yerel isim:  {Colors.CYAN}{local_id}{Colors.RESET}")
        print(f"  Uzak isim:   {Colors.YELLOW}{remote_id}{Colors.RESET}")
        
        # Yerel koddan ilk 8 satir
        local_body = FeatureMerger._extract_code_body(duplicate["local_content"])
        remote_body = FeatureMerger._extract_code_body(duplicate["remote_content"])
        
        print(f"\n{Colors.CYAN}--- Yerel: {local_id} ---{Colors.RESET}")
        for line in local_body.split("\n")[:8]:
            print(f"  {Colors.DIM}{line}{Colors.RESET}")
        
        print(f"\n{Colors.YELLOW}--- Uzak: {remote_id} ---{Colors.RESET}")
        for line in remote_body.split("\n")[:8]:
            print(f"  {Colors.DIM}{line}{Colors.RESET}")
        
        while True:
            print(f"\n{Colors.BOLD}Bu iki ozellik ayni mi? Ne yapmak istersiniz?{Colors.RESET}")
            print(f"  {Colors.GREEN}[1]{Colors.RESET} Evet, ayni ozellik. Yereldekinı koru, uzaktakini EKLEME")
            print(f"  {Colors.BLUE}[2]{Colors.RESET} Evet, ayni ozellik. Uzaktaki versiyonu AL (yerelinkini degistir)")
            print(f"  {Colors.YELLOW}[3]{Colors.RESET} Hayir, farkli ozellikler. Uzaktakini de EKLE")
            print(f"  {Colors.MAGENTA}[4]{Colors.RESET} Evet, ayni ozellik. Uzaktakini yerel isimle YENIDEN ADLANDIR")
            
            try:
                choice = input(f"\n{Colors.BOLD}Seciminiz (1/2/3/4): {Colors.RESET}").strip()
            except (EOFError, KeyboardInterrupt):
                choice = "1"
            
            if choice == "1":
                return "skip"
            elif choice == "2":
                return "replace"
            elif choice == "3":
                return "add"
            elif choice == "4":
                return "rename"
            else:
                print(f"  {Colors.RED}Gecersiz secim! 1, 2, 3 veya 4 girin.{Colors.RESET}")

    @staticmethod
    def merge_features(local_content, remote_content, remote_registry_entry=None, auto_resolve=None):
        """Yerel ve uzak dosyalarin ozelliklerini birlestirir.
        
        Once duplicate tespiti yapar, sonra birlestirme/cakisma islemleri.
        
        Args:
            auto_resolve: None ise interactive sor, "skip"/"add"/"replace"/"rename" ise otomatik coz
        
        Returns:
            (merged_content, conflicts, added_features)
        """
        local_features = FeatureMerger.extract_features_from_content(local_content)
        remote_features = FeatureMerger.extract_features_from_content(remote_content)

        conflicts = []
        added_features = []
        skipped_remote_ids = set()  # Duplicate olarak atlanan uzak feature ID'leri
        local_lines = local_content.replace("\r\n", "\n").split("\n")

        # --- DUPLICATE TESPITI ---
        duplicates = FeatureMerger.detect_duplicates(local_features, remote_features)
        
        for dup in duplicates:
            if auto_resolve:
                resolution = auto_resolve
            else:
                resolution = FeatureMerger.resolve_duplicate_interactive(dup)
            
            if resolution == "skip":
                # Yereldekinı koru, uzaktakini ekleme
                skipped_remote_ids.add(dup["remote_id"])
            
            elif resolution == "replace":
                # Uzaktaki versiyonu al, yerelinkini degistir
                # Yereldeki feature'i uzaktaki ile degistir (marker adini da degistir)
                old_content = dup["local_content"]
                new_content = dup["remote_content"]
                local_content_str = "\n".join(local_lines)
                local_content_str = local_content_str.replace(old_content, new_content)
                local_lines = local_content_str.split("\n")
                skipped_remote_ids.add(dup["remote_id"])
            
            elif resolution == "add":
                # Farkli ozellikler, normal ekleme devam etsin
                pass
            
            elif resolution == "rename":
                # Uzaktaki ozelligi yerel isimle yeniden adlandir ve ekle
                # Marker adini degistir
                renamed_content = dup["remote_content"].replace(
                    f"# --- FEATURE: {dup['remote_id']} ---",
                    f"# --- FEATURE: {dup['local_id']} ---"
                ).replace(
                    f"# --- END FEATURE: {dup['remote_id']} ---",
                    f"# --- END FEATURE: {dup['local_id']} ---"
                )
                # Yereldekinı uzaktaki ile degistir (guncel versiyonu al)
                old_content = dup["local_content"]
                local_content_str = "\n".join(local_lines)
                local_content_str = local_content_str.replace(old_content, renamed_content)
                local_lines = local_content_str.split("\n")
                skipped_remote_ids.add(dup["remote_id"])

        # --- NORMAL BIRLESTIRME ---
        for feat_id, remote_feat in remote_features.items():
            # Duplicate olarak atlananları geç
            if feat_id in skipped_remote_ids:
                continue
            
            if feat_id in local_features:
                local_feat = local_features[feat_id]
                if local_feat["hash"] != remote_feat["hash"]:
                    conflicts.append({
                        "feature_id": feat_id,
                        "local_content": local_feat["content"],
                        "remote_content": remote_feat["content"],
                    })
            else:
                # Yerelde yok, ekle
                position_after = None
                if remote_registry_entry:
                    # Registry'den position bilgisini al
                    for feat_info in remote_registry_entry.get("features", []):
                        if feat_info.get("id") == feat_id:
                            position_after = feat_info.get("position_after")
                            break

                insert_pos = FeatureMerger.find_insert_position(
                    local_lines, position_after=position_after
                )

                # Ozelligi ekle
                feature_lines = remote_feat["content"].split("\n")
                # Bos satir ekle (ayirma icin)
                feature_lines = [""] + feature_lines + [""]

                for j, fl in enumerate(feature_lines):
                    local_lines.insert(insert_pos + j, fl)

                added_features.append(feat_id)

        merged_content = "\n".join(local_lines)
        return merged_content, conflicts, added_features

    @staticmethod
    def resolve_conflict_interactive(conflict):
        """Kullaniciya cakisma icin secim sorur.
        
        Returns:
            "local" | "remote" | "both"
        """
        feat_id = conflict["feature_id"]
        print(f"\n{Colors.YELLOW}{Colors.BOLD}{'=' * 50}")
        print(f"  CAKISMA TESPIT EDILDI: {feat_id}")
        print(f"{'=' * 50}{Colors.RESET}")

        print(f"\n{Colors.CYAN}--- Yerel Versiyon ---{Colors.RESET}")
        # Sadece ilk 10 satiri goster
        local_lines = conflict["local_content"].split("\n")
        for line in local_lines[:10]:
            print(f"  {Colors.DIM}{line}{Colors.RESET}")
        if len(local_lines) > 10:
            print(f"  {Colors.DIM}... ({len(local_lines) - 10} satir daha){Colors.RESET}")

        print(f"\n{Colors.MAGENTA}--- Uzak Versiyon ---{Colors.RESET}")
        remote_lines = conflict["remote_content"].split("\n")
        for line in remote_lines[:10]:
            print(f"  {Colors.DIM}{line}{Colors.RESET}")
        if len(remote_lines) > 10:
            print(f"  {Colors.DIM}... ({len(remote_lines) - 10} satir daha){Colors.RESET}")

        while True:
            print(f"\n{Colors.BOLD}Ne yapmak istersiniz?{Colors.RESET}")
            print(f"  {Colors.GREEN}[1]{Colors.RESET} Yerel versiyonu koru")
            print(f"  {Colors.BLUE}[2]{Colors.RESET} Uzak versiyonu al")
            print(f"  {Colors.YELLOW}[3]{Colors.RESET} Ikisini de koru (sonra elle duzenle)")
            try:
                choice = input(f"\n{Colors.BOLD}Seciminiz (1/2/3): {Colors.RESET}").strip()
            except (EOFError, KeyboardInterrupt):
                choice = "1"  # Default: yerel koru

            if choice == "1":
                return "local"
            elif choice == "2":
                return "remote"
            elif choice == "3":
                return "both"
            else:
                print(f"  {Colors.RED}Gecersiz secim! 1, 2 veya 3 girin.{Colors.RESET}")

    @staticmethod
    def apply_conflict_resolution(content, conflict, resolution):
        """Cakisma cozumunu dosyaya uygular.
        
        Returns:
            updated content
        """
        if resolution == "local":
            # Yerel koru - degisiklik yapma
            return content
        elif resolution == "remote":
            # Uzak versiyonu al - yerel feature'i uzak ile degistir
            return content.replace(conflict["local_content"], conflict["remote_content"])
        elif resolution == "both":
            # Ikisini de koru
            both_content = (
                f"# >>>>>> YEREL VERSIYON <<<<<<\n"
                f"{conflict['local_content']}\n"
                f"# >>>>>> UZAK VERSIYON <<<<<<\n"
                f"{conflict['remote_content']}\n"
                f"# >>>>>> CAKISMA SONU - Elle duzenlemeyi unutmayin! <<<<<<"
            )
            return content.replace(conflict["local_content"], both_content)

        return content
# --- END FEATURE: feature_merger ---


# ============================================================
# ANA GUNCELLEME FONKSIYONU
# ============================================================

# --- FEATURE: update ---
def update():
    """Ana guncelleme fonksiyonu."""
    project_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(project_dir)

    print_header()

    # --- Adim 1: Yerel manifest'i oku ---
    print(f"\n{Colors.BOLD}[1/5] Yerel manifest okunuyor...{Colors.RESET}")
    local_manifest = load_local_manifest()

    if local_manifest is None:
        print_status("[!]", "Yerel manifest bulunamadi. Ilk kurulum olarak devam ediliyor.", Colors.YELLOW)
        local_manifest = {"files": {}, "manifest_version": 0}

    local_files = local_manifest.get("files", {})
    local_version = local_manifest.get("manifest_version", 0)

    base_url = local_manifest.get("base_url", "")
    if not base_url or base_url == "BURAYA_GITHUB_RAW_URL_YAZIN":
        base_url = DEFAULT_BASE_URL
        print_status("[*]", f"Varsayilan URL kullaniliyor: {base_url}", Colors.YELLOW)

    print_status("[OK]", f"Yerel manifest versiyonu: v{local_version}", Colors.GREEN)

    # --- Adim 2: Uzak manifest'i indir ---
    print(f"\n{Colors.BOLD}[2/5] Uzak manifest indiriliyor...{Colors.RESET}")
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
    print(f"\n{Colors.BOLD}[3/5] Dosyalar kontrol ediliyor...{Colors.RESET}")

    stats = {"downloaded": 0, "patched": 0, "skipped": 0, "failed": 0, "new": 0}
    requirements_changed = False

    # Yedek klasorunu temizle
    backup_path = os.path.join(project_dir, BACKUP_DIR)
    if os.path.exists(backup_path):
        shutil.rmtree(backup_path)

    for rel_path, remote_info in sorted(remote_files.items()):
        remote_version_num = remote_info.get("version", 0)
        remote_hash = remote_info.get("hash", "")
        has_diff = remote_info.get("has_diff", False)

        local_info = local_files.get(rel_path, None)
        local_version_num = local_info.get("version", 0) if local_info else 0

        dest_path = os.path.join(project_dir, rel_path.replace("/", os.sep))

        needs_update = False

        if local_info is None:
            if os.path.exists(dest_path):
                current_hash = calculate_hash(dest_path)
                if current_hash == remote_hash:
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
            needs_update = True
            if has_diff:
                print_status("[~]", f"{rel_path} (v{local_version_num} -> v{remote_version_num}) [DIFF]", Colors.YELLOW)
            else:
                print_status("[~]", f"{rel_path} (v{local_version_num} -> v{remote_version_num})", Colors.YELLOW)
        else:
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
            backup_file(project_dir, rel_path)
            update_success = False

            # Diff ile guncelleme dene
            if has_diff and os.path.exists(dest_path) and not is_binary_file(rel_path):
                print_status("  >>", "Diff ile guncelleme deneniyor...", Colors.CYAN)
                diff_success = download_and_apply_diff(base_url, rel_path, dest_path, remote_info)

                if diff_success:
                    # Patch sonrasi hash kontrolu
                    patched_hash = calculate_hash(dest_path)
                    if patched_hash == remote_hash:
                        print_status("  OK", "Diff basariyla uygulandi!", Colors.GREEN)
                        stats["patched"] += 1
                        update_success = True

                        if rel_path == "requirements.txt":
                            requirements_changed = True
                    else:
                        print_status("  !!", "Diff sonrasi hash uyusmuyor, tam dosya indirilecek.", Colors.YELLOW)
                        # Yedekten geri yukle
                        backup_src = os.path.join(project_dir, BACKUP_DIR, rel_path)
                        if os.path.exists(backup_src):
                            shutil.copy2(backup_src, dest_path)

            # Diff basarisiz veya mevcut degil - tam dosya indir
            if not update_success:
                if download_file(base_url, rel_path, dest_path):
                    downloaded_hash = calculate_hash(dest_path)
                    if downloaded_hash == remote_hash:
                        print_status("  OK", "Basariyla indirildi ve dogrulandi", Colors.GREEN)
                        stats["downloaded"] += 1
                        update_success = True

                        if rel_path == "requirements.txt":
                            requirements_changed = True
                    else:
                        print_status("  !!", "Hash uyusmuyor! Yedekten geri yukleniyor...", Colors.RED)
                        backup_src = os.path.join(project_dir, BACKUP_DIR, rel_path)
                        if os.path.exists(backup_src):
                            shutil.copy2(backup_src, dest_path)
                        stats["failed"] += 1
                else:
                    stats["failed"] += 1

    # --- Adim 4: Feature Merge ---
    print(f"\n{Colors.BOLD}[4/5] Ozellik birlestirme kontrol ediliyor...{Colors.RESET}")

    # Uzak feature registry'yi indir
    remote_registry_content = download_text_file(base_url, FEATURE_REGISTRY_FILE)
    remote_registry = None
    if remote_registry_content:
        try:
            remote_registry = json.loads(remote_registry_content)
            print_status("[OK]", "Uzak feature registry indirildi.", Colors.GREEN)
        except json.JSONDecodeError:
            print_status("[!]", "Uzak feature registry okunamadi.", Colors.YELLOW)

    # Yerel feature registry
    local_registry = None
    if os.path.exists(FEATURE_REGISTRY_FILE):
        try:
            with open(FEATURE_REGISTRY_FILE, "r", encoding="utf-8") as f:
                local_registry = json.load(f)
        except (json.JSONDecodeError, IOError):
            pass

    merge_stats = {"merged": 0, "conflicts": 0, "conflict_resolved": 0}

    if remote_registry and remote_registry.get("files"):
        merger = FeatureMerger()

        for rel_path, remote_file_entry in remote_registry.get("files", {}).items():
            dest_path = os.path.join(project_dir, rel_path.replace("/", os.sep))

            if not os.path.exists(dest_path):
                continue

            if not rel_path.endswith(".py"):
                continue

            # Yerel dosyayi oku
            try:
                with open(dest_path, "r", encoding="utf-8") as f:
                    local_content = f.read()
            except (IOError, UnicodeDecodeError):
                continue

            # Uzak dosyayi indir (merge icin)
            remote_content = download_text_file(base_url, rel_path)
            if not remote_content:
                continue

            # Birlestir
            merged_content, conflicts, added_features = merger.merge_features(
                local_content, remote_content, remote_file_entry
            )

            if added_features:
                print_status("[+]", f"{rel_path}: {len(added_features)} yeni ozellik eklendi: {', '.join(added_features)}", Colors.CYAN)
                merge_stats["merged"] += len(added_features)

            # Cakismalari coz
            for conflict in conflicts:
                merge_stats["conflicts"] += 1
                resolution = merger.resolve_conflict_interactive(conflict)
                merged_content = merger.apply_conflict_resolution(merged_content, conflict, resolution)
                merge_stats["conflict_resolved"] += 1
                choice_text = {"local": "Yerel korundu", "remote": "Uzak alindi", "both": "Ikisi de korundu"}
                print_status("  >>", f"{conflict['feature_id']}: {choice_text.get(resolution, resolution)}", Colors.MAGENTA)

            # Degisiklik varsa dosyayi yaz
            if added_features or conflicts:
                backup_file(project_dir, rel_path)
                try:
                    with open(dest_path, "w", encoding="utf-8", newline="\n") as f:
                        f.write(merged_content)
                except IOError as e:
                    print_status("[X]", f"Dosya yazilamadi: {rel_path} - {e}", Colors.RED)

        # Uzak feature registry'yi yerel olarak kaydet
        with open(FEATURE_REGISTRY_FILE, "w", encoding="utf-8") as f:
            json.dump(remote_registry, f, indent=2, ensure_ascii=False)
        print_status("[OK]", "Feature registry guncellendi.", Colors.GREEN)
    else:
        print_status("[*]", "Uzak feature registry bulunamadi veya bos.", Colors.DIM)

    # --- Adim 5: Son islemler ---
    print(f"\n{Colors.BOLD}[5/5] Son islemler...{Colors.RESET}")

    if requirements_changed:
        print_status("[*]", "requirements.txt degisti! Gereksinimler kuruluyor...", Colors.YELLOW)
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "-r", "requirements.txt", "-q"],
                check=True,
                timeout=300,
            )
            print_status("[OK]", "Gereksinimler basariyla kuruldu!", Colors.GREEN)

            # Playwright tarayici binary'lerini kur
            print_status("[*]", "Playwright tarayici kuruluyor...", Colors.YELLOW)
            try:
                subprocess.run(
                    [sys.executable, "-m", "playwright", "install", "chromium"],
                    check=True,
                    timeout=600,
                )
                print_status("[OK]", "Playwright Chromium basariyla kuruldu!", Colors.GREEN)
            except Exception:
                print_status("[!]", "Playwright kurulumu atlanildi (manuel: python -m playwright install chromium)", Colors.YELLOW)

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
    print(f"  {Colors.GREEN}{Colors.BOLD}GUNCELLEME TAMAMLANDI{Colors.RESET}")
    print(f"  Manifest: v{local_version} -> v{remote_version}")
    print(f"  Guncellenen (tam dosya): {Colors.YELLOW}{stats['downloaded']}{Colors.RESET} dosya")
    print(f"  Guncellenen (diff/patch): {Colors.CYAN}{stats['patched']}{Colors.RESET} dosya")
    print(f"  Yeni Eklenen: {Colors.CYAN}{stats['new']}{Colors.RESET} dosya")
    print(f"  Atlanan (guncel): {Colors.DIM}{stats['skipped']}{Colors.RESET} dosya")

    if merge_stats["merged"] > 0:
        print(f"  Birlestirilen Ozellik: {Colors.MAGENTA}{merge_stats['merged']}{Colors.RESET}")
    if merge_stats["conflicts"] > 0:
        print(f"  Cozulen Cakisma: {Colors.YELLOW}{merge_stats['conflict_resolved']}{Colors.RESET}")

    if stats["failed"] > 0:
        print(f"  {Colors.RED}Basarisiz: {stats['failed']} dosya{Colors.RESET}")
        print(f"  {Colors.YELLOW}Yedekler .update_backup/ klasorunde saklanmaktadir.{Colors.RESET}")

    print(f"{Colors.CYAN}{'=' * 60}{Colors.RESET}")
    input("\nCikmak icin Enter'a basin...")
# --- END FEATURE: update ---


if __name__ == "__main__":
    update()
