import json
import requests
import aiohttp
import asyncio
import time
import concurrent.futures
import sys
from typing import List, Dict, Any, Optional, Generator, Union, Tuple
import config
import logging
from utils.model_loader import ModelLoader
import google.generativeai as genai
from openai import AsyncOpenAI
import anthropic
import os
import torch

# 設定日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("LLMHandler")

class LLMHandler:
    def __init__(self, bot_name: str):
        self.bot_name = bot_name
        self.current_llm_type = config.DEFAULT_LLM_TYPE
        self.system_prompt = config.LLM_SYSTEM_PROMPT.format(bot_name=bot_name)
        self.conversation_history = {}  # 用戶 ID -> 對話歷史
        self.max_history_length = config.MAX_HISTORY_LENGTH
        
        # 初始化各種 LLM 客戶端
        self._init_clients()
        
        # 如果使用本地 Python 模型，初始化模型載入器
        if self.current_llm_type == "local_python":
            self.model_loader = ModelLoader.get_instance()
            # 預先載入模型
            asyncio.create_task(self._preload_model())
        
        # 如果使用 GGUF 模型，初始化 GGUF 模型
        if self.current_llm_type == "local_gguf":
            # 預先載入模型
            asyncio.create_task(self._preload_gguf_model())
    
    def _init_clients(self):
        """初始化各種 LLM 客戶端"""
        # 初始化 OpenAI 客戶端
        if config.OPENAI_API_KEY:
            self.openai_client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
        else:
            self.openai_client = None
        
        # 初始化 Anthropic 客戶端
        if config.ANTHROPIC_API_KEY:
            self.anthropic_client = anthropic.AsyncAnthropic(api_key=config.ANTHROPIC_API_KEY)
        else:
            self.anthropic_client = None
        
        # 初始化 Gemini 客戶端
        if config.GEMINI_API_KEY:
            genai.configure(api_key=config.GEMINI_API_KEY)
            self.gemini_client = genai
        else:
            self.gemini_client = None
        
        # 初始化 GGUF 模型相關屬性
        self.gguf_model = None
        self.gguf_model_loaded = False
        self.gguf_model_loading = False
    
    async def _preload_model(self):
        """預先載入模型（非阻塞）"""
        if self.current_llm_type == "local_python":
            try:
                self.model_loader.load_model()
                logger.info("模型預載入完成")
            except Exception as e:
                logger.error(f"模型預載入失敗：{e}")
    
    async def _preload_gguf_model(self):
        """預先載入 GGUF 模型（非阻塞）"""
        if self.current_llm_type == "local_gguf":
            try:
                await self._load_gguf_model()
                logger.info("GGUF 模型預載入完成")
            except Exception as e:
                logger.error(f"GGUF 模型預載入失敗：{e}")
    
    async def _load_gguf_model(self) -> bool:
        """
        載入 GGUF 格式的本地模型
        
        返回:
            bool: 是否成功載入模型
        """
        if self.gguf_model_loaded:
            logger.info("GGUF 模型已經載入")
            return True
        
        if self.gguf_model_loading:
            logger.info("GGUF 模型正在載入中")
            return False
        
        self.gguf_model_loading = True
        logger.info(f"開始載入 GGUF 模型: {config.LOCAL_GGUF_MODEL_PATH}")
        
        try:
            # 檢查模型文件是否存在
            if not os.path.exists(config.LOCAL_GGUF_MODEL_PATH):
                logger.error(f"模型文件不存在: {config.LOCAL_GGUF_MODEL_PATH}")
                self.gguf_model_loading = False
                return False
            
            # 檢查是否已安裝 llama-cpp-python
            try:
                from llama_cpp import Llama
            except ImportError:
                logger.warning("未找到 llama-cpp-python，嘗試安裝...")
                import subprocess
                subprocess.run([sys.executable, "-m", "pip", "install", "llama-cpp-python"], check=True)
                from llama_cpp import Llama
            
            # 確定是否使用 GPU
            use_gpu = torch.cuda.is_available()
            
            # 載入模型參數
            model_params = {
                "model_path": config.LOCAL_GGUF_MODEL_PATH,
                "n_ctx": config.LOCAL_GGUF_CONTEXT_LENGTH,
                "n_batch": config.LOCAL_GGUF_BATCH_SIZE,
            }
            
            if use_gpu:
                logger.info("使用 GPU 加速 GGUF 模型")
                model_params["n_gpu_layers"] = config.LOCAL_GGUF_GPU_LAYERS
            
            # 使用執行器在另一個線程中載入模型
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(lambda: Llama(**model_params))
                self.gguf_model = future.result(timeout=120)  # 設置載入超時為 120 秒
            
            self.gguf_model_loaded = True
            self.gguf_model_loading = False
            logger.info("GGUF 模型載入成功")
            return True
            
        except Exception as e:
            logger.error(f"載入 GGUF 模型時發生錯誤: {str(e)}")
            self.gguf_model_loading = False
            return False
    
    def unload_gguf_model(self) -> None:
        """卸載 GGUF 模型以釋放記憶體"""
        if self.gguf_model_loaded and self.gguf_model is not None:
            logger.info("卸載 GGUF 模型以釋放記憶體")
            del self.gguf_model
            self.gguf_model = None
            self.gguf_model_loaded = False
            
            # 清理 CUDA 快取
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
    
    def _get_user_history(self, user_id: str) -> List[Dict[str, str]]:
        """獲取用戶的對話歷史"""
        if user_id not in self.conversation_history:
            self.conversation_history[user_id] = []
        return self.conversation_history[user_id]
    
    def add_to_history(self, user_id: str, role: str, content: str):
        """添加消息到用戶的對話歷史"""
        history = self._get_user_history(user_id)
        history.append({"role": role, "content": content})
        
        # 如果歷史記錄超過最大長度，移除最舊的消息
        while len(history) > self.max_history_length:
            history.pop(0)
    
    def clear_history(self, user_id: str):
        """清除用戶的對話歷史"""
        if user_id in self.conversation_history:
            self.conversation_history[user_id] = []
            return True
        return False
    
    def switch_model(self, model_type: str) -> bool:
        """切換到指定的模型類型"""
        valid_types = ["openai", "anthropic", "gemini", "local", "local_python", "local_gguf"]
        if model_type not in valid_types:
            return False
        
        # 檢查所選模型是否可用
        if model_type == "openai" and not config.OPENAI_API_KEY:
            return False
        elif model_type == "anthropic" and not config.ANTHROPIC_API_KEY:
            return False
        elif model_type == "gemini" and not config.GEMINI_API_KEY:
            return False
        elif model_type == "local_gguf" and not os.path.exists(config.LOCAL_GGUF_MODEL_PATH):
            return False
        
        # 切換模型
        self.current_llm_type = model_type
        logger.info(f"已切換到模型: {model_type}")
        
        # 如果切換到本地模型，確保模型已載入
        if model_type == "local_python":
            asyncio.create_task(self._preload_model())
        elif model_type == "local_gguf":
            asyncio.create_task(self._preload_gguf_model())
        
        return True
    
    def get_current_model_info(self) -> Dict[str, str]:
        """獲取當前模型信息"""
        model_info = {
            "type": self.current_llm_type,
        }
        
        if self.current_llm_type == "openai":
            model_info["name"] = config.OPENAI_MODEL
        elif self.current_llm_type == "anthropic":
            model_info["name"] = config.ANTHROPIC_MODEL
        elif self.current_llm_type == "gemini":
            model_info["name"] = config.GEMINI_MODEL
        elif self.current_llm_type == "local":
            model_info["name"] = config.LOCAL_LLM_MODEL
        elif self.current_llm_type == "local_python":
            model_info["name"] = config.LOCAL_MODEL_NAME
            # 如果模型已載入，添加更多信息
            if hasattr(self, 'model_loader') and self.model_loader.is_ready:
                gpu_info = self.model_loader.get_gpu_memory_info() if hasattr(self.model_loader, 'get_gpu_memory_info') else None
                if gpu_info and 0 in gpu_info:
                    model_info["gpu_usage"] = f"{gpu_info[0]['allocated']:.1f}GB / {gpu_info[0]['total']:.1f}GB"
                    model_info["gpu_util"] = f"{gpu_info[0].get('utilization', 'N/A')}%"
        elif self.current_llm_type == "local_gguf":
            model_info["name"] = os.path.basename(config.LOCAL_GGUF_MODEL_PATH)
            model_info["status"] = "已載入" if self.gguf_model_loaded else "未載入"
            
            # 如果使用 GPU，添加 GPU 信息
            if torch.cuda.is_available():
                allocated = torch.cuda.memory_allocated() / (1024 ** 3)  # 轉換為 GB
                total = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
                model_info["gpu_usage"] = f"{allocated:.1f}GB / {total:.1f}GB"
                
                # 嘗試獲取 GPU 利用率
                try:
                    import pynvml
                    pynvml.nvmlInit()
                    handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                    util = pynvml.nvmlDeviceGetUtilizationRates(handle)
                    model_info["gpu_util"] = f"{util.gpu}%"
                except:
                    model_info["gpu_util"] = "N/A"
        
        return model_info
    
    async def get_llm_response(self, user_id: str, message: str, stream: bool = False) -> Union[str, Generator[str, None, None]]:
        """獲取 LLM 回應，支援故障轉移"""
        # 添加用戶消息到歷史記錄
        self.add_to_history(user_id, "user", message)
        
        # 嘗試使用當前模型
        try:
            if stream:
                response_stream = await self._get_response_from_model(user_id, message, stream=True)
                return response_stream
            else:
                response = await self._get_response_from_model(user_id, message)
                # 添加助手回應到歷史記錄
                self.add_to_history(user_id, "assistant", response)
                return response
        except Exception as e:
            logger.error(f"使用 {self.current_llm_type} 模型時出錯: {e}")
            
            # 如果啟用了故障轉移且當前模型是本地模型
            if config.ENABLE_FALLBACK and self.current_llm_type in ["local_python", "local", "local_gguf"]:
                fallback_type = config.FALLBACK_LLM_TYPE
                logger.info(f"嘗試使用備用模型 {fallback_type}")
                
                # 暫時切換到備用模型
                original_type = self.current_llm_type
                self.current_llm_type = fallback_type
                
                try:
                    if stream:
                        response_stream = await self._get_response_from_model(user_id, message, stream=True)
                        # 恢復原始模型設置
                        self.current_llm_type = original_type
                        return response_stream
                    else:
                        response = await self._get_response_from_model(user_id, message)
                        # 添加助手回應到歷史記錄
                        self.add_to_history(user_id, "assistant", response)
                        # 恢復原始模型設置
                        self.current_llm_type = original_type
                        return f"[使用備用模型 {fallback_type}] {response}"
                except Exception as fallback_error:
                    # 恢復原始模型設置
                    self.current_llm_type = original_type
                    logger.error(f"備用模型 {fallback_type} 也失敗: {fallback_error}")
                    return f"主模型和備用模型均失敗。錯誤: {str(e)}"
            
            return f"獲取回應時出錯: {str(e)}"
    
    async def _get_response_from_model(self, user_id: str, message: str, stream: bool = False) -> Union[str, Generator[str, None, None]]:
        """從特定模型獲取回應"""
        history = self._get_user_history(user_id)
        
        if self.current_llm_type == "openai":
            return await self._get_openai_response(history, stream)
        elif self.current_llm_type == "anthropic":
            return await self._get_anthropic_response(history, stream)
        elif self.current_llm_type == "gemini":
            return await self._get_gemini_response(history, stream)
        elif self.current_llm_type == "local":
            return await self._get_local_api_response(history, stream)
        elif self.current_llm_type == "local_python":
            return await self._get_local_python_response(history, stream)
        elif self.current_llm_type == "local_gguf":
            return await self._get_local_gguf_response(history, stream)
        else:
            raise ValueError(f"不支援的 LLM 類型: {self.current_llm_type}")
    
    async def _get_openai_response(self, history: List[Dict[str, str]], stream: bool = False) -> Union[str, Generator[str, None, None]]:
        """從 OpenAI API 獲取回應"""
        if not self.openai_client:
            raise ValueError("OpenAI API 密鑰未設置")
        
        # 準備消息
        messages = [{"role": "system", "content": self.system_prompt}]
        for msg in history:
            messages.append({"role": msg["role"], "content": msg["content"]})
        
        if stream:
            response_stream = await self.openai_client.chat.completions.create(
                model=config.OPENAI_MODEL,
                messages=messages,
                temperature=config.LOCAL_MODEL_TEMPERATURE,
                stream=True
            )
            
            async def generate():
                collected_chunks = []
                async for chunk in response_stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        collected_chunks.append(content)
                        yield content
                
                # 將完整回應添加到歷史記錄
                full_response = "".join(collected_chunks)
                self.add_to_history(history[-1].get("user_id", "unknown"), "assistant", full_response)
            
            return generate()
        else:
            response = await self.openai_client.chat.completions.create(
                model=config.OPENAI_MODEL,
                messages=messages,
                temperature=config.LOCAL_MODEL_TEMPERATURE
            )
            return response.choices[0].message.content
    
    async def _get_anthropic_response(self, history: List[Dict[str, str]], stream: bool = False) -> Union[str, Generator[str, None, None]]:
        """從 Anthropic API 獲取回應"""
        if not self.anthropic_client:
            raise ValueError("Anthropic API 密鑰未設置")
        
        # 準備消息
        messages = [{"role": "user" if msg["role"] == "user" else "assistant", "content": msg["content"]} for msg in history]
        
        if stream:
            response_stream = await self.anthropic_client.messages.create(
                model=config.ANTHROPIC_MODEL,
                system=self.system_prompt,
                messages=messages,
                temperature=config.LOCAL_MODEL_TEMPERATURE,
                stream=True
            )
            
            async def generate():
                collected_chunks = []
                async for chunk in response_stream:
                    if hasattr(chunk, 'delta') and hasattr(chunk.delta, 'text'):
                        content = chunk.delta.text
                        if content:
                            collected_chunks.append(content)
                            yield content
                
                # 將完整回應添加到歷史記錄
                full_response = "".join(collected_chunks)
                self.add_to_history(history[-1].get("user_id", "unknown"), "assistant", full_response)
            
            return generate()
        else:
            response = await self.anthropic_client.messages.create(
                model=config.ANTHROPIC_MODEL,
                system=self.system_prompt,
                messages=messages,
                temperature=config.LOCAL_MODEL_TEMPERATURE
            )
            return response.content[0].text
    
    async def _get_gemini_response(self, history: List[Dict[str, str]], stream: bool = False) -> Union[str, Generator[str, None, None]]:
        """從 Gemini API 獲取回應"""
        if not self.gemini_client:
            raise ValueError("Gemini API 密鑰未設置")
        
        # 初始化 Gemini 模型
        model = self.gemini_client.GenerativeModel(config.GEMINI_MODEL)
        
        # 準備對話
        chat = model.start_chat(history=[
            {"role": "user" if msg["role"] == "user" else "model", "parts": [msg["content"]]}
            for msg in history[:-1]  # 不包括最後一條消息，因為我們將單獨發送它
        ])
        
        # 添加系統提示
        system_prompt = self.system_prompt
        
        if stream:
            # Gemini 的串流實現
            response_stream = await chat.send_message_async(
                history[-1]["content"],
                generation_config={
                    "temperature": config.LOCAL_MODEL_TEMPERATURE,
                    "top_p": config.LOCAL_MODEL_TOP_P
                },
                stream=True
            )
            
            async def generate():
                collected_chunks = []
                async for chunk in response_stream:
                    if chunk.text:
                        collected_chunks.append(chunk.text)
                        yield chunk.text
                
                # 將完整回應添加到歷史記錄
                full_response = "".join(collected_chunks)
                self.add_to_history(history[-1].get("user_id", "unknown"), "assistant", full_response)
            
            return generate()
        else:
            response = await chat.send_message_async(
                history[-1]["content"],
                generation_config={
                    "temperature": config.LOCAL_MODEL_TEMPERATURE,
                    "top_p": config.LOCAL_MODEL_TOP_P
                }
            )
            return response.text
    
    async def _get_local_api_response(self, history: List[Dict[str, str]], stream: bool = False) -> Union[str, Generator[str, None, None]]:
        """從本地 API 獲取回應"""
        # 準備消息
        messages = [{"role": "system", "content": self.system_prompt}]
        for msg in history:
            messages.append({"role": msg["role"], "content": msg["content"]})
        
        # 準備請求數據
        request_data = {
            "model": config.LOCAL_LLM_MODEL,
            "messages": messages,
            "temperature": config.LOCAL_MODEL_TEMPERATURE,
            "top_p": config.LOCAL_MODEL_TOP_P,
            "stream": stream
        }
        
        headers = {"Content-Type": "application/json"}
        
        if stream:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{config.LOCAL_LLM_URL}/chat/completions",
                    json=request_data,
                    headers=headers
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise ValueError(f"API 返回錯誤 {response.status}: {error_text}")
                    
                    async def generate():
                        collected_