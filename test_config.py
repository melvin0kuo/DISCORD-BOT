import os
from dotenv import load_dotenv

# 載入 .env 文件
load_dotenv()

# 打印模型名稱
print(f"LOCAL_MODEL_NAME 環境變量: {os.getenv('LOCAL_MODEL_NAME')}")

# 如果有 config.py，也導入它
try:
    import config
    print(f"config.py 中的 LOCAL_MODEL_NAME: {config.LOCAL_MODEL_NAME}")
except ImportError:
    print("無法導入 config.py")