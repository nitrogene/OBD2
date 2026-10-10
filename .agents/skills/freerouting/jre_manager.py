#!/usr/bin/env python3
"""
Gestionnaire d'environnement d'exécution portable (JRE + FreeRouting)
=====================================================================
Skill: freerouting
Règle 0: Ce script est un gestionnaire d'environnement purement agnostique.
Il ne contient aucun composant ni règle spécifique au projet.
"""

import os
import sys
import shutil
import zipfile
import urllib.request
import subprocess
from pathlib import Path
from typing import Optional, Tuple

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

DEFAULT_CACHE_DIR = Path(__file__).resolve().parent / ".cache" / "runtime"

# Adoptium Eclipse Temurin OpenJDK 25 Windows x64 JRE (requis pour FreeRouting >= 2.4.0, bytecode 69.0)
ADOPTIUM_JRE_URL = (
    "https://api.adoptium.net/v3/binary/latest/25/ga/windows/x64/jre/hotspot/normal/eclipse"
)

# FreeRouting v2.4.1 standalone JAR
FREEROUTING_VERSION = "2.4.1"
FREEROUTING_JAR_URL = (
    f"https://github.com/freerouting/freerouting/releases/download/v{FREEROUTING_VERSION}/"
    f"freerouting-{FREEROUTING_VERSION}.jar"
)

HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)"
}


def _download_file(url: str, dest_path: Path, description: str = "Téléchargement") -> None:
    """Télécharge un fichier avec suivi de progression."""
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = dest_path.with_suffix(dest_path.suffix + ".tmp")
    
    print(f"[freerouting] {description}...")
    print(f"             Source : {url}")
    print(f"             Cible  : {dest_path}")
    
    req = urllib.request.Request(url, headers=HTTP_HEADERS)
    with urllib.request.urlopen(req) as resp, open(temp_path, "wb") as out_file:
        total_size = resp.headers.get("Content-Length")
        total_bytes = int(total_size) if total_size else None
        downloaded = 0
        chunk_size = 1024 * 64
        
        while True:
            chunk = resp.read(chunk_size)
            if not chunk:
                break
            out_file.write(chunk)
            downloaded += len(chunk)
            if total_bytes:
                pct = (downloaded / total_bytes) * 100
                mb_done = downloaded / (1024 * 1024)
                mb_total = total_bytes / (1024 * 1024)
                sys.stdout.write(f"\r             Progression : {pct:5.1f}% ({mb_done:.1f}/{mb_total:.1f} Mo)")
                sys.stdout.flush()
        if total_bytes:
            sys.stdout.write("\n")
            sys.stdout.flush()

    if temp_path.exists():
        if dest_path.exists():
            dest_path.unlink()
        temp_path.rename(dest_path)
    print(f"[freerouting] {description} terminé avec succès.")


def _find_system_java() -> Optional[Path]:
    """Vérifie si un binaire java système est présent et compatible (>= Java 25)."""
    java_bin = shutil.which("java")
    if not java_bin:
        return None
    try:
        proc = subprocess.run(
            [java_bin, "-version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5,
        )
        output = proc.stderr or proc.stdout
        # Recherche du numéro de version majeur
        for line in output.splitlines():
            if "version" in line.lower():
                # Exemple: openjdk version "25-beta" ou "25.0.0"
                tokens = line.split('"')
                if len(tokens) >= 2:
                    ver_str = tokens[1]
                    major = int(ver_str.split(".")[0].split("-")[0])
                    if major >= 25:
                        return Path(java_bin)
    except Exception:
        pass
    return None


def _find_cached_java(runtime_dir: Path) -> Optional[Path]:
    """Recherche java.exe dans le sous-dossier jre extrait."""
    jre_dir = runtime_dir / "jre25"
    if not jre_dir.exists():
        return None
    for candidate in jre_dir.rglob("java.exe"):
        if candidate.is_file():
            return candidate
    return None


def ensure_java(runtime_dir: Path, force_portable: bool = False) -> Path:
    """Garantit la disponibilité d'une JRE 25+ fonctionnelle."""
    if not force_portable:
        sys_java = _find_system_java()
        if sys_java:
            print(f"[freerouting] JRE système détectée : {sys_java}")
            return sys_java

    cached_java = _find_cached_java(runtime_dir)
    if cached_java:
        return cached_java

    print("[freerouting] Aucune JRE 25+ adéquate trouvée. Téléchargement d'Eclipse Temurin JRE 25 portable...")
    zip_target = runtime_dir / "jre25.zip"
    _download_file(ADOPTIUM_JRE_URL, zip_target, "Téléchargement JRE 25 OpenJDK Temurin")

    print(f"[freerouting] Extraction de {zip_target.name}...")
    jre_extract_dir = runtime_dir / "jre25"
    jre_extract_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_target, "r") as zf:
        zf.extractall(jre_extract_dir)

    try:
        zip_target.unlink()
    except OSError:
        pass

    cached_java = _find_cached_java(runtime_dir)
    if not cached_java:
        raise RuntimeError(f"Échec de localisation de java.exe après extraction dans {jre_extract_dir}")

    print(f"[freerouting] JRE portable installée : {cached_java}")
    return cached_java


def ensure_freerouting_jar(runtime_dir: Path) -> Path:
    """Garantit la disponibilité du binaire FreeRouting JAR."""
    jar_target = runtime_dir / f"freerouting-{FREEROUTING_VERSION}.jar"
    if jar_target.exists() and jar_target.stat().st_size > 10 * 1024 * 1024:
        return jar_target

    _download_file(
        FREEROUTING_JAR_URL,
        jar_target,
        f"Téléchargement du moteur FreeRouting v{FREEROUTING_VERSION}",
    )
    return jar_target


def ensure_environment(
    cache_dir: Optional[Path] = None, force_portable: bool = False
) -> Tuple[Path, Path]:
    """Garantit l'environnement portable complet JRE + FreeRouting.
    
    Retourne:
        (java_executable, freerouting_jar)
    """
    runtime_dir = cache_dir or DEFAULT_CACHE_DIR
    runtime_dir.mkdir(parents=True, exist_ok=True)

    java_bin = ensure_java(runtime_dir, force_portable=force_portable)
    jar_bin = ensure_freerouting_jar(runtime_dir)

    return java_bin, jar_bin


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Gestionnaire d'environnement FreeRouting")
    parser.add_argument("--check", action="store_true", help="Vérifie et installe l'environnement si nécessaire")
    parser.add_argument("--force-portable", action="store_true", help="Force le téléchargement de la JRE locale")
    args = parser.parse_args()

    java_exe, jar_path = ensure_environment(force_portable=args.force_portable)
    print("\n--- Environnement FreeRouting Validé ---")
    print(f"Java Binary : {java_exe}")
    print(f"Routing JAR : {jar_path}")

    # Test d'exécution rapide CLI
    cmd = [str(java_exe), "-jar", str(jar_path), "--help"]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    first_lines = (res.stdout or res.stderr).splitlines()[:5]
    print("Test d'exécution CLI :")
    for l in first_lines:
        print(f"  {l}")
