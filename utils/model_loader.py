import os
import torch
import logging
import threading
import time
from typing import Dict, Any, Generator, Optional
# from transformers import AutoModelForCausalLM, AutoTokenizer, TextIteratorStreamer
from threading import Thread
import config

# 設定日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ModelLoader")

class ModelLoader:
    _instance = None
    _lock = threading.Lock()
    
    @classmethod
    def get_instance(cls):
        """獲取 ModelLoader 的單例實例"""
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
        return cls._instance
    
    def __init__(self):
        self.model = None
        self.tokenizer = None
        self.is_ready = False
        self.is_loading = False
        self.lock = threading.Lock()
        self.gpu_monitor = None
        self.preloaded_model = None
        self.preloaded_tokenizer = None
        # 檢查 CUDA 可用性
        if torch.cuda.is_available():
            logger.info(f"初始化時檢測到 CUDA，GPU: {torch.cuda.get_device_name(0)}")
            logger.info(f"CUDA 版本: {torch.version.cuda}")
            # 清空 CUDA 緩存
            torch.cuda.empty_cache()
            logger.info("已清空 CUDA 緩存")
        else:
            logger.warning("初始化時未檢測到 CUDA，將使用 CPU 進行推理")
        # 嘗試導入 GPU 監控
        try:
            from utils.gpu_monitor import GPUMonitor
            self.gpu_monitor = GPUMonitor.get_instance()
        except ImportError:
            logger.warning("無法導入 GPUMonitor")
        # 預先加載 HuggingFace 模型（deepseek-ai/deepseek-llm-7b-chat）
        # try:
        #     logger.info("預先加載 HuggingFace 模型: deepseek-ai/deepseek-llm-7b-chat")
        #     self.preloaded_tokenizer = AutoTokenizer.from_pretrained(
        #         "deepseek-ai/deepseek-llm-7b-chat",
        #         trust_remote_code=True
        #     )
        #     self.preloaded_model = AutoModelForCausalLM.from_pretrained(
        #         "deepseek-ai/deepseek-llm-7b-chat",
        #         torch_dtype=torch.float16 if getattr(config, "USE_HALF_PRECISION", False) else torch.float32,
        #         device_map="cuda" if torch.cuda.is_available() else "cpu",
        #         trust_remote_code=True
        #     )
        #     if self.preloaded_model is not None:
        #         self.preloaded_model.eval()
        #         logger.info("deepseek-ai/deepseek-llm-7b-chat 預加載完成")
        #     else:
        #         logger.error("deepseek-ai/deepseek-llm-7b-chat 預加載失敗，模型為 NoneType")
        # except Exception as e:
        #     logger.error(f"預加載 deepseek-ai/deepseek-llm-7b-chat 失敗: {e}")

    # def load_model(self) -> bool:
    #     """加載 Hugging Face 模型"""
    #     if self.is_ready:
    #         logger.info("模型已加載")
    #         return True
    #
    #     if self.is_loading:
    #         logger.info("模型正在加載中")
    #         return False
    #
    #     with self.lock:
    #         self.is_loading = True
    #
    #         try:
    #             logger.info(f"開始加載模型: {config.LOCAL_MODEL_NAME}")
    #             logger.info(f"USE_HALF_PRECISION: {getattr(config, 'USE_HALF_PRECISION', 'NOT FOUND')}")
    #             start_time = time.time()
    #
    #             # 加載分詞器
    #             self.tokenizer = AutoTokenizer.from_pretrained(
    #                 config.LOCAL_MODEL_NAME,
    #                 trust_remote_code=True
    #             )
    #
    #             # 設置 pad token
    #             if self.tokenizer.pad_token is None:
    #                 self.tokenizer.pad_token = self.tokenizer.eos_token
    #
    #             # 加載模型
    #             self.model = AutoModelForCausalLM.from_pretrained(
    #                 config.LOCAL_MODEL_NAME,
    #                 torch_dtype=torch.float16 if getattr(config, "USE_HALF_PRECISION", False) else torch.float32,
    #                 device_map="cuda" if torch.cuda.is_available() else "cpu",
    #                 trust_remote_code=True
    #             )
    #
    #             # 設置模型為評估模式
    #             self.model.eval()
    #
    #             end_time = time.time()
    #             logger.info(f"模型加載完成，耗時: {end_time - start_time:.2f} 秒")
    #
    #             self.is_ready = True
    #             self.is_loading = False
    #             return True
    #
    #         except Exception as e:
    #             logger.error(f"加載模型時出錯: {e}")
    #             logger.error(f"config.USE_HALF_PRECISION: {getattr(config, 'USE_HALF_PRECISION', 'NOT FOUND')}")
    #             self.is_loading = False
    #             return False
       
    # def generate(self, prompt: str, generation_config: Dict[str, Any] = None) -> str:
    #     """生成回應（僅 Hugging Face 模型）"""
    #     try:
    #         if not self.is_ready:
    #             self.load_model()
    #         return self._generate_with_huggingface(prompt, generation_config)
    #     except Exception as e:
    #         logger.error(f"生成回應時出錯: {e}")
    #         return f"生成錯誤: {str(e)}"

    # def _generate_with_huggingface(self, prompt: str, generation_config: Dict[str, Any]) -> str:
    #     """使用 Hugging Face 模型生成回應"""
    #     try:
    #         # 分詞
    #         inputs = self.tokenizer(prompt, return_tensors="pt")
    #         if self.model is None:
    #             logger.error("推理時 model 為 NoneType，請檢查模型是否正確加載")
    #             return "模型尚未正確加載，無法進行推理。"
    #         input_ids = inputs.input_ids.to(self.model.device)
    #
    #         # 生成
    #         with torch.no_grad():
    #             output = self.model.generate(
    #                 input_ids,
    #                 attention_mask=inputs.attention_mask.to(self.model.device) if hasattr(inputs, "attention_mask") else None,
    #                 max_new_tokens=generation_config.get("max_new_tokens", 512),
    #                 temperature=generation_config.get("temperature", 0.7),
    #                 top_p=generation_config.get("top_p", 0.9),
    #                 repetition_penalty=generation_config.get("repetition_penalty", 1.1),
    #                 do_sample=generation_config.get("do_sample", True),
    #                 pad_token_id=self.tokenizer.eos_token_id,
    #                 use_cache=False  # 修正 DynamicCache 問題
    #             )
    #
    #         # 解碼
    #         return self.tokenizer.decode(output[0][input_ids.shape[1]:], skip_special_tokens=True)
    #
    #     except Exception as e:
    #         logger.error(f"使用 Hugging Face 模型生成回應時出錯: {e}")
    #         return f"生成錯誤: {str(e)}"

    # def generate_stream(self, prompt: str, generation_config: Dict[str, Any] = None) -> Generator[str, None, None]:
    #     """流式生成回應（僅 Hugging Face 模型）"""
    #     try:
    #         if not self.is_ready:
    #             self.load_model()
    #         yield from self._generate_with_huggingface_stream(prompt, generation_config)
    #     except Exception as e:
    #         logger.error(f"流式生成回應時出錯: {e}")
    #         yield f"\n[生成錯誤: {str(e)}]"

    # def _generate_with_huggingface_stream(self, prompt: str, generation_config: Dict[str, Any]) -> Generator[str, None, None]:
    #     """使用 Hugging Face 模型流式生成回應"""
    #     try:
    #         # 分詞
    #         inputs = self.tokenizer(prompt, return_tensors="pt")
    #         if self.model is None:
    #             logger.error("推理時 model 為 NoneType，請檢查模型是否正確加載")
    #             yield "模型尚未正確加載，無法進行推理。"
    #             return
    #         input_ids = inputs.input_ids.to(self.model.device)
    #
    #         # 創建 TextIteratorStreamer
    #         streamer = TextIteratorStreamer(self.tokenizer, skip_prompt=True, skip_special_tokens=True)
    #
    #         # 生成參數
    #         gen_kwargs = {
    #             "input_ids": input_ids,
    #             "attention_mask": inputs.attention_mask.to(self.model.device) if hasattr(inputs, "attention_mask") else None,
    #             "max_new_tokens": generation_config.get("max_new_tokens", 512),
    #             "temperature": generation_config.get("temperature", 0.7),
    #             "top_p": generation_config.get("top_p", 0.9),
    #             "repetition_penalty": generation_config.get("repetition_penalty", 1.1),
    #             "do_sample": generation_config.get("do_sample", True),
    #             "pad_token_id": self.tokenizer.eos_token_id,
    #             "streamer": streamer,
    #             "use_cache": False  # 修正 DynamicCache 問題
    #         }
    #
    #         # 在單獨的線程中運行生成
    #         generation_thread = Thread(target=self._generate_in_thread, args=(gen_kwargs,))
    #         generation_thread.start()
    #
    #         # 從 streamer 獲取生成的 tokens
    #         for text in streamer:
    #             yield text
    #
    #     except Exception as e:
    #         logger.error(f"使用 Hugging Face 模型流式生成回應時出錯: {e}")
    #         yield f"\n[生成錯誤: {str(e)}]"

    def _generate_in_thread(self, gen_kwargs: Dict[str, Any]) -> None:
        """在單獨的線程中運行生成"""
        try:
            with torch.no_grad():
                self.model.generate(**gen_kwargs)
        except Exception as e:
            logger.error(f"生成線程中出錯: {e}")
    
    def get_gpu_memory_info(self) -> Optional[Dict[str, Dict[str, float]]]:
        """獲取 GPU 內存使用信息"""
        if self.gpu_monitor:
            return self.gpu_monitor.get_gpu_memory_info()
        return None