window.requireAuth = function requireAuth() {
    const token = localStorage.getItem('token');
    if (!token) {
        window.location.href = "/login";
    }
}

window.getMe = async function getMe() {
    const res = await authFetch("/v1/users/me");
    if (!res.ok) {
        alert("Authentication failed. Redirecting to login.");
        window.location.href = "/login";
    }
    const user = await res.json();
    return user;
}

window.getUser = async function getUser(user_id) {
    const res = await authFetch(`/v1/users/${user_id}`);
    if (!res.ok) {
        alert("Authentication failed. Redirecting to login");
        window.location.href = "/login";
        return false;
    }
    const user = await res.json();
    return user;
}

window.getUserByUsername = async function getUserByUsername(username) {
    const res = await fetch(`/v1/users/username/${username}`);
    if (!res.ok) {
        return null;
    }
    const user = await res.json();
    return user;
}

window.checkAdmin = async function checkAdmin() {
    const res = await authFetch("/v1/users/me");
    if (!res.ok) {
        alert("Authentication failed. Redirecting to login.");
        window.location.href = "/login";
        return false;
    }
    const user = await res.json();
    if (user.isadmin === false) {
        return false;
    }
    return true;
}

window.authFetch = async function authFetch(url, options = {}) {
    token = localStorage.getItem('token')
    const headers = options.headers || {};
    if (token) {
        headers["Authorization"] = "Bearer " + token;
    }
    const res = await fetch(url, {
        ...options,
        headers,
    });
    if (res.status === 401) {
        localStorage.setItem("token", "");
        // window.location.href = "/login";
    }
    return res;
}