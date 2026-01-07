import os

def count_lines(root):
    exclude_dirs = {"venv", ".venv", ".idea", "__pycache__", ".git", "build", "dist", ".mypy_cache"}
    total = 0

    for dirpath, dirnames, filenames in os.walk(root):
        # Удаляем из обхода папки, которые не надо считать
        dirnames[:] = [d for d in dirnames if d not in exclude_dirs]

        for f in filenames:
            if f.endswith(".py"):
                path = os.path.join(dirpath, f)
                try:
                    with open(path, encoding="utf-8", errors="ignore") as file:
                        lines = sum(1 for _ in file)
                        print(f"{path}: {lines}")
                        total += lines
                except Exception as e:
                    print(f"[!] Ошибка при чтении {path}: {e}")

    print(f"\n🧮 Total Python lines (без служебных директорий): {total}")

count_lines(".")

