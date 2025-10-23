import ruaccent
from ruaccent import RUAccent
import os, sys

accentizer = RUAccent()
# Укажите точный путь в контейнере, где смонтированы preinstalled файлы
workdir = "/hf_cache"  # у вас ./hf_cache:/hf_cache

# возможные расположения koziev в hf_cache:
candidates = [
    os.path.join(workdir, "koziev"),  # /hf_cache/koziev
    os.path.join(workdir, "ruaccent", "koziev"),  # /hf_cache/ruaccent/koziev
]

found = None
for c in candidates:
    if os.path.isdir(c):
        found = c
        break

if not found:
    # хорошая диагностическая ошибка — не начинаем скачивать гигабайты
    raise RuntimeError(
        "Не найден каталог 'koziev' в /hf_cache. Положите туда папку koziev (с файлами "
        "rupostagger и т.д.) или проверьте структуру. Проверяемые пути: "
        f"{candidates}"
    )

# убеждаемся, что это пакет (хотя namespace-пакет может работать, лучше иметь __init__.py)
init_py = os.path.join(found, "__init__.py")
if not os.path.exists(init_py):
    try:
        open(init_py, "a").close()
    except Exception as e:
        # если не получилось — всё равно пробуем, но логируем
        print(f"Не удалось создать __init__.py в {found}: {e}", file=sys.stderr)

# теперь делаем так, чтобы при импортах вида `from .koziev` Python проверял /hf_cache
# (вставляем путь в начало, чтобы он имел приоритет)
# ВАЖНО: мы вставляем корневой каталог, куда импортатор будет добавлять 'koziev'
# если found == /hf_cache/koziev -> добавляем workdir
# если found == /hf_cache/ruaccent/koziev -> добавляем /hf_cache/ruaccent
parent_dir = os.path.dirname(found)
if parent_dir not in ruaccent.__path__:
    ruaccent.__path__.insert(0, parent_dir)
# указываем module_path туда же — чтобы блок загрузки koziev видел локальные файлы
accentizer.module_path = workdir

# put this before you import/instantiate RUAccent and before calling .load()
import traceback


def _local_hf_hub_download(*args, **kwargs):
    """
    Поведение:
    - ожидает аргумент filename и локальную директорию (local_dir)
    - если файл есть в local_dir/filename — возвращает путь (как hf_hub_download)
    - иначе пробует найти basename(filename) в пределах local_dir (ограничение по числу файлов)
    - если не найден — бросает RuntimeError (чтобы библиотека не начинала сетевые загрузки)
    """
    filename = kwargs.get("filename") or (args[1] if len(args) > 1 else None)
    local_dir = kwargs.get("local_dir") or (args[2] if len(args) > 2 else None)

    if filename is None:
        raise RuntimeError(
            "[LOCAL HF BLOCK] hf_hub_download blocked: no filename given"
        )

    # 1) прямой путь
    if local_dir:
        candidate = os.path.join(local_dir, filename)
        if os.path.exists(candidate):
            return candidate

        # 2) прямой путь по basename (например когда filename содержит префикс repo/)
        basename = os.path.basename(filename)
        # ограниченный поиск, чтобы не застрять на больших FS
        max_files_checked = 20000
        checked = 0
        for root, dirs, files in os.walk(local_dir):
            for f in files:
                checked += 1
                if f == basename:
                    return os.path.join(root, f)
                if checked >= max_files_checked:
                    # остановим поиск — слишком много файлов
                    break
            if checked >= max_files_checked:
                break

    # 3) короткая проверка в стандартных местах (если вы монтируете /hf_cache)
    common_places = ["/hf_cache", os.getcwd(), os.path.expanduser("~")]
    for base in common_places:
        if base and os.path.isdir(base):
            candidate = os.path.join(base, filename)
            if os.path.exists(candidate):
                return candidate
            # быстрый basename check (без обхода всей FS)
            candidate2 = os.path.join(base, os.path.basename(filename))
            if os.path.exists(candidate2):
                return candidate2

    tb = "".join(traceback.format_stack(limit=8))
    msg = (
        "[LOCAL HF BLOCK] huggingface_hub download blocked — file not found locally.\n"
        f"Expected filename: {filename}\nlocal_dir: {local_dir}\nStack (truncated):\n{tb}"
    )
    # логируем в stderr (будет видно в docker logs)
    print(msg, file=sys.stderr)
    raise RuntimeError(msg)


def _local_snapshot_download(*args, **kwargs):
    # snapshot_download обычно вызывает с local_dir — если такая директория уже есть, вернуть её.
    local_dir = kwargs.get("local_dir") or (args[1] if len(args) > 1 else None)
    if local_dir and os.path.isdir(local_dir):
        return local_dir
    # иначе блокируем (чтобы не делать сетевой вызов)
    raise RuntimeError(
        f"[LOCAL HF BLOCK] snapshot_download blocked. target local_dir: {local_dir}"
    )


# Применим патч в huggingface_hub (если пакет есть)
try:
    import huggingface_hub as _hf

    # перехват основных точек входа
    _hf.hf_hub_download = _local_hf_hub_download
    _hf.snapshot_download = _local_snapshot_download
except Exception:
    # если huggingface_hub не импортирован — ничего страшного, мы всё равно патчим sys.modules ниже
    pass

# Также попытаться патчить внутренние подмодули (иногда hf_hub_download импортируют туда)
for module in list(sys.modules.values()):
    try:
        if hasattr(module, "hf_hub_download"):
            try:
                setattr(module, "hf_hub_download", _local_hf_hub_download)
            except Exception:
                pass
        if hasattr(module, "snapshot_download"):
            try:
                setattr(module, "snapshot_download", _local_snapshot_download)
            except Exception:
                pass
    except Exception:
        # молча пропускаем модули, на которых нельзя писать атрибуты
        pass
accentizer.load(
    omograph_model_size="turbo3.1",
    use_dictionary=True,
    workdir="/hf_cache",
    tiny_mode=False,
)
