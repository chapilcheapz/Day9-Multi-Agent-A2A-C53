"""
Input Reader - Đọc và parse các file input JSON từ thư mục input/.
"""

import glob
import json
import os
from typing import Any, Dict, List


def read_single_case(filepath: str) -> Dict[str, Any]:
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def read_all_cases(input_dir: str = "input") -> List[Dict[str, Any]]:
    """Đọc tất cả file EC_*.json, trả về list sắp xếp theo tên file."""
    cases = []
    for filepath in sorted(glob.glob(os.path.join(input_dir, "EC_*.json"))):
        cases.append(read_single_case(filepath))
    return cases


def get_claimed_order_id(case: Dict[str, Any]) -> str:
    return case.get("customer_request", {}).get("claimed_order_id", "")


def get_case_id(case: Dict[str, Any]) -> str:
    return case.get("case_id", "")


def get_customer_message(case: Dict[str, Any]) -> str:
    return case.get("customer_request", {}).get("message", "")
