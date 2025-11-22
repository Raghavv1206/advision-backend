# demo_setup.py - Run this to setup complete demo data
# Usage: Get-Content create_demo_data.py | python manage.py shell

# backend/create_demo_data.py - UPDATED WITH COMPREHENSIVE DATA

import os
import django
from datetime import datetime, timedelta
from decimal import Decimal
import random

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.contrib.auth import get_user_model
from core.models import (
    Campaign, AdContent, ImageAsset, Comment,
    DailyAnalytics, CampaignAnalyticsSummary,
    UserAPIKey, ABTest, ABTestVariation
)

User = get_user_model()

print("🎬 Setting up AdVision Demo Environment with REAL DATA...")
print("=" * 70)

# ============================================================================
# 1. CREATE DEMO USERS
# ============================================================================
print("\n👤 Creating demo users...")

demo_users = [
    {'email': 'demo@advision.com', 'password': 'demo123', 'role': 'admin'},
    {'email': 'admin@advision.com', 'password': 'admin123', 'role': 'admin'},
    {'email': 'test@advision.com', 'password': 'test123', 'role': 'editor'},
]

for user_data in demo_users:
    user, created = User.objects.get_or_create(
        email=user_data['email'],
        defaults={'role': user_data['role']}
    )
    if created:
        user.set_password(user_data['password'])
        user.save()
        print(f"✅ Created user: {user_data['email']} / {user_data['password']}")
    else:
        print(f"ℹ️  User exists: {user_data['email']}")

demo_user = User.objects.get(email='demo@advision.com')

# ============================================================================
# 2. CREATE MOCK API KEYS
# ============================================================================
print("\n🔑 Creating verified mock API keys...")

api_keys_data = [
    {
        'api_type': 'google_ads',
        'api_name': 'My Google Ads Account',
        'account_id': 'demo-google-ads-123',
        'developer_token': 'demo-dev-token-xxx'
    },
    {
        'api_type': 'facebook_ads',
        'api_name': 'Main Facebook Business',
        'account_id': 'act_demo_456'
    },
    {
        'api_type': 'instagram_ads',
        'api_name': 'Instagram Business Account',
        'account_id': 'ig_demo_789'
    }
]

for key_data in api_keys_data:
    api_key, created = UserAPIKey.objects.get_or_create(
        user=demo_user,
        api_type=key_data['api_type'],
        api_name=key_data['api_name'],
        defaults={
            'account_id': key_data['account_id'],
            'developer_token': key_data.get('developer_token', ''),
            'verification_status': 'verified',
            'is_active': True,
            'last_verified': datetime.now()
        }
    )
    
    if created:
        api_key.encrypt_key(f'demo_{key_data["api_type"]}_key_12345')
        if key_data['api_type'] in ['facebook_ads', 'instagram_ads']:
            api_key.encrypt_secret(f'demo_{key_data["api_type"]}_secret_67890')
        api_key.save()
        print(f"✅ Created API key: {key_data['api_name']} (verified)")

# ============================================================================
# 3. CREATE DIVERSE DEMO CAMPAIGNS WITH VARYING PERFORMANCE
# ============================================================================
print("\n📊 Creating demo campaigns with realistic performance data...")

campaigns_data = [
    {
        'title': 'Summer Sale 2024 - Fashion Collection',
        'description': 'Promote our summer fashion collection with 30% discount',
        'platform': 'instagram',
        'budget': 5000,
        'days_ago': 45,
        'performance_level': 'high'  # High performer
    },
    {
        'title': 'New Product Launch - Eco Water Bottles',
        'description': 'Launch revolutionary eco-friendly water bottles',
        'platform': 'facebook',
        'budget': 8000,
        'days_ago': 38,
        'performance_level': 'medium'  # Average performer
    },
    {
        'title': 'Brand Awareness - Millennial Targeting',
        'description': 'Increase brand visibility among millennials 25-35',
        'platform': 'youtube',
        'budget': 10000,
        'days_ago': 30,
        'performance_level': 'high'  # High performer
    },
    {
        'title': 'Holiday Special - Black Friday Deals',
        'description': 'Black Friday early access deals and promotions',
        'platform': 'tiktok',
        'budget': 6000,
        'days_ago': 25,
        'performance_level': 'low'  # Low performer - needs improvement
    },
    {
        'title': 'LinkedIn B2B Campaign',
        'description': 'Target business professionals for enterprise solutions',
        'platform': 'linkedin',
        'budget': 7500,
        'days_ago': 20,
        'performance_level': 'medium'  # Average performer
    },
    {
        'title': 'Spring Collection Preview',
        'description': 'Early access to new spring collection',
        'platform': 'instagram',
        'budget': 4500,
        'days_ago': 15,
        'performance_level': 'high'  # Recent high performer
    },
    {
        'title': 'Tech Product Demo Campaign',
        'description': 'Showcase product features and benefits',
        'platform': 'youtube',
        'budget': 9000,
        'days_ago': 10,
        'performance_level': 'medium'  # Recent average
    }
]

today = datetime.now().date()
campaigns = []

for camp_data in campaigns_data:
    start_date = today - timedelta(days=camp_data['days_ago'])
    end_date = today + timedelta(days=30)
    
    campaign, created = Campaign.objects.get_or_create(
        user=demo_user,
        title=camp_data['title'],
        defaults={
            'description': camp_data['description'],
            'platform': camp_data['platform'],
            'budget': camp_data['budget'],
            'start_date': start_date,
            'end_date': end_date,
            'is_active': True
        }
    )
    
    # Store performance level for analytics generation
    campaign.performance_level = camp_data['performance_level']
    campaigns.append(campaign)
    
    if created:
        print(f"✅ Created campaign: {camp_data['title']} ({camp_data['performance_level']} performer)")

# ============================================================================
# 4. CREATE VARIED AD CONTENT
# ============================================================================
print("\n✍️  Creating diverse ad content...")

ad_content_templates = {
    'instagram': [
        "🌊 Dive into Summer Savings! Get 30% OFF on all beachwear. Limited time! #SummerSale #BeachReady",
        "Summer vibes only! 🏖️ Refresh your wardrobe with our hottest collection. Link in bio! #FashionDeals",
        "☀️ Sun's out, deals are out! Exclusive summer sale - 30% OFF everything. #ShopNow"
    ],
    'facebook': [
        "Introducing the future of hydration 💧 Our eco-bottles keep drinks cold for 24hrs. Pre-order now!",
        "🌱 Sustainable. Stylish. Superior. Meet the water bottle that does it all.",
        "Say goodbye to single-use plastics! Premium stainless steel bottles built to last."
    ],
    'youtube': [
        "Join thousands who trust our brand. Premium quality. Affordable prices. Exceptional service.",
        "Why choose us? Award-winning products, 5-star service, 100,000+ happy customers.",
        "Transform your lifestyle with our innovative solutions. Watch real testimonials today."
    ],
    'tiktok': [
        "🔥 Black Friday came early! Shop now before it's gone. Swipe up! #BlackFriday #Deals",
        "POV: You found the best Black Friday deals 😱 Limited stock! #Shopping #Sales",
        "This Black Friday deal is INSANE! 🤯 Watch till the end. #BestDeals"
    ],
    'linkedin': [
        "Empower your team with enterprise-grade solutions. Join Fortune 500 companies.",
        "ROI that speaks for itself. 40% productivity gains in first quarter. Read case studies.",
        "Professional tools for professional results. Trusted by industry leaders worldwide."
    ]
}

for campaign in campaigns:
    platform = campaign.platform
    templates = ad_content_templates.get(platform, ad_content_templates['instagram'])
    
    # Create 3-5 ads per campaign
    num_ads = random.randint(3, 5)
    for i in range(num_ads):
        text = templates[i % len(templates)]
        tone = ['persuasive', 'witty', 'casual', 'formal'][i % 4]
        
        # Vary performance based on campaign level
        if campaign.performance_level == 'high':
            views = random.randint(15000, 50000)
            clicks = int(views * random.uniform(0.04, 0.08))  # 4-8% CTR
        elif campaign.performance_level == 'medium':
            views = random.randint(8000, 25000)
            clicks = int(views * random.uniform(0.025, 0.04))  # 2.5-4% CTR
        else:  # low
            views = random.randint(3000, 12000)
            clicks = int(views * random.uniform(0.01, 0.025))  # 1-2.5% CTR
        
        conversions = int(clicks * random.uniform(0.05, 0.15))
        
        ad, created = AdContent.objects.get_or_create(
            campaign=campaign,
            text=text,
            defaults={
                'tone': tone,
                'platform': platform,
                'views': views,
                'clicks': clicks,
                'conversions': conversions
            }
        )
        
        if created:
            print(f"  ✅ Added ad for {campaign.title[:30]}... (CTR: {clicks/views*100:.2f}%)")

# ============================================================================
# 5. GENERATE REALISTIC ANALYTICS WITH TRENDS
# ============================================================================
print("\n📈 Generating realistic analytics data with performance trends...")

for campaign in campaigns:
    campaign_age = (today - campaign.start_date).days
    days_to_generate = min(45, campaign_age + 1)
    
    # Platform-specific multipliers
    platform_multipliers = {
        'instagram': 600, 'facebook': 700, 'youtube': 900,
        'linkedin': 350, 'tiktok': 1200
    }
    
    base_impressions = platform_multipliers.get(campaign.platform, 500)
    
    # Performance level adjustments
    if campaign.performance_level == 'high':
        base_impressions = int(base_impressions * 1.5)
        base_ctr = 0.045  # 4.5% base CTR
        conversion_mult = 1.3
    elif campaign.performance_level == 'medium':
        base_ctr = 0.03  # 3% base CTR
        conversion_mult = 1.0
    else:  # low
        base_impressions = int(base_impressions * 0.7)
        base_ctr = 0.018  # 1.8% base CTR
        conversion_mult = 0.7
    
    daily_budget = float(campaign.budget) / max(days_to_generate, 1)
    
    for day_offset in range(days_to_generate):
        analytics_date = today - timedelta(days=days_to_generate - day_offset - 1)
        
        if analytics_date > today or analytics_date < campaign.start_date:
            continue
        
        # Create realistic trends over time
        # Early days: lower performance
        # Middle days: peak performance
        # Recent days: slight decline or maintenance
        
        if day_offset < days_to_generate * 0.3:
            # Ramp up phase
            growth_factor = 0.6 + (day_offset / (days_to_generate * 0.3)) * 0.4
        elif day_offset < days_to_generate * 0.7:
            # Peak phase
            growth_factor = 1.0 + random.uniform(-0.1, 0.2)
        else:
            # Maturity phase
            if campaign.performance_level == 'high':
                growth_factor = 1.1 + random.uniform(-0.1, 0.1)  # Maintain high
            elif campaign.performance_level == 'low':
                growth_factor = 0.8 + random.uniform(-0.15, 0.05)  # Declining
            else:
                growth_factor = 0.95 + random.uniform(-0.1, 0.1)  # Slight decline
        
        # Day of week effects
        day_of_week = analytics_date.weekday()
        if day_of_week in [4, 5]:  # Friday, Saturday
            day_multiplier = 1.15
        elif day_of_week in [0, 1]:  # Monday, Tuesday
            day_multiplier = 1.05
        else:
            day_multiplier = 1.0
        
        randomness = random.uniform(0.85, 1.15)
        
        # Calculate metrics
        impressions = int(base_impressions * growth_factor * day_multiplier * randomness)
        ctr_variance = random.uniform(-0.01, 0.01)
        actual_ctr = max(0.01, base_ctr + ctr_variance)
        clicks = int(impressions * actual_ctr)
        
        conversion_rate = random.uniform(0.05, 0.15) * conversion_mult
        conversions = int(clicks * conversion_rate)
        
        spend = round(daily_budget * random.uniform(0.85, 1.15), 2)
        
        DailyAnalytics.objects.update_or_create(
            campaign=campaign,
            date=analytics_date,
            defaults={
                'impressions': impressions,
                'clicks': clicks,
                'conversions': conversions,
                'spend': spend
            }
        )
    
    # Update summary
    summary, _ = CampaignAnalyticsSummary.objects.get_or_create(campaign=campaign)
    summary.update_metrics()
    
    print(f"  ✅ {campaign.title[:35]}...")
    print(f"     {summary.total_impressions:,} impressions | {summary.total_clicks:,} clicks | {summary.avg_ctr:.2f}% CTR | Score: {summary.performance_score}/100")

# ============================================================================
# 6. CREATE MEANINGFUL A/B TESTS
# ============================================================================
print("\n🧪 Creating A/B test with real data...")

# Test on a high-performing campaign
test_campaign = campaigns[0]
ab_test, created = ABTest.objects.get_or_create(
    campaign=test_campaign,
    name='Headline Test - Summer Sale',
    defaults={
        'description': 'Testing two different headlines to see which performs better',
        'status': 'running',
        'success_metric': 'ctr',
        'min_sample_size': 1000,
        'start_date': datetime.now() - timedelta(days=7)
    }
)

if created:
    # Variation A: Control
    variation_a = ABTestVariation.objects.create(
        ab_test=ab_test,
        name='A',
        impressions=8500,
        clicks=340,
        conversions=42,
        spend=250
    )
    
    # Variation B: Winner
    variation_b = ABTestVariation.objects.create(
        ab_test=ab_test,
        name='B',
        impressions=8500,
        clicks=468,
        conversions=61,
        spend=250
    )
    
    print(f"✅ Created A/B test: {ab_test.name}")
    print(f"   Variation A: {variation_a.ctr}% CTR, {variation_a.conversion_rate}% Conv Rate")
    print(f"   Variation B: {variation_b.ctr}% CTR, {variation_b.conversion_rate}% Conv Rate (WINNER)")

# ============================================================================
# 7. ADD TEAM COMMENTS
# ============================================================================
print("\n💬 Adding team collaboration comments...")

comments_data = [
    ("Summer Sale campaign is crushing it! Consider scaling budget by 25%.", campaigns[0]),
    ("Instagram engagement is phenomenal. Let's replicate this strategy.", campaigns[0]),
    ("Black Friday campaign needs work. CTR is below 2%. Testing new creatives.", campaigns[3]),
    ("B2B LinkedIn campaign stable. May want to test video content next.", campaigns[4]),
    ("YouTube campaign performing well. Increasing daily budget tomorrow.", campaigns[2]),
]

for message, campaign in comments_data:
    comment, created = Comment.objects.get_or_create(
        campaign=campaign,
        user=demo_user,
        defaults={'message': message}
    )
    if created:
        print(f"  ✅ Added comment to {campaign.title[:40]}...")

# ============================================================================
# SUMMARY & VERIFICATION
# ============================================================================
print("\n" + "=" * 70)
print("🎉 DEMO SETUP COMPLETE!")
print("=" * 70)

print("\n📋 DEMO CREDENTIALS:")
print("-" * 70)
for user_data in demo_users:
    print(f"Email: {user_data['email']}")
    print(f"Password: {user_data['password']}")
    print(f"Role: {user_data['role']}")
    print("-" * 70)

print("\n📊 DEMO DATA SUMMARY:")
total_campaigns = Campaign.objects.filter(user=demo_user).count()
total_ads = AdContent.objects.filter(campaign__user=demo_user).count()
total_analytics = DailyAnalytics.objects.filter(campaign__user=demo_user).count()
total_api_keys = UserAPIKey.objects.filter(user=demo_user).count()

print(f"✅ {total_campaigns} Campaigns (varied performance levels)")
print(f"✅ {total_ads} Ad Copy variations")
print(f"✅ {total_analytics} Days of analytics data")
print(f"✅ {total_api_keys} API Keys (all verified)")
print(f"✅ 1 Active A/B Test with clear winner")
print(f"✅ {len(comments_data)} Team comments")

print("\n📈 PERFORMANCE BREAKDOWN:")
high_performers = [c for c in campaigns if c.performance_level == 'high']
medium_performers = [c for c in campaigns if c.performance_level == 'medium']
low_performers = [c for c in campaigns if c.performance_level == 'low']

print(f"   🔥 High Performers: {len(high_performers)} campaigns (CTR 4-8%)")
print(f"   📊 Medium Performers: {len(medium_performers)} campaigns (CTR 2.5-4%)")
print(f"   ⚠️  Low Performers: {len(low_performers)} campaigns (CTR 1-2.5%)")

print("\n💡 FEATURES TO DEMONSTRATE:")
print("   1. Dashboard - Real metrics with growth trends")
print("   2. Campaign Analytics - 45 days of detailed data")
print("   3. Audience Insights - Real engagement patterns")
print("   4. Weekly Reports - Actionable recommendations")
print("   5. A/B Testing - Live test with statistical significance")
print("   6. API Keys - All verified and ready")
print("   7. Performance Comparison - High vs Low performers")
print("   8. Trend Analysis - Growth/decline patterns")
print("   9. Budget Optimization - ROAS calculations")
print("   10. Team Collaboration - Comments and insights")

print("\n🎯 TEST SCENARIOS:")
print("   📌 High Performer: 'Summer Sale 2024' - Use for scaling demos")
print("   📌 Low Performer: 'Holiday Special' - Use for optimization demos")
print("   📌 Recent Campaign: 'Tech Product Demo' - Use for real-time tracking")
print("   📌 A/B Test: Check 'Headline Test' for winner identification")

print("\n🚀 READY TO DEMO!")
print("\n⚠️  NOTE: All data is demo data with realistic patterns")
print("    Features will show meaningful insights and recommendations!")
print("\n🎬 Start your servers: python manage.py runserver")
print("=" * 70)

# to delete the data
# Delete the database file
# rm db.sqlite3

# Recreate database
# python manage.py migrate

# Create your superuser
# python manage.py createsuperuser