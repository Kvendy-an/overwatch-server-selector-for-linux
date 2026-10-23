#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.."
version=$(python3 -c 'from owselector import __version__; print(__version__)')
architecture=$(uname -m)
[[ $architecture == x86_64 ]] || { echo 'This release recipe currently supports x86_64.' >&2; exit 1; }
mkdir -p build/tools dist
tool=build/tools/appimagetool-x86_64.AppImage
runtime=build/tools/runtime-x86_64
if [[ ! -f $tool ]]; then
    curl -fL --retry 3 https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage -o "$tool"
fi
if [[ ! -f $runtime ]]; then
    curl -fL --retry 3 https://github.com/AppImage/type2-runtime/releases/download/continuous/runtime-x86_64 -o "$runtime"
fi
sha256sum -c packaging/appimage/tools.sha256
chmod +x "$tool"
container_engine=${CONTAINER_ENGINE:-podman}
if [[ $container_engine == podman ]]; then
    container_options=(--root "${APPIMAGE_CONTAINER_STORAGE:-/tmp/ow-selector-containers/storage}" --runroot "${APPIMAGE_CONTAINER_RUNROOT:-/tmp/ow-selector-containers/run}" --storage-driver vfs)
    run_options=(--userns=keep-id --security-opt label=disable)
else
    container_options=()
    run_options=(--user "$(id -u):$(id -g)")
fi
"$container_engine" "${container_options[@]}" build -f packaging/appimage/Containerfile -t ow-selector-appimage-builder .
"$container_engine" "${container_options[@]}" run --rm "${run_options[@]}" -v "$PWD:/src:rw" ow-selector-appimage-builder
APPIMAGE_EXTRACT_AND_RUN=1 ARCH=x86_64 "$tool" --no-appstream --runtime-file "$runtime" build/OverwatchServerSelector.AppDir "dist/Overwatch-Server-Selector-${version}-x86_64.AppImage"
(cd dist && sha256sum "Overwatch-Server-Selector-${version}-x86_64.AppImage" > "Overwatch-Server-Selector-${version}-x86_64.AppImage.sha256")
python3 packaging/appimage/source_archive.py
echo "Release ready: dist/Overwatch-Server-Selector-${version}-x86_64.AppImage"
