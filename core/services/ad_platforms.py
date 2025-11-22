# backend/core/services/ad_platforms.py - FIXED IMPORTS
"""
Ad Platform Integration Services
Handles Google Ads, Facebook Ads API integration using User's own API keys
"""

from datetime import datetime, timedelta
from django.conf import settings
from decimal import Decimal

# ============================================================================
# GOOGLE ADS INTEGRATION
# ============================================================================
class GoogleAdsService:
    """Service for interacting with Google Ads API using user's credentials"""
    
    def __init__(self, user_api_key=None, connection=None):
        """
        Initialize with either UserAPIKey (preferred) or old AdPlatformConnection
        """
        self.user_api_key = user_api_key
        self.connection = connection
        self.client = None
        self.account_id = None
        self.setup_client()
    
    def setup_client(self):
        """Initialize Google Ads client"""
        try:
            from google.ads.googleads.client import GoogleAdsClient
            
            if self.user_api_key:
                # NEW: Use user's encrypted API key
                credentials = {
                    "developer_token": self.user_api_key.developer_token or getattr(settings, 'GOOGLE_ADS_DEVELOPER_TOKEN', ''),
                    "client_id": getattr(settings, 'GOOGLE_ADS_CLIENT_ID', ''),
                    "client_secret": getattr(settings, 'GOOGLE_ADS_CLIENT_SECRET', ''),
                    "refresh_token": self.user_api_key.decrypt_key(),
                    "login_customer_id": self.user_api_key.account_id,
                }
                self.account_id = self.user_api_key.account_id
            elif self.connection:
                # OLD: Fallback to connection (deprecated)
                credentials = {
                    "developer_token": getattr(settings, 'GOOGLE_ADS_DEVELOPER_TOKEN', ''),
                    "client_id": getattr(settings, 'GOOGLE_ADS_CLIENT_ID', ''),
                    "client_secret": getattr(settings, 'GOOGLE_ADS_CLIENT_SECRET', ''),
                    "refresh_token": self.connection.refresh_token,
                    "login_customer_id": self.connection.account_id,
                }
                self.account_id = self.connection.account_id
            else:
                raise Exception("No credentials provided")
            
            self.client = GoogleAdsClient.load_from_dict(credentials)
            return True
        except ImportError:
            print("Google Ads library not installed. Run: pip install google-ads")
            return False
        except Exception as e:
            print(f"Google Ads setup error: {e}")
            return False
    
    @staticmethod
    def from_user(user):
        """Create service from user's stored API key"""
        from core.models import UserAPIKey
        
        try:
            api_key = UserAPIKey.objects.get(
                user=user,
                api_type='google_ads',
                is_active=True,
                verification_status='verified'
            )
            return GoogleAdsService(user_api_key=api_key)
        except UserAPIKey.DoesNotExist:
            raise Exception('No verified Google Ads API key found. Please add one in API Keys settings.')
    
    def get_campaigns(self):
        """Fetch all campaigns from Google Ads"""
        if not self.client:
            return []
        
        try:
            ga_service = self.client.get_service("GoogleAdsService")
            customer_id = self.account_id.replace('-', '')
            
            query = """
                SELECT
                    campaign.id,
                    campaign.name,
                    campaign.status,
                    metrics.impressions,
                    metrics.clicks,
                    metrics.conversions,
                    metrics.cost_micros
                FROM campaign
                WHERE segments.date DURING LAST_30_DAYS
            """
            
            response = ga_service.search_stream(customer_id=customer_id, query=query)
            
            campaigns = []
            for batch in response:
                for row in batch.results:
                    campaigns.append({
                        'external_id': str(row.campaign.id),
                        'name': row.campaign.name,
                        'status': row.campaign.status.name,
                        'impressions': row.metrics.impressions,
                        'clicks': row.metrics.clicks,
                        'conversions': int(row.metrics.conversions),
                        'spend': Decimal(row.metrics.cost_micros / 1_000_000),
                    })
            
            return campaigns
        except Exception as e:
            print(f"Error fetching Google Ads campaigns: {e}")
            return []
    
    def get_campaign_metrics(self, campaign_id, start_date, end_date):
        """Get detailed metrics for a specific campaign"""
        if not self.client:
            return []
        
        try:
            ga_service = self.client.get_service("GoogleAdsService")
            customer_id = self.account_id.replace('-', '')
            
            query = f"""
                SELECT
                    segments.date,
                    metrics.impressions,
                    metrics.clicks,
                    metrics.conversions,
                    metrics.cost_micros,
                    metrics.ctr,
                    metrics.average_cpc
                FROM campaign
                WHERE campaign.id = {campaign_id}
                    AND segments.date BETWEEN '{start_date}' AND '{end_date}'
                ORDER BY segments.date
            """
            
            response = ga_service.search_stream(customer_id=customer_id, query=query)
            
            metrics = []
            for batch in response:
                for row in batch.results:
                    metrics.append({
                        'date': str(row.segments.date),
                        'impressions': row.metrics.impressions,
                        'clicks': row.metrics.clicks,
                        'conversions': int(row.metrics.conversions),
                        'spend': Decimal(row.metrics.cost_micros / 1_000_000),
                        'ctr': float(row.metrics.ctr),
                        'avg_cpc': Decimal(row.metrics.average_cpc / 1_000_000) if row.metrics.average_cpc > 0 else Decimal(0),
                    })
            
            return metrics
        except Exception as e:
            print(f"Error fetching campaign metrics: {e}")
            return []
    
    def create_campaign(self, campaign_data):
        """Create a new campaign in Google Ads"""
        if not self.client:
            return {'success': False, 'error': 'Client not initialized'}
        
        try:
            campaign_service = self.client.get_service("CampaignService")
            campaign_operation = self.client.get_type("CampaignOperation")
            
            campaign = campaign_operation.create
            campaign.name = campaign_data['name']
            campaign.advertising_channel_type = self.client.enums.AdvertisingChannelTypeEnum.SEARCH
            campaign.status = self.client.enums.CampaignStatusEnum.PAUSED
            
            if 'budget_resource_name' in campaign_data:
                campaign.campaign_budget = campaign_data['budget_resource_name']
            
            customer_id = self.account_id.replace('-', '')
            response = campaign_service.mutate_campaigns(
                customer_id=customer_id,
                operations=[campaign_operation]
            )
            
            return {
                'success': True,
                'campaign_id': response.results[0].resource_name.split('/')[-1]
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

# ============================================================================
# FACEBOOK ADS INTEGRATION
# ============================================================================
class FacebookAdsService:
    """Service for interacting with Facebook Ads API using user's credentials"""
    
    def __init__(self, user_api_key=None, connection=None):
        """Initialize with either UserAPIKey (preferred) or old AdPlatformConnection"""
        self.user_api_key = user_api_key
        self.connection = connection
        self.account = None
        self.access_token = None
        self.account_id = None
        self.setup_client()
    
    def setup_client(self):
        """Initialize Facebook Ads client"""
        try:
            from facebook_business.api import FacebookAdsApi
            from facebook_business.adobjects.adaccount import AdAccount
            
            if self.user_api_key:
                # NEW: Use user's encrypted API key
                app_id = getattr(settings, 'FACEBOOK_APP_ID', '')
                app_secret = self.user_api_key.decrypt_secret() if self.user_api_key.encrypted_secret else getattr(settings, 'FACEBOOK_APP_SECRET', '')
                self.access_token = self.user_api_key.decrypt_key()
                self.account_id = self.user_api_key.account_id
            elif self.connection:
                # OLD: Fallback
                app_id = getattr(settings, 'FACEBOOK_APP_ID', '')
                app_secret = getattr(settings, 'FACEBOOK_APP_SECRET', '')
                self.access_token = self.connection.access_token
                self.account_id = self.connection.account_id
            else:
                raise Exception("No credentials provided")
            
            FacebookAdsApi.init(
                app_id=app_id,
                app_secret=app_secret,
                access_token=self.access_token
            )
            
            # Format account ID
            if not self.account_id.startswith('act_'):
                self.account_id = f"act_{self.account_id}"
            
            self.account = AdAccount(self.account_id)
            return True
        except ImportError:
            print("Facebook Business SDK not installed. Run: pip install facebook-business")
            return False
        except Exception as e:
            print(f"Facebook Ads setup error: {e}")
            return False
    
    @staticmethod
    def from_user(user):
        """Create service from user's stored API key"""
        from core.models import UserAPIKey
        
        try:
            api_key = UserAPIKey.objects.get(
                user=user,
                api_type='facebook_ads',
                is_active=True,
                verification_status='verified'
            )
            return FacebookAdsService(user_api_key=api_key)
        except UserAPIKey.DoesNotExist:
            raise Exception('No verified Facebook Ads API key found. Please add one in API Keys settings.')
    
    def get_campaigns(self):
        """Fetch all campaigns from Facebook Ads"""
        if not self.account:
            return []
        
        try:
            from facebook_business.adobjects.campaign import Campaign as FBCampaign
            
            fields = [
                FBCampaign.Field.id,
                FBCampaign.Field.name,
                FBCampaign.Field.status,
            ]
            
            campaigns = self.account.get_campaigns(fields=fields)
            
            result = []
            for campaign in campaigns:
                try:
                    insights = campaign.get_insights(
                        fields=[
                            'impressions',
                            'clicks',
                            'actions',
                            'spend',
                        ],
                        params={
                            'time_range': {'since': '30 days ago', 'until': 'today'},
                        }
                    )
                    
                    insight = insights[0] if insights else {}
                    
                    # Extract conversions from actions
                    conversions = 0
                    actions = insight.get('actions', [])
                    for action in actions:
                        if action.get('action_type') in ['purchase', 'complete_registration', 'lead']:
                            conversions += int(action.get('value', 0))
                    
                    result.append({
                        'external_id': campaign['id'],
                        'name': campaign['name'],
                        'status': campaign['status'],
                        'impressions': int(insight.get('impressions', 0)),
                        'clicks': int(insight.get('clicks', 0)),
                        'conversions': conversions,
                        'spend': Decimal(insight.get('spend', 0)),
                    })
                except Exception as e:
                    print(f"Error fetching insights for campaign {campaign['id']}: {e}")
                    continue
            
            return result
        except Exception as e:
            print(f"Error fetching Facebook campaigns: {e}")
            return []
    
    def get_campaign_metrics(self, campaign_id, start_date, end_date):
        """Get detailed metrics for a specific campaign"""
        if not self.account:
            return []
        
        try:
            from facebook_business.adobjects.campaign import Campaign as FBCampaign
            
            campaign = FBCampaign(campaign_id)
            
            insights = campaign.get_insights(
                fields=[
                    'date_start',
                    'impressions',
                    'clicks',
                    'actions',
                    'spend',
                    'ctr',
                    'cpc',
                ],
                params={
                    'time_range': {
                        'since': start_date,
                        'until': end_date
                    },
                    'time_increment': 1,
                }
            )
            
            metrics = []
            for insight in insights:
                # Extract conversions
                conversions = 0
                actions = insight.get('actions', [])
                for action in actions:
                    if action.get('action_type') in ['purchase', 'complete_registration', 'lead']:
                        conversions += int(action.get('value', 0))
                
                metrics.append({
                    'date': insight['date_start'],
                    'impressions': int(insight.get('impressions', 0)),
                    'clicks': int(insight.get('clicks', 0)),
                    'conversions': conversions,
                    'spend': Decimal(insight.get('spend', 0)),
                    'ctr': float(insight.get('ctr', 0)),
                    'avg_cpc': Decimal(insight.get('cpc', 0)),
                })
            
            return metrics
        except Exception as e:
            print(f"Error fetching campaign metrics: {e}")
            return []
    
    def create_campaign(self, campaign_data):
        """Create a new campaign in Facebook Ads"""
        if not self.account:
            return {'success': False, 'error': 'Account not initialized'}
        
        try:
            from facebook_business.adobjects.campaign import Campaign as FBCampaign
            
            campaign = FBCampaign(parent_id=self.account.get_id_assured())
            
            campaign.update({
                FBCampaign.Field.name: campaign_data['name'],
                FBCampaign.Field.objective: campaign_data.get('objective', 'OUTCOME_TRAFFIC'),
                FBCampaign.Field.status: 'PAUSED',
                FBCampaign.Field.special_ad_categories: [],
            })
            
            campaign.remote_create()
            
            return {
                'success': True,
                'campaign_id': campaign['id']
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

# ============================================================================
# UNIFIED SYNC SERVICE
# ============================================================================
class AdPlatformSyncService:
    """Orchestrate syncing from multiple ad platforms using user's API keys"""
    
    @staticmethod
    def sync_user_campaigns(user):
        """
        NEW: Sync campaigns from all user's verified API keys
        This replaces the old connection-based sync
        """
        from core.models import UserAPIKey, Campaign, DailyAnalytics, CampaignAnalyticsSummary
        
        # Get all verified API keys for user
        api_keys = UserAPIKey.objects.filter(
            user=user,
            is_active=True,
            verification_status='verified'
        )
        
        results = []
        
        for api_key in api_keys:
            try:
                # Get appropriate service based on platform
                if api_key.api_type == 'google_ads':
                    service = GoogleAdsService(user_api_key=api_key)
                    platform_name = 'Google Ads'
                elif api_key.api_type == 'facebook_ads':
                    service = FacebookAdsService(user_api_key=api_key)
                    platform_name = 'Facebook Ads'
                else:
                    continue
                
                # Fetch campaigns from platform
                external_campaigns = service.get_campaigns()
                
                synced_count = 0
                for ext_campaign in external_campaigns:
                    # Find or create local campaign
                    campaign, created = Campaign.objects.get_or_create(
                        user=user,
                        title=ext_campaign['name'],
                        defaults={
                            'platform': api_key.api_type.split('_')[0],
                            'description': f"Synced from {platform_name}",
                            'start_date': datetime.now().date(),
                            'end_date': datetime.now().date() + timedelta(days=30),
                        }
                    )
                    
                    # Fetch detailed metrics
                    end_date = datetime.now().date()
                    start_date = end_date - timedelta(days=30)
                    
                    daily_metrics = service.get_campaign_metrics(
                        ext_campaign['external_id'],
                        start_date.strftime('%Y-%m-%d'),
                        end_date.strftime('%Y-%m-%d')
                    )
                    
                    # Update daily analytics
                    for metric in daily_metrics:
                        DailyAnalytics.objects.update_or_create(
                            campaign=campaign,
                            date=metric['date'],
                            defaults={
                                'impressions': metric['impressions'],
                                'clicks': metric['clicks'],
                                'conversions': metric['conversions'],
                                'spend': metric['spend'],
                            }
                        )
                    
                    # Update campaign summary
                    summary, _ = CampaignAnalyticsSummary.objects.get_or_create(campaign=campaign)
                    summary.update_metrics()
                    
                    synced_count += 1
                
                results.append({
                    'platform': platform_name,
                    'api_key_name': api_key.api_name,
                    'success': True,
                    'synced_campaigns': synced_count
                })
                
            except Exception as e:
                results.append({
                    'platform': api_key.get_api_type_display(),
                    'api_key_name': api_key.api_name,
                    'success': False,
                    'error': str(e)
                })
        
        return results
    
    @staticmethod
    def sync_connection(connection):
        """
        DEPRECATED: Old method for backward compatibility
        Use sync_user_campaigns instead
        """
        from core.models import SyncedCampaign, DailyAnalytics
        
        service = None
        
        if connection.platform == 'google_ads':
            service = GoogleAdsService(connection=connection)
        elif connection.platform == 'facebook_ads':
            service = FacebookAdsService(connection=connection)
        else:
            return {'success': False, 'error': 'Unsupported platform'}
        
        try:
            campaigns = service.get_campaigns()
            
            if not campaigns:
                return {'success': False, 'error': 'No campaigns found or API error'}
            
            synced_count = 0
            for campaign_data in campaigns:
                synced_campaign, created = SyncedCampaign.objects.update_or_create(
                    connection=connection,
                    external_id=campaign_data['external_id'],
                    defaults={
                        'external_name': campaign_data['name'],
                        'external_status': campaign_data['status'],
                        'spend': campaign_data['spend'],
                        'impressions': campaign_data['impressions'],
                        'clicks': campaign_data['clicks'],
                        'conversions': campaign_data['conversions'],
                    }
                )
                
                if synced_campaign.local_campaign:
                    end_date = datetime.now().date()
                    start_date = end_date - timedelta(days=30)
                    
                    daily_metrics = service.get_campaign_metrics(
                        campaign_data['external_id'],
                        start_date.strftime('%Y-%m-%d'),
                        end_date.strftime('%Y-%m-%d')
                    )
                    
                    for metric in daily_metrics:
                        DailyAnalytics.objects.update_or_create(
                            campaign=synced_campaign.local_campaign,
                            date=metric['date'],
                            defaults={
                                'impressions': metric['impressions'],
                                'clicks': metric['clicks'],
                                'conversions': metric['conversions'],
                                'spend': metric['spend'],
                            }
                        )
                    
                    if hasattr(synced_campaign.local_campaign, 'analytics_summary'):
                        synced_campaign.local_campaign.analytics_summary.update_metrics()
                
                synced_count += 1
            
            connection.status = 'connected'
            connection.last_sync = datetime.now()
            connection.error_message = ''
            connection.save()
            
            return {
                'success': True,
                'synced_campaigns': synced_count,
                'message': f'Successfully synced {synced_count} campaigns'
            }
            
        except Exception as e:
            connection.status = 'error'
            connection.error_message = str(e)
            connection.save()
            
            return {
                'success': False,
                'error': str(e)
            }