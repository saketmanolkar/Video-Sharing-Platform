from rest_framework import serializers
from projects.models import Video, Review, Tag, Like
from django.contrib.auth.models import User

class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = '__all__'

class ReviewSerializer(serializers.ModelSerializer):
    username = serializers.SerializerMethodField()
    is_owner = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = ['id', 'username', 'comment', 'is_owner', 'created_at', 'modified_at']

    def get_username(self, obj):
        return obj.user.username if obj.user else None

    def get_is_owner(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.user == request.user
        return False

    def update(self, instance, validated_data):
        instance.comment = validated_data.get('comment', instance.comment)
        instance.save()
        return instance

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = '__all__'

class VideoSerializer(serializers.ModelSerializer):
    uploader = UserSerializer(read_only=True)
    tags = TagSerializer(many=True)
    reviews = serializers.SerializerMethodField()
    class Meta:
        model = Video
        fields = '__all__'

    def get_reviews(self, obj):
        reviews = obj.reviews.all()
        serializer = ReviewSerializer(reviews, many=True)
        return serializer.data
    
class LikeSerializer(serializers.ModelSerializer):
    video = VideoSerializer(read_only=True)
    user = UserSerializer(read_only=True)
    
    # Add these fields for write operations
    video_id = serializers.UUIDField(write_only=True)
    user_id = serializers.IntegerField(write_only=True)
    
    class Meta:
        model = Like
        fields = ['id', 'video', 'user', 'is_like', 'created_at', 'video_id', 'user_id']
