document.getElementById("analyzeBtn").addEventListener("click", async () => {
    const fileInput = document.getElementById("qrFile");
    if (fileInput.files.length === 0) {
        alert("Please select a QR code image!");
        return;
    }

    const formData = new FormData();
    formData.append("file", fileInput.files[0]);

    const output = document.getElementById("output");
    output.textContent = "Analyzing...";

    try {
        const response = await fetch("/analyze-qr", {
            method: "POST",
            body: formData
        });
        const data = await response.json();

        output.textContent = `
Status: ${data.status}
Risk Score: ${data.risk_score}
Extracted UPI: ${data.extracted_upi ?? "N/A"}
Tampering Probability: ${data.tampering_probability.toFixed(2)}
Reasons: ${data.reasons.join(", ") || "None"}
        `;
    } catch (err) {
        output.textContent = "Error: " + err;
    }
});