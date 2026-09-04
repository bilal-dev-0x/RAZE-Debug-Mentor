/**
 * RAZE — AI Debugging Mentor
 * Frontend Controller & Session Management
 *
 * Implements:
 * 1. Strict session isolation with race-condition guards.
 * 2. Editor tab handling & synchronized line numbering.
 * 3. Execution console integration.
 * 4. Progressive 2-question mentor dialogue with strict STOP RULE.
 * 5. 5-part final solution presentation with Prism syntax highlighting.
 */

document.addEventListener('DOMContentLoaded', () => {
  // Application State
  let activeSessionId = null;
  let activeLanguage = 'python';

  // DOM Elements
  const codeEditor = document.getElementById('codeEditor');
  const lineNumbers = document.getElementById('lineNumbers');
  const languageSelect = document.getElementById('languageSelect');
  const executionBadge = document.getElementById('executionBadge');

  const inputError = document.getElementById('inputError');
  const inputExpected = document.getElementById('inputExpected');
  const inputActual = document.getElementById('inputActual');

  const btnRunCode = document.getElementById('btnRunCode');
  const btnStartSession = document.getElementById('btnStartSession');
  const btnNewSession = document.getElementById('btnNewSession');
  const btnClearCode = document.getElementById('btnClearCode');
  const btnClearConsole = document.getElementById('btnClearConsole');
  const btnSolveAnother = document.getElementById('btnSolveAnother');

  const btnLoadExampleA = document.getElementById('btnLoadExampleA');
  const btnLoadExampleB = document.getElementById('btnLoadExampleB');

  const consoleOutput = document.getElementById('consoleOutput');
  const consoleStatus = document.getElementById('consoleStatus');

  const sessionStatusText = document.getElementById('sessionStatusText');
  const sessionPill = document.getElementById('sessionPill');
  const sessionShortId = document.getElementById('sessionShortId');

  const calmLoader = document.getElementById('calmLoader');
  const loaderText = document.getElementById('loaderText');
  const emptyState = document.getElementById('emptyState');

  const cardObservation = document.getElementById('cardObservation');
  const observationContent = document.getElementById('observationContent');

  const cardQ1 = document.getElementById('cardQ1');
  const question1Content = document.getElementById('question1Content');
  const formAnswer1 = document.getElementById('formAnswer1');
  const inputAnswer1 = document.getElementById('inputAnswer1');
  const userResponse1 = document.getElementById('userResponse1');
  const userText1 = document.getElementById('userText1');

  const cardQ2 = document.getElementById('cardQ2');
  const question2Content = document.getElementById('question2Content');
  const formAnswer2 = document.getElementById('formAnswer2');
  const inputAnswer2 = document.getElementById('inputAnswer2');
  const userResponse2 = document.getElementById('userResponse2');
  const userText2 = document.getElementById('userText2');

  const solutionContainer = document.getElementById('solutionContainer');
  const rootCauseValue = document.getElementById('rootCauseValue');
  const solWhatIFound = document.getElementById('solWhatIFound');
  const solWhatsHappening = document.getElementById('solWhatsHappening');
  const solRootCauseText = document.getElementById('solRootCauseText');
  const solCorrectedCode = document.getElementById('solCorrectedCode');
  const solWhyFixWorks = document.getElementById('solWhyFixWorks');
  const solLessonText = document.getElementById('solLessonText');
  const btnCopySolution = document.getElementById('btnCopySolution');
  const copyText = document.getElementById('copyText');

  const stepIndicatorObs = document.getElementById('stepIndicatorObs');
  const stepIndicatorQ1 = document.getElementById('stepIndicatorQ1');
  const stepIndicatorQ2 = document.getElementById('stepIndicatorQ2');
  const stepIndicatorSol = document.getElementById('stepIndicatorSol');

  // =========================================================================
  // Editor Helpers & Line Numbering
  // =========================================================================

  function updateLineNumbers() {
    const lines = codeEditor.value.split('\n').length;
    let numbersHtml = '';
    for (let i = 1; i <= lines; i++) {
      numbersHtml += i + '\n';
    }
    lineNumbers.textContent = numbersHtml;
  }

  codeEditor.addEventListener('input', updateLineNumbers);
  codeEditor.addEventListener('scroll', () => {
    lineNumbers.scrollTop = codeEditor.scrollTop;
  });

  // Support Tab key indentation inside textarea
  codeEditor.addEventListener('keydown', (e) => {
    if (e.key === 'Tab') {
      e.preventDefault();
      const start = codeEditor.selectionStart;
      const end = codeEditor.selectionEnd;
      codeEditor.value = codeEditor.value.substring(0, start) + '    ' + codeEditor.value.substring(end);
      codeEditor.selectionStart = codeEditor.selectionEnd = start + 4;
      updateLineNumbers();
    }
  });

  // Language Selector
  languageSelect.addEventListener('change', () => {
    activeLanguage = languageSelect.value;
    if (activeLanguage === 'python') {
      executionBadge.textContent = 'Runnable';
      executionBadge.className = 'execution-badge';
      btnRunCode.disabled = false;
      btnRunCode.title = 'Run code in Python environment';
    } else {
      executionBadge.textContent = 'AI Diagnosis Only';
      executionBadge.className = 'execution-badge ai-only';
      btnRunCode.disabled = false;
      btnRunCode.title = 'Language supported for AI code analysis';
    }
  });

  // =========================================================================
  // Test Examples Setup (Section 29)
  // =========================================================================

  const TEST_A_CODE = `students = {
    "Ali": {"scores": [85, 92, 78, 105], "bonus": 5},
    "Sara": {"scores": [88, 91, -10, 76], "bonus": 10},
    "Hamza": {"scores": [70, 82, 95, 88], "bonus": 0}
}

processed = students.copy()

for name, data in processed.items():
    scores = data["scores"]

    for score in scores:
        if score < 0 or score > 100:
            scores.remove(score)

    data["scores"] = scores

    average = sum(scores) / len(scores)
    adjusted_average = average + data["bonus"]

    if adjusted_average >= 90:
        grade = "A"
    elif adjusted_average >= 75:
        grade = "B"
    else:
        grade = "C"

    print(
        f"{name}: average={average:.2f}, "
        f"adjusted={adjusted_average:.2f}, grade={grade}"
    )

print("\\nOriginal data:")
print(students)`;

  const TEST_B_CODE = `name = "Bilal"
age = 20

print("Name:", name)
print("Age:", ages)`;

  btnLoadExampleA.addEventListener('click', () => {
    resetAllSessionState();
    languageSelect.value = 'python';
    activeLanguage = 'python';
    codeEditor.value = TEST_A_CODE;
    inputExpected.value = "Filter invalid scores (<0 or >100) and calculate correct averages without altering original students data.";
    inputActual.value = "Original students dictionary data gets mutated, and some out-of-bound scores are skipped.";
    updateLineNumbers();
  });

  btnLoadExampleB.addEventListener('click', () => {
    resetAllSessionState();
    languageSelect.value = 'python';
    activeLanguage = 'python';
    codeEditor.value = TEST_B_CODE;
    inputExpected.value = "Print name and age without errors.";
    inputActual.value = "NameError: name 'ages' is not defined";
    updateLineNumbers();
  });

  btnClearCode.addEventListener('click', () => {
    codeEditor.value = '';
    updateLineNumbers();
  });

  btnClearConsole.addEventListener('click', () => {
    consoleOutput.textContent = 'Execution console cleared.';
    consoleOutput.classList.remove('error');
    consoleStatus.textContent = 'Idle';
  });

  // =========================================================================
  // Session State Reset (Section 5 & 15: Session Isolation)
  // =========================================================================

  function resetAllSessionState() {
    // Invalidate active session to guard against any lingering async responses
    const oldSessionId = activeSessionId;
    activeSessionId = null;

    if (oldSessionId) {
      // Fire-and-forget server cleanup
      fetch('/api/session/reset', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: oldSessionId })
      }).catch(() => {});
    }

    // Reset UI Elements
    sessionStatusText.textContent = 'Ready for new problem';
    sessionPill.style.display = 'none';
    sessionShortId.textContent = '--';

    emptyState.style.display = 'flex';
    calmLoader.style.display = 'none';

    cardObservation.style.display = 'none';
    observationContent.textContent = '';

    cardQ1.style.display = 'none';
    question1Content.textContent = '';
    formAnswer1.style.display = 'flex';
    inputAnswer1.value = '';
    userResponse1.style.display = 'none';
    userText1.textContent = '';

    cardQ2.style.display = 'none';
    question2Content.textContent = '';
    formAnswer2.style.display = 'flex';
    inputAnswer2.value = '';
    userResponse2.style.display = 'none';
    userText2.textContent = '';

    solutionContainer.style.display = 'none';
    rootCauseValue.textContent = '--';
    solWhatIFound.textContent = '';
    solWhatsHappening.textContent = '';
    solRootCauseText.textContent = '';
    solCorrectedCode.textContent = '# Corrected code will appear here...';
    solWhyFixWorks.textContent = '';
    solLessonText.textContent = '';

    updateStepper(1);
    consoleStatus.textContent = 'Idle';
  }

  btnNewSession.addEventListener('click', () => {
    resetAllSessionState();
    codeEditor.value = '';
    inputError.value = '';
    inputExpected.value = '';
    inputActual.value = '';
    consoleOutput.textContent = 'Run your code or start a debugging session to observe live execution.';
    consoleOutput.classList.remove('error');
    updateLineNumbers();
  });

  btnSolveAnother.addEventListener('click', () => {
    resetAllSessionState();
    codeEditor.value = '';
    inputError.value = '';
    inputExpected.value = '';
    inputActual.value = '';
    consoleOutput.textContent = 'Ready for your next debugging problem.';
    consoleOutput.classList.remove('error');
    updateLineNumbers();
  });

  // =========================================================================
  // Stepper Visual Progression
  // =========================================================================

  function updateStepper(step) {
    const steps = [
      { el: stepIndicatorObs, stepNum: 1 },
      { el: stepIndicatorQ1, stepNum: 2 },
      { el: stepIndicatorQ2, stepNum: 3 },
      { el: stepIndicatorSol, stepNum: 4 }
    ];

    steps.forEach(({ el, stepNum }) => {
      el.classList.remove('active', 'completed');
      if (stepNum === step) {
        el.classList.add('active');
      } else if (stepNum < step) {
        el.classList.add('completed');
      }
    });
  }

  // =========================================================================
  // Calm Loader Helper
  // =========================================================================

  function showLoader(message) {
    emptyState.style.display = 'none';
    loaderText.textContent = message;
    calmLoader.style.display = 'flex';
  }

  function hideLoader() {
    calmLoader.style.display = 'none';
  }

  // =========================================================================
  // Live Code Execution (Section 11)
  // =========================================================================

  async function executeCode(code, lang) {
    consoleStatus.textContent = 'Running...';
    consoleOutput.textContent = 'Executing in isolated runner...';
    consoleOutput.classList.remove('error');

    try {
      const resp = await fetch('/api/run-code', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code: code, language: lang })
      });

      if (!resp.ok) {
        throw new Error(`Runner error (Status ${resp.status})`);
      }

      const res = await resp.json();
      consoleStatus.textContent = res.exit_code === 0 ? 'Exited (0)' : `Exited (${res.exit_code})`;

      let outputText = '';
      if (res.runner_message) {
        outputText += `[${res.runner_message}]\n\n`;
      }
      if (res.stdout) {
        outputText += res.stdout;
      }
      if (res.stderr) {
        outputText += (res.stdout ? '\n' : '') + res.stderr;
        consoleOutput.classList.add('error');
        // Auto-populate error message field if currently empty
        if (!inputError.value.trim() && res.error_type) {
          inputError.value = `${res.error_type}: ${res.error_details || ''}`;
        }
      }

      consoleOutput.textContent = outputText.trim() || '(No output produced)';
      return res;

    } catch (err) {
      consoleStatus.textContent = 'Failed';
      consoleOutput.classList.add('error');
      consoleOutput.textContent = `Execution failed: ${err.message}`;
      return null;
    }
  }

  btnRunCode.addEventListener('click', async () => {
    const code = codeEditor.value;
    if (!code.trim()) {
      consoleOutput.textContent = 'Please enter some code to run.';
      return;
    }
    await executeCode(code, activeLanguage);
  });

  // =========================================================================
  // Debug Session Flow: Start Session
  // =========================================================================

  btnStartSession.addEventListener('click', async () => {
    const code = codeEditor.value.trim();
    if (!code) {
      alert('Please enter your code before starting a debugging session.');
      codeEditor.focus();
      return;
    }

    // Reset old session before starting fresh
    resetAllSessionState();

    showLoader('Analyzing your code and tracing runtime behavior...');
    sessionStatusText.textContent = 'Analyzing problem...';

    const payload = {
      language: activeLanguage,
      code: code,
      error_message: inputError.value.trim(),
      expected_result: inputExpected.value.trim(),
      actual_result: inputActual.value.trim()
    };

    try {
      const resp = await fetch('/api/session/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (!resp.ok) {
        const errData = await resp.json();
        throw new Error(errData.detail || 'Failed to start session.');
      }

      const data = await resp.json();

      // Set active session identity
      activeSessionId = data.session_id;
      sessionShortId.textContent = activeSessionId.substring(0, 8);
      sessionPill.style.display = 'inline-block';
      sessionStatusText.textContent = 'Diagnostic Session Active';

      // Update Console with execution result
      if (data.execution_result) {
        const exec = data.execution_result;
        consoleStatus.textContent = exec.exit_code === 0 ? 'Exited (0)' : `Exited (${exec.exit_code})`;
        let text = '';
        if (exec.stdout) text += exec.stdout;
        if (exec.stderr) text += (text ? '\n' : '') + exec.stderr;
        consoleOutput.textContent = text.trim() || '(No output produced)';
        if (exec.stderr) consoleOutput.classList.add('error');
      }

      hideLoader();

      // Display Observation
      if (data.observation) {
        observationContent.textContent = data.observation;
        cardObservation.style.display = 'flex';
      }

      // Display Question 1
      if (data.question_1) {
        question1Content.textContent = data.question_1;
        cardQ1.style.display = 'flex';
        inputAnswer1.focus();
        updateStepper(2);
      }

    } catch (err) {
      hideLoader();
      emptyState.style.display = 'flex';
      sessionStatusText.textContent = 'Session failed';
      alert(`Could not start debugging session: ${err.message}`);
    }
  });

  // =========================================================================
  // Question 1 -> Question 2 Transition
  // =========================================================================

  formAnswer1.addEventListener('submit', async (e) => {
    e.preventDefault();
    const answer = inputAnswer1.value.trim();
    if (!answer || !activeSessionId) return;

    const currentSession = activeSessionId;
    showLoader('Evaluating your response and formulating the next diagnostic step...');

    try {
      const resp = await fetch('/api/session/answer', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: currentSession,
          answer: answer
        })
      });

      // RACE CONDITION CHECK: Ignore if session changed
      if (activeSessionId !== currentSession) return;

      if (!resp.ok) {
        const errData = await resp.json();
        throw new Error(errData.detail || 'Failed to submit answer.');
      }

      const data = await resp.json();
      hideLoader();

      // Lock Q1 Form and show user's answer
      formAnswer1.style.display = 'none';
      userText1.textContent = answer;
      userResponse1.style.display = 'block';

      // Show Question 2
      if (data.question_2) {
        question2Content.textContent = data.question_2;
        cardQ2.style.display = 'flex';
        inputAnswer2.focus();
        updateStepper(3);
      }

    } catch (err) {
      hideLoader();
      alert(`Error submitting answer: ${err.message}`);
    }
  });

  // =========================================================================
  // Question 2 -> Final Solution (STOP RULE ENFORCED)
  // =========================================================================

  formAnswer2.addEventListener('submit', async (e) => {
    e.preventDefault();
    const answer = inputAnswer2.value.trim();
    if (!answer || !activeSessionId) return;

    const currentSession = activeSessionId;
    showLoader('Synthesizing root cause, runtime mechanism, and verified code fix...');

    try {
      const resp = await fetch('/api/session/answer', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: currentSession,
          answer: answer
        })
      });

      // RACE CONDITION CHECK: Ignore if session changed
      if (activeSessionId !== currentSession) return;

      if (!resp.ok) {
        const errData = await resp.json();
        throw new Error(errData.detail || 'Failed to submit answer.');
      }

      const data = await resp.json();
      hideLoader();

      // Lock Q2 Form and show user's answer
      formAnswer2.style.display = 'none';
      userText2.textContent = answer;
      userResponse2.style.display = 'block';

      // STOP RULE: Show Final Solution Presentation
      if (data.final_solution) {
        renderFinalSolution(data.final_solution);
        updateStepper(4);
        sessionStatusText.textContent = 'Diagnosis Complete';
      }

    } catch (err) {
      hideLoader();
      alert(`Error finalizing debugging session: ${err.message}`);
    }
  });

  // =========================================================================
  // Render Final Solution (01 to 05 + Lesson)
  // =========================================================================

  function renderFinalSolution(sol) {
    rootCauseValue.textContent = sol.root_cause || 'Root Cause Identified';
    solWhatIFound.textContent = sol.what_i_found || '';
    solWhatsHappening.textContent = sol.whats_happening || '';
    solRootCauseText.textContent = sol.root_cause || '';

    // Render Corrected Code with Prism Highlight
    solCorrectedCode.textContent = sol.corrected_code || '';
    if (window.Prism) {
      Prism.highlightElement(solCorrectedCode);
    }

    solWhyFixWorks.textContent = sol.why_fix_works || '';
    solLessonText.textContent = sol.lesson || '';

    solutionContainer.style.display = 'flex';
    // Scroll solution into view smoothly
    solutionContainer.scrollIntoView({ behavior: 'smooth' });
  }

  // Copy Solution to Clipboard
  btnCopySolution.addEventListener('click', async () => {
    const code = solCorrectedCode.textContent;
    try {
      await navigator.clipboard.writeText(code);
      copyText.textContent = 'Copied!';
      btnCopySolution.style.borderColor = 'var(--status-success)';
      setTimeout(() => {
        copyText.textContent = 'Copy Solution';
        btnCopySolution.style.borderColor = '';
      }, 2000);
    } catch (e) {
      // Fallback
      const ta = document.createElement('textarea');
      ta.value = code;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      document.body.removeChild(ta);
      copyText.textContent = 'Copied!';
      setTimeout(() => { copyText.textContent = 'Copy Solution'; }, 2000);
    }
  });

  // Initialize
  updateLineNumbers();
});

