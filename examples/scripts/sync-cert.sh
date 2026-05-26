#!/bin/sh
set -eu

DOMAIN=example.com
PROXY_NAME=ru-moscow
PROXY_IP=194.67.92.242
KEY=/root/.ssh/proxy_${PROXY_NAME}_ed25519

CERT_DIR=/var/www/httpd-cert/app
CERT=example.com_le1.crtca
PRIVKEY=example.com_le1.key
REMOTE_DIR=/etc/nginx/ssl/$DOMAIN

SSH_OPTS="-i $KEY -o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new"

tar -C "$CERT_DIR" -cf - "$CERT" "$PRIVKEY" | ssh $SSH_OPTS root@"$PROXY_IP" "
    set -eu
    mkdir -p '$REMOTE_DIR'
    tar -C '$REMOTE_DIR' -xf -
    chown root:root '$REMOTE_DIR/$CERT' '$REMOTE_DIR/$PRIVKEY'
    chmod 0644 '$REMOTE_DIR/$CERT'
    chmod 0600 '$REMOTE_DIR/$PRIVKEY'
    nginx -t >/dev/null
    systemctl reload nginx
"
