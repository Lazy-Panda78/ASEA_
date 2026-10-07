from rest_framework import serializers
from .models import VerificationRun, AuditLog
from .services import GitHubIngestionService, GitHubIngestionError

class VerificationRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = VerificationRun
        fields = [
            'id',
            'repository_url',
            'provider',
            'pr_number',
            'status',
            'ingestion_data',
            'findings',
            'architecture_findings',
            'confidence_score',
            'score_explanation',
            'score_breakdown',
            'error_message',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class SubmitIngestionSerializer(serializers.Serializer):
    repoUrl = serializers.URLField(required=True, help_text="GitHub repository URL")
    prNumber = serializers.IntegerField(required=True, min_value=1, help_text="Pull request number")

    def validate_repoUrl(self, value):
        try:
            GitHubIngestionService.parse_github_url(value)
        except GitHubIngestionError as e:
            raise serializers.ValidationError(str(e))
        return value


class AuditLogSerializer(serializers.ModelSerializer):
    runId = serializers.CharField(source='verification_run.id', read_only=True)

    class Meta:
        model = AuditLog
        fields = [
            'id',
            'runId',
            'event',
            'status',
            'timestamp',
            'details',
        ]
        read_only_fields = ['id', 'runId', 'event', 'status', 'timestamp', 'details']

