let currentChart = null;

function initializeCharts(chartData) {
    const chartCanvas = document.getElementById('analyticsChart');
    const videoSelector = document.getElementById('videoSelector');
    const navButtons = document.querySelectorAll('.chart-nav-btn');

    function createTotalViewsChart() {
        return new Chart(chartCanvas, {
            type: 'line',
            data: {
                labels: chartData.total.labels,
                datasets: [{
                    label: 'Views',
                    data: chartData.total.data,
                    borderColor: 'rgb(75, 192, 192)',
                    backgroundColor: 'rgba(75, 192, 192, 0.1)',
                    tension: 0.3,
                    fill: true
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false
            }
        });
    }

    function createDailyViewsChart(videoId) {
        const selectedData = chartData.daily[videoId];
        return new Chart(chartCanvas, {
            type: 'line',
            data: {
                labels: selectedData.labels,
                datasets: [{
                    label: 'Daily Views',
                    data: selectedData.data,
                    borderColor: 'rgb(54, 162, 235)',
                    backgroundColor: 'rgba(54, 162, 235, 0.1)',
                    tension: 0.3,
                    fill: true
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false
            }
        });
    }

    function createHourlyViewsChart(videoId) {
        const selectedData = chartData.hourly[videoId];
        return new Chart(chartCanvas, {
            type: 'bar',
            data: {
                labels: selectedData.labels,
                datasets: [{
                    label: 'Hourly Views',
                    data: selectedData.data,
                    backgroundColor: 'rgba(75, 192, 192, 0.5)',
                    borderColor: 'rgb(75, 192, 192)',
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false
            }
        });
    }

    function switchChart(chartType, videoId = null) {
        if (currentChart) {
            currentChart.destroy();
        }

        const selector = document.querySelector('.chart-selector');
        
        switch(chartType) {
            case 'total':
                selector.style.display = 'none';
                currentChart = createTotalViewsChart();
                break;
            case 'daily':
                selector.style.display = 'block';
                currentChart = createDailyViewsChart(videoId || videoSelector.value);
                break;
            case 'hourly':
                selector.style.display = 'block';
                currentChart = createHourlyViewsChart(videoId || videoSelector.value);
                break;
        }
    }

    // Initialize with total views chart
    switchChart('total');

    // Add click handlers to navigation buttons
    navButtons.forEach(button => {
        button.addEventListener('click', () => {
            navButtons.forEach(btn => btn.classList.remove('active'));
            button.classList.add('active');
            switchChart(button.dataset.chart);
        });
    });

    // Add change handler to video selector
    if (videoSelector) {
        videoSelector.addEventListener('change', () => {
            const activeButton = document.querySelector('.chart-nav-btn.active');
            switchChart(activeButton.dataset.chart, videoSelector.value);
        });
    }
}