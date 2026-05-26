# Runbook: добавить новый российский edge proxy

Пример: добавить `ru-novosibirsk` к западному origin.

## 0. Переменные

```bash
DOMAIN="example.com"
PROXY_NAME="ru-novosibirsk"
PROXY_IP="186.246.28.244"
ORIGIN_IP="135.125.171.168"
ORIGIN_IFACE="eno1"
ORIGIN_GW="135.125.171.254"
CERT_DIR="/var/www/httpd-cert/app"
CERT_FILE="example.com_le1.crtca"
KEY_FILE="example.com_le1.key"
```

## 1. SSH key на origin

```bash
install -o root -g root -m 0700 -d /root/.ssh
ssh-keygen -t ed25519 -f "/root/.ssh/proxy_${PROXY_NAME}_ed25519" -N "" -C "proxy-${PROXY_NAME}"
cat "/root/.ssh/proxy_${PROXY_NAME}_ed25519.pub"
```

Публичный ключ добавить на edge в `/root/.ssh/authorized_keys`.

Проверка:

```bash
ssh -i "/root/.ssh/proxy_${PROXY_NAME}_ed25519" -o BatchMode=yes root@"$PROXY_IP" 'hostname; uptime; ip -4 addr; ss -ltnp'
```

## 2. Установить nginx на edge

```bash
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y nginx curl ca-certificates openssl libnginx-mod-http-brotli-filter libnginx-mod-http-brotli-static
systemctl enable --now nginx
nginx -V 2>&1 | tr ' ' '\n' | grep -E 'http_ssl|http_v2|http_v3|realip|brotli|gzip' || true
```

Если сборка nginx не поддерживает HTTP/3, не включайте `listen ... quic` и `http3 on`.

## 3. Синхронизировать TLS

На origin:

```bash
tar -C "$CERT_DIR" -cf - "$CERT_FILE" "$KEY_FILE" \
| ssh -i "/root/.ssh/proxy_${PROXY_NAME}_ed25519" root@"$PROXY_IP" "
  set -eu
  mkdir -p /etc/nginx/ssl/$DOMAIN
  tar -C /etc/nginx/ssl/$DOMAIN -xf -
  chown root:root /etc/nginx/ssl/$DOMAIN/*
  chmod 0644 /etc/nginx/ssl/$DOMAIN/$CERT_FILE
  chmod 0600 /etc/nginx/ssl/$DOMAIN/$KEY_FILE
  openssl x509 -in /etc/nginx/ssl/$DOMAIN/$CERT_FILE -noout -subject -enddate
"
```

## 4. Sysctl

```bash
install -o root -g root -m 0644 examples/sysctl/99-proxy-network.conf /etc/sysctl.d/99-proxy-network.conf
sysctl --system
```

## 5. Nginx config

Взять [../examples/nginx/edge-reverse-proxy.conf](../examples/nginx/edge-reverse-proxy.conf), заменить:

- `example.com`;
- `proxy-region`;
- пути сертификатов;
- cache path, если нужен другой;
- upstream tunnel ports.

Активировать:

```bash
ln -sfn /etc/nginx/sites-available/example.com.conf /etc/nginx/sites-enabled/example.com.conf
rm -f /etc/nginx/sites-enabled/default
mkdir -p /var/cache/nginx/app
chown -R www-data:www-data /var/cache/nginx/app
nginx -t
systemctl reload nginx
```

## 6. Reverse SSH tunnels

На origin создать unit из [../examples/systemd/reverse-ssh-tunnel@.service](../examples/systemd/reverse-ssh-tunnel@.service), заменить placeholders и запустить:

```bash
systemctl daemon-reload
systemctl enable --now "proxy-${PROXY_NAME}@18443.service"
systemctl enable --now "proxy-${PROXY_NAME}@18444.service"
systemctl enable --now "proxy-${PROXY_NAME}@18445.service"
```

Проверить на edge:

```bash
ssh root@"$PROXY_IP" "ss -ltnp | grep -E '1844[345]'"
```

## 7. Проверка до DNS

```bash
curl --resolve "$DOMAIN:443:$PROXY_IP" -skI "https://$DOMAIN/"
curl --resolve "$DOMAIN:443:$PROXY_IP" -sk "https://$DOMAIN/_proxy_health"
curl --resolve "$DOMAIN:443:$PROXY_IP" -sS -o /dev/null -w 'code=%{http_code} remote=%{remote_ip} ttfb=%{time_starttransfer} total=%{time_total}\n' "https://$DOMAIN/"
```

Ожидаемо: `HTTP/2 200`, правильный `X-Proxy-Region`, health body `ok REGION`.

## 8. Подключить к DNS/LB

Бесплатный минимум:

```text
A example.com -> old_proxy_ip
A example.com -> new_proxy_ip
A www         -> old_proxy_ip
A www         -> new_proxy_ip
TTL 300
DNS-only
```

Production:

- добавить pool региона;
- включить health monitor;
- выбрать proximity или dynamic latency steering;
- проверить из разных регионов.

## 9. Прогреть cache

```bash
cat urls.txt | xargs -r -P6 -I{} curl --resolve "$DOMAIN:443:$PROXY_IP" -4 -sS --max-time 20 -H 'Accept-Encoding: br,gzip' -o /dev/null '{}'
```

## 10. Rollback

1. Убрать новый IP из DNS/LB.
2. Остановить tunnel services.
3. Проверить, что сайт открывается через старый proxy.
