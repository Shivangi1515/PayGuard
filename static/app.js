/**
 * PayGuard - The AI Agent That Pays Within Your Intent
 * Autonomous Agentic Commerce Frontend Application
 */

class PayGuardApp {
  constructor() {
    this.apiBase = window.location.origin;
    this.currentContract = null;
    this.currentProposal = null;
    this.currentVerification = null;
    this.currentTransaction = null;
    this.isProcessing = false;

    this.dom = {
      initialWorkspace: document.getElementById('initial-workspace'),
      heroInput: document.getElementById('hero-input'),
      heroSendBtn: document.getElementById('hero-send-btn'),
      
      chatContainer: document.getElementById('chat-container'),
      chatStream: document.getElementById('chat-stream'),
      bottomBarContainer: document.getElementById('bottom-bar-container'),
      chatInput: document.getElementById('chat-input'),
      sendBtn: document.getElementById('send-btn'),
      
      // Drawers & Modals
      activityDrawer: document.getElementById('activity-drawer'),
      activityDrawerContent: document.getElementById('activity-drawer-content'),
      auditDrawer: document.getElementById('audit-drawer'),
      auditTimeline: document.getElementById('audit-timeline'),
      policiesModal: document.getElementById('policies-modal'),
      policiesContent: document.getElementById('policies-content'),
      
      // Navigation
      navBrandBtn: document.getElementById('nav-brand-btn'),
      navNewSessionBtn: document.getElementById('nav-new-session-btn'),
      openActivityBtn: document.getElementById('nav-activity-btn'),
      openAuditBtn: document.getElementById('nav-audit-btn'),
      openPoliciesBtn: document.getElementById('nav-policies-btn'),
      closeActivityBtn: document.getElementById('close-activity-btn'),
      closeAuditBtn: document.getElementById('close-audit-btn'),
      closePoliciesBtn: document.getElementById('close-policies-btn'),
    };

    this.init();
  }

  init() {
    this.bindEvents();
    this.checkHealth();
  }

  bindEvents() {
    // Hero Command Input
    this.dom.heroSendBtn?.addEventListener('click', () => {
      const text = this.dom.heroInput?.value.trim();
      if (text) this.handleUserSubmit(text);
    });

    this.dom.heroInput?.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        const text = this.dom.heroInput?.value.trim();
        if (text) this.handleUserSubmit(text);
      }
    });

    // Auto-resize hero textarea
    this.dom.heroInput?.addEventListener('input', () => {
      if (this.dom.heroInput) {
        this.dom.heroInput.style.height = 'auto';
        this.dom.heroInput.style.height = `${Math.min(this.dom.heroInput.scrollHeight, 180)}px`;
      }
    });

    // Bottom Bar Input (in active conversation)
    this.dom.sendBtn?.addEventListener('click', () => {
      const text = this.dom.chatInput?.value.trim();
      if (text) this.handleUserSubmit(text);
    });

    this.dom.chatInput?.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        const text = this.dom.chatInput?.value.trim();
        if (text) this.handleUserSubmit(text);
      }
    });

    // Navigation and Drawers
    this.dom.navBrandBtn?.addEventListener('click', () => this.resetConversation());
    this.dom.navNewSessionBtn?.addEventListener('click', () => this.resetConversation());

    this.dom.openActivityBtn?.addEventListener('click', () => this.openActivityDrawer());
    this.dom.closeActivityBtn?.addEventListener('click', () => this.closeActivityDrawer());

    this.dom.openAuditBtn?.addEventListener('click', () => this.openAuditDrawer());
    this.dom.closeAuditBtn?.addEventListener('click', () => this.closeAuditDrawer());

    this.dom.openPoliciesBtn?.addEventListener('click', () => this.openPoliciesModal());
    this.dom.closePoliciesBtn?.addEventListener('click', () => this.closePoliciesModal());
  }

  async checkHealth() {
    try {
      const res = await fetch(`${this.apiBase}/health`);
      const data = await res.json();
      const statusEl = document.getElementById('agent-status-indicator');
      if (statusEl && data.status === 'ok') {
        statusEl.innerHTML = `
          <span class="w-2 h-2 rounded-full bg-[#5FAF79] agent-pulse inline-block mr-1.5"></span>
          <span class="text-xs text-[#98978F] font-mono-code uppercase tracking-wider">Agent Online</span>
        `;
      }
    } catch (err) {
      console.warn('Backend health check warning:', err);
    }
  }

  resetConversation() {
    this.currentContract = null;
    this.currentProposal = null;
    this.currentVerification = null;
    this.currentTransaction = null;
    this.isProcessing = false;

    if (this.dom.chatStream) this.dom.chatStream.innerHTML = '';
    if (this.dom.initialWorkspace) this.dom.initialWorkspace.classList.remove('hidden');
    if (this.dom.chatContainer) this.dom.chatContainer.classList.add('hidden');
    if (this.dom.bottomBarContainer) this.dom.bottomBarContainer.classList.add('hidden');
    
    if (this.dom.heroInput) {
      this.dom.heroInput.value = '';
      this.dom.heroInput.style.height = 'auto';
    }
    if (this.dom.chatInput) this.dom.chatInput.value = '';
    
    this.updateProcessingState(false);
  }

  updateProcessingState(isBusy) {
    this.isProcessing = isBusy;
    
    // Update Hero Send Button
    if (this.dom.heroSendBtn) {
      this.dom.heroSendBtn.disabled = isBusy;
      this.dom.heroSendBtn.innerHTML = isBusy
        ? `
          <svg class="spin-active w-3.5 h-3.5 text-[#080908]" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
          </svg>
          <span>PROCESSING</span>
        `
        : `
          <span>EXECUTE</span>
          <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14 5l7 7m0 0l-7 7m7-7H3"/>
          </svg>
        `;
    }

    // Update Bottom Bar Send Button
    if (this.dom.sendBtn) {
      this.dom.sendBtn.disabled = isBusy;
      this.dom.sendBtn.innerHTML = isBusy
        ? `
          <svg class="spin-active w-3.5 h-3.5 text-[#080908]" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
          </svg>
        `
        : `
          <span>EXECUTE</span>
          <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14 5l7 7m0 0l-7 7m7-7H3"/>
          </svg>
        `;
    }
  }

  scrollToBottom() {
    window.scrollTo({
      top: document.body.scrollHeight,
      behavior: 'smooth',
    });
  }

  async handleUserSubmit(rawText) {
    if (this.isProcessing || !rawText) return;

    // Transition from initial workspace to active stream
    if (this.dom.initialWorkspace) this.dom.initialWorkspace.classList.add('hidden');
    if (this.dom.chatContainer) this.dom.chatContainer.classList.remove('hidden');
    if (this.dom.bottomBarContainer) this.dom.bottomBarContainer.classList.remove('hidden');

    if (this.dom.heroInput) this.dom.heroInput.value = '';
    if (this.dom.chatInput) this.dom.chatInput.value = '';

    // Append User message card
    this.appendUserMessage(rawText);
    this.updateProcessingState(true);

    const pipelineId = `pipeline-${Date.now()}`;
    const agentMsgEl = this.createAgentMessageContainer(pipelineId);
    this.scrollToBottom();

    try {
      // Step 1: Intent Extraction Agent
      this.updatePipelineStep(pipelineId, 'intent', 'active', 'Analyzing purchase requirements...');
      const intentContract = await this.callIntentAgent(rawText);
      this.currentContract = intentContract;
      this.updatePipelineStep(pipelineId, 'intent', 'done', 'Intent Extracted & Locked');

      // Render Intent Locked Card
      this.appendIntentContractCard(agentMsgEl, intentContract);

      // Step 2: Buyer Agent Candidate Search
      this.updatePipelineStep(pipelineId, 'buyer', 'active', 'Evaluating merchant catalog...');
      const proposal = await this.callBuyerAgent(intentContract.intent_contract_id);
      this.currentProposal = proposal;
      this.updatePipelineStep(pipelineId, 'buyer', 'done', `Product Selected (${proposal.attempts_count} attempt${proposal.attempts_count > 1 ? 's' : ''})`);

      // Check Intent Drift / Mismatch
      if (proposal.drift_detected) {
        this.appendIntentMismatchCard(agentMsgEl, intentContract, proposal);
        this.updateProcessingState(false);
        return;
      }

      // Render Proposal Card
      this.appendProposalCard(agentMsgEl, proposal);

      // Step 3: Verification Agent Checks
      this.updatePipelineStep(pipelineId, 'verify', 'active', 'Running 5-point verification...');
      const verification = await this.callVerificationAgent(
        intentContract.intent_contract_id,
        proposal.product_id,
        proposal.quantity
      );
      this.currentVerification = verification;
      this.updatePipelineStep(pipelineId, 'verify', 'done', 'Verification Complete');

      // Step 4: Deterministic Policy Engine
      this.updatePipelineStep(pipelineId, 'policy', 'active', 'Evaluating merchant spending caps...');
      this.updatePipelineStep(pipelineId, 'policy', 'done', `Policy Decision: ${verification.decision}`);

      // Render Policy Decision Block
      this.appendPolicyDecisionBlock(agentMsgEl, intentContract, proposal, verification);

    } catch (err) {
      console.error('Execution error:', err);
      this.appendErrorBlock(agentMsgEl, err.message || 'An error occurred during agent processing.');
    } finally {
      this.updateProcessingState(false);
      this.scrollToBottom();
    }
  }

  // --- Backend API Calls ---

  async callIntentAgent(userPrompt) {
    const res = await fetch(`${this.apiBase}/agent/intent`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ request: userPrompt }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to extract purchase intent.');
    }
    return await res.json();
  }

  async callBuyerAgent(intentContractId) {
    const res = await fetch(`${this.apiBase}/agent/buy`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ intent_contract_id: intentContractId }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to generate purchase proposal.');
    }
    return await res.json();
  }

  async callVerificationAgent(intentContractId, productId, quantity) {
    const res = await fetch(`${this.apiBase}/agent/verify`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        intent_contract_id: intentContractId,
        product_id: productId,
        quantity: quantity,
      }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to verify purchase proposal.');
    }
    return await res.json();
  }

  async callCreatePayment(intentContractId, productId, quantity, userConfirmed = false) {
    const res = await fetch(`${this.apiBase}/agent/payment/create`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        intent_contract_id: intentContractId,
        product_id: productId,
        quantity: quantity,
        user_confirmed: userConfirmed,
      }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to create payment order.');
    }
    return await res.json();
  }

  async callVerifyPaymentSignature(transactionId, orderId, paymentId, signature) {
    const res = await fetch(`${this.apiBase}/agent/payment/verify`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        transaction_id: transactionId,
        razorpay_order_id: orderId,
        razorpay_payment_id: paymentId,
        razorpay_signature: signature,
      }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Signature verification failed.');
    }
    return await res.json();
  }

  // --- Dynamic UI Component Renderers ---

  appendUserMessage(text) {
    const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const userHtml = `
      <div class="flex justify-end mb-8 animate-fade-in-up">
        <div class="max-w-xl w-full">
          <div class="flex items-center justify-end space-x-2 mb-1.5">
            <span class="text-[10px] font-mono-code text-[#98978F] uppercase">Authorized Request</span>
            <span class="text-[10px] font-mono-code text-[#64635D]">${timeStr}</span>
          </div>
          <div class="bg-[#121311] border border-[#20221F] rounded-2xl px-5 py-3.5 text-[#F4F1E8] shadow-sm text-sm sm:text-base leading-relaxed">
            ${this.escapeHtml(text)}
          </div>
        </div>
      </div>
    `;
    this.dom.chatStream?.insertAdjacentHTML('beforeend', userHtml);
  }

  createAgentMessageContainer(pipelineId) {
    const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const containerId = `agent-msg-${Date.now()}`;
    const agentHtml = `
      <div id="${containerId}" class="flex flex-col mb-12 animate-fade-in-up">
        <div class="flex items-center space-x-2.5 mb-2.5">
          <div class="w-6 h-6 rounded bg-[#121311] border border-[#D6A94A]/40 flex items-center justify-center">
            <span class="font-brand text-[10px] text-[#D6A94A] font-bold">PG</span>
          </div>
          <span class="text-xs font-semibold text-[#F4F1E8] tracking-wide">PayGuard Autonomous Buyer</span>
          <span class="text-[10px] font-mono-code text-[#64635D]">${timeStr}</span>
        </div>

        <div class="space-y-4 max-w-3xl">
          <div class="text-xs sm:text-sm text-[#98978F] leading-relaxed">
            Got it. I'll find the best match while staying within your requirements.
          </div>

          <!-- Embedded Real-Time Activity Pipeline -->
          <div id="${pipelineId}" class="card-base rounded-xl p-4 bg-[#0D0E0D]">
            <div class="text-[11px] font-mono-code text-[#98978F] uppercase tracking-wider mb-3 flex items-center justify-between">
              <span>Agent Execution Pipeline</span>
              <span class="text-[10px] text-[#1688D4] flex items-center">
                <span class="w-1.5 h-1.5 rounded-full bg-[#1688D4] animate-ping mr-1"></span> Live
              </span>
            </div>

            <div class="space-y-2 text-xs">
              <div id="${pipelineId}-intent" class="flex items-center justify-between py-1 border-b border-[#20221F]/60">
                <div class="flex items-center space-x-2">
                  <span class="font-mono-code text-[11px] text-[#D6A94A]">INTENT AGENT</span>
                  <span class="text-[#98978F] text-step-desc">Understanding purchase request</span>
                </div>
                <span class="step-status text-[#64635D] font-mono-code">○</span>
              </div>

              <div id="${pipelineId}-buyer" class="flex items-center justify-between py-1 border-b border-[#20221F]/60">
                <div class="flex items-center space-x-2">
                  <span class="font-mono-code text-[11px] text-[#D6A94A]">BUYER AGENT</span>
                  <span class="text-[#98978F] text-step-desc">Searching merchant catalog</span>
                </div>
                <span class="step-status text-[#64635D] font-mono-code">○</span>
              </div>

              <div id="${pipelineId}-verify" class="flex items-center justify-between py-1 border-b border-[#20221F]/60">
                <div class="flex items-center space-x-2">
                  <span class="font-mono-code text-[11px] text-[#D6A94A]">VERIFICATION AGENT</span>
                  <span class="text-[#98978F] text-step-desc">Checking product requirements</span>
                </div>
                <span class="step-status text-[#64635D] font-mono-code">○</span>
              </div>

              <div id="${pipelineId}-policy" class="flex items-center justify-between py-1 border-b border-[#20221F]/60">
                <div class="flex items-center space-x-2">
                  <span class="font-mono-code text-[11px] text-[#D6A94A]">POLICY ENGINE</span>
                  <span class="text-[#98978F] text-step-desc">Evaluating purchase policy</span>
                </div>
                <span class="step-status text-[#64635D] font-mono-code">○</span>
              </div>

              <div id="${pipelineId}-payment" class="flex items-center justify-between py-1">
                <div class="flex items-center space-x-2">
                  <span class="font-mono-code text-[11px] text-[#D6A94A]">PAYMENT AGENT</span>
                  <span class="text-[#98978F] text-step-desc">Waiting for approval</span>
                </div>
                <span class="step-status text-[#64635D] font-mono-code">○</span>
              </div>
            </div>
          </div>

          <!-- Card Slot for Downstream Components -->
          <div class="card-slot space-y-4"></div>
        </div>
      </div>
    `;

    this.dom.chatStream?.insertAdjacentHTML('beforeend', agentHtml);
    return document.getElementById(containerId);
  }

  updatePipelineStep(pipelineId, stepName, state, textDesc) {
    const el = document.getElementById(`${pipelineId}-${stepName}`);
    if (!el) return;

    const descEl = el.querySelector('.text-step-desc');
    const statusEl = el.querySelector('.step-status');

    if (descEl && textDesc) descEl.innerText = textDesc;

    if (state === 'active') {
      statusEl.innerHTML = `
        <svg class="spin-active w-3.5 h-3.5 text-[#1688D4] inline" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
        </svg>
      `;
      el.classList.add('bg-[#1688D4]/5');
    } else if (state === 'done') {
      statusEl.innerHTML = `<span class="text-[#5FAF79] font-bold">✓</span>`;
      el.classList.remove('bg-[#1688D4]/5');
    }
  }

  appendIntentContractCard(containerEl, intent) {
    const slot = containerEl.querySelector('.card-slot');
    if (!slot) return;

    const formattedBudget = new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 0,
    }).format(intent.max_budget);

    const cardHtml = `
      <div class="card-base rounded-xl p-5 border-l-2 border-l-[#D6A94A] bg-[#0D0E0D] animate-fade-in-up">
        <div class="flex items-center justify-between mb-4 pb-2.5 border-b border-[#20221F]">
          <span class="text-[10px] font-mono-code uppercase px-2 py-0.5 rounded bg-[#D6A94A]/10 text-[#D6A94A] border border-[#D6A94A]/25">
            Authorized Purchase Contract
          </span>
          <div class="flex items-center space-x-1 text-[#5FAF79] text-xs font-mono-code">
            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"/>
            </svg>
            <span class="text-[11px] font-semibold uppercase tracking-wider">Intent Locked</span>
          </div>
        </div>

        <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
          <div>
            <div class="text-[10px] font-mono-code text-[#64635D] uppercase mb-0.5">Product Type</div>
            <div class="font-medium text-[#F4F1E8]">${this.escapeHtml(intent.product_type)}</div>
          </div>
          <div>
            <div class="text-[10px] font-mono-code text-[#64635D] uppercase mb-0.5">Purpose</div>
            <div class="font-medium text-[#F4F1E8] capitalize">${this.escapeHtml(intent.purpose || 'General')}</div>
          </div>
          <div>
            <div class="text-[10px] font-mono-code text-[#64635D] uppercase mb-0.5">Authorized Budget</div>
            <div class="font-mono-code font-semibold text-[#D6A94A]">${formattedBudget} MAX</div>
          </div>
          <div>
            <div class="text-[10px] font-mono-code text-[#64635D] uppercase mb-0.5">Quantity / Auth</div>
            <div class="font-medium text-[#F4F1E8]">${intent.quantity} unit · ${intent.payment_authorized ? '<span class="text-[#5FAF79]">Authorized</span>' : '<span class="text-[#D4A84F]">Confirm req.</span>'}</div>
          </div>
        </div>
      </div>
    `;

    slot.insertAdjacentHTML('beforeend', cardHtml);
  }

  appendProposalCard(containerEl, proposal) {
    const slot = containerEl.querySelector('.card-slot');
    if (!slot) return;

    const formattedFinal = new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 2,
    }).format(proposal.final_amount);

    const formattedBase = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' }).format(proposal.base_price);
    const formattedShipping = proposal.shipping_charge === 0 ? 'FREE' : new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' }).format(proposal.shipping_charge);
    const formattedTax = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' }).format(proposal.tax);

    const altNotice = proposal.alternative_selected
      ? `
        <div class="mb-3 p-2.5 rounded-lg bg-[#5FAF79]/10 border border-[#5FAF79]/30 text-xs text-[#5FAF79] flex items-center space-x-2">
          <span class="font-bold">✓ COMPLIANT ALTERNATIVE FOUND</span>
          <span class="text-[#98978F]">(Evaluated ${proposal.attempts_count} candidate${proposal.attempts_count > 1 ? 's' : ''})</span>
        </div>
      `
      : '';

    const cardHtml = `
      <div class="card-base rounded-xl p-5 border border-[#20221F] bg-[#0D0E0D] animate-fade-in-up">
        ${altNotice}

        <div class="flex items-center justify-between mb-3">
          <span class="text-[10px] font-mono-code uppercase px-2 py-0.5 rounded bg-[#1688D4]/10 text-[#1688D4] border border-[#1688D4]/25">
            Agent Proposal
          </span>
          <span class="text-xs font-mono-code text-[#64635D]">Product #${proposal.product_id}</span>
        </div>

        <div class="flex flex-col sm:flex-row sm:items-start justify-between gap-4 pb-4 border-b border-[#20221F]">
          <div class="space-y-1">
            <h3 class="font-serif-display text-lg sm:text-xl font-medium text-[#F4F1E8]">
              ${this.escapeHtml(proposal.product_name)}
            </h3>
            <p class="text-xs text-[#98978F] leading-relaxed">
              In-stock inventory from verified merchant catalog. Includes calculated GST tax and standard logistics.
            </p>
          </div>

          <div class="bg-[#121311] p-3 rounded-lg border border-[#20221F] sm:text-right min-w-[160px]">
            <div class="text-[10px] font-mono-code text-[#98978F] uppercase">Final Payable Amount</div>
            <div class="font-mono-code text-xl font-bold text-[#F4F1E8] tracking-tight">
              ${formattedFinal}
            </div>
            <div class="text-[10px] font-mono-code text-[#64635D] mt-0.5">
              Base ${formattedBase} + Ship ${formattedShipping} + Tax ${formattedTax}
            </div>
          </div>
        </div>

        <!-- Why PayGuard Selected This -->
        <div class="mt-4">
          <div class="text-[10px] font-mono-code text-[#D6A94A] uppercase tracking-wider mb-1.5 flex items-center space-x-1.5">
            <span>●</span>
            <span>Why PayGuard Selected This</span>
          </div>
          <p class="text-xs text-[#F4F1E8]/90 italic bg-[#121311] p-3 rounded-lg border border-[#20221F] leading-relaxed">
            "${this.escapeHtml(proposal.reason)}"
          </p>
        </div>
      </div>
    `;

    slot.insertAdjacentHTML('beforeend', cardHtml);
  }

  appendPolicyDecisionBlock(containerEl, intent, proposal, verification) {
    const slot = containerEl.querySelector('.card-slot');
    if (!slot) return;

    const decision = verification.decision;
    const checks = verification.checks || [];

    const checksHtml = checks
      .map(
        (c) => `
        <div class="flex items-start space-x-2 py-1 text-xs">
          <span class="${c.status === 'PASS' ? 'text-[#5FAF79]' : 'text-[#C96A67]'} font-bold mt-0.5">
            ${c.status === 'PASS' ? '✓' : '⊘'}
          </span>
          <div class="flex-1">
            <span class="text-[#F4F1E8] font-medium capitalize">${c.check_name.replace(/_/g, ' ')}:</span>
            <span class="text-[#98978F] ml-1">${this.escapeHtml(c.explanation)}</span>
          </div>
        </div>
      `
      )
      .join('');

    let actionSectionHtml = '';
    const formattedAmount = new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 0,
    }).format(proposal.final_amount);

    if (decision === 'APPROVE') {
      actionSectionHtml = `
        <div class="p-4 rounded-xl bg-[#5FAF79]/10 border border-[#5FAF79]/30 mt-4 space-y-3">
          <div class="flex items-center justify-between">
            <div class="flex items-center space-x-2 text-[#5FAF79]">
              <span class="text-base font-bold">✓</span>
              <span class="font-semibold text-sm tracking-wide">PURCHASE APPROVED</span>
            </div>
            <span class="text-[11px] font-mono-code text-[#5FAF79] uppercase">Autonomous Clearance</span>
          </div>
          <p class="text-xs text-[#98978F] leading-relaxed">
            All required checks passed. Payment authorized within your limit.
          </p>
          <div class="pt-1">
            <button class="btn-gold w-full sm:w-auto px-6 py-2.5 rounded-xl text-xs font-semibold tracking-wider flex items-center justify-center space-x-2 continue-pay-btn">
              <span>CONTINUE TO PAYMENT (${formattedAmount})</span>
              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 8l4 4m0 0l-4 4m4-4H3"/>
              </svg>
            </button>
          </div>
        </div>
      `;
    } else if (decision === 'ASK_USER') {
      actionSectionHtml = `
        <div class="p-4 rounded-xl bg-[#D4A84F]/10 border border-[#D4A84F]/35 mt-4 space-y-3">
          <div class="flex items-center justify-between">
            <div class="flex items-center space-x-2 text-[#D4A84F]">
              <span class="text-base font-bold">🟡</span>
              <span class="font-semibold text-sm tracking-wide">CONFIRMATION REQUIRED</span>
            </div>
            <span class="text-[11px] font-mono-code text-[#D4A84F] uppercase">Policy Threshold</span>
          </div>
          <p class="text-xs text-[#98978F] leading-relaxed">
            ${this.escapeHtml(verification.reason)}
          </p>
          <div class="flex flex-wrap gap-2.5 pt-1">
            <button class="btn-gold px-6 py-2.5 rounded-xl text-xs font-semibold tracking-wider flex items-center space-x-2 confirm-approve-btn">
              <span>APPROVE ${formattedAmount}</span>
              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
              </svg>
            </button>
            <button class="btn-secondary px-4 py-2.5 rounded-xl text-xs font-semibold tracking-wider cancel-btn">
              CANCEL
            </button>
          </div>
        </div>
      `;
    } else {
      // BLOCK
      actionSectionHtml = `
        <div class="p-4 rounded-xl bg-[#C96A67]/10 border border-[#C96A67]/35 mt-4 space-y-3">
          <div class="flex items-center justify-between">
            <div class="flex items-center space-x-2 text-[#C96A67]">
              <span class="text-base font-bold">⊘</span>
              <span class="font-semibold text-sm tracking-wide">PURCHASE BLOCKED</span>
            </div>
            <span class="text-[11px] font-mono-code text-[#C96A67] uppercase">Safety Intercept</span>
          </div>
          <p class="text-xs text-[#C96A67] leading-relaxed font-mono-code">
            ${this.escapeHtml(verification.reason)}
          </p>
          <div class="pt-1">
            <button class="btn-secondary px-5 py-2.5 rounded-xl text-xs font-semibold text-[#D6A94A] border-[#D6A94A]/30 hover:border-[#D6A94A] flex items-center space-x-2 find-alt-btn">
              <span>FIND A COMPLIANT ALTERNATIVE</span>
              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
              </svg>
            </button>
          </div>
        </div>
      `;
    }

    const verificationCardHtml = `
      <div class="card-base rounded-xl p-5 border border-[#20221F] bg-[#0D0E0D] animate-fade-in-up">
        <div class="flex items-center justify-between mb-3 pb-2 border-b border-[#20221F]">
          <span class="text-[10px] font-mono-code uppercase px-2 py-0.5 rounded bg-[#121311] text-[#98978F] border border-[#20221F]">
            PayGuard Checks
          </span>
          <span class="text-xs font-mono-code ${decision === 'APPROVE' ? 'text-[#5FAF79]' : decision === 'ASK_USER' ? 'text-[#D4A84F]' : 'text-[#C96A67]'}">
            Result: ${decision}
          </span>
        </div>

        <div class="space-y-1 mb-2">
          ${checksHtml}
        </div>

        ${actionSectionHtml}
      </div>
    `;

    slot.insertAdjacentHTML('beforeend', verificationCardHtml);

    // Bind action events
    const continueBtn = slot.querySelector('.continue-pay-btn');
    if (continueBtn) {
      continueBtn.addEventListener('click', () => {
        continueBtn.disabled = true;
        this.executeRazorpayCheckout(intent, proposal, false, slot);
      });
    }

    const confirmApproveBtn = slot.querySelector('.confirm-approve-btn');
    if (confirmApproveBtn) {
      confirmApproveBtn.addEventListener('click', () => {
        confirmApproveBtn.disabled = true;
        this.executeRazorpayCheckout(intent, proposal, true, slot);
      });
    }

    const cancelBtn = slot.querySelector('.cancel-btn');
    if (cancelBtn) {
      cancelBtn.addEventListener('click', () => {
        cancelBtn.disabled = true;
        slot.insertAdjacentHTML(
          'beforeend',
          `<div class="p-3 bg-[#121311] rounded-lg border border-[#20221F] text-xs text-[#98978F] mt-3">Transaction was cancelled by user.</div>`
        );
      });
    }

    const findAltBtn = slot.querySelector('.find-alt-btn');
    if (findAltBtn) {
      findAltBtn.addEventListener('click', async () => {
        findAltBtn.disabled = true;
        findAltBtn.innerHTML = `Searching alternatives...`;
        try {
          const newProposal = await this.callBuyerAgent(intent.intent_contract_id);
          this.currentProposal = newProposal;
          this.appendProposalCard(containerEl, newProposal);
          const newVerif = await this.callVerificationAgent(intent.intent_contract_id, newProposal.product_id, newProposal.quantity);
          this.currentVerification = newVerif;
          this.appendPolicyDecisionBlock(containerEl, intent, newProposal, newVerif);
        } catch (err) {
          slot.insertAdjacentHTML('beforeend', `<div class="p-3 bg-[#C96A67]/10 text-xs text-[#C96A67] rounded-lg mt-3">${err.message}</div>`);
        }
      });
    }
  }

  appendIntentMismatchCard(containerEl, intent, proposal) {
    const slot = containerEl.querySelector('.card-slot');
    if (!slot) return;

    const diff = proposal.final_amount - intent.max_budget;
    const formattedDiff = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' }).format(diff);

    const cardHtml = `
      <div class="card-base rounded-xl p-5 border-l-2 border-l-[#C96A67] bg-[#0D0E0D] animate-fade-in-up">
        <div class="flex items-center justify-between mb-3 pb-2 border-b border-[#20221F]">
          <span class="text-[10px] font-mono-code uppercase px-2 py-0.5 rounded bg-[#C96A67]/10 text-[#C96A67] border border-[#C96A67]/25">
            Intent Mismatch Detected
          </span>
          <span class="text-xs font-mono-code text-[#C96A67]">Autonomous Payment Intercepted</span>
        </div>

        <div class="grid grid-cols-3 gap-3 my-4 p-3 bg-[#121311] rounded-lg border border-[#20221F] text-center text-xs">
          <div>
            <div class="text-[10px] font-mono-code text-[#98978F] uppercase">Authorized</div>
            <div class="font-mono-code text-[#D6A94A] font-semibold">₹${intent.max_budget.toLocaleString('en-IN')} MAX</div>
          </div>
          <div>
            <div class="text-[10px] font-mono-code text-[#98978F] uppercase">Proposed</div>
            <div class="font-mono-code text-[#C96A67] font-semibold">₹${proposal.final_amount.toLocaleString('en-IN')}</div>
          </div>
          <div>
            <div class="text-[10px] font-mono-code text-[#98978F] uppercase">Difference</div>
            <div class="font-mono-code text-[#C96A67] font-semibold">+${formattedDiff}</div>
          </div>
        </div>

        <p class="text-xs text-[#98978F] leading-relaxed mb-4">
          PayGuard prevented the AI's decision from becoming an unauthorized payment:
          <span class="text-[#F4F1E8] font-mono-code">${(proposal.drift_reasons || []).join(' · ')}</span>
        </p>

        <button class="btn-gold px-5 py-2.5 rounded-xl text-xs font-semibold tracking-wider flex items-center space-x-2 trigger-alt-search-btn">
          <span>FIND COMPLIANT ALTERNATIVE</span>
          <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14 5l7 7m0 0l-7 7m7-7H3"/>
          </svg>
        </button>
      </div>
    `;

    slot.insertAdjacentHTML('beforeend', cardHtml);

    const btn = slot.querySelector('.trigger-alt-search-btn');
    btn?.addEventListener('click', async () => {
      btn.disabled = true;
      btn.innerText = 'Searching compliant alternative...';
      try {
        const altProposal = await this.callBuyerAgent(intent.intent_contract_id);
        this.currentProposal = altProposal;
        this.appendProposalCard(containerEl, altProposal);
        const verif = await this.callVerificationAgent(intent.intent_contract_id, altProposal.product_id, altProposal.quantity);
        this.currentVerification = verif;
        this.appendPolicyDecisionBlock(containerEl, intent, altProposal, verif);
      } catch (err) {
        slot.insertAdjacentHTML('beforeend', `<div class="p-3 bg-[#C96A67]/10 text-xs text-[#C96A67] rounded-lg mt-3">${err.message}</div>`);
      }
    });
  }

  // --- Real Razorpay Test Mode Checkout ---

  async executeRazorpayCheckout(intent, proposal, userConfirmed, slotEl) {
    const payStateId = `pay-state-${Date.now()}`;
    const payStateHtml = `
      <div id="${payStateId}" class="card-base rounded-xl p-5 border border-[#1688D4]/30 bg-[#0D0E0D] animate-fade-in-up mt-4">
        <div class="flex items-center justify-between mb-3">
          <div class="flex items-center space-x-2">
            <span class="w-2 h-2 rounded-full bg-[#1688D4] animate-ping"></span>
            <span class="text-xs font-mono-code uppercase text-[#1688D4]">Payment Agent Initiating Order</span>
          </div>
          <span class="text-[10px] font-mono-code text-[#D6A94A] bg-[#D6A94A]/10 px-2 py-0.5 rounded border border-[#D6A94A]/20">
            Razorpay Test Mode
          </span>
        </div>
        <div class="text-xs text-[#98978F] leading-relaxed pay-status-text">
          Creating order for ₹${proposal.final_amount.toLocaleString('en-IN')} with validated credentials...
        </div>
      </div>
    `;
    slotEl.insertAdjacentHTML('beforeend', payStateHtml);
    const payBox = document.getElementById(payStateId);

    try {
      const orderData = await this.callCreatePayment(
        intent.intent_contract_id,
        proposal.product_id,
        proposal.quantity,
        userConfirmed
      );
      this.currentTransaction = orderData;

      const statusText = payBox.querySelector('.pay-status-text');
      if (statusText) {
        statusText.innerHTML = `
          Order created: <span class="font-mono-code text-[#F4F1E8]">${orderData.razorpay_order_id}</span>. Opening secure checkout popup...
        `;
      }

      if (typeof window.Razorpay === 'undefined') {
        throw new Error('Razorpay SDK failed to load. Please check internet connectivity.');
      }

      const rzpOptions = {
        key: orderData.razorpay_key_id,
        amount: orderData.amount_in_paise,
        currency: orderData.currency || 'INR',
        name: 'PayGuard Commerce',
        description: `Autonomous Purchase: ${proposal.product_name}`,
        order_id: orderData.razorpay_order_id,
        notes: {
          intent_contract_id: intent.intent_contract_id,
          product_id: proposal.product_id,
        },
        theme: {
          color: '#D6A94A',
        },
        handler: async (response) => {
          payBox.innerHTML = `
            <div class="flex items-center space-x-2 text-xs text-[#1688D4]">
              <svg class="spin-active w-4 h-4" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
              </svg>
              <span>Verifying cryptographic payment signature with backend...</span>
            </div>
          `;

          try {
            const verifyRes = await this.callVerifyPaymentSignature(
              orderData.transaction_id,
              response.razorpay_order_id,
              response.razorpay_payment_id,
              response.razorpay_signature
            );

            this.renderPaymentSuccess(payBox, orderData, response, verifyRes);
          } catch (verifErr) {
            this.renderPaymentFailure(payBox, verifErr.message);
          }
        },
        modal: {
          ondismiss: () => {
            if (payBox) {
              payBox.innerHTML = `
                <div class="text-xs text-[#D4A84F] p-3 rounded bg-[#D4A84F]/10 border border-[#D4A84F]/25 flex items-center justify-between">
                  <span>Payment was closed or dismissed by user.</span>
                  <button class="text-[11px] font-mono-code underline ml-2 retry-btn text-[#F4F1E8]">Retry Payment</button>
                </div>
              `;
              payBox.querySelector('.retry-btn')?.addEventListener('click', () => {
                this.executeRazorpayCheckout(intent, proposal, userConfirmed, slotEl);
              });
            }
          },
        },
      };

      const rzpInstance = new window.Razorpay(rzpOptions);
      rzpInstance.on('payment.failed', (failResponse) => {
        this.renderPaymentFailure(payBox, failResponse.error.description || 'Payment rejected by gateway.');
      });
      rzpInstance.open();

    } catch (err) {
      console.error('Payment checkout error:', err);
      this.renderPaymentFailure(payBox, err.message);
    }
  }

  renderPaymentSuccess(containerEl, orderData, rzpData, verifyData) {
    const formattedAmount = new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 2,
    }).format(orderData.amount);

    containerEl.className = 'card-base rounded-xl p-6 border border-[#5FAF79]/40 bg-[#0D0E0D] animate-fade-in-up mt-4';
    containerEl.innerHTML = `
      <div class="flex items-center space-x-3 mb-4 pb-3 border-b border-[#20221F]">
        <div class="w-8 h-8 rounded-full bg-[#5FAF79]/20 flex items-center justify-center text-[#5FAF79] text-base font-bold">
          ✓
        </div>
        <div>
          <h4 class="font-serif-display text-lg font-semibold text-[#F4F1E8]">
            Payment Verified
          </h4>
          <p class="text-xs text-[#5FAF79] font-mono-code uppercase tracking-wider">
            Purchase completed successfully.
          </p>
        </div>
      </div>

      <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs mb-5 p-3.5 bg-[#121311] rounded-lg border border-[#20221F]">
        <div>
          <div class="text-[10px] font-mono-code text-[#64635D] uppercase">Amount Settled</div>
          <div class="font-mono-code text-sm font-bold text-[#F4F1E8]">${formattedAmount}</div>
        </div>
        <div>
          <div class="text-[10px] font-mono-code text-[#64635D] uppercase">Transaction</div>
          <div class="font-mono-code text-xs text-[#F4F1E8]">#TX-${verifyData.transaction_id}</div>
        </div>
        <div>
          <div class="text-[10px] font-mono-code text-[#64635D] uppercase">Razorpay Order</div>
          <div class="font-mono-code text-[11px] text-[#98978F] truncate">${rzpData.razorpay_order_id}</div>
        </div>
        <div>
          <div class="text-[10px] font-mono-code text-[#64635D] uppercase">Payment Reference</div>
          <div class="font-mono-code text-[11px] text-[#5FAF79] truncate">${rzpData.razorpay_payment_id}</div>
        </div>
      </div>

      <div class="flex items-center justify-between text-xs pt-1">
        <span class="text-[#98978F]">Purchase safely fulfilled within your Intent Contract.</span>
        <button class="btn-gold px-5 py-2 rounded-xl text-xs font-semibold tracking-wider flex items-center space-x-1.5 restart-agent-btn">
          <span>DONE</span>
        </button>
      </div>
    `;

    containerEl.querySelector('.restart-agent-btn')?.addEventListener('click', () => {
      this.resetConversation();
    });
  }

  renderPaymentFailure(containerEl, errorMsg) {
    containerEl.className = 'card-base rounded-xl p-5 border border-[#C96A67]/40 bg-[#0D0E0D] animate-fade-in-up mt-4';
    containerEl.innerHTML = `
      <div class="flex items-center space-x-2 text-[#C96A67] mb-2 font-semibold text-sm">
        <span>⊘</span>
        <span>Payment Could Not Be Completed</span>
      </div>
      <p class="text-xs text-[#98978F] leading-relaxed mb-3">
        ${this.escapeHtml(errorMsg)}
      </p>
      <div class="text-[11px] font-mono-code text-[#64635D] bg-[#121311] p-2.5 rounded border border-[#20221F]">
        AUTOMATED RETRIES STOPPED · Further payment attempts require user confirmation.
      </div>
    `;
  }

  appendErrorBlock(containerEl, msg) {
    const slot = containerEl.querySelector('.card-slot');
    if (!slot) return;
    slot.insertAdjacentHTML(
      'beforeend',
      `
      <div class="p-4 rounded-xl bg-[#C96A67]/10 border border-[#C96A67]/30 text-xs text-[#C96A67] animate-fade-in-up">
        <span class="font-bold">Execution Error:</span> ${this.escapeHtml(msg)}
      </div>
    `
    );
  }

  // --- Drawers & Modals ---

  async openAuditDrawer() {
    if (!this.dom.auditDrawer || !this.dom.auditTimeline) return;
    this.dom.auditDrawer.classList.remove('translate-x-full');

    this.dom.auditTimeline.innerHTML = `
      <div class="flex items-center justify-center p-8 text-xs text-[#98978F]">
        <svg class="spin-active w-4 h-4 text-[#D6A94A] mr-2" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
        </svg>
        <span>Loading PostgreSQL audit logs...</span>
      </div>
    `;

    try {
      const res = await fetch(`${this.apiBase}/api/audit-logs?limit=25`);
      const logs = await res.json();

      if (!logs || logs.length === 0) {
        this.dom.auditTimeline.innerHTML = `
          <div class="p-6 text-center text-xs text-[#64635D]">No audit records logged yet.</div>
        `;
        return;
      }

      this.dom.auditTimeline.innerHTML = logs
        .map((log) => {
          const isSuccess = ['SUCCESS', 'APPROVED', 'PASS', 'COMPLETED'].includes(log.decision?.toUpperCase());
          const isWarning = ['ASK_USER', 'PROPOSED', 'ALTERNATIVE_PROPOSED', 'WAITING_USER_CONFIRMATION'].includes(log.decision?.toUpperCase());
          const badgeClass = isSuccess 
            ? 'text-[#5FAF79] bg-[#5FAF79]/10 border-[#5FAF79]/25' 
            : isWarning 
            ? 'text-[#D4A84F] bg-[#D4A84F]/10 border-[#D4A84F]/25' 
            : 'text-[#C96A67] bg-[#C96A67]/10 border-[#C96A67]/25';

          return `
            <div class="relative pl-6 pb-6 border-l border-[#20221F] last:border-l-0">
              <div class="absolute -left-[5px] top-1 w-2.5 h-2.5 rounded-full ${isSuccess ? 'bg-[#5FAF79]' : isWarning ? 'bg-[#D4A84F]' : 'bg-[#C96A67]'}"></div>
              <div class="flex items-center justify-between text-[10px] font-mono-code text-[#64635D] mb-1">
                <span>${log.timestamp}</span>
                <span class="px-2 py-0.5 rounded border text-[9px] font-semibold ${badgeClass}">
                  ${log.decision}
                </span>
              </div>
              <div class="text-xs font-semibold text-[#F4F1E8] mb-0.5">
                <span class="text-[#D6A94A] font-mono-code text-[11px]">${log.agent}</span> → ${log.action}
              </div>
              <p class="text-xs text-[#98978F] leading-relaxed bg-[#121311] p-2.5 rounded border border-[#20221F]/80 mt-1.5">
                ${this.escapeHtml(log.reason || 'No description logged.')}
              </p>
            </div>
          `;
        })
        .join('');
    } catch (err) {
      this.dom.auditTimeline.innerHTML = `
        <div class="p-4 bg-[#C96A67]/10 text-xs text-[#C96A67] rounded-lg">
          Failed to load audit trail: ${err.message}
        </div>
      `;
    }
  }

  closeAuditDrawer() {
    this.dom.auditDrawer?.classList.add('translate-x-full');
  }

  openActivityDrawer() {
    this.dom.activityDrawer?.classList.remove('translate-x-full');
  }

  closeActivityDrawer() {
    this.dom.activityDrawer?.classList.add('translate-x-full');
  }

  async openPoliciesModal() {
    if (!this.dom.policiesModal || !this.dom.policiesContent) return;
    this.dom.policiesModal.classList.remove('hidden');

    try {
      const res = await fetch(`${this.apiBase}/api/policies`);
      const policy = await res.json();
      this.dom.policiesContent.innerHTML = `
        <div class="grid grid-cols-2 gap-4 text-xs">
          <div class="bg-[#121311] p-4 rounded-xl border border-[#20221F]">
            <div class="text-[10px] font-mono-code text-[#98978F] uppercase mb-1">Max Transaction Limit</div>
            <div class="font-mono-code text-lg font-bold text-[#F4F1E8]">₹${policy.max_transaction_amount.toLocaleString('en-IN')}</div>
            <div class="text-[10px] text-[#64635D] mt-1">Autonomous hard limit</div>
          </div>

          <div class="bg-[#121311] p-4 rounded-xl border border-[#20221F]">
            <div class="text-[10px] font-mono-code text-[#98978F] uppercase mb-1">High-Value Threshold</div>
            <div class="font-mono-code text-lg font-bold text-[#D4A84F]">₹${policy.high_value_threshold.toLocaleString('en-IN')}</div>
            <div class="text-[10px] text-[#64635D] mt-1">Requires user approval</div>
          </div>

          <div class="bg-[#121311] p-4 rounded-xl border border-[#20221F]">
            <div class="text-[10px] font-mono-code text-[#98978F] uppercase mb-1">Max Retries</div>
            <div class="font-mono-code text-lg font-bold text-[#F4F1E8]">${policy.max_automated_retries} Attempts</div>
            <div class="text-[10px] text-[#64635D] mt-1">Alternative finder search limit</div>
          </div>

          <div class="bg-[#121311] p-4 rounded-xl border border-[#20221F]">
            <div class="text-[10px] font-mono-code text-[#98978F] uppercase mb-1">Duplicate Purchase Block</div>
            <div class="font-mono-code text-lg font-bold text-[#5FAF79]">${policy.duplicate_purchase_block ? 'ENABLED' : 'DISABLED'}</div>
            <div class="text-[10px] text-[#64635D] mt-1">Prevents double charges</div>
          </div>
        </div>
      `;
    } catch (err) {
      this.dom.policiesContent.innerHTML = `<div class="text-xs text-[#C96A67]">Failed to load policy data.</div>`;
    }
  }

  closePoliciesModal() {
    this.dom.policiesModal?.classList.add('hidden');
  }

  escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }
}

document.addEventListener('DOMContentLoaded', () => {
  window.payguard = new PayGuardApp();
});
