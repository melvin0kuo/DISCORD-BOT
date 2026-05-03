import sqlite3
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
import os

logger = logging.getLogger(__name__)

class UserDatabase:
    """用戶資料庫管理類"""
    
    def __init__(self, db_path: str = "user_memory.db"):
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """初始化資料庫表格"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 創建用戶基本資訊表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS users (
                        user_id TEXT PRIMARY KEY,
                        username TEXT NOT NULL,
                        display_name TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        is_active INTEGER DEFAULT 1
                    )
                ''')
                
                # 創建用戶資料表（鍵值對形式存儲自定義資料）
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS user_data (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id TEXT NOT NULL,
                        data_key TEXT NOT NULL,
                        data_value TEXT,
                        data_type TEXT DEFAULT 'text',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users (user_id),
                        UNIQUE(user_id, data_key)
                    )
                ''')
                
                # 創建用戶標籤表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS user_tags (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id TEXT NOT NULL,
                        tag_name TEXT NOT NULL,
                        tag_value TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users (user_id),
                        UNIQUE(user_id, tag_name)
                    )
                ''')
                
                # 創建用戶互動記錄表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS user_interactions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id TEXT NOT NULL,
                        interaction_type TEXT NOT NULL,
                        content TEXT,
                        metadata TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users (user_id)
                    )
                ''')
                
                # 創建索引以提升查詢效能
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_data_user_id ON user_data(user_id)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_tags_user_id ON user_tags(user_id)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_interactions_user_id ON user_interactions(user_id)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_interactions_type ON user_interactions(interaction_type)')
                
                conn.commit()
                logger.info("用戶資料庫初始化完成")
                
        except sqlite3.Error as e:
            logger.error(f"初始化資料庫失敗: {e}")
            raise
    
    def add_or_update_user(self, user_id: str, username: str, display_name: str = None) -> bool:
        """新增或更新用戶基本資訊"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 檢查用戶是否已存在
                cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,))
                exists = cursor.fetchone()
                
                if exists:
                    # 更新現有用戶
                    cursor.execute('''
                        UPDATE users 
                        SET username = ?, display_name = ?, updated_at = CURRENT_TIMESTAMP 
                        WHERE user_id = ?
                    ''', (username, display_name, user_id))
                    logger.info(f"更新用戶資訊: {user_id}")
                else:
                    # 新增用戶
                    cursor.execute('''
                        INSERT INTO users (user_id, username, display_name) 
                        VALUES (?, ?, ?)
                    ''', (user_id, username, display_name))
                    logger.info(f"新增用戶: {user_id}")
                
                conn.commit()
                return True
                
        except sqlite3.Error as e:
            logger.error(f"新增/更新用戶失敗: {e}")
            return False
    
    def set_user_data(self, user_id: str, data_key: str, data_value: Any, data_type: str = 'text') -> bool:
        """設置用戶資料"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 將複雜資料類型轉換為 JSON 字符串
                if data_type in ['dict', 'list', 'json']:
                    value_str = json.dumps(data_value, ensure_ascii=False)
                else:
                    value_str = str(data_value)
                
                # 使用 INSERT OR REPLACE 來處理更新
                cursor.execute('''
                    INSERT OR REPLACE INTO user_data 
                    (user_id, data_key, data_value, data_type, updated_at) 
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ''', (user_id, data_key, value_str, data_type))
                
                conn.commit()
                logger.info(f"設置用戶資料: {user_id} -> {data_key}")
                return True
                
        except sqlite3.Error as e:
            logger.error(f"設置用戶資料失敗: {e}")
            return False
    
    def get_user_data(self, user_id: str, data_key: str = None) -> Optional[Any]:
        """獲取用戶資料"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                if data_key:
                    # 獲取特定鍵的資料
                    cursor.execute('''
                        SELECT data_value, data_type FROM user_data 
                        WHERE user_id = ? AND data_key = ?
                    ''', (user_id, data_key))
                    result = cursor.fetchone()
                    
                    if result:
                        value_str, data_type = result
                        return self._parse_value(value_str, data_type)
                    return None
                else:
                    # 獲取所有資料
                    cursor.execute('''
                        SELECT data_key, data_value, data_type FROM user_data 
                        WHERE user_id = ?
                    ''', (user_id,))
                    results = cursor.fetchall()
                    
                    user_data = {}
                    for key, value_str, data_type in results:
                        user_data[key] = self._parse_value(value_str, data_type)
                    
                    return user_data
                    
        except sqlite3.Error as e:
            logger.error(f"獲取用戶資料失敗: {e}")
            return None
    
    def get_all_user_data(self, user_id: str) -> List[Dict[str, Any]]:
        """獲取用戶所有資料（以列表格式返回）"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT data_key, data_value, data_type, created_at, updated_at
                    FROM user_data
                    WHERE user_id = ?
                    ORDER BY updated_at DESC
                ''', (user_id,))
                
                results = cursor.fetchall()
                user_data_list = []
                
                for data_key, data_value, data_type, created_at, updated_at in results:
                    parsed_value = self._parse_value(data_value, data_type)
                    user_data_list.append({
                        'data_key': data_key,
                        'data_value': parsed_value,
                        'data_type': data_type,
                        'created_at': created_at,
                        'updated_at': updated_at
                    })
                
                return user_data_list
                
        except sqlite3.Error as e:
            logger.error(f"獲取用戶所有資料失敗: {e}")
            return []
    
    def delete_user_data(self, user_id: str, data_key: str = None) -> bool:
        """刪除用戶資料"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                if data_key:
                    # 刪除特定鍵的資料
                    cursor.execute('''
                        DELETE FROM user_data WHERE user_id = ? AND data_key = ?
                    ''', (user_id, data_key))
                    logger.info(f"刪除用戶資料: {user_id} -> {data_key}")
                else:
                    # 刪除所有資料
                    cursor.execute('DELETE FROM user_data WHERE user_id = ?', (user_id,))
                    logger.info(f"刪除用戶所有資料: {user_id}")
                
                conn.commit()
                return True
                
        except sqlite3.Error as e:
            logger.error(f"刪除用戶資料失敗: {e}")
            return False
    
    def add_user_tag(self, user_id: str, tag_name: str, tag_value: str = None) -> bool:
        """新增用戶標籤"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT OR REPLACE INTO user_tags (user_id, tag_name, tag_value) 
                    VALUES (?, ?, ?)
                ''', (user_id, tag_name, tag_value))
                
                conn.commit()
                logger.info(f"新增用戶標籤: {user_id} -> {tag_name}")
                return True
                
        except sqlite3.Error as e:
            logger.error(f"新增用戶標籤失敗: {e}")
            return False
    
    def get_user_tags(self, user_id: str) -> List[Dict[str, str]]:
        """獲取用戶標籤"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT tag_name, tag_value, created_at FROM user_tags 
                    WHERE user_id = ? ORDER BY created_at DESC
                ''', (user_id,))
                
                results = cursor.fetchall()
                return [
                    {
                        'name': tag_name,
                        'value': tag_value,
                        'created_at': created_at
                    }
                    for tag_name, tag_value, created_at in results
                ]
                
        except sqlite3.Error as e:
            logger.error(f"獲取用戶標籤失敗: {e}")
            return []
    
    def remove_user_tag(self, user_id: str, tag_name: str) -> bool:
        """移除用戶標籤"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    DELETE FROM user_tags WHERE user_id = ? AND tag_name = ?
                ''', (user_id, tag_name))
                
                conn.commit()
                logger.info(f"移除用戶標籤: {user_id} -> {tag_name}")
                return True
                
        except sqlite3.Error as e:
            logger.error(f"移除用戶標籤失敗: {e}")
            return False
    
    def log_interaction(self, user_id: str, interaction_type: str, content: str = None, metadata: Dict = None) -> bool:
        """記錄用戶互動"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                metadata_str = json.dumps(metadata, ensure_ascii=False) if metadata else None
                
                cursor.execute('''
                    INSERT INTO user_interactions (user_id, interaction_type, content, metadata) 
                    VALUES (?, ?, ?, ?)
                ''', (user_id, interaction_type, content, metadata_str))
                
                conn.commit()
                return True
                
        except sqlite3.Error as e:
            logger.error(f"記錄用戶互動失敗: {e}")
            return False
    
    def get_user_interactions(self, user_id: str, interaction_type: str = None, limit: int = 50) -> List[Dict]:
        """獲取用戶互動記錄"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                if interaction_type:
                    cursor.execute('''
                        SELECT interaction_type, content, metadata, created_at 
                        FROM user_interactions 
                        WHERE user_id = ? AND interaction_type = ? 
                        ORDER BY created_at DESC LIMIT ?
                    ''', (user_id, interaction_type, limit))
                else:
                    cursor.execute('''
                        SELECT interaction_type, content, metadata, created_at 
                        FROM user_interactions 
                        WHERE user_id = ? 
                        ORDER BY created_at DESC LIMIT ?
                    ''', (user_id, limit))
                
                results = cursor.fetchall()
                interactions = []
                
                for interaction_type, content, metadata_str, created_at in results:
                    metadata = json.loads(metadata_str) if metadata_str else {}
                    interactions.append({
                        'type': interaction_type,
                        'content': content,
                        'metadata': metadata,
                        'created_at': created_at
                    })
                
                return interactions
                
        except sqlite3.Error as e:
            logger.error(f"獲取用戶互動記錄失敗: {e}")
            return []
    
    def get_user_info(self, user_id: str) -> Optional[Dict]:
        """獲取用戶完整資訊"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 獲取基本資訊
                cursor.execute('''
                    SELECT username, display_name, created_at, updated_at, is_active 
                    FROM users WHERE user_id = ?
                ''', (user_id,))
                user_result = cursor.fetchone()
                
                if not user_result:
                    return None
                
                username, display_name, created_at, updated_at, is_active = user_result
                
                return {
                    'user_id': user_id,
                    'username': username,
                    'display_name': display_name,
                    'created_at': created_at,
                    'updated_at': updated_at,
                    'is_active': bool(is_active),
                    'data': self.get_user_data(user_id),
                    'tags': self.get_user_tags(user_id)
                }
                
        except sqlite3.Error as e:
            logger.error(f"獲取用戶資訊失敗: {e}")
            return None
    
    def search_users(self, query: str, search_type: str = 'username') -> List[Dict]:
        """搜尋用戶"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                if search_type == 'username':
                    cursor.execute('''
                        SELECT user_id, username, display_name 
                        FROM users 
                        WHERE username LIKE ? OR display_name LIKE ? 
                        ORDER BY username
                    ''', (f'%{query}%', f'%{query}%'))
                elif search_type == 'tag':
                    cursor.execute('''
                        SELECT DISTINCT u.user_id, u.username, u.display_name 
                        FROM users u 
                        JOIN user_tags t ON u.user_id = t.user_id 
                        WHERE t.tag_name LIKE ? OR t.tag_value LIKE ?
                        ORDER BY u.username
                    ''', (f'%{query}%', f'%{query}%'))
                elif search_type == 'data':
                    cursor.execute('''
                        SELECT DISTINCT u.user_id, u.username, u.display_name 
                        FROM users u 
                        JOIN user_data d ON u.user_id = d.user_id 
                        WHERE d.data_key LIKE ? OR d.data_value LIKE ?
                        ORDER BY u.username
                    ''', (f'%{query}%', f'%{query}%'))
                
                results = cursor.fetchall()
                return [
                    {
                        'user_id': user_id,
                        'username': username,
                        'display_name': display_name
                    }
                    for user_id, username, display_name in results
                ]
                
        except sqlite3.Error as e:
            logger.error(f"搜尋用戶失敗: {e}")
            return []
    
    def _parse_value(self, value_str: str, data_type: str) -> Any:
        """解析資料值"""
        try:
            if data_type in ['dict', 'list', 'json']:
                return json.loads(value_str)
            elif data_type == 'int':
                return int(value_str)
            elif data_type == 'float':
                return float(value_str)
            elif data_type == 'bool':
                return value_str.lower() in ('true', '1', 'yes')
            else:
                return value_str
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"解析資料值失敗: {e}, 返回原始字符串")
            return value_str
    
    def get_database_stats(self) -> Dict:
        """獲取資料庫統計資訊"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 用戶總數
                cursor.execute('SELECT COUNT(*) FROM users')
                total_users = cursor.fetchone()[0]
                
                # 活躍用戶數
                cursor.execute('SELECT COUNT(*) FROM users WHERE is_active = 1')
                active_users = cursor.fetchone()[0]
                
                # 資料項目總數
                cursor.execute('SELECT COUNT(*) FROM user_data')
                total_data_items = cursor.fetchone()[0]
                
                # 標籤總數
                cursor.execute('SELECT COUNT(*) FROM user_tags')
                total_tags = cursor.fetchone()[0]
                
                # 互動記錄總數
                cursor.execute('SELECT COUNT(*) FROM user_interactions')
                total_interactions = cursor.fetchone()[0]
                
                return {
                    'total_users': total_users,
                    'active_users': active_users,
                    'total_data_items': total_data_items,
                    'total_tags': total_tags,
                    'total_interactions': total_interactions,
                    'database_size': os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0
                }
                
        except sqlite3.Error as e:
            logger.error(f"獲取資料庫統計失敗: {e}")
            return {}

# 創建全域資料庫實例
user_db = UserDatabase()