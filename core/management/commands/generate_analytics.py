# backend/core/management/commands/generate_analytics.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta, date
import random
from core.models import Campaign, DailyAnalytics, CampaignAnalyticsSummary

class Command(BaseCommand):
    help = 'Generate realistic analytics data for existing campaigns'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Number of days of data to generate (default: 30)'
        )

    def handle(self, *args, **options):
        days = options['days']
        campaigns = Campaign.objects.all()
        
        if not campaigns.exists():
            self.stdout.write(self.style.ERROR('No campaigns found. Create campaigns first.'))
            return
        
        self.stdout.write(f'Generating {days} days of analytics data for {campaigns.count()} campaigns...')
        
        for campaign in campaigns:
            self.stdout.write(f'\nProcessing: {campaign.title}')
            
            # Get campaign age in days
            campaign_age = (timezone.now().date() - campaign.start_date).days
            days_to_generate = min(days, campaign_age + 1)
            
            # Base metrics based on platform and budget
            base_impressions = self._get_base_impressions(campaign)
            daily_budget = float(campaign.budget or 100) / max(days_to_generate, 1)
            
            # Generate daily data
            for day_offset in range(days_to_generate):
                analytics_date = timezone.now().date() - timedelta(days=days_to_generate - day_offset - 1)
                
                # Skip if in the future or before campaign start
                if analytics_date > timezone.now().date() or analytics_date < campaign.start_date:
                    continue
                
                # Create or update daily analytics
                daily_analytics, created = DailyAnalytics.objects.get_or_create(
                    campaign=campaign,
                    date=analytics_date,
                    defaults=self._generate_daily_metrics(
                        base_impressions, 
                        daily_budget, 
                        day_offset,
                        days_to_generate
                    )
                )
                
                if not created:
                    # Update existing record
                    metrics = self._generate_daily_metrics(
                        base_impressions, 
                        daily_budget, 
                        day_offset,
                        days_to_generate
                    )
                    for key, value in metrics.items():
                        setattr(daily_analytics, key, value)
                    daily_analytics.save()
            
            # Create or update campaign summary
            summary, created = CampaignAnalyticsSummary.objects.get_or_create(
                campaign=campaign
            )
            summary.update_metrics()
            
            self.stdout.write(self.style.SUCCESS(f'  ✓ Generated {days_to_generate} days of data'))
            self.stdout.write(f'  Total impressions: {summary.total_impressions:,}')
            self.stdout.write(f'  Total clicks: {summary.total_clicks:,}')
            self.stdout.write(f'  Performance score: {summary.performance_score}/100')
        
        self.stdout.write(self.style.SUCCESS('\n✓ Analytics generation complete!'))
    
    def _get_base_impressions(self, campaign):
        """Calculate base impressions based on platform and content"""
        platform_multipliers = {
            'instagram': 500,
            'facebook': 600,
            'youtube': 800,
            'linkedin': 300,
            'tiktok': 1000,
        }
        
        base = platform_multipliers.get(campaign.platform, 500)
        
        # Multiply by number of ads and images
        content_count = campaign.ad_content.count() + campaign.images.count()
        return base * max(content_count, 1)
    
    def _generate_daily_metrics(self, base_impressions, daily_budget, day_offset, total_days):
        """Generate realistic daily metrics with growth pattern"""
        # Growth factor increases over time
        growth_factor = 1 + (day_offset / total_days) * 0.5
        
        # Add some randomness
        randomness = random.uniform(0.85, 1.15)
        
        # Calculate impressions
        impressions = int(base_impressions * growth_factor * randomness)
        
        # Calculate clicks (CTR between 2-5%)
        ctr_rate = random.uniform(0.02, 0.05)
        clicks = int(impressions * ctr_rate)
        
        # Calculate conversions (conversion rate between 5-15%)
        conversion_rate = random.uniform(0.05, 0.15)
        conversions = int(clicks * conversion_rate)
        
        # Calculate spend with some variance
        spend = round(daily_budget * random.uniform(0.85, 1.15), 2)
        
        return {
            'impressions': impressions,
            'clicks': clicks,
            'conversions': conversions,
            'spend': spend,
        }