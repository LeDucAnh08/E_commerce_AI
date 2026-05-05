const tokenField = document.getElementById("accessToken");
const saveTokenButton = document.getElementById("saveToken");
const cartList = document.getElementById("cartList");
const cartTotal = document.getElementById("cartTotal");
const clearCartButton = document.getElementById("clearCart");
const placeOrderButton = document.getElementById("placeOrder");

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

const renderCart = (cart, products) => {
    if (!cartList) {
        return;
    }
    if (!cart.items.length) {
        cartList.innerHTML = "<div class=\"empty\">Cart is empty.</div>";
        cartTotal.textContent = formatMoney(0);
        return;
    }

    const productMap = Object.fromEntries(products.map((product) => [product.id, product]));
    let total = 0;

    cartList.innerHTML = cart.items
        .map((item) => {
            const product = productMap[item.product_id] || { price: 0 };
            const lineTotal = Number(product.price || 0) * item.quantity;
            total += lineTotal;
            return `
            <div class="cart-item" data-item="${item.id}">
                <strong>${product.name || "Product"}</strong>
                <span>${formatMoney(product.price || 0)}</span>
                <input class="qty-input" type="number" min="1" value="${item.quantity}" />
                <div class="cart-actions">
                    <span>${formatMoney(lineTotal)}</span>
                    <button class="btn ghost" data-remove="${item.id}">Remove</button>
                </div>
            </div>
        `;
        })
        .join("");

    cartTotal.textContent = formatMoney(total);
};

const loadCart = async () => {
    const [products, cart] = await Promise.all([
        apiRequest("/products/"),
        apiRequest("/cart/"),
    ]);
    renderCart(cart, products);
};

const handleCartEvents = () => {
    cartList.addEventListener("change", async (event) => {
        const input = event.target.closest(".qty-input");
        if (!input) {
            return;
        }
        const itemElement = event.target.closest(".cart-item");
        const itemId = itemElement.dataset.item;
        try {
            await apiRequest(`/cart/items/${itemId}/`, {
                method: "PUT",
                body: JSON.stringify({ quantity: Number(input.value) }),
            });
            await loadCart();
        } catch (error) {
            alert(error.message);
        }
    });

    cartList.addEventListener("click", async (event) => {
        const removeButton = event.target.closest("button[data-remove]");
        if (!removeButton) {
            return;
        }
        const itemId = removeButton.dataset.remove;
        try {
            await apiRequest(`/cart/remove/${itemId}/`, { method: "DELETE" });
            await loadCart();
        } catch (error) {
            alert(error.message);
        }
    });
};

const initActions = () => {
    clearCartButton.addEventListener("click", async () => {
        try {
            await apiRequest("/cart/clear/", { method: "DELETE" });
            await loadCart();
        } catch (error) {
            alert(error.message);
        }
    });

    placeOrderButton.addEventListener("click", async () => {
        try {
            const order = await apiRequest("/orders/from-cart/", { method: "POST" });
            window.location.href = `/checkout/?order_id=${order.id}`;
        } catch (error) {
            alert(error.message);
        }
    });
};

initToken();
loadCart().catch(() => {
    cartList.innerHTML = "<div class=\"empty\">Sign in to view cart.</div>";
});
handleCartEvents();
initActions();
