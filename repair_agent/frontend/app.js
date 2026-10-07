// ============================================================
// RepairAgent Frontend — app.js
// Ultra-clean, intuitive interface for Quick Debug & Folder Repair
// ============================================================

// ------------------------------------------------------------
// API Base URL Detection (Zero hardcoded URLs/ports)
// ------------------------------------------------------------
function _detectApiBase() {
  if (window.location.protocol.startsWith('http')) {
    return window.location.origin + '/api';
  }
  const metaPort = document.querySelector('meta[name="api-port"]')?.content || '5050';
  return `http://localhost:${metaPort}/api`;
}

const API = _detectApiBase();

async function apiFetch(endpoint, options = {}) {
  const url = `${API}${endpoint.startsWith('/') ? '' : '/'}${endpoint}`;
  const resp = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  });
  if (!resp.ok) {
    let errText = `HTTP ${resp.status}`;
    try {
      const j = await resp.json();
      errText = j.error || j.message || errText;
    } catch {
      errText = await resp.text().catch(() => errText);
    }
    throw new Error(errText);
  }
  return resp.json();
}

function showToast(msg, type = 'info') {
  const t = document.getElementById('toast');
  if (!t) return;
  t.textContent = msg;
  t.className = `toast show toast-${type}`;
  clearTimeout(t._timer);
  t._timer = setTimeout(() => { t.className = 'toast'; }, 3500);
}

// ------------------------------------------------------------
// Navigation Tabs
// ------------------------------------------------------------
function initNavigation() {
  const navBtns = document.querySelectorAll('.sidebar-nav .nav-item');
  navBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const pageId = btn.dataset.page;
      switchPage(pageId);
    });
  });
}

function switchPage(pageId) {
  document.querySelectorAll('.sidebar-nav .nav-item').forEach(b => {
    b.classList.toggle('active', b.dataset.page === pageId);
  });
  document.querySelectorAll('.page').forEach(p => {
    p.classList.toggle('active', p.id === `page-${pageId}`);
  });

  if (pageId === 'debug') {
    renderLangSelector();
    loadModels();
  } else if (pageId === 'folder') {
    loadModels();
  } else if (pageId === 'settings') {
    refreshStatus();
  }
}

// ------------------------------------------------------------
// Config & Model Management
// ------------------------------------------------------------
let appConfig = null;
let supportedLanguages = [
  { id: 'python',     label: 'Python',     icon: '🐍', color: '#3776ab' },
  { id: 'cpp',        label: 'C++',        icon: 'C++', color: '#00599c' },
  { id: 'c',          label: 'C',          icon: 'C',   color: '#6d94c2' },
  { id: 'java',       label: 'Java',       icon: '☕',  color: '#f89820' },
  { id: 'javascript', label: 'JavaScript', icon: 'JS',  color: '#f0db4f' },
  { id: 'typescript', label: 'TypeScript', icon: 'TS',  color: '#3178c6' },
  { id: 'rust',       label: 'Rust',       icon: '🦀', color: '#ce412b' },
  { id: 'go',         label: 'Go',         icon: '🐹', color: '#00add8' },
  { id: 'csharp',     label: 'C#',         icon: 'C#',  color: '#7b5ea7' },
  { id: 'ruby',       label: 'Ruby',       icon: '💎', color: '#cc342d' },
  { id: 'swift',      label: 'Swift',      icon: '🦅', color: '#f05138' },
  { id: 'kotlin',     label: 'Kotlin',     icon: 'K',   color: '#7f52ff' },
  { id: 'bash',       label: 'Bash',       icon: '$',   color: '#4eaa25' },
  { id: 'php',        label: 'PHP',        icon: 'PHP', color: '#777bb4' },
];

let selectedLang = 'cpp';
let availableModels = [];

async function loadAppConfig() {
  try {
    appConfig = await apiFetch('/config');
    const vBadge = document.getElementById('app-version');
    if (vBadge && appConfig.version) vBadge.textContent = 'v' + appConfig.version;

    if (Array.isArray(appConfig.supported_languages) && appConfig.supported_languages.length > 0) {
      supportedLanguages = appConfig.supported_languages;
    }
  } catch (e) {
    console.warn('Config load fallback:', e);
  }
}

async function loadModels() {
  try {
    const data = await apiFetch('/models');
    availableModels = data.models || [];
    populateModelDropdowns(availableModels);
  } catch (e) {
    console.warn('Could not load models:', e);
    // fallback default models
    populateModelDropdowns([
      { id: 'gpt-4o-mini', name: 'GPT-4o mini (OpenAI)' },
      { id: 'gpt-4o', name: 'GPT-4o (OpenAI)' },
      { id: 'claude-sonnet-4-20250514', name: 'Claude Sonnet 4 (Anthropic)' },
    ]);
  }
}

function populateModelDropdowns(models) {
  const selects = [document.getElementById('debug-model'), document.getElementById('folder-model')];
  selects.forEach(sel => {
    if (!sel) return;
    const currentVal = sel.value;
    sel.innerHTML = '';
    models.forEach(m => {
      const opt = document.createElement('option');
      opt.value = m.id;
      opt.textContent = m.name || m.id;
      sel.appendChild(opt);
    });
    if (currentVal && Array.from(sel.options).some(o => o.value === currentVal)) {
      sel.value = currentVal;
    } else if (sel.options.length > 0) {
      sel.selectedIndex = 0;
    }
  });
}

// ------------------------------------------------------------
// Server Status Checks
// ------------------------------------------------------------
async function refreshStatus() {
  const globalDot = document.querySelector('#global-status .status-dot');
  const globalTxt = document.querySelector('#global-status .status-text');
  const envContainer = document.getElementById('env-checks');

  try {
    const data = await apiFetch('/status');
    if (globalDot) globalDot.style.background = data.ready ? 'var(--accent3)' : 'var(--warn)';
    if (globalTxt) globalTxt.textContent = data.ready ? 'Connected' : 'Setup Required';

    if (envContainer && data.checks) {
      envContainer.innerHTML = '';
      Object.entries(data.checks).forEach(([name, val]) => {
        const item = document.createElement('div');
        item.className = 'env-check-item';
        item.innerHTML = `
          <div class="env-check-name">${name}</div>
          <div class="env-check-val ${val.ok ? 'ok' : 'missing'}">
            ${val.ok ? '✓ ' : '✗ '}${val.detail || (val.ok ? 'Ready' : 'Not configured')}
          </div>
        `;
        envContainer.appendChild(item);
      });
    }
  } catch (e) {
    if (globalDot) globalDot.style.background = 'var(--danger)';
    if (globalTxt) globalTxt.textContent = 'Server Offline';
    if (envContainer) {
      envContainer.innerHTML = `<div class="empty-state-sm" style="color:var(--danger)">Cannot connect to API server at ${API}</div>`;
    }
  }
}

// ------------------------------------------------------------
// PAGE 1: Quick Code Debugger Logic
// ------------------------------------------------------------
function renderLangSelector() {
  const container = document.getElementById('lang-selector');
  if (!container) return;
  container.innerHTML = '';

  supportedLanguages.forEach(lang => {
    const pill = document.createElement('div');
    pill.className = 'lang-pill' + (lang.id === selectedLang ? ' selected' : '');
    pill.dataset.lang = lang.id;
    pill.style.setProperty('--lang-color', lang.color || 'var(--accent)');
    pill.innerHTML = `<span class="lang-icon">${lang.icon}</span><span>${lang.label}</span>`;

    pill.addEventListener('click', () => {
      selectedLang = lang.id;
      document.querySelectorAll('.lang-pill').forEach(p => p.classList.remove('selected'));
      pill.classList.add('selected');
      const badge = document.getElementById('selected-lang-badge');
      if (badge) badge.textContent = lang.label;
      const editor = document.getElementById('debug-code');
      if (editor && !editor.value) editor.placeholder = getEditorPlaceholder(lang.id);
    });
    container.appendChild(pill);
  });

  const badge = document.getElementById('selected-lang-badge');
  const currentLangObj = supportedLanguages.find(l => l.id === selectedLang);
  if (badge && currentLangObj) badge.textContent = currentLangObj.label;

  const editor = document.getElementById('debug-code');
  if (editor && !editor.value) editor.placeholder = getEditorPlaceholder(selectedLang);
}

function getEditorPlaceholder(lang) {
  const map = {
    cpp: `#include <iostream>\n#include <vector>\n\n// Paste your C++ code here\nint main() {\n    std::cout << "Hello Bug" << std::endl;\n    return 0;\n}`,
    c: `#include <stdio.h>\n\n// Paste your C code here\nint main() {\n    printf("Hello\\n");\n    return 0;\n}`,
    python: `# Paste your Python code here\ndef solve(arr):\n    return arr[0]`,
    java: `public class Solution {\n    public static void main(String[] args) {\n        // Paste your Java code here\n    }\n}`,
    javascript: `// Paste your JavaScript code here\nfunction calculateTotal(items) {\n    return items.reduce((a, b) => a + b, 0);\n}`,
    typescript: `// Paste your TypeScript code here\nfunction processUser(id: number): string {\n    return "User: " + id;\n}`,
    rust: `// Paste your Rust code here\nfn main() {\n    println!("Hello Rust");\n}`,
    go: `package main\nimport "fmt"\n\nfunc main() {\n    fmt.Println("Hello Go")\n}`,
  };
  return map[lang] || `// Paste your ${lang} code here...`;
}

function loadSampleBugCode() {
  const samples = {
    cpp: `#include <iostream>
#include <vector>

// Bug: Off-by-one error and missing return value
int calculateSum(const std::vector<int>& numbers) {
    int sum = 0;
    for (size_t i = 0; i <= numbers.size(); ++i) { // Bug: <= causes out of bounds read
        sum += numbers[i];
    }
} // Bug: missing return statement

int main() {
    std::vector<int> nums = {10, 20, 30};
    std::cout << "Sum: " << calculateSum(nums) << std::endl;
    return 0;
}`,
    python: `def binary_search(arr, target):
    low = 0
    high = len(arr)  # Bug: should be len(arr) - 1
    while low <= high:
        mid = (low + high) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            low = mid + 1
        else:
            high = mid  # Bug: should be mid - 1
    return -1`,
    java: `public class StringUtils {
    public static String reverseWords(String sentence) {
        String[] words = sentence.split(" ");
        String result = "";
        for (int i = words.length; i >= 0; i--) { // Bug: index out of bounds
            result += words[i] + " ";
        }
        return result.trim();
    }
}`,
    javascript: `function findAverage(numbers) {
    let sum = 0;
    for (let i = 0; i < numbers.length; i++) {
        sum += numbers[i];
    }
    // Bug: Division by zero when array is empty, plus no return statement
    let avg = sum / numbers.length;
}`,
  };

  const code = samples[selectedLang] || samples.cpp;
  const editor = document.getElementById('debug-code');
  if (editor) editor.value = code;
  showToast(`Loaded sample buggy ${selectedLang.toUpperCase()} snippet`);
}

function clearDebugCode() {
  const editor = document.getElementById('debug-code');
  if (editor) {
    editor.value = '';
    editor.placeholder = getEditorPlaceholder(selectedLang);
  }
}

let lastDebugResult = null;

async function submitDebug() {
  const code = document.getElementById('debug-code')?.value.trim();
  if (!code) {
    showToast('Please paste or type some code to debug', 'warn');
    return;
  }

  const desc = document.getElementById('debug-description')?.value.trim();
  const model = document.getElementById('debug-model')?.value || 'gpt-4o-mini';
  const btn = document.getElementById('debug-btn');

  btn.disabled = true;
  btn.innerHTML = `<span class="spinner"></span> Analyzing Code…`;

  try {
    const data = await apiFetch('/debug', {
      method: 'POST',
      body: JSON.stringify({
        code,
        language: selectedLang,
        description: desc,
        model,
      }),
    });

    lastDebugResult = data;
    renderDebugResult(data);
    showToast('Code analysis completed!', 'success');
  } catch (err) {
    showToast(`Debug failed: ${err.message}`, 'danger');
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<span class="btn-icon">⚡</span> Analyze &amp; Fix Code`;
  }
}

function renderDebugResult(data) {
  document.getElementById('debug-empty-state').style.display = 'none';
  const panel = document.getElementById('debug-output-panel');
  panel.style.display = 'block';

  // Metrics Bar
  const bugs = data.bugs_found || [];
  const primaryBug = bugs[0] || {};
  const severity = primaryBug.severity || 'Medium';
  const bugType = primaryBug.type || 'Bug Detected';
  const conf = data.confidence || 'High';

  const sevChip = document.getElementById('metric-severity');
  sevChip.textContent = `Severity: ${severity.toUpperCase()}`;
  sevChip.className = `metric-chip severity-chip ${severity.toLowerCase()}`;

  const typeChip = document.getElementById('metric-bug-type');
  typeChip.textContent = `Type: ${bugType}`;

  const confChip = document.getElementById('metric-confidence');
  confChip.textContent = `Confidence: ${conf}`;

  // Root cause & Explanation
  document.getElementById('debug-root-cause').textContent = data.root_cause || 'Root cause identified.';
  document.getElementById('debug-explanation').textContent = data.explanation || '';

  // Fixed Code
  const fixedPre = document.getElementById('debug-fixed-code');
  fixedPre.textContent = data.fixed_code || '// No fixed code provided';

  const langLabel = document.getElementById('debug-fixed-lang-label');
  if (langLabel) langLabel.textContent = `${(data.language || selectedLang).toUpperCase()} — Fixed Code`;

  // Diff View
  renderDiffView('debug-diff-view', data.diff || '', data.original_code || '', data.fixed_code || '');

  // Changes List
  const changesContainer = document.getElementById('debug-changes-list');
  changesContainer.innerHTML = '';
  const changes = data.changes || [];
  if (changes.length === 0) {
    changesContainer.innerHTML = '<div class="empty-state-sm">No specific line breakdown provided.</div>';
  } else {
    changes.forEach((c, idx) => {
      const card = document.createElement('div');
      card.className = 'change-item-card';
      card.innerHTML = `
        <div class="change-what"><strong>Change #${idx + 1}:</strong> ${escapeHtml(c.what)}</div>
        <div class="change-why">${escapeHtml(c.why)}</div>
      `;
      changesContainer.appendChild(card);
    });
  }

  // Switch to fixed-code tab by default
  switchDebugTab('fixed-code');
}

function switchDebugTab(tabName) {
  document.querySelectorAll('.result-tab').forEach(t => {
    t.classList.toggle('active', t.dataset.tab === tabName);
  });
  document.querySelectorAll('#debug-output-panel .tab-pane').forEach(p => {
    p.classList.toggle('active', p.id === `tab-pane-${tabName}`);
  });
}

function copyFixedCode() {
  if (!lastDebugResult?.fixed_code) return;
  navigator.clipboard.writeText(lastDebugResult.fixed_code)
    .then(() => showToast('Fixed code copied to clipboard!', 'success'))
    .catch(() => showToast('Could not copy to clipboard', 'warn'));
}

function applyFixedCodeToEditor() {
  if (!lastDebugResult?.fixed_code) return;
  const editor = document.getElementById('debug-code');
  if (editor) {
    editor.value = lastDebugResult.fixed_code;
    showToast('Applied fixed code to editor!', 'success');
  }
}

// ------------------------------------------------------------
// PAGE 2: Local Folder Repair Agent
// ------------------------------------------------------------
let currentFolderScanData = null;

function useCurrentWorkspaceDir() {
  const folderInput = document.getElementById('folder-path');
  // Detect current workspace or default path
  folderInput.value = 'c:\\Users\\yashg\\OneDrive\\Desktop\\genai\\repair_agent';
  showToast('Set to current workspace folder');
}

async function scanLocalFolder() {
  const dirPath = document.getElementById('folder-path')?.value.trim();
  if (!dirPath) {
    showToast('Please enter a directory path from your laptop', 'warn');
    return;
  }

  const prompt = document.getElementById('folder-prompt')?.value.trim();
  const model = document.getElementById('folder-model')?.value || 'gpt-4o-mini';
  const btn = document.getElementById('folder-scan-btn');

  btn.disabled = true;
  btn.innerHTML = `<span class="spinner"></span> Scanning &amp; Repairing Directory…`;

  try {
    const data = await apiFetch('/project/scan', {
      method: 'POST',
      body: JSON.stringify({
        directory: dirPath,
        instructions: prompt,
        model,
      }),
    });

    currentFolderScanData = data;
    renderFolderResults(data);
    showToast(`Scanned ${data.total_files_scanned} files — found ${data.files_with_issues} issues!`, 'success');
  } catch (err) {
    showToast(`Scan failed: ${err.message}`, 'danger');
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<span class="btn-icon">🔍</span> Scan &amp; Repair Directory`;
  }
}

function renderFolderResults(data) {
  document.getElementById('folder-empty-state').style.display = 'none';
  const panel = document.getElementById('folder-results-panel');
  panel.style.display = 'block';

  document.getElementById('folder-stat-scanned').textContent = data.total_files_scanned || 0;
  document.getElementById('folder-stat-issues').textContent = data.files_with_issues || 0;
  document.getElementById('folder-summary-text').textContent = data.summary || 'Scan completed.';

  const container = document.getElementById('file-issues-container');
  container.innerHTML = '';

  const issues = data.issues || [];
  if (issues.length === 0) {
    container.innerHTML = `
      <div class="empty-state-sm" style="color:var(--accent3);padding:30px">
        ✓ No bugs or issues found in the scanned files! Codebase looks clean.
      </div>
    `;
    document.getElementById('apply-all-btn').style.display = 'none';
    return;
  }

  document.getElementById('apply-all-btn').style.display = 'inline-flex';

  issues.forEach((issue, idx) => {
    const card = document.createElement('div');
    card.className = 'file-issue-card';
    card.id = `issue-card-${idx}`;

    const sev = issue.severity || 'Medium';
    const relPath = issue.relative_path || `file_${idx}`;

    card.innerHTML = `
      <div class="file-issue-header">
        <div class="file-issue-title-wrap">
          <span class="file-icon">📄</span>
          <span class="file-path">${escapeHtml(relPath)}</span>
          <span class="metric-chip severity-chip ${sev.toLowerCase()}">${sev.toUpperCase()}</span>
        </div>
        <div class="file-issue-actions">
          <button class="btn btn-sm btn-success btn-apply-single" onclick="applySingleFileChange(${idx})">
            ✓ Accept &amp; Apply Fix
          </button>
        </div>
      </div>

      <div class="file-problem-box">
        <div class="problem-title"><strong>Issue:</strong> ${escapeHtml(issue.problem || 'Bug detected')}</div>
        <div class="problem-root"><strong>Root Cause:</strong> ${escapeHtml(issue.root_cause || '')}</div>
        <div class="problem-explanation">${escapeHtml(issue.explanation || '')}</div>
      </div>

      <div class="diff-viewer-wrap">
        <div class="diff-header-bar">Proposed Changes (Diff)</div>
        <div class="diff-viewer" id="folder-diff-${idx}"></div>
      </div>
    `;

    container.appendChild(card);
    renderDiffView(`folder-diff-${idx}`, issue.diff || '', issue.original_code || '', issue.fixed_code || '');
  });
}

async function applyAllFolderChanges() {
  if (!currentFolderScanData || !currentFolderScanData.issues?.length) return;

  const btn = document.getElementById('apply-all-btn');
  btn.disabled = true;
  btn.innerHTML = `<span class="spinner"></span> Applying Changes…`;

  try {
    const payload = {
      directory: currentFolderScanData.directory,
      files: currentFolderScanData.issues.map(i => ({
        relative_path: i.relative_path,
        fixed_code: i.fixed_code,
      })),
    };

    const res = await apiFetch('/project/apply', {
      method: 'POST',
      body: JSON.stringify(payload),
    });

    if (res.success) {
      showToast(`Successfully applied fixes to ${res.applied_files.length} file(s) on disk!`, 'success');
      // Mark all cards as applied
      document.querySelectorAll('.file-issue-card').forEach(c => {
        c.classList.add('applied');
        const actionCol = c.querySelector('.file-issue-actions');
        if (actionCol) actionCol.innerHTML = `<span class="badge badge-success">✓ Applied to Disk</span>`;
      });
      btn.style.display = 'none';
      document.getElementById('revert-btn').style.display = 'inline-flex';
    } else {
      showToast('No changes were applied.', 'warn');
    }
  } catch (err) {
    showToast(`Failed to apply changes: ${err.message}`, 'danger');
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<span class="btn-icon">✓</span> Accept &amp; Apply All Changes to Disk`;
  }
}

async function applySingleFileChange(index) {
  if (!currentFolderScanData || !currentFolderScanData.issues?.[index]) return;
  const issue = currentFolderScanData.issues[index];

  try {
    const payload = {
      directory: currentFolderScanData.directory,
      files: [{
        relative_path: issue.relative_path,
        fixed_code: issue.fixed_code,
      }],
    };

    const res = await apiFetch('/project/apply', {
      method: 'POST',
      body: JSON.stringify(payload),
    });

    if (res.success) {
      showToast(`Applied fix to ${issue.relative_path} on disk!`, 'success');
      const card = document.getElementById(`issue-card-${index}`);
      if (card) {
        card.classList.add('applied');
        const actions = card.querySelector('.file-issue-actions');
        if (actions) actions.innerHTML = `<span class="badge badge-success">✓ Applied to Disk</span>`;
      }
    }
  } catch (err) {
    showToast(`Failed to apply fix: ${err.message}`, 'danger');
  }
}

async function revertFolderChanges() {
  if (!currentFolderScanData) return;

  const btn = document.getElementById('revert-btn');
  btn.disabled = true;

  try {
    const res = await apiFetch('/project/revert', {
      method: 'POST',
      body: JSON.stringify({ directory: currentFolderScanData.directory }),
    });

    if (res.success) {
      showToast(`Reverted ${res.reverted_files.length} file(s) back to original state!`, 'success');
      scanLocalFolder();
    }
  } catch (err) {
    showToast(`Revert failed: ${err.message}`, 'danger');
  } finally {
    btn.disabled = false;
  }
}

// ------------------------------------------------------------
// Diff View Renderer (Green additions, red deletions)
// ------------------------------------------------------------
function renderDiffView(elementId, diffText, origCode, fixedCode) {
  const container = document.getElementById(elementId);
  if (!container) return;
  container.innerHTML = '';

  if (!diffText || !diffText.trim()) {
    if (origCode === fixedCode) {
      container.innerHTML = '<div class="diff-line diff-context">No code differences.</div>';
      return;
    }
  }

  const lines = (diffText || '').split('\n');
  lines.forEach(line => {
    const div = document.createElement('div');
    if (line.startsWith('+++') || line.startsWith('---')) {
      div.className = 'diff-line diff-file-header';
    } else if (line.startsWith('@@')) {
      div.className = 'diff-line diff-chunk-header';
    } else if (line.startsWith('+')) {
      div.className = 'diff-line diff-add';
    } else if (line.startsWith('-')) {
      div.className = 'diff-line diff-del';
    } else {
      div.className = 'diff-line diff-context';
    }
    div.textContent = line;
    container.appendChild(div);
  });
}

// ------------------------------------------------------------
// PAGE 3: Settings & API Keys
// ------------------------------------------------------------
async function saveApiKeys() {
  const gemini_key = document.getElementById('key-gemini')?.value.trim();
  const groq_key = document.getElementById('key-groq')?.value.trim();
  const openai_key = document.getElementById('key-openai')?.value.trim();
  const anthropic_key = document.getElementById('key-anthropic')?.value.trim();
  const statusEl = document.getElementById('keys-save-status');

  if (!gemini_key && !groq_key && !openai_key && !anthropic_key) {
    showToast('Please enter at least one API key (e.g. free Gemini or Groq key)', 'warn');
    return;
  }

  if (statusEl) statusEl.textContent = 'Saving…';

  try {
    await apiFetch('/keys', {
      method: 'POST',
      body: JSON.stringify({ gemini_key, groq_key, openai_key, anthropic_key }),
    });

    if (statusEl) {
      statusEl.textContent = '✓ Saved successfully!';
      statusEl.className = 'save-status success';
    }
    showToast('API keys saved and configured!', 'success');
    refreshStatus();
    loadModels();
  } catch (err) {
    if (statusEl) {
      statusEl.textContent = `Error: ${err.message}`;
      statusEl.className = 'save-status error';
    }
    showToast(`Could not save keys: ${err.message}`, 'danger');
  }
}

// ------------------------------------------------------------
// Utilities
// ------------------------------------------------------------
function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// ------------------------------------------------------------
// Initialization on page load
// ------------------------------------------------------------
document.addEventListener('DOMContentLoaded', async () => {
  initNavigation();
  await loadAppConfig();
  renderLangSelector();
  loadModels();
  refreshStatus();
  setInterval(refreshStatus, 30000);
});
