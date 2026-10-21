#!/usr/bin/env bash
set -euo pipefail
if [[ "$(id -u)" != "0" ]]; then
  echo "Run once with sudo from the cloned ecosmart repository" >&2
  exit 1
fi
apt-get update
apt-get install -y ansible-core git util-linux
install -o root -g root -m 0755 scripts/ecosmart-deploy /usr/local/sbin/ecosmart-deploy
# Only permits this fixed entry point, which validates its inputs and fetches main itself.
cat >/etc/sudoers.d/ecosmart-deploy <<'EOF'
ghrunner ALL=(root) NOPASSWD: /usr/local/sbin/ecosmart-deploy *
EOF
chmod 0440 /etc/sudoers.d/ecosmart-deploy
visudo -cf /etc/sudoers.d/ecosmart-deploy
echo "EcoSmart deploy gateway ready"
