class ApiLikeDislikeHandler {
    constructor() {
        this.setupEventListeners();
        // Check if user is authenticated by looking for token
        this.isAuthenticated = !!localStorage.getItem('access_token');
    }
    
    setupEventListeners() {
        document.querySelectorAll('.api-like-btn, .api-dislike-btn').forEach(button => {
            button.addEventListener('click', (e) => this.handleClick(e));
        });
    }
    
    // Add method to show messages
    showMessage(message, type = 'error') {
        // Check if a message container exists, create one if not
        let messageContainer = document.querySelector('.api-message-container');
        if (!messageContainer) {
            messageContainer = document.createElement('div');
            messageContainer.className = 'api-message-container';
            messageContainer.style.position = 'fixed';
            messageContainer.style.top = '20px';
            messageContainer.style.right = '20px';
            messageContainer.style.zIndex = '1000';
            document.body.appendChild(messageContainer);
        }
        
        // Create message element
        const messageElement = document.createElement('div');
        messageElement.className = `api-message ${type}`;
        messageElement.textContent = message;
        messageElement.style.padding = '10px 15px';
        messageElement.style.margin = '5px 0';
        messageElement.style.borderRadius = '4px';
        messageElement.style.backgroundColor = type === 'error' ? '#f8d7da' : '#d4edda';
        messageElement.style.color = type === 'error' ? '#721c24' : '#155724';
        messageElement.style.boxShadow = '0 2px 5px rgba(0,0,0,0.2)';
        
        // Add to container
        messageContainer.appendChild(messageElement);
        
        // Remove after delay
        setTimeout(() => {
            messageElement.style.opacity = '0';
            messageElement.style.transition = 'opacity 0.5s';
            setTimeout(() => messageElement.remove(), 500);
        }, 3000);
    }
    
    async handleClick(e) {
        e.preventDefault();
        const button = e.currentTarget;
        const videoId = button.dataset.videoId;
        const isLike = button.dataset.action === 'like';
        
        // Check authentication first
        if (!this.isAuthenticated) {
            this.showMessage('Please log in to like or dislike videos');
            return;
        }
        
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
            
            if (response.ok) {
                const data = await response.json();
                console.log('Server response:', data);
                
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
                const data = await response.json().catch(() => ({}));
                const errorMessage = data?.message || 'An error occurred. Please try again.';
                this.showMessage(errorMessage);
            }
        } catch (error) {
            this.showMessage('Network error. Please check your connection.');
        }
    }
}

// Initialize when document is ready
document.addEventListener('DOMContentLoaded', () => {
    new ApiLikeDislikeHandler();
});