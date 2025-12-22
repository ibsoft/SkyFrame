(() => {
    const container = document.getElementById("dashboard-data");
    if (!container || typeof Chart === "undefined") {
        return;
    }

    const parseJson = (value) => {
        if (!value) return [];
        try {
            return JSON.parse(value);
        } catch {
            return [];
        }
    };

    const objectLabels = parseJson(container.dataset.objectLabels);
    const objectCounts = parseJson(container.dataset.objectCounts);
    const dailyLabels = parseJson(container.dataset.dailyLabels);
    const dailyCounts = parseJson(container.dataset.dailyCounts);
    const userObjectLabels = parseJson(container.dataset.userObjectLabels);
    const userObjectCounts = parseJson(container.dataset.userObjectCounts);
    const userDailyLabels = parseJson(container.dataset.userDailyLabels);
    const userDailyCounts = parseJson(container.dataset.userDailyCounts);

    const baseOptions = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: { labels: { color: "#ffffff" } },
            tooltip: {
                titleColor: "#ffffff",
                bodyColor: "#ffffff",
                backgroundColor: "rgba(15, 23, 42, 0.9)",
                borderColor: "rgba(148, 163, 184, 0.4)",
                borderWidth: 1,
            },
        },
        scales: {
            x: { ticks: { color: "#ffffff" }, grid: { color: "rgba(148,163,184,0.15)" } },
            y: { ticks: { color: "#ffffff" }, grid: { color: "rgba(148,163,184,0.15)" }, beginAtZero: true },
        },
    };

    const pieColors = [
        "rgba(59,130,246,0.8)",
        "rgba(14,165,233,0.8)",
        "rgba(56,189,248,0.8)",
        "rgba(34,211,238,0.8)",
        "rgba(125,211,252,0.8)",
        "rgba(30,64,175,0.8)",
        "rgba(37,99,235,0.8)",
        "rgba(147,197,253,0.8)",
    ];

    const buildPie = (elementId, labels, counts) => {
        const el = document.getElementById(elementId);
        if (!el || !labels.length) return;
        new Chart(el, {
            type: "pie",
            data: {
                labels,
                datasets: [
                    {
                        label: "Images",
                        data: counts,
                        backgroundColor: pieColors.slice(0, counts.length),
                        borderColor: "rgba(2,6,23,1)",
                        borderWidth: 1,
                    },
                ],
            },
            options: baseOptions,
        });
    };

    const buildLine = (elementId, labels, counts) => {
        const el = document.getElementById(elementId);
        if (!el) return;
        new Chart(el, {
        type: "line",
        data: {
            labels,
            datasets: [
                {
                    label: "Uploads",
                    data: counts,
                    borderColor: "rgba(14,165,233,1)",
                    backgroundColor: "rgba(14,165,233,0.2)",
                    fill: true,
                    tension: 0.3,
                },
            ],
        },
        options: baseOptions,
        });
    };

    buildPie("objectsChart", objectLabels, objectCounts);
    buildLine("uploadsChart", dailyLabels, dailyCounts);
    buildPie("userObjectsChart", userObjectLabels, userObjectCounts);
    buildLine("userUploadsChart", userDailyLabels, userDailyCounts);
})();
