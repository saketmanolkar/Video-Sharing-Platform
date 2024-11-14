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
        this.activeVideos = new Map();
        this.initializePreviews();
    }

    initializePreviews() {
        document.querySelectorAll('[data-video-url]').forEach(container => {
            this.setupPreviewContainer(container);
        });
    }

    setupPreviewContainer(container) {
        const videoUrl = container.dataset.videoUrl;
        
        // Create video element
        const video = document.createElement('video');
        video.src = videoUrl;
        video.muted = true; // Mute by default for autoplay to work
        video.className = 'thumbnail-preview';
        video.playsInline = true;
        video.controls = false;
        video.preload = 'metadata';
        
        // Store video element for this container
        this.activeVideos.set(container, video);
        
        container.addEventListener('mouseenter', () => {
            this.startPreview(container);
        });

        container.addEventListener('mouseleave', () => {
            this.stopPreview(container);
        });
    }

    startPreview(container) {
        try {
            const video = this.activeVideos.get(container);
            if (!video) return;

            // Hide the thumbnail
            const thumbnail = container.querySelector('img');
            if (thumbnail) {
                thumbnail.style.opacity = '0';
            }

            // Add video to container if not already there
            if (!container.contains(video)) {
                container.appendChild(video);
            }

            // Play video
            const playPromise = video.play();
            if (playPromise !== undefined) {
                playPromise
                    .then(() => {
                        // Video started playing
                        container.classList.remove('loading');
                    })
                    .catch(error => {
                        console.error("Video play failed:", error);
                        this.stopPreview(container);
                    });
            }
        } catch (error) {
            console.error('Preview error:', error);
            this.stopPreview(container);
        }
    }

    stopPreview(container) {
        const video = this.activeVideos.get(container);
        const thumbnail = container.querySelector('img');
        
        if (video) {
            video.pause();
            video.currentTime = 0;
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
