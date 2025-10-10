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
    httpMetric: $('#httpMetric'),
    cpuMetric: $('#cpuMetric'),
    alertList: $('#alertList'),
    systemFeed: $('#systemFeed'),
    notifySlack: $('#notifySlack'),
    notifyJira: $('#notifyJira'),
    slackToken: $('#slackToken'),
    slackWorkspace: $('#slackWorkspace'),
    slackChannel: $('#slackChannel'),
    slackTest: $('#slackTest'),
    slackSave: $('#slackSave'),
    jiraSite: $('#jiraSite'),
    jiraProject: $('#jiraProject'),
    jiraEmail: $('#jiraEmail'),
    jiraToken: $('#jiraToken'),
    jiraTest: $('#jiraTest'),
    jiraSave: $('#jiraSave'),
    jiraCreate: $('#jiraCreate'),
    promUrl: $('#promUrl'),
    promHttpQuery: $('#promHttpQuery'),
    promHttpThreshold: $('#promHttpThreshold'),
    promCpuQuery: $('#promCpuQuery'),
    promCpuThreshold: $('#promCpuThreshold'),
    promTest: $('#promTest'),
    promSave: $('#promSave'),
    toast: $('#toast'),
    analysisContent: $('#analysisContent'),
    modal: $('#reportModal'),
    modalTitle: $('#modalTitle'),
    modalTimestamp: $('#modalTimestamp'),
    modalStatus: $('#modalStatus'),
    modalReport: $('#modalReport'),
    modalHint: $('#modalHint'),
    modalClose: $('#modalClose'),
  };

  const tabs = $$('.tab');
  const tabPanels = $$('.tab-content');

  let pollHandle = null;
  let isRefreshing = false;
  let pendingRefresh = false;
  let applyingPreferences = false;
  let preferenceTimer = null;
  let lastSavedPreferences = { slack: true, jira: true };
  let activeReport = null;
  let toastTimer = null;

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
      init.body = typeof body === 'string' ? body : JSON.stringify(body);
      if (!init.headers['Content-Type']) {
        init.headers['Content-Type'] = 'application/json';
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

  const renderState = (state = {}) => {
    if (!state || typeof state !== 'object') {
      return;
    }
    renderPreferences(state.preferences);
    renderSlack(state.slack);
    renderJira(state.jira);
    renderPrometheus(state.prometheus);
    renderMetrics(state.monitor, state.prometheus);
    renderSamples(state.monitor);
    renderAlerts(state.alert_history);
    renderFeed(state.feed);
    renderAnalysis(state);
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
    if (elements.notifyJira) {
      elements.notifyJira.checked = Boolean(preferences.jira);
      delete elements.notifyJira.dataset.dirty;
    }
    applyingPreferences = false;
    lastSavedPreferences = {
      slack: Boolean(preferences.slack),
      jira: Boolean(preferences.jira),
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

  const renderSlack = (settings = {}) => {
    updateInputValue(elements.slackToken, settings.token || '');
    updateInputValue(elements.slackWorkspace, settings.workspace || '');
    if (elements.slackChannel) {
      updateInputValue(elements.slackChannel, settings.channel || '#ops-incident');
    }
  };

  const renderJira = (settings = {}) => {
    updateInputValue(elements.jiraSite, settings.site || '');
    updateInputValue(elements.jiraProject, settings.project || '');
    updateInputValue(elements.jiraEmail, settings.email || '');
    updateInputValue(elements.jiraToken, settings.token || '');
  };

  const renderPrometheus = (settings = {}) => {
    updateInputValue(elements.promUrl, settings.url || '');
    updateInputValue(elements.promHttpQuery, settings.http_query || '');
    updateInputValue(elements.promHttpThreshold, settings.http_threshold || '0.05');
    updateInputValue(elements.promCpuQuery, settings.cpu_query || '');
    updateInputValue(elements.promCpuThreshold, settings.cpu_threshold || '0.80');
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
        item.textContent = `${formatDate(sample.timestamp)} · HTTP ${formatNumber(
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

  const renderFeed = (feed) => {
    const container = elements.systemFeed;
    if (!container) {
      return;
    }
    container.innerHTML = '';
    const entries = Array.isArray(feed) ? feed.slice() : [];
    if (!entries.length) {
      container.textContent = '시스템 피드가 비어 있습니다.';
      return;
    }
    entries
      .slice()
      .reverse()
      .slice(0, 40)
      .forEach((entry) => {
        const block = document.createElement('div');
        block.className = 'feed-entry';
        block.textContent = entry;
        container.appendChild(block);
      });
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
    channel: elements.slackChannel ? elements.slackChannel.value.trim() || '#ops-incident' : '#ops-incident',
  });

  const getJiraPayload = () => ({
    site: elements.jiraSite ? elements.jiraSite.value.trim() : '',
    project: elements.jiraProject ? elements.jiraProject.value.trim() : '',
    email: elements.jiraEmail ? elements.jiraEmail.value.trim() : '',
    token: elements.jiraToken ? elements.jiraToken.value.trim() : '',
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
      jira: Boolean(elements.notifyJira && elements.notifyJira.checked),
    };
    if (
      payload.slack === lastSavedPreferences.slack &&
      payload.jira === lastSavedPreferences.jira
    ) {
      return;
    }
    try {
      await request('/notifications/preferences', { method: 'POST', body: payload });
      lastSavedPreferences = { ...payload };
      markPristine(elements.notifySlack, elements.notifyJira);
      showToast('알림 대상을 업데이트했습니다.');
    } catch (error) {
      showToast(error.message || '알림 대상 업데이트에 실패했습니다.', 'error');
      applyingPreferences = true;
      if (elements.notifySlack) {
        elements.notifySlack.checked = lastSavedPreferences.slack;
        delete elements.notifySlack.dataset.dirty;
      }
      if (elements.notifyJira) {
        elements.notifyJira.checked = lastSavedPreferences.jira;
        delete elements.notifyJira.dataset.dirty;
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

  const handleJiraTest = async () => {
    const payload = getJiraPayload();
    if (!payload.site || !payload.project || !payload.email || !payload.token) {
      showToast('Jira 사이트 URL과 프로젝트, 이메일, 토큰을 입력해주세요.', 'error');
      return;
    }
    setBusy(elements.jiraTest, true);
    try {
      const result = await request('/jira/test', { method: 'POST', body: payload });
      const name = result && (result.name || result.key || payload.project);
      showToast(name ? `Jira 연결 확인 완료 (${name})` : 'Jira 연결 확인 완료');
    } catch (error) {
      showToast(error.message || 'Jira 테스트에 실패했습니다.', 'error');
    } finally {
      setBusy(elements.jiraTest, false);
    }
  };

  const handleJiraSave = async () => {
    const payload = getJiraPayload();
    if (!payload.site || !payload.project || !payload.email || !payload.token) {
      showToast('Jira 설정을 모두 입력해주세요.', 'error');
      return;
    }
    setBusy(elements.jiraSave, true);
    try {
      const result = await request('/jira/save', { method: 'POST', body: payload });
      const message = result && result.message ? result.message : 'Jira 설정을 저장했습니다.';
      showToast(message);
      markPristine(
        elements.jiraSite,
        elements.jiraProject,
        elements.jiraEmail,
        elements.jiraToken
      );
      await refreshState({ silent: true });
    } catch (error) {
      showToast(error.message || 'Jira 설정 저장에 실패했습니다.', 'error');
    } finally {
      setBusy(elements.jiraSave, false);
    }
  };

  const handleJiraCreate = async () => {
    setBusy(elements.jiraCreate, true);
    try {
      const result = await request('/jira/create', { method: 'POST' });
      const key = result && result.key ? result.key : 'Jira 이슈';
      showToast(`Jira 이슈를 생성했습니다: ${key}`);
      await refreshState({ silent: true });
    } catch (error) {
      showToast(error.message || 'Jira 이슈 생성에 실패했습니다.', 'error');
    } finally {
      setBusy(elements.jiraCreate, false);
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
    elements.sampleToggle.textContent = isOpen ? '샘플 이력 숨기기' : '샘플 이력 보기';
    elements.sampleToggle.setAttribute('aria-expanded', String(isOpen));
  };

  const switchTab = (name) => {
    tabs.forEach((tab) => {
      tab.classList.toggle('active', tab.dataset.tab === name);
    });
    tabPanels.forEach((panel) => {
      panel.classList.toggle('active', panel.id === `tab-${name}`);
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

    [elements.notifySlack, elements.notifyJira].forEach((input) => {
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
      elements.jiraSite,
      elements.jiraProject,
      elements.jiraEmail,
      elements.jiraToken,
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
    if (elements.jiraTest) {
      elements.jiraTest.addEventListener('click', handleJiraTest);
    }
    if (elements.jiraSave) {
      elements.jiraSave.addEventListener('click', handleJiraSave);
    }
    if (elements.jiraCreate) {
      elements.jiraCreate.addEventListener('click', handleJiraCreate);
    }
    if (elements.promTest) {
      elements.promTest.addEventListener('click', handlePromTest);
    }
    if (elements.promSave) {
      elements.promSave.addEventListener('click', handlePromSave);
    }
    if (elements.modalClose) {
      elements.modalClose.addEventListener('click', handleModalClose);
    }
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
