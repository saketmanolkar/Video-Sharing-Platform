class LikeDislikeHandler {
    constructor() {
        this.setupEventListeners();
    }
    
    setupEventListeners() {
        document.querySelectorAll('.like-btn, .dislike-btn').forEach(button => {
            button.addEventListener('click', (e) => this.handleClick(e));
        });
    }
    
    async handleClick(e) {
        const button = e.currentTarget;
        
        // Check if user is logged in
        if (!isAuthenticated) {
            window.location.href = loginUrl;
            return;
        }
        
        const videoId = button.dataset.videoId;
        const isLike = button.dataset.action === 'like';
        
        try {
            const response = await this.sendLikeRequest(videoId, isLike);
            this.updateUI(response, isLike);
        } catch (error) {
            console.error('Error:', error);
        }
    }
    
    async sendLikeRequest(videoId, isLike) {
        const response = await fetch(`/video/${videoId}/like/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': csrfToken,
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: `is_like=${isLike}`
        });
        
        return await response.json();
    }
    
    updateUI(data, isLike) {
        // Find both buttons
        const likeBtn = document.querySelector('.like-btn');
        const dislikeBtn = document.querySelector('.dislike-btn');
        
        // Reset both buttons first
        likeBtn.classList.remove('active');
        dislikeBtn.classList.remove('active');
        
        // Then update based on server response
        if (data.action === 'added' || data.action === 'switched') {
            if (isLike) {
                likeBtn.classList.add('active');
            } else {
                dislikeBtn.classList.add('active');
            }
        }
        
        // Update counts
        document.querySelector('.like-btn + .stats-count').textContent = data.likes_count;
        document.querySelector('.dislike-btn + .stats-count').textContent = data.dislikes_count;
    }
}

// Initialize when document loads
document.addEventListener('DOMContentLoaded', () => {
    new LikeDislikeHandler();
});
