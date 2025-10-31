# gemini_system_prompt_checker.py - 檢查 Gemini API 中的 system prompt
import google.generativeai as genai
import logging
import sys
import importlib

logger = logging.getLogger(__name__)

class GeminiSystemPromptChecker:
    """檢查 Gemini API 中的 system prompt"""
    
    def __init__(self):
        self.model = None
        self.config_loaded = False
        self.api_key_valid = False
        
    def load_config(self):
        """載入配置"""
        try:
            # 清除並重新載入 config
            if 'config' in sys.modules:
                del sys.modules['config']
            
            import config
            self.config = config
            self.config_loaded = True
            
            print(f"✅ 配置載入成功")
            
            # 檢查 API 金鑰
            if hasattr(config, 'GEMINI_API_KEY') and config.GEMINI_API_KEY:
                print(f"✅ Gemini API 金鑰存在")
                return True
            else:
                print(f"❌ Gemini API 金鑰不存在")
                return False
                
        except Exception as e:
            print(f"❌ 載入配置失敗: {e}")
            return False
    
    def initialize_gemini(self):
        """初始化 Gemini"""
        try:
            if not self.config_loaded:
                print(f"❌ 配置未載入")
                return False
            
            # 配置 Gemini API
            genai.configure(api_key=self.config.GEMINI_API_KEY)
            
            # 獲取模型名稱
            model_name = getattr(self.config, 'GEMINI_MODEL', 'gemini-1.5-flash')
            print(f"📱 使用模型: {model_name}")
            
            # 創建模型實例
            self.model = genai.GenerativeModel(model_name)
            self.api_key_valid = True
            
            print(f"✅ Gemini 模型初始化成功")
            return True
            
        except Exception as e:
            print(f"❌ Gemini 初始化失敗: {e}")
            return False
    
    def get_system_prompt(self):
        """獲取系統提示詞"""
        try:
            if not self.config_loaded:
                return None, "配置未載入"
            
            prompt_template = getattr(self.config, 'LLM_SYSTEM_PROMPT', None)
            if not prompt_template:
                return None, "LLM_SYSTEM_PROMPT 不存在"
            
            # 替換 bot_name
            bot_name = "島田 愛里壽"  # 你的機器人名稱
            system_prompt = prompt_template.format(bot_name=bot_name)
            
            return system_prompt, "成功"
            
        except Exception as e:
            return None, f"獲取系統提示詞失敗: {e}"
    
    def test_gemini_with_system_prompt(self, test_message="你好，請介紹一下自己"):
        """測試 Gemini 是否正確使用 system prompt"""
        try:
            if not self.model:
                return False, "Gemini 模型未初始化"
            
            # 獲取系統提示詞
            system_prompt, error = self.get_system_prompt()
            if not system_prompt:
                return False, f"無法獲取系統提示詞: {error}"
            
            print(f"📝 系統提示詞長度: {len(system_prompt)} 字元")
            print(f"📝 系統提示詞預覽: {system_prompt[:200]}...")
            
            # 構建完整的提示
            full_prompt = f"{system_prompt}\n\n用戶: {test_message}\n助手:"
            
            print(f"\n🧪 測試提示 Gemini...")
            print(f"測試訊息: {test_message}")
            
            # 發送請求到 Gemini
            response = self.model.generate_content(full_prompt)
            
            if response and response.text:
                print(f"\n✅ Gemini 回應成功!")
                print(f"📤 回應內容: {response.text[:300]}...")
                
                # 檢查回應是否符合角色設定
                response_text = response.text.lower()
                character_indicators = [
                    "戰車道", "指揮官", "戰略", "戰術", "分析",
                    "少女與戰車", "冷靜", "理性"
                ]
                
                found_indicators = [indicator for indicator in character_indicators 
                                  if indicator in response_text]
                
                if found_indicators:
                    print(f"✅ 檢測到角色特徵: {', '.join(found_indicators)}")
                    return True, {
                        'response': response.text,
                        'character_match': True,
                        'indicators': found_indicators,
                        'system_prompt_used': True
                    }
                else:
                    print(f"⚠️ 未檢測到明顯的角色特徵")
                    return True, {
                        'response': response.text,
                        'character_match': False,
                        'indicators': [],
                        'system_prompt_used': False
                    }
            else:
                return False, "Gemini 無回應或回應為空"
                
        except Exception as e:
            print(f"❌ 測試 Gemini 時出錯: {e}")
            return False, str(e)
    
    def comprehensive_check(self):
        """綜合檢查"""
        print("🔍 開始 Gemini System Prompt 綜合檢查...")
        print("=" * 60)
        
        results = {
            'config_loaded': False,
            'api_key_valid': False,
            'model_initialized': False,
            'system_prompt_exists': False,
            'system_prompt_content': None,
            'gemini_response_test': False,
            'character_match': False,
            'recommendations': []
        }
        
        # 1. 載入配置
        print(f"\n📋 步驟 1: 載入配置")
        if self.load_config():
            results['config_loaded'] = True
        else:
            results['recommendations'].append("檢查 config.py 檔案和 GEMINI_API_KEY")
            return results
        
        # 2. 初始化 Gemini
        print(f"\n🤖 步驟 2: 初始化 Gemini")
        if self.initialize_gemini():
            results['api_key_valid'] = True
            results['model_initialized'] = True
        else:
            results['recommendations'].append("檢查 Gemini API 金鑰是否正確")
            return results
        
        # 3. 檢查系統提示詞
        print(f"\n📝 步驟 3: 檢查系統提示詞")
        system_prompt, error = self.get_system_prompt()
        if system_prompt:
            results['system_prompt_exists'] = True
            results['system_prompt_content'] = {
                'length': len(system_prompt),
                'preview': system_prompt[:300] + "..." if len(system_prompt) > 300 else system_prompt,
                'has_character_setting': "少女與戰車" in system_prompt and "戰車道指揮官" in system_prompt
            }
            
            if not results['system_prompt_content']['has_character_setting']:
                results['recommendations'].append("系統提示詞可能未包含正確的角色設定")
        else:
            results['recommendations'].append(f"系統提示詞問題: {error}")
            return results
        
        # 4. 測試 Gemini 回應
        print(f"\n🧪 步驟 4: 測試 Gemini 回應")
        test_success, test_result = self.test_gemini_with_system_prompt()
        
        if test_success:
            results['gemini_response_test'] = True
            if isinstance(test_result, dict):
                results['character_match'] = test_result.get('character_match', False)
                
                if not results['character_match']:
                    results['recommendations'].append("Gemini 回應中未檢測到角色特徵，可能系統提示詞未生效")
        else:
            results['recommendations'].append(f"Gemini 測試失敗: {test_result}")
        
        # 5. 總結
        print(f"\n" + "=" * 60)
        print(f"📊 檢查結果總結:")
        print(f"  配置載入: {'✅' if results['config_loaded'] else '❌'}")
        print(f"  API 金鑰: {'✅' if results['api_key_valid'] else '❌'}")
        print(f"  模型初始化: {'✅' if results['model_initialized'] else '❌'}")
        print(f"  系統提示詞: {'✅' if results['system_prompt_exists'] else '❌'}")
        print(f"  Gemini 測試: {'✅' if results['gemini_response_test'] else '❌'}")
        print(f"  角色匹配: {'✅' if results['character_match'] else '❌'}")
        
        if results['recommendations']:
            print(f"\n💡 建議:")
            for i, rec in enumerate(results['recommendations'], 1):
                print(f"  {i}. {rec}")
        else:
            print(f"\n🎉 所有檢查通過！Gemini 正確使用了系統提示詞。")
        
        return results

def main():
    """主函數"""
    checker = GeminiSystemPromptChecker()
    results = checker.comprehensive_check()
    
    # 額外測試多個問題
    if results['model_initialized']:
        print(f"\n🔬 額外測試多個問題...")
        test_questions = [
            "請分析一下當前的情況",
            "你是誰？",
            "你有什麼特長？",
            "從戰術角度來看，這個問題如何解決？"
        ]
        
        for i, question in enumerate(test_questions, 1):
            print(f"\n測試 {i}: {question}")
            success, result = checker.test_gemini_with_system_prompt(question)
            if success and isinstance(result, dict):
                print(f"角色匹配: {'✅' if result['character_match'] else '❌'}")
                if result['indicators']:
                    print(f"檢測到特徵: {', '.join(result['indicators'])}")

if __name__ == "__main__":
    main()