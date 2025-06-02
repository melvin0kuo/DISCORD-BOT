from transformers import AutoModelForCausalLM
import os

# 載入模型
model_name = "mistralai/Mixtral-8x7B-Instruct-v0.1"
model = AutoModelForCausalLM.from_pretrained(model_name)

# 印出快取位置
print("模型快取位置:")
for name, param in model.state_dict().items():
    if hasattr(param, "filename"):
        print(f"{name}: {param.filename}")

# 或者印出 Hugging Face 的預設快取目錄
from huggingface_hub import constants
print(f"預設快取目錄: {constants.HF_HUB_CACHE}")
