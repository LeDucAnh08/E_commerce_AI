const loginForm = document.getElementById("loginForm");
const loginUsername = document.getElementById("loginUsername");
const loginPassword = document.getElementById("loginPassword");
const loginError = document.getElementById("loginError");

const showLoginError = (message) => {
    loginError.textContent = message;
    loginError.hidden = false;
};

const saveSession = (data) => {
    localStorage.setItem("accessToken", data.access);
    localStorage.setItem("refreshToken", data.refresh);
    localStorage.setItem("currentUser", JSON.stringify(data.user));
};

const login = async (username, password) => {
    const response = await fetch("/auth/login/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
        throw new Error(data.error || "Login failed");
    }
    return data;
};

document.querySelectorAll("[data-demo-user]").forEach((button) => {
    button.addEventListener("click", () => {
        loginUsername.value = button.dataset.demoUser;
        loginPassword.value = button.dataset.demoPass;
        loginForm.requestSubmit();
    });
});

if (loginForm) {
    loginForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        loginError.hidden = true;
        const submitButton = loginForm.querySelector("button[type='submit']");
        submitButton.disabled = true;
        submitButton.textContent = "Signing in...";

        try {
            const data = await login(loginUsername.value.trim(), loginPassword.value);
            saveSession(data);
            const next = new URLSearchParams(window.location.search).get("next") || "/";
            window.location.href = next;
        } catch (error) {
            showLoginError(error.message);
        } finally {
            submitButton.disabled = false;
            submitButton.textContent = "Sign in";
        }
    });
}
