from django.utils import timezone
from datetime import timedelta
from django.db.models import Count, Sum, Q, Case, When, IntegerField
from projects.models import  VideoAnalytics
from projects.models import Like, Review, ViewHistory, Video
from users.models import Follow
from users.services.follow_services import FollowService

class FollowerAnalyticsService:
    def __init__(self):
        self.follow_service = FollowService()

    def get_follower_analytics(self, user):
        """Get complete follower analytics for a user"""
        
        # Get both growth data and 30-day total in one query
        growth_stats = self.get_growth_data(user)
        
        basic_stats = {
            'new_followers_30d': growth_stats['new_followers_30d']
        }
        
        # Engagement stats
        #engagement_stats = self.get_follower_engagement(user)
        
        follower_percentages = self.get_engagement_breakdown(user)
        
        return {
            **basic_stats,
            'growth_data': growth_stats['growth_data'],
            #**engagement_stats,
            **follower_percentages
        }
    
    @staticmethod
    def get_growth_data(user):
        """Get follower growth over time and 30-day total"""
        thirty_days_ago = timezone.now() - timedelta(days=30)
        
        # Single query to get both daily growth and 30-day total
        growth_data = list(Follow.objects.filter(
            following=user,
            created__gte=thirty_days_ago
        ).values('created__date').annotate(
            new_followers=Count('id')
        ).order_by('created__date'))
        
        # Calculate 30-day total from the same data
        new_followers_30d = sum(day['new_followers'] for day in growth_data)
        
        return {
            'growth_data': growth_data,
            'new_followers_30d': new_followers_30d
        }
    
    @staticmethod
    def get_follower_engagement(user):
        """Get engagement metrics from followers"""
        # Get follower IDs
        follower_ids = Follow.objects.filter(
            following=user
        ).values_list('user_id', flat=True)
        
        return {
            'follower_likes': Like.objects.filter(
                user_id__in=follower_ids,
                video__uploader=user,
                is_like=True
            ).count(),
            
            'follower_dislikes': Like.objects.filter(
                user_id__in=follower_ids,
                video__uploader=user,
                is_like=False
            ).count(),
            
            'follower_comments': Review.objects.filter(
                user_id__in=follower_ids,
                video__uploader=user
            ).count(),
            
            'follower_views': ViewHistory.objects.filter(
                user_id__in=follower_ids,
                video__uploader=user
            ).count()
        }

    def get_engagement_breakdown(self, user):
        """Get percentage breakdown and actual numbers for follower vs non-follower engagement"""
        # Get follower IDs (exclude the user) - cache this
        follower_ids = Follow.objects.filter(
            following=user
        ).exclude(
            user=user
        ).values_list('user_id', flat=True)
        
        # Get likes/dislikes in one query
        likes_stats = Like.objects.filter(
            video__uploader=user
        ).exclude(
            user=user
        ).aggregate(
            total_likes=Count('id', filter=Q(is_like=True)),
            total_dislikes=Count('id', filter=Q(is_like=False)),
            follower_likes=Count('id', filter=Q(is_like=True, user_id__in=follower_ids)),
            follower_dislikes=Count('id', filter=Q(is_like=False, user_id__in=follower_ids))
        )
        
        # Get comments in one query
        comments_stats = Review.objects.filter(
            video__uploader=user
        ).exclude(
            user=user
        ).aggregate(
            total_comments=Count('id'),
            follower_comments=Count('id', filter=Q(user_id__in=follower_ids))
        )
        
        # Get views in one query
        views_stats = {
            'total_views': Video.objects.filter(uploader=user).aggregate(
                total_views=Sum('views')
            )['total_views'] or 0,
            'follower_views': ViewHistory.objects.filter(
                video__uploader=user,
                user_id__in=follower_ids
            ).exclude(user=user).count()
        }
        
        # Format the response (same structure as before)
        return {
            'engagement_breakdown': {
                'likes': self._format_metric_breakdown(
                    likes_stats['total_likes'],
                    likes_stats['follower_likes']
                ),
                'dislikes': self._format_metric_breakdown(
                    likes_stats['total_dislikes'],
                    likes_stats['follower_dislikes']
                ),
                'comments': self._format_metric_breakdown(
                    comments_stats['total_comments'],
                    comments_stats['follower_comments']
                ),
                'views': self._format_metric_breakdown(
                    views_stats['total_views'],
                    views_stats['follower_views']
                )
            }
        }

    def _format_metric_breakdown(self, total, follower_count):
        """Helper to format metric breakdown with consistent structure"""
        follower_percentage = (follower_count / total * 100) if total else 0
        return {
            'total': total,
            'follower_count': follower_count,
            'non_follower_count': total - follower_count,
            'follower_percentage': follower_percentage,
            'non_follower_percentage': 100 - follower_percentage
        }
