import os
import sys
import torch
import logging
import argparse
from dotenv import load_dotenv

# 設定日誌
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ModelDiagnostics")

def check_environment():
  """檢查環境設置"""
  logger.info("=== 環境檢查 ===")
  
  # 檢查 Python 版本
  logger.info(f"Python 版本: {sys.version}")
  
  # 檢查 CUDA 可用性
  cuda_available = torch.cuda.is_available()
  logger.info(f"CUDA 可用: {cuda_available}")
  
  if cuda_available:
      logger.info(f"CUDA 版本: {torch.version.cuda}")
      logger.info(f"GPU 數量: {torch.cuda.device_count()}")
      for i in range(torch.cuda.device_count()):
          logger.info(f"GPU {i}: {torch.cuda.get_device_name(i)}")
          # 獲取顯存信息
          try:
              free_mem, total_mem = torch.cuda.mem_get_info(i)
              logger.info(f"GPU {i} 顯存: {free_mem / 1024**3:.2f}GB 可用 / {total_mem / 1024**3:.2f}GB 總計")
          except:
              logger.info(f"無法獲取 GPU {i} 的顯存信息")
  
  # 檢查環境變數
  load_dotenv()
  logger.info(f"DEFAULT_LLM_TYPE: {os.getenv('DEFAULT_LLM_TYPE', 'Not set')}")
  
  # 根據 LLM 類型檢查相關配置
  llm_type = os.getenv('DEFAULT_LLM_TYPE', '').lower()
  if llm_type == 'local_gguf':
      logger.info("檢查 GGUF 模型配置...")
      model_path = os.getenv('LOCAL_GGUF_MODEL_PATH', '')
      logger.info(f"GGUF 模型路徑: {model_path}")
      if not os.path.exists(model_path):
          logger.error(f"模型文件不存在: {model_path}")
      else:
          logger.info(f"模型文件存在，大小: {os.path.getsize(model_path) / 1024**2:.2f}MB")
      
      # 檢查 llama-cpp-python 是否安裝
      try:
          import llama_cpp
          logger.info(f"llama-cpp-python 版本: {llama_cpp.__version__}")
      except ImportError:
          logger.error("llama-cpp-python 未安裝")
  
  elif llm_type == 'local_python':
      logger.info("檢查 Transformers 模型配置...")
      model_name = os.getenv('LOCAL_MODEL_NAME', '')
      cache_dir = os.getenv('LOCAL_MODEL_CACHE_DIR', '')
      logger.info(f"模型名稱: {model_name}")
      logger.info(f"模型緩存目錄: {cache_dir}")
      
      # 檢查 transformers 是否安裝
      try:
          import transformers
          logger.info(f"transformers 版本: {transformers.__version__}")
      except ImportError:
          logger.error("transformers 未安裝")

def test_gguf_model():
  """測試 GGUF 模型載入"""
  logger.info("=== GGUF 模型測試 ===")
  
  load_dotenv()
  model_path = os.getenv('LOCAL_GGUF_MODEL_PATH', '')
  if not model_path:
      logger.error("LOCAL_GGUF_MODEL_PATH 未設置")
      return
  
  if not os.path.exists(model_path):
      logger.error(f"模型文件不存在: {model_path}")
      return
  
  try:
      from llama_cpp import Llama
      
      # 獲取配置
      context_length = int(os.getenv('LOCAL_GGUF_CONTEXT_LENGTH', '4096'))
      batch_size = int(os.getenv('LOCAL_GGUF_BATCH_SIZE', '512'))
      gpu_layers = int(os.getenv('LOCAL_GGUF_GPU_LAYERS', '-1'))
      
      logger.info(f"正在載入模型: {model_path}")
      logger.info(f"上下文長度: {context_length}")
      logger.info(f"批處理大小: {batch_size}")
      logger.info(f"GPU 層數: {gpu_layers}")
      
      # 載入模型
      model = Llama(
          model_path=model_path,
          n_ctx=context_length,
          n_batch=batch_size,
          n_gpu_layers=gpu_layers
      )
      
      logger.info("模型載入成功!")
      
      # 簡單測試
      prompt = "你好，請介紹一下你自己。"
      logger.info(f"測試提示: {prompt}")
      
      output = model(prompt, max_tokens=100)
      logger.info(f"模型輸出: {output['choices'][0]['text']}")
      
  except Exception as e:
      logger.error(f"載入或使用 GGUF 模型時出錯: {str(e)}")

def test_transformers_model():
  """測試 Transformers 模型載入"""
  logger.info("=== Transformers 模型測試 ===")
  
  load_dotenv()
  model_name = os.getenv('LOCAL_MODEL_NAME', '')
  if not model_name:
      logger.error("LOCAL_MODEL_NAME 未設置")
      return
  
  try:
      import transformers
      from transformers import AutoModelForCausalLM, AutoTokenizer
      
      # 獲取配置
      cache_dir = os.getenv('LOCAL_MODEL_CACHE_DIR', './model_cache')
      device = os.getenv('LOCAL_MODEL_DEVICE', 'cuda' if torch.cuda.is_available() else 'cpu')
      quantization = os.getenv('LOCAL_MODEL_QUANTIZATION', 'auto')
      dtype_str = os.getenv('LOCAL_MODEL_DTYPE', 'auto')
      
      logger.info(f"正在載入模型: {model_name}")
      logger.info(f"緩存目錄: {cache_dir}")
      logger.info(f"設備: {device}")
      logger.info(f"量化: {quantization}")
      logger.info(f"數據類型: {dtype_str}")
      
      # 確定數據類型
      if dtype_str == 'auto':
          dtype = torch.float16 if device == 'cuda' else torch.float32
      elif dtype_str == 'float16':
          dtype = torch.float16
      elif dtype_str == 'bfloat16':
          dtype = torch.bfloat16
      else:
          dtype = torch.float32
      
      logger.info(f"使用數據類型: {dtype}")
      
      # 載入分詞器
      tokenizer = AutoTokenizer.from_pretrained(model_name, cache_dir=cache_dir)
      
      # 載入模型
      if quantization == '4bit':
          logger.info("使用 4-bit 量化")
          from transformers import BitsAndBytesConfig
          quantization_config = BitsAndBytesConfig(
              load_in_4bit=True,
              bnb_4bit_compute_dtype=dtype
          )
          model = AutoModelForCausalLM.from_pretrained(
              model_name,
              cache_dir=cache_dir,
              device_map="auto",
              quantization_config=quantization_config
          )
      elif quantization == '8bit':
          logger.info("使用 8-bit 量化")
          model = AutoModelForCausalLM.from_pretrained(
              model_name,
              cache_dir=cache_dir,
              device_map="auto",
              load_in_8bit=True
          )
      else:
          logger.info("不使用量化")
          model = AutoModelForCausalLM.from_pretrained(
              model_name,
              cache_dir=cache_dir,
              device_map="auto",
              torch_dtype=dtype
          )
      
      logger.info("模型載入成功!")
      
      # 簡單測試
      prompt = "你好，請介紹一下你自己。"
      logger.info(f"測試提示: {prompt}")
      
      inputs = tokenizer(prompt, return_tensors="pt").to(device)
      outputs = model.generate(**inputs, max_new_tokens=100)
      response = tokenizer.decode(outputs[0], skip_special_tokens=True)
      
      logger.info(f"模型輸出: {response}")
      
  except Exception as e:
      logger.error(f"載入或使用 Transformers 模型時出錯: {str(e)}")

def main():
  parser = argparse.ArgumentParser(description="AI 模型診斷工具")
  parser.add_argument("--check", action="store_true", help="檢查環境設置")
  parser.add_argument("--test-gguf", action="store_true", help="測試 GGUF 模型")
  parser.add_argument("--test-transformers", action="store_true", help="測試 Transformers 模型")
  
  args = parser.parse_args()
  
  if args.check or (not args.test_gguf and not args.test_transformers):
      check_environment()
  
  if args.test_gguf:
      test_gguf_model()
  
  if args.test_transformers:
      test_transformers_model()

if __name__ == "__main__":
  main()