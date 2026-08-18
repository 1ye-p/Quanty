"""Scan meta_strategy_configs for tiers+pct same-side mutex violations.

Pre-flight check before enabling the hard mutex validation in
GlobalStopPolicy (PRD_TP_TIERS_I18N v2.0 Task 0). Run result 2026-08-18:
3 configs, 0 containing 'tiers' — zero hits, mutex validation safe.
"""
import json
import urllib.request


def scan(base_url: str = "http://localhost:8000") -> dict:
    """Scan live API for configs with both tiers and pct on the same side."""
    with urllib.request.urlopen(f"{base_url}/api/v1/strategies") as resp:
        data = json.load(resp)
    items = data.get("items", [])
    hits = []
    for it in items:
        cfg = str(it.get("config", "") or "") + str(it.get("parsed_config", "") or "")
        if "tiers" in cfg:
            side = []
            if "stop_loss_pct" in cfg:
                side.append("sl")
            if "take_profit_pct" in cfg:
                side.append("tp")
            if side:
                hits.append({"strategy_id": it.get("strategy_id"), "sides": side})
    return {"total": len(items), "with_tiers": sum(1 for i in items if "tiers" in str(i.get("config", ""))), "mutex_hits": hits}


if __name__ == "__main__":
    result = scan()
    print(f"total={result['total']} with_tiers={result['with_tiers']} mutex_hits={len(result['mutex_hits'])}")
    for h in result["mutex_hits"]:
        print(f"  {h['strategy_id']}: {h['sides']}")
    print("SAFE" if not result["mutex_hits"] else "MIGRATE FIRST")
