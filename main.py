"""
Main Pipeline Entry Point - Xử lý tất cả case trong input/
và ghi output/ + trace.jsonl + metadata.json.

Chạy:  python main.py
"""

import json
import os
import sys
import time

from src import config
from src.agents.coordinator import CoordinatorAgent
from src.data_loader import DataStore
from src.input_reader import get_case_id, get_claimed_order_id, read_all_cases
from src.output_writer import write_case_output

MODEL_NAME = config.LLM_MODEL_NAME


def run_pipeline(input_dir: str = "input", output_dir: str = "output", data_dir: str = "data"):
    start_time = time.time()

    print("=" * 64)
    print("  Multi-Agent E-commerce Dispute Resolution (EC_POLICY_V2)")
    print("=" * 64)

    print("\n[1/4] Loading DataStore (9 CSV files)...")
    data_store = DataStore(data_dir)
    print(f"  Orders={len(data_store.orders)} | Items={len(data_store.order_items)} "
          f"| Payments={len(data_store.order_payments)} | Customers={len(data_store.customers)}")

    print("\n[2/4] Reading input cases...")
    cases = read_all_cases(input_dir)
    print(f"  Found {len(cases)} case(s)")
    if not cases:
        print("  Không có input case nào trong input/!")
        return

    print("\n[3/4] Processing cases via Multi-Agent pipeline...")
    coordinator = CoordinatorAgent(data_dir)
    llm_status = f"ACTIVE ({coordinator.llm_client.model})" if coordinator.llm_client.active else "FALLBACK (no key)"
    print(f"  LLM status: {llm_status}")

    trace_entries = []
    success_count = 0
    error_count = 0

    for i, case in enumerate(cases):
        case_id = get_case_id(case)
        order_id = get_claimed_order_id(case)

        case_start = time.time()
        result = coordinator.process(order_id, case, {})
        case_duration = time.time() - case_start

        if result.success:
            output_data = result.data.get("output", {})
            write_case_output(case_id, output_data, output_dir)
            success_count += 1
            icon = "OK"
        else:
            error_count += 1
            icon = "FAIL"

        agents = ", ".join(step["agent"] for step in result.data.get("trace_steps", [])) if result.success else ""
        print(f"  [{i+1:>2}/{len(cases)}] {case_id} {icon} "
              f"order={order_id[:12]}... ({case_duration:.2f}s) agents={agents}")
        if not result.success:
            print(f"         error: {result.error}")

        trace_entries.append({
            "case_id": case_id,
            "order_id": order_id,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "duration_seconds": round(case_duration, 3),
            "success": result.success,
            "error": result.error if not result.success else "",
            "agents_invoked": [
                step["agent"] for step in result.data.get("trace_steps", [])
            ],
            "llm_used": result.data.get("llm_claims", {}) if result.success else {},
            "primary_issue": result.data.get("output", {}).get("case_assessment", {}).get("primary_issue")
            if result.success else None,
        })

    total_duration = time.time() - start_time

    print("\n[4/4] Generating logs & metadata...")
    os.makedirs("logging", exist_ok=True)
    for path in ["trace.jsonl", "logging/trace.jsonl"]:
        with open(path, "w", encoding="utf-8") as f:
            for entry in trace_entries:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(f"  trace.jsonl generated ({len(trace_entries)} entries)")

    metadata = {
        "model": MODEL_NAME,
        "model_display_name": config.LLM_MODEL_DISPLAY,
        "parameter_size": config.LLM_PARAMETER_SIZE,
        "framework": "Custom Python Multi-Agent Framework",
        "runtime": {
            "python_version": sys.version,
            "total_duration_seconds": round(total_duration, 2),
            "cases_processed": len(cases),
            "success_count": success_count,
            "error_count": error_count,
        },
        "agents": [
            "CoordinatorAgent",
            "CustomerAgent",
            "OrderProductAgent",
            "PaymentAgent",
            "DeliveryAgent",
            "PolicyAgent",
            "VerifierAgent",
        ],
    }
    for path in ["metadata.json", "logging/metadata.json"]:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
    print("  metadata.json generated")

    print("\n" + "=" * 64)
    print(f"  DONE: {success_count}/{len(cases)} cases success | {total_duration:.2f}s")
    print(f"  Outputs: {output_dir}/ | trace: trace.jsonl | metadata: metadata.json")
    print("=" * 64)


if __name__ == "__main__":
    run_pipeline()
