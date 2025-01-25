let currentChart = null;
let likesChart = null;
let commentsChart = null;

// Move commonOptions outside so all functions can access it
const commonOptions = {
    responsive: true,
    maintainAspectRatio: false,
    scales: {
        x: {
            grid: {
                color: 'rgba(0, 0, 0, 0.05)'
            }
        },
        y: {
            grid: {
                color: 'rgba(0, 0, 0, 0.05)'
            },
            beginAtZero: true
        }
    },
    plugins: {
        legend: {
            position: 'top'
        }
    }
};

function initializeCharts(chartData) {
    // Views chart initialization
    const chartCanvas = document.getElementById('analyticsChart');
    const videoSelector = document.getElementById('videoSelector');
    const navButtons = document.querySelectorAll('.chart-nav-btn');
    
    // Views Chart Functions
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
            options: commonOptions
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
            options: commonOptions
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
                    backgroundColor: 'rgba(75, 192, 192, 0.8)',
                    borderColor: 'rgb(75, 192, 192)',
                    borderWidth: 0,
                    categoryPercentage: 0.8,
                    barPercentage: 0.7,
                    barThickness: 'flex'
                }]
            },
            options: {
                ...commonOptions,
                scales: {
                    y: {
                        beginAtZero: true,
                        grid: {
                            color: 'rgba(0, 0, 0, 0.1)'
                        }
                    },
                    x: {
                        grid: {
                            display: false
                        }
                    }
                }
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

    // Initialize views chart
    switchChart('total');

    // Add event listeners for views chart
    navButtons.forEach(button => {
        button.addEventListener('click', () => {
            navButtons.forEach(btn => btn.classList.remove('active'));
            button.classList.add('active');
            switchChart(button.dataset.chart);
        });
    });

    if (videoSelector) {
        videoSelector.addEventListener('change', () => {
            const activeButton = document.querySelector('.chart-nav-btn.active');
            switchChart(activeButton.dataset.chart, videoSelector.value);
        });
    }
}

// Separate functions for likes and comments charts
function initializeLikesChart(chartData) {
    console.log('Initializing likes/dislikes chart...');
    const likesCanvas = document.getElementById('likesChart');
    
    if (likesChart) {
        likesChart.destroy();
    }

    const likesData = typeof chartData.likes_data === 'string' 
        ? JSON.parse(chartData.likes_data) 
        : chartData.likes_data;
    
    likesChart = new Chart(likesCanvas, {
        type: 'bar',
        data: {
            labels: likesData.labels,
            datasets: [
                {
                    label: 'Likes',
                    data: likesData.data.likes,
                    backgroundColor: 'rgba(75, 192, 128, 0.85)',  // Slightly more opaque green
                    borderColor: 'rgb(75, 192, 128)',
                    borderWidth: 1,
                    stack: 'Stack 0',
                    barPercentage: 0.7,  // Control bar width
                    categoryPercentage: 0.8
                },
                {
                    label: 'Dislikes',
                    data: likesData.data.dislikes,
                    backgroundColor: 'rgba(255, 99, 132, 0.85)',  // Slightly more opaque red
                    borderColor: 'rgb(255, 99, 132)',
                    borderWidth: 1,
                    stack: 'Stack 0',
                    barPercentage: 0.7,
                    categoryPercentage: 0.8
                }
            ]
        },
        options: {
            ...commonOptions,
            scales: {
                x: {
                    stacked: true,
                    grid: {
                        display: false
                    }
                },
                y: {
                    stacked: true,
                    beginAtZero: true,
                    grid: {
                        color: 'rgba(0, 0, 0, 0.05)'
                    }
                }
            },
            plugins: {
                legend: {
                    position: 'top',
                    labels: {
                        usePointStyle: true,  // Makes legend markers round
                        padding: 15
                    }
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            let label = context.dataset.label || '';
                            if (label) {
                                label += ': ';
                            }
                            label += context.parsed.y;
                            return label;
                        }
                    }
                }
            },
            // Add value labels on the bars
            plugins: [{
                afterDraw: function(chart) {
                    var ctx = chart.ctx;
                    chart.data.datasets.forEach(function(dataset, datasetIndex) {
                        var meta = chart.getDatasetMeta(datasetIndex);
                        meta.data.forEach(function(bar, index) {
                            var data = dataset.data[index];
                            if (data > 0) {  // Only show label if value is greater than 0
                                ctx.fillStyle = 'rgb(255, 255, 255)';
                                ctx.textAlign = 'center';
                                ctx.textBaseline = 'middle';
                                var position = bar.tooltipPosition();
                                ctx.fillText(data, position.x, position.y);
                            }
                        });
                    });
                }
            }]
        }
    });
}

function initializeCommentsChart(chartData) {
    const commentsCanvas = document.getElementById('commentsChart');
    const commentsChart = new Chart(commentsCanvas, {
        type: 'bar',
        data: {
            labels: chartData.comments_data.labels,
            datasets: [{
                label: 'Comments per Video',
                data: chartData.comments_data.data,
                backgroundColor: 'rgba(147, 112, 219, 0.8)',
                borderColor: 'rgb(147, 112, 219)',
                borderWidth: 0,
                categoryPercentage: 0.8,
                barPercentage: 0.7,
                barThickness: 'flex'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true,
                    grid: {
                        color: 'rgba(0, 0, 0, 0.1)'
                    }
                },
                x: {
                    grid: {
                        display: false
                    }
                }
            }
        }
    });
}

// Extend the initialization
const originalInitializeCharts = initializeCharts;
initializeCharts = function(chartData) {
    originalInitializeCharts(chartData);
    initializeLikesChart(chartData);
    initializeCommentsChart(chartData);
};