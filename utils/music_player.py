"""處理 Discord 語音事件可能以不同順序抵達的握手。"""

import wavelink


class VoicePlayer(wavelink.Player):
    async def on_voice_state_update(self, data, /):
        await super().on_voice_state_update(data)
        # Wavelink 3.5 僅在 server update 送出握手；若它先抵達，需在 state update 補送。
        if data.get('channel_id') and not self._connection_event.is_set():
            await self._dispatch_voice_update()
