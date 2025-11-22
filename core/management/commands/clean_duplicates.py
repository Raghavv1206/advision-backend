# backend/core/management/commands/clean_duplicates.py
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount
from django.db.models import Count

User = get_user_model()

class Command(BaseCommand):
    help = 'Clean duplicate EmailAddress and SocialAccount records'

    def handle(self, *args, **options):
        self.stdout.write('Starting cleanup...')
        
        # Find and fix duplicate EmailAddress records
        duplicate_emails = (
            EmailAddress.objects.values('email')
            .annotate(count=Count('id'))
            .filter(count__gt=1)
        )
        
        for item in duplicate_emails:
            email = item['email']
            self.stdout.write(f'Found {item["count"]} duplicates for email: {email}')
            
            # Get all duplicates
            email_addresses = EmailAddress.objects.filter(email=email).order_by('-verified', '-primary', 'id')
            
            # Keep the first one (most verified/primary)
            keep = email_addresses.first()
            
            # Delete the rest
            deleted_count = email_addresses.exclude(id=keep.id).delete()[0]
            self.stdout.write(self.style.SUCCESS(f'  Kept EmailAddress ID {keep.id}, deleted {deleted_count} duplicates'))
        
        # Find and fix duplicate users with same email
        duplicate_users = (
            User.objects.values('email')
            .annotate(count=Count('id'))
            .filter(count__gt=1)
        )
        
        for item in duplicate_users:
            email = item['email']
            if not email:
                continue
                
            self.stdout.write(f'Found {item["count"]} users with email: {email}')
            
            # Get all duplicates
            users = User.objects.filter(email=email).order_by('-is_staff', '-date_joined')
            
            # Keep the first one (staff or oldest)
            keep = users.first()
            
            # Move social accounts to the user we're keeping
            for user in users.exclude(id=keep.id):
                SocialAccount.objects.filter(user=user).update(user=keep)
                EmailAddress.objects.filter(user=user).update(user=keep)
                
                self.stdout.write(f'  Moved accounts from user {user.id} to {keep.id}')
                user.delete()
                self.stdout.write(self.style.SUCCESS(f'  Deleted duplicate user {user.id}'))
        
        self.stdout.write(self.style.SUCCESS('Cleanup complete!'))