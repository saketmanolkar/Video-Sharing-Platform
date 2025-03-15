async function handleFollow(button) {
    // Get token directly instead of checking isAuthenticated
    const token = localStorage.getItem('access_token');
    if (!token) {
        window.location.href = '/login/';
        return;
    }

    const profileId = button.dataset.profileId;

    try {
        console.log('Using JWT token:', token.substring(0, 20) + '...'); // Debug token

        const response = await fetch(`/api/users/${profileId}/follow/`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });

        const data = await response.json();
        console.log('Server response:', {
            status: data.status,
            is_following: data.is_following,
            followers_count: data.followers_count
        });

        if (data.status === 'success') {
            // Update button state
            const followText = button.querySelector('.follow-text');
            if (followText) {
                if (data.is_following) {
                    button.classList.add('following');
                    followText.textContent = 'Unfollow';
                } else {
                    button.classList.remove('following');
                    followText.textContent = 'Follow';
                }
            }
            
            // Update follower count
            const followersCount = document.querySelector('.followers-count');
            if (followersCount) {
                followersCount.textContent = data.followers_count;
            }
        } else {
            console.error('Follow action failed:', data.message);
        }
    } catch (error) {
        console.error('Follow error:', error);
        if (error.response?.status === 401) {
            window.location.href = '/login/';
        }
    }
}