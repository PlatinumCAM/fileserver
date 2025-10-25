#!/usr/bin/env python3
"""
Serveur de fichiers HTTP avec lecteur MP3 et affichage de la pochette
"""
import argparse
import json
import os
import pathlib
import random
from io import BytesIO
from pathlib import Path
from urllib.parse import unquote

import zipstream
from PIL import Image
from flask import Flask, render_template, request, url_for, Response
from flask import send_file, abort
from mutagen import File as AudioFile, MutagenError
from mutagen.id3 import ID3, APIC

app = Flask(__name__)

# Template HTML
with open("templates/index.html", "r", encoding="utf-8") as f:
    TEMPLATE = f.read()
default_port = open("server.cfg", "r").read()
BASE_DIR = open("root_directory.cfg", "r").read().strip()
print(BASE_DIR)
rick_path = os.path.join(BASE_DIR, "musique", "Disco", "Rick Astley - Never Gonna Give You Up.mp3")
print(rick_path)

with open('background.json', 'r') as file:
    backgrounds = json.load(file)


def human_size(n):
    # simple human-readable
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if n < 1024.0 or unit == 'TB':
            return f"{n:.1f}{unit}"
        n /= 1024.0


def safe_resolve(root: pathlib.Path, rel: str) -> pathlib.Path:
    # empêche sortie du root (path traversal)
    target = (root / rel).resolve()
    try:
        target.relative_to(root.resolve())
    except ValueError:
        # Raised if target is not inside root
        abort(403, "Accès interdit")
    return target


def scan_dir(rel_path=""):
    """Liste les fichiers et dossiers"""
    full_path = os.path.join(BASE_DIR, rel_path)
    dirs, files = [], []
    for entry in os.scandir(full_path):
        if entry.is_dir():
            count = len(os.listdir(entry.path))
            dirs.append({
                "name": entry.name,
                "link": f"/?path={os.path.join(rel_path, entry.name)}",
                "zip_link": f"/download/zip/{os.path.join(rel_path, entry.name)}",
                "count": count
            })
        elif entry.is_file():
            name_no_ext, ext = os.path.splitext(entry.name)
            is_mp3 = ext.lower() in [".mp3", ".flac"]
            album = get_album(entry.path) if is_mp3 else ""
            files.append({
                "name": name_no_ext,  # sans extension
                "link": f"/download/file/{os.path.join(rel_path, entry.name)}",
                "dl_link": f"/download/file/{os.path.join(rel_path, entry.name)}",
                "stream_link": f"/stream/file/{os.path.join(rel_path, entry.name)}",
                "cover_link": f"/cover/{entry.name}.jpg",
                "is_mp3": is_mp3,
                "album": album
            })
    parent_link = f"/?path={os.path.dirname(rel_path)}" if rel_path else None
    return dirs, files, parent_link


def get_album(file_path):
    try:
        audio = AudioFile(file_path)
        if audio is None:
            return ""
        if "TALB" in audio.tags:  # ID3v2
            return str(audio.tags["TALB"])
        elif "album" in audio.tags:
            return str(audio.tags["album"])
    except (MutagenError, KeyError, AttributeError):
        # Only catch expected Mutagen-related errors
        return ""
    return ""


def background(path):
    """
    Retourne le chemin de l'image de fond à utiliser pour un dossier donné.
    """
    print(path)
    candidate = None
    longest_key = ""
    for key in backgrounds:
        if key in path:
            if len(key) > len(longest_key):
                longest_key = key
                candidate = (Path("bg") / backgrounds[key]).as_posix()
                print(candidate)
    return candidate


@app.route('/background')
def background_image():
    """Servez bg.jpg depuis le même dossier que le script Flask."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    bg_path = os.path.join(script_dir, "bg.jpg")
    if os.path.exists(bg_path):
        return send_file(bg_path, mimetype="image/jpeg")
    abort(404)


@app.route('/', defaults={'req_path': ''})
@app.route('/<path:req_path>')
def index(req_path):
    # décodage de l'URL
    req_path = unquote(req_path)
    # 🔧 Normalisation universelle du chemin
    req_path = pathlib.Path(req_path).as_posix()
    root_path = app.config['ROOT_PATH']
    target = safe_resolve(root_path, req_path)

    if target.is_file():
        # redirige vers l'endpoint de téléchargement de fichier
        return send_file_endpoint(req_path)

    if not target.exists() or not target.is_dir():
        abort(404)

    # lister
    entries = list(target.iterdir())
    dirs, files = [], []
    for entry in sorted(entries, key=lambda p: (not p.is_dir(), p.name.lower())):
        rel = os.path.relpath(str(entry), str(root_path))
        rel = pathlib.Path(rel).as_posix()  # 🔧 uniformisation ici aussi
        if entry.is_dir():
            count = len(list(entry.iterdir()))
            dirs.append({
                'name': entry.name,
                'link': url_for('index', req_path=rel),
                'zip_link': url_for('download_dir_zip', dir_path=rel),
                'count': count
            })
        else:
            size = human_size(entry.stat().st_size)
            files.append({
                'name': entry.name,
                'link': url_for('index', req_path=rel),
                'dl_link': url_for('download_file', file_path=rel),
                'stream_link': url_for('stream_file', file_path=rel),
                'cover_link': url_for('cover_image', file_path=rel),
                'size': size,
                'is_mp3': entry.suffix.lower() == '.mp3',
                'album': get_album(entry)
            })

    parent_link = None
    if req_path:
        parent = pathlib.Path(req_path).parent.as_posix()
        parent_link = url_for('index', req_path=parent) if parent != '.' else url_for('index')
    bg_url = url_for('static', filename=f"{background(req_path)}")

    # bg_url = background(req_path)
    print("url", bg_url)
    return render_template("index.html",
                           rel_path=req_path,
                           root_path=str(root_path),
                           dirs=dirs, files=files,
                           parent_link=parent_link,
                           request_url=request.url,
                           bg_url=bg_url)


@app.route('/download/file/<path:file_path>')
def download_file(file_path):
    file_path = unquote(file_path)
    target = safe_resolve(app.config['ROOT_PATH'], file_path)
    if not target.exists() or not target.is_file():
        abort(404)

    # 10% chance Rick Roll
    if random.random() < 0.1:
        return send_file(rick_path, as_attachment=True, download_name=target.name)

    return send_file(str(target), as_attachment=True, download_name=target.name)


def send_file_endpoint(file_path):
    # renvoie un fichier en sécurité
    root_path = app.config['ROOT_PATH']
    file_path = unquote(file_path)
    target = safe_resolve(root_path, file_path)
    if not target.exists() or not target.is_file():
        abort(404)
    # send_file gère le streaming et les en-têtes
    return send_file(str(target), as_attachment=True, download_name=target.name)


@app.route('/stream/<path:file_path>')
def stream_file(file_path):
    file_path = unquote(file_path)
    target = safe_resolve(app.config['ROOT_PATH'], file_path)
    if not target.exists() or not target.is_file():
        abort(404)

    ext = target.suffix.lower()
    if ext == ".mp3":
        mime = "audio/mpeg"
    elif ext == ".flac":
        mime = "audio/flac"
    else:
        mime = "application/octet-stream"  # fallback

    return send_file(str(target), mimetype=mime, as_attachment=False)


@app.route('/cover/<path:file_path>')
def cover_image(file_path):
    """Extrait la pochette intégrée d’un fichier MP3 (si disponible)."""
    root_path = app.config['ROOT_PATH']
    target = safe_resolve(root_path, file_path)
    if not target.exists() or not target.is_file():
        abort(404)

    audio = AudioFile(target)
    if audio is not None and isinstance(audio.tags, ID3):
        for tag in audio.tags.values():
            if isinstance(tag, APIC):
                image = Image.open(BytesIO(tag.data))
                img_io = BytesIO()
                image.save(img_io, format="JPEG")
                img_io.seek(0)
                return send_file(img_io, mimetype="image/jpeg")

    # Pas de pochette : image grise par défaut
    size = (200, 200)  # taille du carré
    image = Image.new('RGB', size, color=(128, 128, 128))  # gris
    img_io = BytesIO()
    image.save(img_io, format="JPEG")
    img_io.seek(0)
    return send_file(img_io, mimetype="image/jpeg")


@app.route('/download/zip/<path:dir_path>')
def download_dir_zip(dir_path):
    root_path = app.config['ROOT_PATH']
    dir_path = unquote(dir_path)
    target = safe_resolve(root_path, dir_path)
    if not target.exists() or not target.is_dir():
        abort(404)

    # Nom du zip côté client
    download_name = f"{target.name}.zip"

    # Création du flux zipstream
    z = zipstream.ZipFile(mode='w', compression=zipstream.ZIP_DEFLATED)

    # Parcours récursif du dossier
    for root, dirs, files in os.walk(target):
        for file in files:
            abs_path = os.path.join(root, file)
            rel_path = os.path.relpath(abs_path, start=target.parent)
            # Ajout du fichier dans le flux
            z.write(abs_path, arcname=rel_path)

    # Retourne une réponse en streaming
    response = Response(z, mimetype='application/zip')
    response.headers['Content-Disposition'] = f'attachment; filename={download_name}'
    return response


def parse_args():
    p = argparse.ArgumentParser(description="Serveur de fichiers HTTP avec lecteur MP3")
    p.add_argument('--root', required=False, default=BASE_DIR, help='Dossier racine à partager')
    p.add_argument('--host', default='0.0.0.0', help='Interface d\'écoute (par défaut 0.0.0.0)')
    p.add_argument('--port', type=int, default=default_port, help='Port HTTP (par défaut 8080 si non-root)')
    p.add_argument('--cert', required=False, default="cert.pem", help='Chemin vers cert.pem')
    p.add_argument('--key', required=False, default="key.pem", help='Chemin vers key.pem')
    return p.parse_args()


if __name__ == '__main__':
    args = parse_args()
    root = pathlib.Path(args.root).resolve()
    if not root.exists() or not root.is_dir():
        raise SystemExit(f"Le dossier racine '{root}' n'existe pas ou n'est pas un répertoire.")
    app.config['ROOT_PATH'] = root

    # NOTE: pour production, utilisez un serveur WSGI (gunicorn/uvicorn) devant un reverse proxy (nginx/Caddy)
    context = (args.cert, args.key)  # Flask accepte un tuple (cert,key)
    # Avertissement: la fonction run de Flask n'est pas recommandée en production mais suffit pour un service simple.
    app.run(host=args.host, port=args.port, threaded=True, ssl_context=context)
