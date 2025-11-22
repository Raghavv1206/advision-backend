# backend/core/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import (
    User, Campaign, AdContent, ImageAsset, Comment,
    DailyAnalytics, CampaignAnalyticsSummary, GeneratedReport, AdPlatformConnection, SyncedCampaign, ABTest, ABTestVariation,
    PredictiveModel, Prediction, ReportSchedule
)


@admin.register(User)
class CustomUserAdmin(BaseUserAdmin):
    list_display = ('email', 'role', 'is_staff', 'is_active', 'date_joined')
    list_filter = ('role', 'is_staff', 'is_active')
    search_fields = ('email',)
    ordering = ('-date_joined',)
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('bio', 'role')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'role', 'is_staff', 'is_active')}
        ),
    )

@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'platform', 'start_date', 'end_date', 'budget', 'is_active', 'created_at')
    list_filter = ('platform', 'is_active', 'created_at')
    search_fields = ('title', 'description', 'user__email')
    date_hierarchy = 'created_at'
    readonly_fields = ('id', 'created_at')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'user', 'title', 'description')
        }),
        ('Campaign Details', {
            'fields': ('platform', 'start_date', 'end_date', 'budget', 'is_active')
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

@admin.register(AdContent)
class AdContentAdmin(admin.ModelAdmin):
    list_display = ('campaign', 'platform', 'tone', 'views', 'clicks', 'conversions', 'ctr', 'created_at')
    list_filter = ('platform', 'tone', 'created_at')
    search_fields = ('text', 'campaign__title')
    date_hierarchy = 'created_at'
    readonly_fields = ('id', 'created_at', 'ctr', 'conversion_rate')
    
    fieldsets = (
        ('Content', {
            'fields': ('campaign', 'text', 'platform', 'tone')
        }),
        ('Performance Metrics', {
            'fields': ('views', 'clicks', 'conversions', 'ctr', 'conversion_rate')
        }),
        ('Metadata', {
            'fields': ('id', 'created_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(ImageAsset)
class ImageAssetAdmin(admin.ModelAdmin):
    list_display = ('campaign', 'prompt_preview', 'impressions', 'clicks', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('prompt', 'campaign__title')
    date_hierarchy = 'created_at'
    readonly_fields = ('id', 'created_at')
    
    def prompt_preview(self, obj):
        return obj.prompt[:50] + '...' if len(obj.prompt) > 50 else obj.prompt
    prompt_preview.short_description = 'Prompt'

@admin.register(DailyAnalytics)
class DailyAnalyticsAdmin(admin.ModelAdmin):
    list_display = ('campaign', 'date', 'impressions', 'clicks', 'conversions', 'spend', 'ctr', 'cpc')
    list_filter = ('date', 'campaign__platform')
    search_fields = ('campaign__title',)
    date_hierarchy = 'date'
    readonly_fields = ('id', 'ctr', 'cpc', 'cpa', 'created_at', 'updated_at')
    
    fieldsets = (
        ('Campaign & Date', {
            'fields': ('campaign', 'date')
        }),
        ('Core Metrics', {
            'fields': ('impressions', 'clicks', 'conversions', 'spend')
        }),
        ('Calculated Metrics', {
            'fields': ('ctr', 'cpc', 'cpa'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['recalculate_metrics']
    
    def recalculate_metrics(self, request, queryset):
        for obj in queryset:
            obj.save()  # This triggers the auto-calculation
        self.message_user(request, f'Recalculated metrics for {queryset.count()} records')
    recalculate_metrics.short_description = 'Recalculate metrics'

@admin.register(CampaignAnalyticsSummary)
class CampaignAnalyticsSummaryAdmin(admin.ModelAdmin):
    list_display = ('campaign', 'total_impressions', 'total_clicks', 'total_conversions', 
                   'avg_ctr', 'performance_score', 'last_updated')
    list_filter = ('performance_score', 'last_updated')
    search_fields = ('campaign__title',)
    readonly_fields = ('id', 'total_impressions', 'total_clicks', 'total_conversions',
                      'total_spend', 'avg_ctr', 'avg_cpc', 'avg_conversion_rate',
                      'roas', 'performance_score', 'last_updated')
    
    fieldsets = (
        ('Campaign', {
            'fields': ('campaign',)
        }),
        ('Lifetime Metrics', {
            'fields': ('total_impressions', 'total_clicks', 'total_conversions', 'total_spend')
        }),
        ('Averages', {
            'fields': ('avg_ctr', 'avg_cpc', 'avg_conversion_rate', 'roas')
        }),
        ('Performance', {
            'fields': ('performance_score', 'last_updated')
        }),
    )
    
    actions = ['update_all_metrics']
    
    def update_all_metrics(self, request, queryset):
        for summary in queryset:
            summary.update_metrics()
        self.message_user(request, f'Updated metrics for {queryset.count()} campaigns')
    update_all_metrics.short_description = 'Update metrics from daily analytics'

@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ('campaign', 'user', 'message_preview', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('message', 'campaign__title', 'user__email')
    date_hierarchy = 'created_at'
    readonly_fields = ('id', 'created_at')
    
    def message_preview(self, obj):
        return obj.message[:50] + '...' if len(obj.message) > 50 else obj.message
    message_preview.short_description = 'Message'

@admin.register(AdPlatformConnection)
class AdPlatformConnectionAdmin(admin.ModelAdmin):
    list_display = ('user', 'platform', 'account_name', 'status', 'last_sync')
    list_filter = ('platform', 'status')
    search_fields = ('user__email', 'account_name', 'account_id')

@admin.register(SyncedCampaign)
class SyncedCampaignAdmin(admin.ModelAdmin):
    list_display = ('external_name', 'connection', 'external_status', 'impressions', 'clicks', 'last_synced')
    list_filter = ('connection__platform', 'external_status')
    search_fields = ('external_name', 'external_id')

@admin.register(ABTest)
class ABTestAdmin(admin.ModelAdmin):
    list_display = ('name', 'campaign', 'status', 'winner', 'is_significant', 'created_at')
    list_filter = ('status', 'is_significant')
    search_fields = ('name', 'campaign__title')

@admin.register(ABTestVariation)
class ABTestVariationAdmin(admin.ModelAdmin):
    list_display = ('name', 'ab_test', 'impressions', 'clicks', 'conversions', 'ctr')
    search_fields = ('name', 'ab_test__name')

@admin.register(ReportSchedule)
class ReportScheduleAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'frequency', 'format', 'is_active', 'next_run')
    list_filter = ('frequency', 'format', 'is_active')
    search_fields = ('name', 'user__email')