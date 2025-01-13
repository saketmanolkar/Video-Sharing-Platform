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

function initializeHeatmapChart(chartData) {
    const heatmapCanvas = document.getElementById('heatmapChart');
    
    if (heatmapChart) {
        heatmapChart.destroy();
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
                pointRadius: 8,  // Increased point size
                backgroundColor: context => {
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
        responsive: true,
        maintainAspectRatio: true,
        aspectRatio: 1.5,
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
        }
    };

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

// Keep the original initialization method
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
};
