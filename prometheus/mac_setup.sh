#!/usr/bin/env bash
set -euo pipefail

VERSION="${1:-2.51.0}"
FORCE="false"
if [[ "${2:-}" == "--force" ]]; then
  FORCE="true"
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DIST_DIR="$SCRIPT_DIR/dist"
TARGET_DIR="$SCRIPT_DIR/mac"
TARBALL="prometheus-${VERSION}.darwin-amd64.tar.gz"
URL="https://github.com/prometheus/prometheus/releases/download/v${VERSION}/${TARBALL}"
DEST_ARCHIVE="$DIST_DIR/$TARBALL"
DEST_FOLDER="$TARGET_DIR/prometheus-${VERSION}.darwin-amd64"

mkdir -p "$DIST_DIR" "$TARGET_DIR"

echo "Prometheus version : ${VERSION}"
echo "Download URL      : ${URL}"

if [[ ! -f "$DEST_ARCHIVE" || "$FORCE" == "true" ]]; then
  echo "Downloading archive to $DEST_ARCHIVE..."
  curl -L "$URL" -o "$DEST_ARCHIVE"
else
  echo "Archive already exists at $DEST_ARCHIVE (use --force to re-download)."
fi

if [[ -d "$DEST_FOLDER" ]]; then
  if [[ "$FORCE" == "true" ]]; then
    echo "Removing existing directory $DEST_FOLDER..."
    rm -rf "$DEST_FOLDER"
  else
    echo "Destination $DEST_FOLDER already exists. Use --force to overwrite."
    exit 0
  fi
fi

echo "Extracting to $TARGET_DIR..."
tar -xzf "$DEST_ARCHIVE" -C "$TARGET_DIR"

echo "Prometheus extracted to $DEST_FOLDER"
echo "Run the following to start Prometheus:"
echo "  $DEST_FOLDER/prometheus --config.file=../prometheus.yml"