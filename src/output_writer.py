"""
Output Writer - Ghi kết quả output JSON vào thư mục output/.
"""

import json
import os
from typing import Any, Dict


def write_case_output(case_id: str, output_data: Dict[str, Any], output_dir: str = "output"):
    os.makedirs(output_dir, exist_ok=True)
    filepath = os.path.join(output_dir, f"{case_id}.json")
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)


def write_json(path: str, data: Any):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def append_jsonl(path: str, entry: Dict[str, Any]):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
