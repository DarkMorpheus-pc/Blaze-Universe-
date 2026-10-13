#!/usr/bin/env bash
# Fetch and verify the pinned stable Limine binary release used by BlazeOS.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BLAZE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
VERSION="12.9.1"
ARCHIVE="limine-binary.tar.xz"
EXPECTED_SHA256="ce972a05e9d1973dc9b725f9130bd15af01add0eb3a7f90c118ac5cfe21c17b8"
CACHE_DIR="${BLAZE_ROOT}/build/sources"
ARCHIVE_PATH="${CACHE_DIR}/limine-${VERSION}-binary.tar.xz"
DEST_DIR="${BLAZE_ROOT}/build/limine-${VERSION}"
URL="https://github.com/Limine-Bootloader/Limine/releases/download/v${VERSION}/${ARCHIVE}"

mkdir -p "${CACHE_DIR}"
if [[ ! -f "${ARCHIVE_PATH}" ]]; then
    echo "[LIMINE] Downloading verified stable release v${VERSION}..."
    curl --fail --location --proto '=https' --tlsv1.2 \
        --output "${ARCHIVE_PATH}" "${URL}"
fi

printf '%s  %s\n' "${EXPECTED_SHA256}" "${ARCHIVE_PATH}" | sha256sum --check --status || {
    echo "[ERROR] Limine v${VERSION} checksum verification failed." >&2
    exit 1
}

if [[ ! -d "${DEST_DIR}" ]]; then
    TEMP_DIR="$(mktemp -d "${BLAZE_ROOT}/build/.limine-${VERSION}.XXXXXX")"
    trap 'rm -rf "${TEMP_DIR}"' EXIT
    tar -xJf "${ARCHIVE_PATH}" -C "${TEMP_DIR}"
    EXTRACTED="$(find "${TEMP_DIR}" -mindepth 1 -maxdepth 1 -type d | head -n1)"
    [[ -n "${EXTRACTED}" ]] || {
        echo "[ERROR] Limine archive layout is invalid." >&2
        exit 1
    }
    mv "${EXTRACTED}" "${DEST_DIR}"
fi

if [[ ! -x "${DEST_DIR}/limine" ]]; then
    make -C "${DEST_DIR}"
fi

"${DEST_DIR}/limine" --version
printf '%s\n' "${DEST_DIR}"
