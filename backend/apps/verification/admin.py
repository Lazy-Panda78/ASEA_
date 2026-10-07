from django.contrib import admin
from .models import VerificationRun, AuditLog

@admin.register(VerificationRun)
class VerificationRunAdmin(admin.ModelAdmin):
    list_display = ('id', 'provider', 'pr_number', 'status', 'repository_url', 'created_at')
    list_filter = ('provider', 'status', 'created_at')
    search_fields = ('id', 'repository_url', 'pr_number')
    readonly_fields = ('id', 'created_at', 'updated_at')


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'verification_run', 'event', 'status', 'timestamp')
    list_filter = ('event', 'status', 'timestamp')
    search_fields = ('verification_run__id', 'event', 'status')
    readonly_fields = ('id', 'verification_run', 'event', 'status', 'details', 'timestamp')

