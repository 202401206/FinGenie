/**
 * FinGenie Login Screen Component
 * Split-screen layout: Left Brand KPI Hero & Right Clean Supabase Auth Form
 */

export function renderLoginPage({ error = '', isLoading = false, defaultEmail = 'demo@fingenie.app' }) {
  return `
    <div class="fg-login-page" style="
      display: flex;
      min-height: 100vh;
      width: 100%;
      background: var(--fg-pure-white);
    ">
      <!-- Left Panel: Deep Forest Green Brand Showcase -->
      <div style="
        flex: 1;
        background: linear-gradient(145deg, var(--fg-forest-green) 0%, #0B1B15 100%);
        color: white;
        padding: 56px 64px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        position: relative;
        overflow: hidden;
      ">
        <!-- Abstract financial trajectory background lines -->
        <div style="
          position: absolute;
          top: -100px;
          right: -100px;
          width: 400px;
          height: 400px;
          border-radius: 50%;
          background: radial-gradient(circle, rgba(29, 138, 96, 0.25) 0%, transparent 70%);
          pointer-events: none;
        "></div>

        <!-- Brand Top Logo -->
        <div style="display: flex; align-items: center; gap: 12px; z-index: 2;">
          <div style="
            width: 42px;
            height: 42px;
            background: var(--fg-emerald-green);
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 4px 12px rgba(29, 138, 96, 0.4);
          ">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="22 7 13.5 15.5 8.5 10.5 2 17"></polyline>
              <polyline points="16 7 22 7 22 13"></polyline>
            </svg>
          </div>
          <div>
            <div style="font-size: 22px; font-weight: 700; letter-spacing: -0.5px; color: white;">FinGenie</div>
            <div style="font-size: 11px; color: var(--fg-pale-mint); letter-spacing: 0.6px; font-weight: 500;">FINANCIAL INTELLIGENCE</div>
          </div>
        </div>

        <!-- Center Value Proposition & Floating KPI Showcase -->
        <div style="z-index: 2; max-width: 480px; margin: 40px 0;">
          <div style="
            display: inline-flex;
            align-items: center;
            gap: 8px;
            background: rgba(231, 244, 236, 0.12);
            border: 1px solid rgba(29, 138, 96, 0.35);
            padding: 6px 14px;
            border-radius: var(--radius-pill);
            font-size: 12px;
            color: var(--fg-pale-mint);
            margin-bottom: 24px;
          ">
            <span style="width: 6px; height: 6px; border-radius: 50%; background: var(--fg-emerald-green);"></span>
            Engineered for Indian Bank Statements (CSV/XLSX)
          </div>

          <h2 style="font-size: 36px; line-height: 1.2; font-weight: 700; margin: 0 0 16px 0; color: #FFFFFF; letter-spacing: -0.8px;">
            Your finances, <br /><span style="color: #4ADE80;">finally in focus.</span>
          </h2>

          <p style="font-size: 15px; color: #B3C2B9; line-height: 1.6; margin: 0 0 36px 0;">
            Turn raw statement narrations, UPI debits, and balance sheets into traceable intelligence, automated categorizations, and interactive conversational answers.
          </p>

          <!-- Floating Metric Cards Preview -->
          <div style="
            background: rgba(255, 255, 255, 0.06);
            backdrop-filter: blur(12px);
            border: 1px solid rgba(255, 255, 255, 0.12);
            border-radius: var(--radius-card);
            padding: 20px 24px;
            display: flex;
            flex-direction: column;
            gap: 16px;
          ">
            <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(255, 255, 255, 0.08); padding-bottom: 12px;">
              <div>
                <div style="font-size: 11px; text-transform: uppercase; color: #94A3B8; letter-spacing: 0.5px;">OCTOBER NET INFLOW</div>
                <div style="font-size: 22px; font-weight: 700; color: white; margin-top: 2px;">₹1,25,000.00</div>
              </div>
              <div style="background: rgba(34, 197, 94, 0.18); color: #4ADE80; font-size: 12px; font-weight: 600; padding: 4px 10px; border-radius: var(--radius-pill);">
                +14.2% vs Sep
              </div>
            </div>

            <div style="display: flex; align-items: center; gap: 12px; font-size: 13px; color: #E2E8F0;">
              <div style="width: 28px; height: 28px; border-radius: 50%; background: rgba(29, 138, 96, 0.3); display: flex; align-items: center; justify-content: center; color: #4ADE80;">
                ✓
              </div>
              <div>
                <span style="font-weight: 600;">142 UPI & IMPS Transactions</span> classified with 100% source provenance.
              </div>
            </div>
          </div>
        </div>

        <!-- Security Reassurance -->
        <div style="display: flex; align-items: center; gap: 12px; color: #8FA297; font-size: 12px; z-index: 2;">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
            <path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
          </svg>
          <span>Bank-grade 256-bit encryption. Zero storage of bank credentials.</span>
        </div>
      </div>

      <!-- Right Panel: Supabase Login Form -->
      <div style="
        flex: 1;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 48px;
        background: var(--fg-pure-white);
      ">
        <div style="width: 100%; max-width: 420px;">
          <div style="margin-bottom: 32px;">
            <h2 style="font-size: 26px; font-weight: 700; color: var(--fg-charcoal); margin: 0 0 8px 0; letter-spacing: -0.5px;">
              Welcome back
            </h2>
            <p style="margin: 0; font-size: 14px; color: var(--fg-muted-grey);">
              Enter your credentials to access your financial dashboard
            </p>
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
              display: flex;
              align-items: center;
              gap: 8px;
            ">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="10"></circle>
                <line x1="12" y1="8" x2="12" y2="12"></line>
                <line x1="12" y1="16" x2="12.01" y2="16"></line>
              </svg>
              <span>${error}</span>
            </div>
          ` : ''}

          <form id="fg-login-form" onsubmit="event.preventDefault(); window.fgSubmitLogin();" style="display: flex; flex-direction: column; gap: 20px;">
            <!-- Email Field -->
            <div>
              <label for="login-email" style="display: block; font-size: 13px; font-weight: 600; color: var(--fg-charcoal); margin-bottom: 6px;">
                Email Address
              </label>
              <input 
                type="email" 
                id="login-email" 
                value="${defaultEmail}" 
                placeholder="name@company.com" 
                required
                style="
                  width: 100%;
                  box-sizing: border-box;
                  padding: 11px 14px;
                  border: 1px solid var(--fg-light-grey-green);
                  border-radius: var(--radius-md);
                  font-size: 14px;
                  color: var(--fg-charcoal);
                  outline: none;
                  transition: border-color var(--transition-fast);
                "
                onfocus="this.style.borderColor='var(--fg-emerald-green)'"
                onblur="this.style.borderColor='var(--fg-light-grey-green)'"
              />
            </div>

            <!-- Password Field with Show/Hide -->
            <div>
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                <label for="login-password" style="font-size: 13px; font-weight: 600; color: var(--fg-charcoal);">
                  Password
                </label>
                <a href="javascript:void(0)" onclick="window.fgNavigate('forgot-password')" style="font-size: 12px; color: var(--fg-emerald-green); text-decoration: none; font-weight: 500;">
                  Forgot password?
                </a>
              </div>
              <div style="position: relative;">
                <input 
                  type="password" 
                  id="login-password" 
                  value="Password@123" 
                  placeholder="••••••••" 
                  required
                  style="
                    width: 100%;
                    box-sizing: border-box;
                    padding: 11px 40px 11px 14px;
                    border: 1px solid var(--fg-light-grey-green);
                    border-radius: var(--radius-md);
                    font-size: 14px;
                    color: var(--fg-charcoal);
                    outline: none;
                    transition: border-color var(--transition-fast);
                  "
                  onfocus="this.style.borderColor='var(--fg-emerald-green)'"
                  onblur="this.style.borderColor='var(--fg-light-grey-green)'"
                />
                <button 
                  type="button" 
                  onclick="window.fgTogglePassword('login-password', this)" 
                  style="
                    position: absolute;
                    right: 12px;
                    top: 12px;
                    background: none;
                    border: none;
                    color: var(--fg-muted-grey);
                    cursor: pointer;
                    padding: 0;
                  "
                  title="Show/Hide Password"
                >
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                    <circle cx="12" cy="12" r="3"></circle>
                  </svg>
                </button>
              </div>
            </div>

            <!-- Remember Me -->
            <div style="display: flex; align-items: center; gap: 8px;">
              <input type="checkbox" id="login-remember" checked style="accent-color: var(--fg-emerald-green); cursor: pointer;" />
              <label for="login-remember" style="font-size: 13px; color: var(--fg-muted-grey); cursor: pointer;">
                Remember my session for 30 days
              </label>
            </div>

            <!-- Primary Login Button -->
            <button 
              type="submit" 
              class="fg-btn-primary" 
              ${isLoading ? 'disabled' : ''}
              style="
                width: 100%;
                background: var(--fg-forest-green);
                color: white;
                border: none;
                padding: 12px;
                border-radius: var(--radius-md);
                font-size: 14px;
                font-weight: 600;
                cursor: pointer;
                transition: background var(--transition-fast);
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 8px;
              "
              onmouseover="this.style.background='var(--fg-emerald-green)'"
              onmouseout="this.style.background='var(--fg-forest-green)'"
            >
              ${isLoading ? 'Signing in securely...' : 'Log in to FinGenie'}
            </button>

            <!-- Social / Google Option -->
            <div style="text-align: center; position: relative; margin: 8px 0;">
              <hr style="border: none; border-top: 1px solid var(--fg-light-grey-green);" />
              <span style="position: absolute; top: -10px; left: 50%; transform: translateX(-50%); background: white; padding: 0 12px; font-size: 12px; color: var(--fg-muted-grey);">
                or continue with
              </span>
            </div>

            <button 
              type="button" 
              onclick="window.fgLoginWithGoogle()"
              style="
                width: 100%;
                background: white;
                border: 1px solid var(--fg-light-grey-green);
                border-radius: var(--radius-md);
                padding: 10px;
                font-size: 13px;
                font-weight: 500;
                color: var(--fg-charcoal);
                cursor: pointer;
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 10px;
                transition: background var(--transition-fast);
              "
              onmouseover="this.style.background='var(--fg-warm-white)'"
              onmouseout="this.style.background='white'"
            >
              <svg width="18" height="18" viewBox="0 0 24 24">
                <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"/>
                <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"/>
              </svg>
              <span>Continue with Google</span>
            </button>
          </form>

          <!-- Sign-up Redirect Link -->
          <div style="margin-top: 28px; text-align: center; font-size: 13px; color: var(--fg-muted-grey);">
            Don't have an account yet? 
            <a href="javascript:void(0)" onclick="window.fgNavigate('signup')" style="color: var(--fg-emerald-green); font-weight: 600; text-decoration: none; margin-left: 4px;">
              Create an account
            </a>
          </div>
        </div>
      </div>
    </div>
  `;
}
