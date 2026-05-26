# Proxy Engine

Документация и шаблоны для построения связки proxy-серверов между западным origin-сервером и российскими edge/VPS в разных регионах.

Цель проекта:

- ускорять доступ пользователей из России, Сибири и Дальнего Востока;
- разгружать основной proxy при росте трафика;
- держать fallback, если один proxy или маршрут до него деградирует;
- не открывать origin напрямую, если стабильнее работать через tunnel;
- описывать настройку повторяемо, без хранения паролей и приватных ключей в репозитории.

## Быстрый выбор схемы

| Задача | Рекомендуемая схема |
| --- | --- |
| Сайт/WordPress/API на западном origin, пользователи в РФ | Reverse proxy на российских edge + reverse SSH или WireGuard tunnel к origin |
| Нужна география Москва/Новосибирск/Владивосток | Cloudflare Load Balancing или другой DNS/LB с geo/proximity steering |
| Нужен бесплатный минимум без health checks | Несколько A-записей DNS round-robin |
| Нужен failover при падении proxy | Cloudflare Load Balancing, NS1, DNS Made Easy или свой authoritative DNS с health checks |
| Нужен внутренний приватный канал между серверами | WireGuard site-to-site |
| Нужен forward proxy для исходящего трафика приложений | 3proxy, Squid или HAProxy CONNECT с ACL |

## Структура

- [docs/01-proxy-types.md](docs/01-proxy-types.md) - виды proxy и когда какой выбирать.
- [docs/02-west-origin-russia-edge.md](docs/02-west-origin-russia-edge.md) - основная архитектура: западный origin + российские edge.
- [docs/03-dns-and-load-balancing.md](docs/03-dns-and-load-balancing.md) - DNS, round-robin, geo/proximity routing, health checks.
- [docs/04-security.md](docs/04-security.md) - безопасность ключей, firewall, TLS, real IP, WordPress/admin bypass.
- [runbooks/add-russian-edge.md](runbooks/add-russian-edge.md) - пошаговый runbook добавления нового российского proxy.
- [runbooks/check-and-debug.md](runbooks/check-and-debug.md) - проверки и диагностика.
- [examples/](examples/) - шаблоны nginx, systemd, sysctl и скриптов.
- [examples/scripts/cloudflare-lb-setup.py](examples/scripts/cloudflare-lb-setup.py) - пример автоматизации Cloudflare Load Balancing.

## Базовая топология

```text
Users
  |
  | DNS / Load Balancer
  v
+-------------------+       reverse tunnel       +----------------------+
| Edge proxy Moscow | <------------------------- | Western origin       |
| nginx/cache/TLS   |                            | app/nginx/php/db     |
+-------------------+                            +----------------------+
  ^
  |
+------------------------+
| Edge proxy Novosibirsk |
| nginx/cache/TLS        |
+------------------------+
```

В такой схеме пользователи ходят на ближайший или выбранный DNS/LB proxy, а proxy получает данные с origin через локальные tunnel-порты. Origin не обязан принимать прямые запросы от всего интернета.

## Что не хранить в репозитории

- приватные SSH-ключи;
- Cloudflare Global API Key/API Token;
- пароли от VPS;
- приватные TLS-ключи;
- полные production-конфиги с секретами.

В `examples/` лежат только шаблоны. Значения вроде IP, домена, путей сертификатов и имен регионов нужно подставлять на сервере.

## Минимальный запуск для нового проекта

1. Прочитать [docs/01-proxy-types.md](docs/01-proxy-types.md) и выбрать схему.
2. Поднять первый edge по [runbooks/add-russian-edge.md](runbooks/add-russian-edge.md).
3. Добавить второй edge в другом регионе.
4. Проверить оба proxy через `curl --resolve`.
5. Подключить DNS round-robin или платный geo/proximity Load Balancer.
6. Настроить monitoring и health checks.
