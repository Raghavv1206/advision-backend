# backend/core/views_oauth.py - GOOGLE ONLY (Production Ready)
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
from django.conf import settings
from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount, SocialApp
import requests
import os

User = get_user_model()


def get_redirect_uri(request=None):
    """
    Get the appropriate redirect URI based on environment.
    In production, uses FRONTEND_URL environment variable.
    In development, uses localhost.
    """
    # Check for production environment
    django_settings = os.getenv('DJANGO_SETTINGS_MODULE', '')
    
    if 'production' in django_settings:
        # Production: Use environment variable
        frontend_url = os.getenv('FRONTEND_URL', 'https://advision-frontend.vercel.app')
        return frontend_url
    
    # Development: Use localhost
    return 'http://localhost:5173'


class GoogleOAuthView(APIView):
    """
    Custom Google OAuth handler that works for both development and production.
    
    Flow:
    1. Frontend sends authorization code from Google
    2. Backend exchanges code for access token
    3. Backend fetches user info from Google
    4. Backend creates/updates user and returns JWT tokens
    """
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        code = request.data.get('code')
        
        if not code:
            return Response(
                {'error': 'Authorization code is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Get redirect URI based on environment
            redirect_uri = get_redirect_uri(request)
            
            # Log for debugging (remove in production if needed)
            print(f"[GoogleOAuth] Using redirect_uri: {redirect_uri}")
            
            # Step 1: Exchange code for access token
            token_url = 'https://oauth2.googleapis.com/token'
            token_data = {
                'code': code,
                'client_id': getattr(settings, 'GOOGLE_OAUTH_CLIENT_ID', os.getenv('GOOGLE_CLIENT_ID', '')),
                'client_secret': getattr(settings, 'GOOGLE_OAUTH_CLIENT_SECRET', os.getenv('GOOGLE_CLIENT_SECRET', '')),
                'redirect_uri': redirect_uri,
                'grant_type': 'authorization_code'
            }
            
            token_response = requests.post(token_url, data=token_data, timeout=15)
            
            if token_response.status_code != 200:
                error_detail = token_response.json() if token_response.text else token_response.text
                print(f"[GoogleOAuth] Token exchange failed: {error_detail}")
                return Response(
                    {
                        'error': 'Failed to exchange code for token',
                        'details': str(error_detail)
                    }, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            token_json = token_response.json()
            access_token = token_json.get('access_token')
            
            if not access_token:
                return Response(
                    {'error': 'No access token received from Google'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Step 2: Get user info from Google
            user_info_url = 'https://www.googleapis.com/oauth2/v2/userinfo'
            headers = {'Authorization': f'Bearer {access_token}'}
            user_info_response = requests.get(user_info_url, headers=headers, timeout=10)
            
            if user_info_response.status_code != 200:
                return Response(
                    {'error': 'Failed to get user info from Google'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            user_info = user_info_response.json()
            email = user_info.get('email')
            google_id = user_info.get('id')
            
            if not email:
                return Response(
                    {'error': 'Email not provided by Google'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            print(f"[GoogleOAuth] Authenticating user: {email}")
            
            # Step 3: Get or create user
            user, user_created = User.objects.get_or_create(
                email=email,
                defaults={'role': 'viewer'}
            )
            
            if user_created:
                print(f"[GoogleOAuth] Created new user: {email}")
            
            # Step 4: Create or update EmailAddress (for django-allauth)
            email_obj, email_created = EmailAddress.objects.get_or_create(
                user=user,
                email=email,
                defaults={
                    'verified': True,
                    'primary': True
                }
            )
            
            # Ensure it's verified and primary
            if not email_obj.verified or not email_obj.primary:
                email_obj.verified = True
                email_obj.primary = True
                email_obj.save()
            
            # Step 5: Create or update SocialApp and SocialAccount
            try:
                social_app = SocialApp.objects.get(provider='google')
            except SocialApp.DoesNotExist:
                # Create the social app if it doesn't exist
                social_app = SocialApp.objects.create(
                    provider='google',
                    name='Google',
                    client_id=getattr(settings, 'GOOGLE_OAUTH_CLIENT_ID', os.getenv('GOOGLE_CLIENT_ID', '')),
                    secret=getattr(settings, 'GOOGLE_OAUTH_CLIENT_SECRET', os.getenv('GOOGLE_CLIENT_SECRET', ''))
                )
                # Add to default site
                try:
                    from django.contrib.sites.models import Site
                    default_site = Site.objects.get(id=1)
                    social_app.sites.add(default_site)
                except Exception as e:
                    print(f"[GoogleOAuth] Could not add site to social app: {e}")
            
            # Create or update social account
            social_account, sa_created = SocialAccount.objects.get_or_create(
                user=user,
                provider='google',
                defaults={
                    'uid': google_id,
                    'extra_data': user_info
                }
            )
            
            if not sa_created:
                # Update extra_data if account already exists
                social_account.extra_data = user_info
                social_account.save()
            
            # Step 6: Generate JWT tokens
            refresh = RefreshToken.for_user(user)
            
            print(f"[GoogleOAuth] Login successful for: {email}")
            
            return Response({
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'user': {
                    'id': str(user.id),
                    'email': user.email,
                    'role': user.role
                }
            }, status=status.HTTP_200_OK)
            
        except requests.Timeout:
            return Response(
                {'error': 'Request to Google timed out. Please try again.'}, 
                status=status.HTTP_504_GATEWAY_TIMEOUT
            )
        except requests.RequestException as e:
            print(f"[GoogleOAuth] Network error: {e}")
            return Response(
                {'error': f'Network error: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            print(f"[GoogleOAuth] Unexpected error: {e}")
            import traceback
            traceback.print_exc()
            return Response(
                {'error': f'Authentication failed: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )