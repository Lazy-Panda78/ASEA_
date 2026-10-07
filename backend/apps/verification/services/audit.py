import copy
from ..models import AuditLog


class AuditLogService:
    """
    Service responsible for recording append-only audit trail entries
    and ensuring sensitive credentials, tokens, or API keys are sanitized.
    """

    SENSITIVE_KEYWORDS = {
        'key', 'secret', 'token', 'auth', 'password',
        'bearer', 'credential', 'private', 'api_key', 'authorization'
    }

    @classmethod
    def sanitize_details(cls, details):
        """
        Recursively sanitizes dictionary/list details to mask sensitive fields.
        """
        if details is None:
            return {}

        if not isinstance(details, (dict, list)):
            return details

        cloned = copy.deepcopy(details)
        return cls._sanitize_recursive(cloned)

    @classmethod
    def _sanitize_recursive(cls, data):
        if isinstance(data, dict):
            sanitized = {}
            for key, val in data.items():
                lower_key = str(key).lower()
                if any(keyword in lower_key for keyword in cls.SENSITIVE_KEYWORDS):
                    sanitized[key] = "[REDACTED]"
                else:
                    sanitized[key] = cls._sanitize_recursive(val)
            return sanitized
        elif isinstance(data, list):
            return [cls._sanitize_recursive(item) for item in data]
        else:
            return data

    @classmethod
    def log_event(cls, verification_run, event, status, details=None):
        """
        Creates an append-only audit log entry associated with a VerificationRun.
        """
        sanitized_details = cls.sanitize_details(details)
        return AuditLog.objects.create(
            verification_run=verification_run,
            event=event,
            status=status,
            details=sanitized_details
        )
