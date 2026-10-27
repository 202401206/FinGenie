-- ====================================================================
-- FinGenie Fintech Web Application: Supabase Database Schema Migration
-- PostgreSQL DDL with Row Level Security (RLS) & Indian Banking Schema
-- ====================================================================

-- 1. Enable UUID Extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 2. Lookup Table: Popular Indian Banks
CREATE TABLE IF NOT EXISTS public.banks (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    short_code TEXT NOT NULL,
    is_popular BOOLEAN DEFAULT true,
    logo_svg TEXT
);

INSERT INTO public.banks (id, name, short_code, is_popular) VALUES
('sbi', 'State Bank of India', 'SBI', true),
('hdfc', 'HDFC Bank', 'HDFC', true),
('icici', 'ICICI Bank', 'ICICI', true),
('axis', 'Axis Bank', 'AXIS', true),
('kotak', 'Kotak Mahindra Bank', 'KOTAK', true),
('bob', 'Bank of Baroda', 'BOB', true),
('pnb', 'Punjab National Bank', 'PNB', true),
('indusind', 'IndusInd Bank', 'INDUSIND', false),
('other', 'Other Bank', 'OTHER', true)
ON CONFLICT (id) DO NOTHING;

-- 3. Profiles Table (Extends Supabase auth.users)
CREATE TABLE IF NOT EXISTS public.profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    full_name TEXT,
    account_type TEXT CHECK (account_type IN ('personal', 'business')) DEFAULT 'personal',
    bank_id TEXT REFERENCES public.banks(id),
    bank_name TEXT,
    onboarding_completed BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL
);

-- 4. Documents Table (Bank Statements & Balance Sheets)
CREATE TABLE IF NOT EXISTS public.documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    file_name TEXT NOT NULL,
    file_type TEXT CHECK (file_type IN ('csv', 'xlsx')) NOT NULL,
    file_size_bytes BIGINT NOT NULL,
    document_category TEXT CHECK (document_category IN ('bank_statement', 'balance_sheet')) DEFAULT 'bank_statement',
    bank_name TEXT NOT NULL,
    status TEXT CHECK (status IN ('uploading', 'validating', 'processing', 'completed', 'failed')) DEFAULT 'completed',
    transaction_count INT DEFAULT 0,
    uploaded_at TIMESTAMPTZ DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL
);

-- 5. Transactions Table (High-density Indian Banking Ledger)
CREATE TABLE IF NOT EXISTS public.transactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    document_id UUID REFERENCES public.documents(id) ON DELETE SET NULL,
    date DATE NOT NULL,
    description TEXT NOT NULL,
    category TEXT NOT NULL,
    type TEXT CHECK (type IN ('credit', 'debit')) NOT NULL,
    payment_method TEXT CHECK (payment_method IN ('UPI', 'NEFT', 'IMPS', 'RTGS', 'Card', 'ATM', 'NetBanking', 'Transfer')) NOT NULL,
    amount NUMERIC(15, 2) NOT NULL,
    balance NUMERIC(15, 2),
    source_file TEXT NOT NULL,
    source_row INT NOT NULL,
    ai_inferred BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL
);

-- 6. Indexes for High Performance Ledger Querying & Filtering
CREATE INDEX IF NOT EXISTS idx_transactions_user_date ON public.transactions(user_id, date DESC);
CREATE INDEX IF NOT EXISTS idx_transactions_user_type ON public.transactions(user_id, type);
CREATE INDEX IF NOT EXISTS idx_transactions_user_category ON public.transactions(user_id, category);

-- 7. Row Level Security (RLS) Setup
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.banks ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.transactions ENABLE ROW LEVEL SECURITY;

-- Profiles RLS
CREATE POLICY "Users can read own profile"
    ON public.profiles FOR SELECT
    USING (auth.uid() = id);

CREATE POLICY "Users can update own profile"
    ON public.profiles FOR UPDATE
    USING (auth.uid() = id);

-- Banks RLS (Public read for all authenticated users)
CREATE POLICY "Authenticated users can read banks"
    ON public.banks FOR SELECT
    TO authenticated
    USING (true);

-- Documents RLS
CREATE POLICY "Users can read own documents"
    ON public.documents FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own documents"
    ON public.documents FOR INSERT
    WITH CHECK (auth.uid() = user_id);

-- Transactions RLS
CREATE POLICY "Users can read own transactions"
    ON public.transactions FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own transactions"
    ON public.transactions FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete own transactions"
    ON public.transactions FOR DELETE
    USING (auth.uid() = user_id);

-- 8. Stored Procedure: Aggregated Financial Summary
CREATE OR REPLACE FUNCTION public.get_financial_summary(p_user_id UUID)
RETURNS JSON AS $$
DECLARE
    v_total_credit NUMERIC(15, 2);
    v_total_debit NUMERIC(15, 2);
    v_net_flow NUMERIC(15, 2);
    v_count INT;
    v_result JSON;
BEGIN
    SELECT 
        COALESCE(SUM(CASE WHEN type = 'credit' THEN amount ELSE 0 END), 0),
        COALESCE(SUM(CASE WHEN type = 'debit' THEN amount ELSE 0 END), 0),
        COUNT(*)
    INTO v_total_credit, v_total_debit, v_count
    FROM public.transactions
    WHERE user_id = p_user_id;

    v_net_flow := v_total_credit - v_total_debit;

    v_result := json_build_object(
        'total_credit', v_total_credit,
        'total_debit', v_total_debit,
        'net_cash_flow', v_net_flow,
        'transaction_count', v_count
    );

    RETURN v_result;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
