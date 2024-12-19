function createCommentRow(comment) {
    const escapedComment = comment.comment.replace(/"/g, '&quot;');
    return `
        <tr data-review-id="${comment.id}">
            <td class="settings__tableInfo">
                <h4>${comment.username}</h4>
                <p>${comment.comment}</p>
            </td>
            <td class="settings__tableActions">
                ${comment.is_owner ? `
                    <button class="tag tag--pill tag--main settings__btn edit-btn" 
                            data-id="${comment.id}" 
                            data-comment="${escapedComment}">
                        <i class="im im-edit"></i> Edit
                    </button>
                    <button class="tag tag--pill tag--main settings__btn delete-btn" 
                            onclick="showDeleteConfirmation('${comment.id}', '${escapedComment}', 'comment')"
                            data-id="${comment.id}">
                        <i class="im im-x-mark"></i> Delete
                    </button>
                ` : ''}
            </td>
        </tr>
    `;
}

function handleSubmit(event) {
    event.preventDefault();
    const form = event.target;
    
    // Prevent double submissions
    if (form.dataset.submitting === 'true') return;
    form.dataset.submitting = 'true';
    
    const formData = new FormData(form);
    
    fetch(form.action, {
        method: 'POST',
        headers: {
            'X-CSRFToken': csrfToken
        },
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Update the comments list
            const commentsList = document.querySelector('.settings__table');
            const newCommentHtml = createCommentRow(data.comment);
            
            // If editing, remove old comment first
            if (form.action.includes('update')) {
                const oldComment = document.querySelector(`tr[data-review-id="${data.comment.id}"]`);
                if (oldComment) oldComment.remove();
            }
            
            // Add new/updated comment at the top
            commentsList.insertAdjacentHTML('afterbegin', newCommentHtml);
            
            // Reset form and hide it
            form.reset();
            const commentForm = document.getElementById('commentForm');
            commentForm.style.display = 'none';
            const commentButton = document.getElementById('commentButton');
            commentButton.innerHTML = '<i class="im im-plus"></i> Add Comment';
            
            showMessage('Comment ' + (form.action.includes('update') ? 'updated' : 'added') + ' successfully!', 'success');
        } else {
            showMessage(data.error || 'Error saving comment', 'error');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showMessage('Error saving comment', 'error');
    })
    .finally(() => {
        // Reset submitting state
        form.dataset.submitting = 'false';
    });
}

// Add this global event handler for all buttons
function initializeAllButtonHandlers() {
    // Handle all button clicks through event delegation
    document.addEventListener('click', function(e) {
        const target = e.target.closest('button');
        if (!target) return;

        // Prevent double-clicks
        if (target.dataset.processing === 'true') return;
        target.dataset.processing = 'true';
        
        setTimeout(() => {
            target.dataset.processing = 'false';
        }, 500); // Prevent rapid clicking

        // Handle different button types
        if (target.id === 'commentButton') {
            handleCommentClick();
        } else if (target.classList.contains('edit-btn')) {
            const commentText = target.closest('tr').querySelector('p').textContent;
            editComment(target.dataset.id, commentText);
        } 
    });
}

// Update the DOMContentLoaded event listener
document.addEventListener('DOMContentLoaded', function() {
    loadInitialComments();
    initializeAllButtonHandlers();
    
    // Add form submit handler
    const reviewForm = document.getElementById('reviewForm');
    if (reviewForm) {
        reviewForm.removeEventListener('submit', handleSubmit);  // Remove any existing handlers
        reviewForm.addEventListener('submit', handleSubmit);     // Add single handler
    }
});

// Update editComment function to use event delegation
function editComment(reviewId, comment) {
    if (!isAuthenticated) {
        window.location.href = loginUrl;
        return;
    }
    
    const commentForm = document.getElementById('commentForm');
    const form = document.getElementById('reviewForm');
    const commentButton = document.getElementById('commentButton');
    const textarea = form.querySelector('textarea');
    
    // Show the form and populate textarea
    commentForm.style.display = 'block';
    textarea.value = comment;
    
    // Update form action
    form.action = `/review/${reviewId}/update/`;
    
    // Update main button
    commentButton.innerHTML = '<i class="im im-edit"></i> Update Comment';
}

// Remove individual onclick handlers from other functions
function handleCommentClick() {
    if (!isAuthenticated) {
        window.location.href = loginUrl;
        return;
    }
    
    const commentForm = document.getElementById('commentForm');
    const form = document.getElementById('reviewForm');
    const commentButton = document.getElementById('commentButton');
    const textarea = form.querySelector('textarea');
    
    if (commentForm.style.display === 'none' || !commentForm.style.display) {
        commentForm.style.display = 'block';
        form.reset();
        form.action = addReviewUrl;
        commentButton.innerHTML = '<i class="im im-plus"></i> Submit Comment';
    } else if (textarea.value.trim()) {
        form.dispatchEvent(new Event('submit'));
    } else {
        commentForm.style.display = 'none';
        commentButton.innerHTML = '<i class="im im-plus"></i> Add Comment';
    }
}

// Add this function to load initial comments
function loadInitialComments() {
    const commentsList = document.querySelector('.settings__table');
    if (window.initialComments && window.initialComments.length > 0) {
        const commentsHtml = window.initialComments
            .map(comment => createCommentRow(comment))
            .join('');
        commentsList.innerHTML = commentsHtml;
    }
}



function handleDeleteComment(event) {
    event.preventDefault();
    const form = event.target;
    const popup = form.closest('.delete-popup');
    const commentId = popup.dataset.commentId;
    
    fetch(form.action, {
        method: 'POST',
        headers: {
            'X-CSRFToken': csrfToken
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Remove comment from DOM
            const commentElement = document.querySelector(`tr[data-review-id="${commentId}"]`);
            if (commentElement) {
                commentElement.remove();
            }
            // Use the global hideDeleteConfirmation function from delete_object.html
            hideDeleteConfirmation();
            showMessage('Comment deleted successfully!', 'success');
            
            // Reset the comment form and button
            const commentForm = document.getElementById('commentForm');
            const commentButton = document.getElementById('commentButton');
            
            if (commentForm) {
                commentForm.style.display = 'none';
                const form = document.getElementById('reviewForm');
                if (form) {
                    form.reset();
                    form.action = addReviewUrl;
                }
            }
            
            if (commentButton) {
                commentButton.innerHTML = '<i class="im im-plus"></i> Add Comment';
            }
        } else {
            showMessage(data.error || 'Error deleting comment', 'error');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showMessage('Error deleting comment', 'error');
    });
}

// Remove onsubmit attribute from the form in HTML and handle it in JavaScript
function initializeFormHandlers() {
    const form = document.getElementById('reviewForm');
    if (form) {
        form.removeAttribute('onsubmit');
        form.addEventListener('submit', handleSubmit);
    }
}

