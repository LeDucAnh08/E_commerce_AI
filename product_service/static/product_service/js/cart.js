const cartList = document.getElementById("cartList");
const cartTotal = document.getElementById("cartTotal");
const clearCartButton = document.getElementById("clearCart");
const placeOrderButton = document.getElementById("placeOrder");
const cartRecommendations = document.getElementById("cartRecommendations");

const formatMoney = (value) => `$${Number(value).toFixed(2)}`;
const fallbackImage = "https://placehold.co/600x400/f3f4f6/111827?text=Product";
const getToken = () => localStorage.getItem("accessToken") || "";

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

const renderRecommendationCards = (products) => {
    if (!cartRecommendations) {
        return;
    }
    if (!products.length) {
        cartRecommendations.innerHTML = "<div class=\"empty\">No recommendations yet.</div>";
        return;
    }
    cartRecommendations.innerHTML = products
        .map(
            (product) => `
            <article class="recommendation-card">
                <img src="${product.image_url || fallbackImage}" alt="${product.name}" loading="lazy" />
                <div>
                    <strong>${product.name}</strong>
                    <span>${product.category} - ${formatMoney(product.price)}</span>
                </div>
                <a class="btn ghost" href="/products/${product.id}/ui/">View</a>
            </article>
        `,
        )
        .join("");
};

const renderCart = (cart, products) => {
    if (!cartList) {
        return;
    }
    if (!cart.items.length) {
        cartList.innerHTML = "<div class=\"empty\">Cart is empty.</div>";
        cartTotal.textContent = formatMoney(0);
        renderRecommendationCards([]);
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

const renderFrequentlyBoughtTogether = async (cart, products) => {
    const productIds = (cart.items || []).map((item) => item.product_id);
    if (!productIds.length) {
        renderRecommendationCards([]);
        return;
    }
    try {
        const recommendation = await apiRequest(
            `/ai/frequently-bought-together/?product_ids=${productIds.join(",")}&limit=5`,
        );
        const productMap = Object.fromEntries(products.map((product) => [product.id, product]));
        const recommendedProducts = (recommendation.product_ids || [])
            .map((productId) => productMap[productId])
            .filter(Boolean);
        renderRecommendationCards(recommendedProducts);
    } catch (error) {
        renderRecommendationCards([]);
    }
};

const loadCart = async () => {
    const [products, cart] = await Promise.all([
        apiRequest("/products/"),
        apiRequest("/cart/"),
    ]);
    renderCart(cart, products);
    await renderFrequentlyBoughtTogether(cart, products);
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
        window.location.href = "/checkout/";
    });
};

loadCart().catch(() => {
    cartList.innerHTML = "<div class=\"empty\">Cart is unavailable.</div>";
});
handleCartEvents();
initActions();
