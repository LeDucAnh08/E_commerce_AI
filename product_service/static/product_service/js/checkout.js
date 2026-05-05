const tokenField = document.getElementById("accessToken");
const saveTokenButton = document.getElementById("saveToken");
const orderSummary = document.getElementById("orderSummary");
const createOrderButton = document.getElementById("createOrder");
const payNowButton = document.getElementById("payNow");
const paymentStatus = document.getElementById("paymentStatus");

const formatMoney = (value) => `$${Number(value).toFixed(2)}`;
const getToken = () => localStorage.getItem("accessToken") || "";
const setToken = (value) => localStorage.setItem("accessToken", value);

const apiRequest = async (url, options = {}) => {
    const token = getToken();
    const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
    if (token) {
        headers.Authorization = `Bearer ${token}`;
    }
    const response = await fetch(url, { ...options, headers });
    if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.error || "Request failed");
    }
    return response.json();
};

const initToken = () => {
    if (tokenField) {
        tokenField.value = getToken();
    }
    if (saveTokenButton) {
        saveTokenButton.addEventListener("click", () => {
            setToken(tokenField.value.trim());
            window.location.reload();
        });
    }
};

const renderOrder = (order) => {
    if (!order) {
        orderSummary.innerHTML = "<div class=\"empty\">No order loaded.</div>";
        return;
    }
    orderSummary.innerHTML = `
        <div><strong>Order #${order.id}</strong></div>
        <div>Status: ${order.status}</div>
        <div>Total: ${formatMoney(order.total_price)}</div>
        <div>Items: ${order.items.length}</div>
    `;
};

const loadOrder = async (orderId) => {
    const order = await apiRequest(`/orders/${orderId}/`);
    renderOrder(order);
    return order;
};

const getOrderIdFromUrl = () => {
    const params = new URLSearchParams(window.location.search);
    return params.get("order_id");
};

const initCheckout = async () => {
    let orderId = getOrderIdFromUrl();
    if (orderId) {
        await loadOrder(orderId);
    }

    createOrderButton.addEventListener("click", async () => {
        try {
            const order = await apiRequest("/orders/from-cart/", { method: "POST" });
            orderId = order.id;
            window.history.replaceState({}, "", `/checkout/?order_id=${orderId}`);
            renderOrder(order);
        } catch (error) {
            alert(error.message);
        }
    });

    payNowButton.addEventListener("click", async () => {
        if (!orderId) {
            alert("Create an order first.");
            return;
        }
        try {
            const order = await loadOrder(orderId);
            const payment = await apiRequest("/payment/pay/", {
                method: "POST",
                body: JSON.stringify({ order_id: Number(orderId), amount: order.total_price }),
            });
            paymentStatus.textContent = `Payment status: ${payment.status}`;
        } catch (error) {
            alert(error.message);
        }
    });
};

initToken();
initCheckout().catch(() => {
    orderSummary.innerHTML = "<div class=\"empty\">Sign in to continue.</div>";
});
