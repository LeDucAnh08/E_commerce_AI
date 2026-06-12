const trackingResult = document.getElementById("trackingResult");

const getToken = () => localStorage.getItem("accessToken") || "";
const formatMoney = (value) => `$${Number(value).toFixed(2)}`;

const apiRequest = async (url, options = {}) => {
    const token = getToken();
    const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
    if (token) {
        headers.Authorization = `Bearer ${token}`;
    }
    const response = await fetch(url, { ...options, headers });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
        throw new Error(data.error || "Request failed");
    }
    return data;
};

const statusSteps = ["processing", "shipped", "in_transit", "delivered"];
const statusLabels = {
    processing: "Processing",
    shipped: "Shipped",
    in_transit: "In transit",
    delivered: "Delivered",
    returned: "Returned",
};
const methodLabels = {
    standard: "Standard",
    express: "Express",
    same_day: "Same day",
};
const paidOrderStatuses = new Set(["paid", "shipping", "delivered", "completed"]);

const timelineHtml = (shipment) => {
    const activeIndex = statusSteps.indexOf(shipment.status);
    return statusSteps
        .map((status, index) => {
            const state = shipment.status === "returned"
                ? "inactive"
                : index <= activeIndex
                    ? "active"
                    : "inactive";
            return `<li class="${state}">${statusLabels[status]}</li>`;
        })
        .join("");
};

const orderCard = (order) => {
    const shipment = order.shipment;
    return `
        <article class="tracking-card">
            <div class="tracking-card-header">
                <div>
                    <div class="summary-label">Order</div>
                    <div class="summary-value">#${order.id}</div>
                </div>
                <span class="status-pill">${order.status}</span>
            </div>
            <div>Total: ${formatMoney(order.total_price)}</div>
            <div>Items: ${order.items.length}</div>
            <div>Shipping: <strong>${statusLabels[shipment.status] || shipment.status}</strong></div>
            <div>Method: ${methodLabels[shipment.shipping_method] || shipment.shipping_method}</div>
            <div>Address: ${shipment.address}</div>
            <ol class="tracking-timeline">${timelineHtml(shipment)}</ol>
        </article>
    `;
};

const renderOrders = (orders) => {
    if (!orders.length) {
        trackingResult.innerHTML = `
            <div class="empty">
                No paid orders with shipping yet. Create an order and pay first.
            </div>
        `;
        return;
    }
    trackingResult.innerHTML = `<div class="tracking-list">${orders.map(orderCard).join("")}</div>`;
};

const initTracking = async () => {
    if (!getToken()) {
        trackingResult.innerHTML = "<div class=\"empty\">Sign in to view shipping status.</div>";
        return;
    }

    const orders = await apiRequest("/orders/");
    const focusedOrderId = Number(new URLSearchParams(window.location.search).get("order_id") || 0);
    let trackableOrders = orders.filter(
        (order) => order.shipment && paidOrderStatuses.has(order.status),
    );

    if (focusedOrderId) {
        trackableOrders = trackableOrders.filter((order) => order.id === focusedOrderId);
    }

    renderOrders(trackableOrders);
};

initTracking().catch((error) => {
    trackingResult.innerHTML = `<div class="empty">${error.message}</div>`;
});
