const form = document.getElementById("chat-form");
const input = document.getElementById("message");
const messages = document.getElementById("messages");

form.addEventListener("submit", async (event) => {
    event.preventDefault();

    const message = input.value.trim();
    if (!message) return;

    messages.innerHTML += `<div class="user"></div>`;
    messages.lastElementChild.textContent = message;
    input.value = "";

    try {
        const response = await fetch("/chat", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ message })
        });

        const data = await response.json();

        const reply = document.createElement("div");
        reply.className = "bot";
        reply.textContent = data.reply || data.error;
        messages.appendChild(reply);
    } catch {
        const error = document.createElement("div");
        error.className = "bot";
        error.textContent = "Unable to connect. Please try again.";
        messages.appendChild(error);
    }
});