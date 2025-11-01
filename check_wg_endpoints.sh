#!/usr/bin/env bash
DIR="wireguard/wg_confs_disabled"
OUT="wg_endpoint_check.tsv"
echo -e "file\tendpoint\thost\tport\tresolved_ip\tping_ms\tnmap_open_udp" >"$OUT"

for f in "$DIR"/*.conf; do
  ep=$(grep -Ei '^Endpoint\s*=' "$f" | awk -F= '{gsub(/^[ \t]+|[ \t]+$/,"",$2); print $2}')
  if [ -z "$ep" ]; then
    echo -e "$(basename "$f")\t-\t-\t-\t-\t-\t-" >>"$OUT"
    continue
  fi
  host=$(echo "$ep" | sed 's/:.*$//')
  port=$(echo "$ep" | sed 's/^.*://')
  # DNS resolution
  resolved=$(getent ahosts "$host" | awk '{print $1; exit}')
  # ping (ICMP) one packet, record ms
  ping_ms="-"
  if command -v ping >/dev/null; then
    ping_out=$(ping -c 1 -W 1 "$host" 2>/dev/null)
    ping_ms=$(echo "$ping_out" | awk -F'=' '/time=/{print $4}' | sed 's/ ms//')
    [ -z "$ping_ms" ] && ping_ms="-"
  fi
  nmap_result="-"
  if command -v nmap >/dev/null && [ -n "$port" ]; then
    # UDP scan, only the single port, fast timeout
    nmap_out=$(nmap -Pn -sU -p "$port" --host-timeout 5s -T4 "$host" 2>/dev/null)
    # look for "open" in output for the port line
    echo "$nmap_out" | grep -E "^[0-9]+/udp" >/dev/null && nmap_result=$(echo "$nmap_out" | awk '/udp/ {print $2; exit}')
  fi
  echo -e "$(basename "$f")\t$ep\t$host\t$port\t$resolved\t$ping_ms\t$nmap_result" >>"$OUT"
done

echo "Готово — результат в $OUT"
