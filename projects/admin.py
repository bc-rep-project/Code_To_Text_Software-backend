from django.contrib import admin
from django.utils.html import format_html
from .models import (
    Project, ScanData, GitHubInfo, GitHubIssue, 
    GitHubCommit, ConversionResult, ProjectMonitoring
)

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('project_name', 'user', 'source_type', 'status', 'created_at', 'updated_at')
    list_filter = ('source_type', 'status', 'created_at')
    search_fields = ('project_name', 'user__username', 'user__email', 'github_repo_url')
    ordering = ('-created_at',)
    
    fieldsets = (
        ('Basic Info', {
            'fields': ('user', 'project_name'),
        }),
        ('Source', {
            'fields': ('source_type', 'github_repo_url', 'uploaded_file_key', 'original_file_name'),
        }),
        ('Status', {
            'fields': ('status',),
        }),
        ('GitHub Tracking', {
            'fields': ('last_github_commit_hash', 'last_scan_at', 'last_conversion_at'),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
        }),
    )
    
    readonly_fields = ('created_at', 'updated_at')

@admin.register(ScanData)
class ScanDataAdmin(admin.ModelAdmin):
    list_display = ('project', 'total_files', 'total_size_mb', 'created_at')
    list_filter = ('created_at', 'languages_used')
    search_fields = ('project__project_name', 'project__user__username')
    ordering = ('-created_at',)
    
    fieldsets = (
        ('Project Info', {
            'fields': ('project',),
        }),
        ('Scan Results', {
            'fields': ('languages_used', 'total_files', 'total_size_bytes'),
        }),
        ('Errors', {
            'fields': ('error_message',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
        }),
    )
    
    readonly_fields = ('created_at', 'updated_at')
    
    def total_size_mb(self, obj):
        if obj.total_size_bytes:
            return f"{obj.total_size_bytes / (1024 * 1024):.2f} MB"
        return "N/A"
    total_size_mb.short_description = 'Total Size'

@admin.register(GitHubInfo)
class GitHubInfoAdmin(admin.ModelAdmin):
    list_display = ('scan_data', 'repo_name', 'owner', 'stars', 'forks', 'updated_at')
    list_filter = ('repo_created_at', 'repo_updated_at', 'updated_at')
    search_fields = ('scan_data__project__project_name', 'repo_name', 'owner')
    ordering = ('-updated_at',)
    
    fieldsets = (
        ('Repository Info', {
            'fields': ('scan_data', 'repo_name', 'owner', 'description'),
        }),
        ('Repository Stats', {
            'fields': ('stars', 'forks', 'open_issues_count'),
        }),
        ('Settings', {
            'fields': ('default_branch',),
        }),
        ('Timestamps', {
            'fields': ('repo_created_at', 'repo_updated_at', 'created_at', 'updated_at'),
        }),
    )
    
    readonly_fields = ('created_at', 'updated_at')

@admin.register(GitHubIssue)
class GitHubIssueAdmin(admin.ModelAdmin):
    list_display = ('github_info', 'title', 'state', 'author', 'issue_created_at')
    list_filter = ('state', 'issue_created_at')
    search_fields = ('github_info__scan_data__project__project_name', 'title', 'author')
    ordering = ('-issue_created_at',)

@admin.register(GitHubCommit)
class GitHubCommitAdmin(admin.ModelAdmin):
    list_display = ('github_info', 'short_sha', 'author_name', 'message_preview', 'commit_date')
    list_filter = ('commit_date',)
    search_fields = ('github_info__scan_data__project__project_name', 'sha', 'author_name', 'author_email', 'message')
    ordering = ('-commit_date',)
    
    def short_sha(self, obj):
        return obj.sha[:8] if obj.sha else ''
    short_sha.short_description = 'SHA'
    
    def message_preview(self, obj):
        return obj.message[:50] + '...' if len(obj.message) > 50 else obj.message
    message_preview.short_description = 'Message'

@admin.register(ConversionResult)
class ConversionResultAdmin(admin.ModelAdmin):
    list_display = ('project', 'file_size_mb', 'total_files_converted', 'download_count', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('project__project_name', 'project__user__username')
    ordering = ('-created_at',)
    
    fieldsets = (
        ('Conversion Info', {
            'fields': ('project',),
        }),
        ('Files', {
            'fields': ('converted_artifact_path', 'google_drive_folder_id', 'google_drive_folder_link'),
        }),
        ('Statistics', {
            'fields': ('total_files_converted', 'conversion_size_bytes', 'conversion_duration_seconds'),
        }),
        ('Downloads', {
            'fields': ('download_count', 'last_downloaded_at'),
        }),
        ('Errors', {
            'fields': ('error_message',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
        }),
    )
    
    readonly_fields = ('created_at', 'updated_at')
    
    def file_size_mb(self, obj):
        if obj.conversion_size_bytes:
            return f"{obj.conversion_size_bytes / (1024 * 1024):.2f} MB"
        return "N/A"
    file_size_mb.short_description = 'File Size'

@admin.register(ProjectMonitoring)
class ProjectMonitoringAdmin(admin.ModelAdmin):
    list_display = ('project', 'is_active', 'total_updates_detected', 'last_checked_at')
    list_filter = ('is_active', 'auto_convert_on_update', 'notify_on_update')
    search_fields = ('project__project_name', 'project__user__username')
    ordering = ('-last_checked_at',)
    
    fieldsets = (
        ('Monitoring Settings', {
            'fields': ('project', 'is_active', 'check_frequency_hours'),
        }),
        ('Automation', {
            'fields': ('auto_convert_on_update', 'notify_on_update'),
        }),
        ('Status', {
            'fields': ('last_checked_at', 'last_known_commit_hash'),
        }),
        ('Statistics', {
            'fields': ('total_updates_detected', 'last_update_detected_at'),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
        }),
    )
    
    readonly_fields = ('total_updates_detected', 'last_checked_at', 'last_update_detected_at', 'created_at', 'updated_at')
