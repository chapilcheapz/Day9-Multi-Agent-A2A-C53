"""
Output Writer - Ghi kết quả output JSON vào thư mục output/.
"""

import json
import os
from typing import Dict, Any


def write_case_output(case_id: str, output_data: Dict[str, Any], output_dir: str = "output"):
    """
    Ghi output JSON cho một case vào output_dir.
    Tên file đầu ra khớp chuẩn với case_id: EC_XXX.json
    """
    os.makedirs(output_dir, exist_ok=True)
    filepath = os.path.join(output_dir, f"{case_id}.json")

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
