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
        this.initializePreviews();
    }

    initializePreviews() {
        document.querySelectorAll('.project__thumbnail-wrapper').forEach(container => {
            const videoUrl = container.dataset.videoUrl;
            if (!videoUrl) return;

            let video; // Declare video variable

            container.addEventListener('mouseenter', () => {
                if (!video) {
                    video = document.createElement('video');
                    video.src = videoUrl;
                    video.muted = true;
                    video.playsInline = true;
                    video.controls = false;
                    video.loop = true;
                    video.className = 'thumbnail-preview';

                    Object.assign(video.style, {
                        width: '100%',
                        height: '100%',
                        objectFit: 'cover',
                        position: 'absolute',
                        top: '0',
                        left: '0',
                        zIndex: '1',
                        opacity: '0',
                        transition: 'opacity 0.3s ease'
                    });

                    container.appendChild(video);

                    video.onloadeddata = () => {
                        if (video && video.style) {
                            video.style.opacity = '1';
                            const thumbnail = container.querySelector('img');
                            if (thumbnail) {
                                thumbnail.style.opacity = '0.3';
                            }
                            video.play().catch(e => console.error('Playback failed:', e));
                        }
                    };
                }
            });

            container.addEventListener('mouseleave', () => {
                if (video) {
                    video.pause();
                    video.remove();
                    video = null;
                    
                    const thumbnail = container.querySelector('img');
                    if (thumbnail) {
                        thumbnail.style.opacity = '1';
                    }
                }
            });
        });
    }
}

// Add CSS
const style = document.createElement('style');
style.textContent = `
    .project__thumbnail-wrapper, .sidebar-thumbnail {
        position: relative;
        overflow: hidden;
    }

    .project__thumbnail-wrapper img, .sidebar-thumbnail img {
        transition: opacity 0.3s ease;
    }

    .preview-video {
        background: #000;
    }

    .loading::after {
        content: '';
        position: absolute;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        width: 30px;
        height: 30px;
        border: 3px solid rgba(255,255,255,0.3);
        border-top-color: #fff;
        border-radius: 50%;
        animation: spin 1s linear infinite;
        z-index: 2;
    }

    @keyframes spin {
        to { transform: translate(-50%, -50%) rotate(360deg); }
    }
`;
document.head.appendChild(style);

// Initialize when document is loaded
document.addEventListener('DOMContentLoaded', function() {
    new VideoPreviewManager();
});
