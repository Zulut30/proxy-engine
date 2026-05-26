# DNS и балансировка между proxy

Чтобы несколько proxy работали вместе, нужен слой выбора: DNS, Load Balancer или CDN/LB. Без этого каждый proxy остается отдельной точкой.

## Level 1: DNS round-robin

```text
example.com. 300 IN A 194.67.92.242
example.com. 300 IN A 186.246.28.244
www          300 IN A 194.67.92.242
www          300 IN A 186.246.28.244
```

Что дает:

- оба proxy получают часть трафика;
- бесплатно;
- быстро включается;
- подходит как fallback, пока нет платного LB.

Ограничения:

- нет настоящей географии;
- нет health checks;
- нет гарантии, что Сибирь пойдет в Новосибирск;
- клиенты и резолверы могут кешировать один IP до TTL.

## Level 2: Geo/proximity DNS

DNS/LB выбирает IP по стране, региону, latency или координатам.

Провайдеры:

- Cloudflare Load Balancing;
- AWS Route53 latency/geolocation;
- NS1;
- DNS Made Easy;
- Gcore DNS;
- собственный authoritative DNS с GeoIP.

Для России внутри одной страны лучше `proximity` или latency, чем country-only geo. Country-only geo не отличает Москву от Сибири.

## Level 3: LB с health checks

Production-схема:

```text
pools:
  ru-moscow       -> 194.67.92.242
  ru-novosibirsk -> 186.246.28.244

monitor:
  GET https://example.com/_proxy_health
  Host: example.com
  expected code: 200
  expected body: ok

steering:
  proximity или dynamic_latency
```

Если proxy падает или health endpoint отвечает `503`, LB выводит его из rotation.

## Proximity coordinates

```text
ru-moscow       55.7558, 37.6173
ru-novosibirsk 55.0084, 82.9357
ru-vladivostok 43.1155, 131.8855
```

Proximity полезен, когда пользователи находятся в одной большой стране, а edge стоят в разных регионах.

## Weighted routing

Если нужна разгрузка, но география не обязательна:

```text
70% Moscow
30% Novosibirsk
```

Weighted routing помогает при большом трафике, но сам по себе не гарантирует ближайший регион.

## Health и перегрузка

LB не знает load сервера, если health endpoint всегда `200`. Поэтому можно поставить guard:

```text
normal:     /_proxy_health -> 200 ok
bad load:   /_proxy_health -> 503 overloaded
```

Guard может смотреть load average, свободную память, disk space, nginx connections или custom app health.

## Проверка DNS

```bash
for r in 1.1.1.1 8.8.8.8 9.9.9.9; do
  echo "resolver=$r"
  dig +short A example.com @"$r"
  dig +short A www.example.com @"$r"
done
```

Authoritative check:

```bash
for ns in ns1.example.net ns2.example.net; do
  dig A example.com @"$ns" +noall +answer
done
```

Live check:

```bash
for i in $(seq 1 20); do
  curl -4 -sS -o /dev/null \
    -w 'remote=%{remote_ip} code=%{http_code} ttfb=%{time_starttransfer}\n' \
    https://example.com/
done
```

## Cloudflare notes

Cloudflare Free plan может бесплатно держать несколько A-записей. Настоящий Cloudflare Load Balancing обычно является paid add-on. Если API при создании pools возвращает `Access Failed`, Load Balancing не активирован на аккаунте.
