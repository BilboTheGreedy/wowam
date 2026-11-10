#!/bin/sh
set -e

repo="BilboTheGreedy/wowam"
dest="${XDG_DATA_HOME:-$HOME/.local/share}/wowam-app"
bin="$HOME/.local/bin"
url="https://github.com/$repo/releases/latest/download/wowam-linux-x86_64.tar.gz"

if [ "$(uname -s)" != Linux ] || [ "$(uname -m)" != x86_64 ]; then
    echo "this installer is for 64-bit Linux"
    exit 1
fi

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

echo "downloading wowam"
curl -fL --progress-bar "$url" -o "$tmp/wowam.tar.gz"
tar -xzf "$tmp/wowam.tar.gz" -C "$tmp"

mkdir -p "$(dirname "$dest")" "$bin"
rm -rf "$dest"
mv "$tmp/wowam" "$dest"
ln -sf "$dest/wowam" "$bin/wowam"
"$dest/wowam" desktop install

echo "done, start wowam from your app menu"
