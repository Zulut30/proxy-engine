# Runbook: проверка и диагностика proxy-связки

## DNS

```bash
dig +short NS example.com
for r in 1.1.1.1 8.8.8.8 9.9.9.9; do
  echo "resolver=$r"
  dig +short A example.com @"$r"
  dig +short A www.example.com @"$r"
done
```

Authoritative:

```bash
for ns in ns1.example.net ns2.example.net; do
  dig A example.com @"$ns" +noall +answer
done
```

## Каждый edge отдельно

```bash
for ip in 194.67.92.242 186.246.28.244; do
  echo "ip=$ip"
  curl --resolve example.com:443:$ip -skD - -o /dev/null https://example.com/ | egrep -i 'HTTP/|x-proxy-region|x-proxy-cache|content-encoding'
  curl --resolve example.com:443:$ip -sk https://example.com/_proxy_health
done
```

## Live-распределение

```bash
for i in $(seq 1 20); do
  curl -4 -sS -o /dev/null -w 'remote=%{remote_ip} code=%{http_code} ttfb=%{time_starttransfer} total=%{time_total}\n' https://example.com/
done
```

Если всегда один IP, возможны DNS cache, browser cache, resolver policy, Cloudflare orange-cloud или отсутствие второй A-записи у authoritative DNS.

## Nginx на edge

```bash
nginx -t
systemctl is-active nginx
ss -ltnp | grep -E ':(80|443|18443|18444|18445)'
tail -n 80 /var/log/nginx/example.com.error.log
tail -n 80 /var/log/nginx/example.com.access.log
```

## Tunnels на origin

```bash
systemctl is-active "proxy-ru-moscow@18443.service" "proxy-ru-moscow@18444.service" "proxy-ru-moscow@18445.service"
journalctl -u "proxy-ru-moscow@18443.service" -n 80 --no-pager
```

На edge:

```bash
ss -ltnp | grep -E '1844[345]'
```

## Cache

```bash
curl --resolve example.com:443:194.67.92.242 -skD - -o /dev/null https://example.com/ | egrep -i 'HTTP/|x-proxy-cache|cache-control|vary'
curl --resolve example.com:443:194.67.92.242 -skD - -o /dev/null https://example.com/ | egrep -i 'HTTP/|x-proxy-cache|cache-control|vary'
```

Ожидаемо: первый запрос `MISS`, повторный `HIT`.

Brotli:

```bash
curl --resolve example.com:443:194.67.92.242 -H 'Accept-Encoding: br' -skD - -o /dev/null https://example.com/ | egrep -i 'HTTP/|content-encoding|x-proxy-cache'
```

## Admin bypass

```bash
curl --resolve example.com:443:194.67.92.242 -skI https://example.com/wp-login.php | egrep -i 'HTTP/|x-proxy-cache|cache-control|set-cookie'
```

Ожидаемо: `X-Proxy-Cache: BYPASS`.

## Типовые проблемы

### 502 Bad Gateway

Проверить tunnel ports, origin:443, `proxy_ssl_name`, firewall и `journalctl` tunnel unit.

### Первый proxy получает весь трафик

Для DNS round-robin это нормально на коротком окне. Нужен geo/proximity LB для управляемого распределения.

### Сибирь не идет в Новосибирск

Round-robin не умеет географию. Нужен proximity/latency/geo Load Balancer.

### Health всегда 200, но сервер перегружен

Добавьте overload guard: при плохом load/memory он ставит файл-флаг, а `/_proxy_health` начинает отдавать `503`.
