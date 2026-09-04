/**
 * PayGuard — Autonomous Multi-Agent AI Commerce Engine
 * Complete End-to-End Client-Side Controller & Razorpay Integration
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
      heroInput: document.getElementById('hero-input'),
      heroSendBtn: document.getElementById('hero-send-btn'),
      chatContainer: document.getElementById('chat-container'),
      chatStream: document.getElementById('chat-stream'),

      // Drawers & Modals
      auditDrawer: document.getElementById('audit-drawer'),
      auditTimeline: document.getElementById('audit-timeline'),
      policiesModal: document.getElementById('policies-modal'),
      policiesContent: document.getElementById('policies-content'),

      // Navigation
      openAuditBtn: document.getElementById('nav-audit-btn'),
      openPoliciesBtn: document.getElementById('nav-policies-btn'),
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

    // Auto-resize textarea
    this.dom.heroInput?.addEventListener('input', () => {
      if (this.dom.heroInput) {
        this.dom.heroInput.style.height = 'auto';
        this.dom.heroInput.style.height = `${Math.min(this.dom.heroInput.scrollHeight, 200)}px`;
      }
    });

    // Drawers and Modals
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
          <span class="w-2 h-2 rounded-full bg-[#62AA78] agent-live-pulse inline-block mr-1.5"></span>
          <span class="text-xs text-[#9A9991] font-mono-code uppercase tracking-wider">Agent Online</span>
        `;
      }
    } catch (err) {
      console.warn('Backend health check warning:', err);
    }
  }

  updateProcessingState(isBusy) {
    this.isProcessing = isBusy;
    if (!this.dom.heroSendBtn) return;

    this.dom.heroSendBtn.disabled = isBusy;
    this.dom.heroSendBtn.innerHTML = isBusy
      ? `
        <svg class="spin-active w-3.5 h-3.5 text-[#080908]" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
        </svg>
        <span>EXECUTING</span>
      `
      : `
        <span>EXECUTE</span>
        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14 5l7 7m0 0l-7 7m7-7H3"/>
        </svg>
      `;
  }

  scrollToActiveStream() {
    if (this.dom.chatContainer) {
      this.dom.chatContainer.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }

  async handleUserSubmit(rawText) {
    if (this.isProcessing || !rawText) return;

    // Show chat stream container
    if (this.dom.chatContainer) this.dom.chatContainer.classList.remove('hidden');

    // Append User message card
    this.appendUserMessage(rawText);
    if (this.dom.heroInput) {
      this.dom.heroInput.value = '';
      this.dom.heroInput.style.height = 'auto';
    }
    this.updateProcessingState(true);

    const pipelineId = `pipeline-${Date.now()}`;
    const agentMsgEl = this.createAgentMessageContainer(pipelineId);
    this.scrollToActiveStream();

    try {
      // Step 1: Real Intent Agent Extraction
      this.updatePipelineStep(pipelineId, 'intent', 'active', 'Extracting constraints & parameters via Groq LLM...');
      const intentContract = await this.callIntentAgent(rawText);
      this.currentContract = intentContract;
      this.updatePipelineStep(pipelineId, 'intent', 'done', `Intent Contract #${intentContract.intent_contract_id} Locked`);

      // Render Real Intent Contract Card
      this.appendIntentContractCard(agentMsgEl, intentContract);

      // Step 2: Real Buyer Agent Candidate Search
      this.updatePipelineStep(pipelineId, 'buyer', 'active', 'Evaluating merchant inventory & drift...');
      const proposal = await this.callBuyerAgent(intentContract.intent_contract_id);
      this.currentProposal = proposal;
      this.updatePipelineStep(
        pipelineId,
        'buyer',
        'done',
        proposal.drift_detected
          ? 'Intent Mismatch Detected'
          : `Selected: ${proposal.product_name} (${proposal.attempts_count} candidate${proposal.attempts_count > 1 ? 's' : ''} evaluated)`
      );

      // Check Intent Drift / Mismatch
      if (proposal.drift_detected) {
        this.appendIntentMismatchCard(agentMsgEl, intentContract, proposal);
        this.updateProcessingState(false);
        return;
      }

      // Render Real Proposal Card
      this.appendProposalCard(agentMsgEl, proposal);

      // Step 3: Real Verification Agent Checks
      this.updatePipelineStep(pipelineId, 'verify', 'active', 'Running 5-point independent verification...');
      const verification = await this.callVerificationAgent(
        intentContract.intent_contract_id,
        proposal.product_id,
        proposal.quantity
      );
      this.currentVerification = verification;
      this.updatePipelineStep(pipelineId, 'verify', 'done', '5-Factor Verification Complete');

      // Step 4: Real Policy Engine Decision
      this.updatePipelineStep(pipelineId, 'policy', 'active', 'Evaluating merchant spending caps...');
      this.updatePipelineStep(pipelineId, 'policy', 'done', `Policy Decision: ${verification.decision}`);

      // Render Policy Decision Block & Handle Auto-Approve / Ask-User / Block
      this.appendPolicyDecisionBlock(agentMsgEl, intentContract, proposal, verification);

    } catch (err) {
      console.error('Execution error:', err);
      this.appendErrorBlock(agentMsgEl, err.message || 'An error occurred during agent processing.');
    } finally {
      this.updateProcessingState(false);
      this.scrollToActiveStream();
    }
  }

  // --- Real Backend API Handlers ---

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
      throw new Error(err.detail || 'Cryptographic payment verification failed.');
    }
    return await res.json();
  }

  async fetchLiveAuditLogs(limit = 25) {
    const res = await fetch(`${this.apiBase}/api/audit-logs?limit=${limit}`);
    if (!res.ok) return [];
    return await res.json();
  }

  // --- UI Component Renderers ---

  appendUserMessage(text) {
    if (!this.dom.chatStream) return;
    const el = document.createElement('div');
    el.className = 'flex items-start space-x-3 justify-end animate-fade-in-up';
    el.innerHTML = `
      <div class="max-w-xl surface-card rounded-2xl p-4 border border-[#22231F] text-right bg-[#0C0D0C]">
        <div class="text-[10px] font-mono-code text-[#D6A94A] uppercase tracking-wider mb-1">
          User Instruction · Intent Input
        </div>
        <p class="text-sm font-normal text-[#F3F0E8] leading-relaxed">
          ${this.escapeHtml(text)}
        </p>
      </div>
      <div class="w-8 h-8 rounded-lg bg-[#111210] border border-[#22231F] flex items-center justify-center text-xs font-mono-code text-[#9A9991] flex-shrink-0 mt-1">
        U
      </div>
    `;
    this.dom.chatStream.appendChild(el);
  }

  createAgentMessageContainer(pipelineId) {
    const wrapper = document.createElement('div');
    wrapper.id = pipelineId;
    wrapper.className = 'w-full space-y-4 animate-fade-in-up';

    wrapper.innerHTML = `
      <!-- Process Header -->
      <div class="surface-card rounded-2xl p-5 border border-[#22231F] bg-[#0C0D0C]">
        <div class="flex items-center justify-between pb-3 border-b border-[#22231F] mb-4">
          <div class="flex items-center space-x-2.5">
            <span class="w-2 h-2 rounded-full bg-[#1688D4] agent-live-pulse"></span>
            <span class="font-mono-code text-xs font-semibold uppercase tracking-wider text-[#F3F0E8]">
              PayGuard Multi-Agent Execution Session
            </span>
          </div>
          <span class="text-[10px] font-mono-code text-[#64635D]">Session ID: ${pipelineId.replace('pipeline-', '#')}</span>
        </div>

        <!-- 5-Agent Process Pipeline Timeline -->
        <div class="grid grid-cols-1 sm:grid-cols-5 gap-2 text-xs">
          <!-- Step 1: Intent -->
          <div id="${pipelineId}-step-intent" class="p-2.5 rounded-lg border border-[#22231F] bg-[#111210] space-y-1 transition">
            <div class="flex items-center justify-between text-[10px] font-mono-code text-[#64635D]">
              <span>01 · INTENT</span>
              <span class="step-status">⏳</span>
            </div>
            <div class="font-mono-code text-[11px] text-[#F3F0E8] font-medium truncate">Extract Intent</div>
            <div class="text-[10px] text-[#9A9991] leading-tight step-desc">Waiting...</div>
          </div>

          <!-- Step 2: Buyer -->
          <div id="${pipelineId}-step-buyer" class="p-2.5 rounded-lg border border-[#22231F] bg-[#111210] space-y-1 transition">
            <div class="flex items-center justify-between text-[10px] font-mono-code text-[#64635D]">
              <span>02 · BUYER</span>
              <span class="step-status">⏳</span>
            </div>
            <div class="font-mono-code text-[11px] text-[#F3F0E8] font-medium truncate">Select Product</div>
            <div class="text-[10px] text-[#9A9991] leading-tight step-desc">Waiting...</div>
          </div>

          <!-- Step 3: Verification -->
          <div id="${pipelineId}-step-verify" class="p-2.5 rounded-lg border border-[#22231F] bg-[#111210] space-y-1 transition">
            <div class="flex items-center justify-between text-[10px] font-mono-code text-[#64635D]">
              <span>03 · VERIFY</span>
              <span class="step-status">⏳</span>
            </div>
            <div class="font-mono-code text-[11px] text-[#F3F0E8] font-medium truncate">5-Point Check</div>
            <div class="text-[10px] text-[#9A9991] leading-tight step-desc">Waiting...</div>
          </div>

          <!-- Step 4: Policy -->
          <div id="${pipelineId}-step-policy" class="p-2.5 rounded-lg border border-[#22231F] bg-[#111210] space-y-1 transition">
            <div class="flex items-center justify-between text-[10px] font-mono-code text-[#64635D]">
              <span>04 · POLICY</span>
              <span class="step-status">⏳</span>
            </div>
            <div class="font-mono-code text-[11px] text-[#F3F0E8] font-medium truncate">Decision Engine</div>
            <div class="text-[10px] text-[#9A9991] leading-tight step-desc">Waiting...</div>
          </div>

          <!-- Step 5: Payment -->
          <div id="${pipelineId}-step-payment" class="p-2.5 rounded-lg border border-[#22231F] bg-[#111210] space-y-1 transition">
            <div class="flex items-center justify-between text-[10px] font-mono-code text-[#64635D]">
              <span>05 · PAYMENT</span>
              <span class="step-status">⏳</span>
            </div>
            <div class="font-mono-code text-[11px] text-[#F3F0E8] font-medium truncate">Razorpay Test</div>
            <div class="text-[10px] text-[#9A9991] leading-tight step-desc">Waiting...</div>
          </div>
        </div>
      </div>

      <!-- Execution Cards Container -->
      <div class="card-slot space-y-4"></div>
    `;

    this.dom.chatStream?.appendChild(wrapper);
    return wrapper;
  }

  updatePipelineStep(pipelineId, stepName, state, desc) {
    const el = document.getElementById(`${pipelineId}-step-${stepName}`);
    if (!el) return;

    const statusEl = el.querySelector('.step-status');
    const descEl = el.querySelector('.step-desc');

    if (descEl && desc) descEl.textContent = desc;

    if (!statusEl) return;

    if (state === 'active') {
      statusEl.innerHTML = `
        <svg class="spin-active w-3 h-3 text-[#1688D4]" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
        </svg>
      `;
      el.classList.add('bg-[#1688D4]/5', 'border-[#1688D4]/40');
    } else if (state === 'done') {
      statusEl.innerHTML = `<span class="text-[#62AA78] font-bold">✓</span>`;
      el.classList.remove('bg-[#1688D4]/5', 'border-[#1688D4]/40');
      el.classList.add('border-[#22231F]');
    } else if (state === 'fail') {
      statusEl.innerHTML = `<span class="text-[#C96A67] font-bold">⊘</span>`;
      el.classList.remove('bg-[#1688D4]/5', 'border-[#1688D4]/40');
      el.classList.add('border-[#C96A67]/40');
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
      <div class="surface-card rounded-xl p-5 border-l-2 border-l-[#D6A94A] bg-[#0C0D0C] animate-fade-in-up">
        <div class="flex items-center justify-between mb-4 pb-2.5 border-b border-[#22231F]">
          <div class="flex items-center space-x-2">
            <span class="text-[10px] font-mono-code uppercase px-2 py-0.5 rounded bg-[#D6A94A]/10 text-[#D6A94A] border border-[#D6A94A]/25">
              Intent Contract #${intent.intent_contract_id}
            </span>
            <span class="text-[11px] font-mono-code text-[#64635D]">Saved in PostgreSQL</span>
          </div>
          <div class="flex items-center space-x-1 text-[#62AA78] text-xs font-mono-code">
            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"/>
            </svg>
            <span class="text-[11px] font-semibold uppercase tracking-wider">Intent Locked</span>
          </div>
        </div>

        <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
          <div>
            <div class="text-[10px] font-mono-code text-[#64635D] uppercase mb-0.5">Product Type</div>
            <div class="font-medium text-[#F3F0E8]">${this.escapeHtml(intent.product_type || 'General')}</div>
          </div>
          <div>
            <div class="text-[10px] font-mono-code text-[#64635D] uppercase mb-0.5">Purpose</div>
            <div class="font-medium text-[#F3F0E8] capitalize">${this.escapeHtml(intent.purpose || 'Personal / General')}</div>
          </div>
          <div>
            <div class="text-[10px] font-mono-code text-[#64635D] uppercase mb-0.5">Authorized Budget</div>
            <div class="font-mono-code font-semibold text-[#D6A94A]">${formattedBudget} MAX</div>
          </div>
          <div>
            <div class="text-[10px] font-mono-code text-[#64635D] uppercase mb-0.5">Quantity / Authority</div>
            <div class="font-medium text-[#F3F0E8]">
              ${intent.quantity} unit · ${intent.payment_authorized ? '<span class="text-[#62AA78]">Payment Authorized</span>' : '<span class="text-[#CFA64D]">Confirmation Required</span>'}
            </div>
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
        <div class="mb-3 p-2.5 rounded-lg bg-[#62AA78]/10 border border-[#62AA78]/30 text-xs text-[#62AA78] flex items-center space-x-2">
          <span class="font-bold">✓ COMPLIANT ALTERNATIVE FOUND</span>
          <span class="text-[#9A9991]">(Evaluated ${proposal.attempts_count} candidate${proposal.attempts_count > 1 ? 's' : ''} in merchant catalog)</span>
        </div>
      `
      : '';

    const cardHtml = `
      <div class="surface-card rounded-xl p-5 border border-[#22231F] bg-[#0C0D0C] animate-fade-in-up">
        ${altNotice}

        <div class="flex items-center justify-between mb-3">
          <span class="text-[10px] font-mono-code uppercase px-2 py-0.5 rounded bg-[#1688D4]/10 text-[#1688D4] border border-[#1688D4]/25">
            Buyer Agent Proposal
          </span>
          <span class="text-xs font-mono-code text-[#64635D]">Catalog Product #${proposal.product_id}</span>
        </div>

        <div class="flex flex-col sm:flex-row sm:items-start justify-between gap-4 pb-4 border-b border-[#22231F]">
          <div class="space-y-1">
            <h3 class="font-serif-display text-lg sm:text-xl font-medium text-[#F3F0E8]">
              ${this.escapeHtml(proposal.product_name)}
            </h3>
            <p class="text-xs text-[#9A9991] leading-relaxed font-light">
              In-stock inventory from verified merchant catalog. Deterministically calculated with applicable GST and delivery.
            </p>
          </div>

          <div class="bg-[#111210] p-3 rounded-lg border border-[#22231F] sm:text-right min-w-[170px]">
            <div class="text-[10px] font-mono-code text-[#9A9991] uppercase">Final Payable Total</div>
            <div class="font-mono-code text-xl font-bold text-[#F3F0E8] tracking-tight">
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
          <p class="text-xs text-[#F3F0E8]/90 italic bg-[#111210] p-3 rounded-lg border border-[#22231F] leading-relaxed">
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
          <span class="${c.status === 'PASS' ? 'text-[#62AA78]' : 'text-[#C96A67]'} font-bold mt-0.5">
            ${c.status === 'PASS' ? '✓' : '⊘'}
          </span>
          <div class="flex-1">
            <span class="text-[#F3F0E8] font-medium capitalize">${c.check_name.replace(/_/g, ' ')}:</span>
            <span class="text-[#9A9991] ml-1">${this.escapeHtml(c.explanation)}</span>
          </div>
        </div>
      `
      )
      .join('');

    let actionSectionHtml = '';
    const formattedAmount = new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 2,
    }).format(proposal.final_amount);

    if (decision === 'APPROVE') {
      // AUTO APPROVE: automatically continue to payment, do not show an approval button
      actionSectionHtml = `
        <div class="p-4 rounded-xl bg-[#62AA78]/10 border border-[#62AA78]/30 mt-4 space-y-3">
          <div class="flex items-center justify-between">
            <div class="flex items-center space-x-2 text-[#62AA78]">
              <span class="text-base font-bold">✓</span>
              <span class="font-semibold text-sm tracking-wide">AUTO-APPROVED</span>
            </div>
            <span class="text-[11px] font-mono-code text-[#62AA78] uppercase">Autonomous Clearance</span>
          </div>
          <p class="text-xs text-[#9A9991] leading-relaxed">
            All 5 verification checks passed and amount (${formattedAmount}) is within authorized budget and merchant policy limits.
            <span class="text-[#F3F0E8] font-medium block mt-1">Automatically launching secure Razorpay Test Mode checkout...</span>
          </p>
        </div>
      `;
    } else if (decision === 'ASK_USER') {
      // ASK_USER: pause the agent, clearly explain why confirmation is required, show APPROVE button
      actionSectionHtml = `
        <div class="p-4 rounded-xl bg-[#CFA64D]/10 border border-[#CFA64D]/35 mt-4 space-y-3">
          <div class="flex items-center justify-between">
            <div class="flex items-center space-x-2 text-[#CFA64D]">
              <span class="text-base font-bold">🟡</span>
              <span class="font-semibold text-sm tracking-wide">PAUSED · CONFIRMATION REQUIRED</span>
            </div>
            <span class="text-[11px] font-mono-code text-[#CFA64D] uppercase">Merchant Policy Guardrail</span>
          </div>
          <p class="text-xs text-[#9A9991] leading-relaxed">
            ${this.escapeHtml(verification.reason)}
          </p>
          <div class="flex flex-wrap gap-2.5 pt-1">
            <button class="btn-gold px-6 py-2.5 rounded-xl text-xs font-semibold tracking-wider flex items-center space-x-2 confirm-approve-btn">
              <span>APPROVE ${formattedAmount}</span>
              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
              </svg>
            </button>
            <button class="btn-outline px-4 py-2.5 rounded-xl text-xs font-semibold tracking-wider cancel-btn">
              CANCEL
            </button>
          </div>
        </div>
      `;
    } else {
      // BLOCK: stop payment completely, show exact reason, show FIND COMPLIANT ALTERNATIVE if available
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
            <button class="btn-outline px-5 py-2.5 rounded-xl text-xs font-semibold text-[#D6A94A] border-[#D6A94A]/30 hover:border-[#D6A94A] flex items-center space-x-2 find-alt-btn">
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
      <div class="surface-card rounded-xl p-5 border border-[#22231F] bg-[#0C0D0C] animate-fade-in-up">
        <div class="flex items-center justify-between mb-3 pb-2 border-b border-[#22231F]">
          <span class="text-[10px] font-mono-code uppercase px-2 py-0.5 rounded bg-[#111210] text-[#9A9991] border border-[#22231F]">
            PayGuard 5-Factor Verification Matrix
          </span>
          <span class="text-xs font-mono-code font-semibold ${decision === 'APPROVE' ? 'text-[#62AA78]' : decision === 'ASK_USER' ? 'text-[#CFA64D]' : 'text-[#C96A67]'}">
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

    // AUTO APPROVE ACTION: Proceed directly without user button
    if (decision === 'APPROVE') {
      setTimeout(() => {
        this.executeRazorpayCheckout(intent, proposal, false, slot);
      }, 700);
      return;
    }

    // ASK_USER Confirmation Button Handler
    const confirmApproveBtn = slot.querySelector('.confirm-approve-btn');
    if (confirmApproveBtn) {
      confirmApproveBtn.addEventListener('click', () => {
        confirmApproveBtn.disabled = true;
        confirmApproveBtn.innerHTML = `
          <svg class="spin-active w-3.5 h-3.5 text-[#080908]" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
          </svg>
          <span>AUTHORIZING PAYMENT...</span>
        `;
        this.executeRazorpayCheckout(intent, proposal, true, slot);
      });
    }

    const cancelBtn = slot.querySelector('.cancel-btn');
    if (cancelBtn) {
      cancelBtn.addEventListener('click', () => {
        cancelBtn.disabled = true;
        slot.insertAdjacentHTML(
          'beforeend',
          `<div class="p-3 bg-[#111210] rounded-lg border border-[#22231F] text-xs text-[#9A9991] mt-3">Transaction was cancelled by user.</div>`
        );
      });
    }

    // FIND COMPLIANT ALTERNATIVE Handler
    const findAltBtn = slot.querySelector('.find-alt-btn');
    if (findAltBtn) {
      findAltBtn.addEventListener('click', async () => {
        findAltBtn.disabled = true;
        findAltBtn.innerHTML = `
          <svg class="spin-active w-3.5 h-3.5 text-[#D6A94A]" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
          </svg>
          <span>Searching merchant catalog alternatives...</span>
        `;
        try {
          const newProposal = await this.callBuyerAgent(intent.intent_contract_id);
          this.currentProposal = newProposal;
          this.appendProposalCard(containerEl, newProposal);
          const newVerif = await this.callVerificationAgent(intent.intent_contract_id, newProposal.product_id, newProposal.quantity);
          this.currentVerification = newVerif;
          this.appendPolicyDecisionBlock(containerEl, intent, newProposal, newVerif);
        } catch (err) {
          slot.insertAdjacentHTML(
            'beforeend',
            `<div class="p-3 bg-[#C96A67]/10 text-xs text-[#C96A67] rounded-lg mt-3 font-mono-code">${err.message}</div>`
          );
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
      <div class="surface-card rounded-xl p-5 border-l-2 border-l-[#C96A67] bg-[#0C0D0C] animate-fade-in-up">
        <div class="flex items-center justify-between mb-3 pb-2 border-b border-[#22231F]">
          <span class="text-[10px] font-mono-code uppercase px-2 py-0.5 rounded bg-[#C96A67]/10 text-[#C96A67] border border-[#C96A67]/25">
            Intent Mismatch Detected
          </span>
          <span class="text-xs font-mono-code text-[#C96A67]">Autonomous Payment Intercepted</span>
        </div>

        <div class="grid grid-cols-3 gap-3 my-4 p-3 bg-[#111210] rounded-lg border border-[#22231F] text-center text-xs">
          <div>
            <div class="text-[10px] font-mono-code text-[#9A9991] uppercase">Authorized Budget</div>
            <div class="font-mono-code text-[#D6A94A] font-semibold">₹${intent.max_budget.toLocaleString('en-IN')} MAX</div>
          </div>
          <div>
            <div class="text-[10px] font-mono-code text-[#9A9991] uppercase">Proposed Total</div>
            <div class="font-mono-code text-[#C96A67] font-semibold">₹${proposal.final_amount.toLocaleString('en-IN')}</div>
          </div>
          <div>
            <div class="text-[10px] font-mono-code text-[#9A9991] uppercase">Over-Budget</div>
            <div class="font-mono-code text-[#C96A67] font-semibold">+${formattedDiff}</div>
          </div>
        </div>

        <p class="text-xs text-[#9A9991] leading-relaxed mb-4">
          PayGuard prevented the candidate selection from becoming an unauthorized payment:
          <span class="text-[#F3F0E8] font-mono-code block mt-1">${(proposal.drift_reasons || []).join(' · ')}</span>
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
      btn.innerHTML = `
        <svg class="spin-active w-3.5 h-3.5 text-[#080908]" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
        </svg>
        <span>Searching compliant alternative...</span>
      `;
      try {
        const altProposal = await this.callBuyerAgent(intent.intent_contract_id);
        this.currentProposal = altProposal;
        this.appendProposalCard(containerEl, altProposal);
        const verif = await this.callVerificationAgent(intent.intent_contract_id, altProposal.product_id, altProposal.quantity);
        this.currentVerification = verif;
        this.appendPolicyDecisionBlock(containerEl, intent, altProposal, verif);
      } catch (err) {
        slot.insertAdjacentHTML(
          'beforeend',
          `<div class="p-3 bg-[#C96A67]/10 text-xs text-[#C96A67] rounded-lg mt-3 font-mono-code">${err.message}</div>`
        );
      }
    });
  }

  // --- Real Razorpay Test Mode Checkout ---

  async executeRazorpayCheckout(intent, proposal, userConfirmed, slotEl) {
    const pipelineEl = slotEl.closest('[id^="pipeline-"]');
    const pipelineId = pipelineEl ? pipelineEl.id : null;

    if (pipelineId) {
      this.updatePipelineStep(pipelineId, 'payment', 'active', 'Creating Razorpay Test order...');
    }

    const payStateId = `pay-state-${Date.now()}`;
    const payStateHtml = `
      <div id="${payStateId}" class="surface-card rounded-xl p-5 border border-[#1688D4]/30 bg-[#0C0D0C] animate-fade-in-up mt-4">
        <div class="flex items-center justify-between mb-3">
          <div class="flex items-center space-x-2">
            <span class="w-2 h-2 rounded-full bg-[#1688D4] animate-ping"></span>
            <span class="text-xs font-mono-code uppercase text-[#1688D4]">Payment Agent Initiating Order</span>
          </div>
          <span class="text-[10px] font-mono-code text-[#D6A94A] bg-[#D6A94A]/10 px-2 py-0.5 rounded border border-[#D6A94A]/20">
            Razorpay Test Mode
          </span>
        </div>
        <div class="text-xs text-[#9A9991] leading-relaxed pay-status-text">
          Creating order for ₹${proposal.final_amount.toLocaleString('en-IN')} using server-side credentials...
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
          Order created: <span class="font-mono-code text-[#F3F0E8]">${orderData.razorpay_order_id}</span>. Opening Razorpay Test Checkout...
        `;
      }

      if (typeof window.Razorpay === 'undefined') {
        throw new Error('Razorpay SDK failed to load. Please check your internet connectivity.');
      }

      const rzpOptions = {
        key: orderData.razorpay_key_id,
        amount: orderData.amount_in_paise,
        currency: orderData.currency || 'INR',
        name: 'PayGuard Autonomous Buyer',
        description: `Verified Purchase: ${proposal.product_name}`,
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
            <div class="flex items-center space-x-2 text-xs text-[#1688D4] p-3">
              <svg class="spin-active w-4 h-4" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
              </svg>
              <span>Verifying HMAC SHA256 cryptographic payment signature with backend...</span>
            </div>
          `;

          try {
            const verifyRes = await this.callVerifyPaymentSignature(
              orderData.transaction_id,
              response.razorpay_order_id,
              response.razorpay_payment_id,
              response.razorpay_signature
            );

            if (pipelineId) {
              this.updatePipelineStep(pipelineId, 'payment', 'done', `Verified (${response.razorpay_payment_id})`);
            }

            this.renderPaymentSuccess(payBox, intent, proposal, orderData, response, verifyRes);
          } catch (verifErr) {
            if (pipelineId) {
              this.updatePipelineStep(pipelineId, 'payment', 'fail', 'Signature Failed');
            }
            this.renderPaymentFailure(payBox, verifErr.message);
          }
        },
        modal: {
          ondismiss: () => {
            if (payBox) {
              payBox.innerHTML = `
                <div class="text-xs text-[#CFA64D] p-3 rounded bg-[#CFA64D]/10 border border-[#CFA64D]/25 flex items-center justify-between">
                  <span>Payment checkout was dismissed by user.</span>
                  <button class="text-[11px] font-mono-code underline ml-2 retry-btn text-[#F3F0E8]">Retry Payment</button>
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
        if (pipelineId) {
          this.updatePipelineStep(pipelineId, 'payment', 'fail', 'Payment Failed');
        }
        this.renderPaymentFailure(payBox, failResponse.error.description || 'Payment rejected by gateway.');
      });
      rzpInstance.open();

    } catch (err) {
      console.error('Payment checkout error:', err);
      if (pipelineId) {
        this.updatePipelineStep(pipelineId, 'payment', 'fail', 'Order Creation Error');
      }
      this.renderPaymentFailure(payBox, err.message);
    }
  }

  async renderPaymentSuccess(containerEl, intent, proposal, orderData, rzpData, verifyData) {
    const formattedAmount = new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 2,
    }).format(orderData.amount);

    containerEl.className = 'surface-card rounded-xl p-6 border border-[#62AA78]/40 bg-[#0C0D0C] animate-fade-in-up mt-4 space-y-5';
    containerEl.innerHTML = `
      <!-- Success Header -->
      <div class="flex items-center justify-between pb-3 border-b border-[#22231F]">
        <div class="flex items-center space-x-3">
          <div class="w-8 h-8 rounded-full bg-[#62AA78]/20 flex items-center justify-center text-[#62AA78] text-base font-bold">
            ✓
          </div>
          <div>
            <h4 class="font-serif-display text-lg font-semibold text-[#F3F0E8]">
              PAYMENT VERIFIED
            </h4>
            <p class="text-xs text-[#62AA78] font-mono-code uppercase tracking-wider">
              Cryptographic HMAC SHA256 Signature Confirmed
            </p>
          </div>
        </div>
        <span class="text-[10px] font-mono-code text-[#D6A94A] bg-[#D6A94A]/10 px-2.5 py-1 rounded border border-[#D6A94A]/25">
          STATUS: COMPLETED
        </span>
      </div>

      <!-- Transaction Details Grid -->
      <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs p-3.5 bg-[#111210] rounded-lg border border-[#22231F]">
        <div>
          <div class="text-[10px] font-mono-code text-[#64635D] uppercase">Amount Settled</div>
          <div class="font-mono-code text-sm font-bold text-[#F3F0E8]">${formattedAmount}</div>
        </div>
        <div>
          <div class="text-[10px] font-mono-code text-[#64635D] uppercase">DB Transaction</div>
          <div class="font-mono-code text-xs text-[#F3F0E8]">#TX-${verifyData.transaction_id}</div>
        </div>
        <div>
          <div class="text-[10px] font-mono-code text-[#64635D] uppercase">Razorpay Order ID</div>
          <div class="font-mono-code text-[11px] text-[#9A9991] truncate" title="${rzpData.razorpay_order_id}">
            ${rzpData.razorpay_order_id}
          </div>
        </div>
        <div>
          <div class="text-[10px] font-mono-code text-[#64635D] uppercase">Payment Reference</div>
          <div class="font-mono-code text-[11px] text-[#62AA78] truncate" title="${rzpData.razorpay_payment_id}">
            ${rzpData.razorpay_payment_id}
          </div>
        </div>
      </div>

      <!-- Collapsible 1: Agent Activity Timeline -->
      <details class="group bg-[#111210] rounded-xl border border-[#22231F] overflow-hidden transition">
        <summary class="flex items-center justify-between p-3.5 cursor-pointer text-xs font-mono-code text-[#F3F0E8] select-none hover:text-[#D6A94A]">
          <span class="flex items-center space-x-2">
            <span class="w-2 h-2 rounded-full bg-[#1688D4]"></span>
            <span>Agent Activity Timeline (Completed Session)</span>
          </span>
          <svg class="w-4 h-4 text-[#9A9991] transform group-open:rotate-180 transition" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
          </svg>
        </summary>
        <div class="p-4 pt-1 text-xs text-[#9A9991] border-t border-[#22231F] space-y-3 font-mono-code">
          <div class="flex items-start space-x-2">
            <span class="text-[#62AA78]">✓</span>
            <div><strong class="text-[#F3F0E8]">Intent Agent:</strong> Contract #${intent.intent_contract_id} created for category "${intent.product_type}" under max budget ₹${intent.max_budget.toLocaleString('en-IN')}.</div>
          </div>
          <div class="flex items-start space-x-2">
            <span class="text-[#62AA78]">✓</span>
            <div><strong class="text-[#F3F0E8]">Buyer Agent:</strong> Selected product "${proposal.product_name}" (#${proposal.product_id}) after evaluating ${proposal.attempts_count} candidate(s).</div>
          </div>
          <div class="flex items-start space-x-2">
            <span class="text-[#62AA78]">✓</span>
            <div><strong class="text-[#F3F0E8]">Verification Agent:</strong> All 5 validation checks passed with calculated final payable amount of ${formattedAmount}.</div>
          </div>
          <div class="flex items-start space-x-2">
            <span class="text-[#62AA78]">✓</span>
            <div><strong class="text-[#F3F0E8]">Policy Engine:</strong> Policy decision APPROVED. Autonomous clearance granted.</div>
          </div>
          <div class="flex items-start space-x-2">
            <span class="text-[#62AA78]">✓</span>
            <div><strong class="text-[#F3F0E8]">Payment Agent:</strong> Razorpay order ${rzpData.razorpay_order_id} created and payment signature verified.</div>
          </div>
        </div>
      </details>

      <!-- Collapsible 2: Live PostgreSQL Audit Trail for this Transaction -->
      <details class="group bg-[#111210] rounded-xl border border-[#22231F] overflow-hidden transition" id="inline-audit-details">
        <summary class="flex items-center justify-between p-3.5 cursor-pointer text-xs font-mono-code text-[#F3F0E8] select-none hover:text-[#D6A94A]">
          <span class="flex items-center space-x-2">
            <span class="w-2 h-2 rounded-full bg-[#D6A94A]"></span>
            <span>Immutable Audit Trail (Real PostgreSQL Records)</span>
          </span>
          <svg class="w-4 h-4 text-[#9A9991] transform group-open:rotate-180 transition" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
          </svg>
        </summary>
        <div class="p-4 pt-1 text-xs border-t border-[#22231F] space-y-2.5 inline-audit-content">
          <div class="text-[11px] text-[#64635D] font-mono-code">Loading latest audit events...</div>
        </div>
      </details>

      <div class="flex items-center justify-between text-xs pt-2">
        <span class="text-[#9A9991]">Purchase successfully fulfilled within your Intent Contract.</span>
        <button class="btn-gold px-5 py-2 rounded-xl text-xs font-semibold tracking-wider flex items-center space-x-1.5 restart-agent-btn">
          <span>START NEW PURCHASE</span>
        </button>
      </div>
    `;

    // Load PostgreSQL audit records for the inline audit drawer
    const auditDetails = containerEl.querySelector('#inline-audit-details');
    auditDetails?.addEventListener('toggle', async () => {
      if (auditDetails.open) {
        const contentEl = auditDetails.querySelector('.inline-audit-content');
        if (!contentEl) return;
        try {
          const logs = await this.fetchLiveAuditLogs(10);
          if (!logs || logs.length === 0) {
            contentEl.innerHTML = `<div class="text-[#64635D] font-mono-code">No audit logs found.</div>`;
            return;
          }
          contentEl.innerHTML = logs
            .map((log) => `
              <div class="p-2 rounded bg-[#0C0D0C] border border-[#22231F] text-xs font-mono-code space-y-1">
                <div class="flex items-center justify-between text-[10px] text-[#64635D]">
                  <span class="text-[#D6A94A] font-semibold">${log.agent}</span>
                  <span>${log.timestamp}</span>
                </div>
                <div class="text-[#F3F0E8] font-medium">${log.action} · <span class="${['SUCCESS', 'APPROVED', 'PASS', 'COMPLETED'].includes(log.decision?.toUpperCase()) ? 'text-[#62AA78]' : 'text-[#CFA64D]'}">${log.decision}</span></div>
                <div class="text-[11px] text-[#9A9991] font-sans">${this.escapeHtml(log.reason || '')}</div>
              </div>
            `)
            .join('');
        } catch (e) {
          contentEl.innerHTML = `<div class="text-[#C96A67] font-mono-code">Failed to load audit logs: ${e.message}</div>`;
        }
      }
    });

    containerEl.querySelector('.restart-agent-btn')?.addEventListener('click', () => {
      if (this.dom.chatContainer) this.dom.chatContainer.classList.add('hidden');
      if (this.dom.chatStream) this.dom.chatStream.innerHTML = '';
      window.scrollTo({ top: document.getElementById('live-agent').offsetTop - 60, behavior: 'smooth' });
    });
  }

  renderPaymentFailure(containerEl, errorMsg) {
    containerEl.className = 'surface-card rounded-xl p-5 border border-[#C96A67]/40 bg-[#0C0D0C] animate-fade-in-up mt-4';
    containerEl.innerHTML = `
      <div class="flex items-center space-x-2 text-[#C96A67] mb-2 font-semibold text-sm">
        <span>⊘</span>
        <span>Payment Could Not Be Completed</span>
      </div>
      <p class="text-xs text-[#9A9991] leading-relaxed mb-3">
        ${this.escapeHtml(errorMsg)}
      </p>
      <div class="text-[11px] font-mono-code text-[#64635D] bg-[#111210] p-2.5 rounded border border-[#22231F]">
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
      <div class="flex items-center justify-center p-8 text-xs text-[#9A9991]">
        <svg class="spin-active w-4 h-4 text-[#D6A94A] mr-2" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
        </svg>
        <span>Loading PostgreSQL audit logs...</span>
      </div>
    `;

    try {
      const logs = await this.fetchLiveAuditLogs(25);

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
            ? 'text-[#62AA78] bg-[#62AA78]/10 border-[#62AA78]/25' 
            : isWarning 
            ? 'text-[#CFA64D] bg-[#CFA64D]/10 border-[#CFA64D]/25' 
            : 'text-[#C96A67] bg-[#C96A67]/10 border-[#C96A67]/25';

          return `
            <div class="relative pl-6 pb-6 border-l border-[#22231F] last:border-l-0">
              <div class="absolute -left-[5px] top-1 w-2.5 h-2.5 rounded-full ${isSuccess ? 'bg-[#62AA78]' : isWarning ? 'bg-[#CFA64D]' : 'bg-[#C96A67]'}"></div>
              <div class="flex items-center justify-between text-[10px] font-mono-code text-[#64635D] mb-1">
                <span>${log.timestamp}</span>
                <span class="px-2 py-0.5 rounded border text-[9px] font-semibold ${badgeClass}">
                  ${log.decision}
                </span>
              </div>
              <div class="text-xs font-semibold text-[#F3F0E8] mb-0.5">
                <span class="text-[#D6A94A] font-mono-code text-[11px]">${log.agent}</span> → ${log.action}
              </div>
              <p class="text-xs text-[#9A9991] leading-relaxed bg-[#111210] p-2.5 rounded border border-[#22231F]/80 mt-1.5">
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
    if (this.dom.auditDrawer) this.dom.auditDrawer.classList.add('translate-x-full');
  }

  async openPoliciesModal() {
    if (!this.dom.policiesModal || !this.dom.policiesContent) return;
    this.dom.policiesModal.classList.remove('hidden');

    try {
      const res = await fetch(`${this.apiBase}/api/policies`);
      const policy = await res.json();

      const formatInr = (val) =>
        new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(val);

      this.dom.policiesContent.innerHTML = `
        <div class="space-y-4 text-xs font-mono-code">
          <div class="p-3.5 rounded-xl bg-[#111210] border border-[#22231F] flex items-center justify-between">
            <span class="text-[#9A9991]">Max Single Transaction Limit:</span>
            <span class="text-[#F3F0E8] font-semibold">${formatInr(policy.max_transaction_amount)}</span>
          </div>
          <div class="p-3.5 rounded-xl bg-[#111210] border border-[#22231F] flex items-center justify-between">
            <span class="text-[#9A9991]">High-Value Policy Threshold:</span>
            <span class="text-[#D6A94A] font-semibold">${formatInr(policy.high_value_threshold)}</span>
          </div>
          <div class="p-3.5 rounded-xl bg-[#111210] border border-[#22231F] flex items-center justify-between">
            <span class="text-[#9A9991]">Max Automated Retry Attempts:</span>
            <span class="text-[#F3F0E8] font-semibold">${policy.max_automated_retries} attempts</span>
          </div>
          <div class="p-3.5 rounded-xl bg-[#111210] border border-[#22231F] flex items-center justify-between">
            <span class="text-[#9A9991]">Duplicate Purchase Intercept:</span>
            <span class="text-[#62AA78] font-semibold">${policy.duplicate_purchase_block ? 'ENABLED' : 'DISABLED'}</span>
          </div>
        </div>
      `;
    } catch (err) {
      this.dom.policiesContent.innerHTML = `
        <div class="p-4 bg-[#C96A67]/10 text-xs text-[#C96A67] rounded-lg">
          Failed to load policies: ${err.message}
        </div>
      `;
    }
  }

  closePoliciesModal() {
    if (this.dom.policiesModal) this.dom.policiesModal.classList.add('hidden');
  }

  escapeHtml(str) {
    if (typeof str !== 'string') return '';
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }
}

// Instantiate application on DOM ready
document.addEventListener('DOMContentLoaded', () => {
  window.payguard = new PayGuardApp();
});
