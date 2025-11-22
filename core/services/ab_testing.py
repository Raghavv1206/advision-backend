# backend/core/services/ab_testing.py - COMPLETE FILE
import numpy as np
from scipy import stats
from datetime import datetime

class ABTestingService:
    """Service for A/B testing analysis and management"""
    
    @staticmethod
    def calculate_statistical_significance(variation_a, variation_b, metric='ctr'):
        """
        Calculate if there's a statistically significant difference between variations
        """
        
        if metric == 'ctr':
            clicks_a = variation_a.clicks
            impressions_a = variation_a.impressions
            clicks_b = variation_b.clicks
            impressions_b = variation_b.impressions
            
            if impressions_a == 0 or impressions_b == 0:
                return {
                    'significant': False,
                    'p_value': 1.0,
                    'winner': None,
                    'confidence': 0,
                    'metric_a': 0,
                    'metric_b': 0,
                    'improvement': 0
                }
            
            # Create contingency table
            observed = np.array([
                [clicks_a, impressions_a - clicks_a],
                [clicks_b, impressions_b - clicks_b]
            ])
            
            # Perform chi-square test
            chi2, p_value, dof, expected = stats.chi2_contingency(observed)
            
            is_significant = p_value < 0.05
            
            ctr_a = variation_a.ctr
            ctr_b = variation_b.ctr
            
            winner = None
            if is_significant:
                winner = 'A' if ctr_a > ctr_b else 'B'
            
            improvement = 0
            if max(ctr_a, ctr_b) > 0:
                improvement = abs(ctr_a - ctr_b) / max(ctr_a, ctr_b) * 100
            
            return {
                'significant': is_significant,
                'p_value': float(p_value),
                'winner': winner,
                'confidence': (1 - p_value) * 100,
                'metric_a': ctr_a,
                'metric_b': ctr_b,
                'improvement': improvement
            }
        
        elif metric == 'conversion_rate':
            conversions_a = variation_a.conversions
            clicks_a = variation_a.clicks
            conversions_b = variation_b.conversions
            clicks_b = variation_b.clicks
            
            if clicks_a == 0 or clicks_b == 0:
                return {
                    'significant': False,
                    'p_value': 1.0,
                    'winner': None,
                    'confidence': 0,
                    'metric_a': 0,
                    'metric_b': 0,
                    'improvement': 0
                }
            
            observed = np.array([
                [conversions_a, clicks_a - conversions_a],
                [conversions_b, clicks_b - conversions_b]
            ])
            
            chi2, p_value, dof, expected = stats.chi2_contingency(observed)
            is_significant = p_value < 0.05
            
            conv_rate_a = variation_a.conversion_rate
            conv_rate_b = variation_b.conversion_rate
            
            winner = None
            if is_significant:
                winner = 'A' if conv_rate_a > conv_rate_b else 'B'
            
            improvement = 0
            if max(conv_rate_a, conv_rate_b) > 0:
                improvement = abs(conv_rate_a - conv_rate_b) / max(conv_rate_a, conv_rate_b) * 100
            
            return {
                'significant': is_significant,
                'p_value': float(p_value),
                'winner': winner,
                'confidence': (1 - p_value) * 100,
                'metric_a': conv_rate_a,
                'metric_b': conv_rate_b,
                'improvement': improvement
            }
        
        return {'significant': False, 'p_value': 1.0, 'winner': None}
    
    @staticmethod
    def check_minimum_sample_size(ab_test):
        """Check if test has reached minimum sample size"""
        variations = ab_test.variations.all()
        
        for variation in variations:
            if variation.impressions < ab_test.min_sample_size:
                return False
        
        return True
    
    @staticmethod
    def analyze_test(ab_test):
        """Analyze A/B test and determine winner"""
        if ab_test.status != 'running':
            return {'error': 'Test is not running'}
        
        if not ABTestingService.check_minimum_sample_size(ab_test):
            return {
                'status': 'insufficient_data',
                'message': f'Need at least {ab_test.min_sample_size} impressions per variation'
            }
        
        variations = list(ab_test.variations.all().order_by('name'))
        
        if len(variations) < 2:
            return {'error': 'Need at least 2 variations'}
        
        results = []
        
        for i in range(len(variations)):
            for j in range(i + 1, len(variations)):
                var_a = variations[i]
                var_b = variations[j]
                
                result = ABTestingService.calculate_statistical_significance(
                    var_a, var_b, ab_test.success_metric
                )
                
                results.append({
                    'variation_a': var_a.name,
                    'variation_b': var_b.name,
                    'result': result
                })
        
        if results and results[0]['result']['significant']:
            winner_name = results[0]['result']['winner']
            ab_test.winner = winner_name
            ab_test.is_significant = True
            ab_test.p_value = results[0]['result']['p_value']
            ab_test.save()
            
            return {
                'status': 'completed',
                'winner': winner_name,
                'significant': True,
                'details': results[0]['result']
            }
        else:
            return {
                'status': 'inconclusive',
                'message': 'No statistically significant winner yet',
                'details': results
            }
    
    @staticmethod
    def get_recommendation(ab_test):
        """Get AI-powered recommendation for the test"""
        analysis = ABTestingService.analyze_test(ab_test)
        
        recommendations = []
        
        if analysis.get('status') == 'insufficient_data':
            recommendations.append({
                'type': 'wait',
                'message': 'Continue running the test until minimum sample size is reached',
                'priority': 'high'
            })
        
        elif analysis.get('status') == 'completed' and analysis.get('significant'):
            winner = analysis['winner']
            improvement = analysis['details'].get('improvement', 0)
            
            recommendations.append({
                'type': 'action',
                'message': f'Variation {winner} is the clear winner with {improvement:.1f}% improvement. Implement this variation.',
                'priority': 'high'
            })
        
        elif analysis.get('status') == 'inconclusive':
            recommendations.append({
                'type': 'extend',
                'message': 'No clear winner yet. Consider running the test longer or increasing traffic.',
                'priority': 'medium'
            })
        
        return recommendations