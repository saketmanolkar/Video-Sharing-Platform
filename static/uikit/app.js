// Invoke Functions Call on Document Loaded
document.addEventListener('DOMContentLoaded', function () {
  hljs.highlightAll();
});


let alertWrapper = document.querySelector('.alert')
let alertClose = document.querySelector('.alert__close')

if (alertWrapper) {
  alertClose.addEventListener('click', () =>
    alertWrapper.style.display = 'none'
  )
}

// Video Preview Utility
class VideoPreviewManager {
    constructor() {
        this.previewTimeouts = new Map();
        this.initializePreviews();
    }

    initializePreviews() {
        document.querySelectorAll('[data-video-url]').forEach(container => {
            this.setupPreviewContainer(container);
        });
    }

    setupPreviewContainer(container) {
        const videoUrl = container.dataset.videoUrl;
        const previewDuration = parseInt(container.dataset.previewDuration || '15') * 1000;

        container.addEventListener('mouseenter', () => {
            this.startPreview(container, videoUrl, previewDuration);
        });

        container.addEventListener('mouseleave', () => {
            this.stopPreview(container);
        });
    }

    startPreview(container, videoUrl, duration) {
        try {
            const video = document.createElement('video');
            
            // Add loading indicator
            container.classList.add('loading');
            
            // Video settings
            video.src = videoUrl;
            video.muted = true; // Mute video for autoplay
            video.className = 'thumbnail-preview';
            video.playsInline = true;
            video.controls = false; // Remove controls
            video.loop = true; // Add loop
            
            // Error handling
            video.onerror = () => {
                console.error('Error loading video:', videoUrl);
                container.classList.remove('loading');
                this.stopPreview(container);
            };
            
            // Loaded handling
            video.onloadeddata = () => {
                container.classList.remove('loading');
                // Hide the thumbnail
                const thumbnail = container.querySelector('img');
                if (thumbnail) thumbnail.style.opacity = '0';
                
                // Play video
                video.play().catch(e => console.error('Playback failed:', e));
            };

            container.appendChild(video);
        } catch (error) {
            console.error('Preview error:', error);
            container.classList.remove('loading');
        }
    }

    stopPreview(container) {
        const video = container.querySelector('video');
        const thumbnail = container.querySelector('img');
        
        if (video) {
            video.pause();
            video.remove();
        }
        
        if (thumbnail) {
            thumbnail.style.opacity = '1';
        }

        container.classList.remove('loading');
    }
}

// Initialize video previews when document is loaded
document.addEventListener('DOMContentLoaded', function() {
    const previewManager = new VideoPreviewManager();
});
