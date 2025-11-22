# backend/core/views_predictive.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from .services.predictive_analytics import PredictiveAnalyticsService
from .models import Campaign

class TrainPredictiveModelView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        """Train predictive model for a campaign"""
        campaign_id = request.data.get('campaign_id')
        
        if not campaign_id:
            return Response(
                {'error': 'campaign_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            campaign = Campaign.objects.get(id=campaign_id, user=request.user)
        except Campaign.DoesNotExist:
            return Response(
                {'error': 'Campaign not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        result = PredictiveAnalyticsService.train_performance_model(campaign_id)
        
        if 'error' in result:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(result)

class PredictNextWeekView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        """Predict next week's performance"""
        campaign_id = request.query_params.get('campaign_id')
        
        if not campaign_id:
            return Response(
                {'error': 'campaign_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            campaign = Campaign.objects.get(id=campaign_id, user=request.user)
        except Campaign.DoesNotExist:
            return Response(
                {'error': 'Campaign not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        result = PredictiveAnalyticsService.predict_next_week(campaign_id)
        
        if 'error' in result:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(result)

class BudgetRecommendationsView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        """Get AI budget allocation recommendations"""
        result = PredictiveAnalyticsService.recommend_budget_allocation(request.user)
        return Response(result)