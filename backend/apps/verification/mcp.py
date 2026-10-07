import json
import uuid
from typing import Dict, Any, Optional

from .models import VerificationRun, VerificationRunStatus
from .serializers import AuditLogSerializer
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


class ASEAMCPInterface:
    """
    Model Context Protocol (MCP) Interface exposing ASEA code verification capabilities.
    Reuses existing verification services without duplicating logic.
    """

    @classmethod
    def submit_verification(cls, repo_url: str, pr_number: int) -> Dict[str, Any]:
        """
        Submits a PR for full ASEA verification and returns the complete execution report.
        """
        # 1. Create run in QUEUED status
        run = VerificationRun.objects.create(
            repository_url=repo_url,
            provider='github',
            pr_number=pr_number,
            status=VerificationRunStatus.QUEUED
        )

        try:
            # 2. Ingestion
            run.status = VerificationRunStatus.INGESTING
            run.save(update_fields=['status', 'updated_at'])

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

            # 3. Negative-Space Scan
            run.status = VerificationRunStatus.SCANNING
            run.save(update_fields=['status', 'updated_at'])
            findings = NegativeSpaceScannerService.scan(run)
            run.findings = findings
            run.status = VerificationRunStatus.SCANNED
            run.save(update_fields=['findings', 'status', 'updated_at'])

            AuditLogService.log_event(
                verification_run=run,
                event='NEGATIVE_SPACE_SCAN',
                status='SUCCESS',
                details={'findingsCount': len(findings)}
            )

            # 4. Architecture Fit Check
            run.status = VerificationRunStatus.CHECKING_ARCHITECTURE
            run.save(update_fields=['status', 'updated_at'])
            arch_findings = ArchitectureCheckerService.check(run)
            run.architecture_findings = arch_findings
            run.status = VerificationRunStatus.ARCHITECTURE_CHECKED
            run.save(update_fields=['architecture_findings', 'status', 'updated_at'])

            AuditLogService.log_event(
                verification_run=run,
                event='ARCHITECTURE_CHECK',
                status='SUCCESS',
                details={'findingsCount': len(arch_findings)}
            )

            # 5. Explainable Confidence Scoring
            run.status = VerificationRunStatus.SCORING
            run.save(update_fields=['status', 'updated_at'])
            score, explanation, breakdown = ConfidenceScoringService.calculate_score(run)
            run.confidence_score = score
            run.score_explanation = explanation
            run.score_breakdown = breakdown
            run.status = VerificationRunStatus.SCORED
            run.save(update_fields=[
                'confidence_score', 'score_explanation', 'score_breakdown', 'status', 'updated_at'
            ])

            AuditLogService.log_event(
                verification_run=run,
                event='CONFIDENCE_SCORING',
                status='SUCCESS',
                details={'score': score, 'breakdownCount': len(breakdown)}
            )

            return {
                "runId": str(run.id),
                "status": run.status,
                "confidenceScore": score,
                "explanation": explanation,
                "breakdown": breakdown,
                "findings": findings,
                "architectureFindings": arch_findings,
            }

        except (GitHubIngestionError, NegativeSpaceScannerError, ArchitectureCheckerError, ConfidenceScoringError, Exception) as exc:
            run.status = VerificationRunStatus.FAILED
            run.error_message = str(exc)
            run.save(update_fields=['status', 'error_message', 'updated_at'])

            AuditLogService.log_event(
                verification_run=run,
                event='PIPELINE_EXECUTION',
                status='FAILED',
                details={'error': str(exc)}
            )

            return {
                "runId": str(run.id),
                "status": run.status,
                "error": str(exc)
            }

    @classmethod
    def get_verification_result(cls, run_id: str) -> Dict[str, Any]:
        """
        Retrieves verification status, findings, confidence score, explanation, and audit trail for a run ID.
        """
        try:
            val_uuid = uuid.UUID(str(run_id))
            run = VerificationRun.objects.get(id=val_uuid)
        except (ValueError, VerificationRun.DoesNotExist):
            return {"error": "Verification run not found."}

        audit_logs = run.audit_logs.all().order_by('timestamp')
        audit_serializer = AuditLogSerializer(audit_logs, many=True)

        return {
            "runId": str(run.id),
            "status": run.status,
            "repositoryUrl": run.repository_url,
            "prNumber": run.pr_number,
            "confidenceScore": run.confidence_score,
            "explanation": run.score_explanation,
            "breakdown": run.score_breakdown,
            "findings": run.findings,
            "architectureFindings": run.architecture_findings,
            "errorMessage": run.error_message,
            "auditTrail": audit_serializer.data,
            "createdAt": run.created_at.isoformat() if run.created_at else None,
            "updatedAt": run.updated_at.isoformat() if run.updated_at else None,
        }

    @classmethod
    def process_jsonrpc(cls, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processes standard MCP JSON-RPC 2.0 request messages.
        """
        rpc_id = request.get("id")
        method = request.get("method")
        params = request.get("params", {})

        if method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": rpc_id,
                "result": {
                    "tools": [
                        {
                            "name": "asea_submit_verification",
                            "description": "Submit a GitHub Pull Request for full ASEA verification analysis.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "repo_url": {
                                        "type": "string",
                                        "description": "GitHub repository URL"
                                    },
                                    "pr_number": {
                                        "type": "integer",
                                        "description": "Pull Request number"
                                    }
                                },
                                "required": ["repo_url", "pr_number"]
                            }
                        },
                        {
                            "name": "asea_get_verification_result",
                            "description": "Retrieve status, score, findings, and audit trail for an ASEA verification run.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "run_id": {
                                        "type": "string",
                                        "description": "VerificationRun UUID"
                                    }
                                },
                                "required": ["run_id"]
                            }
                        }
                    ]
                }
            }

        elif method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments", {})

            if tool_name == "asea_submit_verification":
                repo_url = arguments.get("repo_url")
                pr_number = arguments.get("pr_number")

                if not repo_url or not pr_number:
                    return {
                        "jsonrpc": "2.0",
                        "id": rpc_id,
                        "error": {
                            "code": -32602,
                            "message": "Missing required arguments: 'repo_url' and 'pr_number'."
                        }
                    }

                result = cls.submit_verification(repo_url, int(pr_number))
                return {
                    "jsonrpc": "2.0",
                    "id": rpc_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(result, indent=2)
                            }
                        ]
                    }
                }

            elif tool_name == "asea_get_verification_result":
                run_id = arguments.get("run_id")
                if not run_id:
                    return {
                        "jsonrpc": "2.0",
                        "id": rpc_id,
                        "error": {
                            "code": -32602,
                            "message": "Missing required argument: 'run_id'."
                        }
                    }

                result = cls.get_verification_result(run_id)
                return {
                    "jsonrpc": "2.0",
                    "id": rpc_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(result, indent=2)
                            }
                        ]
                    }
                }

            else:
                return {
                    "jsonrpc": "2.0",
                    "id": rpc_id,
                    "error": {
                        "code": -32601,
                        "message": f"Tool '{tool_name}' not found."
                    }
                }

        else:
            return {
                "jsonrpc": "2.0",
                "id": rpc_id,
                "error": {
                    "code": -32601,
                    "message": f"Method '{method}' not found."
                }
            }
