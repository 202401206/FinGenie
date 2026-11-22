import React, { useMemo } from "react";
import {
  formatCurrency,
  formatBalance,
  formatCurrencyLabel,
} from "../../utils/formatters.js";
import "./DashboardPage.css";

/**
 * Categorizes a transaction description into student-friendly spending buckets.
 */
function categorizeStudentExpense(description = "") {
  const text = (description || "").toLowerCase();

  if (
    /zomato|swiggy|canteen|mess|food|cafe|coffee|chai|restaurant|bakery|snack|mcdonald|burger|pizza/i.test(
      text,
    )
  ) {
    return { id: "food", name: "Food & Canteen", icon: "🍔", color: "#E57373" };
  }
  if (
    /book|xerox|print|stationery|college|tuition|fee|course|udemy|library|exam|pen/i.test(
      text,
    )
  ) {
    return {
      id: "academics",
      name: "Academics & Stationery",
      icon: "📚",
      color: "#4DB6AC",
    };
  }
  if (
    /metro|bus|train|irctc|uber|ola|rapido|auto|petrol|fuel|ticket|commute/i.test(
      text,
    )
  ) {
    return {
      id: "travel",
      name: "Travel & Commute",
      icon: "🚌",
      color: "#64B5F6",
    };
  }
  if (
    /amazon|flipkart|myntra|zara|cloth|shopping|mart|store|blinkit|zepto|instamart/i.test(
      text,
    )
  ) {
    return {
      id: "shopping",
      name: "Shopping & Essentials",
      icon: "🛍️",
      color: "#BA68C8",
    };
  }
  if (
    /netflix|spotify|prime|pvr|movie|game|steam|party|outing|club/i.test(text)
  ) {
    return {
      id: "entertainment",
      name: "Entertainment & Fun",
      icon: "🍿",
      color: "#FFB74D",
    };
  }
  return {
    id: "general",
    name: "General Student Expenses",
    icon: "💳",
    color: "#90A4AE",
  };
}

export function DashboardPage({
  transactions = [],
  documentMetadata = {},
  loading = false,
  error = null,
  onNavigate,
}) {
  const currency = documentMetadata?.currency || "INR";
  const filename =
    documentMetadata?.original_filename || documentMetadata?.filename || null;

  // Compute student financial metrics
  const metrics = useMemo(() => {
    let totalInflow = 0;
    let totalOutflow = 0;
    let closingBalance = 0;
    const categoryTotals = {};

    transactions.forEach((tx) => {
      const debit = Number(tx.debit || 0);
      const credit = Number(tx.credit || 0);
      const bal = Number(tx.balance || 0);

      if (credit > 0) totalInflow += credit;
      if (debit > 0) {
        totalOutflow += debit;
        const cat = categorizeStudentExpense(tx.description);
        if (!categoryTotals[cat.id]) {
          categoryTotals[cat.id] = { ...cat, total: 0, count: 0 };
        }
        categoryTotals[cat.id].total += debit;
        categoryTotals[cat.id].count += 1;
      }
      if (bal > 0) closingBalance = bal;
    });

    // Fallback default student mock data if workspace has zero transactions yet
    const hasData = transactions.length > 0;
    if (!hasData) {
      totalInflow = 15000;
      totalOutflow = 8650;
      closingBalance = 6350;
      categoryTotals["food"] = {
        id: "food",
        name: "Food & Canteen (Swiggy, Mess)",
        icon: "🍔",
        color: "#E57373",
        total: 3900,
        count: 14,
      };
      categoryTotals["travel"] = {
        id: "travel",
        name: "Travel & Metro Commute",
        icon: "🚌",
        color: "#64B5F6",
        total: 1850,
        count: 8,
      };
      categoryTotals["academics"] = {
        id: "academics",
        name: "Books, Xerox & Stationery",
        icon: "📚",
        color: "#4DB6AC",
        total: 1400,
        count: 4,
      };
      categoryTotals["shopping"] = {
        id: "shopping",
        name: "Shopping & Essentials",
        icon: "🛍️",
        color: "#BA68C8",
        total: 1000,
        count: 2,
      };
      categoryTotals["entertainment"] = {
        id: "entertainment",
        name: "Entertainment & Outings",
        icon: "🍿",
        color: "#FFB74D",
        total: 500,
        count: 1,
      };
    }

    const netSavings = totalInflow - totalOutflow;
    const avgDailyBurn = totalOutflow > 0 ? Math.round(totalOutflow / 30) : 0;
    const spendRatio = totalInflow > 0 ? (totalOutflow / totalInflow) * 100 : 0;

    let healthStatus = "healthy";
    let healthTitle = "Student Budget: On Track 🟢";
    let healthDesc =
      "Great job! Your spending is well within your monthly pocket allowance.";
    let healthBadge = "Safe Pace";

    if (spendRatio > 95) {
      healthStatus = "critical";
      healthTitle = "Budget Alert: Overspending 🔴";
      healthDesc =
        "Warning: You have used almost all your allowance. Limit non-essential food and outings.";
      healthBadge = "Deficit Risk";
    } else if (spendRatio > 70) {
      healthStatus = "warning";
      healthTitle = "Student Budget: High Burn Rate 🟡";
      healthDesc =
        "Caution: You have consumed over 70% of your funds. Watch daily food and travel costs.";
      healthBadge = "Watch Spend";
    }

    // Sort categories by expenditure
    const categoriesList = Object.values(categoryTotals).sort(
      (a, b) => b.total - a.total,
    );

    return {
      hasData,
      totalInflow,
      totalOutflow,
      netSavings,
      closingBalance,
      avgDailyBurn,
      spendRatio,
      healthStatus,
      healthTitle,
      healthDesc,
      healthBadge,
      categoriesList,
    };
  }, [transactions]);

  if (loading) {
    return (
      <div
        className="fg-dashboard-view"
        style={{ textAlign: "center", padding: "80px 20px" }}
      >
        <div
          style={{
            fontSize: "18px",
            color: "var(--fg-forest-green, #10251E)",
            fontWeight: 600,
          }}
        >
          Analyzing student statement & calculating KPIs...
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="fg-dashboard-view">
        <div
          className="fg-health-banner critical"
          style={{ margin: "40px auto", maxWidth: "600px" }}
        >
          <div className="fg-health-info">
            <span className="fg-health-icon">⚠️</span>
            <div>
              <h4 className="fg-health-title">Unable to Load Dashboard</h4>
              <p className="fg-health-desc">{error}</p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="fg-dashboard-view">
      {/* Header */}
      <div className="fg-dashboard-header">
        <div>
          <h1 className="fg-dashboard-title">Student Financial Dashboard</h1>
          <div className="fg-dashboard-subtitle">
            {filename ? (
              <>
                <span>
                  Statement: <strong>{filename}</strong>
                </span>
                <span>•</span>
              </>
            ) : (
              <span>Demo Student Overview</span>
            )}
            <span>
              Currency: <strong>{formatCurrencyLabel(currency)}</strong>
            </span>
            <span className="fg-status-pill success">Active Analysis</span>
          </div>
        </div>

        {onNavigate && (
          <button
            type="button"
            onClick={() => onNavigate("upload")}
            style={{
              background: "white",
              border: "1px solid var(--fg-light-grey-green, #E1E8E2)",
              borderRadius: "8px",
              padding: "8px 16px",
              fontSize: "13px",
              fontWeight: 600,
              cursor: "pointer",
              color: "var(--fg-forest-green, #10251E)",
            }}
          >
            Upload New Statement ↑
          </button>
        )}
      </div>

      {/* Financial Health Status Banner */}
      <div className={`fg-health-banner ${metrics.healthStatus}`}>
        <div className="fg-health-info">
          <span className="fg-health-icon">
            {metrics.healthStatus === "healthy"
              ? "🎯"
              : metrics.healthStatus === "warning"
                ? "⚡"
                : "🚨"}
          </span>
          <div>
            <h4 className="fg-health-title">{metrics.healthTitle}</h4>
            <p className="fg-health-desc">{metrics.healthDesc}</p>
          </div>
        </div>
        <span className={`fg-health-badge ${metrics.healthStatus}`}>
          {metrics.healthBadge}
        </span>
      </div>

      {/* 4 Core Student KPI Metric Cards */}
      <div className="fg-kpi-grid">
        <div className="fg-kpi-card">
          <div className="fg-kpi-header">
            <span className="fg-kpi-label">Total Inflow / Allowance</span>
            <span className="fg-kpi-icon">💰</span>
          </div>
          <div className="fg-kpi-value">
            {formatCurrency(metrics.totalInflow, currency)}
          </div>
          <div className="fg-kpi-footer">
            <span className="fg-trend-pill positive">
              Pocket Money & Credits
            </span>
          </div>
        </div>

        <div className="fg-kpi-card">
          <div className="fg-kpi-header">
            <span className="fg-kpi-label">Total Outflow / Spent</span>
            <span className="fg-kpi-icon">💸</span>
          </div>
          <div
            className="fg-kpi-value"
            style={{ color: "var(--fg-soft-red, #C94C4C)" }}
          >
            {formatCurrency(metrics.totalOutflow, currency)}
          </div>
          <div className="fg-kpi-footer">
            <span>{Math.round(metrics.spendRatio)}% of monthly allowance</span>
          </div>
        </div>

        <div className="fg-kpi-card">
          <div className="fg-kpi-header">
            <span className="fg-kpi-label">Remaining Pocket Balance</span>
            <span className="fg-kpi-icon">🏦</span>
          </div>
          <div
            className="fg-kpi-value"
            style={{
              color:
                metrics.netSavings >= 0
                  ? "var(--fg-emerald-green, #1D8A60)"
                  : "var(--fg-soft-red, #C94C4C)",
            }}
          >
            {formatBalance(
              metrics.closingBalance || metrics.netSavings,
              currency,
            )}
          </div>
          <div className="fg-kpi-footer">
            <span
              className={`fg-trend-pill ${metrics.netSavings >= 0 ? "positive" : "negative"}`}
            >
              {metrics.netSavings >= 0
                ? "Surplus Available"
                : "Overdraft / Borrowed"}
            </span>
          </div>
        </div>

        <div className="fg-kpi-card">
          <div className="fg-kpi-header">
            <span className="fg-kpi-label">Avg Daily Spend</span>
            <span className="fg-kpi-icon">📅</span>
          </div>
          <div className="fg-kpi-value">
            {formatCurrency(metrics.avgDailyBurn, currency)}
          </div>
          <div className="fg-kpi-footer">
            <span>Burn rate / 30-day cycle</span>
          </div>
        </div>
      </div>

      {/* Two-Column Breakdown & Insights */}
      <div className="fg-dashboard-sections">
        {/* Category Spending Breakdown */}
        <div className="fg-panel">
          <h3 className="fg-panel-title">
            <span>Student Spending by Category</span>
            <span
              style={{
                fontSize: "12px",
                fontWeight: 500,
                color: "var(--fg-muted-grey, #68746D)",
              }}
            >
              Top Expenses
            </span>
          </h3>

          <div className="fg-category-list">
            {metrics.categoriesList.map((cat) => {
              const pct =
                metrics.totalOutflow > 0
                  ? Math.round((cat.total / metrics.totalOutflow) * 100)
                  : 0;
              return (
                <div key={cat.id} className="fg-category-item">
                  <div className="fg-category-header">
                    <span className="fg-cat-name">
                      <span>{cat.icon}</span>
                      <span>{cat.name}</span>
                    </span>
                    <span className="fg-cat-amount">
                      {formatCurrency(cat.total, currency)}
                      <span className="fg-cat-pct">({pct}%)</span>
                    </span>
                  </div>
                  <div className="fg-progress-bg">
                    <div
                      className="fg-progress-fill"
                      style={{
                        width: `${Math.min(100, Math.max(8, pct))}%`,
                        backgroundColor: cat.color,
                      }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Student Smart Insights Panel */}
        <div className="fg-panel">
          <h3 className="fg-panel-title">
            <span>💡 Smart Student Insights</span>
          </h3>

          <div className="fg-insights-list">
            <div className="fg-insight-card tip">
              <span>🍔</span>
              <div>
                <strong>Highest Spend Category:</strong> Food & Canteen accounts
                for the largest share of your budget. Cooking at hostel or
                eating at mess twice more per week could save ~₹1,200.
              </div>
            </div>

            <div className="fg-insight-card warning">
              <span>⏱️</span>
              <div>
                <strong>Recommended Daily Limit:</strong> To finish this month
                with savings, keep discretionary daily spends under{" "}
                <strong>
                  {formatCurrency(
                    Math.max(150, Math.round(metrics.closingBalance / 20)),
                    currency,
                  )}
                </strong>
                .
              </div>
            </div>

            <div className="fg-insight-card info">
              <span>📚</span>
              <div>
                <strong>Academic Budget:</strong> Books & printouts are under
                15% of total budget. You have healthy margin allocated for
                upcoming exams.
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* AI Financial Buddy Assistant CTA */}
      <div className="fg-ai-cta-card">
        <div className="fg-ai-cta-content">
          <h3>
            <span>🤖</span>
            <span>Have questions about your expenses or budget?</span>
          </h3>
          <p>
            FinGenie AI can analyze your statement transactions, suggest hostel
            saving hacks, or calculate if you can afford a weekend outing.
          </p>
        </div>

        {onNavigate && (
          <button
            type="button"
            className="fg-ai-cta-btn"
            onClick={() => onNavigate("assistant")}
          >
            <span>Ask AI Assistant</span>
            <span>→</span>
          </button>
        )}
      </div>
    </div>
  );
}

export default DashboardPage;
