/* MemoryVault client-side */
document.addEventListener("DOMContentLoaded", function() {
    const statusEl = document.getElementById("device-status");
    if (statusEl) {
        fetch("/api/status")
            .then(r => r.json())
            .then(data => {
                statusEl.innerHTML = "<p>Server running. Version: " + data.version + "</p>";
            })
            .catch(() => {
                statusEl.innerHTML = "<p>Could not reach server.</p>";
            });
    }
});
