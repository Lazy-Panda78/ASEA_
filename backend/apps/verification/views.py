from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework import status
from django.db import connection

from .models import VerificationRun, VerificationRunStatus
from .serializers import SubmitIngestionSerializer, VerificationRunSerializer, AuditLogSerializer
from .services import (
    GitHubIngestionService,
    GitHubIngestionError,
    NegativeSpaceScannerService,
    NegativeSpaceScannerError,
    ArchitectureCheckerService,
    ArchitectureCheckerError,
    ConfidenceScoringService,
    ConfidenceScoringError,
    AuditLogService,
)


class HealthCheckView(APIView):
    """
    Health check endpoint to verify Django backend function and database connectivity.
    Unauthenticated access allowed.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        health_details = {
            "status": "ok"
        }
        
        try:
            connection.ensure_connection()
            health_details["database"] = "connected"
            http_status = status.HTTP_200_OK
        except Exception as e:
            health_details["database"] = f"error: {str(e)}"
            health_details["status"] = "degraded"
            http_status = status.HTTP_503_SERVICE_UNAVAILABLE

        return Response(health_details, status=http_status)


class ProtectedTestView(APIView):
    """
    Protected endpoint to test JWT authentication.
    Requires a valid Bearer token.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({
            "message": "Authenticated successfully",
            "user": request.user.username
        }, status=status.HTTP_200_OK)


class SubmitVerificationView(APIView):
    """
    POST /api/verify/submit
    Submits a GitHub PR and repository for diff ingestion and verification run creation.
    Requires JWT authentication.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = SubmitIngestionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        repo_url = serializer.validated_data['repoUrl']
        pr_number = serializer.validated_data['prNumber']

        # 1. Create initial run in QUEUED status
        run = VerificationRun.objects.create(
            repository_url=repo_url,
            provider='github',
            pr_number=pr_number,
            status=VerificationRunStatus.QUEUED
        )

        # 2. Transition to INGESTING status
        run.status = VerificationRunStatus.INGESTING
        run.save(update_fields=['status', 'updated_at'])

        # 3. Perform GitHub PR & Diff ingestion
        try:
            ingestion_data = GitHubIngestionService.ingest_pull_request(repo_url, pr_number)
            run.ingestion_data = ingestion_data
            run.status = VerificationRunStatus.INGESTED
            run.save(update_fields=['ingestion_data', 'status', 'updated_at'])

            AuditLogService.log_event(
                verification_run=run,
                event='PR_INGESTION',
                status='SUCCESS',
                details={
                    'repository_url': repo_url,
                    'pr_number': pr_number,
                    'files_count': len(ingestion_data.get('files', []))
                }
            )

            return Response({
                "runId": str(run.id),
                "status": run.status
            }, status=status.HTTP_202_ACCEPTED)

        except GitHubIngestionError as exc:
            run.status = VerificationRunStatus.FAILED
            run.error_message = str(exc)
            run.save(update_fields=['status', 'error_message', 'updated_at'])

            AuditLogService.log_event(
                verification_run=run,
                event='PR_INGESTION',
                status='FAILED',
                details={'error': str(exc)}
            )

            return Response({
                "runId": str(run.id),
                "status": run.status,
                "error": str(exc)
            }, status=status.HTTP_400_BAD_REQUEST)

        except Exception as exc:
            run.status = VerificationRunStatus.FAILED
            run.error_message = f"Unexpected error: {str(exc)}"
            run.save(update_fields=['status', 'error_message', 'updated_at'])

            AuditLogService.log_event(
                verification_run=run,
                event='PR_INGESTION',
                status='FAILED',
                details={'error': str(exc)}
            )

            return Response({
                "runId": str(run.id),
                "status": run.status,
                "error": "Failed to ingest pull request."
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ScanVerificationView(APIView):
    """
    POST /api/verify/<uuid:run_id>/scan
    Triggers Module 3 Negative-Space Scanner on an ingested VerificationRun.
    Requires JWT authentication.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, run_id):
        try:
            run = VerificationRun.objects.get(id=run_id)
        except VerificationRun.DoesNotExist:
            return Response({"error": "Verification run not found."}, status=status.HTTP_404_NOT_FOUND)

        run.status = VerificationRunStatus.SCANNING
        run.save(update_fields=['status', 'updated_at'])

        try:
            findings = NegativeSpaceScannerService.scan(run)
            run.findings = findings
            run.status = VerificationRunStatus.SCANNED
            run.error_message = ""
            run.save(update_fields=['findings', 'status', 'error_message', 'updated_at'])

            AuditLogService.log_event(
                verification_run=run,
                event='NEGATIVE_SPACE_SCAN',
                status='SUCCESS',
                details={'findingsCount': len(findings)}
            )

            return Response({
                "runId": str(run.id),
                "status": run.status,
                "findingsCount": len(findings),
                "findings": findings
            }, status=status.HTTP_200_OK)

        except NegativeSpaceScannerError as exc:
            run.status = VerificationRunStatus.SCAN_FAILED
            run.error_message = str(exc)
            run.save(update_fields=['status', 'error_message', 'updated_at'])

            AuditLogService.log_event(
                verification_run=run,
                event='NEGATIVE_SPACE_SCAN',
                status='FAILED',
                details={'error': str(exc)}
            )

            return Response({
                "runId": str(run.id),
                "status": run.status,
                "error": str(exc)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        except Exception as exc:
            run.status = VerificationRunStatus.SCAN_FAILED
            run.error_message = f"Unexpected scan error: {str(exc)}"
            run.save(update_fields=['status', 'error_message', 'updated_at'])

            AuditLogService.log_event(
                verification_run=run,
                event='NEGATIVE_SPACE_SCAN',
                status='FAILED',
                details={'error': str(exc)}
            )

            return Response({
                "runId": str(run.id),
                "status": run.status,
                "error": "Failed to complete negative-space scan."
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ArchitectureCheckView(APIView):
    """
    POST /api/verify/<uuid:run_id>/architecture
    Triggers Module 4 Architecture Fit Checker on a VerificationRun.
    Requires JWT authentication.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, run_id):
        try:
            run = VerificationRun.objects.get(id=run_id)
        except VerificationRun.DoesNotExist:
            return Response({"error": "Verification run not found."}, status=status.HTTP_404_NOT_FOUND)

        run.status = VerificationRunStatus.CHECKING_ARCHITECTURE
        run.save(update_fields=['status', 'updated_at'])

        try:
            findings = ArchitectureCheckerService.check(run)
            run.architecture_findings = findings
            run.status = VerificationRunStatus.ARCHITECTURE_CHECKED
            run.error_message = ""
            run.save(update_fields=['architecture_findings', 'status', 'error_message', 'updated_at'])

            AuditLogService.log_event(
                verification_run=run,
                event='ARCHITECTURE_CHECK',
                status='SUCCESS',
                details={'findingsCount': len(findings)}
            )

            return Response({
                "runId": str(run.id),
                "status": run.status,
                "findingsCount": len(findings),
                "findings": findings
            }, status=status.HTTP_200_OK)

        except ArchitectureCheckerError as exc:
            run.status = VerificationRunStatus.ARCHITECTURE_FAILED
            run.error_message = str(exc)
            run.save(update_fields=['status', 'error_message', 'updated_at'])

            AuditLogService.log_event(
                verification_run=run,
                event='ARCHITECTURE_CHECK',
                status='FAILED',
                details={'error': str(exc)}
            )

            return Response({
                "runId": str(run.id),
                "status": run.status,
                "error": str(exc)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        except Exception as exc:
            run.status = VerificationRunStatus.ARCHITECTURE_FAILED
            run.error_message = f"Unexpected architecture check error: {str(exc)}"
            run.save(update_fields=['status', 'error_message', 'updated_at'])

            AuditLogService.log_event(
                verification_run=run,
                event='ARCHITECTURE_CHECK',
                status='FAILED',
                details={'error': str(exc)}
            )

            return Response({
                "runId": str(run.id),
                "status": run.status,
                "error": "Failed to complete architecture fit check."
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ScoreVerificationView(APIView):
    """
    POST /api/verify/<uuid:run_id>/score
    Triggers Module 5 Explainable Confidence Scoring on a VerificationRun.
    Requires JWT authentication.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, run_id):
        try:
            run = VerificationRun.objects.get(id=run_id)
        except VerificationRun.DoesNotExist:
            return Response({"error": "Verification run not found."}, status=status.HTTP_404_NOT_FOUND)

        run.status = VerificationRunStatus.SCORING
        run.save(update_fields=['status', 'updated_at'])

        try:
            score, explanation, breakdown = ConfidenceScoringService.calculate_score(run)
            run.confidence_score = score
            run.score_explanation = explanation
            run.score_breakdown = breakdown
            run.status = VerificationRunStatus.SCORED
            run.error_message = ""
            run.save(update_fields=[
                'confidence_score',
                'score_explanation',
                'score_breakdown',
                'status',
                'error_message',
                'updated_at'
            ])

            AuditLogService.log_event(
                verification_run=run,
                event='CONFIDENCE_SCORING',
                status='SUCCESS',
                details={'score': score, 'breakdownCount': len(breakdown)}
            )

            return Response({
                "runId": str(run.id),
                "status": run.status,
                "score": score,
                "explanation": explanation,
                "breakdown": breakdown
            }, status=status.HTTP_200_OK)

        except ConfidenceScoringError as exc:
            run.status = VerificationRunStatus.SCORE_FAILED
            run.error_message = str(exc)
            run.save(update_fields=['status', 'error_message', 'updated_at'])

            AuditLogService.log_event(
                verification_run=run,
                event='CONFIDENCE_SCORING',
                status='FAILED',
                details={'error': str(exc)}
            )

            return Response({
                "runId": str(run.id),
                "status": run.status,
                "error": str(exc)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        except Exception as exc:
            run.status = VerificationRunStatus.SCORE_FAILED
            run.error_message = f"Unexpected scoring error: {str(exc)}"
            run.save(update_fields=['status', 'error_message', 'updated_at'])

            AuditLogService.log_event(
                verification_run=run,
                event='CONFIDENCE_SCORING',
                status='FAILED',
                details={'error': str(exc)}
            )

            return Response({
                "runId": str(run.id),
                "status": run.status,
                "error": "Failed to calculate confidence score."
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AuditLogView(APIView):
    """
    GET /api/verify/<uuid:run_id>/audit
    Returns the append-only audit trail in chronological order for a VerificationRun.
    Requires JWT authentication.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, run_id):
        try:
            run = VerificationRun.objects.get(id=run_id)
        except VerificationRun.DoesNotExist:
            return Response({"error": "Verification run not found."}, status=status.HTTP_404_NOT_FOUND)

        audit_logs = run.audit_logs.all().order_by('timestamp')
        serializer = AuditLogSerializer(audit_logs, many=True)

        return Response({
            "runId": str(run.id),
            "auditTrail": serializer.data
        }, status=status.HTTP_200_OK)


class CITriggerVerificationView(APIView):
    """
    POST /api/verify/ci-trigger
    Synchronously triggers full ASEA verification pipeline for CI/CD runners (GitHub Actions).
    Requires JWT authentication.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from .mcp import ASEAMCPInterface

        serializer = SubmitIngestionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        repo_url = serializer.validated_data['repoUrl']
        pr_number = serializer.validated_data['prNumber']

        result = ASEAMCPInterface.submit_verification(repo_url, pr_number)

        status_code = status.HTTP_200_OK if result.get("status") == "SCORED" else status.HTTP_400_BAD_REQUEST
        return Response(result, status=status_code)





