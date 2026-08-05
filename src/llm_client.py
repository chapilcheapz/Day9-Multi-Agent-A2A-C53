"""
LLM Client - Giao tiếp với LLM qua OpenRouter API.
Hỗ trợ model nvidia/nemotron-nano-9b-v2:free (<= 10B parameters).
"""

import os
import requests
from typing import Optional, Dict, Any

DEFAULT_MODEL_NAME = "nvidia/nemotron-nano-9b-v2:free"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


class LLMClient:
    """Client kết nối tới OpenRouter LLM API."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY", "")
        if not self.api_key and os.path.exists(".env"):
            with open(".env", "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("OPENROUTER_API_KEY="):
                        self.api_key = line.split("=", 1)[1].strip().strip('"').strip("'")

        self.model = model or DEFAULT_MODEL_NAME

    def _wait_for_network(self):
        """Tạm dừng chương trình và chờ kết nối mạng phục hồi (kiểm tra mỗi 5s)."""
        import time
        print("\n⚠️ LLM API: Mất kết nối mạng hoặc Timeout! Đang tạm dừng chờ kết nối lại (kiểm tra mỗi 5s)...")
        while True:
            try:
                res = requests.get("https://openrouter.ai/api/v1/models", timeout=5)
                if res.status_code == 200:
                    print("  ✓ Đã có kết nối mạng trở lại! Đang tiếp tục xử lý...")
                    time.sleep(1)
                    break
            except Exception:
                pass
            time.sleep(5)

    def chat_completion(
        self,
        prompt: str,
        system_prompt: str = "You are a helpful e-commerce dispute resolution assistant.",
        temperature: float = 0.1,
        max_tokens: int = 500,
    ) -> str:
        """
        Gửi câu lệnh tới OpenRouter LLM và trả về chuỗi phản hồi text.
        Nếu gặp lỗi mạng/timeout, sẽ tạm dừng chờ có mạng trở lại và thử lại.
        """
        if not self.api_key:
            return f"[Fallback: No OPENROUTER_API_KEY found. Prompt was: {prompt[:50]}...]"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/chapilcheapz/K4-Day9-Multi-Agent-A2A",
            "X-Title": "K4 Multi-Agent System",
        }

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

        import time
        max_retries = 10
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    OPENROUTER_URL, headers=headers, json=payload, timeout=30
                )
                if response.status_code == 200:
                    data = response.json()
                    return data["choices"][0]["message"]["content"]
                elif response.status_code in [401, 402, 429]:
                    err_msg = f"⚠️ LLM API Limit/Quota (Status Code {response.status_code}), using fallback."
                    print(f"\n{err_msg}")
                    return f"[Fallback: {err_msg}]"
                else:
                    print(f"\n⚠️ Lỗi LLM API {response.status_code}, đang thử lại ({attempt + 1}/{max_retries})...")
                    time.sleep(2)
            except Exception as e:
                print(f"\n⚠️ Lỗi kết nối mạng: {e}")
                self._wait_for_network()

        return "[Fallback: Exhausted retries due to network or LLM server issue]"
