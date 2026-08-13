renderMenu = function renderMenu() {
    const menu = document.getElementById("menu");
    const linkClass = "hover:text-yellow-300 transition";
    const buttonClass = "bg-red-500 hover:bg-red-600 px-3 py-1 rounded-lg shadow transition";

    const token = localStorage.getItem("token");
    if (token) {
        menu.innerHTML = `
            <a href="/me" class="${linkClass}">Profile</a>
            <a href="/simulations" class="${linkClass}">Simulations</a>
            <a href="/simulate" class="${linkClass}">Run Simulation</a>
            <a href="/admin" class="${linkClass}">Admin</a>
            <button onclick="logout()" class="${buttonClass}">Logout</button>
        `;
    } else {
        menu.innerHTML = `
            <a href="/login" class="${linkClass}">Login</a>
            <a href="/register" class="${linkClass}">Register</a>
            <a href="/simulations" class="${linkClass}">Simulations</a>
        `;
    }
}

async function login(username, password) {
    const res = await fetch("/v1/users/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password })
    });

    if (!res.ok) {
        alert("Login failed");
        return;
    }

    const data = await res.json();
    console.log(data);
    if (data.challenge_name && data.session) {
        window.location.href = `/2fa.html?username=${encodeURIComponent(username)}&session=${encodeURIComponent(data.session)}`;
        return;
    }

    const id_token = data["ID Token"];
    const access_token = data["Access Token"];
    localStorage.setItem('token', id_token);
    localStorage.setItem('access_token', access_token)
    window.location.href = "/me";
}

async function mfaChallenge(username, session, code) {
    const res = await fetch("/v1/users/challenge-response", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            username,
            session,
            challenge_response: code
        })
    });

    if (!res.ok) {
        alert("Invalid MFA code");
        return;
    }

    const data = await res.json();
    const id_token = data["ID Token"];
    const access_token = data["Access Token"];
    localStorage.setItem('token', id_token);
    localStorage.setItem('access_token', access_token);
    window.location.href = "/me";
}

function logout() {
    localStorage.setItem('token', '');
    window.location.href = "/"
}

async function register(username, password, email) {
    const res = await fetch("/v1/users/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password, email })
    });
    if (!res.ok) {
        const msg = await res.text();
        alert(`Register failed: ${msg}`);
        return;
    }
    alert("Registered! Check your email to confirm your account.");
    window.location.href = `/confirm?username=${username}`;
}

async function loadSimulations(containerID, options = {}, auth = false, admin = false) {
    const sortBy = document.getElementById("sort-by").value;
    const sortOrder = document.getElementById("sort-order").value;
    const status = document.getElementById("filter-status").value;

    const params = {
        ...options,
        ...(sortBy ? { sort_by: sortBy } : {}),
        ...(sortOrder ? { sort_order: sortOrder } : {}),
        ...(status ? { status } : {}),
    };

    let resSims = null;
    if (admin === true) {
        resSims = await fetchAllSimulations(params);
    } else {
        if (auth === true) {
            resSims = await fetchUserSimulations(params);
        } else {
            resSims = await fetchPublicSimulations(params);
        }
    }
    if (!resSims) return;

    const { data: sims, headers } = resSims;
    const container = document.getElementById(containerID);

    const page = parseInt(headers.get("x-page")) || 1;
    const totalPages = parseInt(headers.get("x-total-pages")) || 1;

    let paginationHtml = `<div class="flex space-x-2 mb-2">`;

    if (admin === false) {
        for (let p = 1; p <= totalPages; p++) {
            paginationHtml += `<button
            class="px-2 py-1 border rounded ${p === page ? 'bg-blue-500 text-white' : 'bg-gray-200'}"
            data-container="${containerID}"
            data-options='${JSON.stringify({ ...options, page: p })}'
            data-auth="${auth}">
            ${p}
        </button>`;
        }
        paginationHtml += `</div>`;
    } else {
        paginationHtml = ""
    }

    let currentUser = null;
    if (auth || admin) {
        currentUser = await window.getMe();
    }
    if (!currentUser) {
        currentUser = {
            isadmin: false,
            username: 0
        }
    }

    let html = paginationHtml + `
        <table class="table-auto w-full border-collapse border border-gray-300 mb-4">
            <thead>
                <tr class="bg-gray-200">
                    <th class="border px-2 py-1">UUID</th>
                    <th class="border px-2 py-1">Equation</th>
                    <th class="border px-2 py-1">Theta</th>
                    <th class="border px-2 py-1">Status</th>
                    <th class="border px-2 py-1">Submitted</th>
                    <th class="border px-2 py-1">Completed</th>
                    <th class="border px-2 py-1">Message</th>
                    <th class="border px-2 py-1">Actions</th>
                </tr>
            </thead>
            <tbody>
    `;

    sims.forEach(sim => {
        html += `
            <tr class="hover:bg-gray-100 cursor-pointer" onclick="this.nextElementSibling.classList.toggle('hidden')">
                <td class="border px-2 py-1">${sim.simulation_id}</td>
                <td class="border px-2 py-1">${sim.equation}</td>
                <td class="border px-2 py-1">${sim.theta}</td>
                <td class="border px-2 py-1">${sim.status}</td>
                <td class="border px-2 py-1">${sim.submit_time || "-"}</td>
                <td class="border px-2 py-1">${sim.complete_time || "-"}</td>
                <td class="border px-2 py-1">${sim.message || "-"}</td>
                <td class="border px-2 py-1">
                    <a class="text-blue-600 hover:underline" href="/profile?username=${sim.username}">View User</a>
                    ${sim.status === "complete"
                ? `<a class="download-link text-green-600 hover:underline" data-uuid="${sim.simulation_id}">Download</a>`
                : ""}
                    ${(currentUser.isadmin === true || currentUser.username == sim.username)
                ? `<a class="delete-link text-red-600 hover:underline" data-uuid="${sim.simulation_id}">Delete</a>`
                : ""}
                </td>
            </tr>
            <tr class="hidden bg-gray-200">
                <td colspan="8" class="px-4 py-2 font-mono text-sm whitespace-pre text-wrap">${JSON.stringify(sim.params)}</td>
            <tr>
        `;
    });

    html += "</tbody></table>";
    container.innerHTML = html;
}

async function loadUsers(containerID, options = {}) {
    const sortBy = document.getElementById("user-sort-by").value;
    const sortOrder = document.getElementById("user-sort-order").value;
    const isAdminFilter = document.getElementById("user-filter-admin").value;

    const params = {
        ...options,
        ...(sortBy ? { sort_by: sortBy } : {}),
        ...(sortOrder ? { sort_order: sortOrder } : {}),
        ...(isAdminFilter ? { isadmin: isAdminFilter } : {}),
    };

    const resUsers = await fetchAllUsers(params);
    if (!resUsers) return;

    const { data: users, headers } = resUsers;
    const container = document.getElementById(containerID);

    let html = `
        <table class="table-auto w-full border-collapse border border-gray-300 mb-4">
            <thead>
                <tr class="bg-gray-200">
                    <th class="border px-2 py-1">User ID</th>
                    <th class="border px-2 py-1">Username</th>
                    <th class="border px-2 py-1">Password Hash</th>
                    <th class="border px-2 py-1">Admin</th>
                    <th class="border px-2 py-1">Actions</th>
                </tr>
            </thead>
            <tbody>
    `;

    users.forEach(user => {
        html += `
            <tr class="hover:bg-gray-100">
                <td class="border px-2 py-1">${user.id}</td>
                <td class="border px-2 py-1">${user.username}</td>
                <td class="border px-2 py-1">${user.password_hash}</td>
                <td class="border px-2 py-1">${user.isadmin === true ? "Yes" : "No"}</td>
                <td class="border px-2 py-1">
                    <a class="text-blue-600 hover:underline" href="/profile?user_id=${user.id}">View</a>
                    <a class="text-red-600 hover:underline delete-user-link" data-userid="${user.id}">Delete</a> 
                </td>
            </tr>
        `;
    });

    html += "</tbody></table>"
    container.innerHTML = html;
}

async function fetchPublicSimulations(params = {}) {
    const query = new URLSearchParams(params).toString();
    const res = await fetch(`/v1/simulations/public?${query}`);
    headers = res.headers;
    if (!res.ok) {
        alert("Failed to fetch public simulations");
        return null;
    }
    const data = await res.json();
    return { data, headers }
}

async function fetchUserSimulations(params = {}) {
    const query = new URLSearchParams(params).toString();
    const res = await window.authFetch(`/v1/simulations?${query}`);
    headers = res.headers;
    if (!res.ok) {
        alert("Failed to fetch user simulations");
        return null;
    }
    const data = await res.json();
    return { data, headers }
}

async function fetchAllSimulations(params = {}) {
    const query = new URLSearchParams(params).toString();
    const res = await window.authFetch(`/v1/simulations/all?${query}`);
    headers = res.headers;
    if (!res.ok) {
        alert("Failed to fetch all simulations");
        return null;
    }
    const data = await res.json();
    return { data, headers }
}

async function fetchAllUsers(params = {}) {
    const query = new URLSearchParams(params).toString();
    const res = await window.authFetch(`/v1/users?${query}`);
    const headers = res.headers;
    if (!res.ok) {
        alert("Failed to fetch all users");
        return null;
    }
    const data = await res.json();
    return { data, headers };
}

async function loadProfile(user, auth = "false") {
    const userInfoDiv = document.getElementById("user-info");
    userInfoDiv.innerHTML = `
        <h2 class="text-2xl font-bold mb-2">Profile: ${user["username"]}</h2>
        <p><strong>User ID:</strong> ${user["id"]}</p>
        ${user["isadmin"] === true ? "<p class='text-red-600 font-semibold'>Admin</p>" : ""}    
    `;

    let params = {}
    if (auth === "false") {
        params = { user: user.id };
    }
    loadSimulations("user-simulations", params, auth);
}

async function download(uuid) {
    const res = await window.authFetch(`/v1/simulations/${uuid}/result`);
    if (!res.ok) {
        alert("Authentication failed for download.");
        return;
    }
    const url = await res.json();
    const link = document.createElement("a");
    link.href = url;
    link.download = `${uuid}.h5`;
    link.style.display = "none";
    link.click();
}

async function deleteSim(uuid) {
    const res = await window.authFetch(`/v1/simulations/${uuid}`, {
        method: "DELETE",
        headers: { "Content-Type": "application/json" }
    });
    if (!res.ok) {
        alert("Failed to delete simulation");
        return;
    }
    alert("Successfully deleted simulation");
    window.location.reload();
}

async function deleteUser(userid) {
    const res = await window.authFetch(`/v1/users/${userid}`, {
        method: "DELETE",
        headers: { "Content-Type": "application/json" }
    });
    if (!res.ok) {
        alert("Failed to delete user");
        return;
    }
    alert("Successfully deleted user");
    window.location.reload();
}

document.addEventListener("click", (e) => {
    if (e.target.matches("button[data-container]")) {
        const containerID = e.target.dataset.container;
        const options = JSON.parse(e.target.dataset.options);
        const auth = e.target.dataset.auth === "true";
        loadSimulations(containerID, options, auth);
    }
    if (e.target.matches(".download-link")) {
        download(e.target.dataset.uuid);
    }
    if (e.target.matches(".delete-link")) {
        deleteSim(e.target.dataset.uuid);
    }
    if (e.target.matches(".delete-user-link")) {
        deleteUser(e.target.dataset.userid);
    }
});


renderMenu();