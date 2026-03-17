/* ============================================================
   HL7 → FHIR Converter — Frontend Application
   ============================================================ */

'use strict';

// ---------------------------------------------------------------------------
// Sample HL7 messages
// ---------------------------------------------------------------------------
const SAMPLES = {
  adt: `MSH|^~\\&|ADT_SYSTEM|CITY_HOSPITAL|FHIR_SERVER|HQ|20240315143022||ADT^A01|MSG20240315001|P|2.5
EVN|A01|20240315143022|||NURSE^JANE^A
PID|1||MRN78965^^^CITYHOSP^MR~SSN123456789^^^NPI^SS||JOHNSON^MICHAEL^DAVID^JR^MR||19750820|M|||742 EVERGREEN TER^^SPRINGFIELD^IL^62701^USA||(217)555-0142^PRN^PH~mjohnson@email.com^NET^Internet||ENG|M|||SSN123456789
NK1|1|JOHNSON^SARAH^ANN|SPO|742 EVERGREEN TER^^SPRINGFIELD^IL^62701|(217)555-0143
PV1|1|I|MED^302^A^CITYHOSP|E|||NPI9876543^SMITH^RACHEL^M^DR|||IM|||||ADM|||V|||||||||||||||||||||CITY||||20240315143022`,

  oru: `MSH|^~\\&|LAB_SYSTEM|CITY_LAB|FHIR_SERVER|HQ|20240315150000||ORU^R01|LAB20240315001|P|2.5
PID|1||MRN78965^^^CITYHOSP^MR||JOHNSON^MICHAEL^DAVID||19750820|M
OBR|1|ORD20240315001|FILL20240315001|85025^CBC WITH DIFFERENTIAL^LN|||20240315140000|||||||||NPI9876543^SMITH^RACHEL|||F
OBX|1|NM|718-7^Hemoglobin^LN||14.2|g/dL^Grams per Deciliter^UCUM|13.5-17.5|N|||F|||20240315145500
OBX|2|NM|789-8^Erythrocytes^LN||4.85|10*6/uL^Million per microliter^UCUM|4.5-5.5|N|||F|||20240315145500
OBX|3|NM|6690-2^WBC^LN||7.2|10*3/uL^Thousand per microliter^UCUM|4.5-11.0|N|||F|||20240315145500
OBX|4|NM|777-3^Platelets^LN||220|10*3/uL^Thousand per microliter^UCUM|150-400|N|||F|||20240315145500
OBX|5|NM|4544-3^Hematocrit^LN||42.1|%^Percent^UCUM|41.0-53.0|N|||F|||20240315145500`,

  orm: `MSH|^~\\&|OE_SYSTEM|CITY_HOSPITAL|LAB_SYSTEM|CITY_LAB|20240315151500||ORM^O01|ORM20240315001|P|2.5
PID|1||MRN78965^^^CITYHOSP^MR||JOHNSON^MICHAEL^DAVID||19750820|M
PV1|1|O|CLINIC^101^A
ORC|NW|ORD20240315002||GRP20240315001|||||20240315151500|||NPI9876543^SMITH^RACHEL^M
OBR|1|ORD20240315002||80053^COMPREHENSIVE METABOLIC PANEL^LN|||20240315151500|||||||||NPI9876543^SMITH^RACHEL|||R`,
};

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
let currentResult = null;
let uploadedFile = null;
let historyItems = [];

// ---------------------------------------------------------------------------
// DOM references
// ---------------------------------------------------------------------------
const hl7Input      = document.getElementById('hl7-input');
const convertBtn    = document.getElementById('convert-btn');
const spinner       = document.getElementById('spinner');
const statusBar     = document.getElementById('status-bar');
const statusBadges  = document.getElementById('status-badges');
const warningList   = document.getElementById('warning-list');
const errorPanel    = document.getElementById('error-panel');
const errorMessage  = document.getElementById('error-message');
const errorList     = document.getElementById('error-list');
const outputPanel   = document.getElementById('output-panel');
const jsonOutput    = document.getElementById('json-output');
const xmlOutput     = document.getElementById('xml-output');
const readableOutput = document.getElementById('readable-output');
const summaryContent = document.getElementById('summary-content');
const dropZone      = document.getElementById('drop-zone');
const fileInput     = document.getElementById('file-input');
const fileInfo      = document.getElementById('file-info');
const clearBtn      = document.getElementById('clear-btn');
const refreshHistoryBtn = document.getElementById('refresh-history-btn');
const clearHistoryBtn = document.getElementById('clear-history-btn');
const historyList = document.getElementById('history-list');

// ---------------------------------------------------------------------------
// Input tab switching
// ---------------------------------------------------------------------------
document.querySelectorAll('.input-tabs .tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.input-tabs .tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById(`tab-${btn.dataset.tab}`).classList.add('active');
  });
});

// Output tab switching
document.querySelectorAll('.output-tabs .tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.output-tabs .tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.out-content').forEach(c => c.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById(`out-${btn.dataset.outTab}`).classList.add('active');
  });
});

// ---------------------------------------------------------------------------
// Sample buttons
// ---------------------------------------------------------------------------
document.querySelectorAll('.sample-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const type = btn.dataset.type;
    hl7Input.value = SAMPLES[type] || '';
    // Ensure text tab is active
    document.querySelectorAll('.input-tabs .tab-btn')[0].click();
  });
});

clearBtn.addEventListener('click', () => { hl7Input.value = ''; });

// ---------------------------------------------------------------------------
// History management
// ---------------------------------------------------------------------------
refreshHistoryBtn.addEventListener('click', loadHistory);
clearHistoryBtn.addEventListener('click', clearHistory);

// Load history when history tab is activated
document.querySelectorAll('.input-tabs .tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.input-tabs .tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById(`tab-${btn.dataset.tab}`).classList.add('active');

    // Load history when history tab is selected
    if (btn.dataset.tab === 'history') {
      loadHistory();
    }
  });
});

// ---------------------------------------------------------------------------
// File drag-and-drop / browse
// ---------------------------------------------------------------------------
dropZone.addEventListener('dragover', e => {
  e.preventDefault();
  dropZone.classList.add('drag-over');
});
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
dropZone.addEventListener('drop', e => {
  e.preventDefault();
  dropZone.classList.remove('drag-over');
  const file = e.dataTransfer.files[0];
  if (file) setUploadedFile(file);
});
dropZone.addEventListener('click', () => fileInput.click());
fileInput.addEventListener('change', () => {
  if (fileInput.files[0]) setUploadedFile(fileInput.files[0]);
});

function setUploadedFile(file) {
  uploadedFile = file;
  fileInfo.classList.remove('hidden');
  fileInfo.innerHTML = `
    <span>📄</span>
    <span><strong>${escapeHtml(file.name)}</strong> &nbsp;·&nbsp;
    ${formatBytes(file.size)}</span>
    <button onclick="clearFile()" style="margin-left:auto;background:none;border:none;color:#f06060;cursor:pointer;font-size:1rem;">✕</button>
  `;
}

function clearFile() {
  uploadedFile = null;
  fileInput.value = '';
  fileInfo.classList.add('hidden');
  fileInfo.innerHTML = '';
}

function formatBytes(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

// ---------------------------------------------------------------------------
// Convert button
// ---------------------------------------------------------------------------
convertBtn.addEventListener('click', async () => {
  // Determine which input mode is active
  const activeInputTab = document.querySelector('.input-tabs .tab-btn.active').dataset.tab;

  if (activeInputTab === 'file') {
    if (!uploadedFile) {
      showError('Please select a file to upload.', []);
      return;
    }
    await convertFile();
  } else {
    const text = hl7Input.value.trim();
    if (!text) {
      showError('Please paste an HL7 message or load a sample.', []);
      return;
    }
    await convertText(text);
  }
});

async function convertText(text) {
  setLoading(true);
  try {
    const resp = await fetch('/api/convert/text', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ hl7_message: text }),
    });
    const data = await resp.json();
    if (!resp.ok) {
      showError(data.detail || 'Conversion failed.', []);
    } else {
      handleResult(data);
    }
  } catch (err) {
    showError('Network error: ' + err.message, []);
  } finally {
    setLoading(false);
  }
}

async function convertFile() {
  setLoading(true);
  try {
    const formData = new FormData();
    formData.append('file', uploadedFile);
    const resp = await fetch('/api/convert/file', {
      method: 'POST',
      body: formData,
    });
    const data = await resp.json();
    if (!resp.ok) {
      showError(data.detail || 'Conversion failed.', []);
    } else if (data.batch) {
      // Show first successful result for batch; report summary
      const successes = data.results.filter(r => r.success);
      if (successes.length === 0) {
        showError(`None of the ${data.count} messages could be converted.`, []);
      } else {
        handleResult(successes[0]);
        if (data.count > 1) {
          addWarning(`Batch file: ${data.count} messages found, showing first result. Download to get all.`);
        }
      }
    } else {
      handleResult(data);
    }
  } catch (err) {
    showError('Network error: ' + err.message, []);
  } finally {
    setLoading(false);
  }
}

// ---------------------------------------------------------------------------
// Result handling
// ---------------------------------------------------------------------------
function handleResult(result) {
  currentResult = result;
  hideError();

  if (!result.success) {
    showError('Conversion failed.', result.errors || []);
    return;
  }

  // Status bar
  statusBar.classList.remove('hidden');
  statusBadges.innerHTML = `
    <span class="status-badge status-success">✓ Converted</span>
    <span class="status-badge status-version">HL7 ${escapeHtml(result.hl7_version || 'unknown')}</span>
    <span class="status-badge status-type">${escapeHtml(result.message_type || '?')}${result.message_event ? '^' + escapeHtml(result.message_event) : ''}</span>
    <span class="status-badge status-type">${(result.resource_summary || []).length} FHIR Resources</span>
  `;

  warningList.innerHTML = '';
  (result.warnings || []).forEach(w => {
    const el = document.createElement('div');
    el.className = 'warning-item';
    el.innerHTML = `<span>⚠</span><span>${escapeHtml(w)}</span>`;
    warningList.appendChild(el);
  });

  // JSON
  const jsonStr = JSON.stringify(result.fhir_json, null, 2);
  jsonOutput.innerHTML = syntaxHighlightJson(jsonStr);

  // XML
  xmlOutput.textContent = result.fhir_xml || '';

  // Readable
  readableOutput.textContent = result.human_readable || '';

  // Summary
  summaryContent.innerHTML = '';
  (result.resource_summary || []).forEach(item => {
    const card = document.createElement('div');
    card.className = `summary-card rt-${item.resource_type}`;
    card.innerHTML = `
      <div class="summary-card-type">${escapeHtml(item.resource_type)}</div>
      <div class="summary-card-desc">${escapeHtml(item.description)}</div>
      <div class="summary-card-id">ID: ${escapeHtml(item.resource_id)}</div>
    `;
    summaryContent.appendChild(card);
  });

  outputPanel.classList.remove('hidden');
  outputPanel.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function addWarning(msg) {
  const el = document.createElement('div');
  el.className = 'warning-item';
  el.innerHTML = `<span>⚠</span><span>${escapeHtml(msg)}</span>`;
  warningList.appendChild(el);
}

// ---------------------------------------------------------------------------
// Copy & Download
// ---------------------------------------------------------------------------
window.copyOutput = async function(type) {
  if (!currentResult) return;
  let text = '';
  let btnEl;
  if (type === 'json') {
    text = JSON.stringify(currentResult.fhir_json, null, 2);
    btnEl = document.querySelector('#out-json .tool-btn');
  } else if (type === 'xml') {
    text = currentResult.fhir_xml || '';
    btnEl = document.querySelector('#out-xml .tool-btn');
  } else if (type === 'readable') {
    text = currentResult.human_readable || '';
    btnEl = document.querySelector('#out-readable .tool-btn');
  }

  try {
    await navigator.clipboard.writeText(text);
    if (btnEl) {
      const orig = btnEl.innerHTML;
      btnEl.innerHTML = '✓ Copied!';
      btnEl.classList.add('copied');
      setTimeout(() => { btnEl.innerHTML = orig; btnEl.classList.remove('copied'); }, 1800);
    }
  } catch {
    // Fallback
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    document.body.removeChild(ta);
  }
};

window.downloadOutput = function(type, filename, mimeType) {
  if (!currentResult) return;
  let content = '';
  if (type === 'json') {
    content = JSON.stringify(currentResult.fhir_json, null, 2);
  } else if (type === 'xml') {
    content = currentResult.fhir_xml || '';
  } else if (type === 'readable') {
    content = currentResult.human_readable || '';
  }
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
};

// ---------------------------------------------------------------------------
// UI helpers
// ---------------------------------------------------------------------------
function setLoading(loading) {
  convertBtn.disabled = loading;
  spinner.classList.toggle('hidden', !loading);
}

function showError(msg, errors) {
  errorPanel.classList.remove('hidden');
  errorMessage.textContent = msg;
  errorList.innerHTML = '';
  errors.forEach(e => {
    const li = document.createElement('li');
    li.textContent = e;
    errorList.appendChild(li);
  });
  outputPanel.classList.add('hidden');
  statusBar.classList.add('hidden');
}

function hideError() {
  errorPanel.classList.add('hidden');
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// ---------------------------------------------------------------------------
// JSON syntax highlighting
// ---------------------------------------------------------------------------
function syntaxHighlightJson(json) {
  return json
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(
      /("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g,
      match => {
        let cls = 'json-num';
        if (/^"/.test(match)) {
          if (/:$/.test(match)) {
            cls = 'json-key';
          } else {
            cls = 'json-str';
          }
        } else if (/true|false/.test(match)) {
          cls = 'json-bool';
        } else if (/null/.test(match)) {
          cls = 'json-null';
        }
        return `<span class="${cls}">${match}</span>`;
      }
    );
}

// ---------------------------------------------------------------------------
// History functions
// ---------------------------------------------------------------------------
async function loadHistory() {
  try {
    const resp = await fetch('/api/history');
    const data = await resp.json();
    if (!resp.ok) {
      throw new Error(data.detail || 'Failed to load history');
    }
    historyItems = data.history || [];
    renderHistory();
  } catch (err) {
    console.error('Failed to load history:', err);
    // Show empty state instead of error if fetch succeeded but no history
    historyItems = [];
    renderHistory();
  }
}

async function clearHistory() {
  if (!confirm('Are you sure you want to clear all conversion history?')) {
    return;
  }

  try {
    const resp = await fetch('/api/history', { method: 'DELETE' });
    if (!resp.ok) {
      throw new Error('Failed to clear history');
    }
    historyItems = [];
    renderHistory();
  } catch (err) {
    console.error('Failed to clear history:', err);
    alert('Failed to clear history');
  }
}

function renderHistory() {
  if (historyItems.length === 0) {
    historyList.innerHTML = `
      <div class="history-empty">
        <span>📋</span>
        <p>No conversion history yet. Convert some HL7 messages to see them here.</p>
      </div>
    `;
    return;
  }

  const html = historyItems.map(item => {
    const date = new Date(item.timestamp).toLocaleString();
    const statusClass = item.success ? 'history-success' : 'history-error';
    const statusIcon = item.success ? '✓' : '✗';
    const inputDesc = item.input_type === 'file' && item.input_name ?
      `File: ${escapeHtml(item.input_name)}` : 'Text input';

    return `
      <div class="history-item ${statusClass}" data-id="${item.id}">
        <div class="history-header">
          <div class="history-meta">
            <span class="history-date">${date}</span>
            <span class="history-type">${escapeHtml(item.message_type || '?')}${item.message_event ? '^' + escapeHtml(item.message_event) : ''}</span>
            <span class="history-input">${inputDesc}</span>
          </div>
          <div class="history-status">
            <span class="status-icon">${statusIcon}</span>
            <span class="status-text">${item.success ? 'Success' : 'Failed'}</span>
          </div>
        </div>
        <div class="history-actions">
          <button class="history-btn" onclick="loadHistoryItem('${item.id}')">Load</button>
          ${item.success ? `
            <button class="history-btn" onclick="copyHistoryOutput('${item.id}', 'json')">Copy JSON</button>
            <button class="history-btn" onclick="downloadHistoryOutput('${item.id}', 'json')">Download JSON</button>
            <button class="history-btn" onclick="copyHistoryOutput('${item.id}', 'xml')">Copy XML</button>
            <button class="history-btn" onclick="downloadHistoryOutput('${item.id}', 'xml')">Download XML</button>
          ` : ''}
        </div>
        ${item.errors && item.errors.length > 0 ? `
          <div class="history-errors">
            ${item.errors.map(err => `<div class="history-error-item">${escapeHtml(err)}</div>`).join('')}
          </div>
        ` : ''}
      </div>
    `;
  }).join('');

  historyList.innerHTML = html;
}

async function loadHistoryItem(itemId) {
  try {
    const resp = await fetch(`/api/history/${itemId}`);
    const item = await resp.json();
    if (!resp.ok) {
      throw new Error(item.detail || 'Failed to load history item');
    }

    // Switch to text tab and load the HL7 content
    document.querySelectorAll('.input-tabs .tab-btn')[0].click();
    hl7Input.value = item.hl7_content;

    // If successful, show the result
    if (item.success) {
      // Create a result object similar to what handleResult expects
      const result = {
        success: true,
        hl7_version: item.hl7_version,
        message_type: item.message_type,
        message_event: item.message_event,
        fhir_json: item.fhir_json,
        fhir_xml: item.fhir_xml,
        human_readable: item.human_readable,
        warnings: item.warnings || []
      };
      handleResult(result);
    }
  } catch (err) {
    console.error('Failed to load history item:', err);
    alert('Failed to load history item');
  }
}

function copyHistoryOutput(itemId, format) {
  const item = historyItems.find(h => h.id === itemId);
  if (!item) return;

  let text = '';
  if (format === 'json') {
    text = JSON.stringify(item.fhir_json, null, 2);
  } else if (format === 'xml') {
    text = item.fhir_xml || '';
  }

  if (text) {
    copyToClipboard(text);
  }
}

function downloadHistoryOutput(itemId, format) {
  const item = historyItems.find(h => h.id === itemId);
  if (!item) return;

  let content = '';
  let filename = '';
  let mimeType = '';

  if (format === 'json') {
    content = JSON.stringify(item.fhir_json, null, 2);
    filename = `fhir_bundle_${item.id}.json`;
    mimeType = 'application/json';
  } else if (format === 'xml') {
    content = item.fhir_xml || '';
    filename = `fhir_bundle_${item.id}.xml`;
    mimeType = 'application/xml';
  }

  if (content) {
    downloadFile(content, filename, mimeType);
  }
}

function copyToClipboard(text) {
  navigator.clipboard.writeText(text).then(() => {
    // Could add a toast notification here
    console.log('Copied to clipboard');
  }).catch(() => {
    // Fallback
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    document.body.removeChild(ta);
    document.body.removeChild(ta);
  });
}

function downloadFile(content, filename, mimeType) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
