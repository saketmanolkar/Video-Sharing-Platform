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
            
            try {
                const response = await fetch(`/users/follow/${profileId}/`, {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': csrfToken,
                    },
                });
                
                const data = await response.json();
                
                if (data.status === 'success') {
                    // Toggle active class
                    this.classList.toggle('active');
                    // Toggle icon
                    const icon = this.querySelector('i');
                    icon.classList.toggle('fa-user-plus');
                    icon.classList.toggle('fa-user-minus');
                    // Update text
                    const textSpan = this.querySelector('.follow-text');
                    textSpan.textContent = data.is_following ? 'Following' : 'Follow';
                } else {
                    console.error(data.message);
                }
            } catch (error) {
                console.error('Error:', error);
            }
        });
    });
});