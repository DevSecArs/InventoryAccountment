#!/bin/sh
# Подготавливает Docker Engine и Compose для изолированных проверок на Ubuntu.
set -eu

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    exit 0
fi

if [ ! -r /etc/os-release ]; then
    echo "Docker не установлен. Автоматическая установка поддерживается только на Ubuntu." >&2
    exit 2
fi

. /etc/os-release
if [ "${ID:-}" != "ubuntu" ]; then
    echo "Docker не установлен. Автоматическая установка поддерживается только на Ubuntu." >&2
    exit 2
fi

if ! command -v sudo >/dev/null 2>&1; then
    echo "Для установки Docker нужен sudo. Установите Docker Engine и Docker Compose вручную." >&2
    exit 2
fi

sudo -v
sudo apt-get update
sudo apt-get install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

codename="${UBUNTU_CODENAME:-${VERSION_CODENAME:-}}"
architecture="$(dpkg --print-architecture)"
if [ -z "$codename" ] || [ -z "$architecture" ]; then
    echo "Не удалось определить версию Ubuntu или архитектуру для Docker." >&2
    exit 2
fi

sudo tee /etc/apt/sources.list.d/docker.sources >/dev/null <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $codename
Components: stable
Architectures: $architecture
Signed-By: /etc/apt/keyrings/docker.asc
EOF

sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
current_user="${SUDO_USER:-${USER:-$(id -un)}}"
sudo usermod -aG docker "$current_user"

echo "Docker установлен. Выйдите из SSH-сеанса и подключитесь снова, затем повторите make setup." >&2
exit 3
