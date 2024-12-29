document.addEventListener('DOMContentLoaded', function() {
    const followButtons = document.querySelectorAll('.follow-btn');
    
    followButtons.forEach(button => {
        button.addEventListener('click', async function(e) {
            e.preventDefault();
            
            if (!isAuthenticated) {
                window.location.href = loginUrl;
                return;
            }
            
            const profileId = this.dataset.profileId;
            const token = localStorage.getItem('access_token');
            
            try {
                console.log('Using JWT token:', token.substring(0, 20) + '...'); // Show part of token
                
                const response = await fetch(`/api/users/${profileId}/follow/`, {
                    method: 'POST',
                    headers: {
                        'Authorization': `Bearer ${token}`,
                        'Content-Type': 'application/json'
                    },
                });
                
                const data = await response.json();
                console.log('Server response:', {
                    status: data.status,
                    is_following: data.is_following,
                    followers_count: data.followers_count,
                    following_count: data.following_count
                });
                
                if (data.status === 'success') {
                    this.classList.toggle('active');
                    const icon = this.querySelector('i');
                    icon.classList.toggle('fa-user-plus');
                    icon.classList.toggle('fa-user-minus');
                    const textSpan = this.querySelector('.follow-text');
                    textSpan.textContent = data.is_following ? 'Following' : 'Follow';
                } else {
                    console.error('Follow action failed:', data.message);
                }
            } catch (error) {
                console.error('Follow error:', error);
            }
        });
    });
});