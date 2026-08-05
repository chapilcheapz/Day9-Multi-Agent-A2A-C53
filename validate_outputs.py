"""
QA Validator - Kiểm tra toàn bộ output/ sau khi chạy pipeline:
- Đủ 50 file EC_001..EC_050
- Schema đầy đủ đúng key theo đề bài
- Array limits (5/5/3/5/5/5/5/3/3/20/5)
- Evidence IDs tồn tại thật trong CSV và đúng định dạng
- Null handling (order không có item -> rỗng/null)
- Rounding 2 chữ số, confidence thuộc [0,1], case_status enum
- Timestamp định dạng CSV / null

Chạy:  python validate_outputs.py
"""

import json
import os
import re
import sys
from typing import Dict, List, Optional, Tuple

from src import config
from src.data_loader import DataStore

REQUIRED_TOP = [
    "case_id", "case_assessment", "affected_entities", "customer_context",
    "product_context", "delivery_analysis", "payment_reconciliation",
    "root_cause_analysis", "evidence_ids", "financial_resolution", "resolution_actions",
]

REQUIRED_SECTIONS: Dict[str, List[str]] = {
    "case_assessment": ["primary_issue", "secondary_issues", "case_status", "confidence"],
    "affected_entities": ["order_ids", "item_ids", "seller_ids", "payment_ids"],
    "customer_context": ["customer_unique_id", "related_order_ids"],
    "product_context": ["product_ids", "category_names"],
    "delivery_analysis": [
        "delivered_at", "estimated_delivery_at", "carrier_handoff_at",
        "delivery_variance_hours", "seller_handoff_analysis", "late_handoff_seller_ids",
    ],
    "payment_reconciliation": [
        "currency", "item_total_brl", "freight_total_brl", "expected_total_brl",
        "payment_total_brl", "difference_brl", "reconciled", "payment_types",
    ],
    "root_cause_analysis": ["ranked_causes", "responsible_parties"],
    "financial_resolution": ["currency", "recommended_refund_brl"],
}

ALLOWED_LIMITS: Dict[str, int] = {
    "order_ids": 5, "item_ids": 5, "seller_ids": 3, "payment_ids": 5,
    "related_order_ids": 5, "product_ids": 5, "category_names": 5,
    "ranked_causes": 3, "responsible_parties": 3, "evidence_ids": 20,
    "resolution_actions": 5,
}

VALID_PRIMARY = {
    "canceled_order_paid", "unavailable_order_paid", "late_delivery_seller",
    "late_delivery_logistics", "valid_split_payment", "unsupported_late_claim",
}
VALID_STATUS = {"action_required", "no_action"}
VALID_CAUSES = {
    "SELLER_HANDOFF_AFTER_LIMIT", "CARRIER_DELIVERED_AFTER_ESTIMATE",
    "ORDER_CANCELED_AFTER_PAYMENT", "ORDER_UNAVAILABLE_AFTER_PAYMENT",
    "MULTIPLE_PAYMENTS_RECONCILED", "DELIVERY_WITHIN_ESTIMATE",
}
TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")
MONEY_KEYS = ("item_total_brl", "freight_total_brl", "expected_total_brl",
              "payment_total_brl", "difference_brl")


def _check_evidence(eid: str, out: Dict, ds: DataStore, order_id: str) -> bool:
    if eid.count(":") == 0:
        return False
    prefix, _, rest = eid.partition(":")

    if prefix == "order":
        return rest == order_id and ds.get_order(rest) is not None
    if prefix == "item":
        oid, _, seq = rest.partition(":")
        items = ds.get_order_items(oid)
        if items.empty:
            return False
        valid_seqs = set(str(int(r)) for r in items["order_item_id"])
        return seq in valid_seqs
    if prefix == "payment":
        oid, _, seq = rest.partition(":")
        payments = ds.get_order_payments(oid)
        if payments.empty:
            return False
        return seq in set(str(int(r)) for r in payments["payment_sequential"])
    if prefix == "seller":
        return ds.get_seller(rest) is not None
    if prefix == "policy":
        return rest in VALID_CAUSES
    return False


def _check_limits(out: Dict) -> List[str]:
    errors = []

    def check_container(name: str, container: Dict):
        for key, limit in ALLOWED_LIMITS.items():
            if key in container and isinstance(container[key], list) and len(container[key]) > limit:
                errors.append(f"{name}.{key} len {len(container[key])} > {limit}")

    check_container("affected_entities", out.get("affected_entities", {}))
    check_container("customer_context", out.get("customer_context", {}))
    check_container("product_context", out.get("product_context", {}))
    check_container("root_cause_analysis", out.get("root_cause_analysis", {}))
    check_container("root", {"evidence_ids": out.get("evidence_ids", [])})
    check_container("root", {"resolution_actions": out.get("resolution_actions", [])})
    return errors


def check_case(filepath: str, ds: DataStore) -> Tuple[List[str], int]:
    errors: List[str] = []
    with open(filepath, "r", encoding="utf-8") as f:
        out = json.load(f)

    case_id = out.get("case_id")
    if not case_id:
        errors.append("missing case_id")
        return errors, 0

    # 1. schema top-level
    for key in REQUIRED_TOP:
        if key not in out:
            errors.append(f"missing top-level key: {key}")

    # 2. section keys
    for section, keys in REQUIRED_SECTIONS.items():
        sec = out.get(section)
        if not isinstance(sec, dict):
            errors.append(f"{section} not a dict")
            continue
        for key in keys:
            if key not in sec:
                errors.append(f"{section}.{key} missing")

    # 3. enum + confidence
    assessment = out.get("case_assessment", {})
    if assessment.get("primary_issue") not in VALID_PRIMARY:
        errors.append(f"invalid primary_issue: {assessment.get('primary_issue')}")
    if assessment.get("case_status") not in VALID_STATUS:
        errors.append(f"invalid case_status: {assessment.get('case_status')}")
    conf = assessment.get("confidence")
    if not (isinstance(conf, (int, float)) and 0 <= conf <= 1):
        errors.append(f"confidence out of range: {conf}")

    # 4. array limits
    errors += _check_limits(out)

    # 5. input-order join + evidence
    input_path = os.path.join("input", f"{case_id}.json")
    if os.path.exists(input_path):
        with open(input_path, "r", encoding="utf-8") as f:
            case_input = json.load(f)
        order_id = case_input["customer_request"]["claimed_order_id"]

        items = ds.get_order_items(order_id)
        pay = out.get("payment_reconciliation", {})

        # null handling theo đề bài
        if items.empty:
            if pay.get("expected_total_brl") is not None:
                errors.append("expected_total_brl must be null when order has no items")
            if pay.get("difference_brl") is not None:
                errors.append("difference_brl must be null when order has no items")
            for eid in out.get("evidence_ids", []):
                if eid.startswith("item:") or eid.startswith("seller:"):
                    errors.append(f"evidence {eid} invalid for order without items")
        else:
            if pay.get("expected_total_brl") is None:
                errors.append("expected_total_brl must not be null when order has items")

        # evidence validity
        for eid in out.get("evidence_ids", []):
            if not _check_evidence(eid, out, ds, order_id):
                errors.append(f"bad evidence id: {eid}")

        # affected_entities nằm trong evidence (order gốc)
        affected_orders = out.get("affected_entities", {}).get("order_ids", [])
        if order_id not in affected_orders:
            errors.append("claimed order missing in affected_entities.order_ids")

        # quy tắc primary theo order_status (bắt lỗi order_status bị mất)
        order = ds.get_order(order_id)
        if order is not None:
            status = str(order.get("order_status", ""))
            pay_total = pay.get("payment_total_brl") or 0
            primary = assessment.get("primary_issue")
            if status == "canceled" and pay_total > 0 and primary != "canceled_order_paid":
                errors.append(f"status canceled + paid -> must be canceled_order_paid, got {primary}")
            if status == "unavailable" and pay_total > 0 and primary != "unavailable_order_paid":
                errors.append(f"status unavailable + paid -> must be unavailable_order_paid, got {primary}")

    # 6. rounding
    pay = out.get("payment_reconciliation", {})
    for k in MONEY_KEYS:
        v = pay.get(k)
        if isinstance(v, (int, float)) and round(v, 2) != v:
            errors.append(f"{k} not rounded to 2 decimals: {v}")
    refund = out.get("financial_resolution", {}).get("recommended_refund_brl")
    if isinstance(refund, (int, float)) and round(refund, 2) != refund:
        errors.append(f"recommended_refund_brl not rounded: {refund}")

    # 7. timestamps
    da = out.get("delivery_analysis", {})
    for k in ("delivered_at", "estimated_delivery_at", "carrier_handoff_at"):
        v = da.get(k)
        if v is not None and not TS_RE.match(str(v)):
            errors.append(f"delivery_analysis.{k} invalid format: {v}")
    for row in da.get("seller_handoff_analysis", []):
        lim = row.get("shipping_limit_at")
        if lim is not None and not TS_RE.match(str(lim)):
            errors.append(f"shipping_limit_at invalid format: {lim}")

    return errors, (0 if errors else 1)


def main() -> int:
    print("QA validator for output/ (hard gate check)")
    ds = DataStore()
    files = sorted(
        f for f in os.listdir("output")
        if re.match(r"^EC_\d{3}\.json$", f)
    )
    if len(files) != 50:
        print(f"  WARNING: expected 50 files, found {len(files)}")
        return 1

    all_errors = 0
    for f in files:
        errors, score = check_case(os.path.join("output", f), ds)
        if errors:
            print(f"  {f}: FAIL")
            for e in errors:
                print(f"      - {e}")
        else:
            print(f"  {f}: OK (score {score})")
        all_errors += len(errors)

    print(f"\nTOTAL ERRORS: {all_errors}")
    return 1 if all_errors else 0


if __name__ == "__main__":
    sys.exit(main())