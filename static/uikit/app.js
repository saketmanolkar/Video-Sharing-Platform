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
              // Clear any existing video first
              this.stopPreview(container);
              // Start new preview
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
              video.muted = true;
              video.className = 'thumbnail-preview';
              video.playsInline = true;
              video.controls = false;
              video.loop = true;
              
              // Add inline styles
              Object.assign(video.style, {
                  position: 'absolute',
                  top: '50%',
                  left: '50%',
                  transform: 'translate(-50%, -50%)',
                  width: 'auto',
                  height: '100%',
                  objectFit: 'contain',
                  objectPosition: 'center',
                  zIndex: '1'
              });
              
              // Error handling
              video.onerror = () => {
                  console.error('Error loading video:', videoUrl);
                  container.classList.remove('loading');
                  this.stopPreview(container);
              };
              
              // Loaded handling
              video.onloadeddata = () => {
                  container.classList.remove('loading');
                  const thumbnail = container.querySelector('img');
                  if (thumbnail) thumbnail.style.opacity = '0';
                  video.play().catch(e => console.error('Playback failed:', e));
              };
  
              container.appendChild(video);
          } catch (error) {
              console.error('Preview error:', error);
              container.classList.remove('loading');
          }
      }
  
      stopPreview(container) {
          // Remove any existing video elements
          const videos = container.querySelectorAll('video');
          videos.forEach(video => {
              video.pause();
              video.removeAttribute('src'); // Clear source
              video.load(); // Reset video element
              video.remove();
          });
          
          // Reset thumbnail
          const thumbnail = container.querySelector('img');
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