"""
用戶管理 Cog - 處理用戶資料的斜線指令
提供完整的用戶資料管理功能
"""

import discord
from discord.ext import commands
from discord import app_commands
import logging
from typing import Optional, List
import json
from datetime import datetime

from utils.user_database import user_db
from utils.conversation_memory import conversation_memory

logger = logging.getLogger(__name__)

class UserManagement(commands.Cog):
    """用戶資料管理"""
    
    def __init__(self, bot):
        self.bot = bot
        logger.info("用戶管理模組已載入")
    
    @app_commands.command(name="設定個人資料", description="設置用戶的自定義資料")
    @app_commands.describe(
        key="資料鍵名",
        value="資料值",
        user="要設置資料的用戶（留空表示自己）"
    )
    async def set_user_data(
        self,
        interaction: discord.Interaction,
        key: str,
        value: str,
        user: Optional[discord.Member] = None
    ):
        """設置用戶資料"""
        target_user = user or interaction.user
        
        # 權限檢查：只有管理員可以設置其他用戶的資料
        if user and user != interaction.user:
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message("❌ 只有管理員可以設置其他用戶的資料", ephemeral=True)
                return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            # 確保用戶在資料庫中存在
            user_db.add_or_update_user(
                user_id=str(target_user.id),
                username=target_user.name,
                display_name=target_user.display_name
            )
            
            # 統一使用文字格式儲存，讓LLM自動解析
            success = user_db.set_user_data(
                user_id=str(target_user.id),
                data_key=key,
                data_value=value,  # 直接使用原始文字
                data_type="text"   # 統一使用文字類型
            )
            
            if success:
                # 記錄互動
                user_db.log_interaction(
                    user_id=str(target_user.id),
                    interaction_type="data_set",
                    content=f"{key}={value}",
                    metadata={
                        "set_by": str(interaction.user.id),
                        "data_type": "text"
                    }
                )
                
                embed = discord.Embed(
                    title="✅ 資料設置成功",
                    description=f"已為 **{target_user.display_name}** 設置資料",
                    color=discord.Color.green()
                )
                embed.add_field(name="項目", value=f"`{key}`", inline=True)
                embed.add_field(name="內容", value=f"`{value}`", inline=False)
                
                await interaction.followup.send(embed=embed)
            else:
                await interaction.followup.send("❌ 設置資料失敗，請稍後再試")
                
        except Exception as e:
            logger.error(f"設置用戶資料時出錯: {e}")
            await interaction.followup.send(f"❌ 發生錯誤: {str(e)}")
    
    @app_commands.command(name="個人資料", description="查看用戶的資料")
    @app_commands.describe(
        user="要查看資料的用戶（留空表示自己）",
        key="特定資料鍵名（留空顯示所有）"
    )
    async def get_user_data(
        self,
        interaction: discord.Interaction,
        user: Optional[discord.Member] = None,
        key: Optional[str] = None
    ):
        """查看用戶資料"""
        target_user = user or interaction.user
        
        await interaction.response.defer()
        
        try:
            if key:
                # 獲取特定鍵的資料
                data = user_db.get_user_data(str(target_user.id), key)
                
                if data is not None:
                    embed = discord.Embed(
                        title=f"📊 {target_user.display_name} 的資料",
                        color=discord.Color.blue()
                    )
                    embed.add_field(name=key, value=f"`{data}`", inline=False)
                else:
                    embed = discord.Embed(
                        title="❌ 資料不存在",
                        description=f"用戶 **{target_user.display_name}** 沒有鍵名為 `{key}` 的資料",
                        color=discord.Color.red()
                    )
            else:
                # 獲取所有資料
                all_data = user_db.get_user_data(str(target_user.id))
                
                if all_data:
                    embed = discord.Embed(
                        title=f"📊 {target_user.display_name} 的所有資料",
                        color=discord.Color.blue()
                    )
                    
                    # 限制顯示的項目數量
                    items = list(all_data.items())[:25]  # Discord embed 限制
                    
                    for data_key, data_value in items:
                        # 截斷過長的值
                        display_value = str(data_value)
                        if len(display_value) > 100:
                            display_value = display_value[:97] + "..."
                        
                        embed.add_field(
                            name=data_key,
                            value=f"`{display_value}`",
                            inline=True
                        )
                    
                    if len(all_data) > 25:
                        embed.set_footer(text=f"顯示前 25 項，總共 {len(all_data)} 項")
                else:
                    embed = discord.Embed(
                        title="📊 資料空白",
                        description=f"用戶 **{target_user.display_name}** 還沒有任何資料",
                        color=discord.Color.orange()
                    )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"查看用戶資料時出錯: {e}")
            await interaction.followup.send(f"❌ 發生錯誤: {str(e)}")
    
    @app_commands.command(name="刪除個人資料", description="刪除用戶的資料")
    @app_commands.describe(
        key="要刪除的資料鍵名",
        user="目標用戶（留空表示自己）"
    )
    async def delete_user_data(
        self,
        interaction: discord.Interaction,
        key: str,
        user: Optional[discord.Member] = None
    ):
        """刪除用戶資料"""
        target_user = user or interaction.user
        
        # 權限檢查
        if user and user != interaction.user:
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message("❌ 只有管理員可以刪除其他用戶的資料", ephemeral=True)
                return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            # 檢查資料是否存在
            existing_data = user_db.get_user_data(str(target_user.id), key)
            if existing_data is None:
                await interaction.followup.send(f"❌ 用戶 **{target_user.display_name}** 沒有鍵名為 `{key}` 的資料")
                return
            
            # 刪除資料
            success = user_db.delete_user_data(str(target_user.id), key)
            
            if success:
                # 記錄互動
                user_db.log_interaction(
                    user_id=str(target_user.id),
                    interaction_type="data_delete",
                    content=key,
                    metadata={"deleted_by": str(interaction.user.id)}
                )
                
                embed = discord.Embed(
                    title="✅ 資料刪除成功",
                    description=f"已刪除 **{target_user.display_name}** 的資料 `{key}`",
                    color=discord.Color.green()
                )
                await interaction.followup.send(embed=embed)
            else:
                await interaction.followup.send("❌ 刪除資料失敗")
                
        except Exception as e:
            logger.error(f"刪除用戶資料時出錯: {e}")
            await interaction.followup.send(f"❌ 發生錯誤: {str(e)}")
    
    @app_commands.command(name="添加標籤", description="為用戶新增標籤")
    @app_commands.describe(
        tag_name="標籤名稱",
        tag_value="標籤值（可選）",
        user="目標用戶（留空表示自己）"
    )
    async def add_user_tag(
        self,
        interaction: discord.Interaction,
        tag_name: str,
        tag_value: Optional[str] = None,
        user: Optional[discord.Member] = None
    ):
        """新增用戶標籤"""
        target_user = user or interaction.user
        
        # 權限檢查
        if user and user != interaction.user:
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message("❌ 只有管理員可以為其他用戶新增標籤", ephemeral=True)
                return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            # 確保用戶在資料庫中存在
            user_db.add_or_update_user(
                user_id=str(target_user.id),
                username=target_user.name,
                display_name=target_user.display_name
            )
            
            # 新增標籤
            success = user_db.add_user_tag(str(target_user.id), tag_name, tag_value)
            
            if success:
                # 記錄互動
                user_db.log_interaction(
                    user_id=str(target_user.id),
                    interaction_type="tag_add",
                    content=tag_name,
                    metadata={
                        "tag_value": tag_value,
                        "added_by": str(interaction.user.id)
                    }
                )
                
                embed = discord.Embed(
                    title="✅ 標籤新增成功",
                    description=f"已為 **{target_user.display_name}** 新增標籤",
                    color=discord.Color.green()
                )
                embed.add_field(name="標籤名稱", value=f"`{tag_name}`", inline=True)
                if tag_value:
                    embed.add_field(name="標籤值", value=f"`{tag_value}`", inline=True)
                
                await interaction.followup.send(embed=embed)
            else:
                await interaction.followup.send("❌ 新增標籤失敗")
                
        except Exception as e:
            logger.error(f"新增用戶標籤時出錯: {e}")
            await interaction.followup.send(f"❌ 發生錯誤: {str(e)}")
    
    @app_commands.command(name="檢視標籤", description="查看用戶的標籤")
    @app_commands.describe(user="目標用戶（留空表示自己）")
    async def get_user_tags(
        self,
        interaction: discord.Interaction,
        user: Optional[discord.Member] = None
    ):
        """查看用戶標籤"""
        target_user = user or interaction.user
        
        await interaction.response.defer()
        
        try:
            tags = user_db.get_user_tags(str(target_user.id))
            
            if tags:
                embed = discord.Embed(
                    title=f"🏷️ {target_user.display_name} 的標籤",
                    color=discord.Color.blue()
                )
                
                for tag in tags[:25]:  # 限制顯示數量
                    value_text = f": `{tag['value']}`" if tag['value'] else ""
                    embed.add_field(
                        name=f"🏷️ {tag['name']}",
                        value=f"建立於: {tag['created_at'][:10]}{value_text}",
                        inline=True
                    )
                
                if len(tags) > 25:
                    embed.set_footer(text=f"顯示前 25 個標籤，總共 {len(tags)} 個")
            else:
                embed = discord.Embed(
                    title="🏷️ 沒有標籤",
                    description=f"用戶 **{target_user.display_name}** 還沒有任何標籤",
                    color=discord.Color.orange()
                )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"查看用戶標籤時出錯: {e}")
            await interaction.followup.send(f"❌ 發生錯誤: {str(e)}")
    
    @app_commands.command(name="移除標籤", description="移除用戶的標籤")
    @app_commands.describe(
        tag_name="要移除的標籤名稱",
        user="目標用戶（留空表示自己）"
    )
    async def remove_user_tag(
        self,
        interaction: discord.Interaction,
        tag_name: str,
        user: Optional[discord.Member] = None
    ):
        """移除用戶標籤"""
        target_user = user or interaction.user
        
        # 權限檢查
        if user and user != interaction.user:
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message("❌ 只有管理員可以移除其他用戶的標籤", ephemeral=True)
                return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            # 移除標籤
            success = user_db.remove_user_tag(str(target_user.id), tag_name)
            
            if success:
                # 記錄互動
                user_db.log_interaction(
                    user_id=str(target_user.id),
                    interaction_type="tag_remove",
                    content=tag_name,
                    metadata={"removed_by": str(interaction.user.id)}
                )
                
                embed = discord.Embed(
                    title="✅ 標籤移除成功",
                    description=f"已移除 **{target_user.display_name}** 的標籤 `{tag_name}`",
                    color=discord.Color.green()
                )
                await interaction.followup.send(embed=embed)
            else:
                await interaction.followup.send(f"❌ 移除標籤失敗或標籤不存在")
                
        except Exception as e:
            logger.error(f"移除用戶標籤時出錯: {e}")
            await interaction.followup.send(f"❌ 發生錯誤: {str(e)}")
    
    @app_commands.command(name="用戶完整資訊", description="查看用戶的完整資訊")
    @app_commands.describe(user="目標用戶（留空表示自己）")
    async def get_user_info(
        self,
        interaction: discord.Interaction,
        user: Optional[discord.Member] = None
    ):
        """查看用戶完整資訊"""
        target_user = user or interaction.user
        
        await interaction.response.defer()
        
        try:
            user_info = user_db.get_user_info(str(target_user.id))
            
            if not user_info:
                embed = discord.Embed(
                    title="❌ 用戶資訊不存在",
                    description=f"用戶 **{target_user.display_name}** 的資訊不存在於資料庫中",
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=embed)
                return
            
            embed = discord.Embed(
                title=f"👤 {target_user.display_name} 的完整資訊",
                color=discord.Color.blue()
            )
            
            # 基本資訊
            embed.add_field(
                name="📋 基本資訊",
                value=(
                    f"**用戶名**: {user_info['username']}\n"
                    f"**顯示名稱**: {user_info['display_name']}\n"
                    f"**ID**: {user_info['user_id']}\n"
                    f"**建立時間**: {user_info['created_at'][:19]}\n"
                    f"**更新時間**: {user_info['updated_at'][:19]}\n"
                    f"**狀態**: {'🟢 活躍' if user_info['is_active'] else '🔴 非活躍'}"
                ),
                inline=False
            )
            
            # 資料統計
            data_count = len(user_info['data']) if user_info['data'] else 0
            tag_count = len(user_info['tags']) if user_info['tags'] else 0
            
            embed.add_field(
                name="📊 統計資訊",
                value=f"**自定義資料**: {data_count} 項\n**標籤**: {tag_count} 個",
                inline=True
            )
            
            # 最近互動
            recent_interactions = user_db.get_user_interactions(str(target_user.id), limit=3)
            if recent_interactions:
                interaction_text = []
                for inter in recent_interactions:
                    interaction_text.append(f"• {inter['type']} ({inter['created_at'][:10]})")
                
                embed.add_field(
                    name="🕒 最近互動",
                    value="\n".join(interaction_text),
                    inline=True
                )
            
            # 設置縮圖
            embed.set_thumbnail(url=target_user.display_avatar.url)
            embed.set_footer(text=f"資料查詢時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"查看用戶完整資訊時出錯: {e}")
            await interaction.followup.send(f"❌ 發生錯誤: {str(e)}")
    
    @app_commands.command(name="搜尋用戶", description="搜尋用戶")
    @app_commands.describe(
        query="搜尋關鍵字",
        search_type="搜尋類型"
    )
    @app_commands.choices(search_type=[
        app_commands.Choice(name="用戶名", value="username"),
        app_commands.Choice(name="標籤", value="tag"),
        app_commands.Choice(name="資料", value="data")
    ])
    async def search_users(
        self,
        interaction: discord.Interaction,
        query: str,
        search_type: str = "username"
    ):
        """搜尋用戶"""
        await interaction.response.defer()
        
        try:
            results = user_db.search_users(query, search_type)
            
            if results:
                embed = discord.Embed(
                    title=f"🔍 搜尋結果 - {query}",
                    description=f"搜尋類型: {search_type} | 找到 {len(results)} 個用戶",
                    color=discord.Color.green()
                )
                
                for i, result in enumerate(results[:20], 1):  # 限制顯示數量
                    embed.add_field(
                        name=f"{i}. {result['display_name'] or result['username']}",
                        value=f"ID: `{result['user_id']}`",
                        inline=True
                    )
                
                if len(results) > 20:
                    embed.set_footer(text=f"顯示前 20 個結果，總共找到 {len(results)} 個")
                    
            else:
                embed = discord.Embed(
                    title="🔍 搜尋結果",
                    description=f"沒有找到與 `{query}` 相關的用戶",
                    color=discord.Color.orange()
                )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"搜尋用戶時出錯: {e}")
            await interaction.followup.send(f"❌ 發生錯誤: {str(e)}")
    
    @app_commands.command(name="資料庫統計", description="顯示用戶資料庫統計資訊")
    async def database_stats(self, interaction: discord.Interaction):
        """顯示資料庫統計資訊"""
        # 權限檢查
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ 只有管理員可以查看資料庫統計", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        try:
            stats = user_db.get_database_stats()
            
            embed = discord.Embed(
                title="📊 用戶資料庫統計",
                color=discord.Color.blue()
            )
            
            embed.add_field(
                name="👥 用戶統計",
                value=(
                    f"**總用戶數**: {stats.get('total_users', 0)}\n"
                    f"**活躍用戶**: {stats.get('active_users', 0)}\n"
                    f"**活躍率**: {(stats.get('active_users', 0) / max(stats.get('total_users', 1), 1) * 100):.1f}%"
                ),
                inline=True
            )
            
            embed.add_field(
                name="📁 資料統計",
                value=(
                    f"**資料項目**: {stats.get('total_data_items', 0)}\n"
                    f"**標籤總數**: {stats.get('total_tags', 0)}\n"
                    f"**互動記錄**: {stats.get('total_interactions', 0)}"
                ),
                inline=True
            )
            
            # 資料庫大小
            db_size = stats.get('database_size', 0)
            if db_size > 1024 * 1024:
                size_text = f"{db_size / 1024 / 1024:.2f} MB"
            elif db_size > 1024:
                size_text = f"{db_size / 1024:.2f} KB"
            else:
                size_text = f"{db_size} bytes"
            
            embed.add_field(
                name="💾 資料庫資訊",
                value=f"**檔案大小**: {size_text}",
                inline=True
            )
            
            embed.set_footer(text=f"統計時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"獲取資料庫統計時出錯: {e}")
            await interaction.followup.send(f"❌ 發生錯誤: {str(e)}")
    
    def _parse_input_value(self, value: str, data_type: str = "text"):
        """保留此方法以維持向後相容性，但現在統一返回文字"""
        return value  # 統一使用文字格式，由LLM自動理解內容
    
    @commands.Cog.listener()
    async def on_member_join(self, member):
        """新成員加入時自動建立用戶記錄"""
        try:
            user_db.add_or_update_user(
                user_id=str(member.id),
                username=member.name,
                display_name=member.display_name
            )
            
            user_db.log_interaction(
                user_id=str(member.id),
                interaction_type="member_join",
                metadata={"guild_id": str(member.guild.id)}
            )
            
            logger.info(f"新成員 {member.name} 已加入資料庫")
            
        except Exception as e:
            logger.error(f"處理新成員加入事件時出錯: {e}")
    
    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        """成員資訊更新時同步到資料庫"""
        try:
            if before.display_name != after.display_name or before.name != after.name:
                user_db.add_or_update_user(
                    user_id=str(after.id),
                    username=after.name,
                    display_name=after.display_name
                )
                
                logger.info(f"用戶 {after.name} 資訊已更新")
                
        except Exception as e:
            logger.error(f"處理成員更新事件時出錯: {e}")
    
    @app_commands.command(name="設置記憶", description="設置用戶的個人記憶")
    @app_commands.describe(
        memory="要設置的記憶內容",
        user="目標用戶（留空表示自己）"
    )
    async def set_user_memory(
        self,
        interaction: discord.Interaction,
        memory: str,
        user: Optional[discord.Member] = None
    ):
        """設置用戶記憶"""
        target_user = user or interaction.user
        
        # 權限檢查
        if user and user != interaction.user:
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message("❌ 只有管理員可以設置其他用戶的記憶", ephemeral=True)
                return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            # 確保用戶在資料庫中存在
            user_db.add_or_update_user(
                user_id=str(target_user.id),
                username=target_user.name,
                display_name=target_user.display_name
            )
            
            # 設置記憶（使用特殊的鍵名）
            success = user_db.set_user_data(
                user_id=str(target_user.id),
                data_key="personal_memory",
                data_value=memory,
                data_type="text"
            )
            
            if success:
                # 記錄互動
                user_db.log_interaction(
                    user_id=str(target_user.id),
                    interaction_type="memory_set",
                    content=memory[:100] + "..." if len(memory) > 100 else memory,
                    metadata={"set_by": str(interaction.user.id)}
                )
                
                embed = discord.Embed(
                    title="🧠 記憶設置成功",
                    description=f"已為 **{target_user.display_name}** 設置個人記憶",
                    color=discord.Color.green()
                )
                embed.add_field(
                    name="記憶內容",
                    value=memory[:500] + "..." if len(memory) > 500 else memory,
                    inline=False
                )
                
                await interaction.followup.send(embed=embed)
            else:
                await interaction.followup.send("❌ 設置記憶失敗，請稍後再試")
                
        except Exception as e:
            logger.error(f"設置用戶記憶時出錯: {e}")
            await interaction.followup.send(f"❌ 發生錯誤: {str(e)}")
    
    @app_commands.command(name="查看記憶", description="查看用戶的個人記憶")
    @app_commands.describe(user="目標用戶（留空表示自己）")
    async def get_user_memory(
        self,
        interaction: discord.Interaction,
        user: Optional[discord.Member] = None
    ):
        """查看用戶記憶"""
        target_user = user or interaction.user
        
        await interaction.response.defer()
        
        try:
            memory = user_db.get_user_data(str(target_user.id), "personal_memory")
            
            if memory:
                embed = discord.Embed(
                    title=f"🧠 {target_user.display_name} 的個人記憶",
                    description=memory,
                    color=discord.Color.blue()
                )
                embed.set_thumbnail(url=target_user.display_avatar.url)
            else:
                embed = discord.Embed(
                    title="🧠 沒有記憶",
                    description=f"用戶 **{target_user.display_name}** 還沒有設置個人記憶",
                    color=discord.Color.orange()
                )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"查看用戶記憶時出錯: {e}")
            await interaction.followup.send(f"❌ 發生錯誤: {str(e)}")
    
    @app_commands.command(name="清除記憶", description="清除用戶的個人記憶")
    @app_commands.describe(user="目標用戶（留空表示自己）")
    async def clear_user_memory(
        self,
        interaction: discord.Interaction,
        user: Optional[discord.Member] = None
    ):
        """清除用戶記憶"""
        target_user = user or interaction.user
        
        # 權限檢查
        if user and user != interaction.user:
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message("❌ 只有管理員可以清除其他用戶的記憶", ephemeral=True)
                return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            # 檢查記憶是否存在
            existing_memory = user_db.get_user_data(str(target_user.id), "personal_memory")
            if not existing_memory:
                await interaction.followup.send(f"❌ 用戶 **{target_user.display_name}** 沒有設置記憶")
                return
            
            # 刪除記憶
            success = user_db.delete_user_data(str(target_user.id), "personal_memory")
            
            if success:
                # 記錄互動
                user_db.log_interaction(
                    user_id=str(target_user.id),
                    interaction_type="memory_clear",
                    metadata={"cleared_by": str(interaction.user.id)}
                )
                
                embed = discord.Embed(
                    title="🧠 記憶清除成功",
                    description=f"已清除 **{target_user.display_name}** 的個人記憶",
                    color=discord.Color.green()
                )
                await interaction.followup.send(embed=embed)
            else:
                await interaction.followup.send("❌ 清除記憶失敗")
                
        except Exception as e:
            logger.error(f"清除用戶記憶時出錯: {e}")
            await interaction.followup.send(f"❌ 發生錯誤: {str(e)}")
    
    @app_commands.command(name="記憶歷史", description="查看用戶記憶的歷史記錄")
    @app_commands.describe(user="目標用戶（留空表示自己）")
    async def get_memory_history(
        self,
        interaction: discord.Interaction,
        user: Optional[discord.Member] = None
    ):
        """查看用戶記憶歷史"""
        target_user = user or interaction.user
        
        # 權限檢查（只有管理員或本人可以查看記憶歷史）
        if user and user != interaction.user:
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message("❌ 只有管理員可以查看其他用戶的記憶歷史", ephemeral=True)
                return
        
        await interaction.response.defer()
        
        try:
            # 獲取記憶相關的互動記錄
            interactions = user_db.get_user_interactions(
                str(target_user.id),
                limit=20
            )
            
            # 篩選記憶相關的互動
            memory_interactions = [
                inter for inter in interactions
                if inter['type'] in ['memory_set', 'memory_clear']
            ]
            
            if memory_interactions:
                embed = discord.Embed(
                    title=f"🧠 {target_user.display_name} 的記憶歷史",
                    color=discord.Color.blue()
                )
                
                for i, inter in enumerate(memory_interactions[:10], 1):
                    type_emoji = "📝" if inter['type'] == 'memory_set' else "🗑️"
                    type_text = "設置記憶" if inter['type'] == 'memory_set' else "清除記憶"
                    
                    content = inter['content'] if inter['content'] else "（無內容）"
                    if len(content) > 50:
                        content = content[:47] + "..."
                    
                    embed.add_field(
                        name=f"{type_emoji} {type_text} #{i}",
                        value=f"時間: {inter['created_at'][:19]}\n內容: {content}",
                        inline=True
                    )
                
                if len(memory_interactions) > 10:
                    embed.set_footer(text=f"顯示最近 10 次記憶操作，總共 {len(memory_interactions)} 次")
            else:
                embed = discord.Embed(
                    title="🧠 沒有記憶歷史",
                    description=f"用戶 **{target_user.display_name}** 還沒有任何記憶操作記錄",
                    color=discord.Color.orange()
                )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"查看記憶歷史時出錯: {e}")
            await interaction.followup.send(f"❌ 發生錯誤: {str(e)}")

async def setup(bot):
    await bot.add_cog(UserManagement(bot))