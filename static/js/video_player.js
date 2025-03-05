// FIRST: Start checking immediately and keep checking until found
console.log('🔄 Starting cookie check...');

function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
    return null;
}

const cookieCheckInterval = setInterval(() => {
    const cookies = document.cookie;
    const logoutPending = getCookie('logout_pending');
    
    if (logoutPending === 'true') {
        console.log('🚨 Found logout_pending cookie!');
        clearInterval(cookieCheckInterval);
        
        // Try to call logoutUser if it exists
        if (window.logoutUser) {
            console.log('✅ Calling logoutUser directly');
            window.logoutUser();
        } else {
            console.log('⏳ Waiting for logoutUser to be defined...');
            // Keep checking for logoutUser
            const waitForLogout = setInterval(() => {
                if (window.logoutUser) {
                    clearInterval(waitForLogout);
                    window.logoutUser();
                }
            }, 100);
        }
    }
}, 100);

document.addEventListener('DOMContentLoaded', () => {
    // Get data passed from the template
    const videoPlayerData = window.videoPlayerData || {};
    
    // Get CSRF token at the start
    const videoPlayerCsrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;

    if (document.getElementById('video-js-player')) {
        const player = videojs('video-js-player');
        const videoElement = player.el().querySelector('video');
        console.log('🎥 Player initialized');

        // Add window_id and user tracking - use data from videoPlayerData
        const windowId = videoPlayerData.windowId || '';
        const username = videoPlayerData.username || 'Anonymous';
        const videoId = videoPlayerData.videoId || '';
        const isAuthenticated = videoPlayerData.isAuthenticated || false;
        
        // CHANGE: Ensure userId HAS 'user_' prefix
        let userId = videoPlayerData.userId || '';
        if (!userId.startsWith('user_') && userId) {
            userId = `user_${userId}`; // ADD 'user_' prefix
            console.log('🔄 Added user_ prefix to userId:', userId);
        }

        // Add validation check
        if (!windowId || windowId.trim() === '') {
            console.warn('⚠️ No window_id available for video tracking');
        }

        let isPlaying = false;
        let totalPlaybackTime = 0;
        let playStartTime = 0;
        let watchedRanges = [];
        let lastUpdateTime = 0;
        let isLoggingOut = false;

        // Add duration logging
        player.on('loadedmetadata', function() {
            const duration = player.duration();
            console.log('📼 Initial video duration:', Number(duration).toFixed(2), 'seconds');

            // Log videoId, username, and windowId regardless of its existence
            console.log('🎬 Video View Details:', {
                videoId: videoId,
                username: username, 
                windowId: windowId,
                userId: userId  // Log the processed userId with prefix
            });
        });

        player.on('durationchange', function() {
            const duration = player.duration();
            console.log('📼 Duration updated:', Number(duration).toFixed(2), 'seconds');
        });

        // When video starts playing
        player.on('play', function() {
            isPlaying = true;
            playStartTime = videoElement.currentTime;
            lastUpdateTime = playStartTime;
            console.log('▶️ Start:', {
                exact: playStartTime,
                duration: Number(player.duration()).toFixed(2)  // Log duration at play
            });
        });

        // When video pauses - update local stats
        player.on('pause', function() {
            if (isPlaying) {
                const currentTime = videoElement.currentTime;
                const watchedSegment = currentTime - lastUpdateTime;
                totalPlaybackTime += watchedSegment;

                watchedRanges.push({
                    start: playStartTime,
                    end: currentTime
                });

                isPlaying = false;
                console.log('⏸️ Paused:', {
                    at: Number(currentTime).toFixed(2),
                    total: Number(totalPlaybackTime).toFixed(2),
                    ranges: watchedRanges
                });

                // Update lastUpdateTime to currentTime for the next interval
                lastUpdateTime = currentTime;
            }
        });

        // When video ends
        player.on('ended', function() {
            if (isPlaying) {
                const currentTime = videoElement.currentTime;
                const watchedSegment = currentTime - playStartTime;
                totalPlaybackTime += watchedSegment;
                
                watchedRanges.push({
                    start: playStartTime,
                    end: currentTime
                });
                
                isPlaying = false;
                console.log('🏁 Ended:', {
                    at: Number(currentTime).toFixed(2),
                    total: Number(totalPlaybackTime).toFixed(2),
                    ranges: watchedRanges
                });
                
                // No need to update session storage here anymore
            }
        });

        // Helper function to calculate unique watched time
        function calculateUniqueWatched(ranges) {
            if (ranges.length === 0) return 0;
            
            // Sort ranges by start time
            ranges.sort((a, b) => a.start - b.start);
            
            let uniqueTime = 0;
            let currentStart = ranges[0].start;
            let currentEnd = ranges[0].end;
            
            // Merge overlapping ranges
            for (let i = 1; i < ranges.length; i++) {
                if (ranges[i].start <= currentEnd) {
                    // Ranges overlap, extend current range if needed
                    currentEnd = Math.max(currentEnd, ranges[i].end);
                } else {
                    // No overlap, add current range and start new one
                    uniqueTime += (currentEnd - currentStart);
                    currentStart = ranges[i].start;
                    currentEnd = ranges[i].end;
                }
            }
            
            // Add final range
            uniqueTime += (currentEnd - currentStart);
            return uniqueTime;
        }

        // Get CSRF token from cookie
        function getCSRFToken() {
            const name = 'csrftoken';
            let cookieValue = null;
            if (document.cookie && document.cookie !== '') {
                const cookies = document.cookie.split(';');
                for (let i = 0; i < cookies.length; i++) {
                    const cookie = cookies[i].trim();
                    if (cookie.substring(0, name.length + 1) === (name + '=')) {
                        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                        break;
                    }
                }
            }
            return cookieValue;
        }

        // When video ends or page unloads
        window.addEventListener('beforeunload', function() {
            // Call the existing pause logic to update watched stats
            if (isPlaying) {
                const currentTime = videoElement.currentTime;
                const watchedSegment = currentTime - playStartTime; // Calculate the segment watched
                totalPlaybackTime += watchedSegment; // Update total playback time

                watchedRanges.push({
                    start: playStartTime,
                    end: currentTime
                });

                isPlaying = false; // Reset isPlaying
                console.log('⏸️ Video stopped because of Page Navigation:', {
                    at: Number(currentTime).toFixed(2),
                    total: Number(totalPlaybackTime).toFixed(2),
                    ranges: watchedRanges
                });
            }

            const duration = player.duration();
            const uniqueWatched = calculateUniqueWatched(watchedRanges);
            const percentage = (uniqueWatched / duration) * 100;

            const stats = {
                window_id: windowId,
                video_id: videoId,
                total_watched: Number(totalPlaybackTime).toFixed(2),
                ranges: watchedRanges,
                username: username,
                user_id: userId, // Using userId with 'user_' prefix
                is_completed: percentage >= 90 // Mark as completed if 90% or more watched
            };

            // Set a cookie with the video watch stats only if windowId exists, the user is authenticated, and is not logging out
            if (!windowId) {
                console.warn('⚠️ Window ID missing. Video Stats Cookie will not be set.');
            } else if (isLoggingOut) {
                console.warn('⚠️ User is logging out. Video Stats Cookie will not be set.');
            } else if (!isAuthenticated) { // Check if the user is authenticated
                console.warn('⚠️ User is not authenticated. Video Stats Cookie will not be set.');
            } else {
                try {
                    document.cookie = `videoWatchStats=${encodeURIComponent(JSON.stringify(stats))}; path=/; max-age=3600`; // Cookie expires in 1 hour
                    console.log('🍪 📊 VideoWatchStats cookie set successfully:', stats);
                } catch (error) {
                    console.error('❌ Failed to set video stats cookie:', error);
                }
            }
        });

        // Add chunk monitoring
        player.on('progress', function() {
            const buffered = player.buffered();
            if (buffered.length > 0) {
                const lastRange = buffered.length - 1;
                const progress = (buffered.end(lastRange) / player.duration()) * 100;
                
                console.log('📦 Buffer Progress:', {
                    ranges: Array.from({length: buffered.length}, (_, i) => ({
                        start: Number(buffered.start(i)).toFixed(2),
                        end: Number(buffered.end(i)).toFixed(2),
                        size: Number(buffered.end(i) - buffered.start(i)).toFixed(2) + ' seconds'
                    })),
                    percentage: Number(progress).toFixed(2) + '%'
                });
            }
        });

        // Add seeking monitoring
        player.on('seeking', function() {
            console.log('🔍 Seeking to:', Number(player.currentTime()).toFixed(2));
        });

        // Add loading monitoring
        player.on('waiting', function() {
            console.log('⏳ Buffering...');
        });

        // Add more detailed metadata logging
        player.on('loadedmetadata', function() {
            const duration = player.duration();
            const videoElement = player.el().querySelector('video');
            
            console.log('📼 Video Metadata:', {
                duration: Number(duration).toFixed(2),
                videoWidth: videoElement.videoWidth,
                videoHeight: videoElement.videoHeight,
                readyState: videoElement.readyState,
                size: videoElement.size,  // If available
                type: videoElement.type
            });
        });

        // Make logoutUser function available globally
        window.logoutUser = function() {
            isLoggingOut = true;  // Set flag when logout starts

            // Calculate final stats directly in the logout function
            if (isPlaying) {
                const currentTime = videoElement.currentTime;
                const watchedSegment = currentTime - playStartTime;
                totalPlaybackTime += watchedSegment;

                watchedRanges.push({
                    start: playStartTime,
                    end: currentTime
                });

                isPlaying = false;
                console.log('⏸️ Video stopped because of logout:', {
                    at: Number(currentTime).toFixed(2),
                    total: Number(totalPlaybackTime).toFixed(2),
                    ranges: watchedRanges
                });
            }

            const duration = player.duration();
            const uniqueWatched = calculateUniqueWatched(watchedRanges);
            const percentage = (uniqueWatched / duration) * 100;

            const stats = {
                window_id: windowId,
                video_id: videoId,
                total_watched: Number(totalPlaybackTime).toFixed(2),
                username: username,
                user_id: userId,
                is_completed: percentage >= 90
            };

            // Check for required fields
            if (!windowId) {
                console.warn('⚠️ Window ID missing. Cannot send stats to API');
                // Proceed with logout even if windowId is missing
                window.location.href = '/users/logout/';
            } else {
                // Log the stats being sent to the API
                console.log('📤 Sending video stats to API:', stats);

                // Simply use navigator.sendBeacon which handles page unload gracefully
                try {
                    const blob = new Blob([JSON.stringify(stats)], {type: 'application/json'});
                    const beaconSuccess = navigator.sendBeacon('/api/video-stats/', blob);
                    
                    if (beaconSuccess) {
                        console.log('📡 Stats sent via beacon successfully');
                    } else {
                        console.log('ℹ️ Beacon not available, redirecting to logout');
                    }
                } catch (e) {
                    // Suppress the error completely
                    console.log('ℹ️ Stats sending handled, redirecting to logout');
                }
                
                // Redirect immediately - beacon will continue in background
                window.location.href = '/users/logout/';
            }
        }
    }
});