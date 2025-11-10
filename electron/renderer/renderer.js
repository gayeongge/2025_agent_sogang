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
    slackToken: $('#slackToken'),
    slackWorkspace: $('#slackWorkspace'),
    slackChannel: $('#slackChannel'),
    slackTest: $('#slackTest'),
    slackSave: $('#slackSave'),
    promUrl: $('#promUrl'),
    promHttpQuery: $('#promHttpQuery'),
    promHttpThreshold: $('#promHttpThreshold'),
    promCpuQuery: $('#promCpuQuery'),
    promCpuThreshold: $('#promCpuThreshold'),
    promTest: $('#promTest'),
    promSave: $('#promSave'),
    ragRefresh: $('#ragRefresh'),
    ragStatus: $('#ragStatus'),
    ragTable: $('#ragTable'),
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
  let activeActionExecution = null;
  let activeTab = 'slack';
  let ragLoaded = false;
  let ragLoading = false;

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
      if (activeTab === 'rag') {
        await loadRagData({ force: true, silent: true });
      } else {
        ragLoaded = false;
      }
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
    renderPrometheus(state.prometheus);
    renderMetrics(state.monitor, state.prometheus);
    renderSamples(state.monitor);
    renderAlerts(state.alert_history);
    renderFeed(state.feed);
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

  const renderSlack = (settings = {}) => {
    updateInputValue(elements.slackToken, settings.token || '');
    updateInputValue(elements.slackWorkspace, settings.workspace || '');
    if (elements.slackChannel) {
      updateInputValue(elements.slackChannel, settings.channel || '#ops-incident');
    }
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

  const renderRagDocuments = (documents = []) => {
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
    if (!Array.isArray(documents) || !documents.length) {
      statusEl.textContent = 'No RAG records found.';
      table.classList.add('hidden');
      return;
    }
    statusEl.textContent = `${documents.length} RAG record(s) available.`;
    documents.forEach((doc) => {
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

      const createdCell = document.createElement('td');
      createdCell.textContent = createdAt || '--';
      row.appendChild(createdCell);

      const summaryCell = document.createElement('td');
      summaryCell.textContent = summary || '--';
      row.appendChild(summaryCell);

      body.appendChild(row);
    });
    table.classList.remove('hidden');
  };

  const loadRagData = async ({ force = false, silent = false } = {}) => {
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
    channel: elements.slackChannel ? elements.slackChannel.value.trim() || '#ops-incident' : '#ops-incident',
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
    if (activeTab === 'rag') {
      loadRagData();
    }
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
        loadRagData({ force: true });
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
    if (elements.modalClose) {
      elements.modalClose.addEventListener('click', handleModalClose);
    }
    if (elements.actionModalApprove) {
      elements.actionModalApprove.addEventListener('click', handleActionApprove);
    }
    if (elements.actionModalLater) {
      elements.actionModalLater.addEventListener('click', handleActionLater);
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
