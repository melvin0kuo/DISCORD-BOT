"""處理 Discord 語音事件可能以不同順序抵達的握手。"""

import wavelink


class VoicePlayer(wavelink.Player):
    async def refresh_playback_state(self):
        snapshot = await self.node.fetch_player_info(self.guild.id)
        if snapshot is None or not snapshot.state.connected:
            return False
        if snapshot.track is None:
            self._current = None
            self._paused = False
        return True

    async def on_voice_state_update(self, data, /):
        await super().on_voice_state_update(data)
        # Wavelink 3.5 僅在 server update 送出握手；若它先抵達，需在 state update 補送。
        if data.get('channel_id') and not self._connection_event.is_set():
            await self._dispatch_voice_update()
