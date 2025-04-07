from channels.generic.websocket import WebsocketConsumer
import json
from asgiref.sync import async_to_sync
import logging
import time

logger = logging.getLogger(__name__)

class VideoConsumer(WebsocketConsumer):
    def connect(self):
        """Handle WebSocket connection"""
        self.video_id = self.scope['url_route']['kwargs']['video_id']
        self.window_id = self.scope['url_route']['kwargs']['window_id']
        self.room_group_name = f'video_{self.video_id}_{self.window_id}'
        
        # Store metadata about this connection
        self.connection_metadata = {
            'graceful_closure': False,
            'closed_reason': None,
            'last_stats_update': time.time()
        }
        
        # Join room group
        async_to_sync(self.channel_layer.group_add)(
            self.room_group_name,
            self.channel_name
        )
        
        # Accept connection
        self.accept()
        
        logger.info(f"WebSocket connected: video_id={self.video_id}, window_id={self.window_id}")

    def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        logger.info(f"WebSocket disconnected: video_id={self.video_id}, window_id={self.window_id}, code={close_code}")
        
        # Check if we received a close message
        received_close = self.connection_metadata.get('received_close_message', False)
        close_reason = self.connection_metadata.get('closed_reason', 'unknown')
        
        if received_close and close_reason == 'page_navigation':
            # This was a true navigation (not tab close)
            logger.info(f"✅ Normal navigation closure for video={self.video_id}")
            self.connection_metadata['graceful_closure'] = True

        elif received_close and close_reason == 'user_logout':
            # This was an explicit logout
            logger.info(f"✅ Explicit logout closure for video={self.video_id}")
            self.connection_metadata['graceful_closure'] = True
            
        else:
            # Either no close message or it was a tab/browser close or user not authenticated
            logger.warning(f"❌ Ungraceful Closure for video={self.video_id}")
            
            # Get the last stats that were saved in connection_metadata
            # Use default values if none were provided
            total_watched = self.connection_metadata.get('total_watched', "0.00")
            is_completed = self.connection_metadata.get('is_completed', False)
            
            # Log the stats we're using from the last update
            logger.info(f"📊 Using stats for disconnect: total_watched={total_watched}, is_completed={is_completed}")
            
            # Send final stats to your view history API
            from django.http import JsonResponse
            import requests
            
            try:
                # Use the API endpoint for video stats
                data = {
                    'window_id': self.window_id,
                    'video_id': self.video_id,
                    'total_watched': total_watched,
                    'is_completed': is_completed,
                    'username': getattr(self, 'username', None),
                    'user_id': getattr(self, 'user_id', None)
                }
                
                # Make the request to your own API
                from django.conf import settings
                base_url = settings.BASE_URL if hasattr(settings, 'BASE_URL') else 'http://localhost:8000'
                requests.post(f"{base_url}/api/video-stats/", json=data)
                logger.info(f"✅ Saved final stats from disconnect for video={self.video_id}")
            except Exception as e:
                logger.error(f"Failed to save stats for disconnect: {str(e)}")
        
        # Leave room group
        async_to_sync(self.channel_layer.group_discard)(
            self.room_group_name,
            self.channel_name
        )

    def receive(self, text_data):
        """Handle messages from WebSocket client"""
        try:
            text_data_json = json.loads(text_data)
            message_type = text_data_json.get('type')
            
            if message_type == 'connect':
                # Initial connection data
                self.user_id = text_data_json.get('user_id')
                self.username = text_data_json.get('username')
                logger.info(f"Initial connection data: user={self.username}, video={self.video_id}, window={self.window_id}")
                
            elif message_type == 'heartbeat':
                # Client is sending regular heartbeat
                logger.debug(f"Heartbeat received from {self.window_id}")
                
            elif message_type == 'close':
                # Client is closing connection gracefully
                reason = text_data_json.get('reason', 'unknown')
                
                # Log but DON'T mark as graceful closure yet
                logger.info(f"Close message received: {reason} for video={self.video_id}, window={self.window_id}")
                
                # Use a flag that will be checked in disconnect
                self.connection_metadata['received_close_message'] = True
                self.connection_metadata['closed_reason'] = reason
                
            elif message_type == 'update_stats':
                # Update viewing statistics
                total_watched = text_data_json.get('total_watched', 0)
                is_completed = text_data_json.get('is_completed', False)
                
                # Store stats in connection_metadata
                if 'total_watched' in text_data_json:
                    self.connection_metadata['total_watched'] = text_data_json.get('total_watched')
                if 'is_completed' in text_data_json:
                    self.connection_metadata['is_completed'] = text_data_json.get('is_completed')
                if 'ranges' in text_data_json:
                    self.connection_metadata['ranges'] = text_data_json.get('ranges')
                
                # Update timestamp of last stats update
                self.connection_metadata['last_stats_update'] = time.time()
                
                logger.info(f"Stats updated for video={self.video_id}, window={self.window_id}: "
                           f"total_watched={total_watched}, is_completed={is_completed}")
                
            # You can add more message types as needed
                
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON received: {text_data}")
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}") 