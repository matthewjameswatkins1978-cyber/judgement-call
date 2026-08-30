document.addEventListener('DOMContentLoaded', () => {
    const initialView = document.getElementById('initial-view');
    const runningView = document.getElementById('running-view');
    const decisionView = document.getElementById('decision-view');
    const completedView = document.getElementById('completed-view');

    const startBtn = document.getElementById('start-btn');
    const restartBtn = document.getElementById('restart-btn');
    const taskInput = document.getElementById('task-input');
    const statusMessage = document.getElementById('status-message');
    const eventTimeline = document.getElementById('event-timeline');

    const decisionQuestion = document.getElementById('decision-question');
    const decisionWhy = document.getElementById('decision-why');
    const decisionEvidence = document.getElementById('decision-evidence');
    const decisionOptions = document.getElementById('decision-options');

    const verificationBadge = document.getElementById('verification-badge');
    const diffOutput = document.getElementById('diff-output');
    const receiptGrid = document.getElementById('receipt-grid');

    let currentRunId = null;
    let currentInterruptId = null;

    function switchView(viewId) {
        [initialView, runningView, decisionView, completedView].forEach(v => v.classList.remove('active'));
        document.getElementById(viewId).classList.add('active');
    }

    function addTimelineEvent(text) {
        const li = document.createElement('li');
        li.className = 'timeline-item';
        li.textContent = text;
        eventTimeline.appendChild(li);
    }

    startBtn.addEventListener('click', async () => {
        const task = taskInput.value.trim();
        if (!task) return;

        switchView('running-view');
        eventTimeline.innerHTML = '';
        addTimelineEvent('Starting Judgement Call run...');

        try {
            const res = await fetch('/api/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ op: 'start', scenario: 'concurrency-demo', task: task })
            });
            const data = await res.json();
            handleRunResponse(data);
        } catch (err) {
            statusMessage.textContent = 'Error: ' + err.message;
            addTimelineEvent('Error executing run: ' + err.message);
        }
    });

    restartBtn.addEventListener('click', () => {
        switchView('initial-view');
    });

    function handleRunResponse(data) {
        currentRunId = data.run_id;
        if (data.status === 'needs_human') {
            currentInterruptId = data.decision.interrupt_id;
            decisionQuestion.textContent = data.decision.question;
            decisionWhy.textContent = data.decision.why_human;
            decisionEvidence.textContent = data.decision.evidence;

            decisionOptions.innerHTML = '';
            data.decision.options.forEach(opt => {
                const btn = document.createElement('button');
                btn.className = 'option-btn';
                btn.innerHTML = `<span class="option-label">${opt.id}: ${opt.label}</span><span class="option-consequence">${opt.consequence}</span>`;
                btn.addEventListener('click', () => submitResume(currentInterruptId, opt.id));
                decisionOptions.appendChild(btn);
            });

            addTimelineEvent('Attention Governor requested human judgement.');
            switchView('decision-view');
        } else if (data.status === 'completed') {
            verificationBadge.className = 'badge pass';
            verificationBadge.textContent = 'VERIFICATION: ' + data.verification;
            diffOutput.textContent = data.diff || '(no changes)';
            renderReceipt(data.receipt);
            addTimelineEvent('Run completed and successfully verified.');
            switchView('completed-view');
        } else if (data.status === 'failed') {
            verificationBadge.className = 'badge fail';
            verificationBadge.textContent = 'RUN FAILED: ' + data.code;
            diffOutput.textContent = data.message;
            renderReceipt(data.receipt);
            addTimelineEvent('Run failed: ' + data.message);
            switchView('completed-view');
        }
    }

    async function submitResume(interruptId, choiceId) {
        switchView('running-view');
        addTimelineEvent(`Human selected option ${choiceId}. Resuming run...`);

        try {
            const res = await fetch('/api/resume', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    op: 'resume',
                    interrupt_id: interruptId,
                    response: { choice_id: choiceId, note: 'User selected via web UI' }
                })
            });
            const data = await res.json();
            handleRunResponse(data);
        } catch (err) {
            statusMessage.textContent = 'Error: ' + err.message;
            addTimelineEvent('Error resuming run: ' + err.message);
        }
    }

    function renderReceipt(receipt) {
        receiptGrid.innerHTML = '';
        const fields = [
            { label: 'Decision Proposals', key: 'decision_proposals' },
            { label: 'Auto-Resolved', key: 'auto_resolved' },
            { label: 'Human Interrupts', key: 'human_interrupts' },
            { label: 'Policy Denials', key: 'policy_denials' },
            { label: 'Tool Calls', key: 'tool_calls' },
            { label: 'Test Runs', key: 'test_runs' },
            { label: 'Verifier Passed', key: 'final_verifier_passed' }
        ];

        fields.forEach(f => {
            const div = document.createElement('div');
            div.className = 'receipt-item';
            div.innerHTML = `<span class="receipt-value">${receipt[f.key]}</span><span class="receipt-label">${f.label}</span>`;
            receiptGrid.appendChild(div);
        });
    }
});
