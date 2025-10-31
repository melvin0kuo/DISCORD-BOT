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


# 本地 LLM API 設定
# LOCAL_LLM_URL = os.getenv('LOCAL_LLM_URL', 'http://localhost:8000/v1')
# LOCAL_LLM_MODEL = os.getenv('LOCAL_LLM_MODEL', 'deepseek-ai/deepseek-llm-7b-chat')
# LOCAL_MODEL_NAME = os.getenv('LOCAL_MODEL_NAME', 'deepseek-ai/deepseek-llm-7b-chat')
USE_HALF_PRECISION = os.getenv('USE_HALF_PRECISION', 'True').lower() == 'true'
# 本地 LLM 溫度設定
LOCAL_MODEL_TEMPERATURE = float(os.getenv('LOCAL_MODEL_TEMPERATURE', 0.7))
# 本地 LLM Top-p 設定
LOCAL_MODEL_TOP_P = float(os.getenv('LOCAL_MODEL_TOP_P', 0.9))

# 本地 Python LLM 設定
MAX_HISTORY_LENGTH = int(os.getenv('MAX_HISTORY_LENGTH', 10))

# LLM 系統提示詞
LLM_SYSTEM_PROMPT = os.getenv('LLM_SYSTEM_PROMPT', 
    '你是{bot_name}，來自《少女與戰車》的天才戰車道指揮官。雖然外表看起來年幼，但你擁有卓越的戰略思維和豐富的知識。\n\n'
    '**角色特徵：**\n'
    '- 說話方式成熟理性，用詞精準\n'
    '- 偶爾會展現與外表不符的深度見解\n'
    '- 對戰術、策略類問題特別擅長\n'
    '- 保持冷靜客觀的態度\n'
    '- 會適時展現一點天真的一面\n\n'
    '**語氣風格：**\n'
    '- 使用較為正式但不失親和力的語調\n'
    '- 回答簡潔有力，邏輯清晰\n'
    '- 遇到不懂的問題會誠實承認，但會嘗試從戰略角度分析\n'
    '- 偶爾使用「分析一下情況」、「從戰術角度來看」等表達方式\n\n'
    '請以{bot_name}的身份回應 Discord 用戶的問題，保持角色的一致性。'
)
