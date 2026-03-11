"""
ADD_MARKERS.PY - Feature Marker Ekleme Scripti
================================================
Projedeki tum .py dosyalarina feature marker ve AI talimat notu ekler.
Dosyalari analiz eder, fonksiyon ve sinif bloklarini tespit edip uygun marker atar.

Kullanim:
    python tests/add_markers.py

TEK KULLANIMLIK SCRIPT - markerlar eklendikten sonra silinebilir.
"""

import os
import sys
import re
import ast

# AI talimat notu
AI_NOTE = '''
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
'''

# Her dosya icin hangi ozelliklerin ekleneceği
# Format: {dosya_yolu: [(feature_id, feature_name, baslangic_pattern, bitis_tipi)]}
# bitis_tipi: "class_end", "function_end", "block_end", "manual_line_range"

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Halihazirda marker olan dosyalari atla
FEATURE_MARKER_PATTERN = re.compile(r"#\s*---\s*FEATURE:")
AI_NOTE_PATTERN = "GELISTIRICI NOTU (AI & Insan)"


def has_markers(content):
    """Dosyanin zaten marker icerip icermedigini kontrol eder."""
    return bool(FEATURE_MARKER_PATTERN.search(content))


def has_ai_note(content):
    """Dosyanin zaten AI notu icerip icermedigini kontrol eder."""
    return AI_NOTE_PATTERN in content


def analyze_file_with_ast(filepath):
    """AST kullanarak dosyadaki fonksiyon ve sinif bloklarini analiz eder."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        tree = ast.parse(content)
    except (SyntaxError, UnicodeDecodeError):
        return []

    blocks = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            # Sadece top-level veya class-level tanimlamalari al
            blocks.append({
                "name": node.name,
                "type": type(node).__name__,
                "start_line": node.lineno,
                "end_line": node.end_lineno,
            })

    return blocks


def generate_feature_id(name, context=""):
    """Fonksiyon/sinif adindan feature ID uretir."""
    # CamelCase'i snake_case'e cevir
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    feature_id = re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()
    # Ozel karakterleri temizle
    feature_id = re.sub(r'[^a-z0-9_]', '', feature_id)
    # __ ile baslayanlar icin underscore temizle
    feature_id = feature_id.strip('_')
    return feature_id


def add_markers_to_file(filepath, rel_path):
    """Dosyaya feature marker ve AI notu ekler."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
            lines = content.split("\n")
    except (IOError, UnicodeDecodeError) as e:
        print(f"  [X] Okunamadi: {rel_path} - {e}")
        return False

    if has_markers(content):
        print(f"  [=] Zaten marker var: {rel_path}")
        if not has_ai_note(content):
            # Sadece AI notu ekle
            content = content.rstrip() + "\n" + AI_NOTE
            with open(filepath, "w", encoding="utf-8", newline="\n") as f:
                f.write(content)
            print(f"      + AI notu eklendi")
        return True

    # AST ile analiz et
    blocks = analyze_file_with_ast(filepath)

    if not blocks:
        # Marker eklenecek blok yok, sadece AI notu ekle
        if not has_ai_note(content):
            content = content.rstrip() + "\n" + AI_NOTE
            with open(filepath, "w", encoding="utf-8", newline="\n") as f:
                f.write(content)
            print(f"  [+] AI notu eklendi (blok yok): {rel_path}")
        return True

    # Top-level bloklari bul (indent seviyesi 0 olan fonksiyonlar ve siniflar)
    top_level_blocks = []
    for block in blocks:
        start_line = block["start_line"]
        if start_line <= len(lines):
            line_content = lines[start_line - 1]
            indent = len(line_content) - len(line_content.lstrip())
            if indent == 0:
                top_level_blocks.append(block)

    if not top_level_blocks:
        # Sadece AI notu ekle
        if not has_ai_note(content):
            content = content.rstrip() + "\n" + AI_NOTE
            with open(filepath, "w", encoding="utf-8", newline="\n") as f:
                f.write(content)
            print(f"  [+] AI notu eklendi (top-level yok): {rel_path}")
        return True

    # Birbirine yakin bloklari grupla (eger araları 3 satirdan azsa)
    groups = []
    current_group = [top_level_blocks[0]]

    for i in range(1, len(top_level_blocks)):
        prev_end = current_group[-1]["end_line"]
        curr_start = top_level_blocks[i]["start_line"]

        if curr_start - prev_end <= 3:
            current_group.append(top_level_blocks[i])
        else:
            groups.append(current_group)
            current_group = [top_level_blocks[i]]

    groups.append(current_group)

    # Her gruba marker ekle
    # Sondan basa dogru ekle ki satir numaralari bozulmasin
    new_lines = list(lines)
    markers_added = 0

    for group in reversed(groups):
        group_start = group[0]["start_line"] - 1  # 0-indexed
        group_end = group[-1]["end_line"]  # 1-indexed, son satir dahil

        # Feature ID olustur
        if len(group) == 1:
            feature_id = generate_feature_id(group[0]["name"])
        else:
            # Grup icin en anlamli isim
            names = [b["name"] for b in group]
            if any(isinstance_name := True for b in group if b["type"] == "ClassDef"):
                # Sinif varsa sinif adini kullan
                class_blocks = [b for b in group if b["type"] == "ClassDef"]
                feature_id = generate_feature_id(class_blocks[0]["name"])
            else:
                feature_id = generate_feature_id(names[0])

        # End marker ekle
        end_marker = f"# --- END FEATURE: {feature_id} ---"
        if group_end < len(new_lines):
            new_lines.insert(group_end, end_marker)
        else:
            new_lines.append(end_marker)

        # Start marker ekle
        start_marker = f"# --- FEATURE: {feature_id} ---"
        new_lines.insert(group_start, start_marker)

        markers_added += 1

    # AI notu ekle
    result = "\n".join(new_lines)
    if not has_ai_note(result):
        result = result.rstrip() + "\n" + AI_NOTE

    with open(filepath, "w", encoding="utf-8", newline="\n") as f:
        f.write(result)

    print(f"  [+] {markers_added} marker eklendi: {rel_path}")
    return True


def main():
    """Tum proje dosyalarina marker ekle."""
    print("=" * 60)
    print("  FEATURE MARKER EKLEME ARACI")
    print("=" * 60)

    exclude_dirs = {".venv", "__pycache__", "old", ".git", "tests", "data"}
    exclude_files = {"publish.py", "updater.py"}  # Bunlara zaten ekleyeceğiz ayrı

    py_files = []
    for root, dirs, filenames in os.walk(PROJECT_DIR):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]

        for filename in filenames:
            if not filename.endswith(".py"):
                continue
            
            full_path = os.path.join(root, filename)
            rel_path = os.path.relpath(full_path, PROJECT_DIR).replace("\\", "/")
            py_files.append((full_path, rel_path))

    print(f"\n[*] {len(py_files)} Python dosyasi bulundu.\n")

    success_count = 0
    for full_path, rel_path in sorted(py_files):
        if add_markers_to_file(full_path, rel_path):
            success_count += 1

    print(f"\n{'=' * 60}")
    print(f"  Toplam: {len(py_files)} dosya")
    print(f"  Basarili: {success_count}")
    print(f"  Basarisiz: {len(py_files) - success_count}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
