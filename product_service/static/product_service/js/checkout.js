const tokenField = document.getElementById("accessToken");
const saveTokenButton = document.getElementById("saveToken");
const orderSummary = document.getElementById("orderSummary");
const createOrderButton = document.getElementById("createOrder");
const payNowButton = document.getElementById("payNow");
const paymentStatus = document.getElementById("paymentStatus");
const shippingAddress = document.getElementById("shippingAddress");
const shippingMethod = document.getElementById("shippingMethod");
const shippingEstimate = document.getElementById("shippingEstimate");
const trackOrderLink = document.getElementById("trackOrderLink");

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

const shippingMethods = {
    standard: { label: "Standard", fee: 5, eta: "3 to 5 days" },
    express: { label: "Express", fee: 12, eta: "1 to 2 days" },
    same_day: { label: "Same day", fee: 25, eta: "today" },
};

const renderShippingEstimate = () => {
    const selected = shippingMethods[shippingMethod.value] || shippingMethods.standard;
    shippingEstimate.textContent = `Shipping: ${selected.label}, ETA ${selected.eta}, fee ${formatMoney(selected.fee)}`;
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
    const shipment = order.shipment;
    orderSummary.innerHTML = `
        <div><strong>Order #${order.id}</strong></div>
        <div>Status: ${order.status}</div>
        <div>Total: ${formatMoney(order.total_price)}</div>
        <div>Items: ${order.items.length}</div>
        ${
            shipment
                ? `<div>Shipping: ${shipment.shipping_method} / ${shipment.status}</div>
                   <div>Address: ${shipment.address}</div>`
                : ""
        }
    `;
    if (trackOrderLink) {
        trackOrderLink.hidden = false;
        trackOrderLink.href = `/shipping/track/?order_id=${order.id}`;
    }
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
    renderShippingEstimate();
    shippingMethod.addEventListener("change", renderShippingEstimate);

    if (orderId) {
        await loadOrder(orderId);
    }

    createOrderButton.addEventListener("click", async () => {
        try {
            if (!shippingAddress.value.trim()) {
                alert("Enter a shipping address first.");
                return;
            }
            const order = await apiRequest("/orders/from-cart/", {
                method: "POST",
                body: JSON.stringify({
                    shipping_address: shippingAddress.value.trim(),
                    shipping_method: shippingMethod.value,
                }),
            });
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
            await loadOrder(orderId);
        } catch (error) {
            alert(error.message);
        }
    });
};

initToken();
initCheckout().catch(() => {
    orderSummary.innerHTML = "<div class=\"empty\">Sign in to continue.</div>";
});
