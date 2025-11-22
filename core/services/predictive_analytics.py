# backend/core/services/predictive_analytics.py
from datetime import datetime, timedelta
from decimal import Decimal
import numpy as np
from sklearn.linear_model import LinearRegression
from core.models import Campaign, DailyAnalytics, PredictiveModel, Prediction

class PredictiveAnalyticsService:
    """Service for ML-based predictions"""
    
    @staticmethod
    def train_performance_model(campaign_id):
        """Train model to predict campaign performance"""
        campaign = Campaign.objects.get(id=campaign_id)
        
        # Get historical data
        analytics = DailyAnalytics.objects.filter(
            campaign=campaign
        ).order_by('date').values('date', 'impressions', 'clicks', 'conversions', 'spend')
        
        # FIXED: Proper indentation
        if len(analytics) < 7:
            return {
                'error': 'Insufficient data for training',
                'message': f'Need at least 7 days of data. Currently have {len(analytics)} days.',
                'required_days': 7,
                'current_days': len(analytics)
            }
        
        # Prepare data
        X = []  # Features: day number, impressions, spend
        y = []  # Target: conversions
        
        start_date = campaign.start_date
        for data in analytics:
            day_num = (data['date'] - start_date).days
            X.append([day_num, data['impressions'], float(data['spend'])])
            y.append(data['conversions'])
        
        X = np.array(X)
        y = np.array(y)
        
        # Train model
        model = LinearRegression()
        model.fit(X, y)
        
        # Calculate accuracy (R² score)
        accuracy = model.score(X, y)
        
        # Save model
        predictive_model, created = PredictiveModel.objects.update_or_create(
            user=campaign.user,
            model_type='performance',
            defaults={
                'accuracy': accuracy,
                'last_trained': datetime.now(),
                'training_samples': len(analytics),
                'model_data': {
                    'coefficients': model.coef_.tolist(),
                    'intercept': float(model.intercept_),
                    'campaign_id': str(campaign.id)
                }
            }
        )
        
        return {
            'success': True,
            'accuracy': accuracy,
            'samples': len(analytics)
        }
    
    @staticmethod
    def predict_next_week(campaign_id):
        """Predict next week's performance"""
        campaign = Campaign.objects.get(id=campaign_id)
        
        # Get model
        try:
            model_obj = PredictiveModel.objects.get(
                user=campaign.user,
                model_type='performance',
                is_active=True,
                model_data__campaign_id=str(campaign.id)
            )
        except PredictiveModel.DoesNotExist:
            # Train model first
            train_result = PredictiveAnalyticsService.train_performance_model(campaign_id)
            if 'error' in train_result:
                return train_result
            model_obj = PredictiveModel.objects.get(
                user=campaign.user,
                model_type='performance',
                is_active=True
            )
        
        # Reconstruct model
        model = LinearRegression()
        model.coef_ = np.array(model_obj.model_data['coefficients'])
        model.intercept_ = model_obj.model_data['intercept']
        
        # Get latest data
        latest_analytics = DailyAnalytics.objects.filter(
            campaign=campaign
        ).order_by('-date').first()
        
        if not latest_analytics:
            return {'error': 'No historical data'}
        
        # Predict next 7 days
        predictions = []
        start_date = campaign.start_date
        current_day = (datetime.now().date() - start_date).days
        
        for i in range(1, 8):
            day_num = current_day + i
            # Assume similar impressions and spend
            avg_impressions = latest_analytics.impressions
            avg_spend = float(latest_analytics.spend)
            
            X_pred = np.array([[day_num, avg_impressions, avg_spend]])
            predicted_conversions = int(model.predict(X_pred)[0])
            
            prediction_date = datetime.now().date() + timedelta(days=i)
            
            # Save prediction
            Prediction.objects.create(
                model=model_obj,
                campaign=campaign,
                prediction_date=prediction_date,
                predicted_value=predicted_conversions,
                confidence=model_obj.accuracy * 100,
                features_used={
                    'day_number': day_num,
                    'impressions': avg_impressions,
                    'spend': avg_spend
                }
            )
            
            predictions.append({
                'date': prediction_date.strftime('%Y-%m-%d'),
                'predicted_conversions': predicted_conversions,
                'confidence': round(model_obj.accuracy * 100, 2)
            })
        
        return {
            'success': True,
            'predictions': predictions,
            'model_accuracy': round(model_obj.accuracy * 100, 2)
        }
    
    @staticmethod
    def recommend_budget_allocation(user):
        """Recommend budget allocation across campaigns"""
        campaigns = Campaign.objects.filter(
            user=user,
            is_active=True
        )
        
        recommendations = []
        
        for campaign in campaigns:
            # Get performance data
            summary = campaign.analytics_summary
            
            if not summary:
                continue
            
            # Calculate ROI
            if summary.total_spend > 0:
                roi = (summary.total_conversions * 50) / float(summary.total_spend)
            else:
                roi = 0
            
            # Calculate efficiency score
            efficiency = summary.performance_score
            
            # Recommend budget change
            if roi > 3 and efficiency > 70:
                recommendation = 'increase'
                suggested_change = '+20%'
            elif roi < 1.5 or efficiency < 40:
                recommendation = 'decrease'
                suggested_change = '-20%'
            else:
                recommendation = 'maintain'
                suggested_change = '0%'
            
            recommendations.append({
                'campaign_id': str(campaign.id),
                'campaign_name': campaign.title,
                'current_budget': float(campaign.budget or 0),
                'recommendation': recommendation,
                'suggested_change': suggested_change,
                'roi': round(roi, 2),
                'efficiency_score': efficiency,
                'reason': f'ROI: {roi:.2f}x, Performance: {efficiency}/100'
            })
        
        return {
            'success': True,
            'recommendations': recommendations,
            'total_campaigns': len(recommendations)
        }