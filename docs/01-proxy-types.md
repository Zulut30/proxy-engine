# Виды proxy и когда их использовать

Proxy-инфраструктура обычно состоит из нескольких слоев. Для публичного сайта чаще всего нужен reverse proxy, для приватной связи между западным origin и российским edge нужен tunnel, а для распределения пользователей между регионами нужен DNS или Load Balancer.

## Reverse proxy

Reverse proxy принимает входящий HTTP/HTTPS трафик от пользователя и проксирует его на backend/origin.

Инструменты:

- nginx;
- HAProxy;
- Caddy;
- Envoy;
- Traefik.

Подходит для сайтов, WordPress, API, TLS termination, Brotli/gzip, cache, защиты admin URL и выдачи регионального edge в Москве, Новосибирске или Владивостоке.

Типовая схема:

```text
client -> ru-edge nginx -> local tunnel port -> western origin
```

Плюсы: быстрый, простой, умеет кешировать, хорошо диагностируется через headers `X-Proxy-Region` и `X-Proxy-Cache`.

Минусы: без внешнего DNS/LB не выбирает регион сам; надо аккуратно обходить cache для login/admin/API.

## Forward proxy

Forward proxy используется приложениями или пользователями для исходящего трафика.

Инструменты:

- 3proxy;
- Squid;
- HAProxy CONNECT;
- Dante SOCKS.

Подходит для controlled egress через конкретный регион или внутреннего доступа. Для публичного сайта это не основная схема: там нужен reverse proxy.

## Tunnel proxy

Tunnel соединяет серверы приватным каналом. Пользователь его не видит.

Варианты:

- reverse SSH tunnel;
- WireGuard;
- GRE/IPIP;
- Cloudflare Tunnel;
- Tailscale/Headscale.

Reverse SSH удобен для быстрого старта: origin сам открывает соединение к edge, а edge получает локальные порты `127.0.0.1:18443-18445`.

WireGuard лучше для постоянной инфраструктуры: private subnet, меньше overhead, проще маршрутизировать несколько сервисов.

## DNS load balancing

DNS отвечает несколькими IP или выбирает IP по географии/latency/health.

Варианты:

- несколько A-записей DNS round-robin;
- Cloudflare Load Balancing;
- Route53 latency/geolocation routing;
- NS1, DNS Made Easy, Gcore DNS;
- свой authoritative DNS с health checks.

Round-robin бесплатный, но не знает географию и health. Geo/proximity Load Balancer нужен, если трафик из Сибири должен идти в Новосибирск, а Москва должна оставаться fallback.

## L4 TCP proxy

L4 proxy работает на уровне TCP/UDP и не понимает HTTP.

Инструменты:

- HAProxy TCP mode;
- nginx stream;
- IPVS/LVS;
- Envoy TCP proxy.

Используется для TLS passthrough, raw TCP сервисов, non-HTTP протоколов. Для WordPress/HTTP сайта обычно лучше L7 reverse proxy.

## CDN proxy

Cloudflare orange-cloud, Fastly, Bunny, Gcore и другие CDN могут стоять перед вашим edge/origin. Это дает WAF, DDoS protection и edge cache, но если цель - собственные российские маршруты, часто используют DNS-only и свои edge proxy.

## Рекомендации

Минимум:

```text
DNS round-robin -> nginx edge Moscow + Novosibirsk -> reverse SSH tunnel -> western origin
```

Production:

```text
Geo/proximity Load Balancer -> regional nginx edge proxies -> WireGuard/reverse SSH -> western origin
```

Высокая надежность:

```text
Geo LB + health checks + independent providers + monitoring + cache warming + documented rollback
```
