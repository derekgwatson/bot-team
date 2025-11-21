// Monica Store Monitor - Popup UI Logic

let currentState = null;
let isReconfiguring = false; // Flag to prevent auto-refresh from overriding user action

// Initialize popup
document.addEventListener('DOMContentLoaded', async () => {
  await loadState();
  setupEventListeners();
});

// Show loading overlay
function showLoadingOverlay(message) {
  const overlay = document.getElementById('loading-overlay');
  const messageEl = document.getElementById('loading-message');
  messageEl.textContent = message;
  overlay.classList.add('active');
}

// Hide loading overlay
function hideLoadingOverlay() {
  const overlay = document.getElementById('loading-overlay');
  overlay.classList.remove('active');
}

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
  document.getElementById('cancel-config').addEventListener('click', cancelConfiguration);
}

// Update UI based on state
function updateUI() {
  const configSection = document.getElementById('config-section');
  const statusSection = document.getElementById('status-section');

  // Don't auto-switch views if user is actively reconfiguring
  if (isReconfiguring) {
    return;
  }

  const cancelButton = document.getElementById('cancel-config');
  const saveButton = document.getElementById('save-config');

  if (currentState.configured && currentState.registered) {
    // Show status
    configSection.style.display = 'none';
    statusSection.style.display = 'block';
    updateStatusDisplay();
  } else {
    // Show configuration
    configSection.style.display = 'block';
    statusSection.style.display = 'none';

    // Show cancel button and update button text if there's a valid existing config
    // (i.e., user clicked "Reconfigure" vs first-time setup)
    if (currentState.monicaUrl && currentState.deviceId) {
      cancelButton.style.display = 'block';
      saveButton.textContent = 'Update Configuration';
    } else {
      cancelButton.style.display = 'none';
      saveButton.textContent = 'Save & Start Monitoring';
    }

    // Note: We intentionally don't pre-fill fields during reconfiguration
    // to give users a fresh start. Fields are cleared in showConfiguration()
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
  document.getElementById('server-url-value').textContent = currentState.monicaUrl || '-';
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

  // Disable button and show loading overlay
  const saveButton = document.getElementById('save-config');
  const hasExistingConfig = currentState.monicaUrl && currentState.deviceId;
  const defaultButtonText = hasExistingConfig ? 'Update Configuration' : 'Save & Start Monitoring';

  saveButton.disabled = true;
  saveButton.textContent = 'Requesting permission...';
  showLoadingOverlay('Requesting permission...');

  // Request permission for the specific origin
  const origin = `${urlObj.protocol}//${urlObj.host}/*`;

  chrome.permissions.request({
    origins: [origin]
  }, (granted) => {
    if (!granted) {
      hideLoadingOverlay();
      errorDiv.innerHTML = '<div class="error-message">Permission denied. Extension needs access to your Monica server to work.</div>';
      saveButton.disabled = false;
      saveButton.textContent = defaultButtonText;
      return;
    }

    // Permission granted, now test connection
    saveButton.textContent = 'Testing connection...';
    showLoadingOverlay('Testing connection...');

    chrome.runtime.sendMessage({
      action: 'testConnection',
      monicaUrl: monicaUrl
    }, (response) => {
    if (!response.success) {
      hideLoadingOverlay();
      errorDiv.innerHTML = `<div class="error-message">Cannot connect to Monica server: ${response.error}</div>`;
      saveButton.disabled = false;
      saveButton.textContent = defaultButtonText;
      return;
    }

    // Connection successful, save configuration
    saveButton.textContent = hasExistingConfig ? 'Updating...' : 'Registering...';
    showLoadingOverlay(hasExistingConfig ? 'Updating configuration...' : 'Registering device...');

    chrome.runtime.sendMessage({
      action: 'configure',
      monicaUrl: monicaUrl,
      registrationCode: registrationCode
    }, (response) => {
      hideLoadingOverlay();
      if (response.success) {
        isReconfiguring = false; // Reset flag so UI can update
        currentState = response.state;
        updateUI();
      } else {
        // Show the specific error message from registration
        const errorMessage = response.error || 'Configuration failed';
        errorDiv.innerHTML = `<div class="error-message">${errorMessage}</div>`;
        saveButton.disabled = false;
        saveButton.textContent = defaultButtonText;
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

  // Clear the form for a fresh start
  document.getElementById('monica-url').value = '';
  document.getElementById('registration-code').value = '';

  // Clear any previous errors
  document.getElementById('config-error').innerHTML = '';

  // Show cancel button and update button text if there's an existing config
  const cancelButton = document.getElementById('cancel-config');
  const saveButton = document.getElementById('save-config');
  if (currentState.monicaUrl && currentState.deviceId) {
    cancelButton.style.display = 'block';
    saveButton.textContent = 'Update Configuration';
  }
}

// Cancel configuration and go back to status
function cancelConfiguration() {
  isReconfiguring = false; // Allow normal UI updates
  updateUI(); // This will switch back to status view
}

// Auto-refresh status every 5 seconds
setInterval(() => {
  if (currentState && currentState.configured) {
    loadState();
  }
}, 5000);
