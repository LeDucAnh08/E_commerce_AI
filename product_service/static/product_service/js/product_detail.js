const productDetail = document.getElementById("productDetail");
const similarProducts = document.getElementById("similarProducts");
const fallbackImage = "https://placehold.co/600x400/f3f4f6/111827?text=Product";

const formatMoney = (value) => `$${Number(value).toFixed(2)}`;
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

const productCard = (product) => `
    <article class="recommendation-card">
        <img src="${product.image_url || fallbackImage}" alt="${product.name}" loading="lazy" />
        <div>
            <strong>${product.name}</strong>
            <span>${product.category} - ${formatMoney(product.price)}</span>
        </div>
        <a class="btn ghost" href="/products/${product.id}/ui/">View</a>
    </article>
`;

const renderDetail = (product) => {
    productDetail.innerHTML = `
        <article class="product-detail-card">
            <img
                src="${product.image_url || fallbackImage}"
                alt="${product.name}"
                onerror="this.onerror=null;this.src='${fallbackImage}';"
            />
            <div>
                <div class="product-meta">
                    <span>${product.category}</span>
                    <span>${product.type || "general"}</span>
                </div>
                <h1>${product.name}</h1>
                <div class="price">${formatMoney(product.price)}</div>
                <p>Stock: ${product.stock}</p>
                <button class="btn primary" data-product="${product.id}">Add to cart</button>
            </div>
        </article>
    `;
};

const renderSimilar = (products) => {
    if (!products.length) {
        similarProducts.innerHTML = "<div class=\"empty\">No similar products yet.</div>";
        return;
    }
    similarProducts.innerHTML = products.map(productCard).join("");
};

const initProductDetail = async () => {
    const productId = Number(productDetail.dataset.productId);
    const [product, allProducts] = await Promise.all([
        apiRequest(`/products/${productId}/`),
        apiRequest("/products/"),
    ]);
    renderDetail(product);
    trackBehavior(productId, "view");

    try {
        const similar = await apiRequest(`/ai/similar-products/${productId}/?limit=5`);
        const productMap = Object.fromEntries(allProducts.map((item) => [item.id, item]));
        renderSimilar((similar.product_ids || []).map((id) => productMap[id]).filter(Boolean));
    } catch (error) {
        renderSimilar([]);
    }

    productDetail.addEventListener("click", async (event) => {
        const button = event.target.closest("button[data-product]");
        if (!button) {
            return;
        }
        await apiRequest("/cart/add/", {
            method: "POST",
            body: JSON.stringify({ product_id: Number(button.dataset.product), quantity: 1 }),
        });
        trackBehavior(Number(button.dataset.product), "add_to_cart");
        button.textContent = "Added";
    });
};

if (productDetail) {
    initProductDetail().catch(() => {
        productDetail.innerHTML = "<div class=\"empty\">Product detail is unavailable.</div>";
    });
}
