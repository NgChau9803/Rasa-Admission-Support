(function() {
    // Configuration
    const RASA_URL = "http://localhost:5005";
    const BOT_AVATAR = "bot-avatar.png";
    const WIDGET_ICON = `<svg viewBox="0 0 24 24"><path d="M20,2H4C2.9,2,2,2.9,2,4v18l4-4h14c1.1,0,2-0.9,2-2V4C22,2.9,21.1,2,20,2z M20,16H5.2L4,17.2V4h16V16z M7,9h10V7H7V9z M7,13h10v-2H7V13z"/></svg>`;
    const CLOSE_ICON = `<svg viewBox="0 0 24 24"><path d="M19,6.41L17.59,5,12,10.59,6.41,5,5,6.41,10.59,12,5,17.59,6.41,19,12,13.41,17.59,19,19,17.59,13.41,12z"/></svg>`;

    // 1. Inject CSS if not already there
    if (!document.getElementById('rasa-widget-styles')) {
        const link = document.createElement('link');
        link.id = 'rasa-widget-styles';
        link.rel = 'stylesheet';
        link.href = 'widget-style.css';
        document.head.appendChild(link);
    }

    // 2. Load Socket.io Client
    const script = document.createElement('script');
    script.src = "https://cdn.socket.io/4.7.2/socket.io.min.js";
    script.onload = initWidget;
    document.head.appendChild(script);

    function initWidget() {
        const container = document.createElement('div');
        container.id = 'rasa-widget-container';
        container.innerHTML = `
            <div id="rasa-chat-window">
                <div class="rasa-chat-header">
                    <img src="${BOT_AVATAR}" alt="Bot">
                    <div class="rasa-chat-header-info">
                        <h3>SOICT Assistant</h3>
                        <span>Trực tuyến</span>
                    </div>
                </div>
                <div id="rasa-chat-messages"></div>
                <div class="typing-indicator" id="rasa-typing">
                    <span></span><span></span><span></span>
                </div>
                <div class="rasa-chat-input-area">
                    <input type="text" id="rasa-user-input" placeholder="Hỏi tôi bất cứ điều gì...">
                    <button id="rasa-send-btn">
                        <svg viewBox="0 0 24 24" style="width:20px;height:20px;fill:white;"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>
                    </button>
                </div>
            </div>
            <div id="rasa-widget-launcher">
                ${WIDGET_ICON}
            </div>
        `;
        document.body.appendChild(container);

        const launcher = document.getElementById('rasa-widget-launcher');
        const chatWindow = document.getElementById('rasa-chat-window');
        const input = document.getElementById('rasa-user-input');
        const sendBtn = document.getElementById('rasa-send-btn');
        const messageContainer = document.getElementById('rasa-chat-messages');
        const typingIndicator = document.getElementById('rasa-typing');

        let currentBotBubble = null;

        // Socket.io Connection with forced WebSocket transport to avoid CORS polling issues
        const socket = io(RASA_URL, {
            transports: ['websocket']
        });

        // UI Toggling
        launcher.onclick = () => {
            chatWindow.classList.toggle('active');
            if (chatWindow.classList.contains('active')) {
                launcher.innerHTML = CLOSE_ICON;
                input.focus();
            } else {
                launcher.innerHTML = WIDGET_ICON;
            }
        };

        // Communication Logic
        function addMessage(text, sender, isPartial = false) {
            if (isPartial && currentBotBubble && sender === 'bot') {
                // Update existing bubble
                const cleanText = formatText(text);
                currentBotBubble.innerText += cleanText;
                messageContainer.scrollTop = messageContainer.scrollHeight;
                return;
            }

            const div = document.createElement('div');
            div.className = `rasa-msg ${sender}`;
            div.innerText = formatText(text);
            messageContainer.appendChild(div);
            messageContainer.scrollTop = messageContainer.scrollHeight;

            if (isPartial && sender === 'bot') {
                currentBotBubble = div;
            } else {
                currentBotBubble = null;
            }
        }

        function formatText(text) {
            if (!text) return "";
            // Clean up markdown bullets like "* " or " *"
            let cleanText = text.replace(/^\s*\* /gm, '• '); 
            cleanText = cleanText.replace(/\*\*/g, ''); 
            return cleanText;
        }

        function sendMessage() {
            const text = input.value.trim();
            if (text === "") return;

            addMessage(text, 'user');
            input.value = "";
            currentBotBubble = null;
            
            // Show typing indicator
            typingIndicator.style.display = 'block';
            messageContainer.scrollTop = messageContainer.scrollHeight;

            socket.emit('user_uttered', {
                "message": text,
                "session_id": socket.id || "local_user"
            });
        }

        sendBtn.onclick = sendMessage;
        input.onkeypress = (e) => { if (e.key === 'Enter') sendMessage(); };

        // Handle Bot Responses (Supporting Streaming)
        socket.on('bot_uttered', (response) => {
            typingIndicator.style.display = 'none';
            
            const isPartial = response.metadata && response.metadata.is_partial;
            
            if (response.text) {
                addMessage(response.text, 'bot', isPartial);
            }
            
            // If it's a final message, reset the stream tracker
            if (!isPartial) {
                currentBotBubble = null;
            }

            if (response.attachment) {
                // Handle images/etc if needed
            }
        });

        socket.on('connect', () => {
            console.log("Rasa Socket Connected (Streaming Enabled)");
        });
    }
})();
