'use strict';

(function () {
  const backendUrl =
    (window.incidentAPI && window.incidentAPI.backendUrl) || 'http://127.0.0.1:8000';

  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => Array.from(document.querySelectorAll(selector));

  const elements = {
    verifyButton: $('#verifyButton'),
    sampleToggle: $('#sampleToggle'),
    sampleContainer: $('#sampleContainer'),
    sampleList: $('#sampleList'),
    hotspotBadge: $('#hotspotBadge'),
    hotspotList: $('#hotspotList'),
    httpMetric: $('#httpMetric'),
    cpuMetric: $('#cpuMetric'),
    alertList: $('#alertList'),
    systemFeed: $('#systemFeed'),
    systemFeedPrev: $('#systemFeedPrev'),
    systemFeedNext: $('#systemFeedNext'),
    systemFeedPageInfo: $('#systemFeedPageInfo'),
    notifySlack: $('#notifySlack'),
    slackToken: $('#slackToken'),
    slackWorkspace: $('#slackWorkspace'),
    slackChannel: $('#slackChannel'),
    slackChannelInput: $('#slackChannelInput'),
    slackAddChannel: $('#slackAddChannel'),
    slackRemoveChannel: $('#slackRemoveChannel'),
    slackTest: $('#slackTest'),
    slackSave: $('#slackSave'),
    promUrl: $('#promUrl'),
    promHttpQuery: $('#promHttpQuery'),
    promHttpThreshold: $('#promHttpThreshold'),
    promCpuQuery: $('#promCpuQuery'),
    promCpuThreshold: $('#promCpuThreshold'),
    promTest: $('#promTest'),
    promSave: $('#promSave'),
    aiApiKey: $('#aiApiKey'),
    aiStatus: $('#aiStatus'),
    aiSave: $('#aiSave'),
    ragRefresh: $('#ragRefresh'),
    ragFileInput: $('#ragFileInput'),
    ragUploadButton: $('#ragUploadButton'),
    ragStatus: $('#ragStatus'),
    ragTable: $('#ragTable'),
    ragPageInfo: $('#ragPageInfo'),
    ragPrevPage: $('#ragPrevPage'),
    ragNextPage: $('#ragNextPage'),
    emailInput: $('#emailInput'),
    emailAddButton: $('#emailAddButton'),
    emailList: $('#emailList'),
    emailPageInfo: $('#emailPageInfo'),
    emailPrevPage: $('#emailPrevPage'),
    emailNextPage: $('#emailNextPage'),
    toast: $('#toast'),
    analysisContent: $('#analysisContent'),
    modal: $('#reportModal'),
    modalTitle: $('#modalTitle'),
    modalTimestamp: $('#modalTimestamp'),
    modalStatus: $('#modalStatus'),
    modalReport: $('#modalReport'),
    modalHint: $('#modalHint'),
    modalClose: $('#modalClose'),
    actionResults: $('#actionResults'),
    actionModal: $('#actionModal'),
    actionModalTitle: $('#actionModalTitle'),
    actionModalSubtitle: $('#actionModalSubtitle'),
    actionModalStatus: $('#actionModalStatus'),
    actionModalList: $('#actionModalList'),
    actionModalHint: $('#actionModalHint'),
    actionModalApprove: $('#actionModalApprove'),
    actionModalLater: $('#actionModalLater'),
  };

  const tabs = $$('.tab');
  const tabPanels = $$('.tab-content');

  let pollHandle = null;
  let isRefreshing = false;
  let pendingRefresh = false;
  let applyingPreferences = false;
  let preferenceTimer = null;
  let lastSavedPreferences = { slack: true };
  let activeReport = null;
  let toastTimer = null;
  const STATUS_LABELS = {
    executed: 'Executed',
    pending: 'Pending',
    deferred: 'Deferred',
  };
  const RAG_STATUS_LABELS = {
    executed: 'Approved',
    deferred: 'Deferred',
    report: 'Report',
    reference: 'Reference',
  };
  const RAG_STATUS_CLASS = {
    executed: 'rag-pill--executed',
    deferred: 'rag-pill--deferred',
    report: 'rag-pill--report',
    reference: 'rag-pill--reference',
  };
  const RAG_PAGE_SIZE = 5;
  const EMAIL_PAGE_SIZE = 5;
  const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/i;
  const DEFAULT_SLACK_CHANNELS = ['#ops-incident', '#eng-incident', '#site-reliability'];
  const STORAGE_KEYS = {
    slackChannels: 'incident_console.slack_channels',
  };
  const FEED_PAGE_SIZE = 5;
  const RECOVERY_STATUS_LABELS = {
    recovered: 'Recovered',
    pending: 'Pending',
    not_executed: 'Not Executed',
    not_applicable: 'N/A',
    unknown: 'Unknown',
  };
  const RECOVERY_STATUS_CLASS = {
    recovered: 'rag-pill--recovered',
    pending: 'rag-pill--pending',
    not_executed: 'rag-pill--not_executed',
    not_applicable: 'rag-pill--not_applicable',
    unknown: 'rag-pill--unknown',
  };
  const INCIDENT_HINTS = {
    http_5xx_surge: {
      title: 'HTTP 5xx 폭주',
      hint: 'Checkout/Gateway 경로 5xx 초과',
      metric: 'http_error_rate',
      detail: 'http_error_rate가 Checkout 또는 Gateway 구간에서 임계치를 넘었습니다.',
    },
    cpu_spike_core: {
      title: 'CPU 사용량 스파이크',
      hint: '엣지 노드/핫 파드 CPU 초과',
      metric: 'cpu_usage',
      detail: 'cpu_usage가 특정 노드 또는 파드에서 임계치를 넘었습니다.',
    },
  };
  let activeActionExecution = null;
  let activeTab = 'slack';
  let ragLoaded = false;
  let ragLoading = false;
  let ragDocuments = [];
  let ragPage = 1;
  let emailRecipients = [];
  let emailPage = 1;
  let emailRequestBusy = false;
  let customSlackChannels = [];
  let feedPage = 1;
  let feedEntries = [];

  const escapeHtml = (value) => {
    if (typeof value !== 'string') {
      value = value == null ? '' : String(value);
    }
    return value
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  };

  const formatNumber = (value, digits = 4) => {
    if (typeof value !== 'number' || Number.isNaN(value)) {
      return '--';
    }
    return value.toFixed(digits);
  };

  const parseNumber = (value) => {
    const num = Number(value);
    return Number.isFinite(num) ? num : null;
  };

  const formatDate = (value) => {
    if (!value) {
      return '';
    }
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return value;
    }
    return date.toLocaleString();
  };

  const buildScenarioLookup = (scenarios) => {
    const map = {};
    if (!Array.isArray(scenarios)) {
      return map;
    }
    scenarios.forEach((scenario) => {
      if (scenario && scenario.code) {
        map[scenario.code] = scenario;
      }
    });
    return map;
  };

  const isConfigFeed = (entry) => {
    if (typeof entry !== 'string') {
      return false;
    }
    const lower = entry.toLowerCase();
    return (
      lower.includes('설정') ||
      lower.includes('settings saved') ||
      lower.includes('api key') ||
      lower.includes('configured')
    );
  };

  const translateFeed = (entry) => {
    if (!entry || typeof entry !== 'string') {
      return '';
    }
    if (entry.includes('Slack 설정을 저장했습니다')) {
      return entry;
    }
    if (entry.includes('Prometheus 설정을 저장했습니다')) {
      return entry;
    }
    if (entry.includes('OpenAI API Key가 설정되었습니다')) {
      return entry;
    }
    if (entry.includes('OpenAI API Key가 제거되었습니다')) {
      return entry;
    }
    if (entry.includes('settings saved')) {
      return entry.replace('settings saved', '설정을 저장했습니다');
    }
    if (entry.toLowerCase().includes('api key configured')) {
      return entry.replace(/api key configured/i, 'API Key가 설정되었습니다');
    }
    return entry;
  };

  const setBusy = (button, busy) => {
    if (!button) {
      return;
    }
    if (busy) {
      button.setAttribute('disabled', 'disabled');
      button.dataset.loading = 'true';
    } else {
      button.removeAttribute('disabled');
      delete button.dataset.loading;
    }
  };

  const showToast = (message, variant = 'info', duration = 4200) => {
    const toast = elements.toast;
    if (!toast) {
      return;
    }
    toast.textContent = message;
    toast.setAttribute('data-variant', variant);
    toast.classList.remove('hidden');
    void toast.offsetWidth;
    toast.classList.add('visible');
    if (toastTimer) {
      clearTimeout(toastTimer);
    }
    toastTimer = setTimeout(() => {
      toast.classList.remove('visible');
      toastTimer = setTimeout(() => {
        toast.classList.add('hidden');
        toastTimer = null;
      }, 250);
    }, duration);
  };

  const request = async (path, options = {}) => {
    const { method = 'GET', body, headers } = options;
    const init = { method, headers: { ...(headers || {}) } };
    if (body !== undefined) {
      const isFormData = typeof FormData !== 'undefined' && body instanceof FormData;
      if (isFormData) {
        init.body = body;
      } else {
        init.body = typeof body === 'string' ? body : JSON.stringify(body);
        if (!init.headers['Content-Type']) {
          init.headers['Content-Type'] = 'application/json';
        }
      }
    }
    let response;
    try {
      response = await fetch(`${backendUrl}${path}`, init);
    } catch (error) {
      throw new Error('네트워크 요청에 실패했습니다.');
    }

    const raw = await response.text();
    let data = null;
    if (raw) {
      try {
        data = JSON.parse(raw);
      } catch (_) {
        data = raw;
      }
    }

    if (!response.ok) {
      const detail =
        (data && data.detail) ||
        (data && data.message) ||
        (typeof data === 'string' ? data : `HTTP ${response.status}`);
      throw new Error(detail);
    }

    return data;
  };

  const refreshState = async ({ silent = false } = {}) => {
    if (isRefreshing) {
      pendingRefresh = true;
      return;
    }
    isRefreshing = true;
    try {
      const state = await request('/state');
      renderState(state);
      await loadRagData({ force: true, silent: true });
    } catch (error) {
      if (!silent) {
        showToast(error.message || '상태를 불러오지 못했습니다.', 'error');
      }
    } finally {
      isRefreshing = false;
      if (pendingRefresh) {
        pendingRefresh = false;
        refreshState({ silent: true });
      }
    }
  };

  const normalizeEmail = (value) => {
    if (typeof value !== 'string') {
      return '';
    }
    return value.trim().toLowerCase();
  };

  const getEmailPageCount = () => {
    if (!emailRecipients.length) {
      return 0;
    }
    return Math.ceil(emailRecipients.length / EMAIL_PAGE_SIZE);
  };

  const applyEmailRecipients = (recipients, { resetPage = true } = {}) => {
    if (Array.isArray(recipients)) {
      emailRecipients = recipients
        .slice()
        .map((entry) => ({
          ...entry,
          email: normalizeEmail(entry && entry.email ? String(entry.email) : ''),
        }))
        .filter((entry) => entry.email);
      emailRecipients.sort((a, b) => {
        const aTime = new Date(a.created_at || 0).getTime();
        const bTime = new Date(b.created_at || 0).getTime();
        if (Number.isNaN(aTime) && Number.isNaN(bTime)) {
          return 0;
        }
        if (Number.isNaN(aTime)) {
          return 1;
        }
        if (Number.isNaN(bTime)) {
          return -1;
        }
        return bTime - aTime;
      });
    } else {
      emailRecipients = [];
    }

    if (resetPage) {
      emailPage = 1;
    }

    const totalPages = getEmailPageCount();
    if (totalPages > 0) {
      if (emailPage < 1) {
        emailPage = 1;
      }
      if (emailPage > totalPages) {
        emailPage = totalPages;
      }
    } else {
      emailPage = 1;
    }

    renderEmailList();
  };

  const getEmailPageItems = () => {
    if (!emailRecipients.length) {
      return [];
    }
    const startIndex = (Math.max(emailPage, 1) - 1) * EMAIL_PAGE_SIZE;
    return emailRecipients.slice(startIndex, startIndex + EMAIL_PAGE_SIZE);
  };

  const renderEmailList = () => {
    const list = elements.emailList;
    if (!list) {
      return;
    }
    const entries = getEmailPageItems();
    if (!emailRecipients.length) {
      list.classList.add('empty');
      list.innerHTML = '<li class="email-empty">등록된 이메일 주소가 없습니다.</li>';
    } else {
      list.classList.remove('empty');
      list.innerHTML = '';
      const fragment = document.createDocumentFragment();
      entries.forEach((recipient) => {
        const item = document.createElement('li');
        item.className = 'email-entry';

        const info = document.createElement('div');
        info.className = 'email-entry__info';

        const address = document.createElement('span');
        address.className = 'email-entry__address';
        address.textContent = recipient.email;
        info.appendChild(address);

        const meta = document.createElement('span');
        meta.className = 'email-entry__meta';
        meta.textContent = formatDate(recipient.created_at);
        info.appendChild(meta);

        const remove = document.createElement('button');
        remove.type = 'button';
        remove.className = 'ghost small danger email-entry__delete';
        remove.dataset.recipientId = recipient.id;
        remove.textContent = '삭제';

        item.appendChild(info);
        item.appendChild(remove);
        fragment.appendChild(item);
      });
      list.appendChild(fragment);
    }
    updateEmailPaginationControls();
  };

  const updateEmailPaginationControls = () => {
    const info = elements.emailPageInfo;
    const prev = elements.emailPrevPage;
    const next = elements.emailNextPage;
    const totalPages = getEmailPageCount();
    if (info) {
      info.textContent = totalPages === 0 ? '0 / 0' : `${emailPage} / ${totalPages}`;
    }
    if (prev) {
      prev.disabled = totalPages <= 1 || emailPage <= 1;
    }
    if (next) {
      next.disabled = totalPages === 0 || emailPage >= totalPages;
    }
  };

  const goToEmailPage = (nextPage) => {
    if (!emailRecipients.length) {
      return;
    }
    const totalPages = getEmailPageCount();
    const target = Math.min(Math.max(nextPage, 1), totalPages);
    if (target === emailPage) {
      return;
    }
    emailPage = target;
    renderEmailList();
  };

  const getEmailInputValue = () => {
    if (!elements.emailInput) {
      return '';
    }
    return elements.emailInput.value.trim();
  };

  const updateEmailFormState = () => {
    if (!elements.emailAddButton) {
      return;
    }
    const value = getEmailInputValue();
    const valid = Boolean(value && EMAIL_PATTERN.test(value));
    elements.emailAddButton.disabled = !valid || emailRequestBusy;
  };

  const refreshEmailRecipients = async ({ silent = false } = {}) => {
    try {
      const payload = await request('/notifications/emails');
      applyEmailRecipients(payload && payload.emails, { resetPage: false });
    } catch (error) {
      if (!silent) {
        showToast(error.message || '이메일 목록을 불러오지 못했습니다.', 'error');
      }
    }
  };

  const handleEmailAdd = async () => {
    const email = getEmailInputValue();
    if (!email || !EMAIL_PATTERN.test(email)) {
      showToast('유효한 이메일 주소를 입력하세요.', 'error');
      return;
    }
    if (emailRequestBusy) {
      return;
    }
    emailRequestBusy = true;
    updateEmailFormState();
    setBusy(elements.emailAddButton, true);
    try {
      await request('/notifications/emails', {
        method: 'POST',
        body: { email },
      });
      showToast('이메일을 등록했습니다.');
      if (elements.emailInput) {
        elements.emailInput.value = '';
      }
      await refreshEmailRecipients({ silent: true });
    } catch (error) {
      showToast(error.message || '이메일 등록에 실패했습니다.', 'error');
    } finally {
      emailRequestBusy = false;
      setBusy(elements.emailAddButton, false);
      updateEmailFormState();
    }
  };

  const handleEmailDelete = async (recipientId) => {
    if (!recipientId) {
      return;
    }
    if (emailRequestBusy) {
      return;
    }
    emailRequestBusy = true;
    updateEmailFormState();
    try {
      await request(`/notifications/emails/${encodeURIComponent(recipientId)}`, {
        method: 'DELETE',
      });
      showToast('이메일을 삭제했습니다.');
      await refreshEmailRecipients({ silent: true });
    } catch (error) {
      showToast(error.message || '이메일 삭제에 실패했습니다.', 'error');
    } finally {
      emailRequestBusy = false;
      updateEmailFormState();
    }
  };

  const renderState = (state = {}) => {
    if (!state || typeof state !== 'object') {
      return;
    }
    applyEmailRecipients(state.email_recipients, { resetPage: false });
    renderPreferences(state.preferences);
    renderSlack(state.slack);
    renderPrometheus(state.prometheus);
    renderAi(state.ai);
    renderMetrics(state.monitor, state.prometheus);
    renderHotspots(state.monitor, state.scenarios);
    renderSamples(state.monitor);
    renderAlerts(state.alert_history);
    feedEntries = Array.isArray(state.feed) ? state.feed.slice() : [];
    feedPage = 1;
    renderFeed();
    renderAnalysis(state);
    renderActionResults(state.action_executions);
    handleActionQueue(state.action_executions);
    handlePendingReports(state.pending_reports);
  };

  const renderPreferences = (preferences) => {
    if (!preferences) {
      return;
    }
    applyingPreferences = true;
    if (elements.notifySlack) {
      elements.notifySlack.checked = Boolean(preferences.slack);
      delete elements.notifySlack.dataset.dirty;
    }
    applyingPreferences = false;
    lastSavedPreferences = {
      slack: Boolean(preferences.slack),
    };
  };

  const markPristine = (...inputs) => {
    inputs.forEach((input) => {
      if (input) {
        delete input.dataset.dirty;
      }
    });
  };

  const updateInputValue = (input, value) => {
    if (!input) {
      return;
    }
    const next = value == null ? '' : String(value);
    if (document.activeElement === input || input.dataset.dirty === 'true') {
      return;
    }
    if (input.value !== next) {
      input.value = next;
      delete input.dataset.dirty;
    }
  };

  const normalizeSlackChannelName = (value) => {
    if (typeof value !== 'string') {
      return '';
    }
    let channel = value.trim();
    if (!channel) {
      return '';
    }
    channel = channel.replace(/\s+/g, '-');
    channel = channel.replace(/^#+/, '');
    if (!channel) {
      return '';
    }
    return channel.startsWith('#') ? channel : `#${channel}`;
  };

  const loadCustomSlackChannels = () => {
    if (typeof window === 'undefined' || !window.localStorage) {
      return [];
    }
    try {
      const raw = window.localStorage.getItem(STORAGE_KEYS.slackChannels);
      if (!raw) {
        return [];
      }
      const parsed = JSON.parse(raw);
      if (!Array.isArray(parsed)) {
        return [];
      }
      return parsed
        .map((entry) => normalizeSlackChannelName(String(entry || '')))
        .filter((entry, index, arr) => entry && arr.indexOf(entry) === index);
    } catch {
      return [];
    }
  };

  const persistCustomSlackChannels = () => {
    if (typeof window === 'undefined' || !window.localStorage) {
      return;
    }
    window.localStorage.setItem(
      STORAGE_KEYS.slackChannels,
      JSON.stringify(customSlackChannels),
    );
  };

  let slackChannelsInitialized = false;

  const ensureSlackChannelsLoaded = () => {
    if (slackChannelsInitialized) {
      return;
    }
    customSlackChannels = loadCustomSlackChannels();
    slackChannelsInitialized = true;
  };

  const getAllSlackChannels = () => {
    ensureSlackChannelsLoaded();
    const seen = new Set();
    const ordered = [];
    const register = (value) => {
      const normalized = normalizeSlackChannelName(value);
      if (!normalized || seen.has(normalized)) {
        return;
      }
      seen.add(normalized);
      ordered.push(normalized);
    };
    DEFAULT_SLACK_CHANNELS.forEach(register);
    customSlackChannels.forEach(register);
    return ordered;
  };

  const updateSlackRemoveButtonState = () => {
    ensureSlackChannelsLoaded();
    const button = elements.slackRemoveChannel;
    const select = elements.slackChannel;
    if (!button || !select) {
      return;
    }
    const channel = normalizeSlackChannelName(select.value);
    const removable =
      Boolean(channel) && customSlackChannels.includes(channel);
    if (removable) {
      button.removeAttribute('disabled');
      button.dataset.channel = channel;
    } else {
      button.setAttribute('disabled', 'disabled');
      delete button.dataset.channel;
    }
  };

  const rebuildSlackChannelOptions = (preferredChannel) => {
    const select = elements.slackChannel;
    if (!select) {
      return;
    }
    const channels = getAllSlackChannels();
    const currentValue = select.value;
    const desiredValue =
      select.dataset.dirty === 'true'
        ? currentValue
        : normalizeSlackChannelName(preferredChannel) ||
          normalizeSlackChannelName(currentValue) ||
          channels[0] ||
          DEFAULT_SLACK_CHANNELS[0];

    if (desiredValue && !channels.includes(desiredValue)) {
      channels.push(desiredValue);
    }

    select.innerHTML = '';
    channels.forEach((channel) => {
      const option = document.createElement('option');
      option.value = channel;
      option.textContent = channel;
      select.appendChild(option);
    });

    if (select.dataset.dirty === 'true' && currentValue && channels.includes(currentValue)) {
      select.value = currentValue;
    } else if (desiredValue && channels.includes(desiredValue)) {
      select.value = desiredValue;
      delete select.dataset.dirty;
    } else if (!select.value && channels.length) {
      select.value = channels[0];
    }
    updateSlackRemoveButtonState();
  };

  const renderSlack = (settings = {}) => {
    updateInputValue(elements.slackToken, settings.token || '');
    updateInputValue(elements.slackWorkspace, settings.workspace || '');
    rebuildSlackChannelOptions(settings.channel || '#ops-incident');
  };

  const renderPrometheus = (settings = {}) => {
    updateInputValue(elements.promUrl, settings.url || '');
    updateInputValue(elements.promHttpQuery, settings.http_query || '');
    updateInputValue(elements.promHttpThreshold, settings.http_threshold || '0.05');
    updateInputValue(elements.promCpuQuery, settings.cpu_query || '');
    updateInputValue(elements.promCpuThreshold, settings.cpu_threshold || '0.80');
  };

  const renderAi = (aiState = {}) => {
    if (!elements.aiStatus) {
      return;
    }
    const configured = Boolean(aiState && aiState.configured);
    elements.aiStatus.dataset.configured = String(configured);
    elements.aiStatus.textContent = configured
      ? 'API Key가 이미 설정되었습니다. 새 값을 입력하면 교체됩니다.'
      : 'API Key가 아직 설정되지 않았습니다.';
  };

  const renderMetrics = (monitor, settings) => {
    const samples = monitor && Array.isArray(monitor.samples) ? monitor.samples : [];
    const latest = samples.length ? samples[samples.length - 1] : null;
    const httpThreshold = latest
      ? latest.http_threshold
      : parseNumber(settings && settings.http_threshold);
    const cpuThreshold = latest
      ? latest.cpu_threshold
      : parseNumber(settings && settings.cpu_threshold);

    applyMetric(elements.httpMetric, latest && latest.http, httpThreshold, latest && latest.http_exceeded);
    applyMetric(elements.cpuMetric, latest && latest.cpu, cpuThreshold, latest && latest.cpu_exceeded);
  };

  const renderHotspots = (monitor, scenarios) => {
    const list = elements.hotspotList;
    if (!list) {
      return;
    }
    const badge = elements.hotspotBadge;
    list.innerHTML = '';

    const scenarioMap = buildScenarioLookup(scenarios);
    const samples = monitor && Array.isArray(monitor.samples) ? monitor.samples : [];
    const latest = samples.length ? samples[samples.length - 1] : null;
    const reversedSamples = samples.slice().reverse();
    const httpSample = reversedSamples.find((sample) => sample && sample.http_exceeded) || latest;
    const cpuSample = reversedSamples.find((sample) => sample && sample.cpu_exceeded) || latest;
    const activeIncidents =
      monitor && Array.isArray(monitor.active_incidents) ? monitor.active_incidents : [];
    const sampleNode = latest && typeof latest.node === 'string' ? latest.node : '';

    const buildEntry = (code, metricKey, metricSample) => {
      const scenario = scenarioMap[code] || {};
      const fallback = INCIDENT_HINTS[code] || {};
      const metric = metricKey || fallback.metric || '';
      const valueKey = metric === 'http_error_rate' ? 'http' : 'cpu';
      const thresholdKey = valueKey === 'http' ? 'http_threshold' : 'cpu_threshold';
      const exceededKey = valueKey === 'http' ? 'http_exceeded' : 'cpu_exceeded';
      const sampleForMetric = metricSample || latest;
      const metricNode =
        sampleForMetric && typeof sampleForMetric.node === 'string' ? sampleForMetric.node : sampleNode;
      return {
        code,
        metric,
        title: scenario.title || fallback.title || code,
        hint: fallback.hint || scenario.description || scenario.source || metric || code,
        detail:
          (metricNode && metric
            ? `${metricNode}에서 ${metric} 임계값을 초과했습니다.`
            : '') ||
          fallback.detail ||
          scenario.description ||
          '',
        value: sampleForMetric ? sampleForMetric[valueKey] : null,
        threshold: sampleForMetric ? sampleForMetric[thresholdKey] : null,
        exceeded: sampleForMetric ? Boolean(sampleForMetric[exceededKey]) : false,
        active: activeIncidents.includes(code),
      };
    };

    const entries = [
      buildEntry('http_5xx_surge', 'http_error_rate', httpSample),
      buildEntry('cpu_spike_core', 'cpu_usage', cpuSample),
    ];

    const alertingEntries = entries.filter((entry) => entry.exceeded || entry.active);
    const hasAnyData = Boolean(latest) || activeIncidents.length > 0;

    if (!hasAnyData || !alertingEntries.length) {
      const empty = document.createElement('li');
      empty.className = 'hotspot-empty';
      empty.textContent = hasAnyData
        ? '현재 임계값을 넘은 이벤트가 없습니다.'
        : 'Prometheus 샘플을 기다리는 중입니다.';
      list.appendChild(empty);
      if (badge) {
        badge.textContent = '임계 초과 없음';
        badge.dataset.variant = 'ok';
      }
      return;
    }

    const alertingCount = alertingEntries.length;

    alertingEntries.forEach((entry) => {
      const item = document.createElement('li');
      item.className = 'hotspot-item';
      if (entry.exceeded || entry.active) {
        item.dataset.status = 'alert';
      }
      if (entry.active) {
        item.dataset.active = 'true';
      }

      const left = document.createElement('div');
      left.className = 'hotspot-left';

      const title = document.createElement('p');
      title.className = 'hotspot-title';
      title.textContent = entry.title;

      const meta = document.createElement('p');
      meta.className = 'hotspot-meta';
      meta.textContent = entry.hint;

      const detail = document.createElement('p');
      detail.className = 'hotspot-detail';
      detail.textContent =
        entry.detail ||
        `${entry.metric}가 임계치를 초과했습니다. 어디서 발생했는지 확인하세요.`;

      left.appendChild(title);
      left.appendChild(meta);
      left.appendChild(detail);

      const metric = document.createElement('div');
      metric.className = 'hotspot-metric';

      const metricLabel = document.createElement('span');
      metricLabel.className = 'hotspot-metric__label';
      metricLabel.textContent = entry.metric || entry.code;

      const metricValue = document.createElement('strong');
      metricValue.textContent = formatNumber(entry.value);

      const metricThreshold = document.createElement('span');
      metricThreshold.className = 'hotspot-threshold';
      metricThreshold.textContent = `thr ${formatNumber(entry.threshold)}`;

      const state = document.createElement('span');
      state.className = 'hotspot-state';
      state.textContent = entry.exceeded || entry.active ? 'Alerting' : 'Normal';

      metric.appendChild(metricLabel);
      metric.appendChild(metricValue);
      metric.appendChild(metricThreshold);
      metric.appendChild(state);

      item.appendChild(left);
      item.appendChild(metric);
      list.appendChild(item);
    });

    if (badge) {
      badge.textContent = alertingCount ? `${alertingCount}건 임계 초과` : '임계 초과 없음';
      badge.dataset.variant = alertingCount ? 'alert' : 'ok';
    }
  };

  const applyMetric = (element, value, threshold, exceeded) => {
    if (!element) {
      return;
    }
    const valueEl = element.querySelector('.metric-value');
    const thresholdEl = element.querySelector('.metric-threshold');
    if (!valueEl || !thresholdEl) {
      return;
    }
    if (typeof value === 'number' && Number.isFinite(value)) {
      valueEl.textContent = formatNumber(value);
      const thresholdText =
        typeof threshold === 'number' && Number.isFinite(threshold)
          ? formatNumber(threshold)
          : '--';
      thresholdEl.textContent = `threshold ${thresholdText}`;
      if (exceeded) {
        element.setAttribute('data-status', 'alert');
      } else {
        element.removeAttribute('data-status');
      }
    } else {
      valueEl.textContent = '--';
      const fallbackThreshold =
        typeof threshold === 'number' && Number.isFinite(threshold)
          ? formatNumber(threshold)
          : '--';
      thresholdEl.textContent = `threshold ${fallbackThreshold}`;
      element.removeAttribute('data-status');
    }
  };

  const renderSamples = (monitor) => {
    const list = elements.sampleList;
    if (!list) {
      return;
    }
    list.innerHTML = '';
    const samples = monitor && Array.isArray(monitor.samples) ? monitor.samples.slice() : [];
    if (!samples.length) {
      const empty = document.createElement('li');
      empty.textContent = '샘플 데이터가 아직 없습니다.';
      list.appendChild(empty);
      return;
    }
    samples
      .slice()
      .reverse()
      .forEach((sample) => {
        const item = document.createElement('li');
        const nodeText = sample.node ? `${sample.node} · ` : '';
        item.textContent = `${formatDate(sample.timestamp)} · ${nodeText}HTTP ${formatNumber(
          sample.http
        )} / ${formatNumber(sample.http_threshold)} · CPU ${formatNumber(sample.cpu)} / ${formatNumber(
          sample.cpu_threshold
        )}`;
        if (sample.http_exceeded || sample.cpu_exceeded) {
          item.dataset.status = 'alert';
        }
        list.appendChild(item);
      });
  };

  const renderAlerts = (history) => {
    const list = elements.alertList;
    if (!list) {
      return;
    }
    list.innerHTML = '';
    const alerts = Array.isArray(history) ? history : [];
    if (!alerts.length) {
      const empty = document.createElement('li');
      empty.textContent = '최근 트리거된 사고가 없습니다.';
      list.appendChild(empty);
      return;
    }
    alerts.slice(0, 20).forEach((entry) => {
      const item = document.createElement('li');
      item.textContent = entry;
      list.appendChild(item);
    });
  };

  const renderFeed = () => {
    const container = elements.systemFeed;
    if (!container) {
      return;
    }
    const entries = Array.isArray(feedEntries) ? feedEntries.slice() : [];
    const filtered = entries.filter(isConfigFeed);
    const ordered = filtered.slice().reverse();
    const totalPages = Math.max(1, Math.ceil(ordered.length / FEED_PAGE_SIZE));
    if (feedPage > totalPages) {
      feedPage = totalPages;
    }
    const start = (feedPage - 1) * FEED_PAGE_SIZE;
    const pageEntries = ordered.slice(start, start + FEED_PAGE_SIZE);

    container.innerHTML = '';
    if (!pageEntries.length) {
      container.textContent = '설정 변경 이력이 없습니다.';
    } else {
      pageEntries.forEach((entry) => {
        const block = document.createElement('div');
        block.className = 'feed-entry';
        block.textContent = translateFeed(entry);
        container.appendChild(block);
      });
    }

    if (elements.systemFeedPageInfo) {
      elements.systemFeedPageInfo.textContent = `${Math.min(feedPage, totalPages)} / ${totalPages}`;
    }
    if (elements.systemFeedPrev) {
      if (feedPage > 1) {
        elements.systemFeedPrev.removeAttribute('disabled');
      } else {
        elements.systemFeedPrev.setAttribute('disabled', 'disabled');
      }
    }
    if (elements.systemFeedNext) {
      if (feedPage < totalPages) {
        elements.systemFeedNext.removeAttribute('disabled');
      } else {
        elements.systemFeedNext.setAttribute('disabled', 'disabled');
      }
    }
  };

  const renderAnalysis = (state) => {
    const container = elements.analysisContent;
    if (!container) {
      return;
    }
    const report = state && state.last_report;
    if (report) {
      const metrics = report.metrics || {};
      const actionItems = Array.isArray(report.action_items) && report.action_items.length
        ? report.action_items.map((item) => `<li>${escapeHtml(item)}</li>`).join('')
        : '<li>등록된 조치 항목이 없습니다.</li>';
      const followUp = Array.isArray(report.follow_up) && report.follow_up.length
        ? report.follow_up.map((item) => `<li>${escapeHtml(item)}</li>`).join('')
        : '<li>추가 후속 조치가 없습니다.</li>';
      container.innerHTML = `
        <section class="analysis-section">
          <h3>Summary</h3>
          <p>${escapeHtml(report.summary || '요약 정보가 없습니다.')}</p>
        </section>
        <section class="analysis-section">
          <h3>Root Cause</h3>
          <p>${escapeHtml(report.root_cause || '근본 원인 분석이 필요합니다.')}</p>
        </section>
        <section class="analysis-section">
          <h3>Impact</h3>
          <p>${escapeHtml(report.impact || '영향 범위를 파악 중입니다.')}</p>
        </section>
        <section class="analysis-section">
          <h3>Action Items</h3>
          <ul>${actionItems}</ul>
        </section>
        <section class="analysis-section">
          <h3>Follow-up</h3>
          <ul>${followUp}</ul>
        </section>
        <section class="analysis-section">
          <h3>Latest Metrics</h3>
          <p class="analysis-metrics">HTTP ${formatNumber(metrics.http)} / ${formatNumber(
        metrics.http_threshold
      )} · CPU ${formatNumber(metrics.cpu)} / ${formatNumber(metrics.cpu_threshold)}</p>
        </section>
      `;
      return;
    }

    const scenario = state && state.last_alert;
    if (scenario) {
      const hypotheses = Array.isArray(scenario.hypotheses) && scenario.hypotheses.length
        ? `<ul>${scenario.hypotheses
            .map((item) => `<li>${escapeHtml(item)}</li>`)
            .join('')}</ul>`
        : '<p>등록된 가설이 없습니다.</p>';
      const evidences = Array.isArray(scenario.evidences) && scenario.evidences.length
        ? `<ul>${scenario.evidences
            .map((item) => `<li>${escapeHtml(item)}</li>`)
            .join('')}</ul>`
        : '<p>연계 증거가 없습니다.</p>';
      const actions = Array.isArray(scenario.actions) && scenario.actions.length
        ? `<ul>${scenario.actions
            .map((item) => `<li>${escapeHtml(item)}</li>`)
            .join('')}</ul>`
        : '<p>먼저 알람을 트리거하세요.</p>';
      container.innerHTML = `
        <section class="analysis-section">
          <h3>${escapeHtml(scenario.title)}</h3>
          <p>${escapeHtml(scenario.description || '시나리오 설명이 없습니다.')}</p>
        </section>
        <section class="analysis-section">
          <h3>Hypotheses</h3>
          ${hypotheses}
        </section>
        <section class="analysis-section">
          <h3>Evidence</h3>
          ${evidences}
        </section>
        <section class="analysis-section">
          <h3>Actions</h3>
          ${actions}
        </section>
      `;
      return;
    }

    container.textContent = '아직 분석된 보고서가 없습니다.';
  };

  const renderActionResults = (executions) => {
    const container = elements.actionResults;
    if (!container) {
      return;
    }
    const list = Array.isArray(executions) ? executions.slice().reverse() : [];
    if (!list.length) {
      container.classList.add('empty');
      container.textContent = '아직 승인된 조치 실행 내역이 없습니다.';
      return;
    }
    container.classList.remove('empty');
    container.innerHTML = '';
    list.forEach((execution) => {
      if (!execution) {
        return;
      }
      const entry = document.createElement('article');
      entry.className = 'action-entry';
      const status = (execution.status || 'pending').toLowerCase();
      entry.dataset.status = status;

      const header = document.createElement('header');
      const title = document.createElement('span');
      title.textContent = execution.scenario_title || '조치 계획';
      const badge = document.createElement('span');
      badge.className = 'status-badge';
      badge.dataset.status = status;
      badge.textContent = STATUS_LABELS[status] || status;
      header.appendChild(title);
      header.appendChild(badge);
      entry.appendChild(header);

      const createdAt = formatDate(execution.created_at);
      const executedAt = execution.executed_at ? formatDate(execution.executed_at) : '';
      const meta = document.createElement('div');
      meta.className = 'action-meta';
      meta.textContent = executedAt
        ? `요청 ${createdAt} · 실행 ${executedAt}`
        : `요청 ${createdAt}`;
      entry.appendChild(meta);

      const actions = Array.isArray(execution.actions) ? execution.actions : [];
      if (actions.length) {
        const actionList = document.createElement('ul');
        actions.forEach((action) => {
          const item = document.createElement('li');
          item.textContent = action;
          actionList.appendChild(item);
        });
        entry.appendChild(actionList);
      } else {
        const emptyNotice = document.createElement('div');
        emptyNotice.className = 'action-meta';
        emptyNotice.textContent = '등록된 조치 항목이 없습니다.';
        entry.appendChild(emptyNotice);
      }

      const results = Array.isArray(execution.results) ? execution.results : [];
      if (results.length) {
        const resultsWrapper = document.createElement('div');
        resultsWrapper.className = 'action-result-list';
        results.forEach((result) => {
          if (!result) {
            return;
          }
          const resultBlock = document.createElement('div');
          resultBlock.className = 'action-result';
          const titleEl = document.createElement('strong');
          titleEl.textContent = result.action || '조치';
          const statusLine = document.createElement('span');
          const statusLabel = result.status || '결과 확인';
          const timeLabel = formatDate(result.executed_at);
          statusLine.textContent = timeLabel ? `${statusLabel} · ${timeLabel}` : statusLabel;
          resultBlock.appendChild(titleEl);
          resultBlock.appendChild(statusLine);
          if (result.detail) {
            const detailLine = document.createElement('span');
            detailLine.className = 'action-meta';
            detailLine.textContent = result.detail;
            resultBlock.appendChild(detailLine);
          }
          resultsWrapper.appendChild(resultBlock);
        });
        entry.appendChild(resultsWrapper);
      }

      container.appendChild(entry);
    });
  };

  const getRagTotalPages = () => {
    if (!ragDocuments.length) {
      return 1;
    }
    return Math.ceil(ragDocuments.length / RAG_PAGE_SIZE);
  };

  const updateRagPaginationControls = () => {
    const info = elements.ragPageInfo;
    const prev = elements.ragPrevPage;
    const next = elements.ragNextPage;
    const totalRecords = ragDocuments.length;
    const hasRecords = totalRecords > 0;
    const totalPages = hasRecords ? getRagTotalPages() : 1;
    const currentPage = hasRecords ? ragPage : 1;

    if (info) {
      info.textContent = hasRecords ? `Page ${currentPage} / ${totalPages}` : 'No records';
    }
    if (prev) {
      if (!hasRecords || currentPage <= 1) {
        prev.setAttribute('disabled', 'disabled');
      } else {
        prev.removeAttribute('disabled');
      }
    }
    if (next) {
      if (!hasRecords || currentPage >= totalPages) {
        next.setAttribute('disabled', 'disabled');
      } else {
        next.removeAttribute('disabled');
      }
    }
  };

  const goToFeedPage = (nextPage) => {
    const entries = Array.isArray(feedEntries) ? feedEntries.slice() : [];
    const filtered = entries.filter(isConfigFeed);
    const totalPages = Math.max(1, Math.ceil(filtered.length / FEED_PAGE_SIZE));
    const target = Math.min(Math.max(1, nextPage), totalPages);
    feedPage = target;
    renderFeed();
  };

  const renderRagDocuments = (documents) => {
    if (Array.isArray(documents)) {
      ragDocuments = documents;
    }
    const statusEl = elements.ragStatus;
    const table = elements.ragTable;
    if (!statusEl || !table) {
      return;
    }
    const body = table.querySelector('tbody');
    if (!body) {
      return;
    }
    body.innerHTML = '';
    if (!ragDocuments.length) {
      statusEl.textContent = 'No RAG records found.';
      table.classList.add('hidden');
      updateRagPaginationControls();
      return;
    }
    const totalPages = getRagTotalPages();
    if (ragPage > totalPages) {
      ragPage = totalPages;
    }
    if (ragPage < 1) {
      ragPage = 1;
    }
    const startIndex = (ragPage - 1) * RAG_PAGE_SIZE;
    const pageDocuments = ragDocuments.slice(
      startIndex,
      startIndex + RAG_PAGE_SIZE,
    );
    statusEl.textContent = `${ragDocuments.length} RAG record(s) available.`;
    pageDocuments.forEach((doc) => {
      if (!doc) {
        return;
      }
      const metadata = doc.metadata && typeof doc.metadata === 'object' ? doc.metadata : {};
      const title = metadata.title || doc.title || 'Untitled';
      const scenarioCode = metadata.scenario_code || doc.scenario_code || '--';
      const statusKey = String(metadata.status || doc.status || 'reference').toLowerCase();
      const statusLabel = RAG_STATUS_LABELS[statusKey] || statusKey;
      const statusClass = RAG_STATUS_CLASS[statusKey] || 'rag-pill--reference';
      const createdAt = formatDate(metadata.created_at || doc.created_at || '');
      const summaryRaw = metadata.summary || doc.summary || '';
      const summary =
        typeof summaryRaw === 'string' && summaryRaw.length > 160
          ? `${summaryRaw.slice(0, 157)}…`
          : summaryRaw;
      const typeLabel = metadata.type || doc.type || '';

      const row = document.createElement('tr');

      const titleCell = document.createElement('td');
      titleCell.textContent = title;
      if (typeLabel) {
        const tag = document.createElement('span');
        tag.className = 'rag-type';
        tag.textContent = typeLabel;
        titleCell.appendChild(document.createElement('br'));
        titleCell.appendChild(tag);
      }
      row.appendChild(titleCell);

      const scenarioCell = document.createElement('td');
      scenarioCell.textContent = scenarioCode;
      row.appendChild(scenarioCell);

      const statusCell = document.createElement('td');
      const badge = document.createElement('span');
      badge.className = `rag-pill ${statusClass}`;
      badge.textContent = statusLabel;
      statusCell.appendChild(badge);
      row.appendChild(statusCell);

      const recoveryValue =
        metadata.recovery_status || doc.recovery_status || 'unknown';
      const recoveryKey = String(recoveryValue).toLowerCase();
      const recoveryLabel = RECOVERY_STATUS_LABELS[recoveryKey] || recoveryKey;
      const recoveryClass =
        RECOVERY_STATUS_CLASS[recoveryKey] || RECOVERY_STATUS_CLASS.unknown;
      const recoveryCell = document.createElement('td');
      const recoveryBadge = document.createElement('span');
      recoveryBadge.className = `rag-pill ${recoveryClass}`;
      recoveryBadge.textContent = recoveryLabel;
      recoveryCell.appendChild(recoveryBadge);
      row.appendChild(recoveryCell);

      const createdCell = document.createElement('td');
      createdCell.textContent = createdAt || '--';
      row.appendChild(createdCell);

      const summaryCell = document.createElement('td');
      summaryCell.textContent = summary || '--';
      row.appendChild(summaryCell);

      body.appendChild(row);
    });
    table.classList.remove('hidden');
    updateRagPaginationControls();
  };

  const goToRagPage = (targetPage) => {
    if (!ragDocuments.length) {
      return;
    }
    const totalPages = getRagTotalPages();
    const nextPage = Math.min(Math.max(targetPage, 1), totalPages);
    if (nextPage === ragPage) {
      return;
    }
    ragPage = nextPage;
    renderRagDocuments();
  };

  const loadRagData = async ({ force = false, silent = false, resetPage = false } = {}) => {
    if (!elements.ragTable) {
      return;
    }
    if (ragLoading) {
      return;
    }
    if (!force && ragLoaded) {
      return;
    }
    ragLoading = true;
    try {
      const response = await request('/rag/documents');
      const docsSource = response && response.documents;
      const documents = Array.isArray(docsSource)
        ? docsSource
        : docsSource
        ? Object.values(docsSource)
        : [];
      if (resetPage) {
        ragPage = 1;
      }
      renderRagDocuments(documents);
      ragLoaded = true;
    } catch (error) {
      if (!silent) {
        showToast(error.message || 'Failed to load RAG data.', 'error');
      }
    } finally {
      ragLoading = false;
    }
  };

  const getSelectedRagFile = () => {
    const input = elements.ragFileInput;
    if (!input || !input.files || !input.files.length) {
      return null;
    }
    return input.files[0];
  };

  const resetRagUploadInput = () => {
    if (elements.ragFileInput) {
      elements.ragFileInput.value = '';
    }
  };

  const updateRagUploadState = () => {
    const button = elements.ragUploadButton;
    if (!button || button.dataset.loading === 'true') {
      return;
    }
    const hasFile = Boolean(getSelectedRagFile());
    if (hasFile) {
      button.removeAttribute('disabled');
    } else {
      button.setAttribute('disabled', 'disabled');
    }
  };

  const handleRagUpload = async () => {
    const button = elements.ragUploadButton;
    const file = getSelectedRagFile();
    if (!button || !file) {
      showToast('먼저 JSON 또는 TXT 문서를 선택해 주세요.', 'error');
      return;
    }
    const formData = new FormData();
    formData.append('file', file);
    setBusy(button, true);
    try {
      const response = await request('/rag/upload', {
        method: 'POST',
        body: formData,
      });
      const message =
        (response && response.message) ||
        `${file.name} uploaded as RAG reference.`;
      showToast(message, 'success');
      resetRagUploadInput();
      ragLoaded = false;
      await loadRagData({ force: true, silent: true, resetPage: true });
    } catch (error) {
      showToast(error.message || 'Failed to upload RAG document.', 'error');
    } finally {
      setBusy(button, false);
      updateRagUploadState();
    }
  };

  const showActionModal = (execution) => {
    const modal = elements.actionModal;
    if (!modal || !execution) {
      return;
    }
    activeActionExecution = execution;
    modal.classList.remove('hidden');

    if (elements.actionModalTitle) {
      elements.actionModalTitle.textContent =
        execution.scenario_title || '조치 실행 승인';
    }
    if (elements.actionModalSubtitle) {
      elements.actionModalSubtitle.textContent = formatDate(execution.created_at);
    }
    if (elements.actionModalStatus) {
      elements.actionModalStatus.textContent = STATUS_LABELS.pending;
      elements.actionModalStatus.dataset.status = 'pending';
    }
    if (elements.actionModalList) {
      elements.actionModalList.innerHTML = '';
      const actions = Array.isArray(execution.actions) ? execution.actions : [];
      if (actions.length) {
        const ordered = document.createElement('ol');
        ordered.className = 'modal-ordered';
        actions.forEach((action) => {
          const item = document.createElement('li');
          item.textContent = action;
          ordered.appendChild(item);
        });
        elements.actionModalList.appendChild(ordered);
      } else {
        const empty = document.createElement('p');
        empty.textContent = '실행할 조치가 없습니다.';
        elements.actionModalList.appendChild(empty);
      }
    }
    if (elements.actionModalHint) {
      elements.actionModalHint.textContent =
        '확인을 누르면 조치 시뮬레이터 API를 호출하여 실행합니다.';
    }
  };

  const hideActionModal = () => {
    if (!elements.actionModal) {
      return;
    }
    elements.actionModal.classList.add('hidden');
  };

  const handleActionQueue = (executions) => {
    const queue = Array.isArray(executions) ? executions : [];
    const next = queue.find((item) => item && item.status === 'pending');
    if (!next) {
      activeActionExecution = null;
      hideActionModal();
      return;
    }
    if (
      activeActionExecution &&
      activeActionExecution.id === next.id &&
      elements.actionModal &&
      !elements.actionModal.classList.contains('hidden')
    ) {
      showActionModal(next);
      return;
    }
    showActionModal(next);
  };

  const handleActionApprove = async () => {
    if (!activeActionExecution) {
      hideActionModal();
      return;
    }
    setBusy(elements.actionModalApprove, true);
    if (elements.actionModalLater) {
      elements.actionModalLater.setAttribute('disabled', 'disabled');
    }
    try {
      await request(`/actions/${activeActionExecution.id}/execute`, { method: 'POST' });
      showToast('조치 실행을 완료했습니다.');
      hideActionModal();
      activeActionExecution = null;
      await refreshState({ silent: true });
    } catch (error) {
      showToast(error.message || '조치 실행에 실패했습니다.', 'error');
    } finally {
      setBusy(elements.actionModalApprove, false);
      if (elements.actionModalLater) {
        elements.actionModalLater.removeAttribute('disabled');
      }
    }
  };

  const handleActionLater = async () => {
    if (!activeActionExecution) {
      hideActionModal();
      return;
    }
    setBusy(elements.actionModalLater, true);
    if (elements.actionModalApprove) {
      elements.actionModalApprove.setAttribute('disabled', 'disabled');
    }
    try {
      await request(`/actions/${activeActionExecution.id}/defer`, { method: 'POST' });
      showToast('조치 계획을 조치 결과 탭에 저장했습니다.', 'warn');
      hideActionModal();
      activeActionExecution = null;
      await refreshState({ silent: true });
    } catch (error) {
      showToast(error.message || '조치 실행을 보류하는 데 실패했습니다.', 'error');
    } finally {
      setBusy(elements.actionModalLater, false);
      if (elements.actionModalApprove) {
        elements.actionModalApprove.removeAttribute('disabled');
      }
    }
  };

  const handlePendingReports = (reports) => {
    const queue = Array.isArray(reports) ? reports.slice() : [];
    if (activeReport) {
      const updated = queue.find((item) => item.id === activeReport.id);
      if (updated) {
        showPendingReport(updated);
        return;
      }
      if (!queue.length) {
        activeReport = null;
        hideModal();
        return;
      }
    }
    if (queue.length) {
      showPendingReport(queue[0]);
    } else {
      hideModal();
      activeReport = null;
    }
  };

  const showPendingReport = (report) => {
    const modal = elements.modal;
    if (!modal) {
      return;
    }
    activeReport = report;
    const metrics = report.metrics || {};
    if (elements.modalTitle) {
      elements.modalTitle.textContent = report.title || '자동 탐지 보고서';
    }
    if (elements.modalTimestamp) {
      elements.modalTimestamp.textContent = formatDate(report.created_at || metrics.timestamp);
    }
    if (elements.modalStatus) {
      if (Array.isArray(report.recipients_missing) && report.recipients_missing.length) {
        elements.modalStatus.textContent = '수동 조치 필요';
      } else {
        elements.modalStatus.textContent = '자동 전송 완료';
      }
    }
    if (elements.modalReport) {
      const actionItems = Array.isArray(report.action_items) && report.action_items.length
        ? report.action_items.map((item) => `<li>${escapeHtml(item)}</li>`).join('')
        : '<li>등록된 조치 항목이 없습니다.</li>';
      const followUp = Array.isArray(report.follow_up) && report.follow_up.length
        ? report.follow_up.map((item) => `<li>${escapeHtml(item)}</li>`).join('')
        : '<li>추가 후속 조치가 없습니다.</li>';
      elements.modalReport.innerHTML = `
        <section class="modal-section">
          <h4>요약</h4>
          <p>${escapeHtml(report.summary || '요약 정보가 없습니다.')}</p>
        </section>
        <section class="modal-section">
          <h4>근본 원인</h4>
          <p>${escapeHtml(report.root_cause || '근본 원인 분석이 필요합니다.')}</p>
        </section>
        <section class="modal-section">
          <h4>영향 범위</h4>
          <p>${escapeHtml(report.impact || '영향 범위를 파악 중입니다.')}</p>
        </section>
        <section class="modal-section">
          <h4>조치 계획</h4>
          <ul class="modal-list">${actionItems}</ul>
        </section>
        <section class="modal-section">
          <h4>후속 조치</h4>
          <ul class="modal-list">${followUp}</ul>
        </section>
        <section class="modal-section">
          <h4>지표</h4>
          <p class="analysis-metrics">HTTP ${formatNumber(metrics.http)} / ${formatNumber(
        metrics.http_threshold
      )} · CPU ${formatNumber(metrics.cpu)} / ${formatNumber(metrics.cpu_threshold)}</p>
        </section>
      `;
    }
    if (elements.modalHint) {
      const sent = Array.isArray(report.recipients_sent) ? report.recipients_sent.filter(Boolean) : [];
      const missing = Array.isArray(report.recipients_missing)
        ? report.recipients_missing.filter(Boolean)
        : [];
      const hints = [];
      if (sent.length) {
        hints.push(`전송 완료: ${sent.join(', ')}`);
      }
      if (missing.length) {
        hints.push(`추가 전송 필요: ${missing.join(', ')}`);
      }
      elements.modalHint.textContent = hints.join(' · ') || '보고서를 확인한 뒤 확인 버튼을 눌러주세요.';
    }
    modal.classList.remove('hidden');
  };

  const hideModal = () => {
    if (elements.modal) {
      elements.modal.classList.add('hidden');
    }
  };

  const getSlackPayload = () => ({
    token: elements.slackToken ? elements.slackToken.value.trim() : '',
    workspace: elements.slackWorkspace ? elements.slackWorkspace.value.trim() : '',
    channel:
      normalizeSlackChannelName(
        elements.slackChannel ? elements.slackChannel.value : '',
      ) || '#ops-incident',
  });

  const getPrometheusPayload = () => ({
    url: elements.promUrl ? elements.promUrl.value.trim() : '',
    http_query: elements.promHttpQuery ? elements.promHttpQuery.value.trim() : '',
    http_threshold: elements.promHttpThreshold ? elements.promHttpThreshold.value.trim() || '0.05' : '0.05',
    cpu_query: elements.promCpuQuery ? elements.promCpuQuery.value.trim() : '',
    cpu_threshold: elements.promCpuThreshold ? elements.promCpuThreshold.value.trim() || '0.80' : '0.80',
  });

  const getPrometheusTestPayload = () => ({
    url: elements.promUrl ? elements.promUrl.value.trim() : '',
    http_query: elements.promHttpQuery ? elements.promHttpQuery.value.trim() : '',
    cpu_query: elements.promCpuQuery ? elements.promCpuQuery.value.trim() : '',
  });

  const handlePreferenceChange = () => {
    if (applyingPreferences) {
      return;
    }
    clearTimeout(preferenceTimer);
    preferenceTimer = setTimeout(updatePreferences, 250);
  };

  const updatePreferences = async () => {
    const payload = {
      slack: Boolean(elements.notifySlack && elements.notifySlack.checked),
    };
    if (payload.slack === lastSavedPreferences.slack) {
      return;
    }
    try {
      await request('/notifications/preferences', { method: 'POST', body: payload });
      lastSavedPreferences = { ...payload };
      markPristine(elements.notifySlack);
      showToast('알림 설정을 업데이트했습니다.');
    } catch (error) {
      showToast(error.message || '알림 설정 업데이트에 실패했습니다.', 'error');
      applyingPreferences = true;
      if (elements.notifySlack) {
        elements.notifySlack.checked = lastSavedPreferences.slack;
        delete elements.notifySlack.dataset.dirty;
      }
      applyingPreferences = false;
    }
  };


  const handleVerify = async () => {
    setBusy(elements.verifyButton, true);
    try {
      await request('/alerts/verify', { method: 'POST' });
      showToast('Prometheus 검증을 실행했습니다.');
      await refreshState({ silent: true });
    } catch (error) {
      showToast(error.message || '검증을 실행하지 못했습니다.', 'error');
    } finally {
      setBusy(elements.verifyButton, false);
    }
  };

  const handleSlackTest = async () => {
    const payload = getSlackPayload();
    if (!payload.token) {
      showToast('Slack 토큰을 입력해주세요.', 'error');
      return;
    }
    setBusy(elements.slackTest, true);
    try {
      const result = await request('/slack/test', { method: 'POST', body: payload });
      const team = result && (result.team || result.team_name);
      showToast(team ? `Slack 연결 확인 완료 (${team})` : 'Slack 연결 확인 완료');
    } catch (error) {
      showToast(error.message || 'Slack 테스트에 실패했습니다.', 'error');
    } finally {
      setBusy(elements.slackTest, false);
    }
  };

  
  const handleSlackAddChannel = () => {
    const input = elements.slackChannelInput;
    const select = elements.slackChannel;
    if (!input || !select) {
      return;
    }
    const channel = normalizeSlackChannelName(input.value);
    if (!channel) {
      showToast('Please enter a Slack channel name to add.', 'error');
      return;
    }
    ensureSlackChannelsLoaded();
    if (
      DEFAULT_SLACK_CHANNELS.includes(channel) ||
      customSlackChannels.includes(channel)
    ) {
      rebuildSlackChannelOptions(channel);
      select.dataset.dirty = 'true';
      select.value = channel;
      showToast(`${channel} selected. Click Save to persist the change.`);
      input.value = '';
      return;
    }
    customSlackChannels.push(channel);
    customSlackChannels = customSlackChannels.filter(
      (value, index, arr) => arr.indexOf(value) === index,
    );
    persistCustomSlackChannels();
    rebuildSlackChannelOptions(channel);
    select.dataset.dirty = 'true';
    select.value = channel;
    input.value = '';
    updateSlackRemoveButtonState();
    showToast(`${channel} added. Click Save to apply the new default channel.`, 'success');
  };

  const handleSlackRemoveChannel = () => {
    const select = elements.slackChannel;
    if (!select) {
      return;
    }
    const channel = normalizeSlackChannelName(select.value);
    if (!channel) {
      showToast('삭제할 채널을 먼저 선택해 주세요.', 'error');
      return;
    }
    ensureSlackChannelsLoaded();
    if (!customSlackChannels.includes(channel)) {
      showToast('기본 채널은 삭제할 수 없습니다.', 'error');
      return;
    }
    customSlackChannels = customSlackChannels.filter(
      (value) => value !== channel,
    );
    persistCustomSlackChannels();
    const fallback =
      customSlackChannels[customSlackChannels.length - 1] ||
      DEFAULT_SLACK_CHANNELS[0];
    const preferred = normalizeSlackChannelName(fallback);
    delete select.dataset.dirty;
    rebuildSlackChannelOptions(preferred || DEFAULT_SLACK_CHANNELS[0]);
    select.dataset.dirty = 'true';
    if (preferred) {
      select.value = preferred;
    }
    updateSlackRemoveButtonState();
    showToast(`${channel} 채널을 삭제했습니다. 저장을 눌러 적용해 주세요.`, 'info');
  };

  const handleSlackSave = async () => {
    const payload = getSlackPayload();
    if (!payload.token) {
      showToast('Slack 토큰을 입력해주세요.', 'error');
      return;
    }
    setBusy(elements.slackSave, true);
    try {
      const result = await request('/slack/save', { method: 'POST', body: payload });
      const message = result && result.message ? result.message : 'Slack 설정을 저장했습니다.';
      showToast(message);
      markPristine(
        elements.slackToken,
        elements.slackWorkspace,
        elements.slackChannel
      );
      await refreshState({ silent: true });
    } catch (error) {
      showToast(error.message || 'Slack 설정 저장에 실패했습니다.', 'error');
    } finally {
      setBusy(elements.slackSave, false);
    }
  };


  const handlePromTest = async () => {
    const payload = getPrometheusTestPayload();
    if (!payload.url || !payload.http_query || !payload.cpu_query) {
      showToast('Prometheus URL과 쿼리를 입력해주세요.', 'error');
      return;
    }
    setBusy(elements.promTest, true);
    try {
      const result = await request('/prometheus/test', { method: 'POST', body: payload });
      const http = result && typeof result.http === 'number' ? formatNumber(result.http) : '--';
      const cpu = result && typeof result.cpu === 'number' ? formatNumber(result.cpu) : '--';
      showToast(`Prometheus 테스트 결과 · HTTP ${http} · CPU ${cpu}`);
    } catch (error) {
      showToast(error.message || 'Prometheus 테스트에 실패했습니다.', 'error');
    } finally {
      setBusy(elements.promTest, false);
    }
  };

  const handlePromSave = async () => {
    const payload = getPrometheusPayload();
    if (!payload.url || !payload.http_query || !payload.cpu_query) {
      showToast('Prometheus URL과 쿼리를 입력해주세요.', 'error');
      return;
    }
    setBusy(elements.promSave, true);
    try {
      const result = await request('/prometheus/save', { method: 'POST', body: payload });
      const message = result && result.message ? result.message : 'Prometheus 설정을 저장했습니다.';
      showToast(message);
      markPristine(
        elements.promUrl,
        elements.promHttpQuery,
        elements.promHttpThreshold,
        elements.promCpuQuery,
        elements.promCpuThreshold
      );
      await refreshState({ silent: true });
    } catch (error) {
      showToast(error.message || 'Prometheus 설정 저장에 실패했습니다.', 'error');
    } finally {
      setBusy(elements.promSave, false);
    }
  };

  const handleAiSave = async () => {
    if (!elements.aiApiKey) {
      return;
    }
    const apiKey = elements.aiApiKey.value.trim();
    setBusy(elements.aiSave, true);
    try {
      await request('/ai/save', {
        method: 'POST',
        body: { api_key: apiKey },
      });
      showToast(apiKey ? 'OpenAI API Key를 저장했습니다.' : 'OpenAI API Key를 초기화했습니다.');
      elements.aiApiKey.value = '';
      delete elements.aiApiKey.dataset.dirty;
      await refreshState({ silent: true });
    } catch (error) {
      showToast(error.message || 'AI 설정 저장에 실패했습니다.', 'error');
    } finally {
      setBusy(elements.aiSave, false);
    }
  };

  const handleModalClose = async () => {
    if (!activeReport) {
      hideModal();
      return;
    }
    setBusy(elements.modalClose, true);
    try {
      await request(`/notifications/pending/${activeReport.id}/ack`, { method: 'POST' });
      showToast('보고서를 확인했습니다.');
      hideModal();
      activeReport = null;
      await refreshState({ silent: true });
    } catch (error) {
      showToast(error.message || '보고서 확인에 실패했습니다.', 'error');
    } finally {
      setBusy(elements.modalClose, false);
    }
  };

  const updateSampleToggleLabel = () => {
    if (!elements.sampleToggle || !elements.sampleContainer) {
      return;
    }
    const isOpen = elements.sampleContainer.dataset.open === 'true';
    elements.sampleToggle.textContent = isOpen ? 'Hide Samples' : 'Show Samples';
    elements.sampleToggle.setAttribute('aria-expanded', String(isOpen));
  };

  const switchTab = (name) => {
    if (!name) {
      return;
    }
    activeTab = name;
    tabs.forEach((tab) => {
      tab.classList.toggle('active', tab.dataset.tab === activeTab);
    });
    tabPanels.forEach((panel) => {
      panel.classList.toggle('active', panel.id === `tab-${activeTab}`);
    });
  };

  const bindEvents = () => {
    tabs.forEach((tab) => {
      tab.addEventListener('click', () => {
        const target = tab.dataset.tab;
        if (target) {
          switchTab(target);
        }
      });
    });

    if (elements.ragRefresh) {
      elements.ragRefresh.addEventListener('click', () => {
        loadRagData({ force: true, resetPage: true });
      });
    }

    if (elements.ragPrevPage) {
      elements.ragPrevPage.addEventListener('click', () => {
        goToRagPage(ragPage - 1);
      });
    }

    if (elements.ragNextPage) {
      elements.ragNextPage.addEventListener('click', () => {
        goToRagPage(ragPage + 1);
      });
    }

    if (elements.systemFeedPrev) {
      elements.systemFeedPrev.addEventListener('click', () => {
        goToFeedPage(feedPage - 1);
      });
    }
    if (elements.systemFeedNext) {
      elements.systemFeedNext.addEventListener('click', () => {
        goToFeedPage(feedPage + 1);
      });
    }

    if (elements.ragFileInput) {
      elements.ragFileInput.addEventListener('change', updateRagUploadState);
    }

    if (elements.ragUploadButton) {
      elements.ragUploadButton.addEventListener('click', handleRagUpload);
    }

    if (elements.emailAddButton) {
      elements.emailAddButton.addEventListener('click', handleEmailAdd);
    }
    if (elements.emailInput) {
      elements.emailInput.addEventListener('input', updateEmailFormState);
    }
    if (elements.emailPrevPage) {
      elements.emailPrevPage.addEventListener('click', () => {
        goToEmailPage(emailPage - 1);
      });
    }
    if (elements.emailNextPage) {
      elements.emailNextPage.addEventListener('click', () => {
        goToEmailPage(emailPage + 1);
      });
    }
    if (elements.emailList) {
      elements.emailList.addEventListener('click', (event) => {
        const target = event.target.closest('.email-entry__delete');
        if (!target) {
          return;
        }
        handleEmailDelete(target.dataset.recipientId);
      });
    }

    if (elements.slackChannel) {
      elements.slackChannel.addEventListener('change', () => {
        updateSlackRemoveButtonState();
      });
    }
    if (elements.slackAddChannel) {
      elements.slackAddChannel.addEventListener('click', handleSlackAddChannel);
    }
    if (elements.slackRemoveChannel) {
      elements.slackRemoveChannel.addEventListener('click', handleSlackRemoveChannel);
    }
    if (elements.slackChannelInput) {
      elements.slackChannelInput.addEventListener('keydown', (event) => {
        if (event.key === 'Enter') {
          event.preventDefault();
          handleSlackAddChannel();
        }
      });
    }

    if (elements.verifyButton) {
      elements.verifyButton.addEventListener('click', handleVerify);
    }

    if (elements.sampleToggle && elements.sampleContainer) {
      elements.sampleToggle.addEventListener('click', () => {
        const isOpen = elements.sampleContainer.dataset.open === 'true';
        elements.sampleContainer.dataset.open = (!isOpen).toString();
        updateSampleToggleLabel();
      });
      updateSampleToggleLabel();
    }

    [elements.notifySlack].forEach((input) => {
      if (input) {
        input.addEventListener('change', handlePreferenceChange);
      }
    });

    const trackDirty = (input) => {
      if (!input) {
        return;
      }
      const markDirty = () => {
        input.dataset.dirty = 'true';
      };
      input.addEventListener('input', markDirty);
      input.addEventListener('change', markDirty);
    };

    [
      elements.slackToken,
      elements.slackWorkspace,
      elements.slackChannel,
      elements.promUrl,
      elements.promHttpQuery,
      elements.promHttpThreshold,
      elements.promCpuQuery,
      elements.promCpuThreshold,
    ].forEach(trackDirty);

    if (elements.slackTest) {
      elements.slackTest.addEventListener('click', handleSlackTest);
    }
    if (elements.slackSave) {
      elements.slackSave.addEventListener('click', handleSlackSave);
    }
    if (elements.promTest) {
      elements.promTest.addEventListener('click', handlePromTest);
    }
    if (elements.promSave) {
      elements.promSave.addEventListener('click', handlePromSave);
    }
    if (elements.aiSave) {
      elements.aiSave.addEventListener('click', handleAiSave);
    }
    if (elements.modalClose) {
      elements.modalClose.addEventListener('click', handleModalClose);
    }
    if (elements.actionModalApprove) {
      elements.actionModalApprove.addEventListener('click', handleActionApprove);
    }
    if (elements.actionModalLater) {
      elements.actionModalLater.addEventListener('click', handleActionLater);
    }

    updateRagUploadState();
    updateRagPaginationControls();
    updateSlackRemoveButtonState();
    updateEmailFormState();
    updateEmailPaginationControls();
  };

  document.addEventListener('DOMContentLoaded', () => {
    bindEvents();
    refreshState();
    pollHandle = setInterval(() => refreshState({ silent: true }), 6000);
  });

  window.addEventListener('beforeunload', () => {
    if (pollHandle) {
      clearInterval(pollHandle);
      pollHandle = null;
    }
  });
})();
