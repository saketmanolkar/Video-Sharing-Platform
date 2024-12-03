function handleFollow(button) {
    const profileId = button.dataset.profileId;
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
    
    fetch(`/users/follow/${profileId}/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': csrfToken,
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            // Update button text and class
            const followText = button.querySelector('.follow-text');
            if (data.is_following) {
                button.classList.add('following');
                followText.textContent = 'Unfollow';
            } else {
                button.classList.remove('following');
                followText.textContent = 'Follow';
            }
            
            // Update follower count
            document.querySelector('.followers-count').textContent = data.followers_count;
        }
    })
    .catch(error => console.error('Error:', error));
}