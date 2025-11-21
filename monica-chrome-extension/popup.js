// Monica Store Monitor - Popup UI Logic

let currentState = null;
let isReconfiguring = false; // Flag to prevent auto-refresh from overriding user action

// Initialize popup
document.addEventListener('DOMContentLoaded', async () => {
  await loadState();
  setupEventListeners();
});

// Load current state from background worker
async function loadState() {
  chrome.runtime.sendMessage({ action: 'getState' }, (state) => {
    currentState = state;
    updateUI();
  });
}

// Setup event listeners
function setupEventListeners() {
  document.getElementById('save-config').addEventListener('click', saveConfiguration);
  document.getElementById('reconfigure').addEventListener('click', showConfiguration);
}

// Update UI based on state
function updateUI() {
  const configSection = document.getElementById('config-section');
  const statusSection = document.getElementById('status-section');

  // Don't auto-switch views if user is actively reconfiguring
  if (isReconfiguring) {
    return;
  }

  if (currentState.configured && currentState.registered) {
    // Show status
    configSection.style.display = 'none';
    statusSection.style.display = 'block';
    updateStatusDisplay();
  } else {
    // Show configuration
    configSection.style.display = 'block';
    statusSection.style.display = 'none';

    // Pre-fill Monica URL if partially configured
    if (currentState.monicaUrl) {
      document.getElementById('monica-url').value = currentState.monicaUrl;
    }
  }
}

// Update status display
function updateStatusDisplay() {
  const statusIndicator = document.getElementById('status-indicator');

  // Determine status
  let statusClass = 'not-configured';
  let statusText = 'Not configured';
  let indicatorClass = 'blue';

  if (currentState.configured && currentState.registered) {
    if (currentState.lastError) {
      statusClass = 'disconnected';
      statusText = `Error: ${currentState.lastError}`;
      indicatorClass = 'red';
    } else {
      statusClass = 'connected';
      statusText = 'Connected and monitoring';
      indicatorClass = 'green';
    }
  } else if (currentState.configured) {
    statusClass = 'disconnected';
    statusText = 'Registering...';
    indicatorClass = 'blue';
  }

  statusIndicator.innerHTML = `
    <div class="status-card ${statusClass}">
      <span class="status-indicator ${indicatorClass}"></span>
      <span>${statusText}</span>
    </div>
  `;

  // Update metrics
  document.getElementById('store-value').textContent = currentState.storeCode || '-';
  document.getElementById('device-value').textContent = currentState.deviceLabel || '-';
  document.getElementById('device-id-value').textContent = currentState.deviceId || '-';
  document.getElementById('heartbeat-value').textContent = currentState.heartbeatCount || 0;

  if (currentState.lastLatency !== null) {
    document.getElementById('latency-value').textContent = `${currentState.lastLatency} ms`;
  } else {
    document.getElementById('latency-value').textContent = '-';
  }

  if (currentState.lastHeartbeat) {
    const date = new Date(currentState.lastHeartbeat);
    document.getElementById('last-heartbeat-value').textContent = date.toLocaleTimeString();
  } else {
    document.getElementById('last-heartbeat-value').textContent = '-';
  }
}

// Save configuration
async function saveConfiguration() {
  const monicaUrl = document.getElementById('monica-url').value.trim();
  const registrationCode = document.getElementById('registration-code').value.trim().toUpperCase();

  const errorDiv = document.getElementById('config-error');
  errorDiv.innerHTML = '';

  // Validation
  if (!monicaUrl || !registrationCode) {
    errorDiv.innerHTML = '<div class="error-message">All fields are required</div>';
    return;
  }

  // Validate URL format
  let urlObj;
  try {
    urlObj = new URL(monicaUrl);
  } catch (e) {
    errorDiv.innerHTML = '<div class="error-message">Invalid URL format</div>';
    return;
  }

  // Disable button during save
  const saveButton = document.getElementById('save-config');
  saveButton.disabled = true;
  saveButton.textContent = 'Requesting permission...';

  // Request permission for the specific origin
  const origin = `${urlObj.protocol}//${urlObj.host}/*`;

  chrome.permissions.request({
    origins: [origin]
  }, (granted) => {
    if (!granted) {
      errorDiv.innerHTML = '<div class="error-message">Permission denied. Extension needs access to your Monica server to work.</div>';
      saveButton.disabled = false;
      saveButton.textContent = 'Save & Start Monitoring';
      return;
    }

    // Permission granted, now test connection
    saveButton.textContent = 'Testing connection...';

    chrome.runtime.sendMessage({
      action: 'testConnection',
      monicaUrl: monicaUrl
    }, (response) => {
    if (!response.success) {
      errorDiv.innerHTML = `<div class="error-message">Cannot connect to Monica server: ${response.error}</div>`;
      saveButton.disabled = false;
      saveButton.textContent = 'Save & Start Monitoring';
      return;
    }

    // Connection successful, save configuration
    saveButton.textContent = 'Configuring...';

    chrome.runtime.sendMessage({
      action: 'configure',
      monicaUrl: monicaUrl,
      registrationCode: registrationCode
    }, (response) => {
      if (response.success) {
        isReconfiguring = false; // Reset flag so UI can update
        currentState = response.state;
        updateUI();
      } else {
        errorDiv.innerHTML = '<div class="error-message">Configuration failed</div>';
        saveButton.disabled = false;
        saveButton.textContent = 'Save & Start Monitoring';
      }
    });
    });
  });
}

// Show configuration screen
function showConfiguration() {
  isReconfiguring = true; // Prevent auto-refresh from switching back
  document.getElementById('config-section').style.display = 'block';
  document.getElementById('status-section').style.display = 'none';
}

// Auto-refresh status every 5 seconds
setInterval(() => {
  if (currentState && currentState.configured) {
    loadState();
  }
}, 5000);
