// Simple multi-question wizard + submit to your Python /chat endpoint
document.addEventListener('DOMContentLoaded', () => {
    const questions = [
        { label: 'Q1', placeholder: 'answer 1' },
        { label: 'Q2', placeholder: 'answer 2' },
        { label: 'Q3', placeholder: 'answer 3' },
    ];

    let idx = 0;
    const answers = new Array(questions.length).fill('');

    const qLabel = document.getElementById('qLabel');
    const answerBox = document.getElementById('answerBox');
    const prevBtn = document.getElementById('prevBtn');
    const nextBtn = document.getElementById('nextBtn');
    const submitBtn = document.getElementById('submitBtn');
    const resetBtn = document.getElementById('resetBtn');
    const responseBox = document.getElementById('responseBox');

    function render() {
        const q = questions[idx];
        qLabel.textContent = q.label;
        answerBox.placeholder = q.placeholder;
        answerBox.value = answers[idx] || '';

        prevBtn.disabled = idx === 0;
        nextBtn.disabled = idx === questions.length - 1;
    }

    function storeCurrent() {
        answers[idx] = answerBox.value.trim();
    }

    prevBtn.addEventListener('click', () => {
        storeCurrent();
        if (idx > 0) idx--;
        render();
    });

    nextBtn.addEventListener('click', () => {
        storeCurrent();
        if (idx < questions.length - 1) idx++;
        render();
    });

    resetBtn.addEventListener('click', () => {
        for (let i = 0; i < answers.length; i++) answers[i] = '';
        idx = 0;
        responseBox.textContent = '';
        render();
        answerBox.focus();
    });

    submitBtn.addEventListener('click', async () => {
        storeCurrent();

        // Require all questions answered
        const missing = answers.findIndex(v => !v);
        if (missing !== -1) {
            idx = missing;
            render();
            answerBox.focus();
            return;
        }

        // Compose a concise prompt for your backend
        const prompt = questions
            .map((q, i) => `${q.label}: ${answers[i]}`)
            .join('\n');

        responseBox.textContent = 'Thinking…';

        try {
            // POST to your Flask endpoint (change URL/port to your server)
            const r = await fetch('http://127.0.0.1:5001/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: `Use these answers to provide guidance:\n${prompt}`,
                    history: []
                }),
            });
            const { reply, error } = await r.json();
            responseBox.textContent = error ? `Error: ${error}` : reply;
            responseBox.scrollTop = responseBox.scrollHeight;
        } catch (e) {
            responseBox.textContent = 'Network error contacting the server.';
        }
    });

    // init
    render();
    answerBox.focus();
});
