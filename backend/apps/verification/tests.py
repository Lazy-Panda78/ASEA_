import os
import uuid
import json
from unittest.mock import patch, MagicMock
from django.urls import reverse
from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APITestCase

from .models import VerificationRun, VerificationRunStatus, AuditLog
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



class HealthCheckTests(APITestCase):
    def test_health_check_endpoint(self):
        """Test GET /api/health/ returns HTTP 200 and status ok."""
        url = reverse('health_check')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get('status'), 'ok')
        self.assertEqual(response.data.get('database'), 'connected')


class VerificationRunModelTests(APITestCase):
    def test_create_verification_run(self):
        """Test creation of VerificationRun model instance with ingestion_data."""
        run = VerificationRun.objects.create(
            repository_url="https://github.com/example/repo",
            provider="github",
            pr_number=42,
            status=VerificationRunStatus.QUEUED,
            ingestion_data={"test": "data"}
        )
        self.assertIsInstance(run.id, uuid.UUID)
        self.assertEqual(run.provider, "github")
        self.assertEqual(run.pr_number, 42)
        self.assertEqual(run.status, VerificationRunStatus.QUEUED)
        self.assertEqual(run.ingestion_data, {"test": "data"})
        self.assertIn("VerificationRun", str(run))


class JWTAuthenticationTests(APITestCase):
    def setUp(self):
        self.username = 'testuser'
        self.password = 'StrongTestPassword123!'
        self.user = User.objects.create_user(
            username=self.username,
            password=self.password,
            email='test@example.com'
        )
        self.token_url = reverse('token_obtain_pair')
        self.token_refresh_url = reverse('token_refresh')
        self.protected_url = reverse('protected_test')

    def test_jwt_login_success(self):
        """Test obtaining JWT tokens with valid credentials."""
        response = self.client.post(self.token_url, {
            'username': self.username,
            'password': self.password
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)

    def test_jwt_refresh_token(self):
        """Test refreshing an access token using a refresh token."""
        login_response = self.client.post(self.token_url, {
            'username': self.username,
            'password': self.password
        }, format='json')
        refresh_token = login_response.data['refresh']

        refresh_response = self.client.post(self.token_refresh_url, {
            'refresh': refresh_token
        }, format='json')
        self.assertEqual(refresh_response.status_code, status.HTTP_200_OK)
        self.assertIn('access', refresh_response.data)

    def test_protected_endpoint_unauthenticated_rejects(self):
        """Test unauthenticated request to protected endpoint returns HTTP 401."""
        response = self.client.get(self.protected_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_protected_endpoint_authenticated_succeeds(self):
        """Test authenticated request with valid Bearer token returns HTTP 200."""
        login_response = self.client.post(self.token_url, {
            'username': self.username,
            'password': self.password
        }, format='json')
        access_token = login_response.data['access']

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        response = self.client.get(self.protected_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get('user'), self.username)


class SubmitIngestionTests(APITestCase):
    def setUp(self):
        self.username = 'developer'
        self.password = 'SecurePassword123!'
        self.user = User.objects.create_user(
            username=self.username,
            password=self.password
        )
        self.submit_url = reverse('verification_submit')

        # Obtain JWT Token
        login_res = self.client.post(reverse('token_obtain_pair'), {
            'username': self.username,
            'password': self.password
        }, format='json')
        self.access_token = login_res.data['access']

    def test_submit_verification_unauthenticated_fails(self):
        """Test POST /api/verify/submit without JWT token returns HTTP 401."""
        response = self.client.post(self.submit_url, {
            "repoUrl": "https://github.com/owner/repository",
            "prNumber": 42
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_submit_verification_invalid_url_fails(self):
        """Test submit endpoint rejects non-GitHub repository URLs with HTTP 400."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')
        response = self.client.post(self.submit_url, {
            "repoUrl": "https://gitlab.com/owner/repository",
            "prNumber": 42
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("repoUrl", response.data)

    @patch('requests.get')
    def test_submit_verification_success_mocked_github(self, mock_get):
        """Test successful PR/Diff ingestion with mocked GitHub API response."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')

        # Mock GitHub PR Response
        mock_pr_response = MagicMock()
        mock_pr_response.status_code = 200
        mock_pr_response.json.return_value = {
            "title": "Add Module 1 Ingestion",
            "body": "Implements PR diff ingestion.",
            "html_url": "https://github.com/owner/repository/pull/42",
            "state": "open",
            "user": {"login": "octocat"},
            "base": {"ref": "main"},
            "head": {"ref": "feature/module-1"},
            "additions": 150,
            "deletions": 20,
            "changed_files": 2
        }

        # Mock GitHub Files Response
        mock_files_response = MagicMock()
        mock_files_response.status_code = 200
        mock_files_response.json.return_value = [
            {
                "filename": "backend/apps/verification/models.py",
                "status": "modified",
                "additions": 10,
                "deletions": 2,
                "changes": 12,
                "patch": "@@ -1,5 +1,10 @@\n+ingestion_data = models.JSONField()",
                "raw_url": "https://github.com/owner/repository/raw/file.py"
            },
            {
                "filename": "backend/apps/verification/views.py",
                "status": "added",
                "additions": 140,
                "deletions": 18,
                "changes": 158,
                "patch": "@@ -0,0 +1,140 @@\n+class SubmitVerificationView(APIView):",
                "raw_url": "https://github.com/owner/repository/raw/views.py"
            }
        ]

        # Return PR response on first call, files response on second call
        mock_get.side_effect = [mock_pr_response, mock_files_response]

        payload = {
            "repoUrl": "https://github.com/owner/repository",
            "prNumber": 42
        }

        response = self.client.post(self.submit_url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertIn("runId", response.data)
        self.assertEqual(response.data["status"], "INGESTED")

        # Verify Database Record
        run_id = response.data["runId"]
        run = VerificationRun.objects.get(id=run_id)
        self.assertEqual(run.status, VerificationRunStatus.INGESTED)
        self.assertEqual(run.repository_url, "https://github.com/owner/repository")
        self.assertEqual(run.pr_number, 42)
        
        # Verify normalized ingestion data payload in DB
        ingested = run.ingestion_data
        self.assertEqual(ingested["provider"], "github")
        self.assertEqual(ingested["pr"]["title"], "Add Module 1 Ingestion")
        self.assertEqual(ingested["pr"]["author"], "octocat")
        self.assertEqual(ingested["pr"]["additions"], 150)
        self.assertEqual(len(ingested["files"]), 2)
        self.assertEqual(ingested["files"][0]["filename"], "backend/apps/verification/models.py")

    @patch('requests.get')
    def test_submit_verification_github_404_fails(self, mock_get):
        """Test submitting non-existent PR sets status to FAILED and returns 400 Bad Request."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')

        mock_404_response = MagicMock()
        mock_404_response.status_code = 404
        mock_get.return_value = mock_404_response

        payload = {
            "repoUrl": "https://github.com/owner/repository",
            "prNumber": 99999
        }

        response = self.client.post(self.submit_url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("runId", response.data)
        self.assertEqual(response.data["status"], "FAILED")
        self.assertIn("not found", response.data["error"])

        # Verify DB status is FAILED
        run = VerificationRun.objects.get(id=response.data["runId"])
        self.assertEqual(run.status, VerificationRunStatus.FAILED)
        self.assertIn("not found", run.error_message)


class NegativeSpaceScannerTests(APITestCase):
    def setUp(self):
        self.username = 'scanner_user'
        self.password = 'ScannerPassword123!'
        self.user = User.objects.create_user(
            username=self.username,
            password=self.password
        )
        login_res = self.client.post(reverse('token_obtain_pair'), {
            'username': self.username,
            'password': self.password
        }, format='json')
        self.access_token = login_res.data['access']

        self.sample_ingestion_data = {
            "provider": "github",
            "pr": {
                "title": "Add Auth Endpoint",
                "body": "Implements initial auth view without rate limiting.",
                "author": "dev"
            },
            "files": [
                {
                    "filename": "views.py",
                    "status": "modified",
                    "patch": "@@ -1,3 +1,6 @@\n+def login_user(request):\n+    user = authenticate(request)\n+    return Response(user)"
                }
            ]
        }

        self.run = VerificationRun.objects.create(
            repository_url="https://github.com/owner/repo",
            provider="github",
            pr_number=10,
            status=VerificationRunStatus.INGESTED,
            ingestion_data=self.sample_ingestion_data
        )

    @patch.dict(os.environ, {"LLM_API_KEY": "mock_llm_key", "LLM_MODEL": "gpt-4o-mini"})
    @patch('requests.post')
    def test_scanner_service_success_mocked_llm(self, mock_post):
        """Test scanner service parses valid LLM response into structured findings."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": '[{"category": "RATE_LIMITING", "severity": "HIGH", "description": "Login endpoint lacks rate limiting.", "reason": "No throttling middleware applied in login_user view."}]'
                    }
                }
            ]
        }
        mock_post.return_value = mock_response

        findings = NegativeSpaceScannerService.scan(self.run)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["category"], "RATE_LIMITING")
        self.assertEqual(findings[0]["severity"], "HIGH")
        self.assertEqual(findings[0]["description"], "Login endpoint lacks rate limiting.")
        self.assertEqual(findings[0]["reason"], "No throttling middleware applied in login_user view.")

    @patch.dict(os.environ, {}, clear=True)
    def test_scanner_service_missing_api_key_raises_error(self):
        """Test scanner service raises NegativeSpaceScannerError when LLM_API_KEY is missing."""
        with self.assertRaises(NegativeSpaceScannerError) as ctx:
            NegativeSpaceScannerService.scan(self.run)
        self.assertIn("LLM_API_KEY", str(ctx.exception))

    @patch.dict(os.environ, {"LLM_API_KEY": "mock_llm_key"})
    @patch('requests.post')
    def test_scanner_service_llm_api_failure_raises_error(self, mock_post):
        """Test scanner service raises error when LLM API returns HTTP status 500."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_post.return_value = mock_response

        with self.assertRaises(NegativeSpaceScannerError) as ctx:
            NegativeSpaceScannerService.scan(self.run)
        self.assertIn("500", str(ctx.exception))

    @patch.dict(os.environ, {"LLM_API_KEY": "mock_llm_key"})
    @patch('requests.post')
    def test_scanner_service_invalid_json_raises_error(self, mock_post):
        """Test scanner service raises error when LLM output is invalid JSON."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "This is not JSON text."}}]
        }
        mock_post.return_value = mock_response

        with self.assertRaises(NegativeSpaceScannerError) as ctx:
            NegativeSpaceScannerService.scan(self.run)
        self.assertIn("invalid JSON", str(ctx.exception))

    def test_scan_endpoint_unauthenticated_fails(self):
        """Test POST /api/verify/<run_id>/scan without JWT returns HTTP 401."""
        url = reverse('verification_scan', kwargs={'run_id': self.run.id})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_scan_endpoint_not_found(self):
        """Test POST /api/verify/<non_existent_id>/scan returns HTTP 404."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')
        url = reverse('verification_scan', kwargs={'run_id': uuid.uuid4()})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @patch.dict(os.environ, {"LLM_API_KEY": "mock_llm_key", "LLM_MODEL": "gpt-4o-mini"})
    @patch('requests.post')
    def test_scan_endpoint_success(self, mock_post):
        """Test POST /api/verify/<run_id>/scan triggers scan and returns structured findings."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')
        url = reverse('verification_scan', kwargs={'run_id': self.run.id})

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": '[{"category": "INPUT_VALIDATION", "severity": "MEDIUM", "description": "Unvalidated parameters.", "reason": "Request query params used directly."}]'
                    }
                }
            ]
        }
        mock_post.return_value = mock_response

        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "SCANNED")
        self.assertEqual(response.data["findingsCount"], 1)
        self.assertEqual(len(response.data["findings"]), 1)

        # Check DB State
        self.run.refresh_from_db()
        self.assertEqual(self.run.status, VerificationRunStatus.SCANNED)
        self.assertEqual(len(self.run.findings), 1)
        self.assertEqual(self.run.findings[0]["category"], "INPUT_VALIDATION")

    @patch.dict(os.environ, {"LLM_API_KEY": "mock_llm_key"})
    @patch('requests.post')
    def test_scan_endpoint_failure_sets_scan_failed(self, mock_post):
        """Test POST /api/verify/<run_id>/scan handles LLM failure, updating status to SCAN_FAILED."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')
        url = reverse('verification_scan', kwargs={'run_id': self.run.id})

        mock_response = MagicMock()
        mock_response.status_code = 502
        mock_response.text = "Bad Gateway from LLM Provider"
        mock_post.return_value = mock_response

        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(response.data["status"], "SCAN_FAILED")
        self.assertIn("LLM API request failed", response.data["error"])

        # Check DB State
        self.run.refresh_from_db()
        self.assertEqual(self.run.status, VerificationRunStatus.SCAN_FAILED)
        self.assertIn("Bad Gateway", self.run.error_message)


class ArchitectureCheckerTests(APITestCase):
    def setUp(self):
        self.username = 'arch_user'
        self.password = 'ArchPassword123!'
        self.user = User.objects.create_user(
            username=self.username,
            password=self.password
        )
        login_res = self.client.post(reverse('token_obtain_pair'), {
            'username': self.username,
            'password': self.password
        }, format='json')
        self.access_token = login_res.data['access']

        self.sample_ingestion_data = {
            "provider": "github",
            "pr": {
                "title": "Refactor User Service",
                "body": "Reorganizes user endpoints.",
                "author": "dev"
            },
            "files": [
                {
                    "filename": "backend/apps/users/views.py",
                    "status": "modified",
                    "patch": "@@ -1,3 +1,6 @@\n+class UserHandler:\n+    def handle(self):\n+        pass"
                }
            ]
        }

        self.run = VerificationRun.objects.create(
            repository_url="https://github.com/owner/repo",
            provider="github",
            pr_number=20,
            status=VerificationRunStatus.INGESTED,
            ingestion_data=self.sample_ingestion_data
        )

    @patch.dict(os.environ, {"LLM_API_KEY": "mock_llm_key", "LLM_MODEL": "gpt-4o-mini"})
    @patch('requests.post')
    def test_architecture_checker_service_success_combined(self, mock_post):
        """Test static and LLM architecture fit analysis produces combined findings."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": '[{"category": "DESIGN_PATTERNS", "severity": "MEDIUM", "description": "Handler pattern used instead of View class pattern.", "evidence": "class UserHandler"}]'
                    }
                }
            ]
        }
        mock_post.return_value = mock_response

        findings = ArchitectureCheckerService.check(self.run)
        # Should contain static rule findings (naming convention + missing tests) and LLM finding
        categories = [f["category"] for f in findings]
        self.assertIn("NAMING_CONVENTIONS", categories)
        self.assertIn("TEST_CONVENTIONS", categories)
        self.assertIn("DESIGN_PATTERNS", categories)

    @patch.dict(os.environ, {"LLM_API_KEY": "mock_llm_key"})
    @patch('requests.post')
    def test_architecture_checker_service_llm_failure_raises_error(self, mock_post):
        """Test architecture service raises ArchitectureCheckerError on LLM API failure."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_post.return_value = mock_response

        with self.assertRaises(ArchitectureCheckerError) as ctx:
            ArchitectureCheckerService.check(self.run)
        self.assertIn("500", str(ctx.exception))

    def test_architecture_endpoint_unauthenticated_fails(self):
        """Test POST /api/verify/<run_id>/architecture without JWT returns HTTP 401."""
        url = reverse('verification_architecture', kwargs={'run_id': self.run.id})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_architecture_endpoint_not_found(self):
        """Test POST /api/verify/<non_existent_id>/architecture returns HTTP 404."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')
        url = reverse('verification_architecture', kwargs={'run_id': uuid.uuid4()})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @patch.dict(os.environ, {"LLM_API_KEY": "mock_llm_key", "LLM_MODEL": "gpt-4o-mini"})
    @patch('requests.post')
    def test_architecture_endpoint_success(self, mock_post):
        """Test POST /api/verify/<run_id>/architecture triggers check and returns findings."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')
        url = reverse('verification_architecture', kwargs={'run_id': self.run.id})

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": '[{"category": "API_STRUCTURE", "severity": "LOW", "description": "Non-standard endpoint pattern.", "evidence": "UserHandler.handle"}]'
                    }
                }
            ]
        }
        mock_post.return_value = mock_response

        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "ARCHITECTURE_CHECKED")
        self.assertGreaterEqual(response.data["findingsCount"], 1)

        # Check DB State
        self.run.refresh_from_db()
        self.assertEqual(self.run.status, VerificationRunStatus.ARCHITECTURE_CHECKED)
        self.assertGreaterEqual(len(self.run.architecture_findings), 1)

    @patch.dict(os.environ, {"LLM_API_KEY": "mock_llm_key"})
    @patch('requests.post')
    def test_architecture_endpoint_failure_sets_architecture_failed(self, mock_post):
        """Test POST /api/verify/<run_id>/architecture updates status to ARCHITECTURE_FAILED on error."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')
        url = reverse('verification_architecture', kwargs={'run_id': self.run.id})

        mock_response = MagicMock()
        mock_response.status_code = 504
        mock_response.text = "Gateway Timeout"
        mock_post.return_value = mock_response

        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(response.data["status"], "ARCHITECTURE_FAILED")
        self.assertIn("LLM API architecture check failed", response.data["error"])

        # Check DB State
        self.run.refresh_from_db()
        self.assertEqual(self.run.status, VerificationRunStatus.ARCHITECTURE_FAILED)
        self.assertIn("Gateway Timeout", self.run.error_message)


class ConfidenceScoringTests(APITestCase):
    def setUp(self):
        self.username = 'score_user'
        self.password = 'ScorePassword123!'
        self.user = User.objects.create_user(
            username=self.username,
            password=self.password
        )
        login_res = self.client.post(reverse('token_obtain_pair'), {
            'username': self.username,
            'password': self.password
        }, format='json')
        self.access_token = login_res.data['access']

        self.run = VerificationRun.objects.create(
            repository_url="https://github.com/owner/repo",
            provider="github",
            pr_number=30,
            status=VerificationRunStatus.ARCHITECTURE_CHECKED,
            ingestion_data={"provider": "github"}
        )

    def test_score_no_findings_returns_100(self):
        """Test score calculation with empty findings returns score of 100."""
        score, explanation, breakdown = ConfidenceScoringService.calculate_score(self.run)
        self.assertEqual(score, 100)
        self.assertIn("Base confidence score of 100/100", explanation)
        self.assertEqual(len(breakdown), 0)

    def test_score_each_severity_penalty(self):
        """Test exact penalty deductions for each severity level (CRITICAL=25, HIGH=15, MEDIUM=8, LOW=3, INFO=1)."""
        self.run.findings = [
            {"category": "AUTHENTICATION", "severity": "CRITICAL", "description": "Critical auth issue", "reason": "No auth check"},
            {"category": "RATE_LIMITING", "severity": "HIGH", "description": "High rate limit issue", "reason": "No throttling"},
            {"category": "INPUT_VALIDATION", "severity": "MEDIUM", "description": "Medium input issue", "reason": "Missing validation"},
            {"category": "LOGGING", "severity": "LOW", "description": "Low log issue", "reason": "Missing debug log"},
            {"category": "EDGE_CASES", "severity": "INFO", "description": "Info note", "reason": "Notice"}
        ]
        # Total deduction: 25 + 15 + 8 + 3 + 1 = 52. Expected score: 100 - 52 = 48.
        score, explanation, breakdown = ConfidenceScoringService.calculate_score(self.run)
        self.assertEqual(score, 48)
        self.assertEqual(len(breakdown), 5)
        self.assertIn("reduced by 52 penalty points", explanation)

    def test_score_combined_module3_and_module4(self):
        """Test scoring combining Module 3 (negative space) and Module 4 (architecture) findings."""
        self.run.findings = [
            {"category": "ERROR_HANDLING", "severity": "HIGH", "description": "Unhandled exception", "reason": "Missing try/except"}
        ]
        self.run.architecture_findings = [
            {"category": "NAMING_CONVENTIONS", "severity": "LOW", "description": "Non-standard class name", "evidence": "class UserHandler"}
        ]
        # Total deduction: 15 (HIGH) + 3 (LOW) = 18. Expected score: 100 - 18 = 82.
        score, explanation, breakdown = ConfidenceScoringService.calculate_score(self.run)
        self.assertEqual(score, 82)
        self.assertEqual(len(breakdown), 2)
        self.assertEqual(breakdown[0]["source"], "Module 3 (Negative-Space Scanner)")
        self.assertEqual(breakdown[1]["source"], "Module 4 (Architecture Fit Checker)")

    def test_score_clamping_at_zero(self):
        """Test score calculation clamping at 0 when penalties exceed 100."""
        self.run.findings = [
            {"category": "AUTHENTICATION", "severity": "CRITICAL", "description": "Issue 1", "reason": "r1"},
            {"category": "AUTHORIZATION", "severity": "CRITICAL", "description": "Issue 2", "reason": "r2"},
            {"category": "INPUT_VALIDATION", "severity": "CRITICAL", "description": "Issue 3", "reason": "r3"},
            {"category": "RATE_LIMITING", "severity": "CRITICAL", "description": "Issue 4", "reason": "r4"},
            {"category": "ERROR_HANDLING", "severity": "CRITICAL", "description": "Issue 5", "reason": "r5"}
        ]
        # Total deduction: 5 * 25 = 125. Expected score: 0 (clamped).
        score, explanation, breakdown = ConfidenceScoringService.calculate_score(self.run)
        self.assertEqual(score, 0)

    def test_score_endpoint_unauthenticated_fails(self):
        """Test POST /api/verify/<run_id>/score without JWT returns HTTP 401."""
        url = reverse('verification_score', kwargs={'run_id': self.run.id})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_score_endpoint_not_found(self):
        """Test POST /api/verify/<non_existent_id>/score returns HTTP 404."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')
        url = reverse('verification_score', kwargs={'run_id': uuid.uuid4()})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_score_endpoint_success(self):
        """Test POST /api/verify/<run_id>/score calculates score and saves results on VerificationRun."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')
        url = reverse('verification_score', kwargs={'run_id': self.run.id})

        self.run.findings = [
            {"category": "RATE_LIMITING", "severity": "HIGH", "description": "Missing rate limit", "reason": "No throttling"}
        ]
        self.run.architecture_findings = [
            {"category": "NAMING_CONVENTIONS", "severity": "LOW", "description": "Bad name", "evidence": "class Foo"}
        ]
        self.run.save()

        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "SCORED")
        self.assertEqual(response.data["score"], 82)
        self.assertIn("explanation", response.data)
        self.assertEqual(len(response.data["breakdown"]), 2)

        # Verify Database updates
        self.run.refresh_from_db()
        self.assertEqual(self.run.status, VerificationRunStatus.SCORED)
        self.assertEqual(self.run.confidence_score, 82)
        self.assertEqual(len(self.run.score_breakdown), 2)


class AuditTrailTests(APITestCase):
    def setUp(self):
        self.username = 'audit_user'
        self.password = 'AuditPassword123!'
        self.user = User.objects.create_user(
            username=self.username,
            password=self.password
        )
        login_res = self.client.post(reverse('token_obtain_pair'), {
            'username': self.username,
            'password': self.password
        }, format='json')
        self.access_token = login_res.data['access']

        self.run = VerificationRun.objects.create(
            repository_url="https://github.com/owner/repo",
            provider="github",
            pr_number=50,
            status=VerificationRunStatus.QUEUED
        )

    def test_audit_entry_creation_and_sanitization(self):
        """Test AuditLogService creates audit entry and sanitizes sensitive credentials/keys."""
        log_entry = AuditLogService.log_event(
            verification_run=self.run,
            event='TEST_EVENT',
            status='SUCCESS',
            details={
                'user': 'dev',
                'api_key': 'secret-12345',
                'authorization': 'Bearer token-abc',
                'safe_param': 42,
                'nested': {
                    'secret_token': 'hidden_val'
                }
            }
        )
        self.assertEqual(log_entry.event, 'TEST_EVENT')
        self.assertEqual(log_entry.status, 'SUCCESS')
        self.assertEqual(log_entry.details['user'], 'dev')
        self.assertEqual(log_entry.details['api_key'], '[REDACTED]')
        self.assertEqual(log_entry.details['authorization'], '[REDACTED]')
        self.assertEqual(log_entry.details['safe_param'], 42)
        self.assertEqual(log_entry.details['nested']['secret_token'], '[REDACTED]')

    @patch('requests.get')
    @patch.dict(os.environ, {"LLM_API_KEY": "mock_llm_key", "LLM_MODEL": "gpt-4o-mini"})
    @patch('requests.post')
    def test_successful_verification_flow_audit_trail(self, mock_post, mock_get):
        """Test complete successful verification flow records audit entries in chronological order."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')

        # 1. Submit PR (Ingestion)
        mock_pr_response = MagicMock()
        mock_pr_response.status_code = 200
        mock_pr_response.json.return_value = {
            "title": "Audit PR", "body": "Testing audit", "html_url": "url",
            "state": "open", "user": {"login": "dev"}, "base": {"ref": "main"},
            "head": {"ref": "feature"}, "additions": 10, "deletions": 5, "changed_files": 1
        }
        mock_files_response = MagicMock()
        mock_files_response.status_code = 200
        mock_files_response.json.return_value = [{
            "filename": "app.py", "status": "modified", "additions": 10,
            "deletions": 5, "changes": 15, "patch": "+def foo(): pass", "raw_url": "raw"
        }]
        mock_get.side_effect = [mock_pr_response, mock_files_response]

        submit_res = self.client.post(reverse('verification_submit'), {
            "repoUrl": "https://github.com/owner/repo",
            "prNumber": 50
        }, format='json')
        self.assertEqual(submit_res.status_code, status.HTTP_202_ACCEPTED)
        run_id = submit_res.data['runId']

        # 2. Trigger Scan
        mock_scan_res = MagicMock()
        mock_scan_res.status_code = 200
        mock_scan_res.json.return_value = {
            "choices": [{"message": {"content": '[{"category": "LOGGING", "severity": "LOW", "description": "Log issue", "reason": "No debug log"}]'}}]
        }
        mock_post.return_value = mock_scan_res

        scan_url = reverse('verification_scan', kwargs={'run_id': run_id})
        scan_res = self.client.post(scan_url)
        self.assertEqual(scan_res.status_code, status.HTTP_200_OK)

        # 3. Trigger Architecture Check
        mock_arch_res = MagicMock()
        mock_arch_res.status_code = 200
        mock_arch_res.json.return_value = {
            "choices": [{"message": {"content": '[]'}}]
        }
        mock_post.return_value = mock_arch_res

        arch_url = reverse('verification_architecture', kwargs={'run_id': run_id})
        arch_res = self.client.post(arch_url)
        self.assertEqual(arch_res.status_code, status.HTTP_200_OK)

        # 4. Trigger Score
        score_url = reverse('verification_score', kwargs={'run_id': run_id})
        score_res = self.client.post(score_url)
        self.assertEqual(score_res.status_code, status.HTTP_200_OK)

        # 5. Fetch Audit Trail Endpoint
        audit_url = reverse('verification_audit', kwargs={'run_id': run_id})
        audit_res = self.client.get(audit_url)
        self.assertEqual(audit_res.status_code, status.HTTP_200_OK)
        self.assertEqual(audit_res.data['runId'], run_id)
        
        trail = audit_res.data['auditTrail']
        self.assertEqual(len(trail), 4)
        self.assertEqual(trail[0]['event'], 'PR_INGESTION')
        self.assertEqual(trail[0]['status'], 'SUCCESS')
        self.assertEqual(trail[1]['event'], 'NEGATIVE_SPACE_SCAN')
        self.assertEqual(trail[1]['status'], 'SUCCESS')
        self.assertEqual(trail[2]['event'], 'ARCHITECTURE_CHECK')
        self.assertEqual(trail[2]['status'], 'SUCCESS')
        self.assertEqual(trail[3]['event'], 'CONFIDENCE_SCORING')
        self.assertEqual(trail[3]['status'], 'SUCCESS')

    @patch('requests.get')
    def test_failed_verification_event_audit_entry(self, mock_get):
        """Test failed verification attempt records FAILED status in audit log."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')

        mock_404_res = MagicMock()
        mock_404_res.status_code = 404
        mock_get.return_value = mock_404_res

        submit_res = self.client.post(reverse('verification_submit'), {
            "repoUrl": "https://github.com/owner/repo",
            "prNumber": 999
        }, format='json')
        self.assertEqual(submit_res.status_code, status.HTTP_400_BAD_REQUEST)
        run_id = submit_res.data['runId']

        audit_url = reverse('verification_audit', kwargs={'run_id': run_id})
        audit_res = self.client.get(audit_url)
        self.assertEqual(audit_res.status_code, status.HTTP_200_OK)
        trail = audit_res.data['auditTrail']
        self.assertEqual(len(trail), 1)
        self.assertEqual(trail[0]['event'], 'PR_INGESTION')
        self.assertEqual(trail[0]['status'], 'FAILED')

    def test_audit_endpoint_unauthenticated_fails(self):
        """Test GET /api/verify/<run_id>/audit without JWT token returns HTTP 401."""
        url = reverse('verification_audit', kwargs={'run_id': self.run.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_audit_endpoint_invalid_run_id_returns_404(self):
        """Test GET /api/verify/<invalid_run_id>/audit returns HTTP 404."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')
        url = reverse('verification_audit', kwargs={'run_id': uuid.uuid4()})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data['error'], "Verification run not found.")


class CITriggerTests(APITestCase):
    def setUp(self):
        self.username = 'ci_user'
        self.password = 'CIPassword123!'
        self.user = User.objects.create_user(
            username=self.username,
            password=self.password
        )
        login_res = self.client.post(reverse('token_obtain_pair'), {
            'username': self.username,
            'password': self.password
        }, format='json')
        self.access_token = login_res.data['access']
        self.ci_url = reverse('verification_ci_trigger')

    def test_ci_trigger_unauthenticated_fails(self):
        """Test POST /api/verify/ci-trigger without JWT token returns HTTP 401."""
        response = self.client.post(self.ci_url, {
            "repoUrl": "https://github.com/owner/repo",
            "prNumber": 100
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_ci_trigger_invalid_url_fails(self):
        """Test POST /api/verify/ci-trigger with invalid repo URL returns HTTP 400."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')
        response = self.client.post(self.ci_url, {
            "repoUrl": "https://gitlab.com/owner/repo",
            "prNumber": 100
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('repoUrl', response.data)

    @patch('requests.get')
    @patch.dict(os.environ, {"LLM_API_KEY": "mock_llm_key", "LLM_MODEL": "gpt-4o-mini"})
    @patch('requests.post')
    def test_ci_trigger_success_full_verification(self, mock_post, mock_get):
        """Test POST /api/verify/ci-trigger executes full pipeline synchronously."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')

        mock_pr = MagicMock()
        mock_pr.status_code = 200
        mock_pr.json.return_value = {
            "title": "CI PR", "body": "Testing CI", "html_url": "url",
            "state": "open", "user": {"login": "dev"}, "base": {"ref": "main"},
            "head": {"ref": "feature"}, "additions": 5, "deletions": 2, "changed_files": 1
        }
        mock_files = MagicMock()
        mock_files.status_code = 200
        mock_files.json.return_value = [{
            "filename": "views.py", "status": "modified", "additions": 5,
            "deletions": 2, "changes": 7, "patch": "+def view(): pass", "raw_url": "raw"
        }, {
            "filename": "test_views.py", "status": "added", "additions": 1,
            "deletions": 0, "changes": 1, "patch": "+pass", "raw_url": "raw"
        }]
        mock_get.side_effect = [mock_pr, mock_files]

        mock_llm = MagicMock()
        mock_llm.status_code = 200
        mock_llm.json.return_value = {
            "choices": [{"message": {"content": '[]'}}]
        }
        mock_post.return_value = mock_llm

        response = self.client.post(self.ci_url, {
            "repoUrl": "https://github.com/owner/repo",
            "prNumber": 100
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'SCORED')
        self.assertEqual(response.data['confidenceScore'], 100)
        self.assertIn('runId', response.data)


class MCPInterfaceTests(APITestCase):
    def setUp(self):
        from .mcp import ASEAMCPInterface
        self.mcp = ASEAMCPInterface

    @patch('requests.get')
    @patch.dict(os.environ, {"LLM_API_KEY": "mock_llm_key", "LLM_MODEL": "gpt-4o-mini"})
    @patch('requests.post')
    def test_mcp_submit_verification_request(self, mock_post, mock_get):
        """Test MCP submit_verification executes verification and returns score."""
        mock_pr = MagicMock()
        mock_pr.status_code = 200
        mock_pr.json.return_value = {
            "title": "MCP PR", "body": "Testing MCP", "html_url": "url",
            "state": "open", "user": {"login": "mcp_dev"}, "base": {"ref": "main"},
            "head": {"ref": "feature"}, "additions": 5, "deletions": 2, "changed_files": 1
        }
        mock_files = MagicMock()
        mock_files.status_code = 200
        mock_files.json.return_value = [{
            "filename": "mcp_test.py", "status": "modified", "additions": 5,
            "deletions": 2, "changes": 7, "patch": "+# mcp test", "raw_url": "raw"
        }]
        mock_get.side_effect = [mock_pr, mock_files]

        mock_llm = MagicMock()
        mock_llm.status_code = 200
        mock_llm.json.return_value = {
            "choices": [{"message": {"content": '[]'}}]
        }
        mock_post.return_value = mock_llm

        res = self.mcp.submit_verification("https://github.com/owner/repo", 200)

        self.assertEqual(res['status'], 'SCORED')
        self.assertEqual(res['confidenceScore'], 100)
        self.assertIn('runId', res)

    def test_mcp_get_verification_result(self):
        """Test MCP get_verification_result returns run details, score, and audit logs."""
        run = VerificationRun.objects.create(
            repository_url="https://github.com/owner/repo",
            provider="github",
            pr_number=200,
            status=VerificationRunStatus.SCORED,
            confidence_score=95,
            score_explanation="Base 100 - 5"
        )
        AuditLogService.log_event(run, 'TEST_EVENT', 'SUCCESS', {'info': 'ok'})

        res = self.mcp.get_verification_result(str(run.id))

        self.assertEqual(res['runId'], str(run.id))
        self.assertEqual(res['status'], 'SCORED')
        self.assertEqual(res['confidenceScore'], 95)
        self.assertEqual(len(res['auditTrail']), 1)

    def test_mcp_get_verification_result_invalid_id_returns_error(self):
        """Test MCP get_verification_result with invalid run_id returns error."""
        res = self.mcp.get_verification_result("invalid-uuid-str")
        self.assertIn('error', res)

    @patch('requests.get')
    @patch.dict(os.environ, {"LLM_API_KEY": "mock_llm_key", "LLM_MODEL": "gpt-4o-mini"})
    @patch('requests.post')
    def test_mcp_jsonrpc_tools_list_and_call(self, mock_post, mock_get):
        """Test MCP JSON-RPC 2.0 tools/list and tools/call requests."""
        # 1. tools/list
        list_req = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list"
        }
        list_res = self.mcp.process_jsonrpc(list_req)
        self.assertEqual(list_res["id"], 1)
        tool_names = [t["name"] for t in list_res["result"]["tools"]]
        self.assertIn("asea_submit_verification", tool_names)
        self.assertIn("asea_get_verification_result", tool_names)

        # 2. tools/call - asea_submit_verification
        mock_pr = MagicMock()
        mock_pr.status_code = 200
        mock_pr.json.return_value = {
            "title": "JSONRPC PR", "body": "body", "html_url": "url",
            "state": "open", "user": {"login": "dev"}, "base": {"ref": "main"},
            "head": {"ref": "feat"}, "additions": 1, "deletions": 1, "changed_files": 1
        }
        mock_files = MagicMock()
        mock_files.status_code = 200
        mock_files.json.return_value = [{
            "filename": "f.py", "status": "modified", "additions": 1,
            "deletions": 1, "changes": 2, "patch": "+pass", "raw_url": "raw"
        }, {
            "filename": "test_f.py", "status": "added", "additions": 1,
            "deletions": 0, "changes": 1, "patch": "+pass", "raw_url": "raw"
        }]
        mock_get.side_effect = [mock_pr, mock_files]

        mock_llm = MagicMock()
        mock_llm.status_code = 200
        mock_llm.json.return_value = {"choices": [{"message": {"content": '[]'}}]}
        mock_post.return_value = mock_llm

        call_req = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "asea_submit_verification",
                "arguments": {
                    "repo_url": "https://github.com/owner/repo",
                    "pr_number": 300
                }
            }
        }
        call_res = self.mcp.process_jsonrpc(call_req)
        self.assertEqual(call_res["id"], 2)
        content_text = call_res["result"]["content"][0]["text"]
        result_json = json.loads(content_text)
        self.assertEqual(result_json["status"], "SCORED")





