import threading
import time
import logging
import os
from typing import Dict, List, Optional, Any

logger = logging.getLogger("GPUMonitor")

class GPUMonitor:
    _instance = None
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = GPUMonitor()
        return cls._instance
    
    def __init__(self):
        self.monitoring_thread = None
        self.stop_event = threading.Event()
        self.is_monitoring = False
    
    def start_monitoring(self, interval: int = 60):
        """開始監控 GPU 使用情況
        
        Args:
            interval: 監控間隔（秒）
        """
        if self.is_monitoring:
            logger.info("GPU 監控已經在運行中")
            return
        
        self.stop_event.clear()
        self.is_monitoring = True
        self.monitoring_thread = threading.Thread(target=self._monitor_loop, args=(interval,))
        self.monitoring_thread.daemon = True
        self.monitoring_thread.start()
        logger.info(f"GPU 監控已啟動，間隔: {interval}秒")
    
    def stop_monitoring(self):
        """停止 GPU 監控"""
        if not self.is_monitoring:
            logger.info("GPU 監控未在運行")
            return
        
        self.stop_event.set()
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5)
        self.is_monitoring = False
        logger.info("GPU 監控已停止")
    
    def _monitor_loop(self, interval: int):
        """監控循環"""
        while not self.stop_event.is_set():
            try:
                gpu_info = self.get_gpu_info()
                if gpu_info:
                    for i, info in enumerate(gpu_info):
                        logger.info(
                            f"GPU {i}: {info.get('name', 'Unknown')} | "
                            f"記憶體: {info.get('memory_used', 0):.1f}/{info.get('memory_total', 0):.1f} GB "
                            f"({info.get('memory_percent', 0):.1f}%) | "
                            f"使用率: {info.get('utilization', 0)}%"
                        )
                else:
                    logger.warning("無法獲取 GPU 信息")
            except Exception as e:
                logger.error(f"監控 GPU 時出錯: {e}")
            
            # 等待下一個間隔
            self.stop_event.wait(interval)
    
    def get_gpu_info(self) -> List[Dict[str, Any]]:
        """獲取 GPU 信息"""
        try:
            import torch
            if not torch.cuda.is_available():
                logger.warning("CUDA 不可用")
                return []
            
            gpu_count = torch.cuda.device_count()
            if gpu_count == 0:
                logger.warning("未檢測到 GPU")
                return []
            
            result = []
            
            for i in range(gpu_count):
                try:
                    # 嘗試獲取 GPU 名稱
                    name = torch.cuda.get_device_name(i)
                    
                    # 嘗試獲取 GPU 記憶體信息
                    memory_stats = torch.cuda.mem_get_info(i)
                    free_memory = memory_stats[0] / (1024**3)  # 轉換為 GB
                    total_memory = memory_stats[1] / (1024**3)  # 轉換為 GB
                    used_memory = total_memory - free_memory
                    memory_percent = (used_memory / total_memory) * 100 if total_memory > 0 else 0
                    
                    # 嘗試獲取 GPU 使用率
                    utilization = self._get_gpu_utilization(i)
                    
                    gpu_info = {
                        "name": name,
                        "memory_free": free_memory,
                        "memory_used": used_memory,
                        "memory_total": total_memory,
                        "memory_percent": memory_percent,
                        "utilization": utilization
                    }
                    
                    result.append(gpu_info)
                except Exception as e:
                    logger.error(f"獲取 GPU {i} 信息時出錯: {e}")
            
            return result
        except ImportError:
            logger.warning("未安裝 PyTorch，無法獲取 GPU 信息")
            return []
        except Exception as e:
            logger.error(f"獲取 GPU 信息時出錯: {e}")
            return []
    
    def _get_gpu_utilization(self, gpu_id: int = 0) -> int:
        """獲取 GPU 使用率"""
        try:
            # 嘗試使用 nvidia-smi 獲取 GPU 使用率
            import subprocess
            output = subprocess.check_output(
                [
                    'nvidia-smi', 
                    f'--query-gpu=utilization.gpu', 
                    '--format=csv,noheader,nounits', 
                    '-i', str(gpu_id)
                ],
                encoding='utf-8'
            )
            return int(output.strip())
        except Exception:
            # 如果失敗，返回 -1 表示未知
            return -1
    
    def get_gpu_memory_info(self) -> Dict[int, Dict[str, float]]:
        """獲取 GPU 記憶體信息"""
        try:
            import torch
            if not torch.cuda.is_available():
                return {}
            
            result = {}
            for i in range(torch.cuda.device_count()):
                try:
                    memory_stats = torch.cuda.mem_get_info(i)
                    free_memory = memory_stats[0] / (1024**3)  # 轉換為 GB
                    total_memory = memory_stats[1] / (1024**3)  # 轉換為 GB
                    allocated = total_memory - free_memory
                    
                    result[i] = {
                        "free": free_memory,
                        "allocated": allocated,
                        "total": total_memory,
                        "utilization": self._get_gpu_utilization(i)
                    }
                except Exception:
                    pass
            
            return result
        except Exception:
            return {}