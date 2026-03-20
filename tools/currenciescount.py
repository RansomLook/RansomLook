import json
from valkey import Valkey
red = Valkey(unix_socket_path="cache/cache.sock", db=7)
total_tx = 0
total_addr = 0
for key in red.scan_iter(match="crypto:addr:bitcoin:*"):
    total_addr += 1
    data = json.loads(red.get(key))  # type: ignore[arg-type]
    total_tx += len(data.get("transactions", []))
print(f"Adresses: {total_addr}")
print(f"Transactions: {total_tx}")
