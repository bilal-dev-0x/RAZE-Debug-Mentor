/**
 * RAZE — Senior Python Debugging Mentor
 * Full-Screen Developer Workspace Controller
 * 
 * 3-Step Socratic Debugging Flow:
 * Step 1: Observation & Diagnostic Question 1
 * Step 2: Evaluation & Diagnostic Question 2
 * Step 3: STOP ASKING QUESTIONS -> Transform workspace into Full-Screen Root Cause Analysis & Verified Solution
 */

(function () {
  'use strict';

  // Sample Bug Presets
  const SAMPLE_BUGS = {
    mutation: {
      code: `numbers = [1, 2, 3, 4, 5]

for number in numbers:
    if number % 2 == 0:
        numbers.remove(number)

print(numbers)`,
      error: '',
      expected: '[1, 3, 5]',
      actual: '[1, 3, 4, 5]'
    },
    division: {
      code: `def calculate_average(scores):
    total = 0
    for score in scores:
        total += score
    # Expected precise float average, but fails on empty lists
    return total / len(scores)

grades = [85, 90, 78, 92]
print("Average:", calculate_average(grades))`,
      error: '',
      expected: 'Average: 86.25',
      actual: 'Average: 86.25'
    }
  };

  // Application State
  const state = {
    sessionId: null,
    step: 1, // 1: Observe & Q1, 2: Q2, 3: Resolution & Solution Mode
    sourceCode: '',
    expectedResult: '',
    actualResult: '',
    suspiciousLines: [],
    question1: '',
    answer1: '',
    question2: '',
    answer2: '',
    correctedCode: '',
    liveExecution: null
  };

  // Header Elements
  const btnBrandHome = document.getElementById('btn-brand-home');
  const activeFilename = document.getElementById('active-filename');
  const headerStageText = document.getElementById('header-stage-text');
  const btnHeaderSampleMut = document.getElementById('btn-header-sample-mut');
  const btnHeaderSampleDiv = document.getElementById('btn-header-sample-div');
  const btnRestart = document.getElementById('btn-restart');

  // Sidebar Pipeline Steps
  const stepNav1 = document.getElementById('step-nav-1');
  const stepNav2 = document.getElementById('step-nav-2');
  const stepNav3 = document.getElementById('step-nav-3');
  const stepNav4 = document.getElementById('step-nav-4');
  const stepNav5 = document.getElementById('step-nav-5');

  const iconStep1 = document.getElementById('icon-step-1');
  const iconStep2 = document.getElementById('icon-step-2');
  const iconStep3 = document.getElementById('icon-step-3');
  const iconStep4 = document.getElementById('icon-step-4');
  const iconStep5 = document.getElementById('icon-step-5');

  // Main Workspace Screens
  const screenIntake = document.getElementById('screen-intake');
  const screenSession = document.getElementById('screen-session');
  const screenSolution = document.getElementById('screen-solution');

  // Intake Elements
  const debugForm = document.getElementById('debug-form');
  const codeInput = document.getElementById('code-input');
  const editorGutter = document.getElementById('editor-gutter');
  const codeStats = document.getElementById('code-stats');
  const errorInput = document.getElementById('error-input');
  const expectedInput = document.getElementById('expected-input');
  const actualInput = document.getElementById('actual-input');
  const btnStart = document.getElementById('btn-start');
  const startSpinner = document.getElementById('start-spinner');
  const btnSample = document.getElementById('btn-sample');
  const btnSampleDiv = document.getElementById('btn-sample-div');
  const intakeError = document.getElementById('intake-error');

  // Session Screen Elements
  const discrepancyBanner = document.getElementById('discrepancy-banner');
  const discrepancyText = document.getElementById('discrepancy-text');
  const sourceCodeViewer = document.getElementById('source-code-viewer');
  const suspiciousIndicator = document.getElementById('suspicious-indicator');
  const sourceLineBadge = document.getElementById('source-line-badge');

  // Live Runner Elements (Session screen)
  const runnerCodeInput = document.getElementById('runner-code-input');
  const btnRunLive = document.getElementById('btn-run-live');
  const runnerSpinner = document.getElementById('runner-spinner');
  const runnerOutputBox = document.getElementById('runner-output-box');
  const runnerTime = document.getElementById('runner-time');

  // Solution Screen Elements
  const btnCopySolution = document.getElementById('btn-copy-solution');
  const btnCopySolutionInner = document.getElementById('btn-copy-solution-inner');
  const btnRunSolution = document.getElementById('btn-run-solution');
  const solutionCodeViewer = document.getElementById('solution-code-viewer');
  const panelDiff = document.getElementById('panel-diff');
  const snippetProblem = document.getElementById('snippet-problem');
  const snippetCorrect = document.getElementById('snippet-correct');

  // Solution Terminal Elements
  const solOutputBox = document.getElementById('sol-output-box');
  const solRunnerTime = document.getElementById('sol-runner-time');
  const solExitBadge = document.getElementById('sol-exit-badge');

  // Analysis Elements
  const analysisWhatIFound = document.getElementById('analysis-what-i-found');
  const analysisWhatsHappening = document.getElementById('analysis-whats-happening');
  const analysisHiddenProblem = document.getElementById('analysis-hidden-problem');
  const analysisWhyOutputChanged = document.getElementById('analysis-why-output-changed');
  const analysisDiscrepancySec = document.getElementById('analysis-discrepancy-sec');
  const analysisDiscrepancy = document.getElementById('analysis-discrepancy');
  const analysisWhyFixWorks = document.getElementById('analysis-why-fix-works');
  const analysisLesson = document.getElementById('analysis-lesson');

  // Mentor Panel Elements
  const activeFlowPill = document.getElementById('active-flow-pill');
  const chatFeed = document.getElementById('chat-feed');
  const hintsBanner = document.getElementById('hints-banner');
  const hintsBannerText = document.getElementById('hints-banner-text');
  const btnSkipToSolution = document.getElementById('btn-skip-to-solution');
  const chatInputContainer = document.getElementById('chat-input-container');
  const mentorResponseForm = document.getElementById('mentor-response-form');
  const inputInstructionLabel = document.getElementById('input-instruction-label');
  const mentorUserInput = document.getElementById('mentor-user-input');
  const btnSendAnswer = document.getElementById('btn-send-answer');
  const answerSpinner = document.getElementById('answer-spinner');
  const btnMentorStuck = document.getElementById('btn-mentor-stuck');
  const mentorFormError = document.getElementById('mentor-form-error');
  const mentorCompletedFooter = document.getElementById('mentor-completed-footer');
  const btnAnalysisNewSession = document.getElementById('btn-analysis-new-session');

  // Initialize
  function init() {
    bindEvents();
    updateEditorGutter();
    renderPipelineStatus(0); // 0 = Intake state
  }

  // Bind UI Events
  function bindEvents() {
    // Code input gutter & line counting
    if (codeInput) {
      codeInput.addEventListener('input', updateEditorGutter);
      codeInput.addEventListener('scroll', syncGutterScroll);
      codeInput.addEventListener('keydown', handleEditorTab);
    }

    // Presets
    if (btnSample) {
      btnSample.addEventListener('click', () => loadPreset(SAMPLE_BUGS.mutation));
    }
    if (btnSampleDiv) {
      btnSampleDiv.addEventListener('click', () => loadPreset(SAMPLE_BUGS.division));
    }
    if (btnHeaderSampleMut) {
      btnHeaderSampleMut.addEventListener('click', () => {
        resetToHome();
        loadPreset(SAMPLE_BUGS.mutation);
      });
    }
    if (btnHeaderSampleDiv) {
      btnHeaderSampleDiv.addEventListener('click', () => {
        resetToHome();
        loadPreset(SAMPLE_BUGS.division);
      });
    }

    // Intake Form Submit
    if (debugForm) {
      debugForm.addEventListener('submit', handleStartDebug);
    }

    // Global Key combo: Cmd+Enter or Ctrl+Enter starts debugging
    window.addEventListener('keydown', (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
        if (!screenIntake.classList.contains('hidden')) {
          e.preventDefault();
          if (debugForm) debugForm.requestSubmit();
        } else if (chatInputContainer && !chatInputContainer.classList.contains('hidden')) {
          e.preventDefault();
          if (mentorResponseForm) mentorResponseForm.requestSubmit();
        }
      }
    });

    // Reset to Home / New Session
    if (btnRestart) btnRestart.addEventListener('click', resetToHome);
    if (btnBrandHome) btnBrandHome.addEventListener('click', resetToHome);
    if (btnAnalysisNewSession) btnAnalysisNewSession.addEventListener('click', resetToHome);

    // Mentor Answer Submission
    if (mentorResponseForm) {
      mentorResponseForm.addEventListener('submit', handleMentorSubmit);
    }

    // Stuck Handler
    if (btnMentorStuck) {
      btnMentorStuck.addEventListener('click', handleStuckClick);
    }
    if (btnSkipToSolution) {
      btnSkipToSolution.addEventListener('click', handleSkipToSolution);
    }

    // Live Runner Execution
    if (btnRunLive) {
      btnRunLive.addEventListener('click', handleLiveRun);
    }
    if (btnRunSolution) {
      btnRunSolution.addEventListener('click', handleRunSolutionClick);
    }

    // Copy Solution Buttons
    if (btnCopySolution) {
      btnCopySolution.addEventListener('click', handleCopySolution);
    }
    if (btnCopySolutionInner) {
      btnCopySolutionInner.addEventListener('click', handleCopySolution);
    }
  }

  // Load Preset Code
  function loadPreset(preset) {
    if (!codeInput) return;
    codeInput.value = preset.code;
    if (errorInput) errorInput.value = preset.error;
    if (expectedInput) expectedInput.value = preset.expected;
    if (actualInput) actualInput.value = preset.actual;
    updateEditorGutter();
    hideError(intakeError);
  }

  // Gutter & Line Counts
  function updateEditorGutter() {
    if (!codeInput || !editorGutter) return;
    const lines = codeInput.value.split('\n').length;
    let numbersHtml = '';
    for (let i = 1; i <= Math.max(lines, 1); i++) {
      numbersHtml += `<div>${i}</div>`;
    }
    editorGutter.innerHTML = numbersHtml;
    if (codeStats) {
      codeStats.textContent = `${lines} ${lines === 1 ? 'line' : 'lines'}`;
    }
  }

  function syncGutterScroll() {
    if (!codeInput || !editorGutter) return;
    editorGutter.scrollTop = codeInput.scrollTop;
  }

  function handleEditorTab(e) {
    if (e.key === 'Tab') {
      e.preventDefault();
      const start = this.selectionStart;
      const end = this.selectionEnd;
      this.value = this.value.substring(0, start) + '    ' + this.value.substring(end);
      this.selectionStart = this.selectionEnd = start + 4;
      updateEditorGutter();
    }
  }

  // Step 1: Start Debugging Session
  async function handleStartDebug(e) {
    e.preventDefault();
    hideError(intakeError);

    const code = (codeInput?.value || '').trim();
    const expected = (expectedInput?.value || '').trim();
    const errorMsg = (errorInput?.value || '').trim();
    const actual = (actualInput?.value || '').trim();

    if (!code) {
      showError(intakeError, 'Please provide your Python code.');
      return;
    }
    if (!expected) {
      showError(intakeError, 'Please describe what you expected the code to produce.');
      return;
    }

    setLoading(btnStart, startSpinner, true, 'Analyzing in Python 3...');

    try {
      const resp = await fetch('/api/debug/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          code,
          expected_result: expected,
          error_message: errorMsg || null,
          actual_result: actual || null
        })
      });

      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        throw new Error(data.detail || 'Failed to start debugging session.');
      }

      const data = await resp.json();

      // Populate state
      state.sessionId = data.session_id;
      state.step = 1;
      state.sourceCode = code;
      state.expectedResult = expected;
      state.actualResult = actual;
      state.suspiciousLines = data.suspicious_lines || [];
      state.question1 = data.question || '';

      // Transition views: Switch from intake screen to active session workspace!
      screenIntake.classList.add('hidden');
      screenSession.classList.remove('hidden');
      screenSolution.classList.add('hidden');

      // Update Header
      if (activeFilename) activeFilename.textContent = 'code.py';
      if (headerStageText) headerStageText.textContent = '01 Observation & Question 1';
      if (activeFlowPill) activeFlowPill.textContent = 'Step 1 of 3';

      // Update Left Sidebar Pipeline
      renderPipelineStatus(1);

      // Render submitted code with highlighted suspicious lines
      renderSourceCode(code, state.suspiciousLines);

      // Discrepancy Alert Check
      if (data.discrepancy_note) {
        discrepancyText.textContent = data.discrepancy_note;
        discrepancyBanner.classList.remove('hidden');
      } else {
        discrepancyBanner.classList.add('hidden');
      }

      // Populate Live Runner with submitted code and real execution result
      if (runnerCodeInput) {
        runnerCodeInput.value = code;
      }
      if (data.real_execution) {
        renderRunnerOutput(data.real_execution);
      }

      // Clear & render initial chat feed with Observation and Diagnostic Question 1
      chatFeed.innerHTML = '';
      appendMentorMessage({
        text: data.observation || data.message || 'Observation',
        question: data.question,
        questionLabel: 'Diagnostic Question 1'
      });

      // Update chat input label
      if (inputInstructionLabel) {
        inputInstructionLabel.textContent = 'YOUR ANSWER TO QUESTION 1';
      }
      if (mentorUserInput) {
        mentorUserInput.value = '';
        mentorUserInput.focus();
      }

    } catch (err) {
      showError(intakeError, err.message);
    } finally {
      setLoading(btnStart, startSpinner, false, 'Start Debugging Session');
    }
  }

  // Handle Mentor Form Submit (Question 1 or Question 2 response)
  async function handleMentorSubmit(e) {
    e.preventDefault();
    hideError(mentorFormError);

    const userText = (mentorUserInput?.value || '').trim();
    if (!userText) {
      showError(mentorFormError, 'Please provide an explanation or observation to continue.');
      return;
    }

    setLoading(btnSendAnswer, answerSpinner, true, 'Evaluating...');

    // Append user response to chat immediately
    appendUserMessage(userText);
    mentorUserInput.value = '';

    try {
      const currentStage = state.step === 1 ? 'observation' : 'diagnose_2';

      const resp = await fetch('/api/debug/respond', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: state.sessionId,
          user_message: userText,
          stage: currentStage
        })
      });

      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        throw new Error(data.detail || 'Failed to submit response.');
      }

      const data = await resp.json();

      // Check if this was response to Q1 -> moves to Step 2 (Question 2)
      if (state.step === 1 && !data.is_complete) {
        state.step = 2;
        state.answer1 = userText;
        state.question2 = data.question || '';

        // Update Header & Pipeline
        if (headerStageText) headerStageText.textContent = '02 Diagnostic Isolation & Question 2';
        if (activeFlowPill) activeFlowPill.textContent = 'Step 2 of 3';
        renderPipelineStatus(2);

        // Append RAZE evaluation & Question 2
        appendMentorMessage({
          text: data.evaluation || data.message,
          question: data.question,
          questionLabel: 'Diagnostic Question 2 (Final Question)'
        });

        if (inputInstructionLabel) {
          inputInstructionLabel.textContent = 'YOUR ANSWER TO QUESTION 2 (FINAL QUESTION)';
        }
        if (mentorUserInput) {
          mentorUserInput.focus();
        }

        // Hide any stuck hint banner
        hintsBanner.classList.add('hidden');

      } else {
        // Step 3: STOP ASKING QUESTIONS -> Transform Workspace into Solution Mode!
        state.step = 3;
        state.answer2 = userText;
        state.correctedCode = data.corrected_code || '';

        // Update Header
        if (activeFilename) activeFilename.textContent = 'solution.py';
        if (headerStageText) headerStageText.textContent = '03 Root Cause & Verified Solution';
        if (activeFlowPill) activeFlowPill.textContent = 'Complete';

        // Update Pipeline (all steps marked complete)
        renderPipelineStatus(3);

        // Append wrap-up mentor message
        appendMentorMessage({
          text: (data.evaluation ? `${data.evaluation}\n\n` : '') +
                'Diagnostic complete. I have unpacked the runtime mechanism, root cause, and verified code fix across your workspace.',
          isComplete: true
        });

        // Hide question input form completely and show completion footer
        chatInputContainer.classList.add('hidden');
        hintsBanner.classList.add('hidden');
        mentorCompletedFooter.classList.remove('hidden');

        // Transform Main Workspace to Solution Mode!
        screenSession.classList.add('hidden');
        screenSolution.classList.remove('hidden');

        // Render the Code Solution
        renderSolutionCode(data.corrected_code);

        // Render Before / After Diff
        if (snippetProblem && snippetCorrect && (data.before_snippet || data.after_snippet)) {
          snippetProblem.textContent = data.before_snippet || '# Problem pattern';
          snippetCorrect.textContent = data.after_snippet || '# Correct approach';
          panelDiff.classList.remove('hidden');
          if (window.hljs) {
            window.hljs.highlightElement(snippetProblem);
            window.hljs.highlightElement(snippetCorrect);
          }
        }

        // Render Verified Subprocess Output
        if (data.live_execution) {
          renderSolutionOutput(data.live_execution);
        } else if (data.real_execution) {
          renderSolutionOutput(data.real_execution);
        }

        // Populate and reveal RAZE Analysis Panel
        renderAnalysisPanel(data);
      }

    } catch (err) {
      showError(mentorFormError, err.message);
    } finally {
      setLoading(btnSendAnswer, answerSpinner, false, 'Submit Response');
    }
  }

  // Render Left Sidebar Pipeline Navigation Status
  function renderPipelineStatus(currentStep) {
    const steps = [
      { el: stepNav1, icon: iconStep1 },
      { el: stepNav2, icon: iconStep2 },
      { el: stepNav3, icon: iconStep3 },
      { el: stepNav4, icon: iconStep4 },
      { el: stepNav5, icon: iconStep5 }
    ];

    if (currentStep === 0) {
      // Intake mode
      steps.forEach((s, idx) => {
        s.el.classList.remove('active', 'completed');
        s.icon.textContent = idx === 0 ? '●' : '○';
      });
      stepNav1.classList.add('active');
    } else if (currentStep === 1) {
      // Step 1 active
      stepNav1.classList.add('active');
      stepNav1.classList.remove('completed');
      iconStep1.textContent = '●';

      [stepNav2, stepNav3, stepNav4, stepNav5].forEach((s, i) => {
        s.classList.remove('active', 'completed');
        steps[i + 1].icon.textContent = '○';
      });
    } else if (currentStep === 2) {
      // Step 1 completed, Step 2 active
      stepNav1.classList.remove('active');
      stepNav1.classList.add('completed');
      iconStep1.textContent = '✓';

      stepNav2.classList.add('active');
      stepNav2.classList.remove('completed');
      iconStep2.textContent = '●';

      [stepNav3, stepNav4, stepNav5].forEach((s, i) => {
        s.classList.remove('active', 'completed');
        steps[i + 2].icon.textContent = '○';
      });
    } else if (currentStep >= 3) {
      // Resolution mode: Steps 1 & 2 completed, 3, 4, 5 all active/completed!
      stepNav1.classList.remove('active');
      stepNav1.classList.add('completed');
      iconStep1.textContent = '✓';

      stepNav2.classList.remove('active');
      stepNav2.classList.add('completed');
      iconStep2.textContent = '✓';

      stepNav3.classList.add('completed');
      iconStep3.textContent = '✓';

      stepNav4.classList.add('completed');
      iconStep4.textContent = '✓';

      stepNav5.classList.add('completed');
      iconStep5.textContent = '✓';
    }
  }

  // Render Source Code Viewer with Suspicious Lines
  function renderSourceCode(code, suspiciousLines) {
    if (!sourceCodeViewer) return;

    const lines = (code || '').split('\n');
    const suspSet = new Set(suspiciousLines || []);

    if (suspiciousIndicator) {
      if (suspSet.size > 0) {
        suspiciousIndicator.textContent = `Lines ${Array.from(suspSet).join(', ')} flagged for inspection`;
        suspiciousIndicator.classList.remove('hidden');
      } else {
        suspiciousIndicator.classList.add('hidden');
      }
    }

    let html = '<table class="code-table font-mono"><tbody>';
    lines.forEach((lineText, idx) => {
      const lineNum = idx + 1;
      const isSuspicious = suspSet.has(lineNum);
      const trClass = isSuspicious ? 'code-line-tr suspicious-line' : 'code-line-tr';

      let highlighted = escapeHtml(lineText);
      if (window.hljs) {
        try {
          highlighted = window.hljs.highlight(lineText || ' ', { language: 'python', ignoreIllegals: true }).value;
        } catch (e) {
          highlighted = escapeHtml(lineText);
        }
      }

      html += `
        <tr class="${trClass}" data-line="${lineNum}">
          <td class="code-line-num font-mono">${lineNum}</td>
          <td class="code-line-text font-mono">${highlighted || ' '}</td>
        </tr>
      `;
    });
    html += '</tbody></table>';

    sourceCodeViewer.innerHTML = html;
  }

  // Render Solution Code Viewer
  function renderSolutionCode(code) {
    if (!solutionCodeViewer) return;

    const lines = (code || '').split('\n');
    let html = '<table class="code-table font-mono"><tbody>';
    lines.forEach((lineText, idx) => {
      const lineNum = idx + 1;
      let highlighted = escapeHtml(lineText);
      if (window.hljs) {
        try {
          highlighted = window.hljs.highlight(lineText || ' ', { language: 'python', ignoreIllegals: true }).value;
        } catch (e) {
          highlighted = escapeHtml(lineText);
        }
      }

      html += `
        <tr class="code-line-tr" data-line="${lineNum}">
          <td class="code-line-num font-mono">${lineNum}</td>
          <td class="code-line-text font-mono">${highlighted || ' '}</td>
        </tr>
      `;
    });
    html += '</tbody></table>';

    solutionCodeViewer.innerHTML = html;
  }

  // Render Deep Analysis Panel
  function renderAnalysisPanel(data) {
    if (analysisWhatIFound) {
      analysisWhatIFound.textContent = data.what_i_found || 'Diagnostic assessment completed.';
    }
    if (analysisWhatsHappening) {
      analysisWhatsHappening.textContent = data.whats_happening || 'Detailed mechanical execution trace.';
    }
    if (analysisHiddenProblem) {
      analysisHiddenProblem.textContent = data.hidden_problem || 'Core Python runtime conflict.';
    }
    if (analysisWhyOutputChanged) {
      analysisWhyOutputChanged.textContent = data.why_output_changed || 'Why actual and expected output diverged.';
    }
    if (analysisWhyFixWorks) {
      analysisWhyFixWorks.textContent = data.why_fix_works || 'Why the corrected structure preserves invariants.';
    }
    if (analysisLesson) {
      analysisLesson.textContent = data.lesson || 'Defensive programming principle.';
    }

    // Discrepancy section
    if (data.discrepancy_noticed) {
      if (analysisDiscrepancy) {
        analysisDiscrepancy.textContent = data.discrepancy_noticed;
      }
      analysisDiscrepancySec.classList.remove('hidden');
    } else {
      analysisDiscrepancySec.classList.add('hidden');
    }
  }

  // Append Mentor Message into Feed
  function appendMentorMessage({ text, question, questionLabel, isComplete }) {
    const itemDiv = document.createElement('div');
    itemDiv.className = 'chat-item';

    let questionHtml = '';
    if (question) {
      questionHtml = `
        <div class="diag-question-block">
          <div class="diag-label font-mono">${escapeHtml(questionLabel || 'Diagnostic Question')}</div>
          <div class="diag-text">${escapeHtml(question)}</div>
        </div>
      `;
    }

    itemDiv.innerHTML = `
      <div class="chat-item-header">
        <span class="chat-role-tag chat-role-raze font-mono">RAZE SENIOR MENTOR</span>
        <span class="chat-time font-mono">${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
      </div>
      <div class="chat-box chat-box-mentor">
        <p>${escapeHtml(text).replace(/\n/g, '<br>')}</p>
        ${questionHtml}
      </div>
    `;

    chatFeed.appendChild(itemDiv);
    chatFeed.scrollTop = chatFeed.scrollHeight;
  }

  // Append User Message into Feed
  function appendUserMessage(text) {
    const itemDiv = document.createElement('div');
    itemDiv.className = 'chat-item';
    itemDiv.innerHTML = `
      <div class="chat-item-header">
        <span class="chat-role-tag chat-role-user font-mono">YOU</span>
        <span class="chat-time font-mono">${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
      </div>
      <div class="chat-box chat-box-user font-mono">
        <p>${escapeHtml(text).replace(/\n/g, '<br>')}</p>
      </div>
    `;
    chatFeed.appendChild(itemDiv);
    chatFeed.scrollTop = chatFeed.scrollHeight;
  }

  // Stuck Handler
  async function handleStuckClick() {
    if (!state.sessionId) return;
    try {
      const resp = await fetch('/api/debug/stuck', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: state.sessionId,
          stage: state.step === 1 ? 'observation' : 'diagnose_2'
        })
      });

      if (!resp.ok) return;
      const data = await resp.json();

      if (hintsBanner && hintsBannerText) {
        hintsBannerText.textContent = data.hint || data.message || 'Examine what happens to the list indices.';
        hintsBanner.classList.remove('hidden');
      }
    } catch (err) {
      console.warn('Stuck request error:', err);
    }
  }

  // Skip to Solution Handler
  async function handleSkipToSolution() {
    mentorUserInput.value = "I'm stuck and would like to see the full explanation and solution.";
    handleMentorSubmit(new Event('submit'));
  }

  // Live Code Execution in Subprocess
  async function handleLiveRun() {
    const code = (runnerCodeInput?.value || '').trim();
    if (!code) {
      renderRunnerOutput({ output: '', error: 'No code to execute.', exit_code: 1, execution_time_ms: 0 });
      return;
    }

    setLoading(btnRunLive, runnerSpinner, true, 'Running...');

    try {
      const resp = await fetch('/api/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code, language: 'python' })
      });

      const result = await resp.json();
      renderRunnerOutput(result);
    } catch (err) {
      renderRunnerOutput({
        output: '',
        error: `Execution error: ${err.message}`,
        exit_code: 1,
        execution_time_ms: 0
      });
    } finally {
      setLoading(btnRunLive, runnerSpinner, false, 'Run in Python 3');
    }
  }

  // Run solution button
  async function handleRunSolutionClick() {
    if (!state.correctedCode) return;
    if (solOutputBox) solOutputBox.textContent = '> Running verified solution in Python 3...';
    try {
      const resp = await fetch('/api/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code: state.correctedCode, language: 'python' })
      });
      const result = await resp.json();
      renderSolutionOutput(result);
    } catch (err) {
      if (solOutputBox) solOutputBox.textContent = `> Error: ${err.message}`;
    }
  }

  // Render Runner Output Box (Session view)
  function renderRunnerOutput(result) {
    if (!runnerOutputBox) return;

    const hasError = result.exit_code !== 0 || !!result.error;
    if (hasError) {
      const errText = result.error || 'Execution resulted in a non-zero exit code.';
      runnerOutputBox.textContent = `> Error:\n${errText}`;
      runnerOutputBox.style.color = '#E28A93';
    } else {
      const outText = result.output || '(Execution completed successfully with no stdout)';
      runnerOutputBox.textContent = `> ${outText}`;
      runnerOutputBox.style.color = '#ABD2FA';
    }

    if (runnerTime) {
      runnerTime.textContent = `${result.execution_time_ms || 0}ms`;
      runnerTime.classList.remove('hidden');
    }
  }

  // Render Solution Terminal Output (Solution view)
  function renderSolutionOutput(result) {
    if (!solOutputBox) return;

    const hasError = result.exit_code !== 0 || !!result.error;
    if (hasError) {
      const errText = result.error || 'Execution resulted in a non-zero exit code.';
      solOutputBox.textContent = `> Error:\n${errText}`;
      solOutputBox.style.color = '#E28A93';
    } else {
      const outText = result.output || '(Execution completed successfully with no stdout)';
      solOutputBox.textContent = `> ${outText}`;
      solOutputBox.style.color = '#7FE0BE';
    }

    if (solRunnerTime) {
      solRunnerTime.textContent = `${result.execution_time_ms || 0}ms`;
    }
    if (solExitBadge) {
      solExitBadge.textContent = `exit ${result.exit_code || 0}`;
      solExitBadge.className = result.exit_code === 0 ? 'tab-badge badge-green font-mono' : 'tab-badge font-mono';
    }
  }

  // Copy Solution to Clipboard
  function handleCopySolution() {
    if (!state.correctedCode) return;
    navigator.clipboard.writeText(state.correctedCode).then(() => {
      const targetBtn = btnCopySolution || btnCopySolutionInner;
      const originalText = targetBtn ? targetBtn.textContent : 'Copy Solution';
      if (targetBtn) targetBtn.textContent = 'Copied to Clipboard!';
      setTimeout(() => {
        if (targetBtn) targetBtn.textContent = originalText;
      }, 2000);
    }).catch(() => {
      alert('Could not copy to clipboard.');
    });
  }

  // Reset to Home
  function resetToHome() {
    state.sessionId = null;
    state.step = 1;
    state.sourceCode = '';
    state.correctedCode = '';
    state.suspiciousLines = [];

    screenIntake.classList.remove('hidden');
    screenSession.classList.add('hidden');
    screenSolution.classList.add('hidden');

    if (activeFilename) activeFilename.textContent = 'debug.py';
    if (headerStageText) headerStageText.textContent = 'Intake Workspace';
    if (activeFlowPill) activeFlowPill.textContent = 'Step 1 of 3';

    renderPipelineStatus(0);

    chatInputContainer.classList.remove('hidden');
    hintsBanner.classList.add('hidden');
    mentorCompletedFooter.classList.add('hidden');
    discrepancyBanner.classList.add('hidden');

    chatFeed.innerHTML = '';
  }

  // Helpers
  function setLoading(button, spinner, isLoading, text) {
    if (!button) return;
    button.disabled = isLoading;
    if (spinner) {
      spinner.classList.toggle('hidden', !isLoading);
    }
    const label = button.querySelector('.btn-label');
    if (label && text) {
      label.textContent = text;
    }
  }

  function showError(element, message) {
    if (!element) return;
    element.textContent = message;
    element.classList.remove('hidden');
  }

  function hideError(element) {
    if (!element) return;
    element.textContent = '';
    element.classList.add('hidden');
  }

  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  // Start app on DOMContentLoaded
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
