# Безопасность proxy-инфраструктуры

Proxy-серверы стоят на публичном периметре, поэтому они должны быть простыми, воспроизводимыми и без секретов в git.

## Секреты

Нельзя хранить в репозитории:

- приватные SSH-ключи;
- TLS private keys;
- Cloudflare API keys/tokens;
- пароли от VPS;
- `.env` с секретами;
- production-конфиги с приватными значениями.

Рекомендуемо:

- отдельный SSH key на каждый edge;
- права `0600` на private key;
- Cloudflare API Token вместо Global API Key;
- регулярная ротация ключей;
- `.gitignore` для `*.key`, `*.pem`, `*_ed25519`, `secrets/`.

## SSH

На edge желательно:

```text
PermitRootLogin prohibit-password
PasswordAuthentication no
PubkeyAuthentication yes
```

Если root нужен для reverse tunnel, используйте отдельный ключ с понятным comment и ограничьте доступ firewall-ом.

## Firewall

На edge открыть:

- `80/tcp`;
- `443/tcp`;
- `443/udp`, если есть HTTP/3;
- `22/tcp` только для админских IP или origin.

Tunnel ports должны слушать только localhost:

```text
127.0.0.1:18443 LISTEN
127.0.0.1:18444 LISTEN
127.0.0.1:18445 LISTEN
```

Проверка:

```bash
ss -ltnup
```

## TLS

- TLS 1.2/1.3;
- private key `0600`;
- chain/cert `0644`;
- проверка SAN перед включением proxy.

```bash
openssl x509 -in /etc/nginx/ssl/example.com/fullchain.pem -noout -subject -issuer -dates -ext subjectAltName
```

## Origin hardening

Если весь публичный трафик идет через edge:

- закрыть origin от всего интернета, кроме edge IP;
- оставить SSH только для админских IP;
- database не должна слушать public interface;
- admin панели защищать IP allowlist/basic auth.

## Headers и real IP

Для DNS-only edge:

```nginx
proxy_set_header X-Real-IP $remote_addr;
proxy_set_header X-Forwarded-For $remote_addr;
```

Если перед edge стоит Cloudflare orange-cloud, настройте `real_ip_header CF-Connecting-IP` и `set_real_ip_from` для Cloudflare ranges.

## Cache safety

Никогда не кешировать:

- admin;
- login;
- cart/checkout;
- личный кабинет;
- preview;
- ответы с `Set-Cookie`;
- API с персональными данными.

Всегда включайте диагностику:

```nginx
add_header X-Proxy-Region ru-moscow always;
add_header X-Proxy-Cache $upstream_cache_status always;
```

## Logs

Логировать:

- nginx access/error;
- tunnel systemd journal;
- health check results;
- DNS/LB changes.

Не логировать:

- cookies целиком;
- Authorization headers;
- private tokens;
- POST body.
