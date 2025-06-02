import os
import torch
import logging
import threading
import time
from typing import Dict, Any, Generator, Optional
from transformers import AutoModelForCausalLM, AutoTokenizer, TextIteratorStreamer
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
        self.gguf_model = None
        self.gguf_is_ready = False
        self.gguf_is_loading = False
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
        
        # 嘗試在初始化時加載 GGUF 模型
        try:
            if hasattr(config, 'LOCAL_GGUF_MODEL_PATH') and config.LOCAL_GGUF_MODEL_PATH:
                logger.info("初始化時嘗試加載 GGUF 模型")
                Thread(target=self.load_gguf_model).start()
        except Exception as e:
            logger.error(f"初始化時加載 GGUF 模型失敗: {e}")
    
    def load_model(self) -> bool:
        """加載 Hugging Face 模型"""
        if self.is_ready:
            logger.info("模型已加載")
            return True
        
        if self.is_loading:
            logger.info("模型正在加載中")
            return False
        
        with self.lock:
            self.is_loading = True
            
            try:
                logger.info(f"開始加載模型: {config.LOCAL_MODEL_NAME}")
                start_time = time.time()
                
                # 加載分詞器
                self.tokenizer = AutoTokenizer.from_pretrained(
                    config.LOCAL_MODEL_NAME,
                    trust_remote_code=True
                )
                
                # 設置 pad token
                if self.tokenizer.pad_token is None:
                    self.tokenizer.pad_token = self.tokenizer.eos_token
                
                # 加載模型
                self.model = AutoModelForCausalLM.from_pretrained(
                    config.LOCAL_MODEL_NAME,
                    torch_dtype=torch.float16 if config.USE_HALF_PRECISION else torch.float32,
                    device_map="cuda",
                    trust_remote_code=True
                )
                
                # 設置模型為評估模式
                self.model.eval()
                
                end_time = time.time()
                logger.info(f"模型加載完成，耗時: {end_time - start_time:.2f} 秒")
                
                self.is_ready = True
                self.is_loading = False
                return True
            
            except Exception as e:
                logger.error(f"加載模型時出錯: {e}")
                self.is_loading = False
                return False
   
    def load_gguf_model(self) -> bool:
        """加載 GGUF 模型"""
        if self.gguf_is_ready:
            logger.info("GGUF 模型已加載")
            return True
        
        if self.gguf_is_loading:
            logger.info("GGUF 模型正在加載中")
            return False
        
        with self.lock:
            self.gguf_is_loading = True
            
            try:
                # 檢查 GGUF 模型路徑是否存在
                if not hasattr(config, 'LOCAL_GGUF_MODEL_PATH') or not config.LOCAL_GGUF_MODEL_PATH:
                    raise ValueError("未設定 GGUF 模型路徑")
                
                if not os.path.exists(config.LOCAL_GGUF_MODEL_PATH):
                    raise FileNotFoundError(f"GGUF 模型文件不存在: {config.LOCAL_GGUF_MODEL_PATH}")
                
                # 檢查 CUDA 可用性
                cuda_available = torch.cuda.is_available()
                if cuda_available:
                    logger.info(f"檢測到 CUDA，GPU: {torch.cuda.get_device_name(0)}")
                    logger.info(f"CUDA 版本: {torch.version.cuda}")
                    logger.info(f"可用 GPU 數量: {torch.cuda.device_count()}")
                    logger.info(f"當前 GPU 內存使用: {torch.cuda.memory_allocated(0) / 1024**2:.2f} MB")
                else:
                    logger.warning("未檢測到 CUDA，GGUF 模型將使用 CPU 運行，性能會受到嚴重影響")
                
                logger.info(f"開始加載 GGUF 模型: {config.LOCAL_GGUF_MODEL_PATH}")
                start_time = time.time()
                
                # 導入 llama_cpp
                try:
                    from llama_cpp import Llama
                    # 檢查 llama_cpp 是否支持 CUDA
                    has_cuda_support = hasattr(Llama, "supports_cuda") and Llama.supports_cuda()
                    if cuda_available and not has_cuda_support:
                        logger.warning("llama_cpp 未編譯支持 CUDA，請重新安裝支持 CUDA 的版本")
                        logger.warning("安裝命令: CMAKE_ARGS=\"-DLLAMA_CUBLAS=on\" pip install llama-cpp-python --force-reinstall --no-cache-dir")
                    elif cuda_available:
                        logger.info("llama_cpp 支持 CUDA")
                except ImportError:
                    logger.error("無法導入 llama_cpp 庫，請確保已安裝 llama-cpp-python")
                    raise ImportError("未安裝 llama-cpp-python 庫")
                
                # 從配置中獲取參數，如果沒有設置則使用優化的默認值
                context_size = getattr(config, 'GGUF_CONTEXT_SIZE', 8192)
                batch_size = getattr(config, 'GGUF_BATCH_SIZE', 1024)
                
                # 確保 GPU 層設置正確
                gpu_layers = getattr(config, 'GGUF_GPU_LAYERS', -1)
                if not cuda_available and gpu_layers != 0:
                    logger.warning("CUDA 不可用但嘗試使用 GPU 層，將 GPU 層設置為 0")
                    gpu_layers = 0
                elif cuda_available and gpu_layers == 0:
                    logger.warning("CUDA 可用但 GPU 層設置為 0，將使用所有層")
                    gpu_layers = -1
                
                # 加載模型 - 確保明確指定 CUDA 使用
                self.gguf_model = Llama(
                    model_path=config.LOCAL_GGUF_MODEL_PATH,
                    n_ctx=context_size,
                    n_gpu_layers=gpu_layers,
                    n_batch=batch_size,
                    offload_kqv=cuda_available,
                    f16_kv=cuda_available,
                    use_mmap=True,
                    use_mlock=True,
                    # 明確啟用 CUDA
                    use_cuda=cuda_available,  # 明確設置使用 CUDA
                    flash_attn=cuda_available and has_cuda_support,
                    # 新增 CUDA 相關參數
                    mul_mat_q=cuda_available,  # 使用 CUDA 進行矩陣乘法
                    verbose=True
                )
                
                end_time = time.time()
                logger.info(f"GGUF 模型加載完成，耗時: {end_time - start_time:.2f} 秒")
                
                # 確認 GPU 使用情況
                if cuda_available:
                    # 檢查模型是否確實使用了 GPU
                    if hasattr(self.gguf_model, "model_gpu_layers"):
                        gpu_layer_count = self.gguf_model.model_gpu_layers
                        logger.info(f"GGUF 模型已將 {gpu_layer_count} 層加載到 GPU")
                    
                    logger.info(f"GGUF 模型加載後 GPU 內存使用: {torch.cuda.memory_allocated(0) / 1024**2:.2f} MB")
                    logger.info(f"GGUF 模型加載後 GPU 內存緩存: {torch.cuda.memory_reserved(0) / 1024**2:.2f} MB")
                else:
                    logger.info("GGUF 模型已加載到 CPU")
                
                self.gguf_is_ready = True
                self.gguf_is_loading = False
                return True
            
            except Exception as e:
                logger.error(f"加載 GGUF 模型時出錯: {e}")
                import traceback
                logger.error(traceback.format_exc())
                self.gguf_is_loading = False
                return False


    
    def unload_gguf_model(self) -> bool:
        """卸載 GGUF 模型"""
        if not self.gguf_is_ready:
            logger.info("GGUF 模型未加載")
            return True
        
        with self.lock:
            try:
                logger.info("開始卸載 GGUF 模型")
                
                # 釋放模型
                self.gguf_model = None
                
                # 手動觸發垃圾回收
                import gc
                gc.collect()
                
                # 如果使用 CUDA，清空 CUDA 緩存
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                    logger.info("已清空 CUDA 緩存")
                
                self.gguf_is_ready = False
                logger.info("GGUF 模型已卸載")
                return True
            
            except Exception as e:
                logger.error(f"卸載 GGUF 模型時出錯: {e}")
                return False
    
    def generate(self, prompt: str, generation_config: Dict[str, Any] = None) -> str:
        """生成回應，優先使用 GGUF 模型"""
        try:
            if not self.gguf_is_ready:
                logger.info("GGUF 模型未加載，嘗試加載...")
                if not self.load_gguf_model():
                    logger.error("無法載入 GGUF 模型，將使用 Hugging Face 模型")
                    self.load_model()

            # 使用 GGUF 模型生成回應
            if self.gguf_is_ready:
                return self.generate_with_gguf(prompt, generation_config)

            # 如果 GGUF 模型不可用，則使用 Hugging Face 模型
            if not self.is_ready:
                self.load_model()

            # Hugging Face 模型生成逻辑
            return self._generate_with_huggingface(prompt, generation_config)

        except Exception as e:
            logger.error(f"生成回應時出錯: {e}")
            return f"生成錯誤: {str(e)}"

    def _generate_with_huggingface(self, prompt: str, generation_config: Dict[str, Any]) -> str:
        """使用 Hugging Face 模型生成回應"""
        try:
            # 分詞
            inputs = self.tokenizer(prompt, return_tensors="pt")
            input_ids = inputs.input_ids.to(self.model.device)

            # 生成
            with torch.no_grad():
                output = self.model.generate(
                    input_ids,
                    max_new_tokens=generation_config.get("max_new_tokens", 512),
                    temperature=generation_config.get("temperature", 0.7),
                    top_p=generation_config.get("top_p", 0.9),
                    repetition_penalty=generation_config.get("repetition_penalty", 1.1),
                    do_sample=generation_config.get("do_sample", True),
                    pad_token_id=self.tokenizer.eos_token_id
                )

            # 解碼
            return self.tokenizer.decode(output[0][input_ids.shape[1]:], skip_special_tokens=True)

        except Exception as e:
            logger.error(f"使用 Hugging Face 模型生成回應時出錯: {e}")
            return f"生成錯誤: {str(e)}"

    def generate_stream(self, prompt: str, generation_config: Dict[str, Any] = None) -> Generator[str, None, None]:
        """流式生成回應，優先使用 GGUF 模型"""
        try:
            if not self.gguf_is_ready:
                logger.info("GGUF 模型未加載，嘗試加載...")
                if not self.load_gguf_model():
                    logger.error("無法載入 GGUF 模型，將使用 Hugging Face 模型")
                    self.load_model()

            # 使用 GGUF 模型流式生成回應
            if self.gguf_is_ready:
                yield from self.generate_with_gguf_stream(prompt, generation_config)
                return

            # 如果 GGUF 模型不可用，則使用 Hugging Face 模型
            if not self.is_ready:
                self.load_model()

            # Hugging Face 模型流式生成逻辑
            yield from self._generate_with_huggingface_stream(prompt, generation_config)

        except Exception as e:
            logger.error(f"流式生成回應時出錯: {e}")
            yield f"\n[生成錯誤: {str(e)}]"

    def _generate_with_huggingface_stream(self, prompt: str, generation_config: Dict[str, Any]) -> Generator[str, None, None]:
        """使用 Hugging Face 模型流式生成回應"""
        try:
            # 分詞
            inputs = self.tokenizer(prompt, return_tensors="pt")
            input_ids = inputs.input_ids.to(self.model.device)

            # 創建 TextIteratorStreamer
            streamer = TextIteratorStreamer(self.tokenizer, skip_prompt=True, skip_special_tokens=True)

            # 生成參數
            gen_kwargs = {
                "input_ids": input_ids,
                "max_new_tokens": generation_config.get("max_new_tokens", 512),
                "temperature": generation_config.get("temperature", 0.7),
                "top_p": generation_config.get("top_p", 0.9),
                "repetition_penalty": generation_config.get("repetition_penalty", 1.1),
                "do_sample": generation_config.get("do_sample", True),
                "pad_token_id": self.tokenizer.eos_token_id,
                "streamer": streamer
            }

            # 在單獨的線程中運行生成
            generation_thread = Thread(target=self._generate_in_thread, args=(gen_kwargs,))
            generation_thread.start()

            # 從 streamer 獲取生成的 tokens
            for text in streamer:
                yield text

        except Exception as e:
            logger.error(f"使用 Hugging Face 模型流式生成回應時出錯: {e}")
            yield f"\n[生成錯誤: {str(e)}]"

    def _generate_in_thread(self, gen_kwargs: Dict[str, Any]) -> None:
        """在單獨的線程中運行生成"""
        try:
            with torch.no_grad():
                self.model.generate(**gen_kwargs)
        except Exception as e:
            logger.error(f"生成線程中出錯: {e}")

    def generate_with_gguf(self, prompt: str, generation_config: Dict[str, Any] = None) -> str:
        """使用 GGUF 模型生成回應"""
        if not self.gguf_is_ready:
            raise ValueError("GGUF 模型未加載")
        
        # 設置默認生成參數
        if generation_config is None:
            generation_config = {}
        
        max_new_tokens = generation_config.get("max_new_tokens", 512)
        temperature = generation_config.get("temperature", 0.7)
        top_p = generation_config.get("top_p", 0.9)
        repetition_penalty = generation_config.get("repetition_penalty", 1.1)
        
        try:
            # 使用 GGUF 模型生成
            response = self.gguf_model(
                prompt,
                max_tokens=max_new_tokens,
                temperature=temperature,
                top_p=top_p,
                repeat_penalty=repetition_penalty,
                echo=False
            )
            
            # 提取生成的文本
            if isinstance(response, dict) and "choices" in response:
                text = response["choices"][0]["text"]
            else:
                text = response
            
            return text
        
        except Exception as e:
            logger.error(f"使用 GGUF 模型生成回應時出錯: {e}")
            return f"生成錯誤: {str(e)}"
    
    def generate_with_gguf_stream(self, prompt: str, generation_config: Dict[str, Any] = None) -> Generator[str, None, None]:
        """使用 GGUF 模型流式生成回應"""
        if not self.gguf_is_ready:
            raise ValueError("GGUF 模型未加載")
        
        # 設置默認生成參數
        if generation_config is None:
            generation_config = {}
        
        max_new_tokens = generation_config.get("max_new_tokens", 512)
        temperature = generation_config.get("temperature", 0.7)
        top_p = generation_config.get("top_p", 0.9)
        repetition_penalty = generation_config.get("repetition_penalty", 1.1)
        
        try:
            # 使用 GGUF 模型流式生成
            response_iter = self.gguf_model(
                prompt,
                max_tokens=max_new_tokens,
                temperature=temperature,
                top_p=top_p,
                repeat_penalty=repetition_penalty,
                echo=False,
                stream=True
            )
            
            # 提取生成的文本
            for chunk in response_iter:
                if isinstance(chunk, dict) and "choices" in chunk:
                    text = chunk["choices"][0]["text"]
                    if text:
                        yield text
                else:
                    # 如果是其他格式，嘗試直接提取文本
                    if hasattr(chunk, "text"):
                        text = chunk.text
                        if text:
                            yield text
        
        except Exception as e:
            logger.error(f"使用 GGUF 模型流式生成回應時出錯: {e}")
            yield f"\n[生成錯誤: {str(e)}]"
    
    def get_gpu_memory_info(self) -> Optional[Dict[str, Dict[str, float]]]:
        """獲取 GPU 內存使用信息"""
        if self.gpu_monitor:
            return self.gpu_monitor.get_gpu_memory_info()
        return None