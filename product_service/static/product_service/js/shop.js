const productGrid = document.getElementById("productGrid");
const categoryPills = document.getElementById("categoryPills");
const cartPreview = document.getElementById("cartPreview");
const cartRecommendations = document.getElementById("cartRecommendations");
const aiSearchForm = document.getElementById("aiSearchForm");
const aiSearchInput = document.getElementById("aiSearchInput");

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

const trackBehavior = (productId, action) => {
    apiRequest("/ai/behavior/", {
        method: "POST",
        body: JSON.stringify({ user_id: 0, product_id: productId, action }),
    }).catch(() => {});
};

const renderRecommendationCards = (container, products) => {
    if (!container) {
        return;
    }
    if (!products.length) {
        container.innerHTML = "<div class=\"empty\">No recommendations yet.</div>";
        return;
    }
    container.innerHTML = products
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

const renderProducts = (products) => {
    if (!productGrid) {
        return;
    }
    if (!products.length) {
        productGrid.innerHTML = "<div class=\"empty\">No products found.</div>";
        return;
    }
    productGrid.innerHTML = products
        .map(
            (product) => `
            <article class="product-card">
                <img
                    class="product-image"
                    src="${product.image_url || fallbackImage}"
                    alt="${product.name}"
                    loading="lazy"
                    onerror="this.onerror=null;this.src='${fallbackImage}';"
                />
                <div>
                    <h3>${product.name}</h3>
                    <div class="product-meta">
                        <span>${product.category}</span>
                        <span>${product.type || "general"}</span>
                    </div>
                </div>
                <div class="price">${formatMoney(product.price)}</div>
                <div class="product-actions">
                    <a class="btn ghost" href="/products/${product.id}/ui/">View</a>
                    <button class="btn primary" data-product="${product.id}">Add to cart</button>
                </div>
            </article>
        `,
        )
        .join("");
};

const renderCartPreview = (cart, products) => {
    if (!cartPreview) {
        return;
    }
    if (!cart || !cart.items || cart.items.length === 0) {
        cartPreview.innerHTML = "<div class=\"empty\">Cart is empty.</div>";
        return;
    }
    const productMap = Object.fromEntries(products.map((product) => [product.id, product]));
    cartPreview.innerHTML = cart.items
        .map((item) => {
            const product = productMap[item.product_id] || {};
            return `
            <div class="cart-item">
                <strong>${product.name || "Product"}</strong>
                <span>${formatMoney(product.price || 0)}</span>
                <span>Qty ${item.quantity}</span>
                <span>${formatMoney((product.price || 0) * item.quantity)}</span>
            </div>
        `;
        })
        .join("");
};

const loadCategories = async () => {
    const categories = await apiRequest("/categories/");
    if (!categoryPills) {
        return;
    }
    categoryPills.innerHTML = categories
        .map(
            (category) =>
                `<button class="pill" data-category="${category.name}">${category.name}</button>`,
        )
        .join("");
};

const loadProducts = async (category = "") => {
    const query = category ? `?category=${encodeURIComponent(category)}` : "";
    const products = await apiRequest(`/products/${query}`);
    renderProducts(products);
    return products;
};

const loadCartPreview = async (products) => {
    try {
        const cart = await apiRequest("/cart/");
        renderCartPreview(cart, products);
        await loadCartRecommendations(cart, products);
    } catch (error) {
        cartPreview.innerHTML = "<div class=\"empty\">Cart is unavailable.</div>";
    }
};

const loadCartRecommendations = async (cart, products) => {
    if (!cartRecommendations) {
        return;
    }
    const productIds = (cart.items || []).map((item) => item.product_id);
    if (!productIds.length) {
        renderRecommendationCards(cartRecommendations, []);
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
        renderRecommendationCards(cartRecommendations, recommendedProducts);
    } catch (error) {
        renderRecommendationCards(cartRecommendations, []);
    }
};

const initCatalog = async () => {
    await loadCategories();
    const allProducts = await apiRequest("/products/");
    let products = allProducts;
    renderProducts(products);
    await loadCartPreview(allProducts);

    document.querySelectorAll(".pill").forEach((pill) => {
        pill.addEventListener("click", async () => {
            document.querySelectorAll(".pill").forEach((p) => p.classList.remove("active"));
            pill.classList.add("active");
            products = pill.dataset.category
                ? allProducts.filter((product) => product.category === pill.dataset.category)
                : allProducts;
            renderProducts(products);
        });
    });

    if (aiSearchForm) {
        aiSearchForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            const query = aiSearchInput.value.trim();
            if (!query) {
                return;
            }
            const search = await apiRequest(`/ai/search-products/?q=${encodeURIComponent(query)}&limit=20`);
            const productMap = Object.fromEntries(allProducts.map((product) => [product.id, product]));
            const results = (search.product_ids || [])
                .map((productId) => productMap[productId])
                .filter(Boolean);
            renderProducts(results);
        });
    }

    productGrid.addEventListener("click", async (event) => {
        const button = event.target.closest("button[data-product]");
        if (!button) {
            return;
        }
        try {
            await apiRequest("/cart/add/", {
                method: "POST",
                body: JSON.stringify({ product_id: Number(button.dataset.product), quantity: 1 }),
            });
            trackBehavior(Number(button.dataset.product), "add_to_cart");
            await loadCartPreview(allProducts);
        } catch (error) {
            alert(error.message);
        }
    });
};

if (productGrid) {
    initCatalog();
}
