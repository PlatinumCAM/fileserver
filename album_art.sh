#!/bin/bash

# Dossier cible
TARGET_DIR="$HOME/Music"

# Suppression récursive des fichiers correspondants
find "$TARGET_DIR" -type f -name "AlbumArt*.jpg" -exec rm -f {} \;

echo "Tous les fichiers AlbumArt*.jpg ont été supprimés dans $TARGET_DIR."
