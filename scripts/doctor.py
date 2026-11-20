"""Check that everything needed is installed.

    python scripts/doctor.py
"""
from __future__ import annotations

import importlib
import platform
import shutil
import subprocess
import sys

HINTS = {
    "Windows": "winget install Gyan.FFmpeg",
    "Darwin": "brew install ffmpeg",
    "Linux": "sudo apt install ffmpeg",
}


def main() -> None:
    ok = True
    v = sys.version_info
    print(f"{'OK ' if v >= (3, 10) else 'KO '} Python {v.major}.{v.minor}" + ("" if v >= (3, 10) else "  (3.10+ requis)"))
    ok &= v >= (3, 10)

    for b in ("ffmpeg", "ffprobe"):
        path = shutil.which(b)
        print(f"{'OK ' if path else 'KO '} {b}" + ("" if path else f"  -> {HINTS.get(platform.system(), 'installe ffmpeg')}"))
        ok &= bool(path)
    if shutil.which("ffmpeg"):
        filters = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True).stdout
        for f in ("ass", "loudnorm", "ebur128"):
            has = f" {f} " in filters
            print(f"{'OK ' if has else 'KO '} filtre ffmpeg '{f}'" + ("" if has else "  -> prends une version 'full' de ffmpeg"))
            ok &= has

    for mod, pip_name, required in (("numpy", "numpy", True), ("faster_whisper", "faster-whisper", False),
                                    ("yt_dlp", "yt-dlp", False)):
        try:
            importlib.import_module(mod)
            print(f"OK  {pip_name}")
        except ImportError:
            print(f"{'KO ' if required else '-- '} {pip_name}  -> pip install -r requirements.txt")
            ok &= not required

    try:
        import ctranslate2
        gpu = ctranslate2.get_cuda_device_count() > 0
        print(f"--  GPU pour la transcription: {'oui (rapide)' if gpu else 'non (CPU, plus lent)'}")
    except Exception:
        pass
    print("\nTout est prêt." if ok else "\nIl manque des choses (KO) ci-dessus.")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
