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
// FHIR Sample Bundles
// ---------------------------------------------------------------------------
const FHIR_SAMPLES = {
  adt: {
    resourceType: "Bundle", type: "collection",
    entry: [
      { resource: { resourceType: "Patient", id: "p1",
          name: [{ use: "official", family: "JOHNSON", given: ["MICHAEL", "DAVID"] }],
          birthDate: "1975-08-20", gender: "male",
          identifier: [{ system: "http://hospital.example.org/mrn", value: "MRN78965" }],
          address: [{ line: ["742 EVERGREEN TER"], city: "SPRINGFIELD", state: "IL", postalCode: "62701", country: "USA" }],
          telecom: [{ system: "phone", value: "(217)555-0142", use: "home" }]
      }},
      { resource: { resourceType: "Organization", id: "org1", name: "CITY_HOSPITAL" }},
      { resource: { resourceType: "Encounter", id: "enc1", status: "finished",
          class: { code: "IMP", display: "inpatient" },
          subject: { reference: "Patient/p1" },
          period: { start: "2024-03-15T14:30:22", end: "2024-03-20T10:00:00" },
          identifier: [{ value: "VN20240315001" }]
      }},
      { resource: { resourceType: "Practitioner", id: "dr1",
          identifier: [{ system: "http://hl7.org/fhir/sid/us-npi", value: "NPI9876543" }],
          name: [{ use: "official", family: "SMITH", given: ["RACHEL", "M"] }]
      }}
    ]
  },
  oru: {
    resourceType: "Bundle", type: "collection",
    entry: [
      { resource: { resourceType: "Patient", id: "p1",
          name: [{ family: "JOHNSON", given: ["MICHAEL"] }],
          birthDate: "1975-08-20", gender: "male",
          identifier: [{ system: "http://hospital.example.org/mrn", value: "MRN78965" }]
      }},
      { resource: { resourceType: "Practitioner", id: "dr1",
          identifier: [{ system: "http://hl7.org/fhir/sid/us-npi", value: "NPI9876543" }],
          name: [{ family: "SMITH", given: ["RACHEL"] }]
      }},
      { resource: { resourceType: "DiagnosticReport", id: "dr1",
          status: "final",
          code: { coding: [{ system: "http://loinc.org", code: "85025", display: "CBC WITH DIFFERENTIAL" }] },
          subject: { reference: "Patient/p1" },
          effectiveDateTime: "2024-03-15T14:00:00",
          identifier: [
            { type: { coding: [{ code: "PLAC" }] }, value: "ORD20240315001" },
            { type: { coding: [{ code: "FILL" }] }, value: "FILL20240315001" }
          ],
          result: [{ reference: "Observation/obs1" }, { reference: "Observation/obs2" }]
      }},
      { resource: { resourceType: "Observation", id: "obs1", status: "final",
          code: { coding: [{ system: "http://loinc.org", code: "718-7", display: "Hemoglobin" }] },
          valueQuantity: { value: 14.2, unit: "g/dL", system: "http://unitsofmeasure.org" },
          referenceRange: [{ text: "13.5-17.5" }], interpretation: [{ coding: [{ code: "N" }] }]
      }},
      { resource: { resourceType: "Observation", id: "obs2", status: "final",
          code: { coding: [{ system: "http://loinc.org", code: "6690-2", display: "WBC" }] },
          valueQuantity: { value: 7.2, unit: "10*3/uL", system: "http://unitsofmeasure.org" },
          referenceRange: [{ text: "4.5-11.0" }], interpretation: [{ coding: [{ code: "N" }] }]
      }}
    ]
  },
  orm: {
    resourceType: "Bundle", type: "collection",
    entry: [
      { resource: { resourceType: "Patient", id: "p1",
          name: [{ family: "JOHNSON", given: ["MICHAEL"] }],
          birthDate: "1975-08-20", gender: "male",
          identifier: [{ system: "http://hospital.example.org/mrn", value: "MRN78965" }]
      }},
      { resource: { resourceType: "Practitioner", id: "dr1",
          identifier: [{ system: "http://hl7.org/fhir/sid/us-npi", value: "NPI9876543" }],
          name: [{ family: "SMITH", given: ["RACHEL", "M"] }]
      }},
      { resource: { resourceType: "ServiceRequest", id: "sr1",
          status: "active", intent: "order", priority: "routine",
          subject: { reference: "Patient/p1" },
          requester: { reference: "Practitioner/dr1" },
          code: { coding: [{ system: "http://loinc.org", code: "80053", display: "COMPREHENSIVE METABOLIC PANEL" }] },
          identifier: [
            { type: { coding: [{ code: "PLAC" }] }, value: "ORD20240315002" }
          ],
          authoredOn: "2024-03-15T15:15:00"
      }}
    ]
  }
};

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
let currentResult = null;
let uploadedFile = null;
let historyItems = [];
let conversionDirection = 'hl7_to_fhir';
let aiModeEnabled = false;

// ---------------------------------------------------------------------------
// AI Mode Toggle
// ---------------------------------------------------------------------------
window.toggleAIMode = function() {
  aiModeEnabled = !aiModeEnabled;
  const sw = document.getElementById('ai-toggle-switch');
  const badge = document.getElementById('ai-mode-badge');
  const banner = document.getElementById('ai-active-banner');
  const convertBtnEl = document.getElementById('convert-btn');
  const btnIcon = document.getElementById('convert-btn-icon');
  const spinnerLabel = document.getElementById('spinner-label');
  const aiOutputBadge = document.getElementById('ai-output-badge');

  sw.classList.toggle('on', aiModeEnabled);
  badge.classList.toggle('hidden', !aiModeEnabled);
  banner.classList.toggle('hidden', !aiModeEnabled);
  convertBtnEl.classList.toggle('ai-btn', aiModeEnabled);

  if (aiModeEnabled) {
    btnIcon.textContent = '✨';
    spinnerLabel.textContent = 'AI Converting…';
  } else {
    btnIcon.textContent = '⚡';
    spinnerLabel.textContent = 'Converting…';
  }

  // Hide AI output badge until next conversion
  if (aiOutputBadge) aiOutputBadge.classList.add('hidden');
};

// ---------------------------------------------------------------------------
// Direction toggle
// ---------------------------------------------------------------------------
window.setDirection = function(dir) {
  conversionDirection = dir;
  const isHL7 = dir === 'hl7_to_fhir';

  // Toggle direction buttons
  document.getElementById('btn-hl7-to-fhir').classList.toggle('active', isHL7);
  document.getElementById('btn-fhir-to-hl7').classList.toggle('active', !isHL7);

  // Toggle input areas inside the text tab
  document.getElementById('hl7-input-area').classList.toggle('hidden', !isHL7);
  document.getElementById('fhir-input-area').classList.toggle('hidden', isHL7);

  // Update text tab label
  document.getElementById('in-tab-text').textContent = isHL7 ? 'Paste HL7' : 'Paste FHIR';

  // Hide Mapping Rules tab in FHIR→HL7 direction (Upload File stays visible for both)
  const tabMapping = document.getElementById('in-tab-mapping');
  if (tabMapping) tabMapping.classList.toggle('hidden', !isHL7);

  // Update drop zone hint text to match expected file type
  const dropHint = document.querySelector('.drop-hint');
  const fileAcceptInput = document.getElementById('file-input');
  if (isHL7) {
    if (dropHint) dropHint.textContent = 'Supported: .hl7 · .txt · .csv · .xlsx · .xls · .docx';
    if (fileAcceptInput) fileAcceptInput.accept = '.hl7,.txt,.csv,.xlsx,.xls,.docx';
  } else {
    if (dropHint) dropHint.textContent = 'Supported: .json (FHIR Bundle)';
    if (fileAcceptInput) fileAcceptInput.accept = '.json';
  }

  // If currently on a now-hidden tab, switch back to text tab
  const activeInTab = document.querySelector('.input-tabs .tab-btn.active');
  if (activeInTab && activeInTab.classList.contains('hidden')) {
    document.getElementById('in-tab-text').click();
  }

  // Update convert button label
  document.getElementById('convert-btn-label').textContent = isHL7 ? 'Convert to FHIR' : 'Convert to HL7';

  // HL7→FHIR output tabs: FHIR JSON, XML, Human Readable, Summary, Field Mappings (no HL7 Message)
  // FHIR→HL7 output tabs: HL7 Message only
  const outTabs = ['json', 'xml', 'readable', 'summary', 'mappings'];
  outTabs.forEach(t => {
    const el = document.getElementById('out-tab-' + t);
    if (el) el.classList.toggle('hidden', !isHL7);
  });
  const hl7outTab = document.getElementById('out-tab-hl7out');
  if (hl7outTab) hl7outTab.classList.toggle('hidden', isHL7);

  // Reset output panel
  outputPanel.classList.add('hidden');
  hideError();
  statusBar.classList.add('hidden');
};

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
const pdfPreview     = document.getElementById('pdf-preview');
const summaryContent = document.getElementById('summary-content');
const dropZone      = document.getElementById('drop-zone');
const fileInput     = document.getElementById('file-input');
const fileInfo      = document.getElementById('file-info');
const clearBtn      = document.getElementById('clear-btn');
const refreshHistoryBtn = document.getElementById('refresh-history-btn');
const clearHistoryBtn = document.getElementById('clear-history-btn');
const historyList = document.getElementById('history-list');
const convertBar = document.querySelector('.convert-bar');

// ---------------------------------------------------------------------------
// Input tab switching
// ---------------------------------------------------------------------------
document.querySelectorAll('.input-tabs .tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.input-tabs .tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById(`tab-${btn.dataset.tab}`).classList.add('active');
    // Hide convert bar if history or mapping tab is active
    if (btn.dataset.tab === 'history' || btn.dataset.tab === 'mapping') {
      convertBar.style.display = 'none';
    } else {
      convertBar.style.display = '';
    }
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

// FHIR sample buttons
document.querySelectorAll('.fhir-sample-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const type = btn.dataset.fhirType;
    const sample = FHIR_SAMPLES[type];
    if (sample) {
      document.getElementById('fhir-input').value = JSON.stringify(sample, null, 2);
    }
  });
});
document.getElementById('clear-fhir-btn').addEventListener('click', () => {
  document.getElementById('fhir-input').value = '';
});

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
  // Validate file type matches current direction
  const isFhirDir = conversionDirection === 'fhir_to_hl7';
  if (isFhirDir && !file.name.toLowerCase().endsWith('.json')) {
    showError('Please upload a .json file containing a FHIR Bundle.', []);
    fileInput.value = '';
    return;
  }
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
  const activeInputTab = document.querySelector('.input-tabs .tab-btn.active').dataset.tab;

  if (conversionDirection === 'fhir_to_hl7') {
    if (activeInputTab === 'file') {
      if (!uploadedFile) {
        showError('Please select a JSON file to upload.', []);
        return;
      }
      await convertFhirFileToHl7(uploadedFile);
    } else {
      const text = document.getElementById('fhir-input').value.trim();
      if (!text) {
        showError('Please paste a FHIR Bundle JSON or load a sample.', []);
        return;
      }
      let bundle;
      try {
        bundle = JSON.parse(text);
      } catch (e) {
        showError('Invalid JSON: ' + e.message, []);
        return;
      }
      if (aiModeEnabled) {
        await aiConvertFhirToHl7(bundle);
      } else {
        await convertFhirToHl7(bundle);
      }
    }
    return;
  }

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
    if (aiModeEnabled) {
      await aiConvertHl7ToFhir(text);
    } else {
      await convertText(text);
    }
  }
});

// ---------------------------------------------------------------------------
// API Configuration
// ---------------------------------------------------------------------------
const API_BASE = window.location.protocol + '//' + window.location.hostname + ':8000';

async function convertText(text) {
  setLoading(true);
  try {
    const resp = await fetch(API_BASE + '/api/convert/text', {
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

async function convertFhirToHl7(bundle) {
  setLoading(true);
  try {
    const resp = await fetch(API_BASE + '/api/convert/fhir-to-hl7', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ fhir_bundle: bundle }),
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

async function convertFhirFileToHl7(file) {
  setLoading(true);
  try {
    const text = await file.text();
    let bundle;
    try {
      bundle = JSON.parse(text);
    } catch (e) {
      showError('File does not contain valid JSON: ' + e.message, []);
      return;
    }
    const resp = await fetch(API_BASE + '/api/convert/fhir-to-hl7', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ fhir_bundle: bundle }),
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

// ---------------------------------------------------------------------------
// AI conversion functions
// ---------------------------------------------------------------------------
async function aiConvertHl7ToFhir(text) {
  setLoading(true);
  try {
    const resp = await fetch(API_BASE + '/api/convert/ai/hl7-to-fhir', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ hl7_message: text }),
    });
    const data = await resp.json();
    if (!resp.ok) {
      showError(data.detail || 'AI conversion failed.', []);
    } else {
      handleResult(data);
    }
  } catch (err) {
    showError('Network error: ' + err.message, []);
  } finally {
    setLoading(false);
  }
}

async function aiConvertFhirToHl7(bundle) {
  setLoading(true);
  try {
    const resp = await fetch(API_BASE + '/api/convert/ai/fhir-to-hl7', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ fhir_bundle: bundle }),
    });
    const data = await resp.json();
    if (!resp.ok) {
      showError(data.detail || 'AI conversion failed.', []);
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
    const resp = await fetch(API_BASE + '/api/convert/file', {
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

  // Show/hide AI output badge
  const aiOutputBadge = document.getElementById('ai-output-badge');
  if (aiOutputBadge) aiOutputBadge.classList.toggle('hidden', !result.ai_powered);

  const isFhirToHl7 = result.direction === 'fhir_to_hl7';

  // Status bar
  statusBar.classList.remove('hidden');
  if (isFhirToHl7) {
    statusBadges.innerHTML = `
      <span class="status-badge status-success">✓ Converted</span>
      <span class="status-badge status-direction">FHIR → HL7</span>
      <span class="status-badge status-type">${escapeHtml(result.message_type || '?')}</span>
    `;
  } else {
    statusBadges.innerHTML = `
      <span class="status-badge status-success">✓ Converted</span>
      <span class="status-badge status-version">HL7 ${escapeHtml(result.hl7_version || 'unknown')}</span>
      <span class="status-badge status-type">${escapeHtml(result.message_type || '?')}${result.message_event ? '^' + escapeHtml(result.message_event) : ''}</span>
      <span class="status-badge status-type">${(result.resource_summary || []).length} FHIR Resources</span>
    `;
  }

  warningList.innerHTML = '';
  (result.warnings || []).forEach(w => {
    const el = document.createElement('div');
    el.className = 'warning-item';
    el.innerHTML = `<span>⚠</span><span>${escapeHtml(w)}</span>`;
    warningList.appendChild(el);
  });

  // HL7 output (FHIR→HL7 direction)
  const hl7outEl = document.getElementById('hl7out-output');
  if (hl7outEl) hl7outEl.textContent = result.hl7_output ? result.hl7_output.replace(/\r/g, '\n') : '';

  // Show mappings tab for FHIR→HL7 direction when AI mode provides them
  const mappingsTab = document.getElementById('out-tab-mappings');
  if (mappingsTab && isFhirToHl7) {
    const hasMappings = (result.field_mappings || []).length > 0;
    mappingsTab.classList.toggle('hidden', !hasMappings);
  }

  // Activate the correct output tab for the current direction
  document.querySelectorAll('.output-tabs .tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.out-content').forEach(c => c.classList.remove('active'));
  if (isFhirToHl7) {
    document.getElementById('out-tab-hl7out').classList.add('active');
    document.getElementById('out-hl7out').classList.add('active');
  } else {
    document.getElementById('out-tab-json').classList.add('active');
    document.getElementById('out-json').classList.add('active');
  }

  // JSON
  const jsonStr = JSON.stringify(result.fhir_json, null, 2);
  jsonOutput.innerHTML = syntaxHighlightJson(jsonStr);

  // XML
  xmlOutput.textContent = result.fhir_xml || '';

  // PDF preview
  renderPDFPreview(result);

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

  // Field Mappings
  const mappingsContent = document.getElementById('mappings-content');
  mappingsContent.innerHTML = '';
  (result.field_mappings || []).forEach(resourceMapping => {
    const resourceDiv = document.createElement('div');
    resourceDiv.className = 'mapping-resource';

    const header = document.createElement('div');
    header.className = 'mapping-resource-header';
    header.textContent = `${resourceMapping.resource_type} - ${resourceMapping.resource_id}`;
    resourceDiv.appendChild(header);

    const table = document.createElement('table');
    table.className = 'mapping-table';

    const thead = document.createElement('thead');
    thead.innerHTML = `
      <tr>
        <th style="width:20%">FHIR Field</th>
        <th style="width:15%">HL7 Segment.Field</th>
        <th style="width:35%">HL7 Value</th>
        <th style="width:30%">Description</th>
      </tr>
    `;
    table.appendChild(thead);

    const tbody = document.createElement('tbody');
    (resourceMapping.field_mappings || []).forEach(mapping => {
      const row = document.createElement('tr');
      row.innerHTML = `
        <td class="mapping-fhir-field">${escapeHtml(mapping.fhir_field)}</td>
        <td>
          <span class="mapping-hl7-segment">${escapeHtml(mapping.hl7_segment)}</span>
          <span class="mapping-hl7-field">${escapeHtml(mapping.hl7_field)}</span>
        </td>
        <td class="mapping-hl7-value" title="${escapeHtml(mapping.hl7_value || '')}">${escapeHtml(mapping.hl7_value || 'N/A')}</td>
        <td class="mapping-description">${escapeHtml(mapping.description)}</td>
      `;
      tbody.appendChild(row);
    });
    table.appendChild(tbody);
    resourceDiv.appendChild(table);
    mappingsContent.appendChild(resourceDiv);
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
// ---------------------------------------------------------------------------
// PDF Report
// ---------------------------------------------------------------------------
function renderPDFPreview(result) {
  if (!pdfPreview) return;
  const msgType  = (result.message_type || 'Unknown').toUpperCase();
  const ts       = result.timestamp ? new Date(result.timestamp).toLocaleString() : new Date().toLocaleString();
  const warnings = result.warnings || [];
  const summary  = result.resource_summary || [];
  const mappings = result.field_mappings || [];

  let html = `
    <div class="pdf-prev-header">
      <div class="pdf-prev-title">HL7 → FHIR Conversion Report</div>
      <div class="pdf-prev-meta">
        <span><strong>Message Type:</strong> ${escapeHtml(msgType)}</span>
        <span><strong>Converted:</strong> ${escapeHtml(ts)}</span>
        <span><strong>Resources:</strong> ${summary.length}</span>
        <span><strong>Warnings:</strong> ${warnings.length}</span>
      </div>
    </div>`;

  if (warnings.length) {
    html += `<div class="pdf-prev-section"><div class="pdf-prev-section-title">Warnings</div><ul class="pdf-prev-warnings">`;
    warnings.forEach(w => { html += `<li>${escapeHtml(w)}</li>`; });
    html += `</ul></div>`;
  }

  if (summary.length) {
    html += `<div class="pdf-prev-section"><div class="pdf-prev-section-title">Resource Summary</div>
      <table class="pdf-prev-table"><thead><tr><th>Resource Type</th><th>Resource ID</th><th>Description</th></tr></thead><tbody>`;
    summary.forEach(r => {
      html += `<tr><td><span class="rt-badge rt-${escapeHtml(r.resource_type)}">${escapeHtml(r.resource_type)}</span></td><td class="mono">${escapeHtml(r.resource_id)}</td><td>${escapeHtml(r.description)}</td></tr>`;
    });
    html += `</tbody></table></div>`;
  }

  mappings.forEach(rm => {
    html += `<div class="pdf-prev-section"><div class="pdf-prev-section-title">${escapeHtml(rm.resource_type)} — ${escapeHtml(rm.resource_id)}</div>
      <table class="pdf-prev-table pdf-mapping-table" style="table-layout:fixed;width:100%">
        <colgroup><col style="width:20%"><col style="width:15%"><col style="width:35%"><col style="width:30%"></colgroup>
        <thead><tr><th>FHIR Field</th><th>HL7 Segment.Field</th><th>HL7 Value</th><th>Description</th></tr></thead><tbody>`;
    (rm.field_mappings || []).forEach(f => {
      html += `<tr>
        <td class="mono" style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${escapeHtml(f.fhir_field)}</td>
        <td style="white-space:nowrap"><span class="mapping-hl7-segment">${escapeHtml(f.hl7_segment)}</span> <span class="mapping-hl7-field">${escapeHtml(f.hl7_field)}</span></td>
        <td class="mono" style="word-break:break-all;white-space:normal" title="${escapeHtml(f.hl7_value||'')}">${escapeHtml(f.hl7_value||'N/A')}</td>
        <td style="white-space:normal">${escapeHtml(f.description)}</td>
      </tr>`;
    });
    html += `</tbody></table></div>`;
  });

  pdfPreview.innerHTML = html;
}

window.generatePDF = function() {
  if (!currentResult) return;
  const { jsPDF } = window.jspdf;
  if (!jsPDF) { alert('PDF library not loaded. Check your internet connection.'); return; }

  const doc = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' });
  const pageW   = doc.internal.pageSize.getWidth();
  const margin  = 14;
  const colW    = pageW - margin * 2;
  let   y       = 0;

  const msgType  = (currentResult.message_type || 'Unknown').toUpperCase();
  const ts       = currentResult.timestamp ? new Date(currentResult.timestamp).toLocaleString() : new Date().toLocaleString();
  const warnings = currentResult.warnings || [];
  const summary  = currentResult.resource_summary || [];
  const mappings = currentResult.field_mappings || [];

  // ---- Header bar ----
  doc.setFillColor(30, 64, 175);          // blue-800
  doc.rect(0, 0, pageW, 22, 'F');
  doc.setTextColor(255, 255, 255);
  doc.setFontSize(14);
  doc.setFont('helvetica', 'bold');
  doc.text('HL7 → FHIR Conversion Report', margin, 9);
  doc.setFontSize(8);
  doc.setFont('helvetica', 'normal');
  doc.text(`Message Type: ${msgType}   |   ${ts}   |   ${summary.length} resource(s)   |   ${warnings.length} warning(s)`, margin, 17);
  y = 28;
  doc.setTextColor(0, 0, 0);

  // ---- Warnings ----
  if (warnings.length) {
    doc.setFontSize(10);
    doc.setFont('helvetica', 'bold');
    doc.setTextColor(180, 100, 0);
    doc.text('Warnings', margin, y);
    y += 4;
    doc.setFont('helvetica', 'normal');
    doc.setFontSize(8);
    doc.setTextColor(80, 80, 80);
    warnings.forEach(w => {
      const lines = doc.splitTextToSize(`• ${w}`, colW);
      doc.text(lines, margin, y);
      y += lines.length * 4 + 1;
    });
    y += 4;
    doc.setTextColor(0, 0, 0);
  }

  // ---- Resource Summary ----
  if (summary.length) {
    doc.setFontSize(10);
    doc.setFont('helvetica', 'bold');
    doc.setTextColor(30, 64, 175);
    doc.text('Resource Summary', margin, y);
    y += 2;
    doc.setTextColor(0, 0, 0);
    doc.autoTable({
      startY: y,
      margin: { left: margin, right: margin },
      headStyles: { fillColor: [30, 64, 175], textColor: 255, fontStyle: 'bold', fontSize: 8 },
      bodyStyles: { fontSize: 7.5 },
      alternateRowStyles: { fillColor: [240, 245, 255] },
      head: [['Resource Type', 'Resource ID', 'Description']],
      body: summary.map(r => [r.resource_type, r.resource_id, r.description]),
      columnStyles: { 0: { cellWidth: 35 }, 1: { cellWidth: 45 } },
    });
    y = doc.lastAutoTable.finalY + 8;
  }

  // ---- Field Mappings per resource ----
  mappings.forEach(rm => {
    if (y > 260) { doc.addPage(); y = 14; }
    doc.setFontSize(10);
    doc.setFont('helvetica', 'bold');
    doc.setTextColor(30, 64, 175);
    doc.text(`${rm.resource_type}  —  ${rm.resource_id}`, margin, y);
    y += 2;
    doc.setTextColor(0, 0, 0);
    const tableWidth = pageW - margin * 2;
    doc.autoTable({
      startY: y,
      margin: { left: margin, right: margin },
      tableWidth: tableWidth,
      headStyles: { fillColor: [51, 102, 204], textColor: 255, fontStyle: 'bold', fontSize: 7.5, halign: 'left' },
      bodyStyles: { fontSize: 7, valign: 'top', overflow: 'linebreak' },
      alternateRowStyles: { fillColor: [245, 247, 255] },
      head: [['FHIR Field', 'HL7 Segment.Field', 'HL7 Value', 'Description']],
      body: (rm.field_mappings || []).map(f => [
        f.fhir_field,
        `${f.hl7_segment}  ${f.hl7_field}`,
        f.hl7_value || 'N/A',
        f.description,
      ]),
      columnStyles: {
        0: { cellWidth: tableWidth * 0.20, fontStyle: 'bold' },
        1: { cellWidth: tableWidth * 0.15 },
        2: { cellWidth: tableWidth * 0.35, font: 'courier', fontSize: 6.5 },
        3: { cellWidth: tableWidth * 0.30 },
      },
    });
    y = doc.lastAutoTable.finalY + 8;
  });

  // ---- Footer on every page ----
  const pageCount = doc.internal.getNumberOfPages();
  for (let i = 1; i <= pageCount; i++) {
    doc.setPage(i);
    doc.setFontSize(7);
    doc.setTextColor(150, 150, 150);
    doc.text(`HL7→FHIR Converter  |  Page ${i} of ${pageCount}`, margin, doc.internal.pageSize.getHeight() - 6);
    doc.text(ts, pageW - margin, doc.internal.pageSize.getHeight() - 6, { align: 'right' });
  }

  const safeName = `fhir_report_${msgType}_${Date.now()}.pdf`;
  doc.save(safeName);
};

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
  } else if (type === 'hl7out') {
    text = (currentResult.hl7_output || '').replace(/\r/g, '\n');
    btnEl = document.querySelector('#out-hl7out .tool-btn');
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
  } else if (type === 'hl7out') {
    content = (currentResult.hl7_output || '').replace(/\r/g, '\n');
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
    const resp = await fetch(API_BASE + '/api/history');
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
    const resp = await fetch(API_BASE + '/api/history', { method: 'DELETE' });
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
    const isFhirDir = (item.direction || 'hl7_to_fhir') === 'fhir_to_hl7';
    const dirLabel = isFhirDir ? 'FHIR→HL7' : 'HL7→FHIR';

    return `
      <div class="history-item ${statusClass}" data-id="${item.id}">
        <div class="history-header">
          <div class="history-meta">
            <span class="history-date">${date}</span>
            <span class="history-dir">${dirLabel}</span>
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
          ${item.success && !isFhirDir ? `
            <button class="history-btn" onclick="copyHistoryOutput('${item.id}', 'json')">Copy JSON</button>
            <button class="history-btn" onclick="downloadHistoryOutput('${item.id}', 'json')">Download JSON</button>
            <button class="history-btn" onclick="copyHistoryOutput('${item.id}', 'xml')">Copy XML</button>
            <button class="history-btn" onclick="downloadHistoryOutput('${item.id}', 'xml')">Download XML</button>
          ` : ''}
          ${item.success && isFhirDir ? `
            <button class="history-btn" onclick="copyHistoryOutput('${item.id}', 'hl7out')">Copy HL7</button>
            <button class="history-btn" onclick="downloadHistoryOutput('${item.id}', 'hl7out')">Download HL7</button>
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

    // Restore direction and input content
    const itemDir = item.direction || 'hl7_to_fhir';
    if (itemDir !== conversionDirection) {
      setDirection(itemDir);
    }
    document.getElementById('in-tab-text').click();
    if (itemDir === 'fhir_to_hl7') {
      document.getElementById('fhir-input').value = item.fhir_json
        ? JSON.stringify(item.fhir_json, null, 2)
        : '';
    } else {
      hl7Input.value = item.hl7_content || '';
    }

    // If successful, show the result
    if (item.success) {
      handleResult({
        success: true,
        direction: itemDir,
        hl7_version: item.hl7_version,
        message_type: item.message_type,
        message_event: item.message_event,
        fhir_json: item.fhir_json,
        fhir_xml: item.fhir_xml,
        human_readable: item.human_readable,
        hl7_output: item.hl7_output,
        warnings: item.warnings || [],
        resource_summary: [],
        field_mappings: item.field_mappings || [],
      });
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
  } else if (format === 'hl7out') {
    text = (item.hl7_output || '').replace(/\r/g, '\n');
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
  } else if (format === 'hl7out') {
    content = (item.hl7_output || '').replace(/\r/g, '\n');
    filename = `hl7_message_${item.id}.hl7`;
    mimeType = 'text/plain';
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
