#!/bin/sh
set -eu

flag=/run/proxy-overloaded
reason=/run/proxy-overloaded.reason

cores=$(nproc 2>/dev/null || echo 1)
load1=$(awk '{print $1}' /proc/loadavg)
mem_avail_kb=$(awk '/MemAvailable:/ {print $2}' /proc/meminfo)

if [ -f "$flag" ]; then
    load_limit=$(awk -v c="$cores" 'BEGIN {printf "%.2f", c * 2.5}')
else
    load_limit=$(awk -v c="$cores" 'BEGIN {printf "%.2f", c * 4}')
fi

overloaded=0
why=""

if awk -v l="$load1" -v limit="$load_limit" 'BEGIN {exit !(l > limit)}'; then
    overloaded=1
    why="load1=$load1 limit=$load_limit cores=$cores"
fi

if [ "${mem_avail_kb:-0}" -gt 0 ] && [ "$mem_avail_kb" -lt 262144 ]; then
    overloaded=1
    why="${why:+$why }mem_available_kb=$mem_avail_kb"
fi

if [ "$overloaded" -eq 1 ]; then
    printf '%s\n' "${why:-overloaded}" > "$reason"
    touch "$flag"
else
    rm -f "$flag" "$reason"
fi
