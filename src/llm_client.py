"""
LLM Client - Giao tiếp với LLM qua OpenRouter API.
Model: nvidia/nemotron-nano-9b-v2:free (<= 10B parameters) - khai báo trong src/config.py
Có retry khi bị rate limit/lỗi server và tạm dừng chờ khi mất kết nối mạng.
"""

import json
import os
import re
import time
from typing import Any, Dict, Optional

import requests

from src import config

DEFAULT_SYSTEM_PROMPT = (
    "You are a precise e-commerce dispute resolution assistant working on "
    "the Olist Brazilian e-commerce dataset. Answer based ONLY on the data "
    "provided. Never invent events, timestamps or amounts."
)


def load_env_file(env_path: str = config.ENV_FILE) -> Dict[str, str]:
    """Đọc file .env thủ công (không cần thư viện phụ thuộc)."""
    env: Dict[str, str] = {}
    if not os.path.exists(env_path):
        return env
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            env[key.strip()] = value.strip().strip('"').strip("'")
    return env


class LLMClient:
    """Client kết nối tới OpenRouter LLM API."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY", "")
        if not self.api_key:
            self.api_key = load_env_file().get("OPENROUTER_API_KEY", "")
        self.model = model or config.LLM_MODEL_NAME
        self._requests = 0

    # ------------------------------------------------------------- helpers
    @property
    def active(self) -> bool:
        return bool(self.api_key)

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/chapilcheapz/K4-Day9-Multi-Agent-A2A",
            "X-Title": "K4 Multi-Agent Dispute Resolution",
        }

    def _wait_for_network(self):
        print("\n  [LLM] Mất kết nối mạng - tạm dừng chờ phục hồi (kiểm tra mỗi 5s)...")
        while True:
            try:
                res = requests.get(config.OPENROUTER_MODELS_URL, timeout=5)
                if res.status_code == 200:
                    print("  [LLM] Đã có kết nối trở lại, tiếp tục xử lý...")
                    time.sleep(1)
                    return
            except Exception:
                pass
            time.sleep(5)

    # -------------------------------------------------------------- calls
    def chat_completion(
        self,
        prompt: str,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
        temperature: float = 0.1,
        max_tokens: int = 512,
        max_retries: int = 8,
    ) -> str:
        """Gửi câu lệnh tới OpenRouter và trả về text phản hồi (hoặc fallback)."""
        if not self.active:
            return "[Fallback: no OPENROUTER_API_KEY]"

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }

        for attempt in range(1, max_retries + 1):
            try:
                response = requests.post(
                    config.OPENROUTER_URL, headers=self._headers(), json=payload, timeout=45
                )
                if response.status_code == 200:
                    self._requests += 1
                    data = response.json()
                    return str(data["choices"][0]["message"]["content"])
                if response.status_code in (401, 402):
                    print(f"  [LLM] Lỗi {response.status_code} (key/quota) - fallback rule-based.")
                    return "[Fallback: LLM auth/quota error]"
                if response.status_code == 429:
                    wait = min(2 ** attempt, 30)
                    print(f"  [LLM] Rate limit 429 - chờ {wait}s rồi thử lại ({attempt}/{max_retries})...")
                    time.sleep(wait)
                    continue
                print(
                    f"  [LLM] Lỗi {response.status_code} - thử lại ({attempt}/{max_retries})..."
                )
                time.sleep(2)
            except Exception as e:
                print(f"  [LLM] Lỗi kết nối: {e}")
                self._wait_for_network()

        return "[Fallback: exhausted retries]"

    def extract_json(self, text: str) -> Optional[Dict[str, Any]]:
        """Trích xuất object JSON từ chuỗi phản hồi của LLM (kể cả khi bọc markdown)."""
        if text is None or text.startswith("[Fallback"):
            return None
        text = text.strip()
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        return None
