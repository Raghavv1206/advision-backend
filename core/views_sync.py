# backend/core/views_sync.py - CREATE THIS NEW FILE
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from .services.ad_platforms import AdPlatformSyncService
import traceback

class SyncUserCampaignsView(APIView):
    """Sync campaigns using user's API keys"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        try:
            results = AdPlatformSyncService.sync_user_campaigns(request.user)
            
            successful = sum(1 for r in results if r.get('success'))
            failed = len(results) - successful
            
            return Response({
                'success': True,
                'results': results,
                'summary': {
                    'total_platforms': len(results),
                    'successful': successful,
                    'failed': failed
                }
            })
            
        except Exception as e:
            traceback.print_exc()
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class GetSyncStatusView(APIView):
    """Get sync status for all user's API keys"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        from .models import UserAPIKey
        
        api_keys = UserAPIKey.objects.filter(user=request.user)
        
        status_list = []
        for api_key in api_keys:
            status_list.append({
                'id': str(api_key.id),
                'api_name': api_key.api_name,
                'platform': api_key.get_api_type_display(),
                'is_active': api_key.is_active,
                'verification_status': api_key.verification_status,
                'last_verified': api_key.last_verified,
                'can_sync': api_key.is_active and api_key.verification_status == 'verified'
            })
        
        return Response({
            'api_keys': status_list,
            'total': len(status_list),
            'verified_count': sum(1 for k in status_list if k['can_sync'])
        })