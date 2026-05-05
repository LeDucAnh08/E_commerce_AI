const tokenField = document.getElementById("accessToken");
const saveTokenButton = document.getElementById("saveToken");
const productGrid = document.getElementById("productGrid");
const categoryPills = document.getElementById("categoryPills");
const cartPreview = document.getElementById("cartPreview");

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
                <div>
                    <h3>${product.name}</h3>
                    <div class="product-meta">
                        <span>${product.category}</span>
                        <span>${product.type || "general"}</span>
                    </div>
                </div>
                <div class="price">${formatMoney(product.price)}</div>
                <button class="btn primary" data-product="${product.id}">Add to cart</button>
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
    } catch (error) {
        cartPreview.innerHTML = "<div class=\"empty\">Sign in to view cart.</div>";
    }
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

const initCatalog = async () => {
    await loadCategories();
    let products = await loadProducts();
    await loadCartPreview(products);

    document.querySelectorAll(".pill").forEach((pill) => {
        pill.addEventListener("click", async () => {
            document.querySelectorAll(".pill").forEach((p) => p.classList.remove("active"));
            pill.classList.add("active");
            products = await loadProducts(pill.dataset.category || "");
        });
    });

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
            await loadCartPreview(products);
        } catch (error) {
            alert(error.message);
        }
    });
};

initToken();
if (productGrid) {
    initCatalog();
}
