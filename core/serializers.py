# backend/core/serializers.py - COMPLETE CLEAN VERSION
from rest_framework import serializers
from .models import (
    User, Campaign, AdContent, ImageAsset, Comment,
    DailyAnalytics, CampaignAnalyticsSummary,
    AdPlatformConnection, SyncedCampaign,
    ABTest, ABTestVariation,
    PredictiveModel, Prediction,
    ReportSchedule, GeneratedReport,
    UserAPIKey
)
from dj_rest_auth.registration.serializers import RegisterSerializer

# ============================================================================
# USER & AUTH
# ============================================================================
class UserSerializer(serializers.ModelSerializer):
    """Serializer for basic user info."""
    class Meta:
        model = User
        fields = ['id', 'email', 'role', 'bio']

class CustomRegisterSerializer(RegisterSerializer):
    """Custom registration serializer that doesn't use username."""
    username = None
    
    def get_cleaned_data(self):
        return {
            'email': self.validated_data.get('email', ''),
            'password1': self.validated_data.get('password1', ''),
        }

    def save(self, request):
        from allauth.account.models import EmailAddress
        from django.contrib.auth import get_user_model
        
        User = get_user_model()
        email = self.validated_data.get('email')
        password = self.validated_data.get('password1')
        
        user = User.objects.create_user(
            email=email,
            password=password
        )
        
        EmailAddress.objects.create(
            user=user,
            email=email,
            primary=True,
            verified=True
        )
        
        return user

# ============================================================================
# COMMENTS
# ============================================================================
class CommentSerializer(serializers.ModelSerializer):
    """Serializer for comments."""
    user = UserSerializer(read_only=True)

    class Meta:
        model = Comment
        fields = ['id', 'campaign', 'user', 'message', 'created_at']
        read_only_fields = ['user']

# ============================================================================
# AD CONTENT
# ============================================================================
class AdContentSerializer(serializers.ModelSerializer):
    """Serializer for text-based ad content."""
    ctr = serializers.ReadOnlyField()
    conversion_rate = serializers.ReadOnlyField()
    
    class Meta:
        model = AdContent
        fields = ['id', 'campaign', 'text', 'tone', 'platform', 'created_at', 
                 'views', 'clicks', 'conversions', 'ctr', 'conversion_rate']
        read_only_fields = ['ctr', 'conversion_rate']

# ============================================================================
# IMAGE ASSETS
# ============================================================================
class ImageAssetSerializer(serializers.ModelSerializer):
    """Serializer for image assets."""
    image_url = serializers.CharField(source='image', read_only=True)

    class Meta:
        model = ImageAsset
        fields = ['id', 'campaign', 'prompt', 'created_at', 'image_url', 
                 'cloudinary_public_id', 'impressions', 'clicks']
        read_only_fields = ['id', 'created_at', 'cloudinary_public_id']
    
    def get_image_url(self, obj):
        request = self.context.get('request')
        if obj.image and hasattr(obj.image, 'url'):
            if request:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        return None

# ============================================================================
# ANALYTICS
# ============================================================================
class DailyAnalyticsSerializer(serializers.ModelSerializer):
    """Serializer for daily analytics data"""
    class Meta:
        model = DailyAnalytics
        fields = [
            'id', 'date', 'impressions', 'clicks', 'conversions', 
            'spend', 'ctr', 'cpc', 'cpa'
        ]
        read_only_fields = ['id', 'ctr', 'cpc', 'cpa']

class CampaignAnalyticsSummarySerializer(serializers.ModelSerializer):
    """Serializer for campaign analytics summary"""
    class Meta:
        model = CampaignAnalyticsSummary
        fields = [
            'total_impressions', 'total_clicks', 'total_conversions',
            'total_spend', 'avg_ctr', 'avg_cpc', 'avg_conversion_rate',
            'roas', 'performance_score', 'last_updated'
        ]
        read_only_fields = fields

# ============================================================================
# CAMPAIGNS
# ============================================================================
class CampaignSerializer(serializers.ModelSerializer):
    """Main serializer for a Campaign with analytics."""
    user = UserSerializer(read_only=True)
    ad_content = AdContentSerializer(many=True, read_only=True)
    images = ImageAssetSerializer(many=True, read_only=True)
    comments = CommentSerializer(many=True, read_only=True)
    analytics_summary = CampaignAnalyticsSummarySerializer(read_only=True)

    class Meta:
        model = Campaign
        fields = [
            'id', 'user', 'title', 'description', 'start_date', 'end_date',
            'budget', 'platform', 'is_active', 'created_at', 
            'ad_content', 'images', 'comments', 'analytics_summary'
        ]

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        campaign = super().create(validated_data)
        
        return campaign

# ============================================================================
# AD PLATFORM CONNECTIONS
# ============================================================================
class AdPlatformConnectionSerializer(serializers.ModelSerializer):
    """Serializer for ad platform connections"""
    class Meta:
        model = AdPlatformConnection
        fields = [
            'id', 'platform', 'account_id', 'account_name', 'status',
            'last_sync', 'error_message', 'auto_sync', 'sync_frequency',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'status', 'last_sync', 'error_message', 'created_at', 'updated_at']

class SyncedCampaignSerializer(serializers.ModelSerializer):
    """Serializer for synced campaigns"""
    connection_platform = serializers.CharField(source='connection.get_platform_display', read_only=True)
    local_campaign_title = serializers.CharField(source='local_campaign.title', read_only=True, allow_null=True)
    
    class Meta:
        model = SyncedCampaign
        fields = [
            'id', 'connection', 'connection_platform', 'local_campaign', 
            'local_campaign_title', 'external_id', 'external_name', 
            'external_status', 'spend', 'impressions', 'clicks', 
            'conversions', 'last_synced', 'sync_enabled'
        ]
        read_only_fields = ['id', 'last_synced']

# ============================================================================
# A/B TESTING
# ============================================================================
class ABTestVariationSerializer(serializers.ModelSerializer):
    """Serializer for A/B test variations"""
    ctr = serializers.ReadOnlyField()
    conversion_rate = serializers.ReadOnlyField()
    
    class Meta:
        model = ABTestVariation
        fields = [
            'id', 'name', 'ad_content', 'image_asset', 'impressions',
            'clicks', 'conversions', 'spend', 'ctr', 'conversion_rate'
        ]
        read_only_fields = ['id', 'ctr', 'conversion_rate']

class ABTestSerializer(serializers.ModelSerializer):
    """Serializer for A/B tests"""
    variations = ABTestVariationSerializer(many=True, read_only=True)
    campaign_title = serializers.CharField(source='campaign.title', read_only=True)
    
    class Meta:
        model = ABTest
        fields = [
            'id', 'campaign', 'campaign_title', 'name', 'description', 
            'status', 'start_date', 'end_date', 'traffic_split', 
            'success_metric', 'confidence_level', 'min_sample_size',
            'winner', 'is_significant', 'p_value', 'variations',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'winner', 'is_significant', 'p_value', 'created_at', 'updated_at']

# ============================================================================
# PREDICTIVE ANALYTICS
# ============================================================================
class PredictiveModelSerializer(serializers.ModelSerializer):
    """Serializer for predictive models"""
    class Meta:
        model = PredictiveModel
        fields = [
            'id', 'model_type', 'accuracy', 'last_trained', 
            'training_samples', 'is_active', 'created_at'
        ]
        read_only_fields = ['id', 'accuracy', 'last_trained', 'training_samples', 'created_at']

class PredictionSerializer(serializers.ModelSerializer):
    """Serializer for predictions"""
    campaign_title = serializers.CharField(source='campaign.title', read_only=True)
    model_type = serializers.CharField(source='model.get_model_type_display', read_only=True)
    
    class Meta:
        model = Prediction
        fields = [
            'id', 'model', 'model_type', 'campaign', 'campaign_title',
            'prediction_date', 'predicted_value', 'actual_value',
            'confidence', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']

# ============================================================================
# AUTOMATED REPORTS
# ============================================================================
class ReportScheduleSerializer(serializers.ModelSerializer):
    """Serializer for report schedules"""
    class Meta:
        model = ReportSchedule
        fields = [
            'id', 'name', 'frequency', 'format', 'email_recipients',
            'slack_webhook', 'discord_webhook', 'include_campaigns',
            'include_metrics', 'is_active', 'next_run', 'last_run',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'last_run', 'created_at', 'updated_at']

class GeneratedReportSerializer(serializers.ModelSerializer):
    """Serializer for generated reports"""
    schedule_name = serializers.CharField(source='schedule.name', read_only=True)
    
    class Meta:
        model = GeneratedReport
        fields = [
            'id', 'schedule', 'schedule_name', 'report_data',
            'file_path', 'sent_successfully', 'delivery_errors',
            'created_at'
        ]
        read_only_fields = ['id', 'created_at']

# ============================================================================
# USER API KEYS SERIALIZER
# ============================================================================
class UserAPIKeySerializer(serializers.ModelSerializer):
    """Serializer for UserAPIKey - NEVER exposes actual keys"""
    api_type_display = serializers.CharField(source='get_api_type_display', read_only=True)
    
    class Meta:
        model = UserAPIKey
        fields = [
            'id', 'api_type', 'api_type_display', 'api_name', 'account_id',
            'is_active', 'verification_status', 'last_verified', 
            'error_message', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'verification_status', 'last_verified', 
            'error_message', 'created_at', 'updated_at'
        ]   