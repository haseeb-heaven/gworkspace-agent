import time
import logging

logger = logging.getLogger(__name__)

class VerifierMixin:
    def verify_resource(self, service: str, resource_id: str) -> bool:
        """
        Performs a Triple-Check verification by fetching the resource 3 times
        with increasing delays (0s, 2s, 4s).
        """
        # Mapping of service to the appropriate GET action and parameter name
        resource_map = {
            "sheets": ("get_spreadsheet", "spreadsheet_id"),
            "docs": ("get_document", "document_id"),
            "drive": ("get_file", "file_id"),
            "calendar": ("get_event", "event_id"),
        }
        
        if service not in resource_map:
            logger.debug(f"Triple-check not implemented for service: {service}")
            return True

        action, param_name = resource_map[service]
        
        for i in range(3):
            delay = 2 * i
            logger.info(f"Triple-check attempt {i+1}/3 for {service} resource {resource_id}. Sleeping {delay}s...")
            time.sleep(delay)
            
            try:
                args = self.planner.build_command(service, action, {param_name: resource_id})
                result = self.runner.run(args)
                if not result.success:
                    logger.warning(f"Triple-check attempt {i+1}/3 failed for {service} {resource_id}: {result.error}")
                    return False
            except Exception as e:
                logger.error(f"Error during triple-check for {service} {resource_id}: {e}")
                return False
                
        logger.info(f"Triple-check PASSED for {service} {resource_id}")
        return True

    def _verify_artifact_content(self, *args, **kwargs) -> None:
        pass
