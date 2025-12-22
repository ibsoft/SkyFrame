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

    if (objectLabels.length) {
        new Chart(document.getElementById("objectsChart"), {
            type: "pie",
            data: {
                labels: objectLabels,
                datasets: [
                    {
                        label: "Images",
                        data: objectCounts,
                        backgroundColor: pieColors.slice(0, objectCounts.length),
                        borderColor: "rgba(2,6,23,1)",
                        borderWidth: 1,
                    },
                ],
            },
            options: baseOptions,
        });
    }

    new Chart(document.getElementById("uploadsChart"), {
        type: "line",
        data: {
            labels: dailyLabels,
            datasets: [
                {
                    label: "Uploads",
                    data: dailyCounts,
                    borderColor: "rgba(14,165,233,1)",
                    backgroundColor: "rgba(14,165,233,0.2)",
                    fill: true,
                    tension: 0.3,
                },
            ],
        },
        options: baseOptions,
    });
})();
