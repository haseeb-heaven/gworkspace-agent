import logging
import os
import re
from enum import Enum
from typing import Any

from .config import AppConfig
from .models import AppConfigModel

logger = logging.getLogger(__name__)


class VerificationSeverity(Enum):
    """Severity levels for verification checks."""
    CRITICAL = "CRITICAL"  # Cannot be bypassed, halts the entire system
    ERROR = "ERROR"        # Cannot be bypassed, fails the operation
    WARNING = "WARNING"    # Allows continuation with warning


class VerificationError(Exception):
    """Raised when a verification check fails."""

    def __init__(
        self,
        tool: str,
        reason: str,
        check_number: int | None = None,
        severity: VerificationSeverity = VerificationSeverity.ERROR,
        field: str | None = None,
    ):
        self.tool = tool
        self.reason = reason
        self.check_number = check_number
        self.severity = severity
        self.field = field

        msg_parts = []
        if check_number is not None:
            msg_parts.append(f"[CHECK {check_number}]")
        msg_parts.append(f"[{severity.value}]")
        msg_parts.append(f"{tool} verification failed: {reason}")
        if field:
            msg_parts.append(f"(field: {field})")

        super().__init__(" ".join(msg_parts))


class VerificationEngine:
    """STRICT 5-CHECK verification system that cannot be bypassed."""

    PLACEHOLDER_REGEXES = [
        re.compile(r"^<.*?>$"),
        re.compile(r"^\[.*?\]$"),
        re.compile(r"^{{.*?}}$"),
        re.compile(r"^{.*?}$"),
        re.compile(r"\$\{.*?\}"),  # Shell/template variables ${var}
        re.compile(r"\$\w+"),  # Shell variables $var
        re.compile(r"%\{.*?\}"),  # Ruby-style %{var}
        re.compile(r"\{\{.*?\}\}"),  # Django/Jinja {{var}} (anywhere in string)
    ]

    # Template patterns that indicate unresolved variables
    UNRESOLVED_TEMPLATE_PATTERNS = [
        re.compile(r"\{\{[^}]+\}\}"),  # Jinja2/Django templates
        re.compile(r"\$\{[^}]+\}"),  # Shell/JS template literals
        re.compile(r"<%.*?%>"),  # ERB/ASP templates
        re.compile(r"\[%.*?%\]"),  # Template Toolkit
        re.compile(r"\$\w+"),  # Simple shell variables
        re.compile(r"\{\$[^}]+\}\}"),  # Smarty templates
        re.compile(r"#__.*?__#"),  # Custom placeholder format
        re.compile(r"\[INSERT .+?\]", re.IGNORECASE),  # Insert markers
        re.compile(r"\[PLACEHOLDER\]", re.IGNORECASE),
        re.compile(r"\[TODO\]", re.IGNORECASE),
        re.compile(r"\[FIXME\]", re.IGNORECASE),
    ]

    SPECIAL_CHARS_ONLY = re.compile(r"^[^a-zA-Z0-9\s]+$")

    # Cache for config to avoid repeated calls
    _config_cache: AppConfigModel | None = None

    @classmethod
    def clear_cache(cls):
        """Clear the cached configuration."""
        cls._config_cache = None

    @classmethod
    def _get_config(cls):
        """Get the current AppConfig instance with caching."""
        if cls._config_cache is None:
            try:
                cls._config_cache = AppConfig.from_env()
            except Exception as e:
                logger.warning(f"Could not load AppConfig from environment: {e}. Using verification defaults.")
                # Return a minimal verification-only defaults object that mirrors real config defaults
                # Use instance-level __init__ to avoid shared mutable class-level state
                class VerificationDefaults:
                    def __init__(self):
                        self.verification_exact_placeholders = {
                            "none", "null", "n/a", "na", "undefined",
                            "todo", "fixme", "placeholder", "example", "sample", "dummy",
                            "your_value", "insert_here", "replace_me", "changeme", "default",
                            "fake", "mock", "temporary", "tbd", "missing"
                        }
                        self.verification_numeric_placeholders = {"0000", "1234", "9999", "00000000"}
                        self.verification_exact_emails = {"noreply@domain.com", "noreply@example.com"}
                        self.verification_email_placeholder_domains = ["@test.com"]
                        self.verification_destructive_operations = {
                            "drive_delete_file", "drive_empty_trash", "drive_move_to_trash",
                            "gmail_delete_message", "gmail_trash_message", "gmail_batch_delete", "gmail_empty_trash",
                            "sheets_delete_spreadsheet", "sheets_clear_all_data", "sheets_delete_sheet_tab",
                            "docs_delete_document",
                            "calendar_delete_event", "calendar_delete_calendar",
                            "contacts_delete_contact",
                        }
                        self.verification_bulk_indicators = ["batch", "bulk", "multiple", "all"]
                        self.verification_id_fields = ["file_id", "document_id", "spreadsheet_id", "message_id", "event_id", "task_id", "contact_id"]
                        self.verification_content_fields = ["body", "content", "message", "text", "description"]
                        self.verification_create_id_fields = ["id", "documentId", "spreadsheetId", "fileId", "messageId", "resourceName", "threadId", "name", "formId", "taskId", "contactId", "presentationId"]
                        self.verification_suspicious_patterns = {
                            "delete_all": r"delete.*all",
                            "remove_everything": r"remove.*everything",
                            "wipe_all": r"wipe.*all",
                            "clear_all": r"clear.*all",
                        }
                        # Content validation settings
                        self.verification_min_content_length = {
                            "document": 5,  # Min chars for document content
                            "email_body": 10,  # Min chars for email body
                            "spreadsheet_cell": 1,  # Min chars per cell
                            "task_title": 2,  # Min chars for task title
                            "event_summary": 2,  # Min chars for event title
                            "contact_name": 2,  # Min chars for contact name
                        }
                cls._config_cache = VerificationDefaults()
        return cls._config_cache

    @classmethod
    def clear_config_cache(cls):
        """Clear the config cache (useful for testing)."""
        cls._config_cache = None

    @classmethod
    def exact_placeholders(cls) -> set[str]:
        """Get exact placeholders from config."""
        return cls._get_config().verification_exact_placeholders

    @classmethod
    def numeric_placeholders(cls) -> set[str]:
        """Get numeric placeholders from config."""
        return cls._get_config().verification_numeric_placeholders

    @classmethod
    def exact_emails(cls) -> set[str]:
        """Get exact emails from config."""
        return cls._get_config().verification_exact_emails

    @classmethod
    def email_placeholder_domains(cls) -> list[str]:
        """Get email placeholder domains from config."""
        return cls._get_config().verification_email_placeholder_domains

    @classmethod
    def destructive_operations(cls) -> set[str]:
        """Get destructive operations from config."""
        return cls._get_config().verification_destructive_operations

    @classmethod
    def bulk_indicators(cls) -> list[str]:
        """Get bulk indicators from config."""
        return cls._get_config().verification_bulk_indicators

    @classmethod
    def id_fields(cls) -> list[str]:
        """Get ID fields from config."""
        return cls._get_config().verification_id_fields

    @classmethod
    def content_fields(cls) -> list[str]:
        """Get content fields from config."""
        return cls._get_config().verification_content_fields

    @classmethod
    def create_id_fields(cls) -> list[str]:
        """Get create ID fields from config."""
        return cls._get_config().verification_create_id_fields

    @classmethod
    def suspicious_patterns(cls) -> dict[str, str]:
        """Get suspicious patterns from config."""
        return cls._get_config().verification_suspicious_patterns

    @classmethod
    def verify_pre_execution(cls, tool_name: str, params: dict) -> None:
        """
        Perform pre-execution safety and parameter validation checks.

        Args:
            tool_name: Name of the tool in service_action format.
            params: Parameters being passed to the tool.

        Raises:
            VerificationError: If any pre-execution check fails.
        """
        # CHECK 1: Parameter Validation (must happen pre-exec)
        cls._check_1_parameter_validation(tool_name, params)

        # CHECK 2: Permission & Scope Validation (must happen pre-exec)
        cls._check_2_permission_scope_validation(tool_name, params)

        # CHECK 5: Safety & Idempotency (Safety parts must happen pre-exec)
        # We call the full check but it won't have a result yet
        cls._check_5_idempotency_safety_validation(tool_name, params, result=None)

    @classmethod
    def verify(cls, tool_name: str, params: dict, result: Any) -> None:
        """
        STRICT 5-CHECK verification system.
        All checks run sequentially. CRITICAL and ERROR checks cannot be bypassed.
        Only WARNING checks allow continuation.

        This method CANNOT be bypassed - no try/except that swallows errors.
        """
        if not isinstance(params, dict):
            params = {}

        logger.info(f"Starting STRICT 5-CHECK verification for {tool_name}")
        logger.debug(f"Params keys: {list(params.keys())}")

        # CHECK 1: Parameter Validation (STRICT, ERROR severity)
        try:
            cls._check_1_parameter_validation(tool_name, params)
            logger.info("[CHECK 1] PASSED - Parameter Validation")
        except VerificationError as e:
            if e.severity == VerificationSeverity.WARNING:
                logger.warning(f"[CHECK 1] WARNING - {e}")
            else:
                logger.error(f"[CHECK 1] FAILED - {e}")
                raise  # ERROR and CRITICAL always propagate

        # CHECK 2: Permission & Scope Validation (CRITICAL severity)
        try:
            cls._check_2_permission_scope_validation(tool_name, params)
            logger.info("[CHECK 2] PASSED - Permission & Scope Validation")
        except VerificationError as e:
            # CRITICAL checks always fail and halt
            logger.error(f"[CHECK 2] FAILED (CRITICAL) - {e}")
            raise

        # CHECK 3: Result Validation (STRICT, ERROR severity)
        try:
            cls._check_3_result_validation(tool_name, params, result)
            logger.info("[CHECK 3] PASSED - Result Validation")
        except VerificationError as e:
            if e.severity == VerificationSeverity.WARNING:
                logger.warning(f"[CHECK 3] WARNING - {e}")
            else:
                logger.error(f"[CHECK 3] FAILED - {e}")
                raise  # ERROR and CRITICAL always propagate

        # CHECK 4: Data Integrity & Consistency Validation (STRICT, ERROR severity)
        try:
            cls._check_4_data_integrity_validation(tool_name, params, result)
            logger.info("[CHECK 4] PASSED - Data Integrity & Consistency Validation")
        except VerificationError as e:
            if e.severity == VerificationSeverity.WARNING:
                logger.warning(f"[CHECK 4] WARNING - {e}")
            else:
                logger.error(f"[CHECK 4] FAILED - {e}")
                raise  # ERROR and CRITICAL always propagate

        # CHECK 5: Idempotency & Safety Validation (CRITICAL severity)
        try:
            cls._check_5_idempotency_safety_validation(tool_name, params, result)
            logger.info("[CHECK 5] PASSED - Idempotency & Safety Validation")
        except VerificationError as e:
            # CRITICAL checks always fail and halt
            logger.error(f"[CHECK 5] FAILED (CRITICAL) - {e}")
            raise

        logger.info(f"All 5 verification checks PASSED for {tool_name}")

    # =========================================================================
    # CHECK 1: Parameter Validation (enhanced verify_params)
    # Severity: ERROR
    # =========================================================================

    @classmethod
    def _check_1_parameter_validation(cls, tool_name: str, params: dict) -> None:
        """
        CHECK 1: Parameter Validation
        Validates all input parameters for correctness and completeness.
        Enhanced version of legacy verify_params with STRICT enforcement.
        """
        # Use the existing verification logic but with ERROR severity
        try:
            cls.verify_params(tool_name, params)
            cls._validate_no_invalid_payload_data(
                tool_name,
                params,
                location="params",
                block_empty_strings=False,
            )
        except VerificationError as e:
            # Re-raise with check_number and ensure ERROR severity
            if e.severity == VerificationSeverity.WARNING:
                # Keep WARNING severity for specific cases
                raise VerificationError(
                    tool_name, e.reason, check_number=1, severity=VerificationSeverity.WARNING, field=e.field
                )
            else:
                raise VerificationError(
                    tool_name, e.reason, check_number=1, severity=VerificationSeverity.ERROR, field=e.field
                )

    # =========================================================================
    # CHECK 2: Permission & Scope Validation (NEW)
    # Severity: CRITICAL
    # =========================================================================

    @classmethod
    def _check_2_permission_scope_validation(cls, tool_name: str, params: dict) -> None:
        """
        CHECK 2: Permission & Scope Validation
        CRITICAL check that validates against safety_guard policies.
        This check cannot be bypassed and will halt the system if failed.
        """
        # Import here to avoid circular dependency
        try:
            from gws_assistant.safety_guard import BULK_KEYWORDS, DESTRUCTIVE_ACTIONS
        except ImportError as e:
            logger.error(f"Could not import safety_guard module: {e}")
            raise VerificationError(
                tool_name,
                f"Safety guard module cannot be loaded: {e}",
                check_number=2,
                severity=VerificationSeverity.CRITICAL,
                field="safety_guard",
            )

        # Extract service and action from tool_name
        if "_" in tool_name:
            service, action = tool_name.split("_", 1)
        else:
            service = tool_name
            action = tool_name

        # Check if this is a destructive action
        is_destructive = False
        if service in DESTRUCTIVE_ACTIONS and action in DESTRUCTIVE_ACTIONS[service]:
            is_destructive = True

        # Check for bulk destruction keywords in parameters
        config = cls._get_config()
        # Filter out internal meta-keys before building params_str (Bug 6)
        filtered_params = {k: v for k, v in params.items() if not k.startswith("_")}
        params_str = str(filtered_params).lower()

        # Combine bulk keywords from multiple sources
        all_bulk_keywords = set(BULK_KEYWORDS)
        all_bulk_keywords.update(config.verification_bulk_indicators)

        # Use word-boundary regex for detection (Bug 7)
        bulk_keywords_detected = []
        for kw in all_bulk_keywords:
            if re.search(r"\b" + re.escape(kw) + r"\b", params_str):
                bulk_keywords_detected.append(kw)

        if bulk_keywords_detected and is_destructive:
            # Gate this on lack of confirmation (Bug 4)
            if not params.get("_bulk_confirmed"):
                raise VerificationError(
                    tool_name,
                    f"Bulk destruction keywords detected in parameters: {bulk_keywords_detected}. _bulk_confirmed marker is missing.",
                    check_number=2,
                    severity=VerificationSeverity.CRITICAL,
                    field="parameters",
                )

        # Check for suspicious parameter patterns
        for pattern_name, pattern in cls.suspicious_patterns().items():
            if re.search(pattern, params_str, re.IGNORECASE):
                if is_destructive:
                    # Gate on confirmation (Bug 4)
                    if not params.get("_bulk_confirmed") and not params.get("_safety_confirmed"):
                        raise VerificationError(
                            tool_name,
                            f"Suspicious pattern detected: {pattern_name}",
                            check_number=2,
                            severity=VerificationSeverity.CRITICAL,
                            field="parameters",
                        )

        # Validate that required scopes are present
        required_scopes_by_service = {
            "gmail": ["https://www.googleapis.com/auth/gmail.modify"],
            "drive": ["https://www.googleapis.com/auth/drive"],
            "calendar": ["https://www.googleapis.com/auth/calendar"],
            "sheets": ["https://www.googleapis.com/auth/spreadsheets"],
            "docs": ["https://www.googleapis.com/auth/documents"],
        }

        if service in required_scopes_by_service:
            # Only validate scopes if they were explicitly provided
            # (absence of _granted_scopes means scopes were not checked at this layer)
            if "_granted_scopes" in params:
                granted_scopes = params["_granted_scopes"]
                if isinstance(granted_scopes, list):
                    granted_scopes = set(granted_scopes)
                elif not isinstance(granted_scopes, set):
                    granted_scopes = set()

                required_scopes = required_scopes_by_service[service]
                missing_scopes = [scope for scope in required_scopes if scope not in granted_scopes]

                if missing_scopes:
                    logger.error(f"Service {service} missing required scopes: {missing_scopes}")
                    raise VerificationError(
                        tool_name,
                        f"Missing required scopes for {service}: {missing_scopes}",
                        check_number=2,
                        severity=VerificationSeverity.CRITICAL,
                        field="_granted_scopes",
                    )
            else:
                logger.debug(f"Service {service} requires scopes: {required_scopes_by_service[service]} (not checked at this layer)")

    # =========================================================================
    # CHECK 3: Result Validation (enhanced verify_result)
    # Severity: ERROR
    # =========================================================================

    @classmethod
    def _check_3_result_validation(cls, tool_name: str, params: dict, result: Any) -> None:
        """
        CHECK 3: Result Validation
        Validates that the operation result is valid and successful.
        Enhanced version of legacy verify_result with STRICT enforcement.
        """
        # Use the existing verification logic but with ERROR severity
        try:
            cls.verify_result(tool_name, params, result)
            cls._validate_no_invalid_payload_data(
                tool_name,
                result,
                location="result",
                block_empty_strings=False,
            )
        except VerificationError as e:
            # Re-raise with check_number and ensure ERROR severity
            if e.severity == VerificationSeverity.WARNING:
                # Keep WARNING severity for specific cases
                raise VerificationError(
                    tool_name, e.reason, check_number=3, severity=VerificationSeverity.WARNING, field=e.field
                )
            else:
                raise VerificationError(
                    tool_name, e.reason, check_number=3, severity=VerificationSeverity.ERROR, field=e.field
                )

    # =========================================================================
    # CHECK 4: Data Integrity & Consistency Validation (NEW)
    # Severity: ERROR
    # =========================================================================

    @classmethod
    def _check_4_data_integrity_validation(cls, tool_name: str, params: dict, result: Any) -> None:
        """
        CHECK 4: Data Integrity & Consistency Validation
        Validates that data remains consistent across the operation.
        Checks for data loss, corruption, or inconsistencies.
        """
        # Check 4.1: Verify attachment consistency
        try:
            cls.verify_attachment_sent(params, result)
        except VerificationError as e:
            # Attachment verification is important but can be WARNING — log and continue
            logger.warning(f"[CHECK 4.1] {e}")

        # Check 4.2: Verify document/sheet content consistency
        try:
            cls.verify_document_not_empty(tool_name, params, result)
        except VerificationError as e:
            raise VerificationError(
                tool_name, e.reason, check_number=4, severity=VerificationSeverity.ERROR, field=e.field
            )

        # Check 4.3: Verify ID consistency between params and result
        if isinstance(result, dict) and isinstance(params, dict):
            for id_field in cls.id_fields():
                param_id = params.get(id_field)
                result_id = result.get(id_field) or result.get(id_field.replace("_id", "Id")) or result.get(id_field.replace("_id", ""))

                # If ID was provided in params, it should match or be reflected in result
                if param_id and result_id:
                    if str(param_id) != str(result_id):
                        # Allow for cases where result ID is different only for create/copy operations
                        if "copy" not in tool_name and "create" not in tool_name:
                            raise VerificationError(
                                tool_name,
                                f"ID inconsistency: param {id_field}={param_id} but result has {result_id}",
                                check_number=4,
                                severity=VerificationSeverity.ERROR,
                                field=id_field,
                            )

        # Check 4.4: Verify no data truncation occurred
        if isinstance(result, dict):
            for field in cls.content_fields():
                if field in params and field in result:
                    param_content = str(params[field])
                    result_content = str(result[field])

                    # If content was set, it should be preserved (unless it's a get operation)
                    if "get" not in tool_name and "list" not in tool_name:
                        if len(param_content) > 0 and len(result_content) == 0:
                            raise VerificationError(
                                tool_name,
                                f"Data truncation detected: {field} was set but empty in result",
                                check_number=4,
                                severity=VerificationSeverity.ERROR,
                                field=field,
                            )

        # Check 4.5: Verify count consistency for list operations
        if "list" in tool_name or "search" in tool_name:
            if isinstance(result, dict):
                result_count = result.get("count") or result.get("total") or result.get("size")
                items = result.get("items") or result.get("results") or result.get("messages") or result.get("files")

                if result_count is not None and items is not None:
                    try:
                        count_value = int(result_count)
                        if isinstance(items, list) and len(items) != count_value:
                            # Allow some tolerance for pagination issues
                            if abs(len(items) - count_value) > 5:
                                raise VerificationError(
                                    tool_name,
                                    f"Count inconsistency: result reports {result_count} items but contains {len(items)}",
                                    check_number=4,
                                    severity=VerificationSeverity.WARNING,
                                    field="count",
                                )
                    except (ValueError, TypeError):
                        # Count is not parseable as integer, skip this check
                        logger.debug(f"[CHECK 4.5] Could not parse count '{result_count}' as integer, skipping count consistency check")

    # =========================================================================
    # CHECK 5: Idempotency & Safety Validation (NEW)
    # Severity: CRITICAL
    # =========================================================================

    @classmethod
    def _check_5_idempotency_safety_validation(cls, tool_name: str, params: dict, result: Any) -> None:
        """
        CHECK 5: Idempotency & Safety Validation
        CRITICAL check that validates operation idempotency and detects potential issues.
        """
        # Import here to avoid circular dependency
        try:
            from gws_assistant.safety_guard import BULK_KEYWORDS, DESTRUCTIVE_ACTIONS
        except ImportError as e:
            # Fail closed (Bug 5)
            logger.critical(f"CRITICAL: Could not import safety_guard module: {e}. Failing closed.")
            raise VerificationError(
                tool_name,
                f"Verification failed: safety_guard module could not be loaded. Error: {e}",
                check_number=5,
                severity=VerificationSeverity.CRITICAL,
                field="safety_guard",
            )

        # Extract service and action from tool_name
        if "_" in tool_name:
            service, action = tool_name.split("_", 1)
        else:
            service = tool_name
            action = tool_name

        # Check 5.1: Destructive operation safety validation
        config = cls._get_config()
        is_destructive = False

        # Check against SafetyGuard list
        if service in DESTRUCTIVE_ACTIONS and action in DESTRUCTIVE_ACTIONS[service]:
            is_destructive = True

        # Check against config list (full tool name)
        if tool_name in config.verification_destructive_operations:
            is_destructive = True

        if is_destructive:
            # Accept either _safety_confirmed or _bulk_confirmed for destructive operations
            # Bulk confirmation implicitly satisfies destructive confirmation since bulk operations
            # are potentially more dangerous than single destructive operations
            if not params.get("_safety_confirmed") and not params.get("_bulk_confirmed"):
                raise VerificationError(
                    tool_name,
                    "Destructive operation attempted without safety confirmation",
                    check_number=5,
                    severity=VerificationSeverity.CRITICAL,
                    field="_safety_confirmed",
                )

        # Check 5.2: Bulk operation confirmation validation
        config = cls._get_config()
        # Filter out internal meta-keys before building params_str (Bug 6)
        filtered_params = {k: v for k, v in params.items() if not k.startswith("_")}
        params_str = str(filtered_params).lower()

        # Combine bulk keywords from multiple sources
        all_bulk_keywords = set(BULK_KEYWORDS)
        all_bulk_keywords.update(config.verification_bulk_indicators)

        # Use word-boundary regex for detection (Bug 7)
        has_bulk_keywords = False
        for kw in all_bulk_keywords:
            if re.search(r"\b" + re.escape(kw) + r"\b", params_str):
                has_bulk_keywords = True
                break

        is_bulk_tool = any(kw in tool_name.lower() for kw in ["batch", "bulk"])

        # Special case: query: "*" often means "all"
        has_star_query = params.get("query") == "*" or params.get("q") == "*"

        if has_bulk_keywords or is_bulk_tool or has_star_query:
            if not params.get("_bulk_confirmed"):
                raise VerificationError(
                    tool_name,
                    "Bulk operation attempted without explicit confirmation",
                    check_number=5,
                    severity=VerificationSeverity.CRITICAL,
                    field="_bulk_confirmed",
                )

        # Check 5.3: Verify idempotency for create operations
        # Skip for slides since GWS binary may not return presentationId consistently
        if "create" in tool_name or "insert" in tool_name:
            if not tool_name.startswith("slides_"):
                # Create operations should return a unique ID
                if isinstance(result, dict):
                    has_id = any(k in result for k in cls.create_id_fields())
                    if not has_id:
                        raise VerificationError(
                            tool_name,
                            "Create operation must return a unique ID for idempotency tracking",
                            check_number=5,
                            severity=VerificationSeverity.ERROR,
                            field="id",
                        )

    # Note: Echo detection is handled in CHECK 3 via legacy verify_result method
    # No need to duplicate it here

    # =========================================================================
    # LEGACY METHODS (preserved for backward compatibility)
    # =========================================================================

    @classmethod
    def verify_params(cls, tool_name: str, params: dict) -> None:
        """Legacy method: Verify parameters. Use _check_1_parameter_validation instead."""
        # tool_name is expected to be "service_action"
        if "_" in tool_name:
            service, action = tool_name.split("_", 1)
        else:
            service = tool_name
            action = tool_name

        # CATEGORY 2 - GMAIL
        if (
            service == "gmail"
            or "email" in action
            or tool_name in ("send_message", "reply_message", "forward_message")
            or ("send" in action and service == "gmail")
        ):
            if "send" in tool_name or "reply" in tool_name or "forward" in tool_name:
                to = params.get("to") or params.get("to_email")
                if to is None or to == [] or cls._is_placeholder(str(to)) or not cls._is_valid_email(str(to)):
                    raise VerificationError(tool_name, "Invalid 'to' email address", severity=VerificationSeverity.ERROR, field="to")

                for field in ["cc", "bcc"]:
                    val = params.get(field)
                    if val:
                        if isinstance(val, list):
                            for v in val:
                                if not cls._is_valid_email(str(v)):
                                    raise VerificationError(tool_name, f"Invalid email in {field}", severity=VerificationSeverity.ERROR, field=field)
                        elif isinstance(val, str):
                            if not cls._is_valid_email(val):
                                raise VerificationError(tool_name, f"Invalid {field} email address", severity=VerificationSeverity.ERROR, field=field)

                # STRICT subject validation - block empty/placeholder subjects
                if "reply" not in tool_name and "forward" not in tool_name:  # Reply/Forward might not need subject
                    cls._validate_content_not_empty(
                        tool_name, params, field="subject", min_length=3, block_placeholders=True
                    )

                # STRICT body validation - block empty/placeholder content. The
                # minimum length is intentionally low (covers "ok" but allows
                # short but legitimate bodies like "Payload" used for transient
                # alerts); placeholder detection still blocks empty templates.
                cls._validate_content_not_empty(
                    tool_name, params, field="body", min_length=5, block_placeholders=True
                )

            attachments = params.get("attachments")
            if attachments is not None:
                if not isinstance(attachments, list):
                    attachments = [attachments]
                if len(attachments) == 0:
                    raise VerificationError(
                        tool_name,
                        "Attachments list cannot be empty when attachments are requested",
                        severity=VerificationSeverity.ERROR,
                        field="attachments",
                    )
                for att in attachments:
                    if isinstance(att, dict):
                        file_id = att.get("file_id")
                        file_path = att.get("file_path")
                        if (
                            (file_id is None and file_path is None)
                            or (file_id is not None and cls._is_placeholder(str(file_id)))
                            or (file_path is not None and cls._is_placeholder(str(file_path)))
                        ):
                            raise VerificationError(
                                tool_name, "Attachment must have valid file_id or file_path", severity=VerificationSeverity.ERROR, field="attachments"
                            )
                        filename = att.get("filename")
                        if not filename or cls._is_placeholder(str(filename)):
                            raise VerificationError(tool_name, "Attachment must have filename", severity=VerificationSeverity.ERROR, field="attachments")
                        mime_type = att.get("mime_type")
                        if not mime_type or not str(mime_type).strip():
                            raise VerificationError(tool_name, "Attachment must have mime_type", severity=VerificationSeverity.ERROR, field="attachments")
                        cls._validate_attachment_file(tool_name, att)
                    elif not att or cls._is_placeholder(str(att)):
                        raise VerificationError(
                            tool_name,
                            "Attachment reference must be a non-empty resolved value",
                            severity=VerificationSeverity.ERROR,
                            field="attachments",
                        )

            if "reply" in tool_name:
                thread_id = params.get("thread_id")
                if not thread_id or cls._is_placeholder(str(thread_id)):
                    raise VerificationError(tool_name, "Thread ID required for reply", severity=VerificationSeverity.ERROR, field="thread_id")

            if "forward" in tool_name or "reply" in tool_name:
                message_id = params.get("message_id")
                if not message_id or cls._is_placeholder(str(message_id)):
                    raise VerificationError(tool_name, "Message ID required for forward/reply", severity=VerificationSeverity.ERROR, field="message_id")

        # CATEGORY 3 - GOOGLE DRIVE / DOCUMENT
        if service in ("drive", "docs") or "document" in action or "file" in action or "drive" in action:
            if "create" in tool_name or "copy" in tool_name:
                # Special handling for create_document to provide specific error message
                if tool_name == "create_document" or action == "create_document":
                    title = params.get("title")
                    if not title or not str(title).strip():
                        raise VerificationError(
                            tool_name,
                            "Document title required",
                            severity=VerificationSeverity.ERROR,
                            field="title"
                        )
                    # STRICT validation for create operations - block empty/placeholder titles
                    cls._validate_content_not_empty(
                        tool_name, params,
                        field="title",
                        min_length=2,
                        block_placeholders=True
                    )
                else:
                    title = params.get("title") or params.get("name") or params.get("folder_name")
                    # Determine the actual field that holds the value being checked so error
                    # messages and validation reference the correct parameter name (e.g. copy_file
                    # uses "name", not "title").
                    field_name = (
                        "title" if params.get("title")
                        else "name" if params.get("name")
                        else "folder_name" if params.get("folder_name")
                        else "title"
                    )
                    if not title or not str(title).strip():
                        raise VerificationError(
                            tool_name,
                            f"{field_name} required",
                            severity=VerificationSeverity.ERROR,
                            field=field_name,
                        )
                    # STRICT validation for create operations - block empty/placeholder titles
                    cls._validate_content_not_empty(
                        tool_name, params,
                        field=field_name,
                        min_length=2,
                        block_placeholders=True,
                    )
            # NOTE: empty/short ``content`` for document creates is intentionally
            # NOT enforced here. CHECK 1 already covers placeholder/template
            # leakage on the *title*; emptiness of ``content`` is data-integrity
            # territory and is asserted by CHECK 4 (``verify_document_not_empty``).
            # Enforcing it here too would mask CHECK 4 coverage — see PR #76
            # round 2 review (``test_5_check_system_check_4_data_integrity``).
            content = params.get("content")
            if content is not None and "create" in tool_name and str(content).strip():
                # Only validate non-empty content for placeholder leakage; do
                # not raise on emptiness (left to CHECK 4).
                cls._validate_content_not_empty(
                    tool_name, params, field="content", min_length=1, block_placeholders=True
                )

            for id_field in ["file_id", "document_id", "spreadsheet_id"]:
                file_id = params.get(id_field)
                if file_id is not None:
                    if cls._is_placeholder(str(file_id)) or not cls._is_valid_drive_id(str(file_id)):
                        raise VerificationError(tool_name, f"Invalid {id_field}", severity=VerificationSeverity.ERROR, field=id_field)

            folder_id = params.get("folder_id")
            if folder_id is not None:
                if cls._is_placeholder(str(folder_id)):
                    raise VerificationError(tool_name, "Invalid folder_id", severity=VerificationSeverity.ERROR, field="folder_id")

            mime_type = params.get("mime_type")
            if mime_type is not None:
                if "/" not in str(mime_type):
                    raise VerificationError(tool_name, "Invalid mime_type", severity=VerificationSeverity.ERROR, field="mime_type")

            parent_id = params.get("parent_id")
            if parent_id is not None:
                if cls._is_placeholder(str(parent_id)):
                    raise VerificationError(tool_name, "Invalid parent_id", severity=VerificationSeverity.ERROR, field="parent_id")

        # CATEGORY 4 - GOOGLE SHEETS
        if service in ("sheets", "spreadsheet") or "sheet" in action or "spreadsheet" in action or "values" in action:
            spreadsheet_id = params.get("spreadsheet_id")
            if spreadsheet_id is not None:
                if cls._is_placeholder(str(spreadsheet_id)) or not cls._is_valid_drive_id(str(spreadsheet_id)):
                    raise VerificationError(tool_name, "Invalid spreadsheet_id", severity=VerificationSeverity.ERROR, field="spreadsheet_id")

            sheet_range = params.get("range")
            if sheet_range is not None:
                if not str(sheet_range).strip():
                    raise VerificationError(tool_name, "Range cannot be empty", severity=VerificationSeverity.ERROR, field="range")
                # Updated pattern to support single cells like A1, Sheet1!A1, ranges like A1:B2, and $last_spreadsheet_id, {{message_id}}
                range_pattern = re.compile(
                    r"^(?:(?:'[^']*'|[a-zA-Z0-9_ ]+)!)?[a-zA-Z]+[0-9]*(?::[a-zA-Z]+[0-9]*)?$|^(?:[$<\[{].*)$"
                )
                if not range_pattern.match(str(sheet_range)):
                    raise VerificationError(tool_name, "Invalid range format", severity=VerificationSeverity.ERROR, field="range")

            values = params.get("values")
            if "write" in tool_name or "append" in tool_name or values is not None:
                if values is None or values == [] or values == [[]]:
                    # Allow empty values for clear/delete/get
                    if all(x not in tool_name for x in ("clear", "delete", "get")):
                        raise VerificationError(tool_name, "Values cannot be empty", severity=VerificationSeverity.ERROR, field="values")

                # Check for placeholder in cells
                if isinstance(values, list):
                    for row in values:
                        if isinstance(row, list):
                            for cell in row:
                                if cell is not None and str(cell).strip() and cls._is_placeholder(str(cell)):
                                    logger.debug(f"Placeholder found in values: '{cell}', full params: {params}")
                                    raise VerificationError(tool_name, f"Placeholder found in values: {cell}", severity=VerificationSeverity.ERROR, field="values")

            sheet_name = params.get("sheet_name") or params.get("tab_name")
            if sheet_name is not None:
                if not str(sheet_name).strip():
                    raise VerificationError(tool_name, "Sheet name cannot be empty", severity=VerificationSeverity.ERROR, field="sheet_name")

        # CATEGORY 5 - GOOGLE CALENDAR
        if service == "calendar" or "event" in tool_name:
            if "create" in tool_name or "insert" in tool_name:
                # STRICT event summary validation
                cls._validate_content_not_empty(
                    tool_name, params, field="summary", min_length=3, block_placeholders=True
                )

                # STRICT description validation if provided
                description = params.get("description")
                if description is not None:
                    cls._validate_content_not_empty(
                        tool_name, params, field="description", min_length=5, block_placeholders=True
                    )

                # Heuristic often provides start_date and start_time separately
                start = params.get("start") or params.get("start_date") or params.get("start_datetime")
                end = params.get("end") or params.get("end_date") or params.get("end_datetime")

                if not start or not cls._is_valid_iso8601(start):
                    # Relative strings like "tomorrow at 10am" are allowed as long as they aren't explicit placeholders
                    if cls._is_placeholder(str(start)):
                        raise VerificationError(tool_name, "Valid start date required", severity=VerificationSeverity.ERROR, field="start")

                if end and not cls._is_valid_iso8601(end):
                    if cls._is_placeholder(str(end)):
                        raise VerificationError(tool_name, "Valid end date required", severity=VerificationSeverity.ERROR, field="end")

                if start and end and cls._is_valid_iso8601(start) and cls._is_valid_iso8601(end):
                    if not cls._end_is_after_start(start, end):
                        # For all-day events, Google allows start and end date to be the same if it's a 0-duration event?
                        # Actually GCal usually wants end > start. But let's check if they are datetimes.
                        s_val = start.get("dateTime") if isinstance(start, dict) else start
                        if "T" in str(s_val):
                            raise VerificationError(tool_name, "End time must be after start time", severity=VerificationSeverity.ERROR, field="end")
                        else:
                            # For all-day events, we might want to automatically increment if equal,
                            # but here we just warn if they are equal but not strictly less.
                            if str(start) > str(end):
                                raise VerificationError(tool_name, "End date must be on or after start date", severity=VerificationSeverity.ERROR, field="end")

            attendees = params.get("attendees")
            if attendees:
                if isinstance(attendees, list):
                    for att in attendees:
                        email = att.get("email") if isinstance(att, dict) else str(att)
                        if email and not cls._is_valid_email(email):
                            raise VerificationError(tool_name, "Invalid attendee email", severity=VerificationSeverity.ERROR, field="attendees")

            for field in ["location", "description"]:
                val = params.get(field)
                if val and cls._is_placeholder(str(val)):
                    raise VerificationError(tool_name, f"Placeholder found in {field}", severity=VerificationSeverity.ERROR, field=field)

            event_id = params.get("event_id")
            if event_id is not None:
                if cls._is_placeholder(str(event_id)):
                    raise VerificationError(tool_name, "Invalid event_id", severity=VerificationSeverity.ERROR, field="event_id")

        # CATEGORY 6 - GOOGLE TASKS
        if service == "tasks" or "task" in tool_name:
            if "create" in tool_name or "insert" in tool_name:
                # STRICT task title validation
                title = params.get("title")
                if not title or not str(title).strip():
                    raise VerificationError(
                        tool_name,
                        "Task title required",
                        severity=VerificationSeverity.ERROR,
                        field="title"
                    )
                # Detect placeholder titles (e.g. ``[Replace me]``) and raise a
                # task-specific message so the caller knows *what* needs to be
                # supplied, rather than a generic "placeholder value" error.
                title_str = str(title).strip()
                if cls._is_placeholder(title_str) or cls._has_unresolved_templates(title_str):
                    raise VerificationError(
                        tool_name,
                        "Task title required - placeholder/template value detected",
                        severity=VerificationSeverity.ERROR,
                        field="title",
                    )
                cls._validate_content_not_empty(
                    tool_name, params, field="title", min_length=2, block_placeholders=True
                )

                # STRICT notes validation if provided
                notes = params.get("notes")
                if notes is not None:
                    cls._validate_content_not_empty(
                        tool_name, params, field="notes", min_length=5, block_placeholders=True
                    )

            due = params.get("due")
            if due is not None:
                if not cls._is_valid_iso8601(str(due)):
                    raise VerificationError(tool_name, "Invalid due date format", severity=VerificationSeverity.ERROR, field="due")

            task_id = params.get("task_id")
            if task_id is not None:
                if cls._is_placeholder(str(task_id)):
                    raise VerificationError(tool_name, "Invalid task_id", severity=VerificationSeverity.ERROR, field="task_id")

            tasklist_id = params.get("tasklist_id")
            if tasklist_id is not None:
                if cls._is_placeholder(str(tasklist_id)):
                    raise VerificationError(tool_name, "Invalid tasklist_id", severity=VerificationSeverity.ERROR, field="tasklist_id")

        # CATEGORY 7 - GOOGLE CONTACTS
        if service == "contacts" or "contact" in tool_name:
            if "create" in tool_name:
                # STRICT contact name validation
                first_name = params.get("first_name")
                display_name = params.get("display_name")

                if not first_name and not display_name:
                    raise VerificationError(
                        tool_name,
                        "first_name or display_name required - cannot create contact with no name",
                        severity=VerificationSeverity.ERROR,
                        field="first_name"
                    )

                if first_name:
                    cls._validate_content_not_empty(
                        tool_name, params, field="first_name", min_length=2, block_placeholders=True
                    )

                if display_name:
                    cls._validate_content_not_empty(
                        tool_name, params, field="display_name", min_length=2, block_placeholders=True
                    )

            email = params.get("email")
            if email is not None:
                if not cls._is_valid_email(str(email)):
                    raise VerificationError(tool_name, "Invalid email", severity=VerificationSeverity.ERROR, field="email")

            phone = params.get("phone")
            if phone is not None:
                num = re.sub(r"\D", "", str(phone))
                if len(num) < 7:
                    raise VerificationError(tool_name, "Phone number too short", severity=VerificationSeverity.ERROR, field="phone")

            contact_id = params.get("contact_id")
            if contact_id is not None:
                if cls._is_placeholder(str(contact_id)):
                    raise VerificationError(tool_name, "Invalid contact_id", severity=VerificationSeverity.ERROR, field="contact_id")

        # CATEGORY 8 - GOOGLE KEEP
        if service == "keep" or "note" in tool_name:
            if "create" in tool_name or "insert" in tool_name:
                # STRICT note title validation
                title = params.get("title")
                if title is not None:
                    cls._validate_content_not_empty(
                        tool_name, params, field="title", min_length=2, block_placeholders=True
                    )

                # STRICT note body/text validation
                body = params.get("body") or params.get("text") or params.get("content")
                if body is not None:
                    cls._validate_content_not_empty(
                        tool_name, params, field="body", min_length=5, block_placeholders=True
                    )

            note_id = params.get("note_id")
            if note_id is not None:
                if cls._is_placeholder(str(note_id)):
                    raise VerificationError(tool_name, "Invalid note_id", severity=VerificationSeverity.ERROR, field="note_id")

    @classmethod
    def verify_result(cls, tool_name: str, params: dict, result: Any) -> None:
        """Legacy method: Verify result. Use _check_3_result_validation instead."""
        # CATEGORY 8 - GENERAL
        if result is None:
            raise VerificationError(tool_name, "Result is None", severity=VerificationSeverity.ERROR)

        if isinstance(result, dict):
            if not result:
                raise VerificationError(tool_name, "Result is an empty dict", severity=VerificationSeverity.WARNING)

            if result.get("success") is False or result.get("ok") is False:
                raise VerificationError(tool_name, "Result contains success/ok: False", severity=VerificationSeverity.ERROR)

            status = str(result.get("status", "")).lower()
            if status in ("error", "failed", "failure"):
                raise VerificationError(tool_name, f"Result status is {status}", severity=VerificationSeverity.ERROR)

            try:
                code = int(result.get("code", 0))
                if code >= 400:
                    raise VerificationError(tool_name, f"Result contains HTTP error code {code}", severity=VerificationSeverity.ERROR)
            except (ValueError, TypeError):
                pass

            for k, v in result.items():
                if k in ("id", "file_id", "message_id", "event_id") and v is None:
                    raise VerificationError(tool_name, f"ID field '{k}' is None", severity=VerificationSeverity.ERROR, field=k)
                if isinstance(v, str) and (k.endswith("Url") or k.endswith("Link")):
                    if not v.startswith("http"):
                        raise VerificationError(tool_name, f"URL field '{k}' does not start with http", severity=VerificationSeverity.ERROR, field=k)

            if "error" in result and result["error"]:
                raise VerificationError(tool_name, "Result contains error key with truthy value", severity=VerificationSeverity.ERROR, field="error")

            # Detect if AI returned PARAMS back as RESULT
            if len(params) > 0 and len(result) > 0:
                if all(k in result and result[k] == v for k, v in params.items()):
                    if len(result) == len(params):
                        raise VerificationError(tool_name, "Result is exactly the same as params", severity=VerificationSeverity.WARNING)

            if "create" in tool_name.lower() or "insert" in tool_name.lower():
                has_id = any(
                    k in result
                    for k in [
                        "id",
                        "documentId",
                        "spreadsheetId",
                        "fileId",
                        "messageId",
                        "resourceName",
                        "threadId",
                        "name",
                        "formId",
                        "presentationId",
                    ]
                )
                if not has_id:
                    raise VerificationError(tool_name, "Create operation result missing ID", severity=VerificationSeverity.ERROR)

        parts = tool_name.split("_")
        service = parts[0]
        action = tool_name

        # CATEGORY 2 - GMAIL
        if service == "gmail" or "message" in action or "email" in action or "send" in action:
            if isinstance(result, dict):
                # For lists, messages might be under a list
                is_list_op = "list" in tool_name or "search" in tool_name
                if is_list_op and ("messages" in result or "threads" in result or not result):
                    pass
                else:
                    msg_id = result.get("id") or result.get("messageId")
                    if (
                        not msg_id
                        and "draft" not in tool_name
                        and "send" not in tool_name
                        and "delete" not in tool_name
                        and "trash" not in tool_name
                        and not is_list_op
                    ):
                        raise VerificationError(tool_name, "Result missing id or message_id", severity=VerificationSeverity.ERROR)

                if tool_name in ("gmail_send_message", "send_message"):
                    # A real send result must have an 'id' and usually 'labelIds' containing 'SENT'
                    if not result.get("id") or (not result.get("labelIds") and not result.get("threadId")):
                        raise VerificationError(tool_name, "Send result missing id, labelIds, or threadId", severity=VerificationSeverity.ERROR)

        # CATEGORY 3 - DRIVE / DOCS
        if service in ("drive", "docs") or "document" in action or "file" in action or "drive" in action:
            if isinstance(result, dict):
                if (
                    "list" not in action
                    and "export" not in action
                    and "files" not in result
                    and "saved_file" not in result
                ):
                    doc_id = result.get("id") or result.get("documentId")
                    if not doc_id and "tabs" in result and isinstance(result["tabs"], list) and len(result["tabs"]) > 0:
                        # Tab-based document. Extract tabId as a fallback if documentId is missing at root
                        tab_props = result["tabs"][0].get("tabProperties", {})
                        doc_id = tab_props.get("tabId")

                    if not doc_id or cls._is_placeholder(str(doc_id)) or len(str(doc_id)) < 1:
                        raise VerificationError(tool_name, "Result missing valid id", severity=VerificationSeverity.ERROR, field="id")

        # CATEGORY 4 - SHEETS
        if service in ("sheets", "spreadsheet") or "sheet" in action or "spreadsheet" in action or "values" in action:
            if isinstance(result, dict):
                if "create" in tool_name:
                    if not result.get("spreadsheetId") and not result.get("id"):
                        raise VerificationError(tool_name, "Create sheet missing spreadsheetId", severity=VerificationSeverity.ERROR)

        # CATEGORY 5 - GOOGLE CALENDAR
        if service == "calendar" or "event" in tool_name:
            if isinstance(result, dict):
                if result.get("status") == "cancelled":
                    raise VerificationError(tool_name, "Event status cancelled right after creation", severity=VerificationSeverity.ERROR, field="status")

        # CATEGORY 6 - TASKS
        if service == "tasks" or "task" in tool_name:
            if isinstance(result, dict):
                task_status = result.get("status")
                if task_status and task_status not in ("needsAction", "completed"):
                    raise VerificationError(tool_name, f"Invalid task status {task_status}", severity=VerificationSeverity.ERROR, field="status")

        # CATEGORY 9 - FORMS
        if service == "forms" or "form" in tool_name:
            if isinstance(result, dict):
                if "create" in tool_name:
                    if not result.get("formId") and not result.get("id"):
                        raise VerificationError(tool_name, "Create form missing formId", severity=VerificationSeverity.ERROR)

    @classmethod
    def verify_attachment_sent(cls, params: dict, result: Any) -> None:
        """Legacy method: Verify attachment was sent. Used by CHECK 4."""
        attachments = params.get("attachments")
        if attachments and isinstance(result, dict):
            if not isinstance(attachments, list):
                attachments = [attachments]
            if len(attachments) > 0:
                expected_names = {
                    str(att.get("filename", "")).strip()
                    for att in attachments
                    if isinstance(att, dict) and str(att.get("filename", "")).strip()
                }
                # Basic check: result should have something indicating attachments were handled
                payload = result.get("payload", {})
                parts = payload.get("parts", []) if isinstance(payload, dict) else []
                if not parts:
                    parts = result.get("attachments", [])

                # If no parts/attachments are found in the result, it's a failure.
                if not parts:
                    raise VerificationError(
                        "verify_attachment", "Attachment declared in params but not confirmed in result", severity=VerificationSeverity.WARNING
                    )
                if expected_names:
                    confirmed_names = {
                        str(part.get("filename", "")).strip()
                        for part in parts
                        if isinstance(part, dict) and str(part.get("filename", "")).strip()
                    }
                    missing_names = expected_names - confirmed_names
                    if missing_names:
                        raise VerificationError(
                            "verify_attachment",
                            f"Attachment filenames not confirmed in result: {sorted(missing_names)}",
                            severity=VerificationSeverity.WARNING,
                        )

    @classmethod
    def verify_document_not_empty(cls, tool_name: str, params: dict, result: Any) -> None:
        """Legacy method: Verify document not empty. Used by CHECK 4."""
        # Normalize tool_name by stripping service prefix (e.g., "docs_create_document" -> "create_document")
        # Check both the original and the stripped name to handle both prefixed and unprefixed callers
        if "_" in tool_name:
            # Extract just the action part after the service prefix
            parts = tool_name.split("_", 1)
            normalized_name = parts[1] if len(parts) > 1 else tool_name
        else:
            normalized_name = tool_name

        target_actions = ("create_document", "append_values", "create_spreadsheet", "write_sheet", "write_values")
        if normalized_name in target_actions or tool_name in target_actions:
            content = params.get("content")
            values = params.get("values")
            if content is not None and cls._contains_invalid_content(str(content)):
                raise VerificationError(tool_name, "Operation created/wrote an empty document or sheet", severity=VerificationSeverity.ERROR, field="content")
            if values is not None and (values == [] or values == [[]]):
                raise VerificationError(tool_name, "Operation created/wrote an empty document or sheet", severity=VerificationSeverity.ERROR, field="values")
            if values is not None:
                cls._validate_no_invalid_payload_data(tool_name, values, location="values")

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    @classmethod
    def _validate_no_invalid_payload_data(
        cls,
        tool_name: str,
        payload: Any,
        location: str,
        block_empty_strings: bool = True,
    ) -> None:
        """Recursively block placeholders, empty generated content, and invalid sentinel values."""
        for path, value in cls._iter_payload_leaf_values(payload, location):
            # Always block unresolved placeholders regardless of location (before ignored check)
            if isinstance(value, str) and "___UNRESOLVED_PLACEHOLDER___" in value:
                raise VerificationError(
                    tool_name,
                    f"{location} contains unresolved placeholder data at {path}",
                    severity=VerificationSeverity.ERROR,
                    field=path,
                )
            if cls._is_ignored_validation_path(path):
                continue
            if isinstance(value, str):
                if cls._contains_invalid_content(
                    value,
                    block_empty=block_empty_strings,
                    block_generic_placeholders=location != "result" or cls._is_user_content_path(path),
                ):
                    raise VerificationError(
                        tool_name,
                        f"{location} contains invalid, empty, or unresolved placeholder data at {path}",
                        severity=VerificationSeverity.ERROR,
                        field=path,
                    )
            elif value is None and cls._is_required_data_path(path):
                raise VerificationError(
                    tool_name,
                    f"{location} contains required field with None value at {path}",
                    severity=VerificationSeverity.ERROR,
                    field=path,
                )

    @classmethod
    def _iter_payload_leaf_values(cls, payload: Any, path: str):
        if isinstance(payload, dict):
            for key, value in payload.items():
                if str(key).startswith("_"):
                    continue
                yield from cls._iter_payload_leaf_values(value, f"{path}.{key}")
        elif isinstance(payload, list):
            for index, item in enumerate(payload):
                yield from cls._iter_payload_leaf_values(item, f"{path}[{index}]")
        else:
            yield path, payload

    @classmethod
    def _is_ignored_validation_path(cls, path: str) -> bool:
        ignored_suffixes = (
            ".id",
            ".name",
            ".title",
            ".snippet",
            ".content",
            ".mimeType",
            ".query",
            ".q",
            ".size",
            ".sizeBytes",
        )
        ignored_fragments = (
            ".headers[",
            ".labelIds[",
        )
        if path == "params.code":
            return True
        if path.startswith("result.") and path.endswith(".name"):
            return True
        return path.endswith(ignored_suffixes) or any(fragment in path for fragment in ignored_fragments)

    @classmethod
    def _is_required_data_path(cls, path: str) -> bool:
        required_tokens = (
            "body",
            "content",
            "description",
            "documentId",
            "email",
            "event_id",
            "file_id",
            "filename",
            "formId",
            "id",
            "message",
            "messageId",
            "name",
            "spreadsheetId",
            "subject",
            "summary",
            "task_id",
            "text",
            "title",
        )
        path_lower = path.lower()
        return any(token.lower() in path_lower for token in required_tokens)

    @classmethod
    def _is_user_content_path(cls, path: str) -> bool:
        content_tokens = (
            "body",
            "content",
            "description",
            "message",
            "notes",
            "snippet",
            "subject",
            "summary",
            "text",
            "title",
        )
        path_lower = path.lower()
        ignored_content_fragments = (
            "autotext.content",
            "bulletstyle.",
            "bodyplaceholderlistentity",
            "paragraphmarker.bullet",
            "sectionbreak.sectionstyle",
            ".style.",
            "textstyle.",
            "textrun.style",
        )
        if any(fragment in path_lower for fragment in ignored_content_fragments):
            return False
        path_segments = {segment.lower() for segment in re.split(r"[^A-Za-z0-9_]+", path) if segment}
        return any(token in path_segments for token in content_tokens)

    @classmethod
    def _contains_invalid_content(
        cls,
        value: str,
        block_empty: bool = True,
        block_generic_placeholders: bool = True,
    ) -> bool:
        val_str = str(value).strip()
        if block_empty and not val_str:
            return True
        if not block_empty and not val_str:
            return False
        if "___UNRESOLVED_PLACEHOLDER___" in val_str:
            return True
        from gws_assistant.execution.resolver import LEGACY_PLACEHOLDER_MAP

        if any(placeholder in val_str for placeholder in LEGACY_PLACEHOLDER_MAP):
            return True
        if cls._has_unresolved_templates(val_str):
            return True
        if block_generic_placeholders and cls._is_placeholder(val_str):
            return True
        invalid_literals = {"none", "null", "undefined", "nan", "invalid data", "no data"}
        return block_generic_placeholders and val_str.lower() in invalid_literals

    @classmethod
    def _validate_attachment_file(cls, tool_name: str, attachment: dict) -> None:
        file_path = attachment.get("file_path")
        if not file_path:
            return
        path_str = str(file_path).strip()
        if cls._contains_invalid_content(path_str):
            raise VerificationError(
                tool_name,
                "Attachment file_path contains invalid or unresolved data",
                severity=VerificationSeverity.ERROR,
                field="attachments",
            )
        if not os.path.isfile(path_str):
            raise VerificationError(
                tool_name,
                f"Attachment file does not exist: {path_str}",
                severity=VerificationSeverity.ERROR,
                field="attachments",
            )
        if os.path.getsize(path_str) <= 0:
            raise VerificationError(
                tool_name,
                f"Attachment file is empty: {path_str}",
                severity=VerificationSeverity.ERROR,
                field="attachments",
            )

    @classmethod
    def _is_placeholder(cls, value: str) -> bool:
        """Check if value is a placeholder or contains unresolved template variables."""
        if value is None:
            return False
        val_str = str(value).strip()
        if not val_str:
            return True
        val_lower = val_str.lower()
        if val_lower in cls.exact_placeholders():
            return True
        if val_str in cls.numeric_placeholders():
            return True
        if val_lower in cls.exact_emails():
            return True
        for domain in cls.email_placeholder_domains():
            if val_lower.endswith(domain):
                return True
        # Check for placeholder patterns anywhere in the string (not just exact match)
        # BUT allow known resolvable placeholders from LEGACY_PLACEHOLDER_MAP
        from gws_assistant.execution.resolver import LEGACY_PLACEHOLDER_MAP
        known_placeholders = set(LEGACY_PLACEHOLDER_MAP.keys())

        for pattern in cls.PLACEHOLDER_REGEXES:
            match = pattern.search(val_str)
            if match:
                # Check if this is a known resolvable placeholder
                matched_text = match.group(0)
                if matched_text in known_placeholders:
                    continue  # Allow known resolvable placeholders
                return True
        if cls.SPECIAL_CHARS_ONLY.match(val_str):
            return True
        # Check for unresolved template patterns (excluding known placeholders)
        if cls._has_unresolved_templates(val_str):
            # Double-check that it's not just a known placeholder
            for ph in known_placeholders:
                if ph in val_str:
                    return False
            return True
        return False

    @classmethod
    def _has_unresolved_templates(cls, value: str) -> bool:
        """Detect if string contains unresolved template variables."""
        if not value:
            return False
        # Import known resolvable placeholders
        from gws_assistant.execution.resolver import LEGACY_PLACEHOLDER_MAP
        known_placeholders = set(LEGACY_PLACEHOLDER_MAP.keys())

        for pattern in cls.UNRESOLVED_TEMPLATE_PATTERNS:
            match = pattern.search(value)
            if match:
                # Check if this matched text is a known resolvable placeholder
                matched_text = match.group(0)
                if matched_text in known_placeholders:
                    continue  # Allow known resolvable placeholders
                return True
        return False

    @classmethod
    def _is_empty_or_whitespace_only(cls, value: Any) -> bool:
        """Check if value is empty, None, or contains only whitespace/special chars."""
        if value is None:
            return True
        val_str = str(value).strip()
        if not val_str:
            return True
        # Check if only whitespace or special characters
        if cls.SPECIAL_CHARS_ONLY.match(val_str):
            return True
        return False

    @classmethod
    def _validate_content_not_empty(
        cls, tool_name: str, params: dict, field: str, min_length: int = 1, block_placeholders: bool = True
    ) -> None:
        """Validate that content field is not empty and has no placeholders."""
        value = params.get(field)

        # Check for None or empty
        if value is None:
            raise VerificationError(
                tool_name,
                f"Required field '{field}' is None/missing - cannot create document with empty data",
                severity=VerificationSeverity.ERROR,
                field=field
            )

        val_str = str(value).strip()

        # Check for empty/whitespace only
        if not val_str:
            raise VerificationError(
                tool_name,
                f"Field '{field}' is empty or whitespace-only - cannot create document with no content",
                severity=VerificationSeverity.ERROR,
                field=field
            )

        # Check minimum length
        if len(val_str) < min_length:
            raise VerificationError(
                tool_name,
                f"Field '{field}' content too short ({len(val_str)} chars, min {min_length}) - content appears incomplete",
                severity=VerificationSeverity.ERROR,
                field=field
            )

        # Check for placeholders if enabled
        if block_placeholders:
            if cls._is_placeholder(val_str):
                raise VerificationError(
                    tool_name,
                    f"Field '{field}' contains placeholder value '{val_str[:50]}...' - template variable was not resolved",
                    severity=VerificationSeverity.ERROR,
                    field=field
                )

            if cls._has_unresolved_templates(val_str):
                raise VerificationError(
                    tool_name,
                    f"Field '{field}' contains unresolved template variable - value was not properly substituted",
                    severity=VerificationSeverity.ERROR,
                    field=field
                )

        # Check for suspicious content patterns (repeated special chars, etc.)
        if cls.SPECIAL_CHARS_ONLY.match(val_str):
            raise VerificationError(
                tool_name,
                f"Field '{field}' contains only special characters - content appears invalid",
                severity=VerificationSeverity.ERROR,
                field=field
            )

    @classmethod
    def _is_valid_email(cls, value: str) -> bool:
        if cls._is_placeholder(value):
            return False
        return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", str(value)))

    @classmethod
    def _is_valid_iso8601(cls, value: Any) -> bool:
        if isinstance(value, dict):
            value = value.get("dateTime") or value.get("date")
        if not value:
            return False
        val_str = str(value)
        return bool(re.match(r"^\d{4}-\d{2}-\d{2}", val_str))

    @classmethod
    def _is_valid_url(cls, value: str) -> bool:
        return str(value).startswith("http")

    @classmethod
    def _is_valid_drive_id(cls, value: str) -> bool:
        val_str = str(value)
        # Allow internal placeholders and specific recognized prefixes
        if any(val_str.startswith(prefix) for prefix in ["sheet-", "doc-", "folder-", "file-", "evt-", "sent-", "$", "{{"]):
            return len(val_str) > 2
        # Regular Drive IDs are URL-safe base64 encoded (25-60 chars).
        # Allow: alphanumeric, hyphen, underscore, period, and equals padding.
        return bool(re.match(r"^[a-zA-Z0-9_\-.=]{2,128}$", val_str))

    @classmethod
    def _end_is_after_start(cls, start: Any, end: Any) -> bool:
        from datetime import datetime

        def extract_date(v):
            if isinstance(v, dict):
                return v.get("dateTime") or v.get("date")
            return v

        s = extract_date(start)
        e = extract_date(end)
        if not s or not e:
            return True
        try:
            s_dt = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
            e_dt = datetime.fromisoformat(str(e).replace("Z", "+00:00"))
            return e_dt > s_dt
        except Exception:
            return str(e) > str(s)
