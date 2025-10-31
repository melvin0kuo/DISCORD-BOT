# reload_utility.py - 重新載入工具
import importlib
import sys
import os
from dotenv import load_dotenv

def force_reload_config():
    """強制重新載入配置"""
    print("🔄 開始強制重新載入配置...")
    
    # 1. 清除環境變數快取
    print("📝 清除環境變數快取...")
    
    # 2. 重新載入 .env 檔案
    if os.path.exists('.env'):
        print("📂 重新載入 .env 檔案...")
        load_dotenv('.env', override=True)
        print("✅ .env 檔案重新載入完成")
    else:
        print("❌ .env 檔案不存在")
    
    # 3. 重新載入 config 模組
    if 'config' in sys.modules:
        print("🔧 重新載入 config 模組...")
        importlib.reload(sys.modules['config'])
        print("✅ config 模組重新載入完成")
    
    # 4. 重新載入 LLMHandler 模組
    if 'llm_handler' in sys.modules:
        print("🤖 重新載入 LLMHandler 模組...")
        importlib.reload(sys.modules['llm_handler'])
        print("✅ LLMHandler 模組重新載入完成")
    
    print("🎉 所有模組重新載入完成")

def check_env_file():
    """檢查 .env 檔案內容"""
    if not os.path.exists('.env'):
        print("❌ .env 檔案不存在")
        return False
    
    print("📋 .env 檔案內容:")
    with open('.env', 'r', encoding='utf-8') as f:
        lines = f.readlines()
        for i, line in enumerate(lines, 1):
            line = line.strip()
            if line and not line.startswith('#'):
                # 隱藏敏感資訊
                if '=' in line:
                    key, value = line.split('=', 1)
                    if 'TOKEN' in key or 'KEY' in key:
                        value = '*' * min(len(value), 8) + '...'
                    print(f"  {i:2d}: {key}={value}")
                else:
                    print(f"  {i:2d}: {line}")
    return True

def validate_config():
    """驗證配置是否正確載入"""
    try:
        import config
        print("🔍 驗證配置...")
        
        # 檢查必要的配置項
        required_configs = [
            'DISCORD_TOKEN',
            'GEMINI_API_KEY',
            'GEMINI_MODEL'
        ]
        
        for config_name in required_configs:
            if hasattr(config, config_name):
                value = getattr(config, config_name)
                if value:
                    print(f"✅ {config_name}: 已設定")
                else:
                    print(f"❌ {config_name}: 未設定或為空")
            else:
                print(f"❌ {config_name}: 不存在")
        
        # 檢查數值型配置
        numeric_configs = [
            'GEMINI_TEMPERATURE',
            'GEMINI_TOP_P',
            'GEMINI_MAX_OUTPUT_TOKENS',
            'MAX_HISTORY_LENGTH'
        ]
        
        for config_name in numeric_configs:
            if hasattr(config, config_name):
                value = getattr(config, config_name)
                print(f"📊 {config_name}: {value} ({type(value).__name__})")
            else:
                print(f"❌ {config_name}: 不存在")
        
        return True
        
    except ImportError as e:
        print(f"❌ 無法導入 config 模組: {e}")
        return False
    except Exception as e:
        print(f"❌ 驗證配置時出錯: {e}")
        return False

if __name__ == "__main__":
    print("🚀 配置診斷工具")
    print("=" * 50)
    
    # 檢查 .env 檔案
    check_env_file()
    print()
    
    # 強制重新載入
    force_reload_config()
    print()
    
    # 驗證配置
    validate_config()