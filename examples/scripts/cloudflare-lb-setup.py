#!/usr/bin/env python3
"""Create Cloudflare Load Balancer objects for regional edge proxies.

Template credentials:

    export CF_EMAIL="admin@example.com"
    export CF_API_KEY="global-api-key-or-use-token-version"

For production prefer scoped API Tokens and adapt auth headers accordingly.
Cloudflare Load Balancing must be enabled on the account before pools/LBs can be created.
"""

import json
import os
import sys
import urllib.error
import urllib.request

ZONE_NAME = "example.com"

POOLS = [
    {
        "name": "ru-moscow",
        "description": "Moscow edge proxy",
        "latitude": 55.7558,
        "longitude": 37.6173,
        "origins": [{"name": "ru-moscow-1", "address": "194.67.92.242", "enabled": True, "weight": 1.0}],
    },
    {
        "name": "ru-novosibirsk",
        "description": "Novosibirsk edge proxy",
        "latitude": 55.0084,
        "longitude": 82.9357,
        "origins": [{"name": "ru-novosibirsk-1", "address": "186.246.28.244", "enabled": True, "weight": 1.0}],
    },
]


class CloudflareError(RuntimeError):
    pass


def api(method, path, payload=None):
    email = os.environ.get("CF_EMAIL")
    key = os.environ.get("CF_API_KEY")
    if not email or not key:
        raise CloudflareError("Set CF_EMAIL and CF_API_KEY.")

    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        "https://api.cloudflare.com/client/v4" + path,
        data=data,
        method=method,
        headers={
            "X-Auth-Email": email,
            "X-Auth-Key": key,
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.load(resp)
    except urllib.error.HTTPError as exc:
        result = json.loads(exc.read())

    if not result.get("success"):
        errors = "; ".join(f"{e.get('code')}: {e.get('message')}" for e in result.get("errors", []))
        raise CloudflareError(f"{method} {path} failed: {errors}")
    return result.get("result")


def find_by_name(items, name):
    return next((item for item in items if item.get("name") == name), None)


def get_zone_and_account():
    zones = api("GET", f"/zones?name={ZONE_NAME}&per_page=20")
    zone = find_by_name(zones, ZONE_NAME)
    if not zone:
        raise CloudflareError(f"Zone {ZONE_NAME} is not visible to this API key.")
    return zone["id"], zone["account"]["id"]


def upsert_monitor(account_id):
    payload = {
        "description": f"{ZONE_NAME} proxy health",
        "type": "https",
        "method": "GET",
        "path": "/_proxy_health",
        "expected_codes": "200",
        "expected_body": "ok",
        "header": {"Host": [ZONE_NAME]},
        "follow_redirects": False,
        "allow_insecure": False,
    }
    monitors = api("GET", f"/accounts/{account_id}/load_balancers/monitors")
    current = next((m for m in monitors if m.get("description") == payload["description"]), None)
    if current:
        return api("PUT", f"/accounts/{account_id}/load_balancers/monitors/{current['id']}", payload)
    return api("POST", f"/accounts/{account_id}/load_balancers/monitors", payload)


def upsert_pool(account_id, pool, monitor_id):
    payload = {
        "name": pool["name"],
        "description": pool["description"],
        "enabled": True,
        "minimum_origins": 1,
        "monitor": monitor_id,
        "latitude": pool["latitude"],
        "longitude": pool["longitude"],
        "origins": pool["origins"],
    }
    pools = api("GET", f"/accounts/{account_id}/load_balancers/pools")
    current = find_by_name(pools, pool["name"])
    if current:
        return api("PUT", f"/accounts/{account_id}/load_balancers/pools/{current['id']}", payload)
    return api("POST", f"/accounts/{account_id}/load_balancers/pools", payload)


def delete_conflicting_a_records(zone_id, hostname):
    records = api("GET", f"/zones/{zone_id}/dns_records?type=A&name={hostname}&per_page=100")
    for record in records:
        api("DELETE", f"/zones/{zone_id}/dns_records/{record['id']}")


def upsert_load_balancer(zone_id, hostname, pool_ids):
    delete_conflicting_a_records(zone_id, hostname)
    payload = {
        "name": hostname,
        "description": f"{ZONE_NAME} regional proxy load balancer",
        "proxied": False,
        "ttl": 30,
        "enabled": True,
        "session_affinity": "none",
        "steering_policy": "proximity",
        "location_strategy": {"mode": "resolver_ip", "prefer_ecs": "proximity"},
        "fallback_pool": pool_ids[0],
        "default_pools": pool_ids,
    }
    lbs = api("GET", f"/zones/{zone_id}/load_balancers?per_page=100")
    current = find_by_name(lbs, hostname)
    if current:
        return api("PUT", f"/zones/{zone_id}/load_balancers/{current['id']}", payload)
    return api("POST", f"/zones/{zone_id}/load_balancers", payload)


def main():
    zone_id, account_id = get_zone_and_account()
    monitor = upsert_monitor(account_id)
    pool_ids = [upsert_pool(account_id, pool, monitor["id"])["id"] for pool in POOLS]
    for hostname in (ZONE_NAME, "www." + ZONE_NAME):
        lb = upsert_load_balancer(zone_id, hostname, pool_ids)
        print(f"{lb['name']} -> {lb['id']} steering={lb.get('steering_policy')}")


if __name__ == "__main__":
    try:
        main()
    except CloudflareError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
