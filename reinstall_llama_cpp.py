import os
import sys
import subprocess
import logging

# 設定日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("LlamaCppInstaller")

def reinstall_llama_cpp_with_cuda():
    """重新安裝帶有 CUDA 支持的 llama-cpp-python"""
    logger.info("開始重新安裝 llama-cpp-python 以支持 CUDA...")
    
    # 檢查 CUDA 是否可用
    try:
        import torch
        if not torch.cuda.is_available():
            logger.error("CUDA 不可用，請確保已正確安裝 NVIDIA 驅動和 CUDA")
            return False
        
        cuda_version = torch.version.cuda
        logger.info(f"檢測到 CUDA 版本: {cuda_version}")
    except ImportError:
        logger.warning("無法導入 torch 來檢查 CUDA 版本，將繼續安裝")
    
    # 卸載現有的 llama-cpp-python
    try:
        logger.info("卸載現有的 llama-cpp-python...")
        subprocess.run([sys.executable, "-m", "pip", "uninstall", "-y", "llama-cpp-python"], check=True)
    except subprocess.CalledProcessError as e:
        logger.warning(f"卸載 llama-cpp-python 時出錯: {e}")
    
    # 設置環境變量 - 使用新的 GGML_CUDA 而不是棄用的 LLAMA_CUBLAS
    env = os.environ.copy()
    env["CMAKE_ARGS"] = "-DGGML_CUDA=on"
    env["FORCE_CMAKE"] = "1"
    
    # 安裝帶有 CUDA 支持的 llama-cpp-python
    try:
        logger.info("安裝帶有 CUDA 支持的 llama-cpp-python...")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "llama-cpp-python", "--no-cache-dir", "--force-reinstall"],
            env=env,
            check=False,
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            logger.error(f"安裝 llama-cpp-python 時出錯: {result.stderr}")
            # 嘗試使用特定版本
            logger.info("嘗試安裝特定版本的 llama-cpp-python...")
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "llama-cpp-python==0.2.56", "--no-cache-dir", "--force-reinstall"],
                env=env,
                check=False,
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                logger.error(f"安裝特定版本時出錯: {result.stderr}")
                return False
        
        logger.info("llama-cpp-python 已成功安裝，帶有 CUDA 支持")
    except Exception as e:
        logger.error(f"安裝 llama-cpp-python 時出錯: {e}")
        return False
    
    # 驗證安裝
    try:
        from llama_cpp import Llama
        logger.info("成功導入 llama_cpp.Llama")
        
        # 檢查是否支持 CUDA
        if hasattr(Llama, "cuda_is_available"):
            cuda_available = Llama.cuda_is_available()
            logger.info(f"llama-cpp-python CUDA 支持: {'可用' if cuda_available else '不可用'}")
            return cuda_available
        else:
            logger.warning("無法直接檢查 CUDA 支持，請在使用時驗證")
            return True
    except ImportError as e:
        logger.error(f"導入 llama_cpp 時出錯: {e}")
        return False

def check_cuda_support():
    """檢查系統 CUDA 支持情況"""
    logger.info("檢查系統 CUDA 支持情況...")
    
    # 檢查 NVIDIA 驅動
    try:
        nvidia_smi_output = subprocess.run(
            ["nvidia-smi"], 
            capture_output=True, 
            text=True, 
            check=False
        )
        if nvidia_smi_output.returncode == 0:
            logger.info("NVIDIA 驅動已安裝:")
            for line in nvidia_smi_output.stdout.splitlines()[:10]:  # 只顯示前10行
                logger.info(line)
        else:
            logger.warning("NVIDIA 驅動未安裝或 nvidia-smi 命令不可用")
    except FileNotFoundError:
        logger.warning("找不到 nvidia-smi 命令，NVIDIA 驅動可能未安裝")
    
    # 檢查 PyTorch CUDA 支持
    try:
        import torch
        logger.info(f"PyTorch 版本: {torch.__version__}")
        logger.info(f"CUDA 可用: {torch.cuda.is_available()}")
        if torch.cuda.is_available():
            logger.info(f"CUDA 版本: {torch.version.cuda}")
            logger.info(f"GPU 數量: {torch.cuda.device_count()}")
            for i in range(torch.cuda.device_count()):
                logger.info(f"GPU {i}: {torch.cuda.get_device_name(i)}")
    except ImportError:
        logger.warning("無法導入 PyTorch")
    
    # 檢查 CUDA 工具包
    try:
        nvcc_output = subprocess.run(
            ["nvcc", "--version"], 
            capture_output=True, 
            text=True, 
            check=False
        )
        if nvcc_output.returncode == 0:
            logger.info("CUDA 工具包已安裝:")
            logger.info(nvcc_output.stdout.strip())
        else:
            logger.warning("CUDA 工具包未安裝或 nvcc 命令不可用")
    except FileNotFoundError:
        logger.warning("找不到 nvcc 命令，CUDA 工具包可能未安裝")
    
    # 檢查 Visual Studio (Windows 特有)
    if sys.platform == "win32":
        try:
            vs_where_output = subprocess.run(
                ["vswhere", "-latest", "-property", "installationPath"], 
                capture_output=True, 
                text=True, 
                check=False
            )
            if vs_where_output.returncode == 0 and vs_where_output.stdout.strip():
                logger.info(f"Visual Studio 已安裝: {vs_where_output.stdout.strip()}")
            else:
                logger.warning("Visual Studio 可能未安裝或 vswhere 命令不可用")
        except FileNotFoundError:
            logger.warning("找不到 vswhere 命令，無法檢查 Visual Studio 安裝情況")

def install_precompiled():
    """嘗試安裝預編譯的 llama-cpp-python 包"""
    logger.info("嘗試安裝預編譯的 llama-cpp-python 包...")
    
    # 檢查 CUDA 版本
    cuda_version = None
    try:
        import torch
        if torch.cuda.is_available():
            cuda_version = torch.version.cuda
            logger.info(f"檢測到 CUDA 版本: {cuda_version}")
    except ImportError:
        logger.warning("無法導入 torch 來檢查 CUDA 版本")
    
    # 卸載現有的 llama-cpp-python
    try:
        logger.info("卸載現有的 llama-cpp-python...")
        subprocess.run([sys.executable, "-m", "pip", "uninstall", "-y", "llama-cpp-python"], check=True)
    except subprocess.CalledProcessError as e:
        logger.warning(f"卸載 llama-cpp-python 時出錯: {e}")
    
    # 根據 CUDA 版本選擇適當的預編譯包
    if cuda_version:
        # 去掉 CUDA 版本中的小版本號，例如將 11.8 轉換為 11
        cuda_major = cuda_version.split('.')[0]
        
        # 嘗試安裝預編譯包
        try:
            logger.info(f"嘗試安裝 CUDA {cuda_major} 預編譯包...")
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", f"llama-cpp-python-cuda{cuda_major}", "--no-cache-dir"],
                check=False,
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                logger.info(f"成功安裝 llama-cpp-python-cuda{cuda_major}")
                return True
            else:
                logger.warning(f"安裝預編譯包失敗: {result.stderr}")
                return False
        except Exception as e:
            logger.error(f"安裝預編譯包時出錯: {e}")
            return False
    else:
        logger.warning("未檢測到 CUDA 版本，無法安裝預編譯包")
        return False

if __name__ == "__main__":
    # 檢查系統 CUDA 支持情況
    check_cuda_support()
    
    # 首先嘗試安裝預編譯包
    if install_precompiled():
        logger.info("成功安裝預編譯的 llama-cpp-python 包")
    else:
        # 如果預編譯包安裝失敗，則嘗試從源碼編譯
        logger.info("預編譯包安裝失敗，嘗試從源碼編譯...")
        success = reinstall_llama_cpp_with_cuda()
        if success:
            logger.info("從源碼編譯安裝成功！llama-cpp-python 現在應該支持 CUDA")
        else:
            logger.error("安裝失敗，請查看上面的錯誤信息")