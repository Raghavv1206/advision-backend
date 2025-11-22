# backend/core/adapters.py
from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model

User = get_user_model()

class CustomAccountAdapter(DefaultAccountAdapter):
    """
    Custom adapter to handle account operations.
    """
    def save_user(self, request, user, form, commit=True):
        """
        Saves a new user instance using information provided in the signup form.
        """
        user = super().save_user(request, user, form, commit=False)
        if commit:
            user.save()
            # Create or get email address record (avoid duplicates)
            EmailAddress.objects.get_or_create(
                user=user,
                email=user.email,
                defaults={'primary': True, 'verified': True}
            )
        return user

class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Custom adapter for social account operations.
    """
    def pre_social_login(self, request, sociallogin):
        """
        Connect social account to existing user if email matches.
        """
        # If the social account already exists, skip
        if sociallogin.is_existing:
            return
        
        # Try to get email from social account data
        email = None
        if sociallogin.account.extra_data:
            email = sociallogin.account.extra_data.get('email')
        
        if not email:
            # Some providers might have email in a different field
            email = sociallogin.email_addresses[0].email if sociallogin.email_addresses else None
        
        if email:
            try:
                # Check if user with this email exists
                existing_user = User.objects.get(email=email)
                
                # Connect this social account to the existing user
                sociallogin.connect(request, existing_user)
                
            except User.DoesNotExist:
                # No existing user, will create a new one
                pass
            except User.MultipleObjectsReturned:
                # If there are duplicates, use the first one
                existing_user = User.objects.filter(email=email).first()
                sociallogin.connect(request, existing_user)
    
    def populate_user(self, request, sociallogin, data):
        """
        Populate user instance with data from social provider.
        """
        user = super().populate_user(request, sociallogin, data)
        
        # Ensure email is set
        if not user.email and data.get('email'):
            user.email = data['email']
        
        return user
    
    def save_user(self, request, sociallogin, form=None):
        """
        Save the user and create EmailAddress record.
        """
        user = super().save_user(request, sociallogin, form)
        
        # Ensure EmailAddress record exists (avoid duplicates)
        if user.email:
            email_address, created = EmailAddress.objects.get_or_create(
                user=user,
                email__iexact=user.email,  # Case-insensitive lookup
                defaults={
                    'email': user.email,
                    'primary': True,
                    'verified': True
                }
            )
            
            # If it already existed, make sure it's primary and verified
            if not created:
                if not email_address.primary or not email_address.verified:
                    email_address.primary = True
                    email_address.verified = True
                    email_address.save()
        
        return user