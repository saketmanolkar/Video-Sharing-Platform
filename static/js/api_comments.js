class ApiCommentHandler {
    constructor() {
        if (window.commentHandler) {
            window.commentHandler.cleanup();
        }
        window.commentHandler = this;

        this.currentUser = false;
        this.currentEditId = null;
        this.commentButton = document.getElementById('commentButton');
        this.commentForm = document.getElementById('commentForm');
        this.messageContainer = null;
        this.isEditing = false;
        
        // Find the comments container
        this.commentsTable = document.querySelector('.settings__table tbody');
        
        this.checkAuthentication();
        this.setupMessageContainer();
        this.setupEventListeners();
        this.loadExistingComments();
    }

    init() {
        this.commentButton = document.getElementById('commentButton');
        this.commentForm = document.getElementById('commentForm');
        this.commentsTable = document.querySelector('.settings table tbody');
        
        // Create table if it doesn't exist
        if (!this.commentsTable) {
            const settingsDiv = document.querySelector('.settings');
            if (settingsDiv) {
                const table = document.createElement('table');
                const tbody = document.createElement('tbody');
                table.className = 'settings__table';
                table.appendChild(tbody);
                settingsDiv.appendChild(table);
                this.commentsTable = tbody;
            }
        }

        this.checkAuthentication();
        this.setupMessageContainer();
        this.setupEventListeners();
        this.loadExistingComments();
    }

    setupMutationObserver() {
        // Watch for DOM changes
        const observer = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                if (mutation.type === 'childList' && mutation.removedNodes.length > 0) {
                    // Check if our elements were removed
                    if (!document.contains(this.commentButton) || 
                        !document.contains(this.commentForm) || 
                        !document.contains(this.commentsTable)) {
                        console.log('Critical elements removed, reinitializing...');
                        this.init();
                    }
                }
            });
        });

        // Start observing the document with the configured parameters
        observer.observe(document.body, { childList: true, subtree: true });
    }

    cleanup() {
        // Remove event listeners
        const addCommentBtn = document.querySelector('.add-comment-btn');
        if (addCommentBtn) {
            addCommentBtn.replaceWith(addCommentBtn.cloneNode(true));
        }
        if (this.commentForm) {
            this.commentForm.replaceWith(this.commentForm.cloneNode(true));
        }
    }

    setupEventListeners() {
        // Comment button handler - single button for both show/submit
        if (this.commentButton) {
            this.commentButton.addEventListener('click', async (e) => {
                e.preventDefault();
                
                if (!this.currentUser) {
                    this.showMessage('Please log in to comment', 'error');
                    return;
                }

                const textarea = document.querySelector('textarea[name="comment"]');
                if (!textarea) return;

                // If form is hidden, show it
                if (this.commentForm.style.display === 'none' || !this.commentForm.style.display) {
                    this.commentForm.style.display = 'block';
                    textarea.focus();
                    this.commentButton.innerHTML = '<i class="im im-plus"></i> Submit Comment';
                    return;
                }

                // If form is visible, handle submission
                const comment = textarea.value.trim();
                if (!comment) {
                    this.showMessage('Please write a comment first', 'error');
                    return;
                }

                // Handle edit or add
                if (this.currentEditId) {
                    await this.updateComment(this.currentEditId, comment);
                } else {
                    await this.addComment(comment);
                }

                // Reset form
                textarea.value = '';
                this.commentForm.style.display = 'none';
                this.commentButton.innerHTML = '<i class="im im-plus"></i> Add Comment';
                this.currentEditId = null;
            });
        }

        // Event delegation for edit/delete buttons
        document.addEventListener('click', async (e) => {
            if (!this.currentUser) return;

            const editBtn = e.target.closest('.edit-btn');
            const deleteBtn = e.target.closest('.delete-btn');

            if (editBtn) {
                e.preventDefault();
                const reviewId = editBtn.dataset.reviewId;
                if (!reviewId) return;
                
                const row = document.querySelector(`tr[data-review-id="${reviewId}"]`);
                if (!row) return;
                
                const currentText = row.querySelector('.settings__tableInfo p').textContent;
                this.setupEditMode(reviewId, currentText);
            }

            if (deleteBtn) {
                e.preventDefault();
                const reviewId = deleteBtn.dataset.reviewId;
                if (!reviewId) return;
                
                const row = document.querySelector(`tr[data-review-id="${reviewId}"]`);
                if (!row) return;
                
                const commentText = row.querySelector('.settings__tableInfo p').textContent;
                showDeleteConfirmation(reviewId, commentText, 'comment');
            }
        });
    }

    checkAuthentication() {
        const authElement = document.querySelector('meta[name="user_authenticated"]');
        this.currentUser = authElement && authElement.content === 'true';
    }

    async getAuthHeaders() {
        const token = await AuthHandler.getToken();
        if (!token) {
            console.error('No authentication token found');
            return null;
        }
        return {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
        };
    }

    setupEditMode(reviewId, currentText) {
        this.currentEditId = reviewId;
        const textarea = this.commentForm.querySelector('textarea[name="comment"]');
        textarea.value = currentText;
        this.commentForm.style.display = 'block';
        this.commentButton.innerHTML = '<i class="im im-edit"></i> Update Comment';
        textarea.focus();
    }

    resetForm() {
        const textarea = this.commentForm.querySelector('textarea[name="comment"]');
        textarea.value = '';
        this.commentForm.style.display = 'none';
        this.commentButton.innerHTML = '<i class="im im-plus"></i> Add Comment';
        this.currentEditId = null;
    }

    async updateComment(reviewId, comment) {
        if (!reviewId) {
            console.error('No review ID provided for update');
            return;
        }

        console.log('Updating comment with ID:', reviewId);
        const headers = await this.getAuthHeaders();
        if (!headers) return;

        try {
            const videoId = window.location.pathname.split('/').filter(Boolean).pop();
            const response = await fetch(`/api/projects/${videoId}/reviews/${reviewId}/`, {
                method: 'PUT',
                headers: headers,
                body: JSON.stringify({ comment })
            });

            if (response.ok) {
                const data = await response.json();
                this.showMessage('Comment updated successfully!');
                
                // Update the existing row
                const row = document.querySelector(`tr[data-review-id="${reviewId}"]`);
                if (row) {
                    const commentCell = row.querySelector('.settings__tableInfo p');
                    commentCell.textContent = comment;
                }

                this.resetForm();
            } else {
                const error = await response.json();
                this.showMessage(error.error || 'Error updating comment', 'error');
            }
        } catch (error) {
            console.error('Error:', error);
            this.showMessage('Error updating comment', 'error');
        }
    }

    async addComment(comment) {
        // Ensure we have the latest references
        if (!this.commentsTable) {
            console.log('Comments table not found, reinitializing...');
            this.init();
        }

        const headers = await this.getAuthHeaders();
        if (!headers) return;

        try {
            const videoId = window.location.pathname.split('/').filter(Boolean).pop();
            const response = await fetch(`/api/projects/${videoId}/reviews/`, {
                method: 'POST',
                headers: headers,
                body: JSON.stringify({ comment })
            });

            if (response.ok) {
                const data = await response.json();
                console.log('Received comment data:', data);

                // Handle the nested comment structure
                const commentData = data.comment || data;
                
                // Create and insert the new row
                const newRow = this.createCommentRow(commentData);
                if (newRow) {
                    // Double-check table exists
                    this.commentsTable = this.commentsTable || document.querySelector('.settings table tbody');
                    if (this.commentsTable) {
                        this.commentsTable.insertAdjacentHTML('afterbegin', newRow);
                        this.showMessage('Comment added successfully!');
                    } else {
                        console.error('Comments table not found after recheck');
                    }
                }
            } else {
                const error = await response.json();
                this.showMessage(error.error || 'Error adding comment', 'error');
            }
        } catch (error) {
            console.error('Error:', error);
            this.showMessage('Error adding comment', 'error');
        }
    }

    showMessage(message, type = 'success') {
        if (!this.messageContainer) {
            console.error('Message container not initialized');
            return;
        }

        this.messageContainer.textContent = message;
        this.messageContainer.style.display = 'block';
        this.messageContainer.style.backgroundColor = type === 'success' ? '#4CAF50' : '#f44336';
        this.messageContainer.style.color = 'white';

        // Hide message after 3 seconds
        setTimeout(() => {
            this.messageContainer.style.display = 'none';
        }, 3000);
    }

    setupMessageContainer() {
        // Create message container if it doesn't exist
        let messageContainer = document.querySelector('.message-container');
        if (!messageContainer) {
            messageContainer = document.createElement('div');
            messageContainer.className = 'message-container';
            messageContainer.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                z-index: 1000;
                padding: 15px;
                border-radius: 5px;
                display: none;
                transition: all 0.3s ease;
            `;
            document.body.appendChild(messageContainer);
        }
        this.messageContainer = messageContainer;
    }

    createCommentRow(commentData) {
        console.log('Creating row with data:', commentData);
        
        const escapedComment = commentData.comment.replace(/"/g, '&quot;');
        
        return `
            <tr data-review-id="${commentData.id}">
                <td class="settings__tableInfo">
                    <h4>${commentData.username}</h4>
                    <p>${commentData.comment}</p>
                </td>
                <td class="settings__tableActions">
                    ${this.currentUser && commentData.is_owner ? `
                        <button class="tag tag--pill tag--main settings__btn edit-btn" 
                                data-review-id="${commentData.id}"
                                data-comment="${escapedComment}">
                            <i class="im im-edit"></i> Edit
                        </button>
                        <button class="tag tag--pill tag--main settings__btn delete-btn" 
                                data-review-id="${commentData.id}">
                            <i class="im im-x-mark-circle-o"></i> Delete
                        </button>
                    ` : ''}
                </td>
            </tr>
        `;
    }

    async loadExistingComments() {
        try {
            const videoId = window.location.pathname.split('/').filter(Boolean).pop();
            const headers = await this.getAuthHeaders();
            
            // Make request without headers if not authenticated
            const response = await fetch(`/api/projects/${videoId}/reviews/`, {
                method: 'GET',
                headers: headers || { 'Content-Type': 'application/json' }
            });

            if (response.ok) {
                const comments = await response.json();
                const commentsTable = document.querySelector('.settings__table tbody');
                if (commentsTable) {
                    commentsTable.innerHTML = ''; // Clear existing content
                    comments.forEach(comment => {
                        const commentRow = this.createCommentRow(comment);
                        commentsTable.insertAdjacentHTML('beforeend', commentRow);
                    });
                }
            } else {
                console.error('Failed to load comments');
            }
        } catch (error) {
            console.error('Error loading comments:', error);
        }
    }

    handleDeleteSubmit = async (e) => {
        e.preventDefault();
        e.stopPropagation(); // Stop event bubbling

        const reviewId = e.target.dataset.itemId;
        console.log('Handling delete submit for ID:', reviewId);

        if (!reviewId) {
            console.error('No review ID provided for delete');
            return;
        }

        const headers = await this.getAuthHeaders();
        if (!headers) return;

        try {
            const videoId = window.location.pathname.split('/').filter(Boolean).pop();
            const response = await fetch(`/api/projects/${videoId}/reviews/${reviewId}/`, {
                method: 'DELETE',
                headers: headers
            });

            if (response.ok) {
                this.showMessage('Comment deleted successfully!');
                const row = document.querySelector(`tr[data-review-id="${reviewId}"]`);
                if (row) {
                    row.remove();
                }
                // Close the modal
                const modal = document.getElementById('deleteModal');
                if (modal) {
                    modal.style.display = 'none';
                }
            } else {
                const error = await response.json();
                this.showMessage(error.error || 'Error deleting comment', 'error');
            }
        } catch (error) {
            console.error('Error:', error);
            this.showMessage('Error deleting comment', 'error');
        }
    }
}

function showDeleteConfirmation(itemId, itemName, itemType) {
    const overlay = document.querySelector('.alert-overlay');
    const popup = document.querySelector('.delete-popup');
    if (!popup || !overlay) return;

    // Set the item details
    popup.dataset.commentId = itemId;
    const messageElement = popup.querySelector('.delete-popup__message strong');
    if (messageElement) {
        messageElement.textContent = `${itemType}: "${itemName}"`;
    }

    // Show both overlay and popup
    overlay.style.display = 'flex';
    popup.style.display = 'flex';

    // Handle form submission
    const form = popup.querySelector('form');
    if (form) {
        form.onsubmit = async (e) => {
            e.preventDefault();
            await handleDeleteComment(e);
            overlay.style.display = 'none';
            popup.style.display = 'none';
        };
    }

    // Handle cancel button
    const cancelBtn = popup.querySelector('button:not([type="submit"])');
    if (cancelBtn) {
        cancelBtn.onclick = () => {
            overlay.style.display = 'none';
            popup.style.display = 'none';
        };
    }
}

// Initialize the handler
document.addEventListener('DOMContentLoaded', () => {
    new ApiCommentHandler();
});