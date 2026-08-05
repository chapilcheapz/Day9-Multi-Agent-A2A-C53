"""
Input Reader - Đọc và parse các file input JSON từ thư mục input/.
"""

import json
import os
import glob
from typing import Dict, List, Any


def read_single_case(filepath: str) -> Dict[str, Any]:
    """Đọc một file input JSON và trả về dict."""
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def read_all_cases(input_dir: str = "input") -> List[Dict[str, Any]]:
    """
    Đọc tất cả file EC_*.json trong thư mục input/.
    Trả về list sorted theo tên file case_id.
    """
    cases = []
    pattern = os.path.join(input_dir, "EC_*.json")
    filepaths = sorted(glob.glob(pattern))

    for filepath in filepaths:
        case = read_single_case(filepath)
        cases.append(case)

    return cases


def get_claimed_order_id(case: Dict[str, Any]) -> str:
    """Trích xuất claimed_order_id từ dict case input."""
    return case.get("customer_request", {}).get("claimed_order_id", "")


def get_case_id(case: Dict[str, Any]) -> str:
    """Trích xuất case_id từ dict case input."""
    return case.get("case_id", "")
