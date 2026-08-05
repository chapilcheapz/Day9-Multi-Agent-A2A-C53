"""
Cấu hình toàn cục của hệ thống.
Model name được khai báo trực tiếp trong code (theo yêu cầu đề bài,
không đặt trong .env) và được ghi lại trong metadata.json.
"""

LLM_MODEL_NAME = "qwen/qwen3-8b"
LLM_MODEL_DISPLAY = "qwen/qwen3-8b (OpenRouter)"
LLM_PARAMETER_SIZE = "8B parameters (<= 10B)"

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"

ENV_FILE = ".env"

# Giới hạn mảng theo đề bài (mục 6 - Output schema)
MAX_ORDER_IDS = 5
MAX_ITEM_IDS = 5
MAX_SELLER_IDS = 3
MAX_PAYMENT_IDS = 5
MAX_RELATED_ORDER_IDS = 5
MAX_PRODUCT_IDS = 5
MAX_CATEGORY_NAMES = 5
MAX_RANKED_CAUSES = 3
MAX_RESPONSIBLE_PARTIES = 3
MAX_EVIDENCE_IDS = 20
MAX_RESOLUTION_ACTIONS = 5

# Dung sai đối soát thanh toán (BRL)
RECONCILE_TOLERANCE_BRL = 0.10

CURRENCY = "BRL"

# Thứ tự secondary issues theo đề bài
SECONDARY_ISSUE_ORDER = [
    "multi_item_order",
    "multi_seller_order",
    "split_payment",
    "repeat_customer",
    "multiple_categories",
]
