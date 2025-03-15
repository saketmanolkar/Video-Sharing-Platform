// Create a new file: static/js/inactivity_monitor.js
//Connect it to the main.html

class InactivityMonitor {
    constructor(timeoutMinutes = 30) {
        this.timeoutMinutes = timeoutMinutes;
        this.timeoutId = null;
        this.events = [
            'mousemove',
            'mousedown',
            'keypress',
            'DOMMouseScroll',
            'mousewheel',
            'touchmove',
            'MSPointerMove',
            'scroll'
        ];
        
        this.startMonitoring();
    }

    resetTimer() {
        if (this.timeoutId) {
            clearTimeout(this.timeoutId);
        }

        this.timeoutId = setTimeout(() => {
            this.handleInactivity();
        }, this.timeoutMinutes * 60 * 1000);
    }

    async handleInactivity() {
        try {
            const response = await fetch('/users/logout/?timeout=true', {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                }
            });

            if (response.ok) {
                window.location.replace('/users/login-register/');
            }
        } catch (error) {
            console.error('Logout failed:', error);
        }
    }

    startMonitoring() {
        this.resetTimer();
        this.events.forEach(event => {
            document.addEventListener(event, () => this.resetTimer());
        });
    }
}