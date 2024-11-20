function createCommentRow(comment) {
    return `
        <tr data-review-id="${comment.id}">
            <td class="settings__tableInfo">
                <h4>${comment.username}</h4>
                <p>${comment.comment}</p>
            </td>
            <td class="settings__tableActions">
                ${comment.is_owner ? `
                    <button class="tag tag--pill tag--main settings__btn" 
                            onclick="editComment('${comment.id}', '${comment.comment}')">
                        <i class="im im-edit"></i> Edit
                    </button>
                    <button class="tag tag--pill tag--main settings__btn" 
                            onclick="showDeleteConfirmation('${comment.id}', '${comment.comment}')">
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
            
            // Reset form
            form.reset();
            toggleCommentForm();
            showMessage('Comment ' + (form.action.includes('update') ? 'updated' : 'added') + ' successfully!', 'success');
        } else {
            showMessage(data.error || 'Error saving comment', 'error');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showMessage('Error saving comment', 'error');
    });
}

// Add this function to handle the Add Comment button click
function handleCommentClick() {
    if (!isAuthenticated) {
        window.location.href = loginUrl;
        return;
    }
    
    const commentForm = document.getElementById('commentForm');
    const form = document.getElementById('reviewForm');
    const commentButton = document.getElementById('commentButton');
    
    if (commentForm.style.display === 'none') {
        // Show form
        commentForm.style.display = 'block';
        form.action = addReviewUrl;
        commentButton.innerHTML = '<i class="im im-plus"></i> Submit Comment';
    } else {
        // If form is visible, submit it
        const textarea = form.querySelector('textarea');
        if (textarea.value.trim()) {
            form.dispatchEvent(new Event('submit'));
        } else {
            // Hide form if empty
            commentForm.style.display = 'none';
            form.reset();
            commentButton.innerHTML = '<i class="im im-plus"></i> Add Comment';
        }
    }
}

// Update editComment function to handle submission
function editComment(reviewId, comment) {
    if (!isAuthenticated) {
        window.location.href = loginUrl;
        return;
    }
    
    const commentForm = document.getElementById('commentForm');
    const form = document.getElementById('reviewForm');
    const commentButton = document.getElementById('commentButton');
    
    // Show the form
    commentForm.style.display = 'block';
    
    // Update form action and content
    form.action = `/review/${reviewId}/update/`;
    form.querySelector('textarea').value = comment;
    
    // Update main button and make it submit on click
    commentButton.innerHTML = '<i class="im im-edit"></i> Update Comment';
    commentButton.onclick = function() {
        if (form.querySelector('textarea').value.trim()) {
            form.dispatchEvent(new Event('submit'));
        }
    };
}

// Add this function since it's being used in handleSubmit
function toggleCommentForm() {
    const commentForm = document.getElementById('commentForm');
    const form = document.getElementById('reviewForm');
    const commentButton = document.getElementById('commentButton');
    
    // Hide form and reset
    commentForm.style.display = 'none';
    form.reset();
    form.action = addReviewUrl;
    commentButton.innerHTML = '<i class="im im-plus"></i> Add Comment';
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

// Call this when the page loads
document.addEventListener('DOMContentLoaded', function() {
    loadInitialComments();
});

// Delete Comment Functions
function showDeleteConfirmation(commentId, commentText) {
    console.log('Using delete template:', document.querySelectorAll('.delete-popup').length);
    
    const overlay = document.querySelector('.alert-overlay');
    const popup = document.querySelector('.delete-popup');
    const messageElement = document.querySelector('.delete-popup__message strong');
    
    // Update message and store comment ID
    messageElement.textContent = commentText;
    popup.dataset.commentId = commentId;
    
    // Show overlay and popup
    overlay.style.display = 'block';
    popup.style.display = 'block';
    
    // Update form action and ensure it uses our handler
    const form = popup.querySelector('form');
    form.action = `/review/${commentId}/delete/`;
    form.onsubmit = handleDeleteComment;
}

function hideDeleteConfirmation() {
    const overlay = document.querySelector('.alert-overlay');
    const popup = document.querySelector('.delete-popup');
    
    overlay.style.display = 'none';
    popup.style.display = 'none';
}

function handleDeleteComment(event) {
    event.preventDefault();
    const form = event.target;
    const commentId = form.closest('.delete-popup').dataset.commentId;
    
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
            hideDeleteConfirmation();
            showMessage('Comment deleted successfully!', 'success');
        } else {
            showMessage(data.error || 'Error deleting comment', 'error');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showMessage('Error deleting comment', 'error');
    });
}

