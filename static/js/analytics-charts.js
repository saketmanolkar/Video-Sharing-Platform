let currentChart = null;
let likesChart = null;
let commentsChart = null;
let heatmapChart = null;

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

function initializeGrowthMiniChart(growthData) {
    const miniChartCanvas = document.getElementById('followerGrowthMiniChart');
    if (!miniChartCanvas) return;

    new Chart(miniChartCanvas, {
        type: 'line',
        data: {
            labels: growthData.dates,
            datasets: [{
                label: 'New Followers',
                data: growthData.values,
                borderColor: '#4285f4',
                backgroundColor: 'rgba(66, 133, 244, 0.1)',
                tension: 0.4,
                fill: true,
                pointRadius: 3,
                pointBackgroundColor: 'rgba(66, 133, 244, 0.1)'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                x: {
                    display: false
                },
                y: {
                    display: false,
                    beginAtZero: true
                }
            }
        }
    });
}

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
        
        // Create arrays only for hours that have data
        const filteredLabels = [];
        const filteredData = [];
        selectedData.labels.forEach((label, index) => {
            if (selectedData.data[index] > 0) {
                const hour = parseInt(label);
                if (hour === 0) filteredLabels.push('12 AM');
                else if (hour === 12) filteredLabels.push('12 PM');
                else if (hour < 12) filteredLabels.push(`${hour} AM`);
                else filteredLabels.push(`${hour-12} PM`);
                filteredData.push(selectedData.data[index]);
            }
        });

        return new Chart(chartCanvas, {
            type: 'bar',
            data: {
                labels: filteredLabels,  // These are already formatted (12 AM, 1 AM, etc)
                datasets: [{
                    label: 'Hourly Views',
                    data: filteredData,
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

function initializeHeatmapChart(chartData) {
    const heatmapCanvas = document.getElementById('heatmapChart');
    
    if (heatmapChart) {
        heatmapChart.destroy();
    }

    if (!chartData || !chartData.activity_data) {
        console.log('No activity data for heatmap');
        return;
    }

    const activityData = chartData.activity_data;
    
    const hours = [
        '12AM', '1AM', '2AM', '3AM', '4AM', '5AM', '6AM', '7AM', '8AM', '9AM', '10AM', '11AM',
        '12PM', '1PM', '2PM', '3PM', '4PM', '5PM', '6PM', '7PM', '8PM', '9PM', '10PM', '11PM'
    ];
    
    const days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];

    heatmapChart = new Chart(heatmapCanvas, {
        type: 'scatter',
        data: {
            datasets: [{
                data: Object.entries(activityData).flatMap(([day, hours]) => 
                    Object.entries(hours).map(([hour, value]) => ({
                        x: hour,
                        y: day,
                        v: value
                    }))
                ),
                pointStyle: 'rect',
                pointRadius: 8,
                backgroundColor: function(context) {
                    if (!context.raw) return 'rgba(33, 150, 243, 0.4)';
                    const value = context.raw.v;
                    return value > 30 ? 'rgba(33, 150, 243, 0.9)' : 'rgba(33, 150, 243, 0.4)';
                },
                borderColor: 'transparent'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            layout: {
                padding: {
                    left: -10,
                    right: 15,
                    top: 0,
                    bottom: 25
                }
            },
            plugins: {
                legend: { display: false },
                title: { display: false },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const point = context.raw;
                            return `${point.v.toFixed(1)} mins`;
                        }
                    }
                }
            },
            scales: {
                y: {
                    type: 'category',
                    labels: days,
                    grid: {
                        color: 'rgba(0, 0, 0, 0.05)',
                        lineWidth: 1,
                        drawTicks: false,
                        offset: false,    // Ensure no grid offset
                        drawBorder: false // Remove border which might add space
                    },
                    ticks: {
                        font: { size: 11 },
                        padding: 10,
                        crossAlign: 'center',
                        textBaseline: 'middle'
                    },
                    offset: false,
                    position: 'left',
                    border: {
                        display: false    // Remove axis border
                    }
                },
                x: {
                    type: 'category',
                    labels: hours,
                    grid: {
                        color: 'rgba(0, 0, 0, 0.05)',
                        lineWidth: 1
                    },
                    ticks: {
                        font: { size: 10 },
                        maxRotation: 0,
                        autoSkip: false,
                        padding: 8  // Increased padding between ticks and axis
                    },
                    afterFit: (scale) => {
                        scale.height = 35;  // Increased height for x-axis to prevent cutoff
                    },
                    border: {
                        display: false    // Remove axis border
                    }
                }
            }
        }
    });
}

// Move this outside as a separate function
function initializeFollowerCharts(followerData) {
    const pieChartOptions = {
        responsive: false,
        maintainAspectRatio: false,
        width: 172,  // Match container width
        height: 114, // Match container height
        layout: {
            padding: {
                top: 0,
                right: 0,
                bottom: 0,  // Exact legend height from debug
                left: 0
            }
        },
        plugins: {
            legend: {
                position: 'bottom',
                labels: {
                    boxWidth: 12,
                    font: { size: 10 },
                    padding: 0
                },
                title: {
                    display: true,
                    font: { size: 12 }
                }
            }
        },
        animation: {
            onComplete: function(animation) {
                const chart = animation.chart;
                const canvas = chart.canvas;
                const chartArea = chart.chartArea;
                const container = canvas.parentNode;

                console.log(`${canvas.id} detailed dimensions:`, {
                    // Canvas properties
                    canvas: {
                        width: canvas.width,
                        height: canvas.height,
                        style: {
                            width: canvas.style.width,
                            height: canvas.style.height
                        }
                    },
                    // Chart area (where the actual pie is drawn)
                    chartArea: {
                        top: chartArea.top,
                        right: chartArea.right,
                        bottom: chartArea.bottom,
                        left: chartArea.left,
                        width: chartArea.width,
                        height: chartArea.height
                    },
                    // Container dimensions
                    container: {
                        width: container.offsetWidth,
                        height: container.offsetHeight,
                        clientWidth: container.clientWidth,
                        clientHeight: container.clientHeight
                    },
                    // Computed ratios
                    ratios: {
                        aspectRatio: canvas.width / canvas.height,
                        chartAreaRatio: chartArea.width / chartArea.height,
                        containerRatio: container.offsetWidth / container.offsetHeight
                    },
                    // Legend space
                    legend: {
                        position: chart.options.plugins.legend.position,
                        height: chart.legend.height,
                        width: chart.legend.width
                    }
                });
            }
        }
    };

    // Add CSS to force container size
    const pieCharts = ['commentsPie', 'dislikesPie', 'likesPie', 'viewsPie'];
    pieCharts.forEach(chartId => {
        const canvas = document.getElementById(chartId);
        if (canvas) {
            canvas.style.width = '172px';
            canvas.style.height = '114px';
        }
    });

    // Comments Distribution
    new Chart(document.getElementById('commentsPie'), {
        type: 'pie',
        data: {
            labels: ['Follower Comments', 'Non-Follower Comments'],
            datasets: [{
                data: [
                    followerData.engagement_breakdown.comments.follower_count,
                    followerData.engagement_breakdown.comments.non_follower_count
                ],
                backgroundColor: ['#4285f4', '#34A853']
            }]
        },
        options: {
            ...pieChartOptions,
            plugins: {
                ...pieChartOptions.plugins,
                title: {
                    ...pieChartOptions.plugins.title,
                    text: 'Comments Distribution'
                }
            }
        }
    });

    // Dislikes Distribution
    new Chart(document.getElementById('dislikesPie'), {
        type: 'pie',
        data: {
            labels: ['Follower Dislikes', 'Non-Follower Dislikes'],
            datasets: [{
                data: [
                    followerData.engagement_breakdown.dislikes.follower_count,
                    followerData.engagement_breakdown.dislikes.non_follower_count
                ],
                backgroundColor: ['#4285f4', '#34A853']
            }]
        },
        options: {
            ...pieChartOptions,
            plugins: {
                ...pieChartOptions.plugins,
                title: {
                    ...pieChartOptions.plugins.title,
                    text: 'Dislikes Distribution'
                }
            }
        }
    });

    // Likes Distribution
    new Chart(document.getElementById('likesPie'), {
        type: 'pie',
        data: {
            labels: ['Follower Likes', 'Non-Follower Likes'],
            datasets: [{
                data: [
                    followerData.engagement_breakdown.likes.follower_count,
                    followerData.engagement_breakdown.likes.non_follower_count
                ],
                backgroundColor: ['#4285f4', '#34A853']
            }]
        },
        options: {
            ...pieChartOptions,
            plugins: {
                ...pieChartOptions.plugins,
                title: {
                    ...pieChartOptions.plugins.title,
                    text: 'Likes Distribution'
                }
            }
        }
    });

    // Views Distribution
    new Chart(document.getElementById('viewsPie'), {
        type: 'pie',
        data: {
            labels: ['Follower Views', 'Non-Follower Views'],
            datasets: [{
                data: [
                    followerData.engagement_breakdown.views.follower_count,
                    followerData.engagement_breakdown.views.non_follower_count
                ],
                backgroundColor: ['#4285f4', '#34A853']
            }]
        },
        options: {
            ...pieChartOptions,
            plugins: {
                ...pieChartOptions.plugins,
                title: {
                    ...pieChartOptions.plugins.title,
                    text: 'Views Distribution'
                }
            }
        }
    });
}

// Function to initialize the Average Watch Time chart
function initializeAverageWatchTimeChart(averageWatchTimes) {
    const averageWatchTimeCanvas = document.getElementById('averageWatchTimeChart');
    
    if (!averageWatchTimeCanvas) return;

    const labels = averageWatchTimes.map(video => video.video_title);
    const data = averageWatchTimes.map(item => item.avg_watch_time);

    new Chart(averageWatchTimeCanvas, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Average Watch Time (mins)',
                data: data,
                backgroundColor: 'rgba(75, 192, 192, 0.8)',
                borderColor: 'rgb(75, 192, 192)',
                borderWidth: 1,
                barPercentage: 0.7,
                categoryPercentage: 0.8
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

// Function to initialize the Completion Rate chart
function initializeCompletionRateChart(completionRates) {
    const completionRateCanvas = document.getElementById('completionRateChart');
    
    if (!completionRateCanvas) return;

    const labels = completionRates.map(video => video.video_title);
    const data = completionRates.map(video => video.completion_rate);

    new Chart(completionRateCanvas, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Completion Rate (%)',
                data: data,
                backgroundColor: 'rgba(255, 159, 64, 0.8)',  // Changed to orange
                borderColor: 'rgb(255, 159, 64)',           // Changed to orange
                borderWidth: 1,
                barPercentage: 0.7,
                categoryPercentage: 0.8
            }]
        },
        options: {
            ...commonOptions,
            scales: {
                y: {
                    beginAtZero: true,
                    grid: {
                        color: 'rgba(0, 0, 0, 0.1)'
                    },
                    ticks: {
                        callback: function(value) {
                            return value + '%';  // Add percentage symbol to y-axis
                        }
                    }
                },
                x: {
                    grid: {
                        display: false
                    }
                }
            },
            plugins: {
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return `Completion Rate: ${context.parsed.y.toFixed(1)}%`;
                        }
                    }
                }
            }
        }
    });
}

// Update the original initializeCharts function to include the average watch time chart
const originalInitializeCharts = initializeCharts;
initializeCharts = function(chartData) {
    originalInitializeCharts(chartData);
    initializeLikesChart(chartData);
    initializeCommentsChart(chartData);
    initializeHeatmapChart(chartData);
    if (chartData.mini_chart_data) {
        initializeGrowthMiniChart(JSON.parse(chartData.mini_chart_data));
    }
    if (chartData.follower_analytics) {
        initializeFollowerCharts(chartData.follower_analytics);
    }
    if (chartData.watch_time_data) {
        initializeAverageWatchTimeChart(chartData.watch_time_data);
    }
    if (chartData.completion_rates) {
        initializeCompletionRateChart(chartData.completion_rates);
    }
};