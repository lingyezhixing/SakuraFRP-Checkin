import base64
import json
import re
import os
from dotenv import load_dotenv
from openai import OpenAI

# 加载环境变量
load_dotenv()

class AIService:
    """AI服务类，封装所有AI调用逻辑"""

    def __init__(self):
        """初始化AI服务，从环境变量读取配置"""
        self.api_key = os.getenv("LLM_API_KEY", "")
        self.base_url = os.getenv("LLM_BASE_URL", "http://127.0.0.1:8080/v1")
        self.model_vision = os.getenv("LLM_MODEL_VISION", "Qwen3.5-2B")
        self.model_text = os.getenv("LLM_MODEL_TEXT", "Qwen3.5-2B")

        if not self.api_key:
            raise ValueError("未找到LLM_API_KEY环境变量，请在.env文件中配置")

        self.client = OpenAI(base_url=self.base_url, api_key=self.api_key)

        self.text_params = {
            "temperature": 1.0, "top_p": 1.0, "extra_body": {
                "top_k": 20, "min_p": 0.0,
                "presence_penalty": 2.0, "repetition_penalty": 1.0,
            }
        }
        self.vision_params = {
            "temperature": 0.7, "top_p": 0.8, "extra_body": {
                "top_k": 20, "min_p": 0.0,
                "presence_penalty": 1.5, "repetition_penalty": 1.0,
            }
        }

    def safe_parse_json(self, text):
        """强力解析 AI 返回的 JSON 列表"""
        try:
            match = re.search(r'\[.*\]', text, re.DOTALL)
            if match:
                return json.loads(match.group())
            return json.loads(text)
        except Exception:
            return None

    def call_vision(self, image_bytes, prompt):
        """调用多模态模型"""
        base64_data = base64.b64encode(image_bytes).decode('utf-8')
        try:
            response = self.client.chat.completions.create(
                model=self.model_vision,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_data}"}}
                    ]
                }],
                **self.vision_params
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"[ERROR] AI API 调用失败: {e}")
            return ""

    def identify_captcha_row(self, row_img_bytes, row_index):
        """分行识别逻辑"""
        prompt = "这是验证码的一行图片，包含3个格子。请从左到右识别这3个格子的物体名称，只返回一个 JSON 字符串数组，例如：[\"猫\", \"狗\", \"汽车\"]。不要有任何解释文字。"
        res = self.call_vision(row_img_bytes, prompt)
        print(f"[AI] 第 {row_index} 行识别结果: {res}")

        parsed = self.safe_parse_json(res)
        if parsed and isinstance(parsed, list):
            while len(parsed) < 3:
                parsed.append("未知")
            return parsed[:3]
        return ["未知", "未知", "未知"]

    def semantic_match(self, target, descriptions):
        """语义裁决逻辑"""
        items_text = "\n".join([f"{i+1}. {d}" for i, d in enumerate(descriptions)])
        prompt = f"题目是：找出图片中所有的【{target}】。\n当前 9 个格子的识别结果如下：\n{items_text}\n请根据描述，判断哪些序号（1-9）最符合题目要求？\n返回格式：只返回 JSON 数组，如 [1, 3, 5]。如果没有符合的，返回空数组 []。"

        print(f"[Debug] 正在进行语义裁决，描述列表：\n{items_text}")

        try:
            response = self.client.chat.completions.create(
                model=self.model_text,
                messages=[{"role": "user", "content": prompt}],
                **self.text_params
            )
            content = response.choices[0].message.content.strip()
            print(f"[AI] 语义裁决原始输出: {content}")
            parsed = self.safe_parse_json(content)
            return parsed if isinstance(parsed, list) else []
        except Exception as e:
            print(f"[ERROR] 语义匹配失败: {e}")
            return []

