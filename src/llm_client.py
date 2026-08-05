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
                    elif line.startswith("LLM_MODEL=") and not model:
                        model = line.split("=", 1)[1].strip().strip('"').strip("'")

        self.model = model or os.getenv("LLM_MODEL", DEFAULT_MODEL_NAME)

    def chat_completion(
        self,
        prompt: str,
        system_prompt: str = "You are a helpful e-commerce dispute resolution assistant.",
        temperature: float = 0.1,
        max_tokens: int = 500,
    ) -> str:
        """
        Gửi câu lệnh tới OpenRouter LLM và trả về chuỗi phản hồi text.
        Nếu không có API key hoặc gặp lỗi mạng, sẽ fallback an toàn.
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

        try:
            response = requests.post(
                OPENROUTER_URL, headers=headers, json=payload, timeout=15
            )
            if response.status_code == 200:
                data = response.json()
                return data["choices"][0]["message"]["content"]
            else:
                err_msg = f"❌ LỖI LLM API (Status Code {response.status_code}): {response.text}"
                print(f"\n{err_msg}")
                raise RuntimeError(err_msg)
        except Exception as e:
            if isinstance(e, RuntimeError):
                raise e
            err_msg = f"❌ LỖI KẾT NỐI MẠNG ĐẾN LLM API: {str(e)}"
            print(f"\n{err_msg}")
            raise RuntimeError(err_msg)
