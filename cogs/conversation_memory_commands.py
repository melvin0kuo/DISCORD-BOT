"""
對話記憶管理 Cog - 處理對話記憶相關的斜線指令
提供智慧對話上下文、摘要和洞察分析功能
"""

import discord
from discord.ext import commands
from discord import app_commands
import logging
from typing import Optional
import json
from datetime import datetime, timedelta

from utils.user_database import user_db
from utils.conversation_memory import conversation_memory

logger = logging.getLogger(__name__)

class ConversationMemoryCommands(commands.Cog):
    """對話記憶管理"""
    
    def __init__(self, bot):
        self.bot = bot
        logger.info("對話記憶管理模組已載入")
    
    @app_commands.command(name="檢視對話摘要", description="顯示與機器人的對話摘要")
    @app_commands.describe(
        user="目標用戶（留空表示自己）",
        channel="指定頻道（留空表示當前頻道）"
    )
    async def view_conversation_summary(
        self,
        interaction: discord.Interaction,
        user: Optional[discord.Member] = None,
        channel: Optional[discord.TextChannel] = None
    ):
        """檢視對話摘要"""
        target_user = user or interaction.user
        target_channel = channel or interaction.channel
        
        # 權限檢查
        if user and user != interaction.user:
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message("❌ 只有管理員可以查看其他用戶的對話摘要", ephemeral=True)
                return
        
        await interaction.response.defer()
        
        try:
            # 獲取對話記錄
            recent_conversations = conversation_memory._get_recent_conversations(
                str(target_user.id), 
                str(target_channel.id), 
                10
            )
            
            if not recent_conversations:
                embed = discord.Embed(
                    title="📋 對話摘要",
                    description=f"用戶 **{target_user.display_name}** 在 {target_channel.mention} 還沒有對話記錄",
                    color=discord.Color.orange()
                )
                await interaction.followup.send(embed=embed)
                return
            
            # 創建對話摘要
            summary = conversation_memory.create_conversation_summary(
                str(target_user.id),
                str(target_channel.id),
                recent_conversations
            )
            
            embed = discord.Embed(
                title=f"📋 {target_user.display_name} 的對話摘要",
                description=summary,
                color=discord.Color.blue()
            )
            
            embed.add_field(
                name="📊 統計資訊",
                value=(
                    f"**對話輪次**: {len(recent_conversations)} 輪\n"
                    f"**頻道**: {target_channel.mention}\n"
                    f"**最後更新**: {recent_conversations[0]['created_at'][:19] if recent_conversations else 'N/A'}"
                ),
                inline=False
            )
            
            embed.set_thumbnail(url=target_user.display_avatar.url)
            embed.set_footer(text=f"摘要生成時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"檢視對話摘要時出錯: {e}")
            await interaction.followup.send(f"❌ 發生錯誤: {str(e)}")
    
    @app_commands.command(name="獲取對話洞察", description="分析用戶的對話模式和興趣")
    @app_commands.describe(
        user="目標用戶（留空表示自己）",
        channel="指定頻道（留空表示當前頻道）"
    )
    async def get_conversation_insights(
        self,
        interaction: discord.Interaction,
        user: Optional[discord.Member] = None,
        channel: Optional[discord.TextChannel] = None
    ):
        """獲取對話洞察"""
        target_user = user or interaction.user
        target_channel = channel or interaction.channel
        
        # 權限檢查
        if user and user != interaction.user:
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message("❌ 只有管理員可以查看其他用戶的對話洞察", ephemeral=True)
                return
        
        await interaction.response.defer()
        
        try:
            # 獲取對話洞察
            insights = conversation_memory.get_conversation_insights(
                str(target_user.id),
                str(target_channel.id)
            )
            
            embed = discord.Embed(
                title=f"📊 {target_user.display_name} 的對話洞察",
                color=discord.Color.purple()
            )
            
            # 常討論話題
            if insights.get('common_topics'):
                topics_text = '\n'.join([f"• {topic}" for topic in insights['common_topics'][:10]])
                embed.add_field(
                    name="🗣️ 常討論話題",
                    value=topics_text,
                    inline=False
                )
            
            # 最新興趣
            if insights.get('latest_interests'):
                interests_text = '\n'.join([f"• {interest}" for interest in insights['latest_interests'][:5]])
                embed.add_field(
                    name="⭐ 最新興趣",
                    value=interests_text,
                    inline=True
                )
            
            # 對話統計
            stats = insights.get('conversation_stats', {})
            if stats:
                embed.add_field(
                    name="📈 對話統計",
                    value=(
                        f"**總對話數**: {stats.get('total_conversations', 0)} 輪\n"
                        f"**平均長度**: {stats.get('avg_message_length', 0):.1f} 字元\n"
                        f"**活躍程度**: {stats.get('activity_level', '普通')}"
                    ),
                    inline=True
                )
            
            # 對話模式
            patterns = insights.get('conversation_patterns', {})
            if patterns:
                pattern_text = []
                if patterns.get('most_active_time'):
                    pattern_text.append(f"**最活躍時間**: {patterns['most_active_time']}")
                if patterns.get('conversation_frequency'):
                    pattern_text.append(f"**對話頻率**: {patterns['conversation_frequency']}")
                if patterns.get('preferred_topics'):
                    pattern_text.append(f"**偏好話題**: {', '.join(patterns['preferred_topics'][:3])}")
                
                if pattern_text:
                    embed.add_field(
                        name="🔍 對話模式",
                        value='\n'.join(pattern_text),
                        inline=False
                    )
            
            # 學習建議
            recommendations = insights.get('learning_recommendations', [])
            if recommendations:
                rec_text = '\n'.join([f"• {rec}" for rec in recommendations[:5]])
                embed.add_field(
                    name="💡 個人化建議",
                    value=rec_text,
                    inline=False
                )
            
            embed.set_thumbnail(url=target_user.display_avatar.url)
            embed.set_footer(text=f"分析基於 {target_channel.mention} 的對話記錄")
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"獲取對話洞察時出錯: {e}")
            await interaction.followup.send(f"❌ 發生錯誤: {str(e)}")
    
    @app_commands.command(name="檢視互動歷史", description="查看用戶的互動歷史記錄")
    @app_commands.describe(
        days="查看天數（預設7天）",
        user="目標用戶（留空表示自己）"
    )
    async def view_interaction_history(
        self,
        interaction: discord.Interaction,
        days: int = 7,
        user: Optional[discord.Member] = None
    ):
        """檢視互動歷史"""
        target_user = user or interaction.user
        
        # 權限檢查
        if user and user != interaction.user:
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message("❌ 只有管理員可以查看其他用戶的互動歷史", ephemeral=True)
                return
        
        # 限制查看天數
        if days > 30:
            days = 30
        elif days < 1:
            days = 1
        
        await interaction.response.defer()
        
        try:
            # 獲取互動記錄
            interactions_data = user_db.get_user_interactions(
                str(target_user.id),
                limit=50
            )
            
            # 過濾指定天數內的記錄
            cutoff_date = datetime.now() - timedelta(days=days)
            recent_interactions = []
            
            for inter in interactions_data:
                try:
                    inter_date = datetime.fromisoformat(inter['created_at'].replace('Z', '+00:00'))
                    if inter_date.replace(tzinfo=None) >= cutoff_date:
                        recent_interactions.append(inter)
                except:
                    continue
            
            if not recent_interactions:
                embed = discord.Embed(
                    title="🕒 互動歷史",
                    description=f"用戶 **{target_user.display_name}** 在過去 {days} 天內沒有互動記錄",
                    color=discord.Color.orange()
                )
                await interaction.followup.send(embed=embed)
                return
            
            embed = discord.Embed(
                title=f"🕒 {target_user.display_name} 的互動歷史",
                description=f"過去 {days} 天的互動記錄（顯示最近 {min(len(recent_interactions), 20)} 項）",
                color=discord.Color.blue()
            )
            
            # 互動類型統計
            interaction_types = {}
            for inter in recent_interactions:
                type_name = inter['type']
                interaction_types[type_name] = interaction_types.get(type_name, 0) + 1
            
            # 顯示統計
            stats_text = []
            type_emojis = {
                'message': '💬',
                'ai_response': '🤖',
                'data_set': '📝',
                'tag_add': '🏷️',
                'memory_set': '🧠',
                'chat_command': '⌨️'
            }
            
            for type_name, count in sorted(interaction_types.items(), key=lambda x: x[1], reverse=True):
                emoji = type_emojis.get(type_name, '📊')
                stats_text.append(f"{emoji} {type_name}: {count} 次")
            
            if stats_text:
                embed.add_field(
                    name="📊 互動統計",
                    value='\n'.join(stats_text),
                    inline=False
                )
            
            # 顯示最近的互動
            recent_text = []
            for i, inter in enumerate(recent_interactions[:10], 1):
                emoji = type_emojis.get(inter['type'], '📊')
                content = inter.get('content', '')
                if content and len(content) > 30:
                    content = content[:27] + "..."
                
                time_str = inter['created_at'][:16].replace('T', ' ')
                recent_text.append(f"{i}. {emoji} {inter['type']} - {time_str}")
                if content:
                    recent_text.append(f"   └─ {content}")
            
            if recent_text:
                embed.add_field(
                    name="📋 最近互動",
                    value='\n'.join(recent_text),
                    inline=False
                )
            
            embed.set_thumbnail(url=target_user.display_avatar.url)
            embed.set_footer(text=f"查詢時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"檢視互動歷史時出錯: {e}")
            await interaction.followup.send(f"❌ 發生錯誤: {str(e)}")
    
    @app_commands.command(name="清理對話記憶", description="清理指定天數前的對話記憶")
    @app_commands.describe(
        days="保留天數（預設30天）",
        user="目標用戶（留空表示自己）",
        channel="指定頻道（留空表示當前頻道）"
    )
    async def clean_conversation_memory(
        self,
        interaction: discord.Interaction,
        days: int = 30,
        user: Optional[discord.Member] = None,
        channel: Optional[discord.TextChannel] = None
    ):
        """清理對話記憶"""
        target_user = user or interaction.user
        target_channel = channel or interaction.channel
        
        # 權限檢查
        if user and user != interaction.user:
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message("❌ 只有管理員可以清理其他用戶的對話記憶", ephemeral=True)
                return
        
        # 限制保留天數
        if days < 7:
            days = 7
        elif days > 365:
            days = 365
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            # 清理對話記憶
            cleaned_count = conversation_memory.clear_old_conversations(
                str(target_user.id),
                str(target_channel.id),
                days_to_keep=days
            )
            
            embed = discord.Embed(
                title="🧹 對話記憶清理完成",
                color=discord.Color.green()
            )
            
            embed.add_field(
                name="清理結果",
                value=(
                    f"**用戶**: {target_user.display_name}\n"
                    f"**頻道**: {target_channel.mention}\n"
                    f"**保留天數**: {days} 天\n"
                    f"**清理數量**: {cleaned_count} 筆記錄"
                ),
                inline=False
            )
            
            embed.add_field(
                name="💡 提示",
                value="清理後的對話記憶無法恢復，但不會影響用戶的個人資料和標籤",
                inline=False
            )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"清理對話記憶時出錯: {e}")
            await interaction.followup.send(f"❌ 發生錯誤: {str(e)}")
    
    @app_commands.command(name="導出對話記憶", description="導出用戶的對話記憶資料")
    @app_commands.describe(
        user="目標用戶（留空表示自己）",
        format_type="導出格式"
    )
    @app_commands.choices(format_type=[
        app_commands.Choice(name="JSON 格式", value="json"),
        app_commands.Choice(name="文本格式", value="txt")
    ])
    async def export_conversation_memory(
        self,
        interaction: discord.Interaction,
        user: Optional[discord.Member] = None,
        format_type: str = "json"
    ):
        """導出對話記憶"""
        target_user = user or interaction.user
        
        # 權限檢查
        if user and user != interaction.user:
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message("❌ 只有管理員可以導出其他用戶的對話記憶", ephemeral=True)
                return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            # 獲取所有對話記憶
            all_conversations = {}
            
            # 從對話記憶系統獲取資料
            memory_data = conversation_memory.memory_storage.get(str(target_user.id), {})
            
            # 格式化資料
            export_data = {
                "user_id": str(target_user.id),
                "username": target_user.name,
                "display_name": target_user.display_name,
                "export_time": datetime.now().isoformat(),
                "conversations": memory_data
            }
            
            # 獲取用戶的基本資料
            user_info = user_db.get_user_info(str(target_user.id))
            if user_info:
                export_data["user_info"] = {
                    "created_at": user_info.get("created_at"),
                    "updated_at": user_info.get("updated_at"),
                    "is_active": user_info.get("is_active")
                }
            
            if format_type == "json":
                # JSON 格式導出
                import io
                json_data = json.dumps(export_data, ensure_ascii=False, indent=2)
                file_content = io.BytesIO(json_data.encode('utf-8'))
                filename = f"{target_user.name}_conversation_memory_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                
                file = discord.File(file_content, filename=filename)
                
            else:  # txt 格式
                # 文本格式導出
                import io
                
                txt_content = []
                txt_content.append(f"對話記憶導出報告")
                txt_content.append(f"用戶: {target_user.display_name} ({target_user.name})")
                txt_content.append(f"用戶ID: {target_user.id}")
                txt_content.append(f"導出時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                txt_content.append("=" * 50)
                
                for channel_id, conversations in memory_data.items():
                    txt_content.append(f"\n頻道 ID: {channel_id}")
                    txt_content.append("-" * 30)
                    
                    for i, conv in enumerate(conversations, 1):
                        txt_content.append(f"\n對話 {i}:")
                        txt_content.append(f"時間: {conv.get('timestamp', 'N/A')}")
                        txt_content.append(f"用戶訊息: {conv.get('user_message', 'N/A')}")
                        txt_content.append(f"AI回應: {conv.get('ai_response', 'N/A')}")
                
                txt_data = '\n'.join(txt_content)
                file_content = io.BytesIO(txt_data.encode('utf-8'))
                filename = f"{target_user.name}_conversation_memory_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                
                file = discord.File(file_content, filename=filename)
            
            embed = discord.Embed(
                title="📤 對話記憶導出完成",
                description=f"已為 **{target_user.display_name}** 生成對話記憶導出檔案",
                color=discord.Color.green()
            )
            
            embed.add_field(
                name="檔案資訊",
                value=(
                    f"**格式**: {format_type.upper()}\n"
                    f"**檔名**: {filename}\n"
                    f"**大小**: {len(file_content.getvalue())} bytes"
                ),
                inline=False
            )
            
            embed.add_field(
                name="⚠️ 隱私提醒",
                value="此檔案包含個人對話記錄，請妥善保管並注意隱私安全",
                inline=False
            )
            
            await interaction.followup.send(embed=embed, file=file)
            
        except Exception as e:
            logger.error(f"導出對話記憶時出錯: {e}")
            await interaction.followup.send(f"❌ 發生錯誤: {str(e)}")

async def setup(bot):
    await bot.add_cog(ConversationMemoryCommands(bot))