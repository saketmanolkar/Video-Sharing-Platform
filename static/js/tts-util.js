// Get CSRF token
function getCsrfToken() {
    const name = 'csrftoken';
    let cookieValue = null;
    if (document.cookie) {
        const cookies = document.cookie.split(';');
        for (let cookie of cookies) {
            cookie = cookie.trim();
            if (cookie.startsWith(name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

let lastKnownButtonState = {
    isGenerating: false,
    audioGenerated: false,
    audioUrl: null
};

// Update TTS button based on audio generation status
function updateTTSButton(isGenerating, audioIsGenerated, audioUrl) {
    const generateTtsBtn = document.querySelector('.generate-tts-btn');
    if (!generateTtsBtn) return;

    // Check if ANY type is generating
    const anyGenerating = ['user', 'video'].some(type => 
        getGeneratingState(type)
    );

    // Get current modal's type
    const currentType = generateTtsBtn.getAttribute('data-report-type');
    const isThisModalGenerating = getGeneratingState(currentType);

    // Disable button if:
    // 1. This modal is generating OR
    // 2. Any other modal is generating
    generateTtsBtn.disabled = isThisModalGenerating || anyGenerating;

    if (audioIsGenerated && audioUrl) {
        // Remove the onclick handler when audio is generated
        generateTtsBtn.onclick = null;
        generateTtsBtn.style.cursor = 'default';  // Remove pointer cursor
        generateTtsBtn.disabled = true;  // Disable the button
        generateTtsBtn.innerHTML = '<i class="fas fa-check"></i> Audio Generated<br>Please Refresh';
        generateTtsBtn.classList.add('generated-state');  // Add class for styling
    } else if (isThisModalGenerating) {
        generateTtsBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Generating...<br>Please wait 😊';
    } else if (anyGenerating && !isThisModalGenerating) {
        generateTtsBtn.innerHTML = '<i class="fas fa-lock"></i> Generation in Progress';
    } else {
        // Reset the button to clickable state
        generateTtsBtn.style.cursor = 'pointer';
        generateTtsBtn.disabled = false;
        generateTtsBtn.innerHTML = '<i class="fas fa-volume-up"></i> Generate<br>Text-to-Speech';
        generateTtsBtn.classList.remove('generated-state');
    }
}

// Function to restore the last known button state
function restoreButtonState() {
    updateTTSButton(
        lastKnownButtonState.isGenerating,
        lastKnownButtonState.audioGenerated,
        lastKnownButtonState.audioUrl
    );
}

// Add this at the top to track generation state
let isCurrentlyGenerating = false;
let currentReportType = null;  // Track which modal we're in

function setGeneratingState(reportType, isGenerating) {
    console.log(`Setting ${reportType} state to:`, isGenerating);
    
    if (!isGenerating) {
        localStorage.removeItem(`tts_generating_${reportType}`);
        console.log(`Removed state for ${reportType}`);
    } else {
        localStorage.setItem(`tts_generating_${reportType}`, 'true');
        console.log(`Set state for ${reportType}`);
    }
    
    // Verify the change
    console.log(`Current state for ${reportType}:`, getGeneratingState(reportType));
}

function getGeneratingState(reportType) {
    return localStorage.getItem(`tts_generating_${reportType}`) === 'true';
}

// Change from const to let
let statusCheckIntervals = {};

function checkTTSStatus(username) {
    console.log('Starting status check...'); 

    fetch(`/api/check-tts-status/${username}/`)
        .then(response => response.json())
        .then(data => {
            console.log('Full API Response:', data);

            const button = document.querySelector('.generate-tts-btn');
            const reportType = button ? button.getAttribute('data-report-type') : null;
            
            if (!reportType) {
                console.log('No report type found, checking both types');
                ['user', 'video'].forEach(type => checkAndClearState(type, data));
            } else {
                console.log(`Checking specific type: ${reportType}`);
                checkAndClearState(reportType, data);
            }
        });
}

function checkAndClearState(reportType, data) {
    const reportData = reportType === 'user' ? data.user_report : data.video_report;
    console.log(`Checking ${reportType}:`, reportData);

    const currentState = getGeneratingState(reportType);
    console.log(`Current state for ${reportType}:`, currentState);

    if (reportData.is_completed && reportData.audio_url && currentState) {
        console.log(`🚨 Clearing state for ${reportType} - audio is ready`);
        localStorage.removeItem(`tts_generating_${reportType}`);
        
        if (statusCheckIntervals[reportType]) {
            console.log(`🛑 Stopping interval for ${reportType}`);
            clearInterval(statusCheckIntervals[reportType]);
            delete statusCheckIntervals[reportType];
        }

        // Force update button if it exists
        const button = document.querySelector('.generate-tts-btn');
        if (button && button.getAttribute('data-report-type') === reportType) {
            updateTTSButton(false, true, reportData.audio_url);
        }
    }
}

// Remove setGeneratingState function and directly use localStorage
function generateSpeech(username, reportType) {
    console.log('🎤 Starting generation:', reportType);
    
    // Directly set localStorage
    localStorage.setItem(`tts_generating_${reportType}`, 'true');
    console.log(`Set generating state for ${reportType}`);
    
    updateTTSButton(true, false, null);

    fetch('/api/generate-speech/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken(),
        },
        body: JSON.stringify({ username, report_type: reportType })
    })
    .then(response => response.json())
    .then(data => {
        statusCheckIntervals[reportType] = setInterval(() => {
            checkTTSStatus(username);
        }, 2000);
    })
    .catch(error => {
        console.error('❌ Error:', error);
        localStorage.removeItem(`tts_generating_${reportType}`);
        updateTTSButton(false, false, null);
    });
}

async function fetchTTSStatus() {
    try {
        const response = await fetch(`/api/check-tts-status/${window.username}/`);
        const data = await response.json();

        if (response.ok) {
            // Update the UI based on the response
            updateTTSButton(false, data.user_report.is_completed, data.user_report.audio_url);
        } else if (response.status === 404) {
            // No report found - this is a normal state when no audio has been generated yet
            console.log('No TTS status found yet - ready to generate');
            updateTTSButton(false, false, null); // Set button to initial state
        } else {
            // Handle other errors
            console.warn('Error fetching TTS status:', data.error);
            updateTTSButton(false, false, null); // Reset button state
        }
    } catch (error) {
        // Handle network errors quietly
        console.log('No TTS status available yet');
        updateTTSButton(false, false, null); // Set button to initial state
    }
}

function openReportModal(reportType) {
    // Check if marked is loaded
    console.log('🔍 Marked library status:', typeof marked !== 'undefined' ? 'Loaded' : 'Not loaded');
    
    currentReportType = reportType;
    console.log('🚀 Opening modal for report type:', reportType);
    
    const timestamp = new Date().getTime();
    const url = `/users/report/${profile.id}?report_type=${reportType}&t=${timestamp}`;
    console.log('📡 Fetching from URL:', url);
    
    fetch(url, {
        headers: {
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache'
        }
    })
    .then(response => {
        console.log('📥 Got response status:', response.status);
        return response.text();
    })
    .then(html => {
        console.log('📝 Got HTML response length:', html.length);
        console.log('📝 First 100 chars of HTML:', html.substring(0, 100));
        
        // Insert the HTML into the modal
        const modalContent = document.getElementById('reportContent');
        modalContent.innerHTML = html;
        console.log('🎯 Inserted HTML into modal');
        
        document.getElementById('reportModal').style.display = 'block';
        
        // Check if this type is currently generating
        const isGenerating = getGeneratingState(reportType);
        const anyGenerating = ['user', 'video'].some(type => 
            getGeneratingState(type)
        );

        console.log(`Modal opened for ${reportType}, this generating: ${isGenerating}, any generating: ${anyGenerating}`);

        // Get the button and update its state immediately
        const button = document.querySelector('.generate-tts-btn');
        if (button) {
            updateTTSButton(isGenerating, false, null);
        }
        
        // Parse markdown after content is inserted
        const markdownElement = document.querySelector('#markdown-content');
        console.log('🔍 Looking for markdown element:', markdownElement ? 'Found' : 'Not found');
        
        if (markdownElement) {
            const content = markdownElement.textContent;
            console.log('📄 Raw content length:', content.length);
            console.log('📄 Raw content preview:', content.substring(0, 100));
            
            try {
                if (typeof marked === 'undefined') {
                    throw new Error('Marked library not loaded');
                }
                
                console.log('🔄 Starting markdown parsing...');
                const htmlContent = marked.parse(content);
                console.log('✅ Parsed HTML length:', htmlContent.length);
                console.log('✅ Parsed HTML preview:', htmlContent.substring(0, 100));
                
                markdownElement.innerHTML = htmlContent;
                console.log('✨ Markdown rendered successfully');
                addMarkdownStyles();
            } catch (error) {
                console.error('❌ Error parsing markdown:', error);
                console.error('Current marked status:', typeof marked);
            }
        } else {
            console.error('❌ Markdown element not found in modal content');
            console.log('📍 Modal content preview:', modalContent.innerHTML.substring(0, 200));
        }
        
        // Then check full status
        checkTTSStatus(window.username);
    })
    .catch(error => {
        console.error('❌ Error in openReportModal:', error);
        console.error(error.stack);
    });

    // Add this right after the openReportModal function
    function addMarkdownStyles() {
        if (document.getElementById('markdown-styles')) return;

        const styleSheet = document.createElement("style");
        styleSheet.id = 'markdown-styles';
        styleSheet.textContent = `
            #markdown-content {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                line-height: 1.6;
                color: #333;
                padding: 1rem;
                font-size: 16px !important; /* Force consistent base font size */
            }
            #markdown-content * {
                font-size: inherit !important; /* Make all elements inherit the base font size */
            }
            #markdown-content h1 {
                font-size: 24px !important;
                margin-bottom: 1rem;
                padding-bottom: 0.3rem;
                border-bottom: 2px solid #eee;
                font-weight: 600;
            }
            #markdown-content h2 {
                font-size: 20px !important;
                margin: 1.5rem 0 1rem;
                font-weight: 600;
            }
            #markdown-content p, 
            #markdown-content li {
                font-size: 16px !important;
                margin: 0.5rem 0;
                line-height: 1.6;
            }
            #markdown-content strong {
                font-weight: 600;
                color: inherit;
            }
            #markdown-content ul {
                margin: 1rem 0;
                padding-left: 2rem;
            }
            #markdown-content em {
                font-style: italic;
            }
            /* Override any existing styles */
            #markdown-content .report-content * {
                font-size: inherit !important;
            }
        `;
        document.head.appendChild(styleSheet);
    }
}

function closeReportModal(event) {
    if (event) {
        event.preventDefault();  // Prevent navigation
    }
    document.getElementById('reportModal').style.display = 'none';
}

// Add a cleanup function
function clearAllGeneratingStates() {
    localStorage.removeItem('tts_generating_user');
    localStorage.removeItem('tts_generating_video');
    console.log('Cleared all generating states');
}

// Only clear intervals on page load, not the states
window.addEventListener('load', () => {
    // Clear any existing intervals
    Object.values(statusCheckIntervals).forEach(interval => clearInterval(interval));
    statusCheckIntervals = {};
    
    // Start checking again if there are any active generations
    const generatingTypes = ['user', 'video'].filter(type => 
        getGeneratingState(type)
    );
    
    console.log('Resuming checks for:', generatingTypes);
    
    // Restart intervals for any active generations
    if (generatingTypes.length > 0) {
        generatingTypes.forEach(type => {
            statusCheckIntervals[type] = setInterval(() => {
                checkTTSStatus(window.username);
            }, 2000);
        });
    }
});