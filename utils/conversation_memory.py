"""
對話記憶管理模組
提供智慧的對話上下文工程和記憶管理功能
"""

import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
import hashlib
from utils.user_database import user_db

logger = logging.getLogger(__name__)

class ConversationMemory:
    """對話記憶管理器"""
    
    def __init__(self):
        self.short_term_memory = {}  # 臨時記憶：當前對話階段
        self.conversation_summaries = {}  # 對話摘要：長期記憶
        
    def add_conversation_turn(self, user_id: str, channel_id: str, user_message: str, ai_response: str, context: Dict = None):
        """添加一輪對話到記憶中"""
        try:
            conversation_key = f"{user_id}_{channel_id}"
            timestamp = datetime.now().isoformat()
            
            # 創建對話記錄
            turn_data = {
                "timestamp": timestamp,
                "user_message": user_message,
                "ai_response": ai_response,
                "context": context or {},
                "turn_id": self._generate_turn_id(user_id, channel_id, timestamp)
            }
            
            # 加入短期記憶
            if conversation_key not in self.short_term_memory:
                self.short_term_memory[conversation_key] = []
            
            self.short_term_memory[conversation_key].append(turn_data)
            
            # 存儲到資料庫
            self._save_conversation_to_db(user_id, channel_id, turn_data)
            
            # 檢查是否需要整理記憶
            self._manage_memory_overflow(conversation_key)
            
        except Exception as e:
            logger.error(f"添加對話記錄失敗: {e}")
    
    def get_conversation_context(self, user_id: str, channel_id: str, context_length: int = 5) -> str:
        """獲取對話上下文"""
        try:
            conversation_key = f"{user_id}_{channel_id}"
            context_parts = []
            
            # 1. 獲取對話摘要（長期記憶）
            summary = self._get_conversation_summary(user_id, channel_id)
            if summary:
                context_parts.append(f"【對話歷史摘要】{summary}")
            
            # 2. 獲取最近的對話記錄（短期記憶）
            recent_conversations = self._get_recent_conversations(user_id, channel_id, context_length)
            if recent_conversations:
                conversation_history = []
                for turn in recent_conversations:
                    conversation_history.append(f"用戶: {turn['user_message']}")
                    conversation_history.append(f"AI: {turn['ai_response']}")
                
                context_parts.append(f"【最近對話】\n" + "\n".join(conversation_history))
            
            # 3. 獲取重要話題和關鍵字
            important_topics = self._extract_important_topics(user_id, channel_id)
            if important_topics:
                context_parts.append(f"【重要話題】{', '.join(important_topics)}")
            
            return "\n\n".join(context_parts) if context_parts else ""
            
        except Exception as e:
            logger.error(f"獲取對話上下文失敗: {e}")
            return ""
    
    def create_conversation_summary(self, user_id: str, channel_id: str, conversations: List[Dict]) -> str:
        """創建對話摘要"""
        try:
            if not conversations:
                return ""
            
            # 提取關鍵資訊
            topics = []
            user_interests = []
            important_facts = []
            
            for turn in conversations:
                user_msg = turn.get('user_message', '')
                ai_msg = turn.get('ai_response', '')
                
                # 簡單的關鍵字提取（可以用更複雜的 NLP 方法）
                keywords = self._extract_keywords(user_msg + " " + ai_msg)
                topics.extend(keywords)
                
                # 檢測用戶興趣和偏好
                interests = self._detect_user_interests(user_msg)
                user_interests.extend(interests)
                
                # 檢測重要事實
                facts = self._detect_important_facts(user_msg, ai_msg)
                important_facts.extend(facts)
            
            # 創建摘要
            summary_parts = []
            
            if topics:
                unique_topics = list(set(topics))[:10]  # 最多10個話題
                summary_parts.append(f"討論話題: {', '.join(unique_topics)}")
            
            if user_interests:
                unique_interests = list(set(user_interests))[:5]
                summary_parts.append(f"用戶興趣: {', '.join(unique_interests)}")
            
            if important_facts:
                summary_parts.append(f"重要事實: {'; '.join(important_facts[:3])}")  # 最多3個重要事實
            
            # 添加對話統計
            summary_parts.append(f"對話輪數: {len(conversations)}")
            summary_parts.append(f"時間範圍: {conversations[0]['timestamp'][:10]} 至 {conversations[-1]['timestamp'][:10]}")
            
            return " | ".join(summary_parts)
            
        except Exception as e:
            logger.error(f"創建對話摘要失敗: {e}")
            return ""
    
    def get_conversation_insights(self, user_id: str, channel_id: str) -> Dict[str, Any]:
        """獲取對話洞察分析"""
        try:
            insights = {
                "total_conversations": 0,
                "common_topics": [],
                "user_patterns": {},
                "conversation_frequency": {},
                "latest_interests": []
            }
            
            # 從資料庫獲取對話記錄
            interactions = user_db.get_user_interactions(user_id, limit=100)
            message_interactions = [i for i in interactions if i['type'] in ['message', 'ai_response']]
            
            insights["total_conversations"] = len(message_interactions)
            
            if message_interactions:
                # 分析對話模式
                insights["user_patterns"] = self._analyze_conversation_patterns(message_interactions)
                
                # 提取常見話題
                all_content = []
                for interaction in message_interactions[-20:]:  # 分析最近20條
                    if interaction['content']:
                        all_content.append(interaction['content'])
                
                insights["common_topics"] = self._extract_keywords(" ".join(all_content))[:10]
                
                # 分析對話頻率
                insights["conversation_frequency"] = self._analyze_frequency(message_interactions)
                
                # 最新興趣
                recent_messages = [i['content'] for i in message_interactions[-10:] if i['content']]
                insights["latest_interests"] = self._detect_user_interests(" ".join(recent_messages))
            
            return insights
            
        except Exception as e:
            logger.error(f"獲取對話洞察失敗: {e}")
            return {}
    
    def clear_old_conversations(self, user_id: str, channel_id: str, days_to_keep: int = 7):
        """清理舊對話記錄"""
        try:
            conversation_key = f"{user_id}_{channel_id}"
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            
            if conversation_key in self.short_term_memory:
                # 保留最近的對話
                recent_conversations = []
                old_conversations = []
                
                for turn in self.short_term_memory[conversation_key]:
                    turn_date = datetime.fromisoformat(turn['timestamp'].replace('Z', '+00:00'))
                    if turn_date > cutoff_date:
                        recent_conversations.append(turn)
                    else:
                        old_conversations.append(turn)
                
                # 為舊對話創建摘要
                if old_conversations:
                    summary = self.create_conversation_summary(user_id, channel_id, old_conversations)
                    if summary:
                        self._save_conversation_summary(user_id, channel_id, summary)
                
                # 只保留最近的對話
                self.short_term_memory[conversation_key] = recent_conversations
                
                logger.info(f"清理了 {len(old_conversations)} 條舊對話記錄，創建了摘要")
            
        except Exception as e:
            logger.error(f"清理舊對話記錄失敗: {e}")
    
    def _generate_turn_id(self, user_id: str, channel_id: str, timestamp: str) -> str:
        """生成對話輪次ID"""
        content = f"{user_id}_{channel_id}_{timestamp}"
        return hashlib.md5(content.encode()).hexdigest()[:8]
    
    def _save_conversation_to_db(self, user_id: str, channel_id: str, turn_data: Dict):
        """保存對話記錄到資料庫"""
        try:
            user_db.log_interaction(
                user_id=user_id,
                interaction_type="conversation_turn",
                content=json.dumps(turn_data, ensure_ascii=False),
                metadata={
                    "channel_id": channel_id,
                    "turn_id": turn_data["turn_id"]
                }
            )
        except Exception as e:
            logger.error(f"保存對話記錄到資料庫失敗: {e}")
    
    def _get_conversation_summary(self, user_id: str, channel_id: str) -> str:
        """獲取對話摘要"""
        try:
            # 從用戶資料中獲取對話摘要
            summary_key = f"conversation_summary_{channel_id}"
            return user_db.get_user_data(user_id, summary_key) or ""
        except Exception as e:
            logger.error(f"獲取對話摘要失敗: {e}")
            return ""
    
    def _save_conversation_summary(self, user_id: str, channel_id: str, summary: str):
        """保存對話摘要"""
        try:
            summary_key = f"conversation_summary_{channel_id}"
            user_db.set_user_data(user_id, summary_key, summary, "text")
        except Exception as e:
            logger.error(f"保存對話摘要失敗: {e}")
    
    def _get_recent_conversations(self, user_id: str, channel_id: str, limit: int) -> List[Dict]:
        """獲取最近的對話記錄"""
        try:
            conversation_key = f"{user_id}_{channel_id}"
            if conversation_key in self.short_term_memory:
                return self.short_term_memory[conversation_key][-limit:]
            return []
        except Exception as e:
            logger.error(f"獲取最近對話記錄失敗: {e}")
            return []
    
    def _extract_important_topics(self, user_id: str, channel_id: str) -> List[str]:
        """提取重要話題"""
        try:
            # 從最近的對話中提取重要話題
            recent_conversations = self._get_recent_conversations(user_id, channel_id, 10)
            all_text = ""
            
            for turn in recent_conversations:
                all_text += turn.get('user_message', '') + " " + turn.get('ai_response', '')
            
            return self._extract_keywords(all_text)[:5]  # 返回前5個重要話題
            
        except Exception as e:
            logger.error(f"提取重要話題失敗: {e}")
            return []
    
    def _extract_keywords(self, text: str) -> List[str]:
        """提取關鍵字（簡單版本）"""
        try:
            # 簡單的關鍵字提取，可以升級為更複雜的 NLP 方法
            import re
            
            # 移除標點符號和特殊字符
            cleaned_text = re.sub(r'[^\w\s]', '', text.lower())
            words = cleaned_text.split()
            
            # 過濾常見詞彙
            stop_words = {
                '的', '是', '在', '了', '和', '有', '我', '你', '他', '她', '它', '們', '這', '那', '個', '一', '二', '三',
                'the', 'is', 'in', 'and', 'to', 'a', 'of', 'for', 'as', 'with', 'on', 'by', 'at', 'an', 'be', 'or',
                '嗎', '呢', '吧', '啊', '喔', '哦', '欸', '嗯', '好', '對', '不', '沒', '會', '要', '可以', '可能',
                'what', 'how', 'when', 'where', 'why', 'who', 'can', 'will', 'would', 'could', 'should', 'may'
            }
            
            # 計算詞頻
            word_freq = {}
            for word in words:
                if len(word) > 1 and word not in stop_words:  # 過濾單字元和停用詞
                    word_freq[word] = word_freq.get(word, 0) + 1
            
            # 返回頻率最高的詞彙
            sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
            return [word for word, freq in sorted_words[:20] if freq > 1]
            
        except Exception as e:
            logger.error(f"提取關鍵字失敗: {e}")
            return []
    
    def _detect_user_interests(self, text: str) -> List[str]:
        """檢測用戶興趣"""
        try:
            interests = []
            text_lower = text.lower()
            
            # 技術興趣
            tech_keywords = {
                'python': 'Python程式設計',
                'javascript': 'JavaScript開發',
                'ai': '人工智慧',
                'machine learning': '機器學習',
                'programming': '程式設計',
                'coding': '編程',
                'discord bot': 'Discord機器人開發',
                'web development': '網頁開發'
            }
            
            # 生活興趣
            life_keywords = {
                '咖啡': '咖啡愛好',
                '音樂': '音樂',
                '電影': '電影',
                '遊戲': '遊戲',
                '旅遊': '旅行',
                '運動': '運動',
                '攝影': '攝影',
                '美食': '美食'
            }
            
            # 檢查技術關鍵字
            for keyword, interest in tech_keywords.items():
                if keyword in text_lower:
                    interests.append(interest)
            
            # 檢查生活關鍵字
            for keyword, interest in life_keywords.items():
                if keyword in text_lower:
                    interests.append(interest)
            
            return list(set(interests))  # 去重
            
        except Exception as e:
            logger.error(f"檢測用戶興趣失敗: {e}")
            return []
    
    def _detect_important_facts(self, user_msg: str, ai_msg: str) -> List[str]:
        """檢測重要事實"""
        try:
            facts = []
            
            # 檢測用戶提到的重要資訊
            fact_patterns = [
                r'我(是|叫|叫做)([^，。！？\s]+)',  # 姓名
                r'我(在|住在|來自)([^，。！？\s]+)',  # 地點
                r'我(做|工作是|職業是)([^，。！？\s]+)',  # 職業
                r'我(學|讀|念)([^，。！？\s]+)',  # 學習
                r'我(喜歡|愛|熱愛)([^，。！？\s]+)',  # 興趣愛好
            ]
            
            import re
            for pattern in fact_patterns:
                matches = re.findall(pattern, user_msg)
                for match in matches:
                    if isinstance(match, tuple) and len(match) >= 2:
                        facts.append(f"{match[0]}{match[1]}")
            
            return facts
            
        except Exception as e:
            logger.error(f"檢測重要事實失敗: {e}")
            return []
    
    def _analyze_conversation_patterns(self, interactions: List[Dict]) -> Dict[str, Any]:
        """分析對話模式"""
        try:
            patterns = {
                "avg_message_length": 0,
                "most_active_hours": [],
                "conversation_topics": {},
                "response_sentiment": {}
            }
            
            if not interactions:
                return patterns
            
            # 分析訊息長度
            message_lengths = []
            for interaction in interactions:
                if interaction['content']:
                    message_lengths.append(len(interaction['content']))
            
            if message_lengths:
                patterns["avg_message_length"] = sum(message_lengths) / len(message_lengths)
            
            # 分析活躍時間
            hour_counts = {}
            for interaction in interactions:
                try:
                    created_at = interaction['created_at']
                    # 提取小時（假設格式為 YYYY-MM-DD HH:MM:SS）
                    hour = created_at.split(' ')[1].split(':')[0] if ' ' in created_at else '12'
                    hour_counts[hour] = hour_counts.get(hour, 0) + 1
                except:
                    continue
            
            if hour_counts:
                sorted_hours = sorted(hour_counts.items(), key=lambda x: x[1], reverse=True)
                patterns["most_active_hours"] = [hour for hour, count in sorted_hours[:3]]
            
            return patterns
            
        except Exception as e:
            logger.error(f"分析對話模式失敗: {e}")
            return {}
    
    def _analyze_frequency(self, interactions: List[Dict]) -> Dict[str, int]:
        """分析對話頻率"""
        try:
            frequency = {
                "daily_avg": 0,
                "weekly_total": 0,
                "peak_day": ""
            }
            
            if not interactions:
                return frequency
            
            # 按日期分組
            daily_counts = {}
            for interaction in interactions:
                try:
                    date = interaction['created_at'][:10]  # YYYY-MM-DD
                    daily_counts[date] = daily_counts.get(date, 0) + 1
                except:
                    continue
            
            if daily_counts:
                frequency["weekly_total"] = len(interactions)
                frequency["daily_avg"] = len(interactions) / len(daily_counts)
                
                # 找出最活躍的一天
                peak_day = max(daily_counts.items(), key=lambda x: x[1])
                frequency["peak_day"] = peak_day[0]
            
            return frequency
            
        except Exception as e:
            logger.error(f"分析對話頻率失敗: {e}")
            return {}
    
    def _manage_memory_overflow(self, conversation_key: str, max_turns: int = 50):
        """管理記憶體溢出"""
        try:
            if conversation_key in self.short_term_memory:
                turns = self.short_term_memory[conversation_key]
                
                if len(turns) > max_turns:
                    # 提取用戶ID和頻道ID
                    user_id, channel_id = conversation_key.split('_', 1)
                    
                    # 為舊對話創建摘要
                    old_turns = turns[:-max_turns//2]  # 保留一半最新的對話
                    summary = self.create_conversation_summary(user_id, channel_id, old_turns)
                    
                    if summary:
                        self._save_conversation_summary(user_id, channel_id, summary)
                    
                    # 只保留最新的對話
                    self.short_term_memory[conversation_key] = turns[-max_turns//2:]
                    
                    logger.info(f"記憶體整理完成，保留 {len(self.short_term_memory[conversation_key])} 輪對話")
            
        except Exception as e:
            logger.error(f"管理記憶體溢出失敗: {e}")

# 創建全域實例
conversation_memory = ConversationMemory()