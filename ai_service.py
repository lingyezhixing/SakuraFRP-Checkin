import base64
import os
from openai import OpenAI


class AIService:

    def __init__(self):
        self.api_key = os.getenv("LLM_API_KEY")
        self.base_url = os.getenv("LLM_BASE_URL")
        self.model = os.getenv("LLM_MODEL")

        self.client = OpenAI(base_url=self.base_url, api_key=self.api_key)
        self.vision_params = {
            "temperature": 0.7, "top_p": 0.8, "extra_body": {
                "top_k": 20, "min_p": 0.0,
                "presence_penalty": 1.5, "repetition_penalty": 1.0,
                "chat_template_kwargs": {"enable_thinking": False},
            }
        }

    def call_vision(self, image_bytes, prompt):
        base64_data = base64.b64encode(image_bytes).decode("utf-8")
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_data}"}},
                        {"type": "text", "text": prompt}
                    ]
                }],
                **self.vision_params
            )
            content = response.choices[0].message.content.strip()
            print(f"[AI] raw vision response: {content}")
            return content
        except Exception as e:
            print(f"[ERROR] AI API call failed: {e}")
            return ""

    def classify_cell(self, cell_img_bytes, target_object):
        prompt = f'图片中是否有【{target_object}】？只回答：是 或 否'
        res = self.call_vision(cell_img_bytes, prompt)
        print(f"[AI] classify target={target_object}: {res}")
        return "是" in res
