class AuthHandler {
    static clearAuth() {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        localStorage.removeItem('user');
    }

    static async getToken() {
        try {
            let token = localStorage.getItem('access_token');
            
            // Debug logging
            console.log('Current token payload:', token ? 
                JSON.parse(atob(token.split('.')[1])) : 
                'No token'
            );
            
            if (!token) {
                return null;
            }

            return token;
        } catch (error) {
            console.error('Auth error:', error);
            return null;
        }
    }

    static async refreshToken() {
        const refresh = localStorage.getItem('refresh_token');
        if (!refresh) return false;

        try {
            const response = await fetch('/api/token/refresh/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    refresh: refresh
                })
            });

            if (response.ok) {
                const data = await response.json();
                localStorage.setItem('access_token', data.access);
                return true;
            }
            return false;
        } catch (error) {
            console.error('Refresh error:', error);
            return false;
        }
    }

    static async handleLogout() {
        try {
            const response = await fetch('/users/logout/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCsrfToken()
                },
                credentials: 'same-origin'
            });

            const data = await response.json();
            
            // Clear local storage
            this.clearAuth();
            
            // Redirect to login page
            window.location.href = data.redirect || '/users/login-register/';
            
        } catch (error) {
            console.error('Logout error:', error);
            // Fallback redirect
            window.location.href = '/users/login-register/';
        }
    }

    static getCsrfToken() {
        return document.querySelector('[name=csrfmiddlewaretoken]')?.value;
    }
}

// Add event listener to logout button/link
document.addEventListener('DOMContentLoaded', () => {
    const logoutBtn = document.querySelector('.logout-link'); // Update selector as needed
    if (logoutBtn) {
        logoutBtn.addEventListener('click', async (e) => {
            e.preventDefault();
            await AuthHandler.handleLogout();
        });
    }
});