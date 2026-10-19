"""首次準備本機音樂服務所需的可攜式 Java 與插件。"""

from utils.local_lavalink import install_local_runtime
from utils.youtube_runtime import install_youtube_tools
import config


if __name__ == '__main__':
    install_local_runtime()
    if config.YOUTUBE_CIPHER_ENABLED or config.YOUTUBE_FALLBACK_ENABLED:
        install_youtube_tools()
