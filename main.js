


document.addEventListener('DOMContentLoaded', () => {

    const form = document.querySelector('.chat-input');
    const input = form.querySelector('input[type="text"]');
    const content = document.querySelector('.chat-content');


    form.addEventListener('submit', (e) => {

        e.preventDefault();

        const text = input.value.trim();
        if (!text) return;

        appendMessage(text, 'me')
        input.value = '';
        input.focus();
        content.scrollTop = content.scrollHeight;


        setTimeout(() => appendMessage("This is a bot reply.", 'bot'), 600);

    })

    function appendMessage(text, who = "me") {

        const row = document.createElement('div');
        row.className = `msg ${who}`;

        const bubble = document.createElement('div');
        bubble.className = 'bubble';
        bubble.textContent = text;

        row.appendChild(bubble);
        content.appendChild(row);
    }



})

