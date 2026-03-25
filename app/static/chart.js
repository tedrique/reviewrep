// Lightweight helper to render simple bar chart (no deps)
function renderBarChart(canvasId, labels, data) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const maxVal = Math.max(...data, 1);
    const barWidth = canvas.width / data.length * 0.6;
    const gap = canvas.width / data.length * 0.4;
    data.forEach((v, i) => {
        const h = (v / maxVal) * (canvas.height - 20);
        ctx.fillStyle = "#2563eb";
        ctx.fillRect(i * (barWidth + gap) + gap/2, canvas.height - h, barWidth, h);
        ctx.fillStyle = "#6b7280";
        ctx.font = "10px sans-serif";
        ctx.fillText(labels[i], i * (barWidth + gap) + gap/2, canvas.height - 2);
    });
}
