from .logger import setup_framework_logger

logger = setup_framework_logger("validator")

class OutputValidator:
    @staticmethod
    def validate_success(result) -> bool:
        success = result.returncode == 0
        if not success:
            logger.error(f"Command failed with code {result.returncode}")
            logger.error(f"Stderr: {result.stderr}")
        return success
        
    @staticmethod
    def validate_output_contains(result, expected_text: str) -> bool:
        contains = expected_text in result.stdout or expected_text in result.stderr
        if not contains:
            logger.error(f"Expected text '{expected_text}' not found in output")
            logger.debug(f"Actual stdout: {result.stdout}")
        return contains
