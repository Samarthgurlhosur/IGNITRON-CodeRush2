// script.js

let html5QrCode = null;
let currentTeamId = null;
let currentMembers = [];

// 🚀 Start the QR Scanner
async function startScanner() {
    const mascot = document.getElementById("mascot-loader");
    const reader = document.getElementById("reader");

    if (!reader) {
        console.error("Reader element not found.");
        return;
    }

    if (mascot) mascot.style.display = "flex";
    reader.innerHTML = ""; // Clear old view

    html5QrCode = new Html5Qrcode("reader");

    try {
        await html5QrCode.start(
            { facingMode: "environment" },
            { fps: 10, qrbox: 250 },
            async (decodedText) => {
                if (mascot) mascot.style.display = "none";

                let payload;
                try {
                    payload = JSON.parse(decodedText);
                } catch (e) {
                    alert("⚠️ Invalid QR Code. Please scan a valid team QR.");
                    return;
                }

                if (!payload.team_id) {
                    alert("⚠️ QR Code missing team_id.");
                    return;
                }

                currentTeamId = payload.team_id;

                // Fetch team details
                await fetchTeamDetails(currentTeamId);
            }
        );
    } catch (err) {
        console.error("Scanner start error:", err);
        alert("⚠️ Please allow camera access and reload the page.");
    } finally {
        setTimeout(() => {
            if (mascot) mascot.style.display = "none";
        }, 1000);
    }
}

// 🎯 Fetch Team Details From Backend
async function fetchTeamDetails(teamId) {
    try {
        const response = await fetch("/get_team_details", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ team_id: teamId })
        });

        const data = await response.json();

        if (data.error) {
            alert("⚠️ " + data.error);
            return;
        }

        // Team name
        const teamNameEl = document.getElementById("team-name");
        if (teamNameEl) {
            teamNameEl.textContent = data.team.team_name;
        }

        // Members table
        const tableBody = document.querySelector("#members-table tbody");
        if (!tableBody) {
            console.error("members-table tbody not found.");
            return;
        }

        tableBody.innerHTML = "";
        currentMembers = data.members || [];

        currentMembers.forEach(member => {
            const row = document.createElement("tr");
            row.dataset.memberId = member.member_id;

            row.innerHTML = `
                <td>${member.member_name}</td>
                <td><input type="checkbox" ${member.check_in == 1 ? "checked" : ""}></td>
                <td><input type="checkbox" ${member.snacks == 1 ? "checked" : ""}></td>
                <td><input type="checkbox" ${member.round1 == 1 ? "checked" : ""}></td>
                <td><input type="checkbox" ${member.dinner == 1 ? "checked" : ""}></td>
                <td><input type="checkbox" ${member.refresh2 == 1 ? "checked" : ""}></td>
                <td><input type="checkbox" ${member.round2 == 1 ? "checked" : ""}></td>
                <td><input type="checkbox" ${member.refresh3 == 1 ? "checked" : ""}></td>
                <td><input type="checkbox" ${member.round3 == 1 ? "checked" : ""}></td>
                <td><input type="checkbox" ${member.check_out == 1 ? "checked" : ""}></td>
            `;

            tableBody.appendChild(row);
        });

        // Show team details section
        const teamDetails = document.getElementById("team-details");
        if (teamDetails) teamDetails.style.display = "block";

        const scanNextBtn = document.getElementById("scan-next");
        if (scanNextBtn) scanNextBtn.classList.remove("hidden");

        // Stop scanner after successful scan
        try {
            if (html5QrCode) {
                await html5QrCode.stop();
                await html5QrCode.clear();
            }
        } catch (err) {
            console.warn("Error stopping scanner:", err);
        }

    } catch (err) {
        console.error("Error fetching team details:", err);
        alert("⚠️ Unable to fetch team details. Please try again.");
    }
}

// 📝 Update Member Status
async function updateMembers() {
    if (!currentTeamId) {
        alert("⚠️ No team selected. Please scan a team QR first.");
        return;
    }

    const rows = document.querySelectorAll("#members-table tbody tr");
    if (!rows.length) {
        alert("⚠️ No members to update.");
        return;
    }

    const updates = [];

    rows.forEach(row => {
        const checkboxes = row.querySelectorAll("input[type='checkbox']");
        updates.push({
            member_id: row.dataset.memberId,
            check_in:    checkboxes[0].checked ? 1 : 0,
            snacks:      checkboxes[1].checked ? 1 : 0, // Refreshment-1
            round1:      checkboxes[2].checked ? 1 : 0,
            dinner:      checkboxes[3].checked ? 1 : 0,
            refresh2:    checkboxes[4].checked ? 1 : 0,
            round2:      checkboxes[5].checked ? 1 : 0,
            refresh3:    checkboxes[6].checked ? 1 : 0,
            round3:      checkboxes[7].checked ? 1 : 0,
            check_out:   checkboxes[8].checked ? 1 : 0
        });
    });

    try {
        const response = await fetch("/update_members", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                team_id: currentTeamId,
                members: updates
            })
        });

        const result = await response.json();

        if (result.status === "updated") {
            alert("✅ Team details updated successfully!");
        } else {
            alert("⚠️ Failed to update. Please try again.");
        }
    } catch (err) {
        console.error("Error updating members:", err);
        alert("⚠️ Server error. Please try again.");
    }
}

// 🔄 Scan Next QR
async function startNextScan() {
    const teamDetails = document.getElementById("team-details");
    const scanNextBtn = document.getElementById("scan-next");

    if (teamDetails) teamDetails.style.display = "none";
    if (scanNextBtn) scanNextBtn.classList.add("hidden");

    currentTeamId = null;
    currentMembers = [];

    try {
        if (html5QrCode) {
            await html5QrCode.stop();
            await html5QrCode.clear();
        }
    } catch (err) {
        console.warn("Error resetting scanner:", err);
    }

    setTimeout(() => {
        startScanner();
    }, 800);
}

// 🚀 Auto-start scanner on page load
window.onload = () => {
    startScanner();
};
