#!/usr/bin/env bash
# Build the GnuCOBOL 3.2 reference compiler on Debian/Ubuntu (root required).
# The tarball is checked against its pinned SHA256 and the GNU keyring signature.
set -euo pipefail

VERSION=3.2
SHA256=3bb48af46ced4779facf41fdc2ee60e4ccb86eaa99d010b36685315df39c2ee2
PREFIX=${PREFIX:-/usr/local}
WORK=${WORK:-/opt/src}
BASE=https://ftp.gnu.org/gnu/gnucobol

if command -v cobc >/dev/null && cobc -V | head -1 | grep -q "GnuCOBOL) ${VERSION}.0"; then
    echo "GnuCOBOL ${VERSION}.0 déjà installé : $(command -v cobc)"
    exit 0
fi

apt-get update
apt-get install -y build-essential gpg libgmp-dev libdb-dev libncurses-dev \
    libxml2-dev libjson-c-dev

mkdir -p "$WORK"
cd "$WORK"
for file in "gnucobol-${VERSION}.tar.xz" "gnucobol-${VERSION}.tar.xz.sig"; do
    [ -f "$file" ] || curl -sSfLO "${BASE}/${file}"
done
[ -f gnu-keyring.gpg ] || curl -sSfLO https://ftp.gnu.org/gnu/gnu-keyring.gpg
echo "${SHA256}  gnucobol-${VERSION}.tar.xz" | sha256sum -c -
gpg --no-default-keyring --keyring ./gnu-keyring.gpg \
    --verify "gnucobol-${VERSION}.tar.xz.sig" "gnucobol-${VERSION}.tar.xz"

rm -rf "gnucobol-${VERSION}"
tar xf "gnucobol-${VERSION}.tar.xz"
cd "gnucobol-${VERSION}"
# BDB fournit le gestionnaire INDEXED utilisé par le profil de référence.
./configure --prefix="$PREFIX" --with-db --with-json=json-c --with-xml2
make -j"$(nproc)"
make install
ldconfig
cobc -V | head -1
cobc --info | grep -E "indexed file handler"
