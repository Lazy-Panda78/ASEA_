from django.urls import path
from .views import (
    HealthCheckView,
    ProtectedTestView,
    SubmitVerificationView,
    ScanVerificationView,
    ArchitectureCheckView,
    ScoreVerificationView,
    AuditLogView,
    CITriggerVerificationView,
)

urlpatterns = [
    path('health/', HealthCheckView.as_view(), name='health_check'),
    path('protected-test/', ProtectedTestView.as_view(), name='protected_test'),
    path('verify/submit', SubmitVerificationView.as_view(), name='verification_submit'),
    path('verify/ci-trigger', CITriggerVerificationView.as_view(), name='verification_ci_trigger'),
    path('verify/<uuid:run_id>/scan', ScanVerificationView.as_view(), name='verification_scan'),
    path('verify/<uuid:run_id>/architecture', ArchitectureCheckView.as_view(), name='verification_architecture'),
    path('verify/<uuid:run_id>/score', ScoreVerificationView.as_view(), name='verification_score'),
    path('verify/<uuid:run_id>/audit', AuditLogView.as_view(), name='verification_audit'),
]


