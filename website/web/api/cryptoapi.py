#!/usr/bin/env python3

import json
import re
from typing import Any

from flask_restx import Namespace, Resource, fields  # type: ignore
from valkey import Valkey

from ransomlook.default import DB_CRYPTO, get_socket_path

api = Namespace("CryptoAPI", description="Cryptocurrency wallet tracking API", path="/api/crypto")

ALIAS_PREFIX = "crypto:alias:"

# ── Swagger models ──────────────────────────────────────────────────────

crypto_group_model = api.model(
    "CryptoGroup",
    {
        "name": fields.String(description="Canonical group name"),
        "aliases": fields.List(fields.String, description="Known aliases for this group"),
    },
)

wallet_model = api.model(
    "Wallet",
    {
        "address": fields.String(description="Wallet address"),
        "blockchain": fields.String(description="Blockchain name (bitcoin, ethereum, …)"),
        "group": fields.String(description="Associated group slug"),
        "family": fields.String(description="Ransomware family name"),
        "label": fields.String(description="Optional label"),
        "source": fields.String(description="Data source (ransomwhe.re, ransomlook, …)"),
        "tx_count": fields.Integer(description="Number of known transactions"),
        "last_tx_time": fields.String(description="Timestamp of last known transaction"),
        "risk_score": fields.Integer(description="Risk score (0-100)"),
    },
)

tx_model = api.model(
    "Transaction",
    {
        "hash": fields.String(description="Transaction hash"),
        "amount": fields.Float(description="Transaction amount"),
        "from": fields.String(description="Sender address", attribute="from"),
        "to": fields.String(description="Recipient address"),
        "time": fields.String(description="Transaction timestamp"),
        "block": fields.Integer(description="Block number"),
        "fee": fields.Float(description="Transaction fee"),
        "source": fields.String(description="Data source"),
    },
)

wallet_full_model = api.model(
    "WalletFull",
    {
        "address": fields.String(description="Wallet address"),
        "blockchain": fields.String(description="Blockchain name"),
        "group": fields.String(description="Associated group slug"),
        "family": fields.String(description="Ransomware family name"),
        "label": fields.String(description="Optional label"),
        "source": fields.String(description="Data source"),
        "tx_count": fields.Integer(description="Number of known transactions"),
        "last_tx_time": fields.String(description="Timestamp of last known transaction"),
        "risk_score": fields.Integer(description="Risk score (0-100)"),
        "transactions": fields.List(fields.Nested(tx_model), description="Transaction history"),
    },
)

crypto_detail_model = api.model(
    "CryptoDetail",
    {
        "group": fields.String(description="Canonical group name"),
        "aliases": fields.List(fields.String, description="Known aliases"),
        "total": fields.Integer(description="Total number of wallets"),
        "by_chain": fields.Raw(description="Wallets grouped by blockchain {chain: [wallet, …]}"),
    },
)


crypto_stats_model = api.model(
    "CryptoStats",
    {
        "total_addresses": fields.Integer(description="Total number of tracked addresses"),
        "total_transactions": fields.Integer(description="Total number of tracked transactions"),
        "by_chain": fields.Raw(description="Per-blockchain breakdown {chain: {addresses, transactions}}"),
        "groups_with_crypto": fields.Integer(description="Number of groups with at least one wallet"),
    },
)


@api.route("/stats")
@api.doc(description="Return global cryptocurrency statistics: address and transaction counts, broken down by blockchain.")
class CryptoStats(Resource):  # type: ignore[misc]
    @api.response(200, "Crypto statistics", crypto_stats_model)  # type: ignore[untyped-decorator]
    def get(self) -> dict[str, Any]:
        red = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_CRYPTO)
        by_chain: dict[str, dict[str, int]] = {}
        total_addr = 0
        total_tx = 0

        by_group: dict[str, dict[str, int]] = {}

        for key in red.scan_iter(match="crypto:addr:*"):
            k_dec = key.decode()
            parts = k_dec.split(":", 3)
            if len(parts) < 4:
                continue
            chain = parts[2]
            total_addr += 1
            raw = red.get(key)
            if not raw:
                continue
            try:
                doc = json.loads(raw)  # type: ignore[arg-type]
            except Exception:
                continue
            ntx = len(doc.get("transactions", []))
            total_tx += ntx
            group = doc.get("group", "unknown")

            if chain not in by_chain:
                by_chain[chain] = {"addresses": 0, "transactions": 0}
            by_chain[chain]["addresses"] += 1
            by_chain[chain]["transactions"] += ntx

            if group not in by_group:
                by_group[group] = {"addresses": 0, "transactions": 0}
            by_group[group]["addresses"] += 1
            by_group[group]["transactions"] += ntx

        by_chain = dict(sorted(by_chain.items()))
        by_group = dict(sorted(by_group.items(), key=lambda x: x[1]["transactions"], reverse=True))
        return {
            "total_addresses": total_addr,
            "total_transactions": total_tx,
            "groups_with_crypto": len(by_group),
            "by_chain": by_chain,
            "by_group": by_group,
        }


@api.route("/chain/<string:chain>")
@api.doc(
    description="Return all wallet addresses for a given blockchain.",
    params={"chain": "Blockchain name (bitcoin, ethereum, litecoin, …)"},
)
class CryptoByChain(Resource):  # type: ignore[misc]
    @api.response(200, "List of wallets for this blockchain", [wallet_model])  # type: ignore[untyped-decorator]
    @api.response(404, "No wallets found for this blockchain")  # type: ignore[untyped-decorator]
    def get(self, chain: str) -> list[dict[str, Any]]:
        red = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_CRYPTO)
        chain = chain.strip().lower()
        wallets: list[dict[str, Any]] = []

        for key in red.scan_iter(match=f"crypto:addr:{chain}:*"):
            raw = red.get(key)
            if not raw:
                continue
            try:
                doc = json.loads(raw)  # type: ignore[arg-type]
            except Exception:
                continue
            doc.pop("transactions", None)
            doc.setdefault("blockchain", chain)
            doc.setdefault("address", key.decode().split(":", 3)[3] if key.decode().count(":") >= 3 else "")
            doc.setdefault("source", "unknown")
            wallets.append(doc)

        if not wallets:
            api.abort(404, f"No wallets found for blockchain '{chain}'")

        wallets.sort(key=lambda x: (x.get("tx_count", 0), x.get("last_tx_time") or ""), reverse=True)
        return wallets


@api.route("/recent")
@api.route("/recent/<int:limit>")
@api.doc(
    description="Return the most recent transactions across all wallets.",
    params={"limit": "Maximum number of transactions to return (default 50, max 500)"},
)
class CryptoRecent(Resource):  # type: ignore[misc]
    @api.response(200, "Recent transactions", [tx_model])  # type: ignore[untyped-decorator]
    def get(self, limit: int = 50) -> list[dict[str, Any]]:
        limit = min(max(1, limit), 500)
        red = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_CRYPTO)
        all_txs: list[dict[str, Any]] = []

        for key in red.scan_iter(match="crypto:addr:*"):
            raw = red.get(key)
            if not raw:
                continue
            try:
                doc = json.loads(raw)  # type: ignore[arg-type]
            except Exception:
                continue
            chain = doc.get("blockchain", "unknown")
            addr = doc.get("address", "")
            group = doc.get("group", "unknown")
            for tx in doc.get("transactions", []):
                tx["_chain"] = chain
                tx["_address"] = addr
                tx["_group"] = group
                all_txs.append(tx)

        # Sort by time descending
        all_txs.sort(key=lambda t: t.get("time") or 0, reverse=True)
        result = []
        for tx in all_txs[:limit]:
            result.append({
                "hash": tx.get("hash", ""),
                "amount": tx.get("amount"),
                "amountUSD": tx.get("amountUSD"),
                "from": tx.get("from", ""),
                "to": tx.get("to", ""),
                "time": tx.get("time"),
                "block": tx.get("block"),
                "source": tx.get("source", "unknown"),
                "blockchain": tx.pop("_chain", ""),
                "address": tx.pop("_address", ""),
                "group": tx.pop("_group", ""),
            })
        return result


@api.route("/links")
@api.route("/links/<string:name>")
@api.doc(
    description="Find cross-group links via shared transaction addresses. "
    "Detects when a tracked address sends to or receives from another tracked address, "
    "potentially linking different ransomware groups.",
    params={"name": "(Optional) Filter links for a specific group"},
)
class CryptoLinks(Resource):  # type: ignore[misc]
    @api.response(200, "Cross-group transaction links")  # type: ignore[untyped-decorator]
    def get(self, name: str | None = None) -> list[dict[str, Any]]:
        red = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_CRYPTO)

        # Build index: address → {group, chain}
        addr_index: dict[str, dict[str, str]] = {}
        all_docs: list[dict[str, Any]] = []

        for key in red.scan_iter(match="crypto:addr:*"):
            raw = red.get(key)
            if not raw:
                continue
            try:
                doc = json.loads(raw)  # type: ignore[arg-type]
            except Exception:
                continue
            chain = doc.get("blockchain", "unknown")
            addr = doc.get("address", "")
            group = doc.get("group", "unknown")
            addr_index[addr.lower()] = {"group": group, "chain": chain}
            all_docs.append(doc)

        # Scan transactions for links
        links: list[dict[str, Any]] = []
        seen: set[str] = set()

        for doc in all_docs:
            src_group = doc.get("group", "unknown")
            src_addr = doc.get("address", "")
            chain = doc.get("blockchain", "unknown")

            if name and src_group.lower() != name.lower():
                continue

            for tx in doc.get("transactions", []):
                tx_hash = tx.get("hash", "")
                for direction, field in [("outgoing", "to"), ("incoming", "from")]:
                    counterpart = (tx.get(field) or "").lower()
                    if not counterpart or counterpart == src_addr.lower():
                        continue
                    match = addr_index.get(counterpart)
                    if not match:
                        continue

                    # Deduplicate by tx hash + direction
                    link_key = f"{tx_hash}:{src_addr}:{counterpart}"
                    if link_key in seen:
                        continue
                    seen.add(link_key)

                    link: dict[str, Any] = {
                        "source_group": src_group,
                        "source_address": src_addr,
                        "target_group": match["group"],
                        "target_address": counterpart,
                        "direction": direction,
                        "blockchain": chain,
                        "tx_hash": tx_hash,
                        "amount": tx.get("amount"),
                        "time": tx.get("time"),
                        "same_group": src_group.lower() == match["group"].lower(),
                    }
                    links.append(link)

        links.sort(key=lambda x: x.get("time") or 0, reverse=True)
        return links


@api.route("/")
@api.doc(description="Return the list of all groups that have associated cryptocurrency wallets.")
class CryptoGroups(Resource):  # type: ignore[misc]
    @api.response(200, "List of crypto groups", [crypto_group_model])  # type: ignore[untyped-decorator]
    def get(self) -> list[dict[str, Any]]:
        red = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_CRYPTO)

        found = set()
        cursor = 0
        while True:
            cursor, keys = red.scan(cursor=cursor, match="idx:group:*:crypto", count=500)  # type: ignore[misc]
            for k in keys:
                k_dec = k.decode()
                parts = k_dec.split(":")
                if len(parts) >= 4 and red.scard(k) > 0:  # type: ignore[operator]
                    found.add(parts[2])
            if cursor == 0:
                break

        # Build alias mapping
        alias_to_canon: dict[str, str] = {}
        cursor = 0
        while True:
            cursor, keys = red.scan(cursor=cursor, match=ALIAS_PREFIX + "*", count=500)  # type: ignore[misc]
            for akey in keys:
                tgt = red.get(akey)
                if not tgt:
                    continue
                alias_norm = akey.decode()[len(ALIAS_PREFIX) :]
                alias_to_canon[alias_norm] = tgt.decode()  # type: ignore[union-attr]
            if cursor == 0:
                break

        canon_to_aliases: dict[str, list[str]] = {}
        for alias, canon in alias_to_canon.items():
            canon_to_aliases.setdefault(canon, []).append(alias)

        data = []
        for canon in sorted(found):
            data.append(
                {
                    "name": canon,
                    "aliases": sorted(canon_to_aliases.get(canon, [])),
                }
            )
        return data


@api.route("/<string:name>")
@api.doc(
    description="Return all cryptocurrency wallets for a group, organized by blockchain.",
    params={"name": "Group name or alias (case-insensitive)"},
)
class CryptoDetail(Resource):  # type: ignore[misc]
    @api.response(200, "Crypto details for the group", crypto_detail_model)  # type: ignore[untyped-decorator]
    @api.response(404, "Group not found or has no wallets")  # type: ignore[untyped-decorator]
    def get(self, name: str) -> dict[str, Any]:
        red = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_CRYPTO)

        # Resolve alias
        alias_norm = re.sub(r"[^a-z0-9]+", "", (name or "").lower())
        canon_raw = red.get(ALIAS_PREFIX + alias_norm)
        canon = canon_raw.decode() if canon_raw else (name or "").strip() or "Unknown"  # type: ignore[union-attr]

        # Collect aliases
        aliases: list[str] = []
        cursor = 0
        while True:
            cursor, keys = red.scan(cursor=cursor, match=ALIAS_PREFIX + "*", count=500)  # type: ignore[misc]
            for k in keys:
                tgt = red.get(k)
                if tgt and tgt.decode() == canon:  # type: ignore[union-attr]
                    aliases.append(k.decode()[len(ALIAS_PREFIX) :])
            if cursor == 0:
                break
        aliases.sort()

        # Wallets
        members: set[bytes] = red.smembers(f"idx:group:{canon}:crypto") or set()  # type: ignore[assignment]
        by_chain: dict[str, list[dict[str, Any]]] = {}
        total = 0
        for it in members:
            ca = it.decode()
            if ":" not in ca:
                continue
            chain, addr = ca.split(":", 1)
            raw = red.get(f"crypto:addr:{chain}:{addr}")
            if not raw:
                continue
            try:
                doc = json.loads(raw)  # type: ignore[arg-type]
            except Exception:
                continue
            # Strip transactions from list view (can be large)
            doc.pop("transactions", None)
            doc.setdefault("source", "unknown")
            doc.setdefault("blockchain", chain)
            doc.setdefault("address", addr)
            by_chain.setdefault(chain, []).append(doc)
            total += 1

        if total == 0:
            api.abort(404, "No wallets found for this group")

        for lst in by_chain.values():
            lst.sort(key=lambda x: (x.get("tx_count", 0), x.get("last_tx_time") or ""), reverse=True)
        by_chain = dict(sorted(by_chain.items()))

        return {
            "group": canon,
            "aliases": aliases,
            "total": total,
            "by_chain": by_chain,
        }


@api.route("/addr/<string:chain>/<string:address>")
@api.doc(
    description="Return full wallet details including transaction history.",
    params={"chain": "Blockchain name (bitcoin, ethereum, …)", "address": "Wallet address"},
)
class CryptoAddress(Resource):  # type: ignore[misc]
    @api.response(200, "Wallet details with transactions", wallet_full_model)  # type: ignore[untyped-decorator]
    @api.response(404, "Wallet not found")  # type: ignore[untyped-decorator]
    def get(self, chain: str, address: str) -> dict[str, Any]:
        red = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_CRYPTO)
        raw = red.get(f"crypto:addr:{chain}:{address}")
        if not raw:
            api.abort(404, "Wallet not found")
        try:
            doc = json.loads(raw)  # type: ignore[arg-type]
        except Exception:
            api.abort(500, "Malformed wallet data")
        doc.setdefault("blockchain", chain)
        doc.setdefault("address", address)
        doc.setdefault("transactions", [])
        return doc
