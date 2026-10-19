import os
from dotenv import load_dotenv

# 使用絕對路徑載入 .env
dotenv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
load_dotenv(dotenv_path)

# --- 開發者設定 ---
# 開發模式開關，True 會啟用熱重載等功能
DEV_MODE = os.getenv('DEV_MODE', 'True').lower() == 'true'

# Discord 設定
TOKEN = os.getenv('DISCORD_TOKEN')
print(f"TOKEN 載入狀態: {'✅ 已載入' if TOKEN else '❌ 未載入'}")
PREFIX = '!'

# 圖片生成 API 設定
IMAGE_API_KEY = os.getenv('IMAGE_API_KEY')
IMAGE_API_URL = "https://api.example.com/generate"  # 替換為實際的 API URL

# LLM 設定
DEFAULT_LLM_TYPE = os.getenv('DEFAULT_LLM_TYPE', 'gemini')
FALLBACK_LLM_TYPE = os.getenv('FALLBACK_LLM_TYPE', 'gemini')
ENABLE_FALLBACK = os.getenv('ENABLE_FALLBACK', 'True').lower() == 'true'
FALLBACK_TIMEOUT = int(os.getenv('FALLBACK_TIMEOUT', 30))

# 性能監控開關
ENABLE_PERFORMANCE_LOGGING = os.getenv('ENABLE_PERFORMANCE_LOGGING', 'False').lower() == 'true'
LOCAL_MODEL_DEVICE = os.getenv('LOCAL_MODEL_DEVICE', 'cpu')

# Hugging Face 設定
# HUGGINGFACE_TOKEN = os.getenv('HUGGINGFACE_TOKEN')

# OpenAI API 設定
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-3.5-turbo')

# Anthropic API 設定
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
ANTHROPIC_MODEL = os.getenv('ANTHROPIC_MODEL', 'claude-3-sonnet-20240229')

# Gemini API 設定
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-1.0-pro')
# Gemini 生成參數
GEMINI_TEMPERATURE = float(os.getenv('GEMINI_TEMPERATURE', '0.7'))
GEMINI_TOP_P = float(os.getenv('GEMINI_TOP_P', '0.9'))
GEMINI_MAX_OUTPUT_TOKENS = int(os.getenv('GEMINI_MAX_OUTPUT_TOKENS', '2048'))
LLM_SYSTEM_PROMPT = """你是{bot_name}，《少女與戰車》中戰車道名門「島田流」的千金大小姐。你是一位13歲就跳級讀大學的天才少女，擁有超越同齡人的智慧和成熟度。作為島田家的千金，你具有高貴的氣質，但同時保持著少女的純真。你說話時會展現出與年齡不符的成熟和理性，偶爾也會流露出符合實際年齡的天真一面。在戰車道方面，你承繼了島田流的傳統，對戰術和策略有著深刻的理解。請以島田愛里壽的身份和語調來回應用戶。回應長度控制在100-200字，提供適度詳細的回應。"""
MAX_HISTORY_LENGTH = int(os.getenv('MAX_HISTORY_LENGTH', '20'))
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')


# LM Studio 本地模型備援設定（Gemini 429 時自動切換）
LMSTUDIO_API_URL = os.getenv('LMSTUDIO_API_URL', 'http://localhost:1234')
LMSTUDIO_API_KEY = os.getenv('LMSTUDIO_API_KEY', '')
LMSTUDIO_MODEL   = os.getenv('LMSTUDIO_MODEL', 'local-model')

# 本地 LLM API 設定（舊版，保留相容性）
USE_HALF_PRECISION = os.getenv('USE_HALF_PRECISION', 'True').lower() == 'true'
# 本地 LLM 溫度設定
LOCAL_MODEL_TEMPERATURE = float(os.getenv('LOCAL_MODEL_TEMPERATURE', 0.7))
# 本地 LLM Top-p 設定
LOCAL_MODEL_TOP_P = float(os.getenv('LOCAL_MODEL_TOP_P', 0.9))

# 本地 Python LLM 設定
MAX_HISTORY_LENGTH = int(os.getenv('MAX_HISTORY_LENGTH', 15))

# LLM 系統提示詞
LLM_SYSTEM_PROMPT = os.getenv('LLM_SYSTEM_PROMPT',
    '你是呱呱，一隻精通程式設計與電機工程的專家鴨。'
    '外表是隻小黃鴨，但擁有深厚的技術功底：精通 Python、C++、Rust 等語言，熟悉嵌入式、電路設計與微控制器。\n\n'
    '【Discord 回應格式規範】：\n'
    '1. 雙換行原則：段落、標題、清單之間務必使用 **兩次換行** (`\\n\\n`)，這是確保 Discord 不會將文字縮成一團的唯一方式。\n'
    '2. 善用 Markdown：重要名詞用 **粗體**。標題使用 `### 標題`（前面也要空一行）。\n'
    '3. 強制折行：若需在同一段落內換行，請在行末加上兩個空格再換行。\n'
    '4. 程式碼區塊：務必使用 ```語言名稱\\n代碼\\n```，並確保代碼縮進正確。\n'
    '5. 結構清晰：先給結論，再用分點列表 (1. 2. 3.) 解釋步驟，避免長篇大論。\n\n'
    '回答技術問題時風格專業、有條理；閒聊時句尾點綴「呱」。'
    '技術回答務必完整；閒聊控制在 80 字內。'
    '如果用戶用其他語言，請用相同語言回應。'
)
