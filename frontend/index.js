
    let crawlerData = [];
    let currentSite = 'all';
    let performanceChart = null;

    const siteColors = {
      'bbc': '#bb1919',
      'nbc': '#0089cc',
      'sky': '#0072c9',
      'cbs': '#00234b',
      'aljazeera': '#f27d00'
    };

    // Detect system capabilities
    function detectSystemCapabilities() {
      const cores = navigator.hardwareConcurrency || 4;
      document.getElementById('cpu-cores').textContent = cores;

      const recommendedThreads = Math.max(cores * 2, 8);
      document.getElementById('max-threads').textContent = recommendedThreads;

      // Estimate memory (rough estimate)
      if (navigator.deviceMemory) {
        document.getElementById('memory').textContent = `~${navigator.deviceMemory}GB`;
      }

      // Warning if user sets too many threads
      document.getElementById('thread-count').addEventListener('input', (e) => {
        const value = parseInt(e.target.value);
        const warning = document.getElementById('thread-warning');

        if (value > recommendedThreads) {
          warning.textContent = `⚠️ Using more than ${recommendedThreads} threads may impact performance`;
        } else {
          warning.textContent = '';
        }
      });
    }

    // Initialize performance chart
    function initChart() {
      const ctx = document.getElementById('performanceChart').getContext('2d');
      performanceChart = new Chart(ctx, {
        type: 'bar',
        data: {
          labels: ['Sequential', 'Parallel (2)', 'Parallel (4)', 'Parallel (8)', 'Multiprocess', 'Asyncio', 'Hybrid'],
          datasets: [{
            label: 'Time (seconds)',
            data: [0, 0, 0, 0, 0, 0, 0],
            backgroundColor: [
              'rgba(220, 53, 69, 0.7)',
              'rgba(255, 193, 7, 0.7)',
              'rgba(255, 152, 0, 0.7)',
              'rgba(40, 167, 69, 0.7)',
              'rgba(102, 126, 234, 0.7)',
              'rgba(23, 162, 184, 0.7)',
              'rgba(111, 66, 193, 0.7)'
            ],
            borderColor: [
              'rgb(220, 53, 69)',
              'rgb(255, 193, 7)',
              'rgb(255, 152, 0)',
              'rgb(40, 167, 69)',
              'rgb(102, 126, 234)',
              'rgb(23, 162, 184)',
              'rgb(111, 66, 193)'
            ],
            borderWidth: 2
          }]
        },
        options: {
          responsive: true,
          plugins: {
            legend: {
              display: false
            },
            title: {
              display: true,
              text: 'Crawling Time Comparison (Lower is Better)',
              font: {
                size: 16
              }
            },
            tooltip: {
              callbacks: {
                afterLabel: function(context) {
                  const baseTime = Math.max(...context.dataset.data);
                  const speedup = baseTime / context.parsed.y;
                  return `Speedup: ${speedup.toFixed(2)}x`;
                }
              }
            }
          },
          scales: {
            y: {
              beginAtZero: true,
              title: {
                display: true,
                text: 'Time (seconds)'
              }
            }
          }
        }
      });
    }

    // Start crawler (instructions)
    async function startCrawler() {
  const mode = document.getElementById('crawl-mode').value;
  const threadCount = parseInt(document.getElementById('thread-count').value);
  const articlesPerSite = parseInt(document.getElementById('articles-per-site').value);

  const payload = {
    mode,
    threadCount,
    articlesPerSite
  };

  const response = await fetch("http://localhost:8000/start-crawler", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  });

  const result = await response.json();

  alert(
    `Crawler started.\n\n` +
    `Executed: ${result.executed_command}\n\n` +
    `Output:\n${result.stdout || "(no output)"}`
  );
}

    // Load results from JSON
    async function loadResults() {
      try {
        const response = await fetch("./results.json");
        if (!response.ok) throw new Error('File not found');

        // Get raw text first to handle empty files
        const text = await response.text();
        let data = [];
        try {
          data = text ? JSON.parse(text) : [];
        } catch (e) {
          console.warn("JSON empty or invalid, returning empty array");
          data = [];
        }

        crawlerData = data.map(article => ({
          ...article,
          site: article.site || new URL(article.url).hostname.replace('www.', '').split('.')[0]
        }));

        renderArticles();
        updateStats();

      } catch (error) {
        alert('❌ Could not load results.json');
        console.error(error);
      }
    }

    // Load performance metrics
    async function loadPerformanceMetrics() {
      try {
        const response = await fetch("./performance_metrics.json");
        if (!response.ok) throw new Error('File not found');

        // Get raw text first to handle empty files
        const text = await response.text();
        let metrics = {};
        try {
          metrics = text ? JSON.parse(text) : {};
        } catch (e) {
          console.warn("JSON empty or invalid, returning empty object");
          metrics = {};
        }

        // Update chart
        const labels = [];
        const times = [];

        for (const [method, data] of Object.entries(metrics)) {
          let label = method.replace('_', ' ').replace('threaded', 'Parallel');
          label = label.charAt(0).toUpperCase() + label.slice(1);
          labels.push(label);
          times.push(data.time);
        }

        performanceChart.data.labels = labels;
        performanceChart.data.datasets[0].data = times;
        performanceChart.update();

        // Update stats
        if (times.length > 0) {
          const bestTime = Math.min(...times);
          const baseTime = metrics.sequential?.time || times[0];
          const maxSpeedup = baseTime / bestTime;

          document.getElementById('crawl-time').textContent = bestTime.toFixed(2) + 's';
          document.getElementById('speedup').textContent = maxSpeedup.toFixed(2) + 'x';
        }

      } catch (error) {
        alert('❌ Could not load performance_metrics.json');
        console.error(error);
      }
    }

    function renderArticles() {
      const container = document.getElementById('articles-container');
      const navigation = document.getElementById('site-navigation');

      if (crawlerData.length === 0) {
        container.innerHTML = `
          <div class="empty-state">
            <h3>📭 No articles loaded</h3>
            <p>Click "Load Results" to view crawled articles</p>
          </div>`;
        return;
      }

      // Get unique sites with counts
      const siteCounts = {};
      crawlerData.forEach(article => {
        const site = article.site;
        siteCounts[site] = (siteCounts[site] || 0) + 1;
      });

      const sites = ['all', ...Object.keys(siteCounts)];

      // Render navigation
      navigation.innerHTML = sites.map(site => {
        const count = site === 'all' ? crawlerData.length : siteCounts[site];
        return `<button class="site-btn ${site === currentSite ? 'active' : ''}" onclick="filterBySite('${site}')">
          ${site === 'all' ? '🌐 All Sites' : '📰 ' + site.toUpperCase()}
          <span class="badge">${count}</span>
        </button>`;
      }).join('');

      // Filter and render articles
      const filtered = currentSite === 'all'
        ? crawlerData
        : crawlerData.filter(a => a.site === currentSite);

      if (filtered.length === 0) {
        container.innerHTML = `
          <div class="empty-state">
            <h3>No articles from ${currentSite}</h3>
          </div>`;
        return;
      }

      container.innerHTML = filtered.map(article => {
        const siteColor = siteColors[article.site] || '#667eea';
        return `
        <div class="article" style="border-left-color: ${siteColor}">
          <h3>${article.title || 'Untitled'}</h3>
          <div class="article-meta">
            <div class="meta-item">
              <strong>👤</strong> ${article.authors?.join(", ") || "Unknown"}
            </div>
            <div class="meta-item">
              <strong>🌐</strong> ${article.site?.toUpperCase() || 'Unknown'}
            </div>
            ${article.crawled_at ? `<div class="meta-item"><strong>🕒</strong> ${new Date(article.crawled_at).toLocaleString()}</div>` : ''}
          </div>
          <p>${article.text || 'No content available'}</p>
          ${article.top_image ? `<img src="${article.top_image}" class="top-image" alt="Article image" onerror="this.style.display='none'" />` : ''}
          <p style="margin-top: 10px;">
            <a href="${article.url}" target="_blank" style="color: ${siteColor}; font-weight: 600; text-decoration: none;">
              Read full article →
            </a>
          </p>
        </div>
      `}).join('');
    }

    function filterBySite(site) {
      currentSite = site;
      renderArticles();
    }

    function updateStats() {
      document.getElementById('total-articles').textContent = crawlerData.length;

      const uniqueSites = new Set(crawlerData.map(a => a.site));
      document.getElementById('total-sites').textContent = uniqueSites.size;
    }

    function switchView(view) {
      document.querySelectorAll('.tab').forEach(tab => tab.classList.remove('active'));
      event.target.classList.add('active');
    }

    // Initialize
    detectSystemCapabilities();
    initChart();

    // Try to load data on startup
    loadResults().catch(() => {
      console.log("No results found on startup");
    });

    loadPerformanceMetrics().catch(() => {
      console.log("No metrics found on startup");
    });
