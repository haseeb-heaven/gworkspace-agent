import logging
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from gws_assistant.memory_backend import get_memory_backend

from gws_assistant.config import AppConfig



def main():
    # Setup minimal logging
    logging.basicConfig(level=logging.ERROR)
    logger = logging.getLogger("read_mem0")

    config = AppConfig.from_env()
    memory = get_memory_backend(config, logger=logger)

    users = [config.mem0_user_id or "mem0-mcp-user"]

    for user in users:
        print(f"\n--- Retrieving Memories for: {user} ---")
        results = memory.get_all(user_id=user)

        if not results:
            print("No memories found.")
        else:
            for i, m in enumerate(results, 1):
                if isinstance(m, dict):
                    text = m.get('memory', m.get('text', str(m)))
                else:
                    text = str(m)
                print(f"{i}. {text}")

if __name__ == "__main__":
    main()
