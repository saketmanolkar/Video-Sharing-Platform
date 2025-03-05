// Wait for DOM to be fully loaded
document.addEventListener('DOMContentLoaded', function() {
    // Initialize Box Office Chart
    initBoxOfficeChart();
    
    // Initialize Current Movies Chart
    initMovieChart();
});

// Box Office Chart Initialization
function initBoxOfficeChart() {
    const ctx = document.getElementById('boxOfficeChart').getContext('2d');
    const boxOfficeData = window.boxOfficeData;
    
    // Add colors for each studio
    boxOfficeData.datasets = boxOfficeData.datasets.map(dataset => {
        let color;
        switch(dataset.label) {
            case 'Warner Bros.':
                color = 'rgb(77, 171, 247)';  // Light blue
                break;
            case 'Universal Pictures':
                color = 'rgb(255, 128, 155)';  // Pink
                break;
            case 'Paramount Pictures':
                color = 'rgb(255, 177, 101)';  // Orange
                break;
            case 'Sony Pictures Releasing':
                color = 'rgb(255, 212, 96)';  // Yellow
                break;
            case 'Walt Disney Studios Motion Pictures':
                color = 'rgb(111, 207, 203)';  // Turquoise
                break;
            case 'Total Industry Earnings':
                color = 'rgb(156, 136, 255)';  // Purple
                break;
            default:
                color = '#' + Math.floor(Math.random()*16777215).toString(16);
        }
        return {
            ...dataset,
            borderColor: color,
            backgroundColor: color,
            pointRadius: 4,
            pointHoverRadius: 6,
            borderWidth: 2,
            tension: 0.3  // Makes lines slightly curved
        };
    });

    new Chart(ctx, {
        type: 'line',
        data: boxOfficeData,
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'top',
                    align: 'center',
                    labels: {
                        usePointStyle: true,
                        padding: 20,
                        font: {
                            size: 12
                        }
                    }
                }
            },
            scales: {
                y: {
                    grid: {
                        color: 'rgba(0, 0, 0, 0.1)',
                        drawBorder: false
                    },
                    ticks: {
                        callback: function(value) {
                            if (value >= 1000000000) {
                                return '$' + (value/1000000000).toFixed(1) + 'B';
                            }
                            return '$' + (value/1000000).toFixed(0) + 'M';
                        }
                    }
                },
                x: {
                    grid: {
                        display: false
                    },
                    ticks: {
                        maxRotation: 45,
                        minRotation: 45
                    }
                }
            }
        }
    });
}

// Movie Chart Initialization
function initMovieChart() {
    const data = window.currentMoviesData;
    
    const margin = {top: 40, right: 120, bottom: 40, left: 100};
    const width = 1000 - margin.left - margin.right;
    const height = 520 - margin.top - margin.bottom;
    
    const svg = d3.select("#movieChart")
        .append("svg")
        .attr("width", width + margin.left + margin.right)
        .attr("height", height + margin.top + margin.bottom)
        .append("g")
        .attr("transform", `translate(${margin.left},${margin.top})`);
    
    const x = d3.scaleLinear()
        .domain([0, d3.max(data.daily_gross)])
        .range([0, width]);
    
    const y = d3.scaleBand()
        .domain(data.titles)
        .range([0, height])
        .padding(0.2);

    // Create groups for each bar+poster combination
    const barGroups = svg.selectAll(".bar-group")
        .data(data.daily_gross)
        .enter()
        .append("g")
        .attr("class", "bar-group");

    // Add bars with hover effect
    barGroups.append("rect")
        .attr("class", "bar")
        .attr("x", 0)
        .attr("y", (d, i) => y(data.titles[i]))
        .attr("width", d => x(d))
        .attr("height", y.bandwidth())
        .attr("fill", "rgba(111, 207, 203, 0.8)")
        .style("transition", "all 0.3s ease")
        .on("mouseover", function() {
            d3.select(this)
                .attr("fill", "rgba(111, 207, 203, 1)")
                .attr("filter", "brightness(1.1)");
        })
        .on("mouseout", function() {
            d3.select(this)
                .attr("fill", "rgba(111, 207, 203, 0.8)")
                .attr("filter", "none");
        });

    // Add posters with spacing and hover effect
    barGroups.append("image")
        .attr("class", "poster")
        .attr("x", (d, i) => x(data.daily_gross[i]) + 10)  // 10px spacing after bar
        .attr("y", (d, i) => y(data.titles[i]))
        .attr("width", 40)
        .attr("height", y.bandwidth())
        .attr("href", (d, i) => `https://image.tmdb.org/t/p/w500${data.posters[i]}`)
        .style("transition", "all 0.3s ease")
        .style("cursor", "pointer")
        .on("mouseover", function() {
            d3.select(this)
                .attr("width", 45)  // Slightly larger on hover
                .attr("height", y.bandwidth() * 1.1)
                .style("filter", "brightness(1.2)");
        })
        .on("mouseout", function() {
            d3.select(this)
                .attr("width", 40)
                .attr("height", y.bandwidth())
                .style("filter", "none");
        });

    // Add axes
    svg.append("g")
        .attr("transform", `translate(0,${height})`)
        .call(d3.axisBottom(x)
            .tickFormat(d => `$${d/1000000}M`));

    // Update y-axis text styling
    svg.append("g")
        .call(d3.axisLeft(y)
            .tickSize(0))
        .selectAll(".tick text")
        .attr("x", -10)
        .style("text-anchor", "end")
        .style("font-size", "14px")
        .call(wrap, margin.left - 20);

    // Remove y-axis line
    svg.select(".domain").remove();
}

// Text wrapping function for chart labels
function wrap(text, width) {
    text.each(function() {
        let text = d3.select(this),
            fullText = text.text(),
            words = fullText.split(/\s+/),
            line = [],
            lines = [],
            lineHeight = 1.1;

        // Create lines that fit within width
        let currentLine = [];
        words.forEach(word => {
            currentLine.push(word);
            let testLine = currentLine.join(" ");
            let testWidth = getTextWidth(testLine, "14px Arial");
            
            if (testWidth > width) {
                if (currentLine.length > 1) {
                    currentLine.pop();
                    lines.push(currentLine.join(" "));
                    currentLine = [word];
                } else {
                    lines.push(word);
                    currentLine = [];
                }
            }
        });
        if (currentLine.length > 0) {
            lines.push(currentLine.join(" "));
        }

        // Clear existing text
        text.text(null);

        // Calculate vertical offset to center all lines
        let totalHeight = (lines.length - 1) * lineHeight;
        let startY = -totalHeight / 2;

        // Add lines with minimal spacing
        lines.forEach((line, i) => {
            text.append("tspan")
                .attr("x", -10)
                .attr("dy", i === 0 ? startY + "em" : lineHeight + "em")
                .text(line)
                .style("dominant-baseline", "middle");
        });
    });
}

// Helper function to calculate text width
function getTextWidth(text, font) {
    let canvas = document.createElement("canvas");
    let context = canvas.getContext("2d");
    context.font = font;
    return context.measureText(text).width;
}

// Graph toggle functionality
function toggleGraph(graphType) {
    // Hide all graphs
    document.querySelectorAll('.graph-container').forEach(container => {
        container.style.display = 'none';
    });
    
    // Remove active class from all buttons
    document.querySelectorAll('.graph-toggle-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    
    // Show selected graph and activate button
    if (graphType === 'boxOffice') {
        document.getElementById('boxOfficeContainer').style.display = 'block';
        document.getElementById('boxOfficeBtn').classList.add('active');
    } else {
        document.getElementById('currentMoviesContainer').style.display = 'block';
        document.getElementById('currentMoviesBtn').classList.add('active');
    }
}