"""
JSON 解析工具 - 从模型输出中提取 JSON
"""

import json
import re


def parse_json_output(output):
    match = re.search(r'```json\s*(.*?)\s*```', output, re.DOTALL)
    if match:
        json_str = match.group(1)
        json_str = json_str.replace('\n', '').replace('\r', '').strip()
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass
    return None
