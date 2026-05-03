"""
斜線指令 Cog - 專門處理斜線指令
包含 Lavalink 伺服器管理和其他實用功能
"""

import discord
from discord.ext import commands
from discord import app_commands
import wavelink
import logging

logger = logging.getLogger(__name__)

class SlashCommands(commands.Cog):
    """斜線指令處理"""
    
    def __init__(self, bot):
        self.bot = bot
        
    @commands.hybrid_command(name="switch_lavalink", description="切換到另一個 Lavalink 伺服器")
    @app_commands.describe(force="是否強制切換（即使當前連接正常）")
    async def switch_lavalink(self, ctx: commands.Context, force: bool = False):
        """切換 Lavalink 伺服器（支援斜線指令和 prefix 指令）"""
        # 安全的交互類型處理
        try:
            if hasattr(ctx, 'interaction') and ctx.interaction is not None:
                await ctx.defer()
            
            # 統一使用 ctx.send，它會自動處理斜線指令和 prefix 指令
            send_func = ctx.send
        except Exception as e:
            logger.error(f"處理交互類型時出錯: {e}")
            send_func = ctx.send
        
        try:
            # 獲取音樂 cog
            music_cog = self.bot.get_cog('EnhancedMusic')
            if not music_cog:
                await send_func("❌ 音樂模組未載入")
                return
            
            # 檢查當前連接狀態
            current_status = "無連接"
            if wavelink.Pool.nodes:
                for node in wavelink.Pool.nodes.values():
                    if node.status.name == "CONNECTED":
                        current_status = f"已連接到 {node.identifier}"
                        break
            
            # 如果當前連接正常且不強制切換
            if not force and "已連接" in current_status:
                embed = discord.Embed(
                    title="🔗 Lavalink 伺服器狀態",
                    description=f"目前狀態: {current_status}",
                    color=discord.Color.green()
                )
                embed.add_field(
                    name="💡 提示",
                    value="如果要強制切換伺服器，請使用 `force=True` 參數",
                    inline=False
                )
                await send_func(embed=embed)
                return
            
            # 嘗試切換伺服器
            embed = discord.Embed(
                title="🔄 正在切換 Lavalink 伺服器",
                description="請稍候...",
                color=discord.Color.orange()
            )
            msg = await send_func(embed=embed)
            
            success = await music_cog.switch_lavalink_server()
            
            if success:
                # 獲取新的連接狀態
                new_status = "未知"
                if wavelink.Pool.nodes:
                    for node in wavelink.Pool.nodes.values():
                        if node.status.name == "CONNECTED":
                            new_status = node.identifier
                            break
                
                embed = discord.Embed(
                    title="✅ 伺服器切換成功",
                    description=f"已切換到: **{new_status}**",
                    color=discord.Color.green()
                )
                embed.add_field(
                    name="📊 狀態",
                    value=f"舊連接: {current_status}\n新連接: {new_status}",
                    inline=False
                )
            else:
                embed = discord.Embed(
                    title="❌ 伺服器切換失敗",
                    description="無法找到可用的替代伺服器",
                    color=discord.Color.red()
                )
                embed.add_field(
                    name="💡 建議",
                    value="• 檢查網路連接\n• 稍後再試\n• 使用指令查看伺服器狀態",
                    inline=False
                )
            
            # 統一發送回應
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"切換伺服器失敗: {e}")
            embed = discord.Embed(
                title="❌ 切換失敗",
                description=f"發生錯誤: {str(e)}",
                color=discord.Color.red()
            )
            await send_func(embed=embed)
    
    @commands.hybrid_command(name="lavalink_status", description="顯示 Lavalink 伺服器狀態")
    async def lavalink_status(self, ctx: commands.Context):
        """顯示 Lavalink 狀態（支援斜線指令和 prefix 指令）"""
        # 安全的交互類型處理
        try:
            if hasattr(ctx, 'interaction') and ctx.interaction is not None:
                await ctx.defer()
            
            # 統一使用 ctx.send
            send_func = ctx.send
        except Exception as e:
            logger.error(f"處理交互類型時出錯: {e}")
            send_func = ctx.send
        
        try:
            # 檢查 Lavalink 管理器
            try:
                from utils.lavalink_manager import lavalink_manager
            except ImportError:
                lavalink_manager = None
            
            embed = discord.Embed(
                title="🌐 Lavalink 伺服器狀態",
                color=discord.Color.blue()
            )
            
            # 顯示當前連接狀態
            current_connections = []
            if wavelink.Pool.nodes:
                for node_id, node in wavelink.Pool.nodes.items():
                    status_emoji = "🟢" if node.status.name == "CONNECTED" else "🔴"
                    current_connections.append(f"{status_emoji} **{node.identifier}** - {node.status.name}")
            
            if current_connections:
                embed.add_field(
                    name="🔗 當前連接",
                    value="\n".join(current_connections),
                    inline=False
                )
            else:
                embed.add_field(
                    name="🔗 當前連接",
                    value="❌ 無連接",
                    inline=False
                )
            
            # 如果有 Lavalink 管理器，顯示更多資訊
            if lavalink_manager:
                try:
                    status = lavalink_manager.get_server_status_summary()
                    
                    # 版本相容性資訊
                    embed.add_field(
                        name="🔧 版本相容性",
                        value=(
                            f"Wavelink: **{status.get('wavelink_version', '未知')}**\n"
                            f"偏好 Lavalink: **{status.get('preferred_lavalink_version', '未知')}**\n"
                            f"相容伺服器: **{status.get('compatible', 0)}/{status.get('total', 0)}** 個"
                        ),
                        inline=True
                    )
                except Exception as status_error:
                    logger.error(f"獲取伺服器狀態失敗: {status_error}")
                    embed.add_field(
                        name="⚠️ 狀態錯誤",
                        value="無法獲取詳細狀態資訊",
                        inline=True
                    )
                    # 使用基本狀態
                    status = {"total": len(lavalink_manager.servers) if hasattr(lavalink_manager, 'servers') else 0}
                
                try:
                    embed.add_field(
                        name="📊 伺服器統計",
                        value=(
                            f"總計: {status.get('total', 0)} 個\n"
                            f"🟢 線上: {status.get('online', 0)} 個\n"
                            f"🔴 離線: {status.get('offline', 0)} 個\n"
                            f"⚠️ 錯誤: {status.get('error', 0)} 個"
                        ),
                        inline=True
                    )
                    
                    # 版本分佈統計
                    version_info = status.get('version_info', {})
                    embed.add_field(
                        name="📋 版本分佈",
                        value=(
                            f"Lavalink 4.x: {version_info.get('4.x', 0)} 個\n"
                            f"Lavalink 3.x: {version_info.get('3.x', 0)} 個\n"
                            f"未知版本: {version_info.get('unknown', 0)} 個"
                        ),
                        inline=True
                    )
                    
                    # 顯示最佳相容伺服器
                    if hasattr(lavalink_manager, 'servers') and lavalink_manager.servers:
                        try:
                            compatible_servers = lavalink_manager._get_compatible_servers()
                            online_compatible = [s for s in compatible_servers if s.status == "online"]
                            
                            if online_compatible:
                                # 使用智能排序
                                best_servers = sorted(online_compatible, key=lavalink_manager._server_sort_key)[:3]
                                server_list = []
                                for i, server in enumerate(best_servers, 1):
                                    ping = f"{server.response_time*1000:.0f}ms" if server.response_time > 0 else "N/A"
                                    version_emoji = "🆕" if server.version == "4.x" else "📦" if server.version == "3.x" else "❓"
                                    server_list.append(f"{i}. {version_emoji} {server.name} - {ping}")
                                
                                embed.add_field(
                                    name="🏆 最佳相容伺服器",
                                    value="\n".join(server_list),
                                    inline=False
                                )
                            else:
                                embed.add_field(
                                    name="⚠️ 相容性警告",
                                    value=f"沒有線上的相容伺服器！\n建議檢查 Wavelink 版本設定",
                                    inline=False
                                )
                        except Exception as e:
                            logger.warning(f"獲取相容伺服器清單失敗: {e}")
                            embed.add_field(
                                name="📋 伺服器清單",
                                value=f"共 {len(lavalink_manager.servers)} 個伺服器",
                                inline=False
                            )
                except Exception as e:
                    logger.warning(f"顯示伺服器統計失敗: {e}")
            else:
                embed.add_field(
                    name="⚠️ 注意",
                    value="伺服器管理器未啟用",
                    inline=False
                )
            
            # 添加操作提示
            embed.add_field(
                name="🛠️ 可用操作",
                value="• `/switch_lavalink` - 切換伺服器\n• `/reconnect_lavalink` - 重新連接",
                inline=False
            )
            
            await send_func(embed=embed)
            
        except Exception as e:
            logger.error(f"獲取 Lavalink 狀態失敗: {e}")
            embed = discord.Embed(
                title="❌ 獲取狀態失敗",
                description=f"發生錯誤: {str(e)}",
                color=discord.Color.red()
            )
            await send_func(embed=embed)
    
    @commands.hybrid_command(name="reconnect_lavalink", description="重新連接到最佳 Lavalink 伺服器")
    @commands.is_owner()
    async def reconnect_lavalink(self, ctx: commands.Context):
        """重新連接 Lavalink（支援斜線指令和 prefix 指令，僅限擁有者）"""
        # 安全的交互類型處理
        try:
            if hasattr(ctx, 'interaction') and ctx.interaction is not None:
                await ctx.defer()
            
            # 統一使用 ctx.send
            send_func = ctx.send
        except Exception as e:
            logger.error(f"處理交互類型時出錯: {e}")
            send_func = ctx.send
        
        try:
            # 獲取音樂 cog
            music_cog = self.bot.get_cog('EnhancedMusic')
            if not music_cog:
                await send_func("❌ 音樂模組未載入")
                return
            
            embed = discord.Embed(
                title="🔌 正在重新連接 Lavalink",
                description="正在斷開現有連接並重新連接到最佳伺服器...",
                color=discord.Color.orange()
            )
            msg = await send_func(embed=embed)
            
            # 關閉所有現有節點（Pool.nodes 是唯讀 mapping，必須逐一 close）
            for node in list(wavelink.Pool.nodes.values()):
                try:
                    await node.close()
                except Exception:
                    pass
            
            # 重新連接
            success = await music_cog.connect_to_lavalink()
            
            if success:
                # 獲取新連接狀態
                new_status = "未知"
                if wavelink.Pool.nodes:
                    for node in wavelink.Pool.nodes.values():
                        if node.status.name == "CONNECTED":
                            new_status = node.identifier
                            break
                
                embed = discord.Embed(
                    title="✅ 重新連接成功",
                    description=f"已連接到: **{new_status}**",
                    color=discord.Color.green()
                )
            else:
                embed = discord.Embed(
                    title="❌ 重新連接失敗",
                    description="無法連接到任何 Lavalink 伺服器",
                    color=discord.Color.red()
                )
            
            # 統一發送回應
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"重新連接 Lavalink 失敗: {e}")
            embed = discord.Embed(
                title="❌ 重新連接失敗",
                description=f"發生錯誤: {str(e)}",
                color=discord.Color.red()
            )
            await send_func(embed=embed)
    
    @commands.hybrid_command(name="music_help", description="顯示音樂功能說明")
    async def music_help(self, ctx: commands.Context):
        """音樂功能說明（支援斜線指令和 prefix 指令）"""
        embed = discord.Embed(
            title="🎵 音樂功能說明",
            description="完整的 Discord 音樂機器人功能列表",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="🎶 基本播放",
            value=(
                "`/play <搜尋>` - 播放音樂\n"
                "`/next` - 播放佇列中的下一首\n"
                "`/skip` - 跳過當前音樂\n"
                "`/stop` - 停止播放並離開語音頻道\n"
                "`/pause` - 暫停播放\n"
                "`/resume` - 繼續播放"
            ),
            inline=False
        )
        
        embed.add_field(
            name="📋 佇列管理",
            value=(
                "`/queue` - 顯示播放佇列\n"
                "`/clear` - 清空佇列\n"
                "`/shuffle` - 切換隨機播放\n"
                "`/loop` - 切換循環模式\n"
                "`/remove <位置>` - 移除指定音樂"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🔧 進階功能",
            value=(
                "`/volume` - 調整音量\n"
                "`/nowplaying` - 顯示當前播放\n"
                "`/autoplay` - 自動播放推薦\n"
                "`/search <關鍵字>` - 搜尋音樂\n"
                "`/playlist` - 播放列表管理"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🌐 伺服器管理",
            value=(
                "`/lavalink_status` - 顯示伺服器狀態\n"
                "`/switch_lavalink` - 切換伺服器\n"
                "`/reconnect_lavalink` - 重新連接（擁有者）"
            ),
            inline=False
        )
        
        embed.set_footer(text="💡 提示：所有指令都支援斜線指令和傳統指令兩種方式")
        
        # 統一發送回應
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="test_version_matching", description="測試版本匹配功能")
    @commands.is_owner()
    async def test_version_matching(self, ctx: commands.Context):
        """測試版本匹配功能（僅限擁有者）"""
        # 安全的交互類型處理
        try:
            if hasattr(ctx, 'interaction') and ctx.interaction is not None:
                await ctx.defer()
            send_func = ctx.send
        except Exception as e:
            logger.error(f"處理交互類型時出錯: {e}")
            send_func = ctx.send
        
        try:
            # 獲取 Lavalink 管理器
            try:
                from utils.lavalink_manager import lavalink_manager
            except ImportError:
                await send_func("❌ Lavalink 管理器未載入")
                return
            
            embed = discord.Embed(
                title="🔬 版本匹配功能測試",
                description="正在測試智能版本匹配和伺服器選擇功能...",
                color=discord.Color.blue()
            )
            
            # 顯示系統資訊
            embed.add_field(
                name="📋 系統資訊",
                value=(
                    f"Wavelink 版本: **{lavalink_manager.wavelink_version}**\n"
                    f"偏好 Lavalink 版本: **{lavalink_manager.preferred_lavalink_version}**\n"
                    f"總伺服器數: **{len(lavalink_manager.servers)}** 個"
                ),
                inline=False
            )
            
            # 測試伺服器過濾
            compatible_servers = lavalink_manager._get_compatible_servers()
            embed.add_field(
                name="🎯 相容性測試",
                value=(
                    f"相容伺服器: **{len(compatible_servers)}** 個\n"
                    f"過濾比例: **{len(compatible_servers)/max(len(lavalink_manager.servers), 1)*100:.1f}%**"
                ),
                inline=True
            )
            
            # 顯示排序結果
            if compatible_servers:
                sorted_servers = sorted(compatible_servers, key=lavalink_manager._server_sort_key)
                top_servers = []
                for i, server in enumerate(sorted_servers[:5], 1):
                    version_emoji = "🆕" if server.version == "4.x" else "📦" if server.version == "3.x" else "❓"
                    priority_text = f"P{server.priority}" if server.priority < 10 else f"P{server.priority}"
                    status_emoji = "🟢" if server.status == "online" else "🔴" if server.status == "offline" else "⚠️"
                    top_servers.append(f"{i}. {version_emoji}{status_emoji} {server.name[:20]}... ({priority_text})")
                
                embed.add_field(
                    name="🏆 智能排序結果（前5名）",
                    value="\n".join(top_servers) if top_servers else "無相容伺服器",
                    inline=False
                )
            
            # 版本統計
            version_stats = {}
            for server in lavalink_manager.servers:
                version_stats[server.version] = version_stats.get(server.version, 0) + 1
            
            version_text = []
            for version, count in version_stats.items():
                emoji = "🆕" if version == "4.x" else "📦" if version == "3.x" else "❓"
                is_preferred = " ⭐" if version == lavalink_manager.preferred_lavalink_version else ""
                version_text.append(f"{emoji} {version}: {count} 個{is_preferred}")
            
            embed.add_field(
                name="📊 版本分佈統計",
                value="\n".join(version_text) if version_text else "無資料",
                inline=True
            )
            
            # 功能測試結果
            test_results = []
            
            # 測試1: 版本檢測
            try:
                detected_version = lavalink_manager._detect_wavelink_version()
                test_results.append(f"✅ 版本檢測: {detected_version}")
            except Exception as e:
                test_results.append(f"❌ 版本檢測失敗: {str(e)[:30]}...")
            
            # 測試2: 伺服器過濾
            try:
                filtered = lavalink_manager._get_compatible_servers()
                test_results.append(f"✅ 伺服器過濾: {len(filtered)} 個")
            except Exception as e:
                test_results.append(f"❌ 伺服器過濾失敗: {str(e)[:30]}...")
            
            # 測試3: 排序算法
            try:
                if compatible_servers:
                    sorted_test = sorted(compatible_servers, key=lavalink_manager._server_sort_key)
                    test_results.append(f"✅ 排序算法: {len(sorted_test)} 個")
                else:
                    test_results.append("⚠️ 排序算法: 無伺服器可排序")
            except Exception as e:
                test_results.append(f"❌ 排序算法失敗: {str(e)[:30]}...")
            
            embed.add_field(
                name="🧪 功能測試結果",
                value="\n".join(test_results),
                inline=False
            )
            
            # 建議
            suggestions = []
            if len(compatible_servers) == 0:
                suggestions.append("• 沒有相容伺服器，請檢查版本設定")
            elif len(compatible_servers) < len(lavalink_manager.servers) / 2:
                suggestions.append("• 相容伺服器較少，考慮升級 Wavelink")
            else:
                suggestions.append("• 版本匹配運作正常！")
            
            if version_stats.get("unknown", 0) > 0:
                suggestions.append("• 有未知版本伺服器，建議更新伺服器資訊")
            
            embed.add_field(
                name="💡 建議",
                value="\n".join(suggestions),
                inline=False
            )
            
            await send_func(embed=embed)
            
        except Exception as e:
            logger.error(f"版本匹配測試失敗: {e}")
            embed = discord.Embed(
                title="❌ 測試失敗",
                description=f"發生錯誤: {str(e)}",
                color=discord.Color.red()
            )
            await send_func(embed=embed)
    
    @commands.hybrid_command(name="test_slash", description="測試指令是否正常工作")
    async def test_slash(self, ctx: commands.Context):
        """測試指令功能（支援斜線指令和 prefix 指令）"""
        # 判斷指令類型
        try:
            command_type = "斜線指令" if (hasattr(ctx, 'interaction') and ctx.interaction) else "Prefix 指令"
        except:
            command_type = "未知類型"
        
        embed = discord.Embed(
            title=f"✅ {command_type}測試成功",
            description=f"如果你能看到這個訊息，表示{command_type}正常工作！",
            color=discord.Color.green()
        )
        embed.add_field(
            name="📊 系統資訊",
            value=f"伺服器: {ctx.guild.name if ctx.guild else 'DM'}\n用戶: {ctx.author.display_name}\n指令類型: {command_type}",
            inline=False
        )
        
        # 統一發送回應
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(SlashCommands(bot))