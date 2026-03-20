import json
from collections import defaultdict
from valkey import Valkey

red = Valkey(unix_socket_path="cache/cache.sock", db=7)
stats: dict[str, dict[str, int]] = defaultdict(lambda: {"addr": 0, "tx": 0})
for key in red.scan_iter(match="crypto:addr:*"):
    data = json.loads(red.get(key))  # type: ignore[arg-type]
    group = data.get("group", "unknown")
    stats[group]["addr"] += 1
    stats[group]["tx"] += len(data.get("transactions", []))

print(f"{'Group':<30} {'Addr':>6} {'TX':>8}")
print("-" * 46)
for group in sorted(stats, key=lambda g: stats[g]["tx"], reverse=True):
    s = stats[group]
    print(f"{group:<30} {s['addr']:>6} {s['tx']:>8}")

print("-" * 46)
total_addr = sum(s["addr"] for s in stats.values())
total_tx = sum(s["tx"] for s in stats.values())
print(f"{'TOTAL':<30} {total_addr:>6} {total_tx:>8}")
