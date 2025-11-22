# backend/core/views_advanced.py - NEW COMPLETE FILE
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from .models import (
    AdPlatformConnection, SyncedCampaign, ABTest, ABTestVariation, Campaign
)
from .serializers import (
    AdPlatformConnectionSerializer, SyncedCampaignSerializer,
    ABTestSerializer
)
from .services.ad_platforms import AdPlatformSyncService, GoogleAdsService, FacebookAdsService
from .services.ab_testing import ABTestingService
from datetime import datetime

# ============================================================================
# AD PLATFORM CONNECTIONS
# ============================================================================
class ConnectGoogleAdsView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        """Connect Google Ads account"""
        refresh_token = request.data.get('refresh_token')
        account_id = request.data.get('account_id')
        
        if not refresh_token or not account_id:
            return Response(
                {'error': 'refresh_token and account_id are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        connection, created = AdPlatformConnection.objects.update_or_create(
            user=request.user,
            platform='google_ads',
            defaults={
                'refresh_token': refresh_token,
                'account_id': account_id,
                'status': 'pending'
            }
        )
        
        try:
            service = GoogleAdsService(connection)
            campaigns = service.get_campaigns()
            
            connection.status = 'connected'
            connection.account_name = f"Google Ads Account {account_id}"
            connection.last_sync = datetime.now()
            connection.save()
            
            return Response({
                'success': True,
                'message': f'Successfully connected Google Ads account with {len(campaigns)} campaigns',
                'connection_id': str(connection.id)
            })
        except Exception as e:
            connection.status = 'error'
            connection.error_message = str(e)
            connection.save()
            
            return Response(
                {'error': f'Failed to connect: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )

class ConnectFacebookAdsView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        """Connect Facebook Ads account"""
        access_token = request.data.get('access_token')
        account_id = request.data.get('account_id')
        
        if not access_token or not account_id:
            return Response(
                {'error': 'access_token and account_id are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        connection, created = AdPlatformConnection.objects.update_or_create(
            user=request.user,
            platform='facebook_ads',
            defaults={
                'access_token': access_token,
                'account_id': account_id,
                'status': 'pending'
            }
        )
        
        try:
            service = FacebookAdsService(connection)
            campaigns = service.get_campaigns()
            
            connection.status = 'connected'
            connection.account_name = f"Facebook Ad Account {account_id}"
            connection.last_sync = datetime.now()
            connection.save()
            
            return Response({
                'success': True,
                'message': f'Successfully connected Facebook Ads account with {len(campaigns)} campaigns',
                'connection_id': str(connection.id)
            })
        except Exception as e:
            connection.status = 'error'
            connection.error_message = str(e)
            connection.save()
            
            return Response(
                {'error': f'Failed to connect: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )

class SyncAdPlatformView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        """Manually trigger sync for a platform connection"""
        connection_id = request.data.get('connection_id')
        
        if not connection_id:
            results = AdPlatformSyncService.sync_all_connections(request.user)
            return Response({'results': results})
        
        try:
            connection = AdPlatformConnection.objects.get(
                id=connection_id,
                user=request.user
            )
            
            result = AdPlatformSyncService.sync_connection(connection)
            return Response(result)
            
        except AdPlatformConnection.DoesNotExist:
            return Response(
                {'error': 'Connection not found'},
                status=status.HTTP_404_NOT_FOUND
            )

class SyncedCampaignsView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        """Get all synced campaigns"""
        connections = AdPlatformConnection.objects.filter(user=request.user)
        synced_campaigns = SyncedCampaign.objects.filter(
            connection__in=connections
        ).select_related('connection', 'local_campaign')
        
        serializer = SyncedCampaignSerializer(synced_campaigns, many=True)
        return Response(serializer.data)

# ============================================================================
# A/B TESTING
# ============================================================================
class ABTestListView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        """List all A/B tests"""
        ab_tests = ABTest.objects.filter(
            campaign__user=request.user
        ).prefetch_related('variations')
        
        serializer = ABTestSerializer(ab_tests, many=True)
        return Response(serializer.data)

class CreateABTestView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        """Create a new A/B test"""
        campaign_id = request.data.get('campaign_id')
        name = request.data.get('name')
        variations_data = request.data.get('variations', [])
        
        try:
            campaign = Campaign.objects.get(id=campaign_id, user=request.user)
            
            ab_test = ABTest.objects.create(
                campaign=campaign,
                name=name,
                description=request.data.get('description', ''),
                success_metric=request.data.get('success_metric', 'ctr'),
                traffic_split=request.data.get('traffic_split', {'A': 50, 'B': 50}),
                min_sample_size=request.data.get('min_sample_size', 1000),
                status='draft'
            )
            
            for var_data in variations_data:
                ABTestVariation.objects.create(
                    ab_test=ab_test,
                    name=var_data['name'],
                    ad_content_id=var_data.get('ad_content_id'),
                    image_asset_id=var_data.get('image_asset_id')
                )
            
            return Response({
                'success': True,
                'ab_test_id': str(ab_test.id),
                'message': 'A/B test created successfully'
            })
            
        except Campaign.DoesNotExist:
            return Response(
                {'error': 'Campaign not found'},
                status=status.HTTP_404_NOT_FOUND
            )

class StartABTestView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, test_id):
        """Start an A/B test"""
        try:
            ab_test = ABTest.objects.get(
                id=test_id,
                campaign__user=request.user
            )
            
            if ab_test.variations.count() < 2:
                return Response(
                    {'error': 'Need at least 2 variations to start test'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            ab_test.status = 'running'
            ab_test.start_date = datetime.now()
            ab_test.save()
            
            return Response({
                'success': True,
                'message': 'A/B test started'
            })
            
        except ABTest.DoesNotExist:
            return Response(
                {'error': 'A/B test not found'},
                status=status.HTTP_404_NOT_FOUND
            )

class AnalyzeABTestView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, test_id):
        """Analyze A/B test results"""
        try:
            ab_test = ABTest.objects.get(
                id=test_id,
                campaign__user=request.user
            )
            
            analysis = ABTestingService.analyze_test(ab_test)
            recommendations = ABTestingService.get_recommendation(ab_test)
            
            variations = []
            for var in ab_test.variations.all():
                variations.append({
                    'name': var.name,
                    'impressions': var.impressions,
                    'clicks': var.clicks,
                    'conversions': var.conversions,
                    'ctr': var.ctr,
                    'conversion_rate': var.conversion_rate,
                    'spend': float(var.spend)
                })
            
            return Response({
                'ab_test': {
                    'id': str(ab_test.id),
                    'name': ab_test.name,
                    'status': ab_test.status,
                    'success_metric': ab_test.success_metric
                },
                'variations': variations,
                'analysis': analysis,
                'recommendations': recommendations
            })
            
        except ABTest.DoesNotExist:
            return Response(
                {'error': 'A/B test not found'},
                status=status.HTTP_404_NOT_FOUND
            )