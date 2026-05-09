import logging
import os
import re
import time
from pathlib import Path

from filelock import FileLock, Timeout

logger = logging.getLogger(__name__)

ENV_PATH = Path(".env").expanduser().resolve()
ENV_LOCK_PATH = Path(".env.lock").expanduser().resolve()

def _safe_replace(temp_path: Path, dest_path: Path) -> None:
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
    """Reads .env safely with retry for Windows locking issues."""
    if not ENV_PATH.exists():
        return {}

    for attempt in range(3):
        try:
            env_vars = {}
            with open(ENV_PATH, "r", encoding="utf-8") as f:
                for line in f:
                    if "=" in line and not line.strip().startswith("#"):
                        key, val = line.split("=", 1)
                        env_vars[key.strip()] = val.strip()
            return env_vars
        except (OSError, PermissionError):
            if attempt == 2:
                break
            time.sleep(0.1)

    # Fallback to empty if all retries fail
    return {}

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

def rotate_api_key_in_env(failed_key: str) -> None:
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

            key_pattern = re.compile(r"^LLM_API_KEY(\d*)$")
            key_map = {}
            for line in lines:
                if "=" in line and not line.strip().startswith("#"):
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip()
                    if key_pattern.match(k):
                        key_map[k] = v

            if failed_key not in key_map.values():
                return

            def _llm_key_index(k: str) -> int:
                match = key_pattern.match(k)
                if not match:
                    return 999  # Should not happen due to filter above
                suffix = match.group(1)
                return int(suffix) if suffix else 1

            sorted_keys = sorted(key_map.keys(), key=_llm_key_index)
            values = [key_map[k] for k in sorted_keys]

            if failed_key in values:
                idx = values.index(failed_key)
                values.append(values.pop(idx))

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

def rotate_model_in_env(failed_model: str) -> None:
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

            fallback_pattern = re.compile(r"^LLM_FALLBACK_MODEL(\d*)$")
            fallback_keys = [k for k in key_map.keys() if fallback_pattern.match(k)]

            def parse_fallback_index(k: str) -> int:
                match = fallback_pattern.match(k)
                if not match:
                    return 999
                suffix = match.group(1)
                return int(suffix) if suffix else 1

            sorted_fallbacks = sorted(fallback_keys, key=parse_fallback_index)

            all_model_keys = []
            if "LLM_MODEL" in key_map:
                all_model_keys.append("LLM_MODEL")
            all_model_keys.extend(sorted_fallbacks)

            all_values = [key_map[k] for k in all_model_keys]

            if failed_model in all_values:
                idx = all_values.index(failed_model)
                # Only rotate if it's the current model or if we want to be robust
                # The instructions say "locate the index of failed_key anywhere... pop it, and append it"
                all_values.append(all_values.pop(idx))

                mutations = {}
                for i, k in enumerate(all_model_keys):
                    mutations[k] = all_values[i]

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
