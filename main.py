"""
Main Pipeline Entry Point - Tự động xử lý tất cả các case trong input/
và ghi file output/ cùng với trace.jsonl và metadata.json.
"""

import json
import os
import time
import sys

from src.data_loader import DataStore
from src.input_reader import read_all_cases, get_claimed_order_id, get_case_id
from src.output_writer import write_case_output
from src.agents.coordinator import CoordinatorAgent


def run_pipeline(input_dir: str = "input", output_dir: str = "output", data_dir: str = "data"):
    """Chạy toàn bộ pipeline xử lý khiếu nại."""
    start_time = time.time()

    print("=" * 60)
    print("  Multi-Agent E-commerce Dispute Resolution System")
    print("=" * 60)

    print("\n[1/4] Loading DataStore (9 CSV files)...")
    data_store = DataStore(data_dir)
    print(f"  ✓ Orders: {len(data_store.orders)}")
    print(f"  ✓ Items: {len(data_store.order_items)}")
    print(f"  ✓ Payments: {len(data_store.order_payments)}")
    print(f"  ✓ Customers: {len(data_store.customers)}")

    print("\n[2/4] Reading input cases from input/...")
    cases = read_all_cases(input_dir)
    print(f"  ✓ Found {len(cases)} case(s)")

    if len(cases) == 0:
        print("  ⚠ No input cases found in input/ folder!")
        print("  --> Please copy EC_001.json ... EC_050.json into input/ and re-run.")
        return

    print("\n[3/4] Processing cases via Multi-Agent pipeline...")
    coordinator = CoordinatorAgent(data_dir)
    if coordinator.policy_agent.llm_client.api_key:
        print(f"  ✓ OpenRouter LLM Active: {coordinator.policy_agent.llm_client.model}")
    else:
        print("  ⚠ No LLM API Key found - running fallback mode.")

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
            icon = "✓"
        else:
            error_count += 1
            icon = "✗"

        print(f"  {icon} [{i + 1}/{len(cases)}] {case_id} (Order: {order_id[:10]}...) - {case_duration:.3f}s")

        trace_entry = {
            "case_id": case_id,
            "order_id": order_id,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "duration_seconds": round(case_duration, 3),
            "success": result.success,
            "error": result.error if not result.success else "",
            "agents_invoked": [
                step["agent"] for step in result.data.get("trace_steps", [])
            ],
        }
        trace_entries.append(trace_entry)

    total_duration = time.time() - start_time

    print(f"\n[4/4] Generating logs & metadata...")

    os.makedirs("logging", exist_ok=True)
    for trace_path in ["trace.jsonl", "logging/trace.jsonl"]:
        with open(trace_path, "w", encoding="utf-8") as f:
            for entry in trace_entries:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(f"  ✓ trace.jsonl generated ({len(trace_entries)} entries)")

    model_name = "nvidia/nemotron-nano-9b-v2:free"
    metadata = {
        "model": model_name,
        "model_display_name": f"{model_name} (OpenRouter)",
        "parameter_size": "9B parameters (<= 10B)",
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

    for meta_path in ["metadata.json", "logging/metadata.json"]:
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
    print(f"  ✓ metadata.json generated")

    print("\n" + "=" * 60)
    print(f"  DONE! Processed {success_count}/{len(cases)} cases successfully.")
    print(f"  Total execution time: {total_duration:.2f} seconds")
    print(f"  Outputs written to: {output_dir}/")
    print("=" * 60)


if __name__ == "__main__":
    run_pipeline()
