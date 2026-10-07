import uuid
from django.db import models

class VerificationRunStatus(models.TextChoices):
    QUEUED = 'QUEUED', 'Queued'
    INGESTING = 'INGESTING', 'Ingesting'
    INGESTED = 'INGESTED', 'Ingested'
    SCANNING = 'SCANNING', 'Scanning'
    SCANNED = 'SCANNED', 'Scanned'
    SCAN_FAILED = 'SCAN_FAILED', 'Scan Failed'
    CHECKING_ARCHITECTURE = 'CHECKING_ARCHITECTURE', 'Checking Architecture'
    ARCHITECTURE_CHECKED = 'ARCHITECTURE_CHECKED', 'Architecture Checked'
    ARCHITECTURE_FAILED = 'ARCHITECTURE_FAILED', 'Architecture Failed'
    SCORING = 'SCORING', 'Scoring'
    SCORED = 'SCORED', 'Scored'
    SCORE_FAILED = 'SCORE_FAILED', 'Score Failed'
    FAILED = 'FAILED', 'Failed'

class VerificationRun(models.Model):
    """
    Core database model representing a single code verification run.
    Stores PR/Diff ingestion details and execution state.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    repository_url = models.URLField(max_length=500, help_text="Git repository URL")
    provider = models.CharField(max_length=50, default='github', help_text="VCS Provider (github, gitlab, etc.)")
    pr_number = models.IntegerField(null=True, blank=True, help_text="Pull Request / Merge Request number")
    status = models.CharField(
        max_length=30,
        choices=VerificationRunStatus.choices,
        default=VerificationRunStatus.QUEUED,
        help_text="Current execution status of the run"
    )
    ingestion_data = models.JSONField(default=dict, blank=True, help_text="Normalized PR and diff metadata")
    findings = models.JSONField(default=list, blank=True, help_text="Negative-space scanner findings")
    architecture_findings = models.JSONField(default=list, blank=True, help_text="Architecture fit checker findings")
    confidence_score = models.IntegerField(null=True, blank=True, help_text="Confidence score 0-100")
    score_explanation = models.TextField(blank=True, default="", help_text="Explanation of confidence score calculation")
    score_breakdown = models.JSONField(default=list, blank=True, help_text="Detailed penalty breakdown for confidence score")
    error_message = models.TextField(blank=True, default="", help_text="Error details if verification run failed")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Verification Run'
        verbose_name_plural = 'Verification Runs'

    def __str__(self):
        return f"VerificationRun {self.id} ({self.provider} PR #{self.pr_number}) - {self.status}"


class AuditLog(models.Model):
    """
    Append-only audit trail entry associated with a VerificationRun.
    Records key pipeline stages, statuses, timestamps, and metadata details.
    """
    verification_run = models.ForeignKey(
        VerificationRun,
        on_delete=models.CASCADE,
        related_name='audit_logs',
        help_text="Associated verification run"
    )
    event = models.CharField(max_length=100, help_text="Pipeline event or stage name")
    status = models.CharField(max_length=50, help_text="Status of event (SUCCESS, FAILED, etc.)")
    details = models.JSONField(default=dict, blank=True, help_text="Sanitized event details and context")
    timestamp = models.DateTimeField(auto_now_add=True, help_text="Timestamp when audit log was recorded")

    class Meta:
        ordering = ['timestamp']
        verbose_name = 'Audit Log'
        verbose_name_plural = 'Audit Logs'

    def __str__(self):
        return f"AuditLog [{self.event}] ({self.status}) for Run {self.verification_run_id} at {self.timestamp}"

