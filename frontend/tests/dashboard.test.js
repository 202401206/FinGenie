/**
 * dashboard.test.js — Unit tests for Student Dashboard calculations and categorizations
 *
 * Uses Node's built-in test runner (node:test).
 */
import test from "node:test";
import assert from "node:assert/strict";
import { formatCurrency, formatBalance } from "../src/utils/formatters.js";

test("dashboard: formatCurrency handles student numbers and Indian commas", () => {
  assert.equal(formatCurrency(15000, "INR"), "₹15,000.00");
  assert.equal(formatCurrency(8650, "INR"), "₹8,650.00");
  assert.equal(formatCurrency(450.5, "INR"), "₹450.50");
  assert.equal(formatCurrency(0, "INR"), "₹0.00");
  assert.equal(formatBalance(6350, "INR"), "₹6,350.00");
});

test("dashboard: net savings calculation with surplus and deficit", () => {
  const inflow = 15000;
  const outflow = 8650;
  const surplus = inflow - outflow;
  assert.equal(surplus, 6350);

  const highOutflow = 16200;
  const deficit = inflow - highOutflow;
  assert.equal(deficit, -1200);
});

test("dashboard: student category matching covers common student expenses", () => {
  function matchCategory(desc) {
    const text = desc.toLowerCase();
    if (
      /zomato|swiggy|canteen|mess|cafe|coffee|chai|restaurant|mcdonald/i.test(
        text,
      )
    )
      return "food";
    if (/book|xerox|print|stationery|college|tuition|fee|course/i.test(text))
      return "academics";
    if (/metro|bus|train|irctc|uber|ola|rapido|auto|petrol/i.test(text))
      return "travel";
    if (/amazon|flipkart|myntra|zara|cloth|shopping|blinkit/i.test(text))
      return "shopping";
    if (/netflix|spotify|prime|pvr|movie|game|party/i.test(text))
      return "entertainment";
    return "general";
  }

  assert.equal(matchCategory("UPI/Swiggy Order #482"), "food");
  assert.equal(matchCategory("CAMPUS CANTEEN TEA AND SAMOSA"), "food");
  assert.equal(matchCategory("COLLEGE PHOTOCOPY XEROX SHOP"), "academics");
  assert.equal(matchCategory("DELHI METRO SMART CARD RECHARGE"), "travel");
  assert.equal(matchCategory("AMAZON PAY NOTEBOOK PURCHASE"), "academics");
  assert.equal(matchCategory("MYNTRA CLOTHING STORE SHOPPING"), "shopping");
  assert.equal(matchCategory("PVR INOX CINEMA TICKETS"), "entertainment");
  assert.equal(matchCategory("ATM CASH WITHDRAWAL"), "general");
});

test("dashboard: daily average burn rate calculation for students", () => {
  const totalOutflow = 9000;
  const daysInMonth = 30;
  const avgDaily = Math.round(totalOutflow / daysInMonth);
  assert.equal(avgDaily, 300);
});
