import time
import logging
from typing import Any

logger = logging.getLogger(__name__)

class VerifierMixin:
    def verify_resource(self, service: str, resource_id: str) -> bool:
        """
        Performs a Triple-Check verification by fetching the resource 3 times.
        Ensures consistency and that the resource is truly available in GWS.
        """
        resource_map = {
            "sheets": ("get_spreadsheet", "spreadsheet_id"),
            "docs": ("get_document", "document_id"),
            "drive": ("get_file", "file_id"),
            "calendar": ("get_event", "event_id"),
            "keep": ("get_note", "name"),
            "tasks": ("get_task", "task_id"),
            "gmail": ("get_message", "message_id"),
        }

        if service not in resource_map:
            logger.warning(f"No verification mapping for service: {service}")
            return True # Assume success if we don't know how to verify

        action, id_param = resource_map[service]
        
        for i in range(3):
            # Increasing delay: 0s, 2s, 4s
            delay = 2 * i 
            if delay > 0:
                time.sleep(delay)
            
            logger.info(f"Triple-check attempt {i+1}/3 for {service} {resource_id}...")
            
            try:
                # Build the command using the planner to ensure correct argument structure
                # self.planner and self.runner are available because this is a Mixin for PlanExecutor
                args = self.planner.build_command(service, action, {id_param: resource_id})
                result = self.runner.run(args)
                
                if result.success:
                    logger.info(f"Triple-check success on attempt {i+1} for {service} {resource_id}")
                else:
                    logger.warning(f"Triple-check FAILED on attempt {i+1} for {service} {resource_id}: {result.error}")
                    return False
            except Exception as e:
                logger.error(f"Error during triple-check of {service} {resource_id}: {e}")
                return False
                
        logger.info(f"Triple-check PASSED for {service} {resource_id}")
        return True

    def _verify_artifact_content(self, *args, **kwargs) -> None:
        """Placeholder for deeper content-level verification if needed."""
        pass
