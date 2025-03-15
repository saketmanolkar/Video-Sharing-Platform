class ApiLikeDislikeHandler {
    constructor() {
        this.setupEventListeners();
    }
    
    setupEventListeners() {
        document.querySelectorAll('.api-like-btn, .api-dislike-btn').forEach(button => {
            button.addEventListener('click', (e) => this.handleClick(e));
        });
    }
    
    async handleClick(e) {
        e.preventDefault();
        const button = e.currentTarget;
        const videoId = button.dataset.videoId;
        const isLike = button.dataset.action === 'like';
        
        try {
            const response = await fetch(`/api/projects/${videoId}/like/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${localStorage.getItem('access_token')}`
                },
                body: JSON.stringify({
                    is_like: isLike
                })
            });
            
            const data = await response.json();
            console.log('Server response:', data);
            
            if (response.ok) {
                // Get both buttons
                const likeBtn = document.querySelector('.api-like-btn');
                const dislikeBtn = document.querySelector('.api-dislike-btn');
                
                // Reset both buttons first
                likeBtn.classList.remove('active');
                dislikeBtn.classList.remove('active');
                
                // Update based on action
                if (data.action === 'added' || data.action === 'switched') {
                    if (isLike) {
                        likeBtn.classList.add('active');
                    } else {
                        dislikeBtn.classList.add('active');
                    }
                }
                
                // Update counts
                document.querySelector('.api-like-btn + .stats-count').textContent = data.likes_count;
                document.querySelector('.api-dislike-btn + .stats-count').textContent = data.dislikes_count;
                
            } else {
                console.error('Request failed:', response.status);
                console.error('Error message:', data.message);
            }
        } catch (error) {
            console.error('Error:', error);
        }
    }
}

// Initialize when document is ready
document.addEventListener('DOMContentLoaded', () => {
    new ApiLikeDislikeHandler();
});