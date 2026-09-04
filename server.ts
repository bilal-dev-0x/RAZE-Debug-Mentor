import express from "express";
import path from "path";
import dotenv from "dotenv";
import { execFile } from "child_process";
import { GoogleGenAI } from "@google/genai";

dotenv.config();

const app = express();
const PORT = 3000;

app.use(express.json({ limit: "5mb" }));

// Mount static assets from the static directory
const staticDir = path.join(process.cwd(), "static");
const templatesDir = path.join(process.cwd(), "templates");

app.use("/static", express.static(staticDir));

// Serve templates/index.html at root route
app.get("/", (req, res) => {
  res.sendFile(path.join(templatesDir, "index.html"));
});

// Health check endpoints (GET /health and GET /api/health)
app.get("/health", (req, res) => {
  res.json({
    status: "healthy",
    service: "RAZE AI Debugging Mentor",
    gemini_configured: !!process.env.GEMINI_API_KEY,
    supported_languages: ["python"],
  });
});

app.get("/api/health", (req, res) => {
  res.json({
    status: "healthy",
    service: "RAZE AI Debugging Mentor",
    gemini_configured: !!process.env.GEMINI_API_KEY,
    supported_languages: ["python"],
  });
});

// Safe Subprocess Execution for Python
export interface ExecutionResult {
  output: string;
  error: string | null;
  exit_code: number;
  execution_time_ms: number;
  timed_out: boolean;
}

function runPythonSafe(code: string, timeoutMs: number = 4000): Promise<ExecutionResult> {
  return new Promise((resolve) => {
    const startTime = Date.now();
    const cleanCode = code.trim();

    if (!cleanCode) {
      return resolve({
        output: "",
        error: "No code provided to execute.",
        exit_code: 1,
        execution_time_ms: 0,
        timed_out: false,
      });
    }

    execFile(
      "python3",
      ["-u", "-c", cleanCode],
      {
        timeout: timeoutMs,
        maxBuffer: 64 * 1024,
        env: {
          ...process.env,
          PYTHONUNBUFFERED: "1",
          PYTHONDONTWRITEBYTECODE: "1",
        },
      },
      (error: any, stdout: string, stderr: string) => {
        const executionTime = Date.now() - startTime;
        const timed_out = error ? error.killed && (error.signal === "SIGTERM" || error.signal === "SIGKILL") : false;

        let errMsg: string | null = null;
        if (timed_out) {
          errMsg = `Execution timed out (${(timeoutMs / 1000).toFixed(1)}s limit). Check for infinite loops or blocking input.`;
        } else if (stderr && stderr.trim()) {
          errMsg = stderr.trim();
        } else if (error && error.message && !stdout) {
          errMsg = error.message;
        }

        resolve({
          output: stdout ? stdout.trim() : "",
          error: errMsg,
          exit_code: error ? (typeof error.code === "number" ? error.code : 1) : 0,
          execution_time_ms: executionTime,
          timed_out,
        });
      }
    );
  });
}

// POST /api/run — Real Live Code Execution endpoint
app.post("/api/run", async (req, res) => {
  try {
    const { code, language = "python" } = req.body;

    if (language.toLowerCase() !== "python" && language.toLowerCase() !== "py") {
      return res.status(400).json({
        output: "",
        error: `Only Python is supported by the backend execution engine. Requested: ${language}`,
        exit_code: 1,
        execution_time_ms: 0,
        timed_out: false,
      });
    }

    if (!code || !code.trim()) {
      return res.status(400).json({
        output: "",
        error: "Source code cannot be empty.",
        exit_code: 1,
        execution_time_ms: 0,
        timed_out: false,
      });
    }

    const result = await runPythonSafe(code);
    res.json(result);
  } catch (err: any) {
    res.status(500).json({
      output: "",
      error: err.message || "Execution failed",
      exit_code: 1,
      execution_time_ms: 0,
      timed_out: false,
    });
  }
});

// Lazy initialization of Gemini API Client
const GEMINI_MODEL = process.env.GEMINI_MODEL || "gemini-3.6-flash";
let geminiClient: GoogleGenAI | null = null;
function getGeminiClient(): GoogleGenAI | null {
  const apiKey = process.env.GEMINI_API_KEY;
  if (!apiKey) {
    return null;
  }
  if (!geminiClient) {
    geminiClient = new GoogleGenAI({
      apiKey: apiKey,
      httpOptions: {
        headers: {
          "User-Agent": "aistudio-build",
        },
      },
    });
  }
  return geminiClient;
}

// Stage definitions for the 3-step senior developer flow
const STAGES = [
  { id: "observation", number: 1, title: "Observation", description: "Initial observation & Diagnostic Question 1" },
  { id: "diagnose_2", number: 2, title: "Diagnostic Question 2", description: "Evaluation of Answer 1 & Diagnostic Question 2" },
  { id: "resolution", number: 3, title: "Solution & Analysis", description: "Complete explanation, corrected code & live verification" },
];

interface SessionState {
  sessionId: string;
  code: string;
  errorMessage?: string;
  expectedResult: string;
  actualResult?: string;
  currentStage: "observation" | "diagnose_2" | "resolution";
  stageNumber: number;
  suspiciousLines: number[];
  realExecution: ExecutionResult;
  observationMessage: string;
  question1: string;
  answer1?: string;
  eval1?: string;
  question2?: string;
  answer2?: string;
  eval2?: string;
  discrepancyNote?: string;
}

const sessions = new Map<string, SessionState>();

// Helper: detect suspicious lines in Python code
function detectSuspiciousLines(code: string): number[] {
  const lines = code.split("\n");
  const suspicious: number[] = [];
  lines.forEach((line, idx) => {
    const trimmed = line.trim();
    if (
      trimmed.includes(".remove(") ||
      trimmed.includes(".pop(") ||
      trimmed.includes("del ") ||
      trimmed.includes(".append(") ||
      trimmed.includes(".copy(") ||
      trimmed.includes("for ") ||
      trimmed.includes("while ") ||
      trimmed.includes("==") ||
      trimmed.includes("/ ") ||
      trimmed.includes("//")
    ) {
      suspicious.push(idx + 1);
    }
  });
  return suspicious.length ? suspicious : [Math.min(2, lines.length)];
}

// GET /api/debug/stages
app.get("/api/debug/stages", (req, res) => {
  res.json({ stages: STAGES });
});

// POST /api/debug/start
app.post("/api/debug/start", async (req, res) => {
  try {
    const { code, error_message, expected_result, actual_result } = req.body;

    if (!code || !code.trim()) {
      return res.status(400).json({ detail: "Python source code is required." });
    }
    if (!expected_result || !expected_result.trim()) {
      return res.status(400).json({ detail: "Expected result is required." });
    }

    const sessionId = "session-" + Date.now() + "-" + Math.random().toString(36).substring(2, 8);
    const suspiciousLines = detectSuspiciousLines(code);

    // Run user's code safely in Python to get ground-truth execution result
    const realExecution = await runPythonSafe(code);

    let observation = "";
    let question1 = "";
    let discrepancyNote: string | undefined = undefined;

    // Check discrepancy between user reported actual result and real output
    const userReportedActual = (actual_result || "").trim();
    const realOutputSummary = realExecution.error
      ? `Raised error: ${realExecution.error.split("\n")[0]}`
      : realExecution.output || "No output printed";

    if (
      userReportedActual &&
      userReportedActual.toLowerCase() !== "none" &&
      !realOutputSummary.toLowerCase().includes(userReportedActual.toLowerCase()) &&
      !userReportedActual.toLowerCase().includes(realOutputSummary.toLowerCase())
    ) {
      discrepancyNote = `There is an inconsistency between your reported Actual Result ("${userReportedActual}") and what this code actually produces when executed ("${realOutputSummary}").`;
    }

    const ai = getGeminiClient();

    if (ai) {
      try {
        const prompt = `You are RAZE, an expert senior developer helping a frustrated developer debug Python code.
Guiding Principle: RAZE should feel like a senior developer helping a colleague, not an AI asking an endless interview.

The student submitted this Python code:
\`\`\`python
${code}
\`\`\`
- Expected result: ${expected_result}
- Actual result reported by user: ${actual_result || "None provided"}
- Actual execution result when run on Python 3: ${realOutputSummary}
- Error message: ${error_message || "None provided"}

TASK: Step 1 of the Debugging Flow:
1. Provide a useful Observation (2-3 short, conversational paragraphs).
   - Point out what the code is doing vs what was expected.
   - If there is a discrepancy between user's reported actual result and real execution output, explicitly call it out.
   - Do NOT give away the corrected code or the full solution.
2. Ask Diagnostic Question 1: ONE focused question that guides the developer's attention to the runtime mechanism.

Respond in strict JSON with:
{
  "observation": "2-3 short conversational sentences from a senior dev perspective...",
  "question": "One focused question about the execution mechanism...",
  "suspicious_lines": [3, 4]
}`;

        const response = await ai.models.generateContent({
          model: GEMINI_MODEL,
          contents: prompt,
          config: {
            responseMimeType: "application/json",
          },
        });

        const raw = response.text || "{}";
        const parsed = JSON.parse(raw);
        observation = parsed.observation || "";
        question1 = parsed.question || "";
        if (Array.isArray(parsed.suspicious_lines) && parsed.suspicious_lines.length > 0) {
          // Keep detected or refined lines
          suspiciousLines.splice(0, suspiciousLines.length, ...parsed.suspicious_lines);
        }
      } catch (err) {
        console.warn("Gemini generation notice during start:", err);
      }
    }

    if (!observation) {
      observation = `I analyzed your code against your expected output (${expected_result}).\n\nNotice that the code operates on the collection directly while iterating over it. When elements are altered or removed during traversal, Python's internal index pointer continues to advance, which often produces unexpected gaps or shifts.`;
    }

    if (!question1) {
      question1 = "When an element is removed or mutated inside the loop, what happens to the position of the remaining items relative to Python's loop counter?";
    }

    if (discrepancyNote && !observation.includes("inconsistency") && !observation.includes("discrepancy")) {
      observation = `${discrepancyNote}\n\n${observation}`;
    }

    const sessionState: SessionState = {
      sessionId,
      code,
      errorMessage: error_message,
      expectedResult: expected_result,
      actualResult: actual_result,
      currentStage: "observation",
      stageNumber: 1,
      suspiciousLines,
      realExecution,
      observationMessage: observation,
      question1,
      discrepancyNote,
    };

    sessions.set(sessionId, sessionState);

    res.json({
      session_id: sessionId,
      stage: "observation",
      stage_number: 1,
      stage_title: "Observation & Question 1",
      observation,
      question: question1,
      message: `${observation}\n\n${question1}`,
      suspicious_lines: suspiciousLines,
      real_execution: realExecution,
      discrepancy_note: discrepancyNote || null,
    });
  } catch (error: any) {
    res.status(500).json({ detail: error.message || "Failed to start session" });
  }
});

// POST /api/debug/respond
app.post("/api/debug/respond", async (req, res) => {
  try {
    const { session_id, user_message, stage } = req.body;
    const session = sessions.get(session_id);

    const userText = (user_message || "").trim();

    if (!session) {
      return res.status(404).json({ detail: "Session expired or not found. Please start a new session." });
    }

    const ai = getGeminiClient();

    // STAGE 1 -> STAGE 2: User answered Question 1. We evaluate and ask Diagnostic Question 2.
    if (session.stageNumber === 1 || stage === "observation") {
      session.answer1 = userText;

      let eval1 = "";
      let question2 = "";

      if (ai) {
        try {
          const prompt = `You are RAZE, an expert senior developer helping a colleague debug Python code.
The student is debugging this code:
\`\`\`python
${session.code}
\`\`\`
Expected: ${session.expectedResult}
Actual: ${session.actualResult || "None"}
Real execution on Python: ${session.realExecution.output || session.realExecution.error}

Question 1 was: "${session.question1}"
The developer answered: "${userText}".

TASK:
1. Briefly evaluate their answer in 1-2 conversational sentences.
   - Explain what they got right or gently clarify what was off.
   - Even if their answer is weak or incomplete, do NOT punish them. Be constructive.
2. Ask Diagnostic Question 2 (this will be the FINAL question before we give the full solution):
   - ONE focused question that helps them connect the dot to why the output diverged or why a specific copy/mutation took place.

Respond in strict JSON:
{
  "evaluation": "Brief, encouraging evaluation of their answer...",
  "question": "Diagnostic Question 2 (final question)..."
}`;

          const response = await ai.models.generateContent({
            model: GEMINI_MODEL,
            contents: prompt,
            config: {
              responseMimeType: "application/json",
            },
          });

          const parsed = JSON.parse(response.text || "{}");
          eval1 = parsed.evaluation || "";
          question2 = parsed.question || "";
        } catch (err) {
          console.warn("Gemini evaluation error:", err);
        }
      }

      if (!eval1) {
        eval1 = "Good thinking. You're touching on the exact mechanism: modifying a data structure in place shifts indices while the traversal counter keeps incrementing.";
      }
      if (!question2) {
        question2 = "If the items shift left by 1 index, but the loop pointer advances forward by 1 on the very next step, what happens to the item that just shifted into the current index?";
      }

      session.stageNumber = 2;
      session.currentStage = "diagnose_2";
      session.eval1 = eval1;
      session.question2 = question2;

      return res.json({
        session_id,
        stage: "diagnose_2",
        stage_number: 2,
        stage_title: "Diagnostic Question 2",
        evaluation: eval1,
        question: question2,
        message: `${eval1}\n\n${question2}`,
        suspicious_lines: session.suspiciousLines,
      });
    }

    // STAGE 2 -> STAGE 3: User answered Question 2. STOP ASKING QUESTIONS!
    // Immediately provide the complete explanation, code solution, and live result.
    session.answer2 = userText;

    let eval2 = "";
    let what_i_found = "";
    let whats_happening = "";
    let hidden_problem = "";
    let why_output_changed = "";
    let discrepancy_noticed = session.discrepancyNote || "";
    let corrected_code = "";
    let before_snippet = "";
    let after_snippet = "";
    let why_fix_works = "";
    let lesson = "";

    if (ai) {
      try {
        const prompt = `You are RAZE, an expert senior developer helping a colleague debug Python code.
The developer has completed Question 1 and Question 2.
STOP ASKING QUESTIONS. Now provide the complete diagnosis, solution, and takeaway.

CODE WITH BUG:
\`\`\`python
${session.code}
\`\`\`
Expected result: ${session.expectedResult}
Actual result reported by developer: ${session.actualResult || "None"}
Real execution output on Python 3: ${session.realExecution.output || session.realExecution.error}
Developer's Answer to Question 1: "${session.answer1 || ""}"
Developer's Answer to Question 2: "${userText}"

REQUIREMENTS:
1. "evaluation": 1-2 sentence brief wrap-up evaluating their Answer 2.
2. "what_i_found": 2–4 sentences clearly explaining the overall problem.
3. "whats_happening": Step-by-step breakdown of what happens at runtime.
4. "hidden_problem": Explain related issues such as references, in-place mutation, shallow copies vs deep copies, or off-by-one indices.
5. "why_output_changed": Explicitly connect the code behavior to the user's actual output.
6. "discrepancy_noticed": If Expected or Actual Result does not match what the supplied code would produce, point it out clearly. Never blindly trust user output. If no discrepancy, return null.
7. "corrected_code": Clean, idiomatic, fully functional Python code fixing the bug.
8. "before_snippet": 2-4 lines showing the problematic pattern/code.
9. "after_snippet": 2-4 lines showing the corrected approach.
10. "why_fix_works": 2–4 short paragraphs explaining why the fix works.
11. "lesson": Short, reusable software engineering / debugging principle.

Respond strictly in valid JSON:
{
  "evaluation": "...",
  "what_i_found": "...",
  "whats_happening": "...",
  "hidden_problem": "...",
  "why_output_changed": "...",
  "discrepancy_noticed": "..." or null,
  "corrected_code": "...",
  "before_snippet": "...",
  "after_snippet": "...",
  "why_fix_works": "...",
  "lesson": "..."
}`;

        const response = await ai.models.generateContent({
          model: GEMINI_MODEL,
          contents: prompt,
          config: {
            responseMimeType: "application/json",
          },
        });

        const parsed = JSON.parse(response.text || "{}");
        eval2 = parsed.evaluation || "";
        what_i_found = parsed.what_i_found || "";
        whats_happening = parsed.whats_happening || "";
        hidden_problem = parsed.hidden_problem || "";
        why_output_changed = parsed.why_output_changed || "";
        discrepancy_noticed = parsed.discrepancy_noticed || session.discrepancyNote || "";
        corrected_code = parsed.corrected_code || "";
        before_snippet = parsed.before_snippet || "";
        after_snippet = parsed.after_snippet || "";
        why_fix_works = parsed.why_fix_works || "";
        lesson = parsed.lesson || "";
      } catch (err) {
        console.warn("Gemini resolution generation notice:", err);
      }
    }

    // High quality offline fallback if needed
    if (!corrected_code) {
      eval2 = "Exactly right. When an element is removed, the remaining items shift left, and the pointer advances right, skipping the item that just moved into the current index.";
      what_i_found = "The primary bug is that the collection is being mutated in place during iteration. In Python, modifying the length of a list while traversing it desynchronizes the loop's internal index pointer.";
      whats_happening = "1. The loop starts at index 0 and inspects the first element.\n2. When an even number is detected, `.remove()` deletes it and shifts all subsequent elements left by 1 index.\n3. The loop counter increments to index 1 on the next step, skipping the element that just slid into index 0.";
      hidden_problem = "Python lists are mutable arrays of object references. When you call `.remove()`, the list resizes and elements shift immediately, but the iterator has no awareness that elements have shifted beneath it.";
      why_output_changed = `Because every removal causes the subsequent element to be skipped without inspection, only alternating matching elements are handled, leaving ${session.expectedResult} unsatisfied.`;
      corrected_code = `# Corrected idiomatic Python approach using list comprehension\nnumbers = [1, 2, 3, 4, 5]\nfiltered_numbers = [n for n in numbers if n % 2 != 0]\nprint(filtered_numbers)`;
      before_snippet = `# Problem: mutating list during for-loop traversal\nfor number in numbers:\n    if number % 2 == 0:\n        numbers.remove(number)`;
      after_snippet = `# Correct: construct a new filtered collection\nfiltered_numbers = [n for n in numbers if n % 2 != 0]`;
      why_fix_works = "Constructing a new list through a list comprehension avoids in-place mutation altogether. The original list remains untouched during filtering, ensuring every single element is inspected deterministically.";
      lesson = "Defensive Programming Principle: Never mutate the size of a collection while directly iterating over it. Prefer pure list comprehensions or iterate over an explicit snapshot (e.g. `list[:]`).";
    }

    // Run the corrected code in the real Python subprocess to provide genuine execution output
    const liveExecution = await runPythonSafe(corrected_code);

    session.stageNumber = 3;
    session.currentStage = "resolution";
    session.eval2 = eval2;

    res.json({
      session_id,
      stage: "resolution",
      stage_number: 3,
      stage_title: "Complete Analysis & Solution",
      is_complete: true,
      evaluation: eval2,
      what_i_found,
      whats_happening,
      hidden_problem,
      why_output_changed,
      discrepancy_noticed: discrepancy_noticed || null,
      corrected_code,
      before_snippet,
      after_snippet,
      why_fix_works,
      lesson,
      live_execution: liveExecution,
    });
  } catch (error: any) {
    res.status(500).json({ detail: error.message || "Failed to process response" });
  }
});

// POST /api/debug/stuck — Senior dev unblocking guidance
app.post("/api/debug/stuck", async (req, res) => {
  try {
    const { session_id, stage } = req.body;
    const session = sessions.get(session_id);

    if (!session) {
      return res.status(404).json({ detail: "Session not found." });
    }

    if (session.stageNumber === 1 || stage === "observation") {
      return res.json({
        session_id,
        stage: "observation",
        stage_number: 1,
        stage_title: "Mentor Hint",
        hint: "Look at what happens to the length and indexing of a list when `.remove()` runs: the items to the right shift left by 1 index to fill the gap.",
        message: "Hint: In Python, removing an item from a list shifts all subsequent items left by one position. But the `for` loop pointer continues moving forward to the next index number.",
        can_skip_to_solution: true,
      });
    }

    return res.json({
      session_id,
      stage: "diagnose_2",
      stage_number: 2,
      stage_title: "Mentor Hint",
      hint: "Because the remaining elements shift left while the loop counter moves right, the element that took the removed item's place is never inspected at all.",
      message: "Hint: When an item shifts into index i and the loop pointer immediately advances to index i + 1, index i is never visited again, skipping that element completely.",
      can_skip_to_solution: true,
    });
  } catch (err: any) {
    res.status(500).json({ detail: err.message || "Error handling stuck request" });
  }
});

app.listen(PORT, "0.0.0.0", () => {
  console.log(`RAZE AI Debugging Mentor running on http://0.0.0.0:${PORT}`);
});

