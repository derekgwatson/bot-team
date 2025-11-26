// Monica Store Monitor - Popup UI Logic

let currentState = null;
let isReconfiguring = false; // Flag to prevent auto-refresh from overriding user action

// Initialize popup
document.addEventListener('DOMContentLoaded', async () => {
  await loadState();
  setupEventListeners();
});

// Show loading overlay
function showLoadingOverlay(message, submessage = 'Please wait...') {
  const overlay = document.getElementById('loading-overlay');
  const messageEl = document.getElementById('loading-message');
  const submessageEl = document.getElementById('loading-submessage');
  messageEl.textContent = message;
  submessageEl.textContent = submessage;
  overlay.classList.add('active');
}

// Hide loading overlay
function hideLoadingOverlay() {
  const overlay = document.getElementById('loading-overlay');
  overlay.classList.remove('active');
  // Reset submessage to default
  document.getElementById('loading-submessage').textContent = 'Please wait...';
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

  // Allow Enter key to submit configuration
  document.getElementById('monica-url').addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
      saveConfiguration();
    }
  });
  document.getElementById('registration-code').addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
      saveConfiguration();
    }
  });

  // Save form values as user types (so they persist if popup closes)
  document.getElementById('monica-url').addEventListener('input', (e) => {
    chrome.storage.local.set({ temp_monica_url: e.target.value });
  });
  document.getElementById('registration-code').addEventListener('input', (e) => {
    chrome.storage.local.set({ temp_registration_code: e.target.value });
  });
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

  // Device deleted from server - show config form with error message
  const deviceDeleted = currentState.configured && !currentState.registered && currentState.lastError;

  if (currentState.configured && currentState.registered) {
    // Show status
    configSection.style.display = 'none';
    statusSection.style.display = 'block';
    updateStatusDisplay();
  } else if (deviceDeleted) {
    // Device was deleted - show config form with error
    configSection.style.display = 'block';
    statusSection.style.display = 'none';

    // Show the error message in the config section
    document.getElementById('config-error').innerHTML =
      `<div class="error-message">${currentState.lastError}</div>`;

    // Pre-fill the server URL since we kept it
    if (currentState.monicaUrl) {
      document.getElementById('monica-url').value = currentState.monicaUrl;
    }

    // Clear registration code field
    document.getElementById('registration-code').value = '';

    // Hide cancel button since there's no valid config to go back to
    cancelButton.style.display = 'none';
    saveButton.textContent = 'Save & Start Monitoring';

    // Auto-focus registration code since URL is pre-filled
    setTimeout(() => {
      document.getElementById('registration-code').focus();
    }, 100);
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

    // Restore any temporary form values (in case popup was closed while filling form)
    restoreTemporaryFormValues();

    // Auto-focus the URL input field for better UX
    setTimeout(() => {
      document.getElementById('monica-url').focus();
    }, 100);
  }
}

// Restore temporary form values from storage
async function restoreTemporaryFormValues() {
  const { temp_monica_url, temp_registration_code, temp_awaiting_permission } =
    await chrome.storage.local.get(['temp_monica_url', 'temp_registration_code', 'temp_awaiting_permission']);

  if (temp_monica_url) {
    document.getElementById('monica-url').value = temp_monica_url;
  }
  if (temp_registration_code) {
    document.getElementById('registration-code').value = temp_registration_code;
  }

  // If we were waiting for permission and it's now granted, auto-continue
  if (temp_awaiting_permission && temp_monica_url) {
    try {
      const urlObj = new URL(temp_monica_url);
      const origin = `${urlObj.protocol}//${urlObj.host}/*`;
      const hasPermission = await chrome.permissions.contains({ origins: [origin] });

      if (hasPermission) {
        // Clear the flag
        await chrome.storage.local.remove(['temp_awaiting_permission']);
        console.log('[Monica Popup] Permission was granted, auto-continuing...');

        // Wake up the service worker and wait for it to be ready
        // by sending a getState message first
        chrome.runtime.sendMessage({ action: 'getState' }, () => {
          // Service worker is now awake, give it a moment to initialize
          // then auto-continue with registration
          setTimeout(() => saveConfiguration(), 500);
        });
      }
    } catch (e) {
      console.log('[Monica Popup] Error checking permission:', e);
    }
  }
}

// Clear temporary form values from storage
function clearTemporaryFormValues() {
  chrome.storage.local.remove(['temp_monica_url', 'temp_registration_code', 'temp_awaiting_permission']);
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
    // Check if there's an error (e.g., device was deleted from server)
    if (currentState.lastError) {
      statusClass = 'disconnected';
      statusText = currentState.lastError;
      indicatorClass = 'red';
    } else {
      statusClass = 'disconnected';
      statusText = 'Registering...';
      indicatorClass = 'blue';
    }
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
  } else if (currentState.configured && currentState.registered) {
    // Registered but no latency yet - first test pending
    document.getElementById('latency-value').textContent = 'Testing...';
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
  let monicaUrl = document.getElementById('monica-url').value.trim();
  const registrationCode = document.getElementById('registration-code').value.trim().toUpperCase();

  const errorDiv = document.getElementById('config-error');
  errorDiv.innerHTML = '';

  // Validation
  if (!monicaUrl || !registrationCode) {
    errorDiv.innerHTML = '<div class="error-message">All fields are required</div>';
    return;
  }

  // Add http:// if no protocol specified
  if (!monicaUrl.match(/^https?:\/\//i)) {
    monicaUrl = 'http://' + monicaUrl;
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
  showLoadingOverlay('Checking permission...');

  // Request permission for the specific origin
  const origin = `${urlObj.protocol}//${urlObj.host}/*`;

  // Check if permission already exists (wrap in Promise for compatibility)
  const hasPermission = await new Promise(resolve => {
    chrome.permissions.contains({ origins: [origin] }, resolve);
  });

  if (hasPermission) {
    // Permission already granted, skip straight to connection test
    console.log('[Monica Popup] Permission already granted, skipping request');
    await chrome.storage.local.remove(['temp_awaiting_permission']);
    proceedWithConfiguration(monicaUrl, registrationCode, saveButton, errorDiv, hasExistingConfig);
    return;
  }

  // Need to request permission - show instructions first with delay so user can read
  saveButton.textContent = 'Requesting permission...';
  showLoadingOverlay(
    'Permission Required',
    'A dialog will appear. Click "Allow", then REOPEN this extension to finish setup.'
  );

  // Set flag before requesting permission (popup may close during permission dialog)
  await chrome.storage.local.set({ temp_awaiting_permission: true });

  // Wait 2 seconds so user can read the instruction before dialog appears
  await new Promise(resolve => setTimeout(resolve, 2000));

  chrome.permissions.request({
    origins: [origin]
  }, async (granted) => {
    // Clear the awaiting flag since we're continuing in this session
    await chrome.storage.local.remove(['temp_awaiting_permission']);
    if (!granted) {
      hideLoadingOverlay();
      errorDiv.innerHTML = '<div class="error-message">Permission denied. Extension needs access to your Monica server to work.</div>';
      saveButton.disabled = false;
      saveButton.textContent = hasExistingConfig ? 'Update Configuration' : 'Save & Start Monitoring';
      return;
    }

    // Permission granted, proceed with configuration
    proceedWithConfiguration(monicaUrl, registrationCode, saveButton, errorDiv, hasExistingConfig);
  });
}

// Proceed with connection test and registration after permission is confirmed
function proceedWithConfiguration(monicaUrl, registrationCode, saveButton, errorDiv, hasExistingConfig) {
  const defaultButtonText = hasExistingConfig ? 'Update Configuration' : 'Save & Start Monitoring';

  // Test connection
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
        clearTemporaryFormValues(); // Clear temporary form values after successful configuration
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
}

// Show configuration screen
function showConfiguration() {
  isReconfiguring = true; // Prevent auto-refresh from switching back
  document.getElementById('config-section').style.display = 'block';
  document.getElementById('status-section').style.display = 'none';

  // Clear the form fields only (but don't clear temp storage yet - user might have been filling it out)
  document.getElementById('monica-url').value = '';
  document.getElementById('registration-code').value = '';

  // Restore any saved values from temp storage
  restoreTemporaryFormValues();

  // Clear any previous errors
  document.getElementById('config-error').innerHTML = '';

  // Show cancel button and update button text if there's an existing config
  const cancelButton = document.getElementById('cancel-config');
  const saveButton = document.getElementById('save-config');
  if (currentState.monicaUrl && currentState.deviceId) {
    cancelButton.style.display = 'block';
    saveButton.textContent = 'Update Configuration';
  }

  // Auto-focus the URL input field for better UX
  setTimeout(() => {
    document.getElementById('monica-url').focus();
  }, 100);
}

// Cancel configuration and go back to status
function cancelConfiguration() {
  isReconfiguring = false; // Allow normal UI updates
  clearTemporaryFormValues(); // Clear temporary form values when canceling
  updateUI(); // This will switch back to status view
}

// Auto-refresh status every 5 seconds
setInterval(() => {
  if (currentState && currentState.configured) {
    loadState();
  }
}, 5000);
