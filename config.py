import os
from dotenv import load_dotenv

# 使用絕對路徑載入 .env
dotenv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
load_dotenv(dotenv_path)

# Discord 設定
TOKEN = os.getenv('DISCORD_TOKEN')
PREFIX = '!'

# 圖片生成 API 設定
IMAGE_API_KEY = os.getenv('IMAGE_API_KEY')
IMAGE_API_URL = "https://api.example.com/generate"  # 替換為實際的 API URL

# Lavalink 設定
LAVALINK_HOST = os.getenv('LAVALINK_HOST', '127.0.0.1')
LAVALINK_PORT = int(os.getenv('LAVALINK_PORT', 2333))
LAVALINK_PASSWORD = os.getenv('LAVALINK_PASSWORD', 'youshallnotpass')

# LLM 設定
DEFAULT_LLM_TYPE = os.getenv('DEFAULT_LLM_TYPE', 'local_python')
FALLBACK_LLM_TYPE = os.getenv('FALLBACK_LLM_TYPE', 'gemini')
ENABLE_FALLBACK = os.getenv('ENABLE_FALLBACK', 'True').lower() == 'true'
FALLBACK_TIMEOUT = int(os.getenv('FALLBACK_TIMEOUT', 30))

# Hugging Face 設定
HUGGINGFACE_TOKEN = os.getenv('HUGGINGFACE_TOKEN')

# OpenAI API 設定
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-3.5-turbo')

# Anthropic API 設定
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
ANTHROPIC_MODEL = os.getenv('ANTHROPIC_MODEL', 'claude-3-sonnet-20240229')

# Gemini API 設定
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-1.0-pro')

# 本地 LLM API 設定
LOCAL_LLM_URL = os.getenv('LOCAL_LLM_URL', 'http://localhost:8000/v1')
LOCAL_LLM_MODEL = os.getenv('LOCAL_LLM_MODEL', 'llama3')

# 本地 Python LLM 設定
LOCAL_MODEL_NAME = os.getenv('LOCAL_MODEL_NAME', 'mistralai/Mixtral-8x7B-Instruct-v0.1')
LOCAL_MODEL_CACHE_DIR = os.getenv('LOCAL_MODEL_CACHE_DIR', './models')

# 本地 GGUF 模型設定
LOCAL_GGUF_MODEL_PATH = os.getenv('LOCAL_GGUF_MODEL_PATH', "./models/mistralai_Mistral-Small-3.1-24B-Instruct-2503-Q6_K_L.gguf")
LOCAL_GGUF_CONTEXT_LENGTH = int(os.getenv('LOCAL_GGUF_CONTEXT_LENGTH', 4096))
LOCAL_GGUF_GPU_LAYERS = int(os.getenv('LOCAL_GGUF_GPU_LAYERS', -1))
LOCAL_GGUF_BATCH_SIZE = int(os.getenv('LOCAL_GGUF_BATCH_SIZE', 512))

# 硬體優化設定
LOCAL_MODEL_DEVICE = os.getenv('LOCAL_MODEL_DEVICE', 'cuda')
LOCAL_MODEL_DTYPE = os.getenv('LOCAL_MODEL_DTYPE', 'bfloat16')
LOCAL_MODEL_USE_FLASH_ATTN = os.getenv('LOCAL_MODEL_USE_FLASH_ATTN', 'True').lower() == 'true'
LOCAL_MODEL_QUANTIZATION = os.getenv('LOCAL_MODEL_QUANTIZATION', 'auto')

# 模型上下文長度
MODEL_CONTEXT_LENGTH = int(os.getenv('MODEL_CONTEXT_LENGTH', 4096))

# 生成參數
LOCAL_MODEL_MAX_NEW_TOKENS = int(os.getenv('LOCAL_MODEL_MAX_NEW_TOKENS', 512))
LOCAL_MODEL_TEMPERATURE = float(os.getenv('LOCAL_MODEL_TEMPERATURE', 0.7))
LOCAL_MODEL_TOP_P = float(os.getenv('LOCAL_MODEL_TOP_P', 0.9))
LOCAL_MODEL_REPETITION_PENALTY = float(os.getenv('LOCAL_MODEL_REPETITION_PENALTY', 1.1))

# LLM 系統提示詞
LLM_SYSTEM_PROMPT = os.getenv('LLM_SYSTEM_PROMPT', 
                             '你是一個友善、有幫助的 Discord 機器人助手。你的名字是 {bot_name}。請提供簡潔、有用的回答。如果你不知道答案，請誠實地說出來。')

# LLM 對話記憶設定
MAX_HISTORY_LENGTH = int(os.getenv('MAX_HISTORY_LENGTH', 10))

# 效能監控設定
ENABLE_PERFORMANCE_LOGGING = os.getenv('ENABLE_PERFORMANCE_LOGGING', 'True').lower() == 'true'
