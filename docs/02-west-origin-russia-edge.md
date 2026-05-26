# Западный origin + российские edge proxy

Эта схема нужна, когда приложение находится на западном origin-сервере, а пользователи из России должны получать быстрый и устойчивый доступ через российские VPS в разных регионах.

## Роли

### Origin

Origin - основной сервер приложения: WordPress/API, PHP, database, production TLS certificates, исходный nginx/apache. Origin держит исходящие tunnel-соединения к edge proxy.

Пример переменных:

```bash
ORIGIN_IP="135.125.171.168"
ORIGIN_IFACE="eno1"
ORIGIN_GW="135.125.171.254"
```

### Edge proxy

Edge proxy - региональный сервер, куда приходит пользовательский трафик:

- nginx;
- TLS termination;
- HTTP/2 или HTTP/3, если сборка поддерживает;
- Brotli/gzip;
- cache;
- health endpoint;
- локальные tunnel ports.

Пример регионов:

```bash
ru-moscow       194.67.92.242
ru-novosibirsk 186.246.28.244
ru-vladivostok 203.0.113.30
```

## Базовый поток

```text
Users -> DNS/Load Balancer -> regional edge nginx -> 127.0.0.1:18443..18445 -> tunnel -> origin:443
```

Edge не обязан ходить напрямую на публичный origin. Надежнее, когда origin сам открывает reverse SSH tunnel или WireGuard-соединение к edge.

## Reverse SSH tunnel

На edge nginx видит upstream как локальные порты:

```nginx
upstream app_origin {
    zone app_origin 64k;
    server 127.0.0.1:18443 max_fails=1 fail_timeout=5s;
    server 127.0.0.1:18444 max_fails=1 fail_timeout=5s;
    server 127.0.0.1:18445 max_fails=1 fail_timeout=5s;
    keepalive 64;
}
```

На origin systemd держит три SSH-процесса с `-R 127.0.0.1:%i:ORIGIN_IP:443 root@PROXY_IP`.

Плюсы reverse SSH:

- быстрый запуск;
- origin инициирует соединение сам;
- работает через NAT/firewall;
- можно закрепить маршрут и congestion control;
- удобно проверять через `ss -ltnp` на edge.

## WireGuard вместо SSH

WireGuard лучше, если edge становится несколько, нужно проксировать больше сервисов или хочется private subnet.

Пример:

```text
origin wg0:       10.70.0.1
moscow wg0:       10.70.0.11
novosibirsk wg0:  10.70.0.12
```

Nginx upstream на edge:

```nginx
upstream app_origin {
    server 10.70.0.1:443 max_fails=1 fail_timeout=5s;
    keepalive 64;
}
```

## Cache

Кешировать можно anonymous HTML и static assets. Нельзя кешировать:

- `/wp-admin/`;
- `/wp-login.php`;
- `/wp-json/`, если API динамический;
- `/xmlrpc.php`;
- preview pages;
- ответы с `Set-Cookie`;
- авторизованных пользователей.

Всегда добавляйте диагностику:

```nginx
add_header X-Proxy-Region ru-moscow always;
add_header X-Proxy-Cache $upstream_cache_status always;
```

## Health endpoint

Каждый edge должен иметь endpoint без похода на origin:

```nginx
location = /_proxy_health {
    access_log off;
    add_header X-Proxy-Region ru-moscow always;
    return 200 "ok ru-moscow\n";
}
```

Для failover по перегрузке endpoint может отдавать `503`, если локальный guard создал `/run/proxy-overloaded`.

## TLS

Варианты:

1. Синхронизировать сертификат с origin на edge.
2. Выпускать сертификат на каждом edge через DNS challenge.

Для старта проще синхронизация:

```bash
tar -C "$CERT_DIR" -cf - "$CERT_FILE" "$KEY_FILE" \
| ssh root@"$EDGE_IP" "mkdir -p /etc/nginx/ssl/$DOMAIN && tar -C /etc/nginx/ssl/$DOMAIN -xf -"
```

Private key должен быть `0600`, chain можно `0644`.

## DNS/LB

Чтобы proxy работали в связке, нужен внешний выбор:

- бесплатно: несколько A-записей;
- правильно: geo/proximity Load Balancer с health checks.

Для Сибири/Востока лучше proximity/latency routing, потому что country-only geo видит всю Россию как одну страну.
