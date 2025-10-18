#!/usr/bin/env python3
"""
Serveur de fichiers simple (Flask)
- Affiche le contenu des dossiers dans une page HTML
- Téléchargement direct des fichiers
- Téléchargement des dossiers sous forme d'archive .zip (tempfile)
- HTTPS via certificat + clé (ssl_context)
Usage:
  python3 file_server.py --root /chemin/vers/dossier --cert /path/cert.pem --key /path/key.pem --port 443
"""

import argparse
import os
import pathlib
from urllib.parse import unquote

import zipstream
from flask import Flask, send_file, abort, render_template, request, url_for, Response

app = Flask(__name__)

# Template HTML minimal, sérieux et lisible
TEMPLATE = open("templates/files.html", "r").read().encode("utf-8")
default_port = open("server.cfg", "r").read()
root_directory = open("root_directory.cfg", "r").read()
print(root_directory)


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
    except Exception:
        abort(403, "Accès interdit")
    return target


@app.route('/', defaults={'req_path': ''})
@app.route('/<path:req_path>')
def index(req_path):
    # décodage de l'URL
    req_path = unquote(req_path)
    root_path = app.config['ROOT_PATH']
    target = safe_resolve(root_path, req_path)

    if target.is_file():
        # redirige vers l'endpoint de téléchargement de fichier
        return send_file_endpoint(req_path)

    if not target.exists() or not target.is_dir():
        abort(404)

    # lister
    entries = list(target.iterdir())
    dirs = []
    files = []
    for e in sorted(entries, key=lambda p: (not p.is_dir(), p.name.lower())):
        rel = os.path.relpath(str(e), str(root_path))
        if e.is_dir():
            count = len(list(e.iterdir()))
            dirs.append({
                'name': e.name,
                'link': url_for('index', req_path=rel),
                'zip_link': url_for('download_dir_zip', dir_path=rel),
                'count': count
            })
        else:
            size = human_size(e.stat().st_size)
            files.append({
                'name': e.name,
                'link': url_for('index', req_path=rel),
                'dl_link': url_for('download_file', file_path=rel),
                'size': size
            })

    # parent link
    parent_link = None
    if req_path:
        parent = pathlib.Path(req_path).parent.as_posix()
        parent_link = url_for('index', req_path=parent) if parent != '.' else url_for('index')

    return render_template("files.html",
                           rel_path=req_path,
                           root_path=str(root_path),
                           dirs=dirs, files=files,
                           parent_link=parent_link,
                           request_url=request.url)


@app.route('/download/file/<path:file_path>')
def download_file(file_path):
    return send_file_endpoint(file_path)


def send_file_endpoint(file_path):
    # renvoie un fichier en sécurité
    root_path = app.config['ROOT_PATH']
    file_path = unquote(file_path)
    target = safe_resolve(root_path, file_path)
    if not target.exists() or not target.is_file():
        abort(404)
    # send_file gère le streaming et les en-têtes
    return send_file(str(target), as_attachment=True, download_name=target.name)


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
    p = argparse.ArgumentParser(description="Serveur de fichiers HTTP (Flask)")
    p.add_argument('--root', required=False, default=root_directory, help='Dossier racine à partager')
    p.add_argument('--host', default='0.0.0.0', help='Interface d\'écoute (par défaut 0.0.0.0)')
    p.add_argument('--port', type=int, default=default_port, help='Port HTTP (par défaut 8080 si non-root)')
    # p.add_argument('--cert', required=False, default="cert.pem", help='Chemin vers cert.pem')
    # p.add_argument('--key', required=False, default="key.pem", help='Chemin vers key.pem')
    return p.parse_args()


if __name__ == '__main__':
    args = parse_args()
    root = pathlib.Path(args.root).resolve()
    if not root.exists() or not root.is_dir():
        raise SystemExit(f"Le dossier racine '{root}' n'existe pas ou n'est pas un répertoire.")

    app.config['ROOT_PATH'] = root

    # NOTE: pour production, utilisez un serveur WSGI (gunicorn/uvicorn) devant un reverse proxy (nginx/Caddy)
    # context = (args.cert, args.key)  # Flask accepte un tuple (cert,key)
    # Avertissement: la fonction run de Flask n'est pas recommandée en production mais suffit pour un service simple.
    app.run(host=args.host, port=args.port, threaded=True)  # , ssl_context=context)
