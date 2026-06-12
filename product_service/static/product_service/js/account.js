const authAction = document.getElementById("authAction");
const userAvatar = document.getElementById("userAvatar");
const userName = document.getElementById("userName");

const readCurrentUser = () => {
    try {
        return JSON.parse(localStorage.getItem("currentUser") || "null");
    } catch {
        return null;
    }
};

const clearSession = () => {
    localStorage.removeItem("accessToken");
    localStorage.removeItem("refreshToken");
    localStorage.removeItem("currentUser");
};

const renderAccount = () => {
    const user = readCurrentUser();
    if (!authAction || !userAvatar || !userName) {
        return;
    }

    if (!user) {
        authAction.textContent = "Sign in";
        authAction.href = `/login/?next=${encodeURIComponent(window.location.pathname)}`;
        userAvatar.textContent = "G";
        userName.textContent = "Guest";
        return;
    }

    authAction.textContent = "Sign out";
    authAction.href = "#logout";
    userAvatar.textContent = (user.username || "U").slice(0, 1).toUpperCase();
    userName.textContent = user.username || "User";
};

if (authAction) {
    authAction.addEventListener("click", (event) => {
        if (authAction.getAttribute("href") !== "#logout") {
            return;
        }
        event.preventDefault();
        clearSession();
        renderAccount();
        window.location.href = "/";
    });
}

renderAccount();
