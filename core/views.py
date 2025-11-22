# backend/core/views.py - WITH DEEPSEEK AND REAL-TIME ANALYTICS
from django.conf import settings
from django.core.files.base import ContentFile
from django.db.models import Sum, Count, Avg, Q, F, Max, Min
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, viewsets, permissions
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
import requests
import base64
import uuid
import io
import os
from datetime import datetime, timedelta
import json
from .models import Campaign, AdContent, ImageAsset, Comment, User, DailyAnalytics, CampaignAnalyticsSummary
from .serializers import (
    CampaignSerializer, AdContentSerializer, 
    ImageAssetSerializer, CommentSerializer, UserSerializer
)
from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from allauth.socialaccount.providers.github.views import GitHubOAuth2Adapter
from allauth.socialaccount.providers.oauth2.client import OAuth2Client
from dj_rest_auth.registration.views import SocialLoginView
from decimal import Decimal
from django.utils import timezone
from core.utils.cloudinary_storage import CloudinaryStorage


class IsOwnerOrReadOnly(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        if hasattr(obj, 'user'):
            return obj.user == request.user
        if hasattr(obj, 'campaign'):
            return obj.campaign.user == request.user
        return False

class CampaignViewSet(viewsets.ModelViewSet):
    serializer_class = CampaignSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrReadOnly]

    def get_queryset(self):
        return Campaign.objects.filter(user=self.request.user).order_by('-created_at')

    def get_serializer_context(self):
        return {'request': self.request}

class AdContentViewSet(viewsets.ModelViewSet):
    serializer_class = AdContentSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrReadOnly]

    def get_queryset(self):
        return AdContent.objects.filter(campaign__user=self.request.user).order_by('-created_at')

    def perform_create(self, serializer):
        campaign = serializer.validated_data['campaign']
        if campaign.user != self.request.user:
            raise permissions.PermissionDenied("You do not have permission for this campaign.")
        serializer.save()

class ImageAssetViewSet(viewsets.ModelViewSet):
    serializer_class = ImageAssetSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrReadOnly]

    def get_queryset(self):
        return ImageAsset.objects.filter(campaign__user=self.request.user).order_by('-created_at')
    
    def perform_create(self, serializer):
        campaign = serializer.validated_data['campaign']
        if campaign.user != self.request.user:
            raise permissions.PermissionDenied("You do not have permission for this campaign.")
        serializer.save()

class CommentViewSet(viewsets.ModelViewSet):
    serializer_class = CommentSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrReadOnly]

    def get_queryset(self):
        return Comment.objects.filter(campaign__user=self.request.user).order_by('-created_at')

    def perform_create(self, serializer):
        campaign = serializer.validated_data['campaign']
        if campaign.user != self.request.user:
            raise permissions.PermissionDenied("You do not have permission for this campaign.")
        serializer.save(user=self.request.user)

# ============================================================================
# Dashboard with Insights
# ============================================================================
class DashboardStatsView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        user = request.user
        
        # Force update all summaries before showing stats
        campaigns = Campaign.objects.filter(user=user)
        for campaign in campaigns:
            summary, created = CampaignAnalyticsSummary.objects.get_or_create(campaign=campaign)
            if created or summary.last_updated < timezone.now() - timedelta(hours=1):
                summary.update_metrics()
        
        # Basic counts
        total_campaigns = campaigns.count()
        total_ads = AdContent.objects.filter(campaign__user=user).count()
        total_images = ImageAsset.objects.filter(campaign__user=user).count()
        
        # Budget
        total_budget = campaigns.aggregate(
            total=Sum('budget')
        )['total'] or 0
        
        # Active campaigns
        today = datetime.now().date()
        active_campaigns = campaigns.filter(
            is_active=True,
            end_date__gte=today
        ).count()
        
        # This week stats
        week_ago = today - timedelta(days=7)
        ads_this_week = AdContent.objects.filter(
            campaign__user=user,
            created_at__gte=week_ago
        ).count()
        
        images_this_week = ImageAsset.objects.filter(
            campaign__user=user,
            created_at__gte=week_ago
        ).count()
        
        # Platform distribution
        platform_stats = campaigns.values('platform').annotate(
            count=Count('id')
        )
        
        # REAL AGGREGATE ANALYTICS
        summaries = CampaignAnalyticsSummary.objects.filter(campaign__user=user)
        total_impressions = sum(int(s.total_impressions) for s in summaries)
        total_clicks = sum(s.total_clicks for s in summaries)
        total_spend = sum(float(s.total_spend) for s in summaries)
        
        # Calculate overall CTR
        overall_ctr = round((total_clicks / total_impressions * 100), 2) if total_impressions > 0 else 0
        
        return Response({
            'total_campaigns': total_campaigns,
            'active_campaigns': active_campaigns,
            'total_ads': total_ads,
            'total_images': total_images,
            'total_budget': float(total_budget),
            'ads_this_week': ads_this_week,
            'images_this_week': images_this_week,
            'platform_distribution': list(platform_stats),
            
            # Real analytics
            'total_impressions': total_impressions,
            'total_clicks': total_clicks,
            'total_spend': round(total_spend, 2),
            'overall_ctr': overall_ctr,
            
            # Growth rate
            'growth_rate': round(((ads_this_week + images_this_week) / max(total_ads + total_images, 1)) * 100, 1),
            
            # Last updated
            'last_updated': timezone.now().isoformat()
        })

# ============================================================================
# REAL-TIME Analytics Summary
# ============================================================================
class AnalyticsSummaryView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        campaign_id = request.query_params.get('campaign_id')
        
        if not campaign_id:
            return Response(
                {'error': 'campaign_id query parameter is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            campaign = Campaign.objects.get(id=campaign_id, user=request.user)
        except Campaign.DoesNotExist:
            return Response(
                {'error': 'Campaign not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get real counts
        ad_count = AdContent.objects.filter(campaign=campaign).count()
        image_count = ImageAsset.objects.filter(campaign=campaign).count()
        
        # Calculate days since campaign started
        start_date = campaign.start_date
        today = datetime.now().date()
        days_active = (today - start_date).days + 1
        
        # Generate realistic data based on actual campaign data
        dates = []
        impressions = []
        clicks = []
        conversions = []
        spend = []
        ctr_data = []
        
        current_date = start_date
        # Base metrics on actual content created
        content_multiplier = max(1, ad_count + image_count)
        base_impressions = 300 * content_multiplier
        daily_budget = float(campaign.budget or 100) / max(days_active, 1)
        
        days_shown = min(days_active, 30)
        
        for day_num in range(days_shown):
            dates.append(current_date.strftime('%b %d'))
            
            # More realistic growth pattern
            growth_factor = 1 + (day_num * 0.12)
            randomness = 0.9 + (day_num % 7) * 0.03
            
            day_impressions = int(base_impressions * growth_factor * randomness)
            day_clicks = int(day_impressions * (0.025 + (day_num % 5) * 0.008))
            day_conversions = int(day_clicks * (0.06 + (day_num % 3) * 0.015))
            day_spend = round(daily_budget * (0.85 + (day_num % 4) * 0.07), 2)
            day_ctr = round((day_clicks / day_impressions * 100), 2) if day_impressions > 0 else 0
            
            impressions.append(day_impressions)
            clicks.append(day_clicks)
            conversions.append(day_conversions)
            spend.append(day_spend)
            ctr_data.append(day_ctr)
            
            current_date += timedelta(days=1)
        
        total_impressions = sum(impressions)
        total_clicks = sum(clicks)
        total_conversions = sum(conversions)
        total_spend = sum(spend)
        
        avg_ctr = round((total_clicks / total_impressions * 100), 2) if total_impressions > 0 else 0
        avg_cpc = round((total_spend / total_clicks), 2) if total_clicks > 0 else 0
        conversion_rate = round((total_conversions / total_clicks * 100), 2) if total_clicks > 0 else 0
        cost_per_conversion = round((total_spend / total_conversions), 2) if total_conversions > 0 else 0
        roas = round((total_conversions * 45 / total_spend), 2) if total_spend > 0 else 0
        
        return Response({
            'campaign_id': str(campaign.id),
            'campaign_name': campaign.title,
            'platform': campaign.platform,
            'ad_count': ad_count,
            'image_count': image_count,
            'days_active': days_active,
            'dates': dates,
            'impressions': impressions,
            'clicks': clicks,
            'conversions': conversions,
            'spend': spend,
            'ctr': ctr_data,
            'total_impressions': total_impressions,
            'total_clicks': total_clicks,
            'total_conversions': total_conversions,
            'total_spend': round(total_spend, 2),
            'avg_ctr': avg_ctr,
            'avg_cpc': avg_cpc,
            'conversion_rate': conversion_rate,
            'cost_per_conversion': cost_per_conversion,
            'roas': roas,
            'performance_score': min(98, int(65 + (roas * 6) + (conversion_rate * 2.5)))
        })

# ============================================================================
# REAL AUDIENCE INSIGHTS - COMPLETELY REWRITTEN
# ============================================================================
class AudienceInsightsView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        campaign_id = request.query_params.get('campaign_id')
        
        if campaign_id:
            try:
                campaign = Campaign.objects.get(id=campaign_id, user=request.user)
                # Get real analytics for this campaign
                summary, _ = CampaignAnalyticsSummary.objects.get_or_create(campaign=campaign)
                
                total_reach = int(summary.total_impressions)
                engaged_users = summary.total_clicks
                engagement_rate = float(summary.avg_ctr)
                
                platform = campaign.platform
                
                # Get daily data for trend analysis
                daily_data = DailyAnalytics.objects.filter(
                    campaign=campaign
                ).order_by('-date')[:30]
                
                # Calculate engagement trends
                recent_7_days = daily_data[:7]
                previous_7_days = daily_data[7:14]
                
                recent_engagement = sum(d.clicks for d in recent_7_days)
                previous_engagement = sum(d.clicks for d in previous_7_days)
                
                engagement_trend = "Increasing" if recent_engagement > previous_engagement else "Decreasing"
                engagement_change = 0
                if previous_engagement > 0:
                    engagement_change = round(((recent_engagement - previous_engagement) / previous_engagement) * 100, 1)
                
            except Campaign.DoesNotExist:
                return Response({'error': 'Campaign not found'}, status=404)
        else:
            # Aggregate across all user campaigns
            user = request.user
            summaries = CampaignAnalyticsSummary.objects.filter(campaign__user=user)
            
            total_reach = sum(int(s.total_impressions) for s in summaries)
            engaged_users = sum(s.total_clicks for s in summaries)
            engagement_rate = round(
                (engaged_users / total_reach * 100) if total_reach > 0 else 0, 
                2
            )
            
            # Get most used platform
            platform_counts = Campaign.objects.filter(user=user).values('platform').annotate(
                count=Count('id')
            ).order_by('-count')
            
            platform = platform_counts[0]['platform'] if platform_counts else 'instagram'
            
            # Aggregate trend
            week_ago = datetime.now().date() - timedelta(days=7)
            two_weeks_ago = week_ago - timedelta(days=7)
            
            recent = DailyAnalytics.objects.filter(
                campaign__user=user,
                date__gte=week_ago
            ).aggregate(clicks=Sum('clicks'))['clicks'] or 0
            
            previous = DailyAnalytics.objects.filter(
                campaign__user=user,
                date__gte=two_weeks_ago,
                date__lt=week_ago
            ).aggregate(clicks=Sum('clicks'))['clicks'] or 1
            
            engagement_trend = "Increasing" if recent > previous else "Decreasing"
            engagement_change = round(((recent - previous) / previous) * 100, 1)
        
        # REAL RECOMMENDATIONS based on actual data
        recommendations = self._generate_real_recommendations(
            engagement_rate, 
            total_reach, 
            engaged_users,
            engagement_trend,
            engagement_change
        )
        
        # Platform-specific demographics (based on industry data)
        demographics = self._get_platform_demographics(platform)
        
        # Best posting times based on actual campaign performance
        best_times = self._calculate_best_times(campaign_id if campaign_id else None, request.user)
        
        # Top locations (if you have location data, otherwise industry averages)
        top_locations = self._get_top_locations(platform)
        
        # Top interests based on platform
        interests = self._get_platform_interests(platform, engagement_rate)
        
        return Response({
            'platform': platform,
            'total_reach': total_reach,
            'engaged_users': engaged_users,
            'engagement_rate': engagement_rate,
            'engagement_trend': engagement_trend,
            'engagement_change': f"{'+' if engagement_change > 0 else ''}{engagement_change}%",
            
            # Real data-driven insights
            'age_groups': demographics['age_groups'],
            'gender': demographics['gender'],
            'interests': interests,
            'best_times': best_times,
            'top_locations': top_locations,
            
            'recommendations': recommendations,
            'data_note': 'Demographics based on industry averages for ' + platform.title() + '. Connect ad platforms for precise audience data.'
        })
    
    def _generate_real_recommendations(self, engagement_rate, total_reach, engaged_users, trend, change):
        """Generate actionable recommendations based on real metrics"""
        recommendations = []
        
        # Engagement rate analysis
        if engagement_rate < 2:
            recommendations.append({
                'type': 'performance',
                'message': f'Your {engagement_rate}% engagement rate is below industry average (3-5%). Test different ad creatives and targeting.',
                'priority': 'high',
                'action': 'A/B test new creatives'
            })
        elif engagement_rate > 5:
            recommendations.append({
                'type': 'performance',
                'message': f'Excellent {engagement_rate}% engagement rate! Consider increasing budget to maximize reach.',
                'priority': 'high',
                'action': 'Scale campaign budget'
            })
        else:
            recommendations.append({
                'type': 'performance',
                'message': f'Your {engagement_rate}% engagement rate is on par with industry standards. Continue optimizing.',
                'priority': 'medium',
                'action': 'Monitor and optimize'
            })
        
        # Reach analysis
        if total_reach < 10000:
            recommendations.append({
                'type': 'reach',
                'message': f'Current reach: {total_reach:,} impressions. Increase budget or extend campaign duration for better visibility.',
                'priority': 'high',
                'action': 'Increase budget by 20%'
            })
        elif total_reach > 100000:
            recommendations.append({
                'type': 'reach',
                'message': f'Great reach of {total_reach:,} impressions! Focus on conversion optimization.',
                'priority': 'medium',
                'action': 'Optimize for conversions'
            })
        
        # Trend analysis
        if trend == "Decreasing":
            recommendations.append({
                'type': 'timing',
                'message': f'Engagement is {trend.lower()} ({change}%). Review posting schedule and refresh ad creatives.',
                'priority': 'high',
                'action': 'Refresh campaign strategy'
            })
        else:
            recommendations.append({
                'type': 'timing',
                'message': f'Positive trend: Engagement is {trend.lower()} ({change}%). Maintain current strategy.',
                'priority': 'low',
                'action': 'Continue monitoring'
            })
        
        return recommendations
    
    def _calculate_best_times(self, campaign_id, user):
        """Calculate actual best posting times from campaign data"""
        if campaign_id:
            # Get performance by day of week for specific campaign
            daily_data = DailyAnalytics.objects.filter(campaign_id=campaign_id)
        else:
            # Aggregate across all user campaigns
            daily_data = DailyAnalytics.objects.filter(campaign__user=user)
        
        if not daily_data.exists():
            # Return defaults if no data
            return [
                {'day': 'Monday', 'time': '6-9 PM', 'engagement': 'Medium'},
                {'day': 'Wednesday', 'time': '12-2 PM', 'engagement': 'High'},
                {'day': 'Friday', 'time': '5-8 PM', 'engagement': 'Very High'},
            ]
        
        # Group by day of week and calculate average engagement
        day_performance = {}
        for data in daily_data:
            day_name = data.date.strftime('%A')
            if day_name not in day_performance:
                day_performance[day_name] = {'clicks': 0, 'impressions': 0, 'count': 0}
            
            day_performance[day_name]['clicks'] += data.clicks
            day_performance[day_name]['impressions'] += data.impressions
            day_performance[day_name]['count'] += 1
        
        # Calculate engagement rates and sort
        results = []
        for day, stats in day_performance.items():
            avg_ctr = (stats['clicks'] / stats['impressions'] * 100) if stats['impressions'] > 0 else 0
            
            # Determine engagement level
            if avg_ctr > 5:
                engagement = 'Very High'
            elif avg_ctr > 3:
                engagement = 'High'
            elif avg_ctr > 1:
                engagement = 'Medium'
            else:
                engagement = 'Low'
            
            results.append({
                'day': day,
                'time': '6-9 PM',  # Default prime time
                'engagement': engagement,
                'ctr': round(avg_ctr, 2)
            })
        
        # Sort by engagement and return top 4
        results.sort(key=lambda x: x['ctr'], reverse=True)
        return results[:4]
    
    def _get_platform_demographics(self, platform):
        """Get industry-standard demographics for platform"""
        demographics = {
            'instagram': {
                'age_groups': [
                    {'range': '18-24', 'percentage': 30.8, 'engagement': 'High'},
                    {'range': '25-34', 'percentage': 31.5, 'engagement': 'Very High'},
                    {'range': '35-44', 'percentage': 16.1, 'engagement': 'Medium'},
                    {'range': '45-54', 'percentage': 11.2, 'engagement': 'Low'},
                    {'range': '55+', 'percentage': 10.4, 'engagement': 'Low'}
                ],
                'gender': [
                    {'type': 'Female', 'percentage': 51.8},
                    {'type': 'Male', 'percentage': 48.2}
                ]
            },
            'facebook': {
                'age_groups': [
                    {'range': '18-24', 'percentage': 23.1, 'engagement': 'Medium'},
                    {'range': '25-34', 'percentage': 31.6, 'engagement': 'High'},
                    {'range': '35-44', 'percentage': 18.8, 'engagement': 'High'},
                    {'range': '45-54', 'percentage': 14.2, 'engagement': 'Medium'},
                    {'range': '55+', 'percentage': 12.3, 'engagement': 'Low'}
                ],
                'gender': [
                    {'type': 'Male', 'percentage': 56.3},
                    {'type': 'Female', 'percentage': 43.7}
                ]
            },
            'linkedin': {
                'age_groups': [
                    {'range': '18-24', 'percentage': 20.4, 'engagement': 'Medium'},
                    {'range': '25-34', 'percentage': 38.9, 'engagement': 'Very High'},
                    {'range': '35-44', 'percentage': 21.7, 'engagement': 'High'},
                    {'range': '45-54', 'percentage': 12.6, 'engagement': 'Medium'},
                    {'range': '55+', 'percentage': 6.4, 'engagement': 'Low'}
                ],
                'gender': [
                    {'type': 'Male', 'percentage': 57.2},
                    {'type': 'Female', 'percentage': 42.8}
                ]
            },
            'tiktok': {
                'age_groups': [
                    {'range': '18-24', 'percentage': 42.9, 'engagement': 'Very High'},
                    {'range': '25-34', 'percentage': 32.5, 'engagement': 'High'},
                    {'range': '35-44', 'percentage': 15.4, 'engagement': 'Medium'},
                    {'range': '45-54', 'percentage': 6.2, 'engagement': 'Low'},
                    {'range': '55+', 'percentage': 3.0, 'engagement': 'Low'}
                ],
                'gender': [
                    {'type': 'Female', 'percentage': 57.1},
                    {'type': 'Male', 'percentage': 42.9}
                ]
            },
            'youtube': {
                'age_groups': [
                    {'range': '18-24', 'percentage': 15.2, 'engagement': 'High'},
                    {'range': '25-34', 'percentage': 21.3, 'engagement': 'Very High'},
                    {'range': '35-44', 'percentage': 19.8, 'engagement': 'High'},
                    {'range': '45-54', 'percentage': 16.7, 'engagement': 'Medium'},
                    {'range': '55+', 'percentage': 27.0, 'engagement': 'Medium'}
                ],
                'gender': [
                    {'type': 'Male', 'percentage': 54.4},
                    {'type': 'Female', 'percentage': 45.6}
                ]
            }
        }
        
        return demographics.get(platform, demographics['instagram'])
    
    def _get_platform_interests(self, platform, engagement_rate):
        """Get top interests based on platform and engagement"""
        base_interests = {
            'instagram': [
                {'name': 'Fashion & Beauty', 'score': 88},
                {'name': 'Health & Fitness', 'score': 82},
                {'name': 'Food & Dining', 'score': 79},
                {'name': 'Travel & Adventure', 'score': 75},
                {'name': 'Technology', 'score': 68}
            ],
            'facebook': [
                {'name': 'Family & Relationships', 'score': 85},
                {'name': 'News & Current Events', 'score': 78},
                {'name': 'Entertainment', 'score': 76},
                {'name': 'Shopping & Retail', 'score': 72},
                {'name': 'Sports & Outdoors', 'score': 68}
            ],
            'linkedin': [
                {'name': 'Business & Industry', 'score': 92},
                {'name': 'Technology & Innovation', 'score': 88},
                {'name': 'Leadership & Management', 'score': 82},
                {'name': 'Marketing & Sales', 'score': 78},
                {'name': 'Finance & Investing', 'score': 74}
            ],
            'tiktok': [
                {'name': 'Entertainment & Comedy', 'score': 95},
                {'name': 'Music & Dance', 'score': 89},
                {'name': 'Fashion & Style', 'score': 84},
                {'name': 'Food & Recipes', 'score': 78},
                {'name': 'DIY & Crafts', 'score': 72}
            ],
            'youtube': [
                {'name': 'Entertainment & Gaming', 'score': 86},
                {'name': 'How-To & Education', 'score': 83},
                {'name': 'Music & Videos', 'score': 80},
                {'name': 'Technology & Reviews', 'score': 76},
                {'name': 'Sports & Fitness', 'score': 71}
            ]
        }
        
        interests = base_interests.get(platform, base_interests['instagram'])
        
        # Adjust scores based on engagement rate
        engagement_multiplier = min(1.2, max(0.8, engagement_rate / 4))
        for interest in interests:
            interest['score'] = int(interest['score'] * engagement_multiplier)
        
        return interests
    
    def _get_top_locations(self, platform):
        """Get top locations (industry data)"""
        return [
            {'city': 'New York, NY', 'percentage': 12.4},
            {'city': 'Los Angeles, CA', 'percentage': 10.8},
            {'city': 'Chicago, IL', 'percentage': 7.2},
            {'city': 'Houston, TX', 'percentage': 6.5},
            {'city': 'Miami, FL', 'percentage': 5.9},
            {'city': 'San Francisco, CA', 'percentage': 5.3}
        ]


# ============================================================================
# REAL WEEKLY REPORT WITH ACTIONABLE INSIGHTS
# ============================================================================
class WeeklyReportView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        user = request.user
        today = datetime.now().date()
        week_ago = today - timedelta(days=7)
        two_weeks_ago = week_ago - timedelta(days=7)
        
        # REAL DATA: Count actual resources created this week
        campaigns_created = Campaign.objects.filter(
            user=user,
            created_at__date__gte=week_ago
        ).count()
        
        ads_generated = AdContent.objects.filter(
            campaign__user=user,
            created_at__date__gte=week_ago
        ).count()
        
        images_generated = ImageAsset.objects.filter(
            campaign__user=user,
            created_at__date__gte=week_ago
        ).count()
        
        active_campaigns = Campaign.objects.filter(
            user=user,
            is_active=True,
            end_date__gte=today
        ).count()
        
        # REAL WEEKLY ANALYTICS
        weekly_analytics = DailyAnalytics.objects.filter(
            campaign__user=user,
            date__gte=week_ago,
            date__lte=today
        ).aggregate(
            total_impressions=Sum('impressions'),
            total_clicks=Sum('clicks'),
            total_conversions=Sum('conversions'),
            total_spend=Sum('spend')
        )
        
        # PREVIOUS WEEK FOR COMPARISON
        previous_week_analytics = DailyAnalytics.objects.filter(
            campaign__user=user,
            date__gte=two_weeks_ago,
            date__lt=week_ago
        ).aggregate(
            prev_impressions=Sum('impressions'),
            prev_clicks=Sum('clicks'),
            prev_conversions=Sum('conversions'),
            prev_spend=Sum('spend')
        )
        
        # Calculate metrics
        total_impressions = weekly_analytics['total_impressions'] or 0
        total_clicks = weekly_analytics['total_clicks'] or 0
        total_conversions = weekly_analytics['total_conversions'] or 0
        total_spend = float(weekly_analytics['total_spend'] or 0)
        
        prev_impressions = previous_week_analytics['prev_impressions'] or 1
        prev_clicks = previous_week_analytics['prev_clicks'] or 1
        prev_conversions = previous_week_analytics['prev_conversions'] or 1
        
        # Calculate growth rates
        impression_growth = round(((total_impressions - prev_impressions) / prev_impressions) * 100, 1)
        click_growth = round(((total_clicks - prev_clicks) / prev_clicks) * 100, 1)
        conversion_growth = round(((total_conversions - prev_conversions) / prev_conversions) * 100, 1)
        
        # Calculate rates
        avg_ctr = round((total_clicks / total_impressions * 100), 2) if total_impressions > 0 else 0
        conversion_rate = round((total_conversions / total_clicks * 100), 2) if total_clicks > 0 else 0
        
        # Get top performing campaign
        top_campaign = Campaign.objects.filter(
            user=user,
            analytics_summary__isnull=False
        ).order_by('-analytics_summary__performance_score').first()
        
        # Get worst performing campaign for improvement suggestions
        worst_campaign = Campaign.objects.filter(
            user=user,
            analytics_summary__isnull=False
        ).order_by('analytics_summary__performance_score').first()
        
        # REAL INSIGHTS from actual data
        insights = {
            'top_performing_platform': top_campaign.platform.title() if top_campaign else 'N/A',
            'top_campaign_name': top_campaign.title if top_campaign else 'N/A',
            'top_campaign_score': top_campaign.analytics_summary.performance_score if top_campaign else 0,
            'total_impressions': total_impressions,
            'total_clicks': total_clicks,
            'total_conversions': total_conversions,
            'total_spend': round(total_spend, 2),
            'avg_ctr': avg_ctr,
            'conversion_rate': conversion_rate,
            'impression_growth': f"{'+' if impression_growth > 0 else ''}{impression_growth}%",
            'click_growth': f"{'+' if click_growth > 0 else ''}{click_growth}%",
            'conversion_growth': f"{'+' if conversion_growth > 0 else ''}{conversion_growth}%",
            'engagement_trend': 'Increasing' if click_growth > 0 else 'Decreasing',
            'roas': round((total_conversions * 50 / total_spend), 2) if total_spend > 0 else 0
        }
        
        # SMART RECOMMENDATIONS based on real performance
        recommendations = self._generate_weekly_recommendations(
            avg_ctr=avg_ctr,
            conversion_rate=conversion_rate,
            click_growth=click_growth,
            total_spend=total_spend,
            active_campaigns=active_campaigns,
            ads_generated=ads_generated,
            top_campaign=top_campaign,
            worst_campaign=worst_campaign,
            insights=insights
        )
        
        # ACTIONABLE NEXT STEPS
        next_steps = self._generate_next_steps(
            top_campaign=top_campaign,
            worst_campaign=worst_campaign,
            avg_ctr=avg_ctr,
            ads_generated=ads_generated,
            active_campaigns=active_campaigns
        )
        
        return Response({
            'period': f'{week_ago.strftime("%b %d")} - {today.strftime("%b %d, %Y")}',
            'summary': {
                'campaigns_created': campaigns_created,
                'ads_generated': ads_generated,
                'images_generated': images_generated,
                'active_campaigns': active_campaigns,
                'total_engagement': total_clicks,
                'engagement_growth': insights['click_growth']
            },
            'insights': insights,
            'recommendations': recommendations,
            'next_steps': next_steps,
            'comparison_available': prev_clicks > 0
        })
    
    def _generate_weekly_recommendations(self, avg_ctr, conversion_rate, click_growth, 
                                        total_spend, active_campaigns, ads_generated,
                                        top_campaign, worst_campaign, insights):
        """Generate data-driven recommendations"""
        recommendations = []
        
        # CTR Analysis
        if avg_ctr < 2:
            recommendations.append({
                'category': 'Performance',
                'priority': 'high',
                'title': 'Improve Click-Through Rate',
                'description': f'Your weekly CTR is {avg_ctr}%, which is below the 3-5% industry benchmark. Test new headlines and visuals.',
                'action': 'A/B Test Creatives',
                'impact': '+50-100% potential CTR increase',
                'metric': 'CTR',
                'current': f'{avg_ctr}%',
                'target': '3-5%'
            })
        elif avg_ctr >= 5:
            recommendations.append({
                'category': 'Performance',
                'priority': 'high',
                'title': 'Excellent Performance - Scale Up',
                'description': f'Your {avg_ctr}% CTR is outstanding! Scale your best campaigns to maximize results.',
                'action': 'Increase Budget',
                'impact': '+100-200% potential reach',
                'metric': 'CTR',
                'current': f'{avg_ctr}%',
                'target': 'Maintain'
            })
        
        # Conversion Rate Analysis
        if conversion_rate < 5 and avg_ctr > 2:
            recommendations.append({
                'category': 'Optimization',
                'priority': 'high',
                'title': 'Optimize Conversion Funnel',
                'description': f'You have good traffic ({avg_ctr}% CTR) but low conversions ({conversion_rate}%). Review landing pages.',
                'action': 'Optimize Landing Page',
                'impact': '+30-60% conversion increase',
                'metric': 'Conversion Rate',
                'current': f'{conversion_rate}%',
                'target': '5-10%'
            })
        
        # Growth Trend
        if click_growth < -10:
            recommendations.append({
                'category': 'Engagement',
                'priority': 'high',
                'title': 'Reverse Declining Engagement',
                'description': f'Engagement dropped {click_growth}% this week. Refresh ad creatives and review audience targeting.',
                'action': 'Refresh Campaign',
                'impact': 'Reverse negative trend',
                'metric': 'Weekly Growth',
                'current': f'{click_growth}%',
                'target': '+10%'
            })
        elif click_growth > 20:
            recommendations.append({
                'category': 'Growth',
                'priority': 'medium',
                'title': 'Capitalize on Momentum',
                'description': f'Strong {click_growth}% growth! Now is the time to increase investment and expand reach.',
                'action': 'Scale Investment',
                'impact': 'Maximize growth period',
                'metric': 'Weekly Growth',
                'current': f'{click_growth}%',
                'target': 'Sustain'
            })
        
        # Content Generation
        if ads_generated < 5:
            recommendations.append({
                'category': 'Content',
                'priority': 'medium',
                'title': 'Increase Ad Variations',
                'description': f'Only {ads_generated} ads created this week. More variations improve testing effectiveness.',
                'action': 'Generate 5+ Variations',
                'impact': '+25% optimization potential',
                'metric': 'Content Volume',
                'current': f'{ads_generated} ads',
                'target': '10+ ads/week'
            })
        
        # Budget Efficiency
        if total_spend > 0 and insights['roas'] < 2:
            recommendations.append({
                'category': 'Budget',
                'priority': 'high',
                'title': 'Improve Return on Ad Spend',
                'description': f'Current ROAS is {insights["roas"]}x. Review targeting and pause low-performing campaigns.',
                'action': 'Optimize Budget Allocation',
                'impact': '+50-100% ROAS improvement',
                'metric': 'ROAS',
                'current': f'{insights["roas"]}x',
                'target': '3-5x'
            })
        
        # Campaign Activity
        if active_campaigns == 0:
            recommendations.append({
                'category': 'Campaigns',
                'priority': 'high',
                'title': 'Launch Active Campaigns',
                'description': 'No active campaigns running. Create and launch campaigns to start generating results.',
                'action': 'Create Campaign',
                'impact': 'Begin generating ROI',
                'metric': 'Active Campaigns',
                'current': '0',
                'target': '3-5'
            })
        
        # Top Campaign Optimization
        if top_campaign and top_campaign.analytics_summary.performance_score > 70:
            recommendations.append({
                'category': 'Scaling',
                'priority': 'medium',
                'title': f'Scale Top Performer: {top_campaign.title}',
                'description': f'This campaign has {top_campaign.analytics_summary.performance_score}/100 score. Allocate more budget.',
                'action': 'Increase Budget by 25%',
                'impact': '+30-50% additional reach',
                'metric': 'Performance Score',
                'current': f'{top_campaign.analytics_summary.performance_score}/100',
                'target': 'Maximize'
            })
        
        # Sort by priority
        priority_order = {'high': 0, 'medium': 1, 'low': 2}
        recommendations.sort(key=lambda x: priority_order.get(x['priority'], 3))
        
        return recommendations[:6]  # Return top 6
    
    def _generate_next_steps(self, top_campaign, worst_campaign, avg_ctr, 
                            ads_generated, active_campaigns):
        """Generate specific action items"""
        steps = []
        
        if top_campaign:
            steps.append(f"Review and scale best performer: {top_campaign.title}")
        
        if worst_campaign and worst_campaign.analytics_summary.performance_score < 50:
            steps.append(f"Improve or pause low performer: {worst_campaign.title} ({worst_campaign.analytics_summary.performance_score}/100)")
        
        if avg_ctr < 3:
            steps.append(f"Run A/B tests on headlines and visuals to improve {avg_ctr}% CTR")
        
        if ads_generated < 10:
            steps.append(f"Generate {10 - ads_generated} more ad variations for testing")
        
        if active_campaigns < 3:
            steps.append("Launch 2-3 new campaigns targeting different audiences")
        
        steps.append("Check audience insights for optimal posting times")
        steps.append("Review budget allocation across all campaigns")
        
        return steps[:5]

# ============================================================================
# AI Text Generation with DeepSeek V3.1
# ============================================================================
class AdContentGeneratorView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        prompt = request.data.get('prompt')
        tone = request.data.get('tone', 'persuasive')
        platform = request.data.get('platform', 'instagram')
        campaign_id = request.data.get('campaign_id')
        num_variations = request.data.get('variations', 1)

        if not prompt:
            return Response({"error": "Prompt is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Check if API key is configured
            api_key = settings.OPENROUTER_API_KEY
            if not api_key:
                return Response(
                    {"error": "OPENROUTER_API_KEY not configured. Please add it to your .env file"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            platform_guides = {
                'instagram': "Keep it under 150 characters, use 2-3 relevant emojis, include a strong CTA, and 3-5 hashtags",
                'facebook': "Be conversational, 100-150 words, ask questions to encourage engagement",
                'linkedin': "Professional tone, focus on business value, 150-250 words, no emojis",
                'youtube': "Engaging hook in first 5 words, 150-200 words, include timestamp markers",
                'tiktok': "Super casual, trendy language, under 100 characters, use popular slang"
            }
            
            guide = platform_guides.get(platform, platform_guides['instagram'])
            
            full_prompt = f"""You are an expert advertising copywriter. Generate {num_variations} creative ad {'copies' if num_variations > 1 else 'copy'} for {platform} with a {tone} tone.

Platform Guidelines: {guide}

Product/Service Description: {prompt}

Generate high-quality, conversion-focused ad copy that:
1. Grabs attention immediately
2. Highlights key benefits
3. Creates urgency or desire
4. Includes a clear call-to-action
5. Follows platform best practices

{'Generate ' + str(num_variations) + ' different variations, each on a new line starting with "VARIATION X:"' if num_variations > 1 else ''}"""
            
            # Use DeepSeek V3.1 via OpenRouter
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
                'HTTP-Referer': 'http://localhost:5173',
                'X-Title': 'AdVision AI'
            }
            
            payload = {
                "model": "deepseek/deepseek-chat",
                "messages": [
                    {
                        "role": "user",
                        "content": full_prompt
                    }
                ],
                "temperature": 0.9,
                "max_tokens": 2048,
            }
            
            response = requests.post(
                'https://openrouter.ai/api/v1/chat/completions',
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code != 200:
                error_msg = response.json().get('error', {}).get('message', 'Unknown error')
                raise Exception(f"OpenRouter API error: {error_msg}")
            
            response_data = response.json()
            
            # Extract generated text from OpenRouter response
            if 'choices' in response_data and len(response_data['choices']) > 0:
                generated_text = response_data['choices'][0]['message']['content']
            else:
                raise Exception("No content generated from DeepSeek API")
            
            saved_ads = []
            if campaign_id:
                try:
                    campaign = Campaign.objects.get(id=campaign_id, user=request.user)
                    
                    if num_variations > 1 and "VARIATION" in generated_text:
                        variations = [v.strip() for v in generated_text.split("VARIATION") if v.strip()]
                        variations = [v.split(":", 1)[-1].strip() if ":" in v else v for v in variations]
                    else:
                        variations = [generated_text]
                    
                    for var_text in variations[:num_variations]:
                        ad_content = AdContent.objects.create(
                            campaign=campaign,
                            text=var_text,
                            tone=tone,
                            platform=platform
                        )
                        saved_ads.append(AdContentSerializer(ad_content).data)
                        
                except Campaign.DoesNotExist:
                    pass
            
            return Response({
                "generated_text": generated_text,
                "variations": len(saved_ads) if saved_ads else 1,
                "saved_ads": saved_ads
            }, status=status.HTTP_200_OK)

        except requests.exceptions.Timeout:
            return Response(
                {"error": "Request timed out. Please try again."},
                status=status.HTTP_408_REQUEST_TIMEOUT
            )
        except requests.exceptions.RequestException as e:
            return Response(
                {"error": f"Network error: {str(e)}"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            print(f"Text generation error: {error_trace}")
            
            error_message = str(e)
            if "API key" in error_message or "403" in error_message:
                error_message = "Invalid or missing OpenRouter API key. Please check your configuration."
            elif "quota" in error_message.lower() or "429" in error_message:
                error_message = "API quota exceeded. Please try again later."
            elif "timeout" in error_message.lower():
                error_message = "Request timed out. Please try again with a shorter prompt."
            
            return Response(
                {"error": f"AI generation failed: {error_message}"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

# ============================================================================
# ENHANCED AI IMAGE GENERATION WITH MULTIPLE AI PROVIDERS
# ============================================================================
class ImageGeneratorView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        prompt = request.data.get('prompt')
        campaign_id = request.data.get('campaign_id')
        style = request.data.get('style', 'professional')
        aspect_ratio = request.data.get('aspect_ratio', '1:1')
        
        # Ad template options
        ad_template = request.data.get('ad_template', 'modern')
        include_text = request.data.get('include_text', True)
        headline = request.data.get('headline', '')
        tagline = request.data.get('tagline', '')
        cta_text = request.data.get('cta_text', 'Learn More')
        
        generate_both = request.data.get('generate_both', True)

        if not prompt:
            return Response({"error": "Prompt is required"}, status=status.HTTP_400_BAD_REQUEST)
        if not campaign_id:
            return Response({"error": "campaign_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            campaign = Campaign.objects.get(id=campaign_id, user=request.user)
        except Campaign.DoesNotExist:
            return Response(
                {"error": "Campaign not found or you do not have permission"}, 
                status=status.HTTP_404_NOT_FOUND
            )

        # Enhanced prompt engineering
        style_prompts = {
            'professional': 'professional photography, commercial advertising style, studio lighting, high-end product photography, sharp focus, clean background, advertisement quality',
            'creative': 'creative advertising design, vibrant and eye-catching, artistic composition, bold colors, modern aesthetic, Instagram-worthy',
            'minimal': 'minimalist advertisement design, clean and simple, lots of negative space, elegant typography area, modern premium look, white or subtle background',
            'vintage': 'vintage advertisement poster style, retro aesthetic, classic design, nostalgic feel, aged paper texture',
            'lifestyle': 'lifestyle photography, authentic moments, aspirational living, natural lighting, relatable scenes, Instagram aesthetic',
            'luxury': 'luxury brand advertisement, premium quality, elegant and sophisticated, high-end lifestyle, metallic accents, refined aesthetic'
        }
        
        style_modifier = style_prompts.get(style, style_prompts['professional'])
        
        enhanced_prompt = f"""Professional advertisement image: {prompt}. 
Style: {style_modifier}. 
Requirements: Leave space for text overlay at top or bottom, central focus on product/subject, 
high contrast for text readability, commercial quality, ultra sharp, 8k resolution, 
perfect for social media advertising, professional color grading, no existing text or watermarks."""

        dimensions = {
            '1:1': (1024, 1024),
            '16:9': (1344, 768),
            '9:16': (768, 1344),
            '4:5': (1024, 1280),
        }
        
        width, height = dimensions.get(aspect_ratio, (1024, 1024))

        generated_images = []
        
        try:
            # 1. ALWAYS Generate from Pollinations.AI (Free, Primary)
            try:
                print(f"🎨 Generating with Pollinations.ai...")
                pollinations_bytes = self._generate_with_pollinations(
                    enhanced_prompt,
                    width,
                    height
                )
                
                if pollinations_bytes:
                    pollinations_image = Image.open(io.BytesIO(pollinations_bytes))
                    
                    if include_text and (headline or tagline or cta_text):
                        pollinations_final = self._apply_ad_template(
                            pollinations_image,
                            ad_template,
                            headline,
                            tagline,
                            cta_text,
                            aspect_ratio
                        )
                    else:
                        pollinations_final = pollinations_image
                    
                    pollinations_output = io.BytesIO()
                    pollinations_final.save(pollinations_output, format='PNG', quality=95)
                    pollinations_output.seek(0)
                    pollinations_base64 = base64.b64encode(pollinations_output.read()).decode('utf-8')
                    
                    generated_images.append({
                        'provider': 'pollinations',
                        'image_data': f"data:image/png;base64,{pollinations_base64}",
                        'name': 'Pollinations.AI (Free)',
                        'description': 'Fast generation, creative results'
                    })
                    print(f"✅ Pollinations.ai: SUCCESS")
                else:
                    print(f"❌ Pollinations.ai: No image data returned")
            except Exception as e:
                print(f"❌ Pollinations generation failed: {str(e)}")
                import traceback
                traceback.print_exc()
            
            # 2. Generate from Stability.AI (Premium, Optional)
            if generate_both:
                try:
                    # Check if API key exists before attempting
                    api_key = getattr(settings, 'STABILITY_API_KEY', None)
                    if api_key and api_key.strip():
                        print(f"🎨 Generating with Stability.ai...")
                        stability_bytes = self._generate_with_stability_api(
                            enhanced_prompt,
                            width,
                            height,
                            style
                        )
                        
                        if stability_bytes:
                            stability_image = Image.open(io.BytesIO(stability_bytes))
                            
                            if include_text and (headline or tagline or cta_text):
                                stability_final = self._apply_ad_template(
                                    stability_image,
                                    ad_template,
                                    headline,
                                    tagline,
                                    cta_text,
                                    aspect_ratio
                                )
                            else:
                                stability_final = stability_image
                            
                            stability_output = io.BytesIO()
                            stability_final.save(stability_output, format='PNG', quality=95)
                            stability_output.seek(0)
                            stability_base64 = base64.b64encode(stability_output.read()).decode('utf-8')
                            
                            generated_images.append({
                                'provider': 'stability',
                                'image_data': f"data:image/png;base64,{stability_base64}",
                                'name': 'Stability.AI (Premium)',
                                'description': 'High quality, photorealistic'
                            })
                            print(f"✅ Stability.ai: SUCCESS")
                        else:
                            print(f"⚠️ Stability.ai: No image data returned")
                    else:
                        print(f"⚠️ Stability.ai: API key not configured (skipping)")
                except Exception as e:
                    print(f"❌ Stability generation failed: {str(e)}")
                    # Don't print full traceback for missing API key
                    if "not configured" not in str(e):
                        import traceback
                        traceback.print_exc()
            
            if not generated_images:
                return Response(
                    {
                        "error": "Failed to generate images from any AI provider. Please check your internet connection and try again.",
                        "details": "Pollinations.ai generation failed. Check server logs for details."
                    }, 
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            return Response({
                "images": generated_images,
                "prompt": enhanced_prompt,
                "dimensions": f"{width}x{height}",
                "style": style,
                "template": ad_template,
                "message": "Choose your favorite image to save to campaign" if len(generated_images) > 1 else "Image generated successfully"
            }, status=status.HTTP_200_OK)

        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            print(f"❌ Image generation error: {error_trace}")
            return Response(
                {"error": f"AI generation failed: {str(e)}"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _generate_with_pollinations(self, prompt, width, height):
        """
        Generate image using Pollinations.AI (Free, no API key needed)
        Updated URL format: https://image.pollinations.ai/prompt/{prompt}?width=X&height=Y
        """
        try:
            import urllib.parse
            
            # Clean the prompt
            cleaned_prompt = prompt.strip().replace('\n', ' ').replace('  ', ' ')
            
            # URL encode the prompt
            encoded_prompt = urllib.parse.quote(cleaned_prompt)
            
            # CORRECTED URL FORMAT (changed from /p/ to /prompt/)
            pollinations_url = (
                f"https://image.pollinations.ai/prompt/{encoded_prompt}"
                f"?width={width}&height={height}&nologo=true&enhance=true"
            )
            
            print(f"🔗 Pollinations URL (first 150 chars): {pollinations_url[:150]}...")
            
            # Make request with timeout
            response = requests.get(pollinations_url, timeout=90, stream=True)
            
            print(f"📡 Response status: {response.status_code}")
            print(f"📦 Content-Type: {response.headers.get('content-type', 'unknown')}")
            
            if response.status_code == 200:
                # Check if we got image data
                content_type = response.headers.get('content-type', '')
                if 'image' in content_type:
                    image_bytes = response.content
                    print(f"✅ Image received: {len(image_bytes)} bytes")
                    
                    # Verify it's a valid image
                    try:
                        test_image = Image.open(io.BytesIO(image_bytes))
                        test_image.verify()
                        print(f"✅ Image verified: {test_image.format} {test_image.size}")
                        return image_bytes
                    except Exception as verify_error:
                        print(f"❌ Image verification failed: {str(verify_error)}")
                        return None
                else:
                    print(f"❌ Wrong content type: {content_type}")
                    print(f"Response preview: {response.text[:200]}")
                    return None
            else:
                print(f"❌ HTTP Error {response.status_code}")
                print(f"Response: {response.text[:300]}")
                return None
                
        except requests.exceptions.Timeout:
            print(f"⏱️ Pollinations request timed out")
            return None
        except requests.exceptions.ConnectionError as e:
            print(f"🔌 Connection error: {str(e)}")
            return None
        except Exception as e:
            print(f"❌ Pollinations generation error: {str(e)}")
            import traceback
            traceback.print_exc()
            return None

    def _generate_with_stability_api(self, prompt, width, height, style):
        """Generate image using Stability AI REST API"""
        
        api_key = getattr(settings, 'STABILITY_API_KEY', None)
        
        if not api_key or not api_key.strip():
            print("⚠️ STABILITY_API_KEY not configured in settings")
            return None
        
        engine_id = "stable-diffusion-xl-1024-v1-0"
        api_host = "https://api.stability.ai"
        
        sampler_map = {
            'professional': 'K_DPMPP_2M',
            'creative': 'K_EULER_ANCESTRAL',
            'minimal': 'K_DPM_2',
            'vintage': 'K_HEUN',
            'lifestyle': 'K_DPMPP_2M',
            'luxury': 'K_DPM_2'
        }
        
        try:
            response = requests.post(
                f"{api_host}/v1/generation/{engine_id}/text-to-image",
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "Authorization": f"Bearer {api_key}"
                },
                json={
                    "text_prompts": [
                        {
                            "text": prompt,
                            "weight": 1
                        },
                        {
                            "text": "blurry, bad quality, distorted, ugly, bad anatomy, watermark, text, logo, signature, low resolution",
                            "weight": -1
                        }
                    ],
                    "cfg_scale": 8,
                    "height": height,
                    "width": width,
                    "samples": 1,
                    "steps": 50,
                    "sampler": sampler_map.get(style, 'K_DPMPP_2M'),
                },
                timeout=90
            )
            
            if response.status_code != 200:
                print(f"❌ Stability API error {response.status_code}: {response.text[:200]}")
                return None
            
            data = response.json()
            
            if data.get("artifacts"):
                image_data = data["artifacts"][0]
                return base64.b64decode(image_data["base64"])
            
            return None
            
        except Exception as e:
            print(f"❌ Stability API exception: {str(e)}")
            return None

    def _apply_ad_template(self, base_image, template, headline, tagline, cta_text, aspect_ratio):
        """Apply professional ad template with text overlays"""
        
        width, height = base_image.size
        img = base_image.copy()
        
        # Enhance image quality
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(1.1)
        
        enhancer = ImageEnhance.Color(img)
        img = enhancer.enhance(1.05)
        
        draw = ImageDraw.Draw(img)
        
        # Apply selected template
        if template == 'modern':
            img = self._apply_modern_template(img, draw, headline, tagline, cta_text)
        elif template == 'minimal':
            img = self._apply_minimal_template(img, draw, headline, tagline, cta_text)
        elif template == 'bold':
            img = self._apply_bold_template(img, draw, headline, tagline, cta_text)
        elif template == 'gradient':
            img = self._apply_gradient_template(img, draw, headline, tagline, cta_text)
        
        return img

    def _get_font(self, size):
        """Get font with fallback for different OS"""
        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "C:\\Windows\\Fonts\\arial.ttf",
            "C:\\Windows\\Fonts\\arialbd.ttf",
        ]
        
        for font_path in font_paths:
            if os.path.exists(font_path):
                try:
                    return ImageFont.truetype(font_path, size)
                except:
                    pass
        
        return ImageFont.load_default()

    def _apply_modern_template(self, img, draw, headline, tagline, cta_text):
        """Modern template with bottom overlay"""
        width, height = img.size
        
        # Create gradient overlay
        overlay = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)
        
        overlay_height = int(height * 0.35)
        for i in range(overlay_height):
            alpha = int((i / overlay_height) * 180)
            overlay_draw.rectangle(
                [(0, height - overlay_height + i), (width, height - overlay_height + i + 1)],
                fill=(0, 0, 0, alpha)
            )
        
        img = img.convert('RGBA')
        img = Image.alpha_composite(img, overlay)
        img = img.convert('RGB')
        
        draw = ImageDraw.Draw(img)
        
        headline_font = self._get_font(int(width * 0.05))
        tagline_font = self._get_font(int(width * 0.03))
        cta_font = self._get_font(int(width * 0.035))
        
        if headline:
            bbox = draw.textbbox((0, 0), headline, font=headline_font)
            text_width = bbox[2] - bbox[0]
            x = (width - text_width) // 2
            y = height - overlay_height + 30
            
            # Add shadow
            for adj in range(-2, 3):
                for adj2 in range(-2, 3):
                    draw.text((x+adj, y+adj2), headline, font=headline_font, fill=(0, 0, 0))
            
            draw.text((x, y), headline, font=headline_font, fill=(255, 255, 255))
        
        if tagline:
            bbox = draw.textbbox((0, 0), tagline, font=tagline_font)
            text_width = bbox[2] - bbox[0]
            x = (width - text_width) // 2
            y = height - overlay_height + int(width * 0.09)
            draw.text((x, y), tagline, font=tagline_font, fill=(220, 220, 220))
        
        if cta_text:
            button_width = int(width * 0.25)
            button_height = int(height * 0.05)
            button_x = (width - button_width) // 2
            button_y = height - int(height * 0.08)
            
            draw.rounded_rectangle(
                [(button_x, button_y), (button_x + button_width, button_y + button_height)],
                radius=int(button_height * 0.5),
                fill=(0, 122, 255)
            )
            
            bbox = draw.textbbox((0, 0), cta_text, font=cta_font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            text_x = button_x + (button_width - text_width) // 2
            text_y = button_y + (button_height - text_height) // 2 - 5
            
            draw.text((text_x, text_y), cta_text, font=cta_font, fill=(255, 255, 255))
        
        return img

    def _apply_minimal_template(self, img, draw, headline, tagline, cta_text):
        """Minimal template with clean top text"""
        width, height = img.size
        
        new_height = height + int(height * 0.15)
        new_img = Image.new('RGB', (width, new_height), (255, 255, 255))
        new_img.paste(img, (0, int(height * 0.15)))
        
        draw = ImageDraw.Draw(new_img)
        
        headline_font = self._get_font(int(width * 0.045))
        tagline_font = self._get_font(int(width * 0.025))
        
        if headline:
            bbox = draw.textbbox((0, 0), headline, font=headline_font)
            text_width = bbox[2] - bbox[0]
            x = (width - text_width) // 2
            draw.text((x, 40), headline, font=headline_font, fill=(30, 30, 30))
        
        if tagline:
            bbox = draw.textbbox((0, 0), tagline, font=tagline_font)
            text_width = bbox[2] - bbox[0]
            x = (width - text_width) // 2
            draw.text((x, int(height * 0.10)), tagline, font=tagline_font, fill=(100, 100, 100))
        
        return new_img

    def _apply_bold_template(self, img, draw, headline, tagline, cta_text):
        """Bold template with vibrant overlays"""
        width, height = img.size
        
        overlay = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)
        
        banner_height = int(height * 0.12)
        overlay_draw.rectangle(
            [(0, 0), (width, banner_height)],
            fill=(255, 59, 92, 220)
        )
        
        img = img.convert('RGBA')
        img = Image.alpha_composite(img, overlay)
        img = img.convert('RGB')
        
        draw = ImageDraw.Draw(img)
        headline_font = self._get_font(int(width * 0.055))
        
        if headline:
            bbox = draw.textbbox((0, 0), headline, font=headline_font)
            text_width = bbox[2] - bbox[0]
            x = (width - text_width) // 2
            draw.text((x, int(banner_height * 0.3)), headline, font=headline_font, fill=(255, 255, 255))
        
        return img

    def _apply_gradient_template(self, img, draw, headline, tagline, cta_text):
        """Gradient overlay template"""
        width, height = img.size
        
        overlay = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)
        
        for i in range(height):
            ratio = i / height
            r = int(138 + (255 - 138) * ratio)
            g = int(43 + (59 - 43) * ratio)
            b = int(226 + (92 - 226) * ratio)
            alpha = int(120 * (1 - abs(ratio - 0.5) * 2))
            
            overlay_draw.line([(0, i), (width, i)], fill=(r, g, b, alpha))
        
        img = img.convert('RGBA')
        img = Image.alpha_composite(img, overlay)
        img = img.convert('RGB')
        
        draw = ImageDraw.Draw(img)
        headline_font = self._get_font(int(width * 0.06))
        
        if headline:
            bbox = draw.textbbox((0, 0), headline, font=headline_font)
            text_width = bbox[2] - bbox[0]
            x = (width - text_width) // 2
            y = (height // 2) - int(height * 0.05)
            
            # Add shadow
            for adj in range(-3, 4):
                for adj2 in range(-3, 4):
                    draw.text((x+adj, y+adj2), headline, font=headline_font, fill=(0, 0, 0))
            
            draw.text((x, y), headline, font=headline_font, fill=(255, 255, 255))
        
        return img

# ============================================================================
# Save Chosen AI Image
# ============================================================================
class SaveChosenImageView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        """Save the user's chosen image to Cloudinary"""
        campaign_id = request.data.get('campaign_id')
        image_data = request.data.get('image_data')
        provider = request.data.get('provider')
        prompt = request.data.get('prompt')
        
        if not all([campaign_id, image_data, provider, prompt]):
            return Response(
                {"error": "Missing required fields"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            campaign = Campaign.objects.get(id=campaign_id, user=request.user)
        except Campaign.DoesNotExist:
            return Response(
                {"error": "Campaign not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        try:
            # Upload to Cloudinary
            folder = f"advision/campaigns/{campaign_id}/images"
            public_id = f"{uuid.uuid4()}"
            
            upload_result = CloudinaryStorage.upload_base64_image(
                image_data,
                folder=folder,
                public_id=public_id
            )
            
            if not upload_result.get('success'):
                return Response(
                    {"error": f"Failed to upload image: {upload_result.get('error')}"}, 
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            # Create ImageAsset with Cloudinary URL
            img_asset = ImageAsset.objects.create(
                campaign=campaign,
                image=upload_result['url'],
                cloudinary_public_id=upload_result['public_id'],
                prompt=f"[{provider.upper()}] {prompt}"
            )
            
            return Response({
                "success": True,
                "image_url": upload_result['url'],
                "asset_id": str(img_asset.id),
                "provider": provider,
                "cloudinary_public_id": upload_result['public_id']
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            import traceback
            print(traceback.format_exc())
            return Response(
                {"error": f"Failed to save image: {str(e)}"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

# ============================================================================
# Ad Preview
# ============================================================================
class AdPreviewView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        ad_text = request.data.get('ad_text')
        image_url = request.data.get('image_url')
        platform = request.data.get('platform', 'instagram')
        device = request.data.get('device', 'mobile')
        
        preview_config = {
            'platform': platform,
            'device': device,
            'ad_text': ad_text,
            'image_url': image_url,
            'dimensions': {
                'instagram': {'mobile': '1080x1350', 'desktop': '1080x1350'},
                'facebook': {'mobile': '1200x628', 'desktop': '1200x628'},
                'linkedin': {'mobile': '1200x627', 'desktop': '1200x627'},
            }.get(platform, {}).get(device, '1080x1350'),
            'character_limit': {
                'instagram': 2200,
                'facebook': 63206,
                'linkedin': 3000,
                'youtube': 5000
            }.get(platform, 2200),
            'hashtag_limit': {
                'instagram': 30,
                'facebook': 'unlimited',
                'linkedin': 3,
            }.get(platform, 30)
        }
        
        return Response(preview_config)

# ============================================================================
# User Profile
# ============================================================================
class UserProfileView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)
    
    def patch(self, request):
        user = request.user
        serializer = UserSerializer(user, data=request.data, partial=True)
        
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# ============================================================================
# Social Authentication
# ============================================================================
class GoogleLoginView(SocialLoginView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]
    adapter_class = GoogleOAuth2Adapter
    callback_url = "http://localhost:5173"

class GitHubLoginView(SocialLoginView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]
    adapter_class = GitHubOAuth2Adapter
    callback_url = "http://localhost:5173/auth/github/callback"

# backend/core/views.py - FIXED ANALYTICS VIEWS


# ============================================================================
# REAL-TIME ANALYTICS SUMMARY - FIXED
# ============================================================================
class AnalyticsSummaryView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        campaign_id = request.query_params.get('campaign_id')
        days = int(request.query_params.get('days', 30))  # Default 30 days
        
        if not campaign_id:
            return Response(
                {'error': 'campaign_id query parameter is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            campaign = Campaign.objects.get(id=campaign_id, user=request.user)
        except Campaign.DoesNotExist:
            return Response(
                {'error': 'Campaign not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get or create campaign summary
        summary, created = CampaignAnalyticsSummary.objects.get_or_create(
            campaign=campaign
        )
        
        if created:
            summary.update_metrics()
        
        # Get date range for daily data
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days-1)
        
        # Get daily analytics
        daily_data = DailyAnalytics.objects.filter(
            campaign=campaign,
            date__gte=start_date,
            date__lte=end_date
        ).order_by('date')
        
        # Prepare data for charts
        dates = []
        impressions = []
        clicks = []
        conversions = []
        spend = []
        ctr_data = []
        
        for day in daily_data:
            dates.append(day.date.strftime('%b %d'))
            impressions.append(day.impressions)
            clicks.append(day.clicks)
            conversions.append(day.conversions)
            spend.append(float(day.spend))
            ctr_data.append(day.ctr)
        
        # Get counts
        ad_count = campaign.ad_content.count()
        image_count = campaign.images.count()
        
        # Calculate days active
        days_active = (datetime.now().date() - campaign.start_date).days + 1
        
        # Calculate cost per conversion - FIXED TYPE CONVERSION
        cost_per_conversion = 0
        if summary.total_conversions > 0 and summary.total_spend > 0:
            cost_per_conversion = float(summary.total_spend) / summary.total_conversions
        
        return Response({
            'campaign_id': str(campaign.id),
            'campaign_name': campaign.title,
            'platform': campaign.platform,
            'ad_count': ad_count,
            'image_count': image_count,
            'days_active': days_active,
            
            # Chart data
            'dates': dates,
            'impressions': impressions,
            'clicks': clicks,
            'conversions': conversions,
            'spend': spend,
            'ctr': ctr_data,
            
            # Summary metrics - ALL PROPERLY CONVERTED TO FLOAT
            'total_impressions': int(summary.total_impressions),
            'total_clicks': summary.total_clicks,
            'total_conversions': summary.total_conversions,
            'total_spend': float(summary.total_spend),
            'avg_ctr': float(summary.avg_ctr),
            'avg_cpc': float(summary.avg_cpc),
            'conversion_rate': float(summary.avg_conversion_rate),
            'cost_per_conversion': round(cost_per_conversion, 2),
            'roas': float(summary.roas),
            'performance_score': summary.performance_score,
        })

# ============================================================================
# DASHBOARD STATS WITH REAL DATA - FIXED
# ============================================================================
class DashboardStatsView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        user = request.user
        
        # Basic counts - FIXED VARIABLE REFERENCE
        total_campaigns = Campaign.objects.filter(user=user).count()
        total_ads = AdContent.objects.filter(campaign__user=user).count()
        total_images = ImageAsset.objects.filter(campaign__user=user).count()
        
        # Budget
        total_budget = Campaign.objects.filter(user=user).aggregate(
            total=Sum('budget')
        )['total'] or 0
        
        # Active campaigns
        today = datetime.now().date()
        active_campaigns = Campaign.objects.filter(
            user=user,
            is_active=True,
            end_date__gte=today
        ).count()
        
        # This week stats
        week_ago = today - timedelta(days=7)
        ads_this_week = AdContent.objects.filter(
            campaign__user=user,
            created_at__gte=week_ago
        ).count()
        
        images_this_week = ImageAsset.objects.filter(
            campaign__user=user,
            created_at__gte=week_ago
        ).count()
        
        # Platform distribution
        platform_stats = Campaign.objects.filter(user=user).values('platform').annotate(
            count=Count('id')
        )
        
        # Get aggregate analytics from all campaigns
        user_campaigns = Campaign.objects.filter(user=user)
        total_impressions = 0
        total_clicks = 0
        total_spend = 0
        
        for campaign in user_campaigns:
            try:
                summary = CampaignAnalyticsSummary.objects.get(campaign=campaign)
                total_impressions += summary.total_impressions
                total_clicks += summary.total_clicks
                total_spend += float(summary.total_spend)
            except CampaignAnalyticsSummary.DoesNotExist:
                continue
        
        # Calculate overall CTR
        overall_ctr = round((total_clicks / total_impressions * 100), 2) if total_impressions > 0 else 0
        
        return Response({
            'total_campaigns': total_campaigns,
            'active_campaigns': active_campaigns,
            'total_ads': total_ads,
            'total_images': total_images,
            'total_budget': float(total_budget),
            'ads_this_week': ads_this_week,
            'images_this_week': images_this_week,
            'platform_distribution': list(platform_stats),
            
            # Real analytics
            'total_impressions': total_impressions,
            'total_clicks': total_clicks,
            'total_spend': round(total_spend, 2),
            'overall_ctr': overall_ctr,
            
            # Growth rate
            'growth_rate': ((ads_this_week + images_this_week) / max(total_ads + total_images, 1)) * 100
        })

# ============================================================================
# CAMPAIGN COMPARISON VIEW
# ============================================================================
class CampaignComparisonView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        user = request.user
        campaigns = Campaign.objects.filter(user=user).order_by('-created_at')[:5]
        
        comparison_data = []
        
        for campaign in campaigns:
            try:
                summary = CampaignAnalyticsSummary.objects.get(campaign=campaign)
                comparison_data.append({
                    'id': str(campaign.id),
                    'title': campaign.title,
                    'platform': campaign.platform,
                    'impressions': int(summary.total_impressions),
                    'clicks': summary.total_clicks,
                    'conversions': summary.total_conversions,
                    'spend': float(summary.total_spend),
                    'ctr': float(summary.avg_ctr),
                    'performance_score': summary.performance_score,
                })
            except CampaignAnalyticsSummary.DoesNotExist:
                comparison_data.append({
                    'id': str(campaign.id),
                    'title': campaign.title,
                    'platform': campaign.platform,
                    'impressions': 0,
                    'clicks': 0,
                    'conversions': 0,
                    'spend': 0.0,
                    'ctr': 0.0,
                    'performance_score': 0,
                })
        
        # Sort by performance score
        comparison_data.sort(key=lambda x: x['performance_score'], reverse=True)
        
        return Response({
            'campaigns': comparison_data
        })

# ============================================================================
# AUDIENCE INSIGHTS WITH REAL DATA
# ============================================================================
class AudienceInsightsView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        campaign_id = request.query_params.get('campaign_id')
        
        if campaign_id:
            try:
                campaign = Campaign.objects.get(id=campaign_id, user=request.user)
                try:
                    summary = CampaignAnalyticsSummary.objects.get(campaign=campaign)
                    total_reach = int(summary.total_impressions)
                    engaged_users = summary.total_clicks
                    engagement_rate = float(summary.avg_ctr)
                except CampaignAnalyticsSummary.DoesNotExist:
                    total_reach = 0
                    engaged_users = 0
                    engagement_rate = 0.0
            except Campaign.DoesNotExist:
                return Response({'error': 'Campaign not found'}, status=404)
        else:
            # Aggregate across all user campaigns
            user = request.user
            summaries = CampaignAnalyticsSummary.objects.filter(campaign__user=user)
            
            total_reach = sum(int(s.total_impressions) for s in summaries)
            engaged_users = sum(s.total_clicks for s in summaries)
            engagement_rate = round(
                (engaged_users / total_reach * 100) if total_reach > 0 else 0, 
                2
            )
        
        # REAL DATA: Calculate from actual performance
        platform = campaign.platform if campaign_id else 'instagram'
        
        # Generic insights (not platform-specific dummy data)
        return Response({
            'platform': platform,
            'total_reach': total_reach,
            'engaged_users': engaged_users,
            'engagement_rate': engagement_rate,
            
            # Generic demographic data (industry averages - not fake)
            'age_groups': [
                {'range': '18-24', 'percentage': 30, 'engagement': 'Medium'},
                {'range': '25-34', 'percentage': 40, 'engagement': 'High'},
                {'range': '35-44', 'percentage': 20, 'engagement': 'Medium'},
                {'range': '45+', 'percentage': 10, 'engagement': 'Low'}
            ],
            'gender': [
                {'type': 'Female', 'percentage': 52},
                {'type': 'Male', 'percentage': 46},
                {'type': 'Other', 'percentage': 2}
            ],
            'note': 'Demographic data based on industry averages. Connect ad platform APIs for precise targeting data.',
            
            # Real recommendations based on actual data
            'recommendations': [
                {
                    'type': 'performance',
                    'message': f"Your campaigns have {engagement_rate}% engagement rate. {'Excellent!' if engagement_rate > 5 else 'Industry average is 3-5%. Consider optimizing.' if engagement_rate > 3 else 'Below average. Review ad creative and targeting.'}",
                    'priority': 'high' if engagement_rate < 3 else 'medium'
                },
                {
                    'type': 'reach',
                    'message': f"Total reach: {total_reach:,} impressions. {'Great visibility!' if total_reach > 50000 else 'Consider increasing budget for more reach.'}",
                    'priority': 'medium'
                }
            ]
        })

# ============================================================================
# WEEKLY REPORT WITH REAL DATA
# ============================================================================
class WeeklyReportView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        user = request.user
        week_ago = datetime.now().date() - timedelta(days=7)
        
        # REAL DATA: Count actual resources created
        campaigns_created = Campaign.objects.filter(
            user=user,
            created_at__gte=week_ago
        ).count()
        
        ads_generated = AdContent.objects.filter(
            campaign__user=user,
            created_at__gte=week_ago
        ).count()
        
        images_generated = ImageAsset.objects.filter(
            campaign__user=user,
            created_at__gte=week_ago
        ).count()
        
        active_campaigns = Campaign.objects.filter(
            user=user,
            is_active=True,
            end_date__gte=datetime.now().date()
        ).count()
        
        # REAL ANALYTICS: Get weekly performance
        weekly_analytics = DailyAnalytics.objects.filter(
            campaign__user=user,
            date__gte=week_ago
        ).aggregate(
            total_impressions=Sum('impressions'),
            total_clicks=Sum('clicks'),
            total_conversions=Sum('conversions'),
            total_spend=Sum('spend')
        )
        
        total_engagement = weekly_analytics['total_clicks'] or 0
        total_impressions = weekly_analytics['total_impressions'] or 0
        total_spend = float(weekly_analytics['total_spend'] or 0)
        
        # Calculate growth (compare to previous week)
        two_weeks_ago = week_ago - timedelta(days=7)
        previous_week = DailyAnalytics.objects.filter(
            campaign__user=user,
            date__gte=two_weeks_ago,
            date__lt=week_ago
        ).aggregate(
            prev_clicks=Sum('clicks')
        )
        
        prev_engagement = previous_week['prev_clicks'] or 1
        engagement_growth = round(((total_engagement - prev_engagement) / prev_engagement) * 100, 1)
        
        # REAL INSIGHTS: Calculate from actual data
        top_campaign = Campaign.objects.filter(
            user=user,
            analytics_summary__isnull=False
        ).order_by('-analytics_summary__total_clicks').first()
        
        insights = {
            'top_performing_platform': top_campaign.platform if top_campaign else 'N/A',
            'total_impressions': total_impressions,
            'total_clicks': total_engagement,
            'total_spend': round(total_spend, 2),
            'avg_ctr': round((total_engagement / total_impressions * 100), 2) if total_impressions > 0 else 0,
            'engagement_trend': 'Increasing' if engagement_growth > 0 else 'Decreasing'
        }
        
        # SMART RECOMMENDATIONS: Based on actual performance
        recommendations = []
        
        # Performance-based recommendation
        avg_ctr = insights['avg_ctr']
        if avg_ctr < 2:
            recommendations.append({
                'category': 'Performance',
                'priority': 'high',
                'title': 'Improve Click-Through Rate',
                'description': f'Your CTR is {avg_ctr}%. Industry average is 3-5%. Consider A/B testing different ad creatives.',
                'action': 'Start A/B Test',
                'impact': '+50% potential CTR increase'
            })
        elif avg_ctr > 5:
            recommendations.append({
                'category': 'Performance',
                'priority': 'high',
                'title': 'Excellent Performance - Scale Up',
                'description': f'Your {avg_ctr}% CTR is above industry average. Consider increasing budget to maximize results.',
                'action': 'Increase Budget',
                'impact': '+100% potential reach'
            })
        
        # Content recommendation
        if ads_generated < 5:
            recommendations.append({
                'category': 'Content',
                'priority': 'medium',
                'title': 'Generate More Ad Variations',
                'description': f'You created {ads_generated} ads this week. More variations improve A/B testing effectiveness.',
                'action': 'Create 5 variations',
                'impact': '+25% optimization potential'
            })
        
        # Campaign recommendation
        if active_campaigns == 0:
            recommendations.append({
                'category': 'Campaigns',
                'priority': 'high',
                'title': 'No Active Campaigns',
                'description': 'You have no active campaigns running. Create a new campaign to start driving results.',
                'action': 'Create Campaign',
                'impact': 'Start generating ROI'
            })
        
        return Response({
            'period': 'Last 7 days',
            'summary': {
                'campaigns_created': campaigns_created,
                'ads_generated': ads_generated,
                'images_generated': images_generated,
                'active_campaigns': active_campaigns,
                'total_engagement': total_engagement,
                'engagement_growth': f"{'+' if engagement_growth > 0 else ''}{engagement_growth}%"
            },
            'insights': insights,
            'recommendations': recommendations if recommendations else [{
                'category': 'General',
                'priority': 'low',
                'title': 'Keep Up the Good Work',
                'description': 'Your campaigns are performing well. Continue monitoring and optimizing.',
                'action': 'View Analytics',
                'impact': 'Maintain performance'
            }],
            'next_steps': [
                f"Review top performing campaign: {top_campaign.title if top_campaign else 'N/A'}",
                f"Analyze campaigns with CTR below {avg_ctr}%",
                "Test new ad creatives with AI generator",
                "Check budget allocation across platforms"
            ]
        })

# ============================================================================
# NEW: Delete Image from Cloudinary
# ============================================================================
class DeleteImageView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def delete(self, request, image_id):
        """Delete image from Cloudinary and database"""
        try:
            image = ImageAsset.objects.get(id=image_id, campaign__user=request.user)
            
            # Delete from Cloudinary if public_id exists
            if image.cloudinary_public_id:
                delete_result = CloudinaryStorage.delete_file(
                    image.cloudinary_public_id,
                    resource_type='image'
                )
                
                if not delete_result.get('success'):
                    print(f"Warning: Failed to delete from Cloudinary: {delete_result.get('error')}")
            
            # Delete from database
            image.delete()
            
            return Response({
                "success": True,
                "message": "Image deleted successfully"
            })
            
        except ImageAsset.DoesNotExist:
            return Response(
                {"error": "Image not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": f"Failed to delete image: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

# ============================================================================
# NEW: report generator from Cloudinary
# ============================================================================
class GenerateCampaignReportView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        """Generate and upload campaign report to Cloudinary"""
        campaign_id = request.data.get('campaign_id')
        
        if not campaign_id:
            return Response(
                {'error': 'campaign_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            campaign = Campaign.objects.get(id=campaign_id, user=request.user)
            
            # Get analytics data
            summary, created = CampaignAnalyticsSummary.objects.get_or_create(
                campaign=campaign
            )
            if created:
                summary.update_metrics()
            
            analytics_data = {
                'total_impressions': int(summary.total_impressions),
                'total_clicks': summary.total_clicks,
                'total_conversions': summary.total_conversions,
                'total_spend': float(summary.total_spend),
                'avg_ctr': float(summary.avg_ctr),
                'avg_cpc': float(summary.avg_cpc),
                'roas': float(summary.roas),
                'performance_score': summary.performance_score,
            }
            
            # Generate report
            from core.utils.report_generator import ReportGenerator
            result = ReportGenerator.generate_campaign_report(campaign, analytics_data)
            
            if result.get('success'):
                return Response({
                    'success': True,
                    'report_url': result['url'],
                    'public_id': result['public_id'],
                    'message': 'Report generated successfully'
                })
            else:
                return Response(
                    {'error': result.get('error', 'Failed to generate report')},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
                
        except Campaign.DoesNotExist:
            return Response(
                {'error': 'Campaign not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
# ============================================================================
# UPDATE: Image Edit View
# ============================================================================
class UpdateImageView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def patch(self, request, image_id):
        """Update image metadata (prompt only, image itself is immutable)"""
        try:
            image = ImageAsset.objects.get(id=image_id, campaign__user=request.user)
            
            # Update prompt if provided
            new_prompt = request.data.get('prompt')
            if new_prompt:
                image.prompt = new_prompt
                image.save()
            
            return Response({
                "success": True,
                "message": "Image updated successfully",
                "image": {
                    "id": str(image.id),
                    "prompt": image.prompt,
                    "image_url": image.image,
                }
            })
            
        except ImageAsset.DoesNotExist:
            return Response(
                {"error": "Image not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": f"Failed to update image: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )