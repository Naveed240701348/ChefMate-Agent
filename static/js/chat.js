/**
 * ChefMate-Agent — Chat Page JavaScript
 *
 * Architecture: Browser → POST /api/chat → Flask → IBM watsonx Orchestrate REST API
 *
 * Pure Fetch API — all AI calls go through the Flask back-end, never directly to IBM.
 * All AI calls go through our own Flask back-end using the Fetch API.
 *
 * Responsibilities
 * ----------------
 *  - Sidebar open / close (desktop + mobile overlay)
 *  - Send user message  →  /api/chat  →  render AI response
 *  - Typing animation during in-flight requests
 *  - Markdown rendering (Marked.js + DOMPurify)
 *  - Auto-scroll to latest message
 *  - Character counter + auto-resize textarea
 *  - Copy-to-clipboard on AI bubbles
 *  - Suggestion chips + ingredient quick-chips
 *  - Voice button (UI only)
 *  - Clear / New Chat  →  POST /api/chat/clear
 *  - Saved Recipes (localStorage)
 *  - Shopping List and Settings modals
 *  - Dark / light theme sync (sidebar toggle)
 */

(function () {
  'use strict';

  /* ═══════════════════════ CONSTANTS ══════════════════════════ */
  const API_CHAT        = '/api/chat';
  const API_CLEAR       = '/api/chat/clear';
  const MAX_CHARS       = 2000;
  const CONV_KEY        = 'cm-conv-id';
  const SAVED_KEY       = 'cm-saved-recipes';

  /* ═══════════════════════ STATE ══════════════════════════════ */
  let conversationId = getOrCreateConvId();
  let isWaiting      = false;

  /* ═══════════════════════ DOM REFERENCES ═════════════════════ */
  const sidebar         = document.getElementById('chatSidebar');
  const sidebarOverlay  = document.getElementById('sidebarOverlay');
  const sidebarToggle   = document.getElementById('sidebarToggle');
  const sidebarClose    = document.getElementById('sidebarClose');
  const newChatBtn      = document.getElementById('newChatBtn');
  const clearChatBtn    = document.getElementById('clearChatBtn');
  const messagesArea    = document.getElementById('messagesArea');
  const messagesList    = document.getElementById('messagesList');
  const welcomeScreen   = document.getElementById('welcomeScreen');
  const typingIndicator = document.getElementById('typingIndicator');
  const messageInput    = document.getElementById('messageInput');
  const sendBtn         = document.getElementById('sendBtn');
  const charCounter     = document.getElementById('charCounter');
  const statusDot       = document.getElementById('statusDot');
  const statusText      = document.getElementById('statusText');
  const suggestionsGrid = document.getElementById('suggestionsGrid');
  const ingredientChips = document.getElementById('ingredientChips');
  const savedLink       = document.getElementById('savedLink');
  const shoppingLink    = document.getElementById('shoppingLink');
  const settingsLink    = document.getElementById('settingsLink');
  const savedCount      = document.getElementById('savedCount');
  const rightPanel      = document.getElementById('rightPanel');
  const rightPanelClose = document.getElementById('rightPanelClose');
  const savedRecipesList= document.getElementById('savedRecipesList');
  const genShoppingBtn  = document.getElementById('generateShoppingListBtn');

  /* ═══════════════════════ BOOT ═══════════════════════════════ */
  document.body.classList.add('chat-page');
  refreshSavedBadge();
  applyUrlPrefill();
  messageInput && messageInput.focus();

  /* ═══════════════════════ CONVERSATION ID ════════════════════ */
  function getOrCreateConvId() {
    let id = sessionStorage.getItem(CONV_KEY);
    if (!id) {
      id = 'conv-' + Date.now() + '-' + Math.random().toString(36).slice(2, 7);
      sessionStorage.setItem(CONV_KEY, id);
    }
    return id;
  }
  function resetConvId() {
    const id = 'conv-' + Date.now() + '-' + Math.random().toString(36).slice(2, 7);
    sessionStorage.setItem(CONV_KEY, id);
    return id;
  }

  /* ═══════════════════════ SIDEBAR ════════════════════════════ */
  function openSidebar()  { sidebar.classList.add('open'); sidebarOverlay.classList.add('visible'); }
  function closeSidebar() { sidebar.classList.remove('open'); sidebarOverlay.classList.remove('visible'); }

  sidebarToggle  && sidebarToggle.addEventListener('click',  function () {
    sidebar.classList.contains('open') ? closeSidebar() : openSidebar();
  });
  sidebarClose   && sidebarClose.addEventListener('click',   closeSidebar);
  sidebarOverlay && sidebarOverlay.addEventListener('click', closeSidebar);

  /* ═══════════════════════ TEXTAREA INPUT ═════════════════════ */
  messageInput && messageInput.addEventListener('input', function () {
    // Auto-resize
    this.style.height = 'auto';
    this.style.height = Math.min(this.scrollHeight, 160) + 'px';

    // Character counter
    const len = this.value.length;
    charCounter.textContent = len + '/' + MAX_CHARS;
    charCounter.classList.toggle('near-limit', len >= MAX_CHARS * 0.8 && len < MAX_CHARS);
    charCounter.classList.toggle('at-limit',   len >= MAX_CHARS);

    // Gate the send button
    sendBtn.disabled = !this.value.trim() || isWaiting;
  });

  messageInput && messageInput.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (!sendBtn.disabled) sendMessage();
    }
  });

  sendBtn && sendBtn.addEventListener('click', sendMessage);

  /* ═══════════════════════ SUGGESTION CHIPS ═══════════════════ */
  suggestionsGrid && suggestionsGrid.addEventListener('click', function (e) {
    const chip = e.target.closest('.cm-suggestion-chip');
    if (!chip) return;
    setInput(chip.dataset.prompt || '');
    sendMessage();
  });

  /* ═══════════════════════ INGREDIENT CHIPS ═══════════════════ */
  ingredientChips && ingredientChips.addEventListener('click', function (e) {
    const chip = e.target.closest('.cm-ing-chip');
    if (!chip) return;
    const cur = messageInput.value.trim();
    setInput(cur ? cur + ', ' + chip.dataset.ingredient : 'Give me a recipe using ' + chip.dataset.ingredient);
    messageInput.focus();
  });

  function setInput(text) {
    messageInput.value = text;
    messageInput.dispatchEvent(new Event('input'));
  }

  /* ═══════════════════════ VOICE BUTTON (UI) ══════════════════ */
  const voiceBtn = document.getElementById('voiceBtn');
  voiceBtn && voiceBtn.addEventListener('click', function () {
    this.classList.toggle('mic-active');
  });

  /* ═══════════════════════ CLEAR / NEW CHAT ═══════════════════ */
  clearChatBtn && clearChatBtn.addEventListener('click', async function () {
    if (!messagesList.children.length) return;
    if (!confirm('Clear this conversation?')) return;
    await callClearApi();
    resetUI();
  });

  newChatBtn && newChatBtn.addEventListener('click', async function () {
    await callClearApi();
    conversationId = resetConvId();
    resetUI();
    closeSidebar();
  });

  async function callClearApi() {
    try {
      await fetch(API_CLEAR, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ conversation_id: conversationId }),
      });
    } catch (_) { /* non-critical — swallow silently */ }
  }

  function resetUI() {
    messagesList.innerHTML = '';
    welcomeScreen.style.display = '';
    setInput('');
    messageInput.style.height = 'auto';
    sendBtn.disabled = true;
    charCounter.textContent = '0/' + MAX_CHARS;
    setStatus('ready');
  }

  /* ═══════════════════════ STATUS DOT ═════════════════════════ */
  function setStatus(state) {
    if (!statusDot || !statusText) return;
    if (state === 'thinking') {
      statusDot.classList.add('thinking');
      statusText.textContent = 'Thinking…';
    } else {
      statusDot.classList.remove('thinking');
      statusText.textContent = 'Ready to cook';
    }
  }

  /* ═══════════════════════ SEND MESSAGE ═══════════════════════ */
  async function sendMessage() {
    const text = messageInput.value.trim();
    if (!text || isWaiting) return;

    isWaiting = true;
    sendBtn.disabled = true;
    setInput('');
    messageInput.style.height = 'auto';
    charCounter.textContent = '0/' + MAX_CHARS;

    appendUserBubble(text);
    showTyping();
    setStatus('thinking');

    try {
      const resp = await fetch(API_CHAT, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ message: text, conversation_id: conversationId }),
      });

      const data = await resp.json();
      hideTyping();

      if (data.success) {
        appendAIBubble(data.response);
      } else {
        appendErrorBubble(data.error || 'Something went wrong. Please try again.');
      }

    } catch (err) {
      hideTyping();
      appendErrorBubble('Network error — could not reach the server. Check your connection.');
      console.error('[ChefMate] fetch error:', err);
    } finally {
      isWaiting = false;
      setStatus('ready');
      sendBtn.disabled = !messageInput.value.trim();
      messageInput.focus();
    }
  }

  /* ═══════════════════════ TYPING INDICATOR ═══════════════════ */
  function showTyping() {
    typingIndicator.style.display = 'flex';
    scrollBottom();
  }
  function hideTyping() {
    typingIndicator.style.display = 'none';
  }

  /* ═══════════════════════ MESSAGE BUILDERS ═══════════════════ */

  function appendUserBubble(text) {
    welcomeScreen.style.display = 'none';
    const row = document.createElement('div');
    row.className = 'cm-message-row user-row';
    row.innerHTML =
      '<div class="cm-msg-avatar user-avatar"><i class="bi bi-person-fill"></i></div>' +
      '<div class="cm-msg-content">' +
        '<div class="cm-bubble user-bubble">' + escHtml(text).replace(/\n/g, '<br>') + '</div>' +
        '<div class="cm-msg-meta"><span>' + formatTime() + '</span></div>' +
      '</div>';
    messagesList.appendChild(row);
    scrollBottom();
  }

  function appendAIBubble(text) {
    const msgId = 'msg-' + Date.now();
    const row   = document.createElement('div');
    row.className = 'cm-message-row ai-row';
    row.innerHTML =
      '<div class="cm-msg-avatar ai-avatar"><i class="bi bi-stars"></i></div>' +
      '<div class="cm-msg-content">' +
        '<div class="cm-bubble ai-bubble" id="' + msgId + '">' + renderMd(text) + '</div>' +
        '<div class="cm-msg-meta">' +
          '<span>' + formatTime() + '</span>' +
          '<button class="cm-msg-copy-btn" data-target="' + msgId + '" title="Copy response">' +
            '<i class="bi bi-clipboard"></i> Copy' +
          '</button>' +
        '</div>' +
      '</div>';
    messagesList.appendChild(row);
    scrollBottom();
  }

  function appendErrorBubble(msg) {
    const row = document.createElement('div');
    row.className = 'cm-message-row ai-row';
    row.innerHTML =
      '<div class="cm-msg-avatar ai-avatar" style="background:#EF4444">' +
        '<i class="bi bi-exclamation-triangle-fill"></i>' +
      '</div>' +
      '<div class="cm-msg-content">' +
        '<div class="cm-bubble error-bubble">' +
          '<i class="bi bi-exclamation-triangle me-2"></i>' + escHtml(msg) +
        '</div>' +
        '<div class="cm-msg-meta"><span>' + formatTime() + '</span></div>' +
      '</div>';
    messagesList.appendChild(row);
    scrollBottom();
  }

  /* ═══════════════════════ COPY BUTTON ════════════════════════ */
  messagesList && messagesList.addEventListener('click', function (e) {
    const btn = e.target.closest('.cm-msg-copy-btn');
    if (!btn) return;
    const bubble = document.getElementById(btn.dataset.target);
    if (!bubble) return;
    const copyText = bubble.innerText || bubble.textContent || '';

    navigator.clipboard.writeText(copyText).then(function () {
      btn.innerHTML = '<i class="bi bi-check2"></i> Copied!';
      btn.classList.add('copied');
      setTimeout(function () {
        btn.innerHTML = '<i class="bi bi-clipboard"></i> Copy';
        btn.classList.remove('copied');
      }, 2000);
    }).catch(function () {
      // Fallback for non-secure contexts
      const ta = document.createElement('textarea');
      ta.value = copyText;
      document.body.appendChild(ta);
      ta.select();
      try { document.execCommand('copy'); } catch (_) {}
      document.body.removeChild(ta);
    });
  });

  /* ═══════════════════════ AUTO-SCROLL ════════════════════════ */
  function scrollBottom() {
    requestAnimationFrame(function () {
      messagesArea.scrollTop = messagesArea.scrollHeight;
    });
  }

  /* ═══════════════════════ SAVED RECIPES ══════════════════════ */
  function loadSaved()        { try { return JSON.parse(localStorage.getItem(SAVED_KEY) || '[]'); } catch(_){ return []; } }
  function persistSaved(arr)  { localStorage.setItem(SAVED_KEY, JSON.stringify(arr)); }
  function refreshSavedBadge(){ if (savedCount) savedCount.textContent = loadSaved().length; }

  window.chefmateSaveRecipe = function (name, cuisine) {
    const arr = loadSaved();
    if (!arr.some(function(r){ return r.name === name; })) {
      arr.push({ name: name, cuisine: cuisine || '', savedAt: new Date().toISOString() });
      persistSaved(arr);
      refreshSavedBadge();
    }
  };

  function renderSavedPanel() {
    if (!savedRecipesList) return;
    const arr = loadSaved();
    if (!arr.length) {
      savedRecipesList.innerHTML =
        '<div class="cm-empty-panel">' +
        '<i class="bi bi-heart fs-1 text-muted"></i>' +
        '<p class="mt-2 text-muted small">No saved recipes yet.</p>' +
        '</div>';
      return;
    }
    savedRecipesList.innerHTML = arr.map(function(r, i) {
      return '<div class="cm-saved-recipe-item border rounded-3 p-2 mb-2 position-relative">' +
        '<div class="fw-600 small">' + escHtml(r.name) + '</div>' +
        '<div class="text-muted" style="font-size:.75rem">' + escHtml(r.cuisine || '') + '</div>' +
        '<button class="btn btn-link btn-sm text-danger p-0 cm-del-saved" data-idx="' + i + '"' +
        ' style="position:absolute;top:.5rem;right:.5rem"><i class="bi bi-trash3"></i></button>' +
        '</div>';
    }).join('');
    savedRecipesList.querySelectorAll('.cm-del-saved').forEach(function(btn) {
      btn.addEventListener('click', function() {
        const arr2 = loadSaved();
        arr2.splice(parseInt(this.dataset.idx), 1);
        persistSaved(arr2);
        refreshSavedBadge();
        renderSavedPanel();
      });
    });
  }

  savedLink && savedLink.addEventListener('click', function(e) {
    e.preventDefault();
    renderSavedPanel();
    if (rightPanel) {
      const showing = rightPanel.style.display !== 'none' && rightPanel.style.display !== '';
      rightPanel.style.display   = showing ? 'none' : 'flex';
      rightPanel.style.flexDirection = 'column';
    }
    closeSidebar();
  });
  rightPanelClose && rightPanelClose.addEventListener('click', function() {
    if (rightPanel) rightPanel.style.display = 'none';
  });

  /* ═══════════════════════ MODAL LINKS ════════════════════════ */
  shoppingLink && shoppingLink.addEventListener('click', function(e) {
    e.preventDefault();
    new bootstrap.Modal(document.getElementById('shoppingModal')).show();
    closeSidebar();
  });
  settingsLink && settingsLink.addEventListener('click', function(e) {
    e.preventDefault();
    new bootstrap.Modal(document.getElementById('settingsModal')).show();
    closeSidebar();
  });

  /* Shopping list — ask AI to generate one */
  genShoppingBtn && genShoppingBtn.addEventListener('click', function() {
    const modal = bootstrap.Modal.getInstance(document.getElementById('shoppingModal'));
    if (modal) modal.hide();
    setInput('Generate a detailed shopping list for a week of healthy balanced meals');
    sendMessage();
  });

  /* Settings nutrition toggle */
  const nutritionToggle = document.getElementById('nutritionToggle');
  nutritionToggle && nutritionToggle.addEventListener('click', function() {
    this.classList.toggle('active');
  });

  /* ═══════════════════════ URL PREFILL ════════════════════════ */
  function applyUrlPrefill() {
    const q = new URLSearchParams(window.location.search).get('q');
    if (q) {
      history.replaceState(null, '', window.location.pathname);
      setInput(decodeURIComponent(q));
      setTimeout(sendMessage, 400);
    }
  }

  /* ═══════════════════════ UTILITIES ══════════════════════════ */

  function escHtml(str) {
    return String(str)
      .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }

  function renderMd(text) {
    if (typeof marked === 'undefined') return escHtml(text).replace(/\n/g,'<br>');
    try {
      const html = marked.parse(String(text), { breaks: true, gfm: true });
      return typeof DOMPurify !== 'undefined' ? DOMPurify.sanitize(html) : html;
    } catch(_) {
      return escHtml(text).replace(/\n/g,'<br>');
    }
  }

  function formatTime() {
    return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }

})();
