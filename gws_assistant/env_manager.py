import os
import logging
import time
from pathlib import Path
from filelock import FileLock, Timeout

logger = logging.getLogger(__name__)

ENV_PATH = Path(".env").expanduser().resolve()
ENV_LOCK_PATH = Path(".env.lock").expanduser().resolve()

def _safe_replace(temp_path: Path, dest_path: Path):
    """Safely replace file with retry for Windows locking issues."""
    for attempt in range(5):
        try:
            os.replace(temp_path, dest_path)
            return
        except OSError:
            if attempt == 4:
                raise
            time.sleep(0.5)

def read_env_safe() -> dict[str, str]:
    """Reads .env safely without acquiring a long-term lock."""
    if not ENV_PATH.exists():
        return {}
    env_vars = {}
    with open(ENV_PATH, "r", encoding="utf-8") as f:
        for line in f:
            if "=" in line and not line.strip().startswith("#"):
                key, val = line.split("=", 1)
                env_vars[key.strip()] = val.strip()
    return env_vars

def write_env_safe(mutations: dict[str, str]) -> None:
    """
    Acquires lock, re-reads latest state, applies mutation,
    verifies integrity, and atomically writes changes.
    """
    lock = FileLock(str(ENV_LOCK_PATH), timeout=10)
    try:
        with lock:
            if not ENV_PATH.exists():
                lines = []
            else:
                with open(ENV_PATH, "r", encoding="utf-8") as f:
                    lines = f.readlines()

            env_vars = {}
            for line in lines:
                if "=" in line and not line.strip().startswith("#"):
                    key, val = line.split("=", 1)
                    env_vars[key.strip()] = val.strip()

            for k, v in mutations.items():
                env_vars[k] = v

            if not env_vars and lines:
                logger.error("Integrity check failed: Attempted to write empty .env")
                return

            new_lines = []
            mutated_keys = set()
            for line in lines:
                if "=" in line and not line.strip().startswith("#"):
                    key = line.split("=", 1)[0].strip()
                    if key in mutations:
                        new_lines.append(f"{key}={mutations[key]}\n")
                        mutated_keys.add(key)
                    else:
                        new_lines.append(line)
                else:
                    new_lines.append(line)

            for k, v in mutations.items():
                if k not in mutated_keys:
                    new_lines.append(f"{k}={v}\n")

            temp_path = ENV_PATH.with_suffix(".env.tmp")
            with open(temp_path, "w", encoding="utf-8") as f:
                f.writelines(new_lines)

            _safe_replace(temp_path, ENV_PATH)
            logger.info(f"Safely mutated .env; {len(mutations)} keys updated")

    except Timeout:
        logger.error("Could not acquire lock to mutate .env")
    except Exception as e:
        logger.error(f"Failed to safely mutate .env: {e}")

def rotate_api_key_in_env(failed_key: str):
    """
    Moves the failed_key to the end of the rotation list in .env.
    """
    lock = FileLock(str(ENV_LOCK_PATH), timeout=10)
    try:
        with lock:
            if not ENV_PATH.exists():
                return
            with open(ENV_PATH, "r", encoding="utf-8") as f:
                lines = f.readlines()

            key_map = {}
            for line in lines:
                if "=" in line and not line.strip().startswith("#"):
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip()
                    if k.startswith("LLM_API_KEY"):
                        key_map[k] = v

            if failed_key not in key_map.values():
                return

            def _llm_key_index(k: str) -> int:
                return int(k.replace("LLM_API_KEY", "") or 1)

            sorted_keys = sorted(key_map.keys(), key=_llm_key_index)
            values = [key_map[k] for k in sorted_keys]

            if values[0] == failed_key:
                values.append(values.pop(0))

                mutations = {}
                for i, k in enumerate(sorted_keys):
                    mutations[k] = values[i]

                new_lines = []
                for line in lines:
                    if "=" in line and not line.strip().startswith("#"):
                        k = line.split("=", 1)[0].strip()
                        if k in mutations:
                            new_lines.append(f"{k}={mutations[k]}\n")
                        else:
                            new_lines.append(line)
                    else:
                        new_lines.append(line)

                temp_path = ENV_PATH.with_suffix(".env.tmp")
                with open(temp_path, "w", encoding="utf-8") as f:
                    f.writelines(new_lines)

                _safe_replace(temp_path, ENV_PATH)
                logger.info("Successfully rotated API key in .env")

    except Timeout:
        logger.error("Could not acquire lock to rotate API key in .env")
    except Exception as e:
        logger.error(f"Failed to rotate API key in .env: {e}")

def rotate_model_in_env(failed_model: str):
    """
    Rotates LLM_MODEL in .env with the next available fallback model.
    """
    lock = FileLock(str(ENV_LOCK_PATH), timeout=10)
    try:
        with lock:
            if not ENV_PATH.exists():
                return
            with open(ENV_PATH, "r", encoding="utf-8") as f:
                lines = f.readlines()

            key_map = {}
            for line in lines:
                if "=" in line and not line.strip().startswith("#"):
                    k, v = line.split("=", 1)
                    key_map[k.strip()] = v.strip()

            current_model = key_map.get("LLM_MODEL", "")
            if current_model != failed_model:
                return

            fallback_keys = [k for k in key_map.keys() if k.startswith("LLM_FALLBACK_MODEL")]

            def parse_fallback_index(k: str) -> int:
                return int(k.replace("LLM_FALLBACK_MODEL", "") or 1)

            sorted_fallbacks = sorted(fallback_keys, key=parse_fallback_index)

            if not sorted_fallbacks:
                return

            new_model = key_map[sorted_fallbacks[0]]

            mutations = {"LLM_MODEL": new_model}
            for i in range(len(sorted_fallbacks) - 1):
                mutations[sorted_fallbacks[i]] = key_map[sorted_fallbacks[i+1]]
            mutations[sorted_fallbacks[-1]] = failed_model

            new_lines = []
            for line in lines:
                if "=" in line and not line.strip().startswith("#"):
                    k = line.split("=", 1)[0].strip()
                    if k in mutations:
                        new_lines.append(f"{k}={mutations[k]}\n")
                    else:
                        new_lines.append(line)
                else:
                    new_lines.append(line)

            temp_path = ENV_PATH.with_suffix(".env.tmp")
            with open(temp_path, "w", encoding="utf-8") as f:
                f.writelines(new_lines)

            _safe_replace(temp_path, ENV_PATH)
            logger.info("Successfully rotated model in .env")

    except Timeout:
        logger.error("Could not acquire lock to rotate model in .env")
    except Exception as e:
        logger.error(f"Failed to rotate model in .env: {e}")
