/**
 * FinGenie Multi-Step Sign-Up & Indian Bank Onboarding Component
 * Step 1: Account Creation
 * Step 2: Account Type (Personal vs Business)
 * Step 3: Searchable Indian Bank Selection (SBI, HDFC, ICICI, Axis, Kotak, BOB, etc.)
 * Step 4: Finish Onboarding & Workspace Access
 */

import { INDIAN_BANKS } from '../../services/authService.js';

export function renderSignUpPage({
  step = 1,
  formData = {},
  selectedAccountType = 'personal',
  selectedBankId = 'hdfc',
  bankSearchQuery = '',
  error = '',
  isLoading = false
}) {
  const filteredBanks = INDIAN_BANKS.filter(b => 
    b.name.toLowerCase().includes((bankSearchQuery || '').toLowerCase()) ||
    b.shortCode.toLowerCase().includes((bankSearchQuery || '').toLowerCase())
  );

  return `
    <div class="fg-signup-page" style="
      min-height: 100vh;
      width: 100%;
      background: var(--fg-warm-white);
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 40px 20px;
      box-sizing: border-box;
    ">
      <!-- Top Brand Header -->
      <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 32px; cursor: pointer;" onclick="window.fgNavigate('login')">
        <div style="
          width: 36px;
          height: 36px;
          background: linear-gradient(135deg, var(--fg-forest-green) 0%, var(--fg-emerald-green) 100%);
          border-radius: 10px;
          display: flex;
          align-items: center;
          justify-content: center;
          color: white;
          box-shadow: 0 4px 10px rgba(29, 138, 96, 0.25);
        ">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="22 7 13.5 15.5 8.5 10.5 2 17"></polyline>
            <polyline points="16 7 22 7 22 13"></polyline>
          </svg>
        </div>
        <span style="font-size: 20px; font-weight: 700; color: var(--fg-forest-green); letter-spacing: -0.5px;">FinGenie</span>
      </div>

      <!-- Main Onboarding Modal Card -->
      <div class="fg-card" style="
        width: 100%;
        max-width: 580px;
        padding: 40px;
        box-sizing: border-box;
        border-radius: var(--radius-card);
      ">
        <!-- Progress Stepper (Steps 1 to 4) -->
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 32px;">
          ${[
            { num: 1, label: 'Account' },
            { num: 2, label: 'Account Type' },
            { num: 3, label: 'Select Bank' },
            { num: 4, label: 'Ready' }
          ].map((s, idx) => `
            <div style="display: flex; align-items: center; gap: 8px;">
              <div style="
                width: 28px;
                height: 28px;
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 12px;
                font-weight: 700;
                background: ${step > s.num ? 'var(--fg-emerald-green)' : step === s.num ? 'var(--fg-forest-green)' : 'var(--fg-warm-white)'};
                color: ${step >= s.num ? 'white' : 'var(--fg-muted-grey)'};
                border: 1px solid ${step >= s.num ? 'transparent' : 'var(--fg-light-grey-green)'};
                transition: all var(--transition-fast);
              ">
                ${step > s.num ? '✓' : s.num}
              </div>
              <span style="
                font-size: 12px;
                font-weight: ${step === s.num ? '600' : '500'};
                color: ${step === s.num ? 'var(--fg-charcoal)' : 'var(--fg-muted-grey)'};
                display: ${idx === 3 ? 'inline' : 'inline'};
              ">
                ${s.label}
              </span>
            </div>
            ${idx < 3 ? `
              <div style="
                flex: 1;
                height: 2px;
                background: ${step > s.num ? 'var(--fg-emerald-green)' : 'var(--fg-light-grey-green)'};
                margin: 0 8px;
              "></div>
            ` : ''}
          `).join('')}
        </div>

        ${error ? `
          <div style="
            background: var(--fg-soft-red-light);
            border: 1px solid rgba(201, 76, 76, 0.3);
            color: var(--fg-soft-red);
            padding: 12px 16px;
            border-radius: var(--radius-md);
            font-size: 13px;
            margin-bottom: 20px;
          ">
            ${error}
          </div>
        ` : ''}

        <!-- STEP 1: Account Creation Form -->
        ${step === 1 ? `
          <div>
            <h2 style="font-size: 22px; font-weight: 700; color: var(--fg-charcoal); margin: 0 0 6px 0;">Create your FinGenie account</h2>
            <p style="font-size: 14px; color: var(--fg-muted-grey); margin: 0 0 24px 0;">Start analyzing your Indian bank statements with complete privacy and intelligence.</p>

            <form id="fg-signup-step1" onsubmit="event.preventDefault(); window.fgSubmitSignUpStep1();" style="display: flex; flex-direction: column; gap: 16px;">
              <div>
                <label style="display: block; font-size: 13px; font-weight: 600; margin-bottom: 6px;">Full Name</label>
                <input type="text" id="su-fullname" value="${formData.fullName || ''}" placeholder="e.g. Aditya Sharma" required style="
                  width: 100%; box-sizing: border-box; padding: 10px 14px; border: 1px solid var(--fg-light-grey-green); border-radius: var(--radius-md); font-size: 14px; outline: none;
                " />
              </div>

              <div>
                <label style="display: block; font-size: 13px; font-weight: 600; margin-bottom: 6px;">Work or Personal Email</label>
                <input type="email" id="su-email" value="${formData.email || ''}" placeholder="aditya@example.com" required style="
                  width: 100%; box-sizing: border-box; padding: 10px 14px; border: 1px solid var(--fg-light-grey-green); border-radius: var(--radius-md); font-size: 14px; outline: none;
                " />
              </div>

              <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 14px;">
                <div>
                  <label style="display: block; font-size: 13px; font-weight: 600; margin-bottom: 6px;">Password</label>
                  <input type="password" id="su-password" value="${formData.password || ''}" placeholder="At least 8 chars" required style="
                    width: 100%; box-sizing: border-box; padding: 10px 14px; border: 1px solid var(--fg-light-grey-green); border-radius: var(--radius-md); font-size: 14px; outline: none;
                  " />
                </div>
                <div>
                  <label style="display: block; font-size: 13px; font-weight: 600; margin-bottom: 6px;">Confirm Password</label>
                  <input type="password" id="su-confirmpassword" value="${formData.confirmPassword || ''}" placeholder="Repeat password" required style="
                    width: 100%; box-sizing: border-box; padding: 10px 14px; border: 1px solid var(--fg-light-grey-green); border-radius: var(--radius-md); font-size: 14px; outline: none;
                  " />
                </div>
              </div>

              <div style="display: flex; align-items: flex-start; gap: 8px; margin-top: 4px;">
                <input type="checkbox" id="su-terms" checked style="accent-color: var(--fg-emerald-green); margin-top: 3px; cursor: pointer;" />
                <label for="su-terms" style="font-size: 12px; color: var(--fg-muted-grey); line-height: 1.4; cursor: pointer;">
                  I agree to FinGenie's Terms of Service and Privacy Policy. My data stays encrypted and confidential.
                </label>
              </div>

              <button type="submit" style="
                margin-top: 8px; width: 100%; background: var(--fg-forest-green); color: white; border: none; padding: 12px; border-radius: var(--radius-md); font-size: 14px; font-weight: 600; cursor: pointer; transition: background var(--transition-fast);
              " onmouseover="this.style.background='var(--fg-emerald-green)'" onmouseout="this.style.background='var(--fg-forest-green)'">
                Continue to Account Type →
              </button>
            </form>

            <div style="margin-top: 24px; text-align: center; font-size: 13px; color: var(--fg-muted-grey);">
              Already have an account? <a href="javascript:void(0)" onclick="window.fgNavigate('login')" style="color: var(--fg-emerald-green); font-weight: 600; text-decoration: none;">Log in</a>
            </div>
          </div>
        ` : ''}

        <!-- STEP 2: Choose Account Type -->
        ${step === 2 ? `
          <div>
            <h2 style="font-size: 22px; font-weight: 700; color: var(--fg-charcoal); margin: 0 0 6px 0;">Choose your account type</h2>
            <p style="font-size: 14px; color: var(--fg-muted-grey); margin: 0 0 24px 0;">Select how you plan to use FinGenie so we can tailor metrics and document slots.</p>

            <div style="display: flex; flex-direction: column; gap: 16px; margin-bottom: 28px;">
              <!-- Personal Card -->
              <div onclick="window.fgSelectAccountType('personal')" style="
                border: 2px solid ${selectedAccountType === 'personal' ? 'var(--fg-emerald-green)' : 'var(--fg-light-grey-green)'};
                background: ${selectedAccountType === 'personal' ? 'var(--fg-pale-mint)' : 'white'};
                border-radius: var(--radius-card);
                padding: 20px;
                cursor: pointer;
                display: flex;
                align-items: center;
                gap: 16px;
                transition: all var(--transition-fast);
              ">
                <div style="
                  width: 44px; height: 44px; border-radius: 10px; background: ${selectedAccountType === 'personal' ? 'var(--fg-emerald-green)' : 'var(--fg-warm-white)'}; color: ${selectedAccountType === 'personal' ? 'white' : 'var(--fg-charcoal)'}; display: flex; align-items: center; justify-content: center; flex-shrink: 0;
                ">
                  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
                    <circle cx="12" cy="7" r="4"></circle>
                  </svg>
                </div>
                <div style="flex: 1;">
                  <div style="display: flex; align-items: center; justify-content: space-between;">
                    <div style="font-weight: 700; font-size: 16px; color: var(--fg-charcoal);">Personal Account</div>
                    ${selectedAccountType === 'personal' ? `
                      <span style="color: var(--fg-emerald-green); font-weight: 700;">✓ Selected</span>
                    ` : ''}
                  </div>
                  <div style="font-size: 13px; color: var(--fg-muted-grey); margin-top: 4px;">
                    For individuals tracking personal cash flows, UPI expenses, investments, and bank statements.
                  </div>
                </div>
              </div>

              <!-- Business Card -->
              <div onclick="window.fgSelectAccountType('business')" style="
                border: 2px solid ${selectedAccountType === 'business' ? 'var(--fg-emerald-green)' : 'var(--fg-light-grey-green)'};
                background: ${selectedAccountType === 'business' ? 'var(--fg-pale-mint)' : 'white'};
                border-radius: var(--radius-card);
                padding: 20px;
                cursor: pointer;
                display: flex;
                align-items: center;
                gap: 16px;
                transition: all var(--transition-fast);
              ">
                <div style="
                  width: 44px; height: 44px; border-radius: 10px; background: ${selectedAccountType === 'business' ? 'var(--fg-emerald-green)' : 'var(--fg-warm-white)'}; color: ${selectedAccountType === 'business' ? 'white' : 'var(--fg-charcoal)'}; display: flex; align-items: center; justify-content: center; flex-shrink: 0;
                ">
                  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <rect x="2" y="7" width="20" height="14" rx="2" ry="2"></rect>
                    <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"></path>
                  </svg>
                </div>
                <div style="flex: 1;">
                  <div style="display: flex; align-items: center; justify-content: space-between;">
                    <div style="font-weight: 700; font-size: 16px; color: var(--fg-charcoal);">Small Business & Freelancer</div>
                    ${selectedAccountType === 'business' ? `
                      <span style="color: var(--fg-emerald-green); font-weight: 700;">✓ Selected</span>
                    ` : ''}
                  </div>
                  <div style="font-size: 13px; color: var(--fg-muted-grey); margin-top: 4px;">
                    For enterprises and proprietorships uploading bank statements and balance sheets for P&L analysis.
                  </div>
                </div>
              </div>
            </div>

            <div style="display: flex; gap: 12px;">
              <button onclick="window.fgGoToStep(1)" style="
                flex: 1; background: white; border: 1px solid var(--fg-light-grey-green); color: var(--fg-charcoal); padding: 12px; border-radius: var(--radius-md); font-size: 14px; font-weight: 600; cursor: pointer;
              ">
                ← Back
              </button>
              <button onclick="window.fgConfirmAccountType()" style="
                flex: 2; background: var(--fg-forest-green); color: white; border: none; padding: 12px; border-radius: var(--radius-md); font-size: 14px; font-weight: 600; cursor: pointer;
              ">
                Continue to Bank Selection →
              </button>
            </div>
          </div>
        ` : ''}

        <!-- STEP 3: Select Bank (Explicit & Searchable) -->
        ${step === 3 ? `
          <div>
            <h2 style="font-size: 22px; font-weight: 700; color: var(--fg-charcoal); margin: 0 0 6px 0;">Select your primary bank</h2>
            <p style="font-size: 14px; color: var(--fg-muted-grey); margin: 0 0 16px 0;">Choose the banking institution associated with your statement files for optimized parsing.</p>

            <!-- Important Clear Disclaimer per Specification -->
            <div style="
              background: #F8FAF9;
              border: 1px solid var(--fg-light-grey-green);
              border-radius: var(--radius-md);
              padding: 10px 14px;
              font-size: 12px;
              color: var(--fg-muted-grey);
              margin-bottom: 20px;
              display: flex;
              align-items: center;
              gap: 8px;
            ">
              <span style="color: var(--fg-emerald-green); font-weight: bold;">ℹ</span>
              <span>Selecting a bank identifies the institution format of your records. <strong>FinGenie does not connect to or link your live bank account.</strong></span>
            </div>

            <!-- Search Field -->
            <div style="position: relative; margin-bottom: 16px;">
              <input 
                type="text" 
                id="bank-search-input"
                placeholder="Search your bank (e.g. HDFC, SBI, ICICI, Axis...)" 
                value="${bankSearchQuery || ''}"
                oninput="window.fgFilterBanks(this.value)"
                style="
                  width: 100%; box-sizing: border-box; padding: 10px 14px 10px 36px; border: 1px solid var(--fg-light-grey-green); border-radius: var(--radius-md); font-size: 13px; outline: none;
                "
              />
              <svg style="position: absolute; left: 12px; top: 12px; color: var(--fg-muted-grey);" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="11" cy="11" r="8"></circle>
                <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
              </svg>
            </div>

            <!-- Bank Grid -->
            <div style="max-height: 240px; overflow-y: auto; display: flex; flex-direction: column; gap: 8px; margin-bottom: 24px; padding-right: 4px;">
              ${filteredBanks.map(b => `
                <div onclick="window.fgSelectBank('${b.id}')" style="
                  display: flex;
                  align-items: center;
                  justify-content: space-between;
                  padding: 12px 16px;
                  border: 1px solid ${selectedBankId === b.id ? 'var(--fg-emerald-green)' : 'var(--fg-light-grey-green)'};
                  background: ${selectedBankId === b.id ? 'var(--fg-pale-mint)' : 'white'};
                  border-radius: var(--radius-md);
                  cursor: pointer;
                  transition: all var(--transition-fast);
                ">
                  <div style="display: flex; align-items: center; gap: 12px;">
                    <div style="
                      width: 32px; height: 32px; border-radius: 8px; background: #EEF2F6; color: var(--fg-forest-green); font-size: 11px; font-weight: 700; display: flex; align-items: center; justify-content: center;
                    ">
                      ${b.shortCode}
                    </div>
                    <div>
                      <div style="font-size: 14px; font-weight: 600; color: var(--fg-charcoal);">${b.name}</div>
                      <div style="font-size: 11px; color: var(--fg-muted-grey);">${b.tagline}</div>
                    </div>
                  </div>

                  <div style="
                    width: 20px; height: 20px; border-radius: 50%; border: 2px solid ${selectedBankId === b.id ? 'var(--fg-emerald-green)' : 'var(--fg-light-grey-green)'}; display: flex; align-items: center; justify-content: center;
                  ">
                    ${selectedBankId === b.id ? `
                      <div style="width: 10px; height: 10px; border-radius: 50%; background: var(--fg-emerald-green);"></div>
                    ` : ''}
                  </div>
                </div>
              `).join('')}
            </div>

            <div style="display: flex; gap: 12px;">
              <button onclick="window.fgGoToStep(2)" style="
                flex: 1; background: white; border: 1px solid var(--fg-light-grey-green); color: var(--fg-charcoal); padding: 12px; border-radius: var(--radius-md); font-size: 14px; font-weight: 600; cursor: pointer;
              ">
                ← Back
              </button>
              <button onclick="window.fgConfirmBankSelection()" style="
                flex: 2; background: var(--fg-forest-green); color: white; border: none; padding: 12px; border-radius: var(--radius-md); font-size: 14px; font-weight: 600; cursor: pointer;
              ">
                Confirm & Complete Onboarding →
              </button>
            </div>
          </div>
        ` : ''}

        <!-- STEP 4: Finish Onboarding Success -->
        ${step === 4 ? `
          <div style="text-align: center; padding: 20px 0;">
            <div style="
              width: 64px; height: 64px; border-radius: 50%; background: var(--fg-pale-mint); color: var(--fg-emerald-green); display: flex; align-items: center; justify-content: center; margin: 0 auto 20px auto;
            ">
              <svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="20 6 9 17 4 12"></polyline>
              </svg>
            </div>

            <h2 style="font-size: 24px; font-weight: 700; color: var(--fg-charcoal); margin: 0 0 8px 0;">Account ready!</h2>
            <p style="font-size: 14px; color: var(--fg-muted-grey); margin: 0 0 24px 0; line-height: 1.5;">
              Your profile is verified. You can now explore your financial ledger, inspect UPI transactions, or upload bank statement files.
            </p>

            <button onclick="window.fgGoToDashboard()" style="
              width: 100%; background: var(--fg-emerald-green); color: white; border: none; padding: 13px; border-radius: var(--radius-md); font-size: 15px; font-weight: 600; cursor: pointer; box-shadow: 0 2px 8px rgba(29, 138, 96, 0.3);
            ">
              Open Financial Ledger & Dashboard →
            </button>
          </div>
        ` : ''}
      </div>
    </div>
  `;
}
