/**
 * Supabase Client & Local Mock State Manager
 * FinGenie Fintech Application
 */

const getEnv = (key) => {
  if (typeof process !== 'undefined' && process.env && process.env[key]) {
    return process.env[key];
  }
  if (typeof window !== 'undefined' && window.__ENV__ && window.__ENV__[key]) {
    return window.__ENV__[key];
  }
  return null;
};

const supabaseUrl = getEnv('VITE_SUPABASE_URL') || getEnv('SUPABASE_URL');
const supabaseAnonKey = getEnv('VITE_SUPABASE_ANON_KEY') || getEnv('SUPABASE_ANON_KEY');

// In-memory mock store for test runs and preview without live cloud credentials
const mockStore = {
  session: null,
  users: [
    {
      id: 'usr-fingenie-demo-001',
      email: 'demo@fingenie.app',
      password: 'Password@123',
      profile: {
        id: 'usr-fingenie-demo-001',
        full_name: 'Aditya Sharma',
        account_type: 'personal',
        bank_id: 'hdfc',
        bank_name: 'HDFC Bank',
        onboarding_completed: true,
      }
    }
  ],
  transactions: [
    {
      id: 'tx-101',
      user_id: 'usr-fingenie-demo-001',
      date: '2026-10-24',
      description: 'UPI/Zomato Media Ltd/Order-94821/AxisBank',
      category: 'Dining',
      type: 'debit',
      payment_method: 'UPI',
      amount: 649.00,
      balance: 142350.50,
      source_file: 'HDFC_Statement_Oct2026.csv',
      source_row: 142,
      ai_inferred: true
    },
    {
      id: 'tx-102',
      user_id: 'usr-fingenie-demo-001',
      date: '2026-10-22',
      description: 'TCS LTD / OCT SALARY / CMS NEFT 883921',
      category: 'Salary',
      type: 'credit',
      payment_method: 'NEFT',
      amount: 125000.00,
      balance: 142999.50,
      source_file: 'HDFC_Statement_Oct2026.csv',
      source_row: 141,
      ai_inferred: false
    },
    {
      id: 'tx-103',
      user_id: 'usr-fingenie-demo-001',
      date: '2026-10-20',
      description: 'ZERODHA BROKING / FUNDS ADDED / UPI 329104',
      category: 'Investments',
      type: 'debit',
      payment_method: 'UPI',
      amount: 25000.00,
      balance: 17999.50,
      source_file: 'HDFC_Statement_Oct2026.csv',
      source_row: 140,
      ai_inferred: true
    },
    {
      id: 'tx-104',
      user_id: 'usr-fingenie-demo-001',
      date: '2026-10-18',
      description: 'BESCOM ELEC BILL / AUTOPAY / BANGALORE',
      category: 'Utilities',
      type: 'debit',
      payment_method: 'NetBanking',
      amount: 2420.00,
      balance: 42999.50,
      source_file: 'HDFC_Statement_Oct2026.csv',
      source_row: 139,
      ai_inferred: true
    },
    {
      id: 'tx-105',
      user_id: 'usr-fingenie-demo-001',
      date: '2026-10-15',
      description: 'RENT PAYMENT / IMPS TO LANDLORD S BALAJI',
      category: 'Rent',
      type: 'debit',
      payment_method: 'IMPS',
      amount: 28000.00,
      balance: 45419.50,
      source_file: 'HDFC_Statement_Oct2026.csv',
      source_row: 138,
      ai_inferred: false
    },
    {
      id: 'tx-106',
      user_id: 'usr-fingenie-demo-001',
      date: '2026-10-12',
      description: 'NATURES BASKET / GROCERY INDIRANAGAR / POS CARD',
      category: 'Groceries',
      type: 'debit',
      payment_method: 'Card',
      amount: 4320.00,
      balance: 73419.50,
      source_file: 'HDFC_Statement_Oct2026.csv',
      source_row: 137,
      ai_inferred: true
    },
    {
      id: 'tx-107',
      user_id: 'usr-fingenie-demo-001',
      date: '2026-10-08',
      description: 'FREELANCE CONSULTING / CLIENT REMITTANCE / RTGS',
      category: 'Consulting',
      type: 'credit',
      payment_method: 'RTGS',
      amount: 45000.00,
      balance: 77739.50,
      source_file: 'HDFC_Statement_Oct2026.csv',
      source_row: 136,
      ai_inferred: false
    },
    {
      id: 'tx-108',
      user_id: 'usr-fingenie-demo-001',
      date: '2026-10-05',
      description: 'CASH WITHDRAWAL / HDFC ATM KORAMANGALA',
      category: 'Cash',
      type: 'debit',
      payment_method: 'ATM',
      amount: 5000.00,
      balance: 32739.50,
      source_file: 'HDFC_Statement_Oct2026.csv',
      source_row: 135,
      ai_inferred: false
    }
  ]
};

export const isLiveSupabaseConfigured = Boolean(
  supabaseUrl && 
  supabaseAnonKey && 
  !supabaseUrl.includes('your-project-ref')
);

export const mockDb = mockStore;

export const getSupabaseConfig = () => ({
  supabaseUrl,
  supabaseAnonKey,
  isLive: isLiveSupabaseConfigured
});
