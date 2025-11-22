# backend/core/urls.py - WITHOUT GITHUB
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from . import views_advanced
from . import views_predictive
from . import views_api_keys
from . import views_sync  
from . import views_oauth 

router = DefaultRouter()
router.register(r'campaigns', views.CampaignViewSet, basename='campaign')
router.register(r'adcontent', views.AdContentViewSet, basename='adcontent')
router.register(r'images', views.ImageAssetViewSet, basename='imageasset')
router.register(r'comments', views.CommentViewSet, basename='comment')

urlpatterns = [
    path('', include(router.urls)),
    
    # AI Generation
    path('generate/text/', views.AdContentGeneratorView.as_view(), name='generate-text'),
    path('generate/image/', views.ImageGeneratorView.as_view(), name='generate-image'),
    path('generate/image/save/', views.SaveChosenImageView.as_view(), name='save-chosen-image'),
    
    # Social Auth (GOOGLE ONLY)
    path('auth/google/', views_oauth.GoogleOAuthView.as_view(), name='google_login'),
    
    # Dashboard & Analytics
    path('dashboard/stats/', views.DashboardStatsView.as_view(), name='dashboard-stats'),
    path('analytics/summary/', views.AnalyticsSummaryView.as_view(), name='analytics-summary'),
    path('analytics/comparison/', views.CampaignComparisonView.as_view(), name='campaign-comparison'),
    
    # Advanced Features
    path('audience/insights/', views.AudienceInsightsView.as_view(), name='audience-insights'),
    path('reports/weekly/', views.WeeklyReportView.as_view(), name='weekly-report'),
    path('preview/ad/', views.AdPreviewView.as_view(), name='ad-preview'),
    
    # User Profile
    path('profile/', views.UserProfileView.as_view(), name='user-profile'),

    # Ad Platform Connections
    path('platforms/connect/google/', views_advanced.ConnectGoogleAdsView.as_view(), name='connect-google-ads'),
    path('platforms/connect/facebook/', views_advanced.ConnectFacebookAdsView.as_view(), name='connect-facebook-ads'),
    path('platforms/sync/', views_advanced.SyncAdPlatformView.as_view(), name='sync-platforms'),
    path('platforms/synced-campaigns/', views_advanced.SyncedCampaignsView.as_view(), name='synced-campaigns'),
    
    # A/B Testing
    path('ab-tests/', views_advanced.ABTestListView.as_view(), name='ab-test-list'),
    path('ab-tests/create/', views_advanced.CreateABTestView.as_view(), name='ab-test-create'),
    path('ab-tests/<uuid:test_id>/start/', views_advanced.StartABTestView.as_view(), name='ab-test-start'),
    path('ab-tests/<uuid:test_id>/analyze/', views_advanced.AnalyzeABTestView.as_view(), name='ab-test-analyze'),
    
    # Predictive Analytics
    path('predictive/train/', views_predictive.TrainPredictiveModelView.as_view(), name='train-model'),
    path('predictive/predict/', views_predictive.PredictNextWeekView.as_view(), name='predict-next-week'),
    path('predictive/budget/', views_predictive.BudgetRecommendationsView.as_view(), name='budget-recommendations'),
    
    # User API Keys
    path('api-keys/', views_api_keys.UserAPIKeyListView.as_view(), name='user-api-keys'),
    path('api-keys/create/', views_api_keys.UserAPIKeyCreateView.as_view(), name='create-api-key'),
    path('api-keys/<uuid:key_id>/delete/', views_api_keys.UserAPIKeyDeleteView.as_view(), name='delete-api-key'),
    path('api-keys/<uuid:key_id>/verify/', views_api_keys.UserAPIKeyVerifyView.as_view(), name='verify-api-key'),
    path('api-keys/<uuid:key_id>/toggle/', views_api_keys.UserAPIKeyToggleView.as_view(), name='toggle-api-key'),

    # Sync Campaigns
    path('sync/campaigns/', views_sync.SyncUserCampaignsView.as_view(), name='sync-user-campaigns'),
    path('sync/status/', views_sync.GetSyncStatusView.as_view(), name='sync-status'),

     # Report generation
    path('reports/generate/', views.GenerateCampaignReportView.as_view(), name='generate-report'),
    
   # Image CRUD
    path('images/<uuid:image_id>/delete/', views.DeleteImageView.as_view(), name='delete-image'),
    path('images/<uuid:image_id>/update/', views.UpdateImageView.as_view(), name='update-image'),
]