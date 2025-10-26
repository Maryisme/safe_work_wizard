
document.addEventListener('DOMContentLoaded', () => {

    const API_BASE = window.API_BASE || 'http://127.0.0.1:5001';


    // hold all the questions in an array of objects
    const questions = [
        {
            id: 'Q1',
            text: 'Do you feel that you have been bullied or harassed by someone?',
            type: 'single',
            options: ['Yes', 'No']
        },
        {
            id: 'Q2',
            text: 'Was the bullying or harassment from a co-worker?',
            type: 'single',
            options: ['Yes', 'No']
        },
        {
            id: 'Q3',
            text: 'Do you think that your co-worker was trying to humiliate you?',
            type: 'single',
            options: ['Yes', 'No', "I don't know"]
        },
        {
            id: 'Q4',
            text: 'Do you think that your co-worker was trying to intimidate you?',
            type: 'single',
            options: ['Yes', 'No', "I don't know"]
        },
        {
            id: 'Q5',
            text: 'Was the bullying or harassing behaviour connected to any of these?',
            type: 'multi',
            options: [
                'Your Indigenous identity',
                'Your race',
                'Your skin colour',
                'Ancestry',
                'Where you were born or grew up',
                'Your religion',
                'Whether you have parents or children',
                'Your physical disability',
                'Your mental disability',
                'Your biological sex',
                'Your gender',
                'Your age',
                'Your sexual orientation',
                'Your gender identity or gender expression',
                'Your political beliefs',
                'A previous criminal conviction that is not related to your employment',
                'None of these'
            ]
        },
        {
            id: 'Q6',
            text: 'Describe your situation',
            type: 'text'   // open text box unlike others
        }
    ];


    let idx = 0;
    // strings for single-select; arrays for multi-select
    const answers = {};
    questions.forEach(q => (answers[q.text] = q.type === 'multi' ? [] : ''));

    // DOM
    const qLabel = document.getElementById('qLabel');
    const qText  = document.getElementById('qText');
    const group  = document.getElementById('choiceGroup');
    const prevBtn = document.getElementById('prevBtn');
    const nextBtn = document.getElementById('nextBtn');
    const submitBtn = document.getElementById('submitBtn');
    const resetBtn  = document.getElementById('resetBtn');
    const responseBox = document.getElementById('responseBox');
    const qPane = document.querySelector('.q-pane');


    function playOnce(el, cls) {
        return new Promise(resolve => {
            const onEnd = () => { el.removeEventListener('animationend', onEnd); el.classList.remove(cls); resolve(); };
            el.addEventListener('animationend', onEnd, { once: true });
            // force reflow so repeated animations retrigger reliably
            void el.offsetWidth;
            el.classList.add(cls);
        });
    }

    async function slideTo(direction, updateFn) {
        if (!qPane) { updateFn(); return; }

        if (direction === 'next') {
            await playOnce(qPane, 'slide-out-left');
            updateFn();                     // re-render content for the next question
            await playOnce(qPane, 'slide-in-right');
        } else {
            await playOnce(qPane, 'slide-out-right');
            updateFn();                     // re-render content for the previous question
            await playOnce(qPane, 'slide-in-left');
        }
    }

    function typewriter(el, text, { min = 2, max = 5 } = {}) {
        el.classList.add('typing');
        el.textContent = '';
        let i = 0;
        (function tick() {
            if (i < text.length) {
                el.textContent += text[i++];
                el.scrollTop = el.scrollHeight;
                // Slightly slower on line-breaks or bullet characters for nice cadence
                const ch = text[i - 1];
                const slow = (ch === '\n' || ch === '.' || ch === '•' || ch === '-');
                const delay = slow ? max : min;
                setTimeout(tick, delay);
            } else {
                el.classList.remove('typing');
            }
        })();
    }

    function render() {
        const q = questions[idx];
        qLabel.textContent = q.id;
        qText.textContent  = q.text;
        group.innerHTML = '';

        group.classList.toggle('no-frame', q.type === 'text');



        // build choices
        group.innerHTML = '';
        if (q.type === 'single') {
            group.setAttribute('role', 'radiogroup');
            q.options.forEach((opt, i) => {
                const id = `q${idx}-opt${i}`;
                const label = document.createElement('label');
                label.className = 'choice';

                const input = document.createElement('input');
                input.type = 'radio';
                input.name = 'answer';
                input.id = id;
                input.value = opt;
                input.checked = answers[q.text] === opt;

                const span = document.createElement('span');
                span.textContent = opt;

                label.append(input, span);
                group.appendChild(label);
            });
        } else if (q.type === 'multi') {
            group.setAttribute('role', 'group');
            q.options.forEach((opt, i) => {
                const id = `q${idx}-opt${i}`;
                const label = document.createElement('label');
                label.className = 'choice';

                const input = document.createElement('input');
                input.type = 'checkbox';
                input.name = 'answer-multi';
                input.id = id;
                input.value = opt;
                input.checked = Array.isArray(answers[q.text]) && answers[q.text].includes(opt);

                input.addEventListener('change', () => {
                    if (opt === 'None of these' && input.checked) {
                        document.querySelectorAll('input[name="answer-multi"]').forEach(cb => {
                            if (cb.value !== 'None of these') cb.checked = false;
                        });
                    } else if (input.checked) {
                        const none = [...document.querySelectorAll('input[name="answer-multi"]')].find(cb => cb.value === 'None of these');
                        if (none) none.checked = false;
                    }
                });

                const span = document.createElement('span');
                span.textContent = opt;

                label.append(input, span);
                group.appendChild(label);
            });
        } else if (q.type === 'text') {
        group.setAttribute('role', 'group');
        const textarea = document.createElement('textarea');
        textarea.id = 'textAnswer';
        textarea.className = 'answer-box';        // uses your existing textarea styling
        textarea.placeholder = 'Describe your situation...';
        textarea.value = typeof answers[q.text] === 'string' ? answers[q.text] : '';
        group.appendChild(textarea);
        textarea.focus();                          // optional: auto-focus
        }

        prevBtn.disabled = idx === 0;
        nextBtn.disabled = idx === questions.length - 1;
    }

    function storeCurrent() {
        const q = questions[idx];
        if (q.type === 'single') {
            const sel = document.querySelector('input[name="answer"]:checked');
            answers[q.text] = sel ? sel.value : '';
        } else if (q.type === 'multi') {
            const sels = [...document.querySelectorAll('input[name="answer-multi"]:checked')].map(n => n.value);
            answers[q.text] = sels;
        } else if (q.type === 'text') {
            const ta = document.getElementById('textAnswer');
            answers[q.text] = ta ? ta.value.trim() : '';
        }
    }

    function isAnswered(q) {
        const val = answers[q.text];
        if (q.type === 'single') return !!val;
        if (q.type === 'multi')  return Array.isArray(val) && val.length > 0;
        if (q.type === 'text')   return typeof val === 'string' && val.trim().length > 0;
        return false;
    }


    prevBtn.addEventListener('click', async () => {
        storeCurrent();
        if (idx > 0) {
            await slideTo('prev', () => { idx--; render(); });
        }
    });

    nextBtn.addEventListener('click', async () => {
        storeCurrent();
        if (idx < questions.length - 1) {
            await slideTo('next', () => { idx++; render(); });
        }
    });

    resetBtn.addEventListener('click', () => {
        questions.forEach(q => (answers[q.text] = q.type === 'multi' ? [] : ''));
        idx = 0;
        responseBox.textContent = '';
        render();
    });

    submitBtn.addEventListener('click', async () => {
        storeCurrent();
        const firstMissing = questions.find(q => !isAnswered(q));
        if (firstMissing) {
            idx = questions.indexOf(firstMissing);
            render();
            return;
        }

        responseBox.textContent = 'Thinking…';
        try {
            const payload = JSON.stringify(answers, null, 2);

            const r = await fetch(`${API_BASE}/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: `Use this questionnaire to provide guidance.\n${payload}`,
                    history: []
                })
            });

            const { reply, error } = await r.json();
            if (error) {
                responseBox.textContent = `Error: ${error}`;
            } else {
                typewriter(responseBox, reply);
            }

            responseBox.scrollTop = responseBox.scrollHeight;
        } catch (e) {
            responseBox.textContent = 'Network error contacting the server.';
        }
    });

    render();
});
