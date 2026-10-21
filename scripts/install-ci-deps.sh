#!/usr/bin/env bash
# All required packages are in Ubuntu. Do not let unrelated runner vendor
# repositories (for example Microsoft packages) break apt update.
set -euo pipefail
test -f /etc/apt/sources.list.d/ubuntu.sources || {
  echo 'Expected Ubuntu 24.04 repository configuration'; exit 1;
}
options=(-o Dir::Etc::sourcelist=/etc/apt/sources.list.d/ubuntu.sources
         -o Dir::Etc::sourceparts=- -o Acquire::Retries=3)
packages=(build-essential gnupg nasm)
case "${1:?Use media or build}" in
  media) packages+=(ffmpeg) ;;
  build) packages+=(cmake ninja-build meson pkg-config libgl1 unzip openjdk-17-jre-headless) ;;
  *) exit 2 ;;
esac
sudo apt-get "${options[@]}" update
sudo apt-get "${options[@]}" install -y "${packages[@]}"
