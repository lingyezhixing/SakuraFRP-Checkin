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

    def _extract_bracket(self, text):
        """提取第一个 [...] 内容"""
        match = re.search(r'\[.*?\]', text, re.DOTALL)
        return match.group() if match else None

    def safe_parse_list(self, text):
        """解析字符串列表，兼容带引号/不带引号/换行等格式"""
        bracket = self._extract_bracket(text)
        if not bracket:
            return None
        try:
            return json.loads(bracket)
        except json.JSONDecodeError:
            # 修复不带引号：[猫, 狗, 汽车] → ['猫', '狗', '汽车']
            items = re.findall(r'[^,\[\]\s"\']+', bracket)
            return items if items else None

    def safe_parse_ints(self, text):
        """解析整数列表"""
        bracket = self._extract_bracket(text)
        if not bracket:
            return None
        numbers = re.findall(r'\d+', bracket)
        return [int(n) for n in numbers] if numbers else None

    def call_vision(self, image_bytes, prompt):
        """调用多模态模型"""
        base64_data = base64.b64encode(image_bytes).decode('utf-8')
        try:
            response = self.client.chat.completions.create(
                model=self.model_vision,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_data}"}},
                        {"type": "text", "text": prompt}
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
        prompt = """识别图中3个物品，从左到右依次输出名称。严格按此格式输出，禁止添加任何其他文字：["名称1","名称2","名称3"]"""
        res = self.call_vision(row_img_bytes, prompt)
        print(f"[AI] 第 {row_index} 行识别结果: {res}")

        parsed = self.safe_parse_list(res)
        if parsed and isinstance(parsed, list) and len(parsed) > 0:
            while len(parsed) < 3:
                parsed.append("未知")
            return parsed[:3]
        return ["未知", "未知", "未知"]

    def semantic_match(self, target, descriptions):
        """语义裁决逻辑"""
        items_text = "\n".join([f"{i+1}. {d}" for i, d in enumerate(descriptions)])
        prompt = f"""找出所有【{target}】的编号。物品列表：{items_text}，从左向右依次编号为1~9。严格按照以下示例格式输出编号数组，禁止添加其他文字：[1, 3, 5]"""

        print(f"[Debug] 正在进行语义裁决，描述列表：\n{items_text}")

        try:
            response = self.client.chat.completions.create(
                model=self.model_text,
                messages=[{"role": "user", "content": prompt}],
                **self.text_params
            )
            content = response.choices[0].message.content.strip()
            print(f"[AI] 语义裁决原始输出: {content}")
            parsed = self.safe_parse_ints(content)
            return parsed if isinstance(parsed, list) else []
        except Exception as e:
            print(f"[ERROR] 语义匹配失败: {e}")
            return []
