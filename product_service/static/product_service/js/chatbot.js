const chatbotWidget = document.getElementById("chatbotWidget");
const chatbotToggle = document.getElementById("chatbotToggle");
const chatbotClose = document.getElementById("chatbotClose");
const chatbotPanel = document.getElementById("chatbotPanel");
const chatbotMessages = document.getElementById("chatbotMessages");
const chatbotForm = document.getElementById("chatbotForm");
const chatbotInput = document.getElementById("chatbotInput");
const chatbotRefresh = document.getElementById("chatbotRefresh");
const chatbotPrompts = document.querySelectorAll("[data-chat-prompt]");

const chatbotEndpoint = `${window.location.protocol}//${window.location.hostname}:8001/chatbot`;

const formatChatProduct = (product) => {
    if (product && typeof product === "object") {
        const price = Number(product.price);
        const priceText = Number.isFinite(price) ? ` - $${price.toFixed(2)}` : "";
        const categoryText = product.category ? ` (${product.category})` : "";
        const fallbackName = product.id ? `Product ${product.id}` : "Product";
        return `${product.name || fallbackName}${categoryText}${priceText}`;
    }
    return `Product ${product}`;
};

const appendChatMessage = (text, type = "bot", products = []) => {
    if (!chatbotMessages) {
        return null;
    }
    const message = document.createElement("div");
    message.className = `chat-message ${type}`;

    const textElement = document.createElement("div");
    textElement.textContent = text;
    message.appendChild(textElement);

    if (products.length) {
        const productList = document.createElement("div");
        productList.className = "chat-products";
        products.forEach((product) => {
            const badge = document.createElement("span");
            badge.textContent = formatChatProduct(product);
            productList.appendChild(badge);
        });
        message.appendChild(productList);
    }

    chatbotMessages.appendChild(message);
    chatbotMessages.scrollTop = chatbotMessages.scrollHeight;
    return message;
};

const updateChatMessage = (messageElement, text, type = "bot", products = []) => {
    if (!messageElement) {
        return;
    }
    messageElement.className = `chat-message ${type}`;
    messageElement.innerHTML = "";
    const textElement = document.createElement("div");
    textElement.textContent = text;
    messageElement.appendChild(textElement);
    if (products.length) {
        const productList = document.createElement("div");
        productList.className = "chat-products";
        products.forEach((product) => {
            const badge = document.createElement("span");
            badge.textContent = formatChatProduct(product);
            productList.appendChild(badge);
        });
        messageElement.appendChild(productList);
    }
    chatbotMessages.scrollTop = chatbotMessages.scrollHeight;
};

const setChatbotOpen = (isOpen) => {
    if (!chatbotWidget || !chatbotPanel) {
        return;
    }
    chatbotWidget.classList.toggle("open", isOpen);
    chatbotPanel.hidden = !isOpen;
    chatbotPanel.setAttribute("aria-hidden", isOpen ? "false" : "true");
    if (isOpen && chatbotInput) {
        chatbotInput.focus();
    }
};

const resetChatbotMessages = () => {
    if (!chatbotMessages) {
        return;
    }
    chatbotMessages.innerHTML = `
        <div class="chatbot-date-divider">
            <span></span>
            <time>Today</time>
            <span></span>
        </div>
        <div class="chat-message bot">
            Hi there! I can help you find products, compare options, and pick the right item.
        </div>
        <div class="chatbot-quick-replies" aria-label="Quick replies">
            <button type="button" data-chat-prompt="Yes, recommend something for me">Yes, sure!</button>
            <button type="button" data-chat-prompt="No thanks, show popular products">No, thanks!</button>
        </div>
    `;
    chatbotMessages.querySelectorAll("[data-chat-prompt]").forEach((button) => {
        button.addEventListener("click", handlePromptClick);
    });
};

const askAssistant = async (message) => {
    const response = await fetch(chatbotEndpoint, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({ message }),
    });

    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
        throw new Error(data.detail || data.error || "AI service request failed");
    }
    return data;
};

setChatbotOpen(false);

if (chatbotToggle) {
    chatbotToggle.addEventListener("click", () => {
        setChatbotOpen(!chatbotWidget.classList.contains("open"));
    });
}

if (chatbotClose) {
    chatbotClose.addEventListener("click", () => setChatbotOpen(false));
}

if (chatbotRefresh) {
    chatbotRefresh.addEventListener("click", resetChatbotMessages);
}

if (chatbotForm) {
    chatbotForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const message = chatbotInput.value.trim();
        if (!message) {
            return;
        }

        appendChatMessage(message, "user");
        chatbotInput.value = "";
        chatbotInput.disabled = true;

        const pendingMessage = appendChatMessage("Thinking...", "bot loading");
        try {
            const data = await askAssistant(message);
            const products = Array.isArray(data.products) ? data.products : [];
            updateChatMessage(pendingMessage, data.reply || "No reply returned.", "bot", products);
        } catch (error) {
            updateChatMessage(
                pendingMessage,
                `AI service unavailable: ${error.message}`,
                "bot error",
            );
        } finally {
            chatbotInput.disabled = false;
            chatbotInput.focus();
        }
    });
}

const handlePromptClick = (event) => {
    const button = event.currentTarget;
    if (button && chatbotInput && chatbotForm) {
        setChatbotOpen(true);
        chatbotInput.value = button.dataset.chatPrompt || "";
        chatbotForm.requestSubmit();
    }
};

chatbotPrompts.forEach((button) => {
    button.addEventListener("click", handlePromptClick);
});
