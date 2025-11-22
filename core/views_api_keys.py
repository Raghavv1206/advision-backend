# backend/core/views_api_keys.py - COMPLETE
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from .models import UserAPIKey
from .serializers import UserAPIKeySerializer

class UserAPIKeyListView(APIView):
    """List all API keys for current user"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        api_keys = UserAPIKey.objects.filter(user=request.user)
        
        # Return safe data (no decrypted keys)
        data = []
        for key in api_keys:
            data.append({
                'id': str(key.id),
                'api_type': key.api_type,
                'api_name': key.api_name,
                'account_id': key.account_id,
                'is_active': key.is_active,
                'verification_status': key.verification_status,
                'last_verified': key.last_verified,
                'error_message': key.error_message,
                'created_at': key.created_at,
            })
        
        return Response({
            'api_keys': data,
            'total': len(data)
        })

class UserAPIKeyCreateView(APIView):
    """Add new API key"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        api_type = request.data.get('api_type')
        api_name = request.data.get('api_name')
        api_key = request.data.get('api_key')
        api_secret = request.data.get('api_secret', '')
        account_id = request.data.get('account_id', '')
        developer_token = request.data.get('developer_token', '')
        
        if not all([api_type, api_name, api_key]):
            return Response(
                {'error': 'api_type, api_name, and api_key are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check for duplicates
        if UserAPIKey.objects.filter(
            user=request.user,
            api_type=api_type,
            api_name=api_name
        ).exists():
            return Response(
                {'error': f'API key with name "{api_name}" already exists for {api_type}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Create and encrypt
            user_api_key = UserAPIKey(
                user=request.user,
                api_type=api_type,
                api_name=api_name,
                account_id=account_id,
                developer_token=developer_token,
            )
            
            # Encrypt sensitive data
            user_api_key.encrypt_key(api_key)
            if api_secret:
                user_api_key.encrypt_secret(api_secret)
            
            user_api_key.save()
            
            return Response({
                'success': True,
                'message': 'API key added successfully',
                'api_key_id': str(user_api_key.id),
                'verification_status': user_api_key.verification_status,
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response(
                {'error': f'Failed to save API key: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class UserAPIKeyDeleteView(APIView):
    """Delete API key"""
    permission_classes = [permissions.IsAuthenticated]
    
    def delete(self, request, key_id):
        try:
            api_key = UserAPIKey.objects.get(
                id=key_id,
                user=request.user
            )
            api_key.delete()
            
            return Response({
                'success': True,
                'message': 'API key deleted successfully'
            })
            
        except UserAPIKey.DoesNotExist:
            return Response(
                {'error': 'API key not found'},
                status=status.HTTP_404_NOT_FOUND
            )

class UserAPIKeyVerifyView(APIView):
    """Re-verify API key"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, key_id):
        try:
            api_key = UserAPIKey.objects.get(
                id=key_id,
                user=request.user
            )
            
            # Re-verify credentials
            api_key.verify_credentials()
            api_key.save()
            
            return Response({
                'success': True,
                'verification_status': api_key.verification_status,
                'error_message': api_key.error_message,
                'last_verified': api_key.last_verified,
            })
            
        except UserAPIKey.DoesNotExist:
            return Response(
                {'error': 'API key not found'},
                status=status.HTTP_404_NOT_FOUND
            )

class UserAPIKeyToggleView(APIView):
    """Enable/disable API key"""
    permission_classes = [permissions.IsAuthenticated]
    
    def patch(self, request, key_id):
        try:
            api_key = UserAPIKey.objects.get(
                id=key_id,
                user=request.user
            )
            
            api_key.is_active = not api_key.is_active
            api_key.save()
            
            return Response({
                'success': True,
                'is_active': api_key.is_active,
                'message': f'API key {"enabled" if api_key.is_active else "disabled"}'
            })
            
        except UserAPIKey.DoesNotExist:
            return Response(
                {'error': 'API key not found'},
                status=status.HTTP_404_NOT_FOUND
            )