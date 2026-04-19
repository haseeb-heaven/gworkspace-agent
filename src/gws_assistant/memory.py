from .memory_backend import get_memory_backend

class LongTermMemory:
    def __init__(self, config, logger=None):
        self._backend = get_memory_backend(config, logger)

    def search(self, query: str, user_id: str | None = None, limit: int = 5):
        return self._backend.search(query, user_id, limit)

    def add(self, data, user_id=None, metadata=None):
        return self._backend.add(data, user_id, metadata)

def recall_similar(goal: str, max_results: int = 3):
    from .config import AppConfig
    config = AppConfig.from_env()
    backend = get_memory_backend(config)
    return backend.recall_similar(goal, max_results)


    def search(self, query: str, user_id: str | None = None, limit: int = 5):
        return self._backend.search(query, user_id, limit)

    def add(self, data, user_id=None, metadata=None):
        return self._backend.add(data, user_id, metadata)

def recall_similar(goal: str, max_results: int = 3):
    from .config import AppConfig
    config = AppConfig.from_env()
    backend = get_memory_backend(config)
    return backend.recall_similar(goal, max_results)

def save_episode(goal: str, tasks: list[dict], outcome: str):
    from .config import AppConfig
    config = AppConfig.from_env()
    backend = get_memory_backend(config)
    backend.save_episode(goal, tasks, outcome)
