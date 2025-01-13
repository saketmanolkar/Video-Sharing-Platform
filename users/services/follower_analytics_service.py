from django.utils import timezone
from datetime import timedelta
from django.db.models import Count, Sum
from projects.models import  VideoAnalytics
from projects.models import Like, Review, ViewHistory, Video
from users.models import Follow
from users.services.follow_services import FollowService

class FollowerAnalyticsService:
    def __init__(self):
        self.follow_service = FollowService()

    def get_follower_analytics(self, user):
        """Get complete follower analytics for a user"""
        
        # Use existing FollowService for basic stats
        basic_stats = self.follow_service.get_follower_stats(user.profile)
        
        # Rename the key to match what we use elsewhere
        basic_stats['total_followers'] = basic_stats.pop('followers_count')  # Fix the key name
        
        # Add 30-day new followers
        thirty_days_ago = timezone.now() - timedelta(days=30)
        basic_stats['new_followers_30d'] = Follow.objects.filter(
            following=user,
            created__gte=thirty_days_ago
        ).count()
        
        # Growth data
        growth_data = self.get_growth_data(user)
        
        # Engagement stats (now includes both likes and dislikes)
        engagement_stats = self.get_follower_engagement(user)
        
        # Get engagement percentages
        follower_percentages = self.get_engagement_breakdown(user)
        
        return {
            **basic_stats,
            'growth_data': growth_data,
            **engagement_stats,  # This will now include follower_dislikes
            **follower_percentages
        }
    
    @staticmethod
    def get_growth_data(user):
        """Get follower growth over time"""
        return list(Follow.objects.filter(
            following=user
        ).values('created__date').annotate(
            new_followers=Count('id')
        ).order_by('created__date'))
    
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
        # Get follower IDs (exclude the user)
        follower_ids = Follow.objects.filter(
            following=user
        ).exclude(
            user=user  # Exclude the user's own follow
        ).values_list('user_id', flat=True)
        
        # Follower engagement (exclude user)
        follower_engagement = {
            'likes': Like.objects.filter(
                user_id__in=follower_ids,
                video__uploader=user,
                is_like=True
            ).exclude(user=user).count(),
            'dislikes': Like.objects.filter(
                user_id__in=follower_ids,
                video__uploader=user,
                is_like=False
            ).exclude(user=user).count(),
            'comments': Review.objects.filter(
                user_id__in=follower_ids,
                video__uploader=user
            ).exclude(user=user).count(),
            'views': ViewHistory.objects.filter(
                user_id__in=follower_ids,
                video__uploader=user
            ).exclude(user=user).count()
        }
        
        # Total engagement (exclude user)
        total_engagement = {
            'total_likes': Like.objects.filter(
                video__uploader=user,
                is_like=True
            ).exclude(user=user).count(),
            'total_dislikes': Like.objects.filter(
                video__uploader=user,
                is_like=False
            ).exclude(user=user).count(),
            'total_comments': Review.objects.filter(
                video__uploader=user
            ).exclude(user=user).count(),
            'total_views': Video.objects.filter(
                uploader=user
            ).aggregate(
                total_views=Sum('views')
            )['total_views'] or 0
        }
        
        return {
            'engagement_breakdown': {
                'likes': {
                    'total': total_engagement['total_likes'],
                    'follower_count': follower_engagement['likes'],
                    'non_follower_count': total_engagement['total_likes'] - follower_engagement['likes'],
                    'follower_percentage': (follower_engagement['likes'] / total_engagement['total_likes'] * 100) if total_engagement['total_likes'] else 0,
                    'non_follower_percentage': 100 - ((follower_engagement['likes'] / total_engagement['total_likes'] * 100) if total_engagement['total_likes'] else 0)
                },
                'dislikes': {
                    'total': total_engagement['total_dislikes'],
                    'follower_count': follower_engagement['dislikes'],
                    'non_follower_count': total_engagement['total_dislikes'] - follower_engagement['dislikes'],
                    'follower_percentage': (follower_engagement['dislikes'] / total_engagement['total_dislikes'] * 100) if total_engagement['total_dislikes'] else 0,
                    'non_follower_percentage': 100 - ((follower_engagement['dislikes'] / total_engagement['total_dislikes'] * 100) if total_engagement['total_dislikes'] else 0)
                },
                'comments': {
                    'total': total_engagement['total_comments'],
                    'follower_count': follower_engagement['comments'],
                    'non_follower_count': total_engagement['total_comments'] - follower_engagement['comments'],
                    'follower_percentage': (follower_engagement['comments'] / total_engagement['total_comments'] * 100) if total_engagement['total_comments'] else 0,
                    'non_follower_percentage': 100 - ((follower_engagement['comments'] / total_engagement['total_comments'] * 100) if total_engagement['total_comments'] else 0)
                },
                'views': {
                    'total': total_engagement['total_views'],
                    'follower_count': follower_engagement['views'],
                    'non_follower_count': total_engagement['total_views'] - follower_engagement['views'],
                    'follower_percentage': (follower_engagement['views'] / total_engagement['total_views'] * 100) if total_engagement['total_views'] else 0,
                    'non_follower_percentage': 100 - ((follower_engagement['views'] / total_engagement['total_views'] * 100) if total_engagement['total_views'] else 0)
                }
            }
        }
