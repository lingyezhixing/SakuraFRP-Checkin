import base64
import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


class AIService:

    def __init__(self):
        self.api_key = os.getenv("LLM_API_KEY", "")
        self.base_url = os.getenv("LLM_BASE_URL", "http://127.0.0.1:8080/v1")
        self.model_vision = os.getenv("LLM_MODEL_VISION", "Qwen3.5-2B")

        if not self.api_key:
            raise ValueError("LLM_API_KEY not found")

        self.client = OpenAI(base_url=self.base_url, api_key=self.api_key)
        self.vision_params = {
            "temperature": 0.7, "top_p": 0.8, "extra_body": {
                "top_k": 20, "min_p": 0.0,
                "presence_penalty": 1.5, "repetition_penalty": 1.0,
            }
        }

    def compare_images(self, tip_img_bytes, cell_img_bytes):
        tip_b64 = base64.b64encode(tip_img_bytes).decode("utf-8")
        cell_b64 = base64.b64encode(cell_img_bytes).decode("utf-8")
        prompt = "Determine if these two images show the same or similar object. Answer only: true or false"
        try:
            response = self.client.chat.completions.create(
                model=self.model_vision,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{tip_b64}"}},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{cell_b64}"}},
                        {"type": "text", "text": prompt}
                    ]
                }],
                **self.vision_params
            )
            res = response.choices[0].message.content.strip()
            print(f"[AI] compare: {res}")
            return "true" in res.lower()
        except Exception as e:
            print(f"[ERROR] AI compare call failed: {e}")
            return False
