#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import csv
import importlib.util
import io
import json
import os
import socket
import threading
from collections import Counter, deque
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse


REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
MODULE_PATH = os.path.join(REPO_ROOT, "simple_IMSI-catcher.py")
spec = importlib.util.spec_from_file_location("simple_imsi_catcher", MODULE_PATH)
simple_imsi_catcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(simple_imsi_catcher)


UI_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>IMSI Catcher Control Grid</title>
  <style>
    :root {
      --bg: #07111f;
      --panel: rgba(10, 20, 37, 0.88);
      --panel-strong: rgba(14, 28, 51, 0.96);
      --line: rgba(117, 184, 255, 0.22);
      --line-strong: rgba(117, 184, 255, 0.48);
      --text: #e8f3ff;
      --muted: #8ea6c4;
      --cyan: #55e6ff;
      --lime: #8cffb5;
      --amber: #ffc670;
      --rose: #ff7ca8;
      --danger: #ff5a70;
      --shadow: 0 24px 80px rgba(0, 0, 0, 0.35);
      --radius: 22px;
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      min-height: 100vh;
      color: var(--text);
      background:
        radial-gradient(circle at 20% 20%, rgba(85, 230, 255, 0.16), transparent 30%),
        radial-gradient(circle at 80% 0%, rgba(140, 255, 181, 0.10), transparent 25%),
        linear-gradient(160deg, #030812 0%, #07111f 50%, #03070f 100%);
      font-family: "Space Grotesk", "Eurostile", "Bank Gothic", "Segoe UI", sans-serif;
    }

    body::before {
      content: "";
      position: fixed;
      inset: 0;
      pointer-events: none;
      background-image:
        linear-gradient(rgba(117, 184, 255, 0.05) 1px, transparent 1px),
        linear-gradient(90deg, rgba(117, 184, 255, 0.05) 1px, transparent 1px);
      background-size: 36px 36px;
      mask-image: linear-gradient(to bottom, rgba(0, 0, 0, 0.7), transparent);
    }

    .shell {
      width: min(1460px, calc(100vw - 32px));
      margin: 24px auto;
      display: grid;
      gap: 18px;
    }

    .hero,
    .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      backdrop-filter: blur(16px);
    }

    .hero {
      padding: 28px;
      display: grid;
      gap: 22px;
      overflow: hidden;
      position: relative;
    }

    .hero::after {
      content: "";
      position: absolute;
      inset: auto -8% -45% 38%;
      height: 320px;
      background: radial-gradient(circle, rgba(85, 230, 255, 0.22), transparent 62%);
      transform: rotate(-12deg);
      pointer-events: none;
    }

    .eyebrow {
      display: inline-flex;
      align-items: center;
      gap: 10px;
      color: var(--cyan);
      font-size: 12px;
      letter-spacing: 0.26em;
      text-transform: uppercase;
    }

    .eyebrow::before {
      content: "";
      width: 42px;
      height: 1px;
      background: linear-gradient(90deg, transparent, var(--cyan));
    }

    h1 {
      margin: 0;
      font-size: clamp(2.2rem, 4vw, 4.4rem);
      line-height: 0.95;
      letter-spacing: -0.04em;
      max-width: 760px;
    }

    .subtitle {
      margin: 0;
      color: var(--muted);
      max-width: 780px;
      font-size: 1rem;
      line-height: 1.6;
    }

    .statusline {
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      align-items: center;
    }

    .pill {
      display: inline-flex;
      align-items: center;
      gap: 10px;
      border-radius: 999px;
      border: 1px solid var(--line);
      padding: 9px 14px;
      background: rgba(255, 255, 255, 0.03);
      color: var(--text);
      font-size: 13px;
    }

    .pill strong {
      color: var(--cyan);
      font-weight: 600;
    }

    .layout {
      display: grid;
      grid-template-columns: 420px 1fr;
      gap: 18px;
    }

    .stack {
      display: grid;
      gap: 18px;
    }

    .panel {
      padding: 20px;
    }

    .panel h2 {
      margin: 0 0 16px;
      font-size: 1rem;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: var(--cyan);
    }

    .stats {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 14px;
    }

    .stat {
      padding: 16px;
      border-radius: 18px;
      border: 1px solid var(--line);
      background: linear-gradient(180deg, rgba(255,255,255,0.03), rgba(255,255,255,0.015));
    }

    .stat label {
      display: block;
      color: var(--muted);
      font-size: 12px;
      letter-spacing: 0.14em;
      text-transform: uppercase;
      margin-bottom: 10px;
    }

    .stat strong {
      display: block;
      font-size: 2rem;
      line-height: 1;
      font-weight: 700;
    }

    .grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 14px;
    }

    .field,
    .toggle {
      display: grid;
      gap: 8px;
    }

    .field label,
    .toggle label {
      font-size: 12px;
      color: var(--muted);
      letter-spacing: 0.12em;
      text-transform: uppercase;
    }

    input,
    select,
    button {
      font: inherit;
    }

    input,
    select {
      width: 100%;
      border-radius: 14px;
      border: 1px solid rgba(117, 184, 255, 0.22);
      background: rgba(6, 13, 25, 0.9);
      color: var(--text);
      padding: 12px 14px;
      outline: none;
      transition: border-color 140ms ease, box-shadow 140ms ease, transform 140ms ease;
    }

    input:focus,
    select:focus {
      border-color: var(--cyan);
      box-shadow: 0 0 0 4px rgba(85, 230, 255, 0.14);
    }

    .toggle-row {
      display: flex;
      gap: 10px;
      align-items: center;
      border: 1px solid rgba(117, 184, 255, 0.22);
      border-radius: 14px;
      background: rgba(6, 13, 25, 0.9);
      padding: 10px 12px;
      min-height: 48px;
    }

    .toggle-row input {
      width: 18px;
      height: 18px;
      accent-color: var(--cyan);
      margin: 0;
    }

    .actions,
    .toolbar {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
    }

    button {
      border: 0;
      border-radius: 14px;
      padding: 12px 16px;
      cursor: pointer;
      color: #05101c;
      font-weight: 700;
      letter-spacing: 0.05em;
      text-transform: uppercase;
      transition: transform 140ms ease, opacity 140ms ease, box-shadow 140ms ease;
    }

    button:hover { transform: translateY(-1px); }
    button:disabled { opacity: 0.45; cursor: not-allowed; transform: none; }

    .primary { background: linear-gradient(135deg, var(--cyan), #95f2ff); box-shadow: 0 12px 26px rgba(85, 230, 255, 0.24); }
    .secondary { background: linear-gradient(135deg, #d8e7ff, #9ebfff); }
    .ghost { background: rgba(255, 255, 255, 0.06); color: var(--text); border: 1px solid var(--line); }
    .danger { background: linear-gradient(135deg, #ff8ca0, var(--danger)); box-shadow: 0 12px 26px rgba(255, 90, 112, 0.22); }

    .toolbar,
    .tabbar {
      justify-content: space-between;
      align-items: center;
      margin-bottom: 14px;
    }

    .toolbar-left,
    .toolbar-right {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      align-items: center;
    }

    .logline,
    .summary-list {
      font-family: "IBM Plex Mono", "SFMono-Regular", Consolas, monospace;
      font-size: 12px;
      color: var(--muted);
      padding: 12px 14px;
      border-radius: 14px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.025);
      min-height: 48px;
      white-space: pre-wrap;
    }

    .summary-grid {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 14px;
    }

    .summary-card {
      border: 1px solid var(--line);
      border-radius: 18px;
      background: rgba(255,255,255,0.025);
      padding: 14px;
    }

    .summary-card h3 {
      margin: 0 0 10px;
      font-size: 12px;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.14em;
    }

    .summary-list {
      min-height: 174px;
      display: grid;
      gap: 8px;
      padding: 0;
      margin: 0;
      list-style: none;
    }

    .summary-item {
      display: flex;
      justify-content: space-between;
      gap: 8px;
      color: var(--text);
      border-bottom: 1px solid rgba(117,184,255,0.08);
      padding-bottom: 8px;
    }

    .summary-item:last-child {
      border-bottom: 0;
      padding-bottom: 0;
    }

    .summary-item small {
      color: var(--muted);
    }

    .tabbar {
      display: flex;
      gap: 10px;
      justify-content: flex-start;
      margin-bottom: 12px;
    }

    .tab {
      background: rgba(255, 255, 255, 0.04);
      color: var(--text);
      border: 1px solid var(--line);
    }

    .tab.active {
      background: linear-gradient(135deg, rgba(85,230,255,0.22), rgba(158,191,255,0.18));
      border-color: var(--line-strong);
      color: var(--cyan);
    }

    .view { display: none; }
    .view.active { display: block; }

    .table-wrap {
      overflow: auto;
      border-radius: 18px;
      border: 1px solid var(--line);
      background: var(--panel-strong);
    }

    table {
      width: 100%;
      border-collapse: collapse;
      min-width: 1240px;
      font-family: "IBM Plex Mono", "SFMono-Regular", Consolas, monospace;
      font-size: 12px;
    }

    thead th {
      position: sticky;
      top: 0;
      z-index: 1;
      background: rgba(8, 17, 31, 0.98);
      color: var(--cyan);
      text-transform: uppercase;
      letter-spacing: 0.1em;
      font-size: 11px;
    }

    th,
    td {
      text-align: left;
      padding: 12px 14px;
      border-bottom: 1px solid rgba(117, 184, 255, 0.12);
      white-space: nowrap;
    }

    tbody tr:nth-child(odd) { background: rgba(255, 255, 255, 0.02); }
    tbody tr:hover { background: rgba(85, 230, 255, 0.08); }

    .tag {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 84px;
      padding: 6px 10px;
      border-radius: 999px;
      font-size: 11px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      border: 1px solid transparent;
    }

    .tag.current { color: #082216; background: rgba(140, 255, 181, 0.88); }
    .tag.stale { color: #2e1b00; background: rgba(255, 198, 112, 0.9); }
    .tag.unknown { color: #230514; background: rgba(255, 124, 168, 0.88); }

    @media (max-width: 1180px) {
      .layout { grid-template-columns: 1fr; }
      .stats { grid-template-columns: repeat(2, 1fr); }
      .summary-grid { grid-template-columns: repeat(2, 1fr); }
    }

    @media (max-width: 720px) {
      .shell { width: min(100vw - 18px, 1460px); margin: 12px auto; }
      .hero, .panel { padding: 16px; border-radius: 18px; }
      .stats, .grid, .summary-grid { grid-template-columns: 1fr; }
      .toolbar { align-items: stretch; }
      .toolbar-left, .toolbar-right { width: 100%; }
      .toolbar-right button, .actions button { flex: 1 1 auto; }
    }
  </style>
</head>
<body>
  <div class="shell">
    <section class="hero">
      <div class="eyebrow">Signal Intelligence Grid</div>
      <div>
        <h1>Live IMSI capture in a browser-grade control surface.</h1>
        <p class="subtitle">Run the existing decoder from a web UI, track IMSI and TMSI events in real time, inspect RF metadata, and export the current session as JSON or CSV.</p>
      </div>
      <div class="statusline">
        <div class="pill">Status <strong id="hero-status">Idle</strong></div>
        <div class="pill">Mode <strong id="hero-mode">udp</strong></div>
        <div class="pill">Port <strong id="hero-port">4729</strong></div>
        <div class="pill">Filter <strong id="hero-filter">none</strong></div>
      </div>
    </section>

    <div class="layout">
      <div class="stack">
        <section class="panel">
          <h2>Capture Controls</h2>
          <div class="grid">
            <div class="field">
              <label for="mode">Capture Mode</label>
              <select id="mode">
                <option value="udp">UDP Listener</option>
                <option value="sniff">Sniff Interface</option>
              </select>
            </div>
            <div class="field">
              <label for="iface">Interface</label>
              <input id="iface" value="lo" />
            </div>
            <div class="field">
              <label for="port">Port</label>
              <input id="port" type="number" value="4729" />
            </div>
            <div class="field">
              <label for="event-limit">Visible Events</label>
              <input id="event-limit" type="number" min="25" max="2000" value="250" />
            </div>
            <div class="field" style="grid-column: 1 / -1;">
              <label for="imsi-filter">Track Specific IMSI Prefix</label>
              <input id="imsi-filter" placeholder="123456789101112" />
            </div>
            <div class="field" style="grid-column: 1 / -1;">
              <label for="search">Table Filter</label>
              <input id="search" placeholder="Search IMSI, TMSI, operator, ARFCN, message type..." />
            </div>
            <div class="field">
              <label for="operator-filter">Operator</label>
              <select id="operator-filter"><option value="">All operators</option></select>
            </div>
            <div class="field">
              <label for="message-filter">Message Type</label>
              <select id="message-filter"><option value="">All message types</option></select>
            </div>
            <div class="field">
              <label for="cellstate-filter">Cell State</label>
              <select id="cellstate-filter">
                <option value="">All states</option>
                <option value="current">current</option>
                <option value="stale">stale</option>
                <option value="unknown">unknown</option>
              </select>
            </div>
            <div class="field">
              <label for="arfcn-filter">ARFCN</label>
              <input id="arfcn-filter" placeholder="975" />
            </div>
            <div class="field" style="grid-column: 1 / -1;">
              <label for="sqlite-path">SQLite Capture File</label>
              <input id="sqlite-path" placeholder="Optional: capture.sqlite" />
            </div>
            <div class="field" style="grid-column: 1 / -1;">
              <label for="csv-path">CSV Capture File</label>
              <input id="csv-path" placeholder="Optional: capture.csv" />
            </div>
            <div class="toggle">
              <label>Show Unresolved TMSI</label>
              <div class="toggle-row"><input id="alltmsi" type="checkbox"><span>Include TMSI values without linked IMSI</span></div>
            </div>
            <div class="toggle">
              <label>Mirror To MySQL</label>
              <div class="toggle-row"><input id="mysql" type="checkbox"><span>Use the existing `.env` settings</span></div>
            </div>
          </div>
          <div class="actions" style="margin-top:16px;">
            <button class="primary" id="start-btn">Start Capture</button>
            <button class="danger" id="stop-btn">Stop Capture</button>
            <button class="ghost" id="clear-btn">Clear Session</button>
          </div>
        </section>

        <section class="panel">
          <h2>Session Feed</h2>
          <div class="logline" id="session-log">Waiting for capture commands.</div>
        </section>
      </div>

      <div class="stack">
        <section class="panel">
          <h2>Session Metrics</h2>
          <div class="stats">
            <div class="stat"><label>Total Events</label><strong id="stat-events">0</strong></div>
            <div class="stat"><label>Unique IMSI</label><strong id="stat-imsi">0</strong></div>
            <div class="stat"><label>Known TMSI</label><strong id="stat-tmsi">0</strong></div>
            <div class="stat"><label>Active IMSI</label><strong id="stat-active">0</strong></div>
          </div>
        </section>

        <section class="panel">
          <h2>Signal Summaries</h2>
          <div class="summary-grid">
            <div class="summary-card">
              <h3>Top Operators</h3>
              <ul class="summary-list" id="top-operators"></ul>
            </div>
            <div class="summary-card">
              <h3>Top Countries</h3>
              <ul class="summary-list" id="top-countries"></ul>
            </div>
            <div class="summary-card">
              <h3>Top Messages</h3>
              <ul class="summary-list" id="top-messages"></ul>
            </div>
            <div class="summary-card">
              <h3>Top Cells</h3>
              <ul class="summary-list" id="top-cells"></ul>
            </div>
          </div>
        </section>

        <section class="panel">
          <div class="toolbar">
            <div class="toolbar-left">
              <div class="pill">Current Cell <strong id="current-cell">unknown</strong></div>
              <div class="pill">Operator <strong id="current-operator">unknown</strong></div>
            </div>
            <div class="toolbar-right">
              <button class="secondary" id="export-json">Export JSON</button>
              <button class="secondary" id="export-csv">Export CSV</button>
            </div>
          </div>
          <div class="tabbar">
            <button class="tab active" data-view="events-view" id="events-tab">Events</button>
            <button class="tab" data-view="devices-view" id="devices-tab">Devices</button>
          </div>
          <div class="view active" id="events-view">
            <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Count</th>
                  <th>Timestamp</th>
                  <th>IMSI</th>
                  <th>TMSI-1</th>
                  <th>TMSI-2</th>
                  <th>Operator</th>
                  <th>Country</th>
                  <th>MCC</th>
                  <th>MNC</th>
                  <th>LAC</th>
                  <th>Cell</th>
                  <th>ARFCN</th>
                  <th>TS</th>
                  <th>SS</th>
                  <th>dBm</th>
                  <th>SNR</th>
                  <th>Frame</th>
                  <th>Msg</th>
                  <th>Cell State</th>
                </tr>
              </thead>
              <tbody id="events-body"></tbody>
            </table>
          </div>
          </div>
          <div class="view" id="devices-view">
            <div class="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Identity</th>
                    <th>Type</th>
                    <th>Seen</th>
                    <th>First Seen</th>
                    <th>Last Seen</th>
                    <th>Operator</th>
                    <th>Country</th>
                    <th>ARFCN</th>
                    <th>Last Cell</th>
                    <th>Last dBm</th>
                    <th>Last Msg</th>
                    <th>Cell State</th>
                  </tr>
                </thead>
                <tbody id="devices-body"></tbody>
              </table>
            </div>
          </div>
        </section>
      </div>
    </div>
  </div>

  <script>
    const state = { limit: 250, query: "", view: "events-view" };

    function byId(id) { return document.getElementById(id); }

    function esc(value) {
      return String(value ?? "").replace(/[&<>"]/g, (char) => ({ "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;" }[char]));
    }

    async function api(path, options = {}) {
      const response = await fetch(path, {
        headers: { "Content-Type": "application/json" },
        ...options,
      });
      if (!response.ok) {
        const text = await response.text();
        throw new Error(text || `HTTP ${response.status}`);
      }
      const contentType = response.headers.get("Content-Type") || "";
      if (contentType.includes("application/json")) {
        return response.json();
      }
      return response.text();
    }

    function captureForm() {
      return {
        mode: byId("mode").value,
        iface: byId("iface").value.trim(),
        port: Number(byId("port").value),
        all_tmsi: byId("alltmsi").checked,
        imsi_filter: byId("imsi-filter").value.trim(),
        sqlite_path: byId("sqlite-path").value.trim(),
        csv_path: byId("csv-path").value.trim(),
        mysql: byId("mysql").checked,
      };
    }

    function activeFilters() {
      return new URLSearchParams({
        limit: String(state.limit),
        search: byId("search").value.trim(),
        operator: byId("operator-filter").value,
        message_type: byId("message-filter").value,
        cell_status: byId("cellstate-filter").value,
        arfcn: byId("arfcn-filter").value.trim(),
      }).toString();
    }

    function setLog(message) {
      byId("session-log").textContent = message;
    }

    function renderState(payload) {
      const data = payload.manager;
      const config = data.config || {};
      byId("hero-status").textContent = data.running ? "Running" : "Idle";
      byId("hero-mode").textContent = config.mode || "udp";
      byId("hero-port").textContent = config.port ?? "4729";
      byId("hero-filter").textContent = config.imsi_filter || "none";
      byId("stat-events").textContent = data.total_events;
      byId("stat-imsi").textContent = data.unique_imsis;
      byId("stat-tmsi").textContent = data.known_tmsis;
      byId("stat-active").textContent = data.active_imsis;

      const cell = data.last_cell || {};
      const cellText = cell.cell ? `${cell.mcc}/${cell.mnc} LAC ${cell.lac} Cell ${cell.cell}` : "unknown";
      byId("current-cell").textContent = cellText;
      byId("current-operator").textContent = cell.operator || "unknown";
      byId("start-btn").disabled = data.running;
      byId("stop-btn").disabled = !data.running;
      renderFilterOptions(payload.filters || {});

      if (payload.error) {
        setLog(payload.error);
      } else if (data.last_log) {
        setLog(data.last_log);
      }
    }

    function renderFilterOptions(filters) {
      const operatorSelect = byId("operator-filter");
      const messageSelect = byId("message-filter");
      const selectedOperator = operatorSelect.value;
      const selectedMessage = messageSelect.value;

      operatorSelect.innerHTML = `<option value="">All operators</option>${(filters.operators || []).map((value) => `<option value="${esc(value)}">${esc(value)}</option>`).join("")}`;
      messageSelect.innerHTML = `<option value="">All message types</option>${(filters.message_types || []).map((value) => `<option value="${esc(value)}">${esc(value)}</option>`).join("")}`;
      operatorSelect.value = selectedOperator;
      messageSelect.value = selectedMessage;
    }

    function renderSummaryList(id, entries, formatter) {
      byId(id).innerHTML = (entries || []).slice(0, 6).map((entry) => {
        const rendered = formatter(entry);
        return `<li class="summary-item"><span>${rendered.label}</span><small>${rendered.value}</small></li>`;
      }).join("") || `<li class="summary-item"><span>No data</span><small>0</small></li>`;
    }

    function renderSummaries(summaries) {
      renderSummaryList("top-operators", summaries.top_operators, (entry) => ({ label: esc(entry.key), value: esc(entry.count) }));
      renderSummaryList("top-countries", summaries.top_countries, (entry) => ({ label: esc(entry.key), value: esc(entry.count) }));
      renderSummaryList("top-messages", summaries.top_messages, (entry) => ({ label: esc(entry.key), value: esc(entry.count) }));
      renderSummaryList("top-cells", summaries.top_cells, (entry) => ({ label: esc(entry.key), value: esc(entry.count) }));
    }

    function renderEvents(events) {
      byId("events-body").innerHTML = events.map((event) => {
        const status = esc(event.cell_status || "unknown");
        return `
          <tr>
            <td>${esc(event.count)}</td>
            <td>${esc(event.timestamp)}</td>
            <td>${esc(event.imsi)}</td>
            <td>${esc(event.tmsi1)}</td>
            <td>${esc(event.tmsi2)}</td>
            <td>${esc(event.imsioperator)}</td>
            <td>${esc(event.imsicountry)}</td>
            <td>${esc(event.mcc)}</td>
            <td>${esc(event.mnc)}</td>
            <td>${esc(event.lac)}</td>
            <td>${esc(event.cell)}</td>
            <td>${esc(event.arfcn)}</td>
            <td>${esc(event.timeslot)}</td>
            <td>${esc(event.sub_slot)}</td>
            <td>${esc(event.signal_dbm)}</td>
            <td>${esc(event.snr_db)}</td>
            <td>${esc(event.frame_number)}</td>
            <td>${esc(event.message_type)}</td>
            <td><span class="tag ${status}">${status}</span></td>
          </tr>
        `;
      }).join("");
    }

    function renderDevices(devices) {
      byId("devices-body").innerHTML = devices.map((device) => {
        const status = esc(device.cell_status || "unknown");
        return `
          <tr>
            <td>${esc(device.identity)}</td>
            <td>${esc(device.identity_type)}</td>
            <td>${esc(device.seen_count)}</td>
            <td>${esc(device.first_seen)}</td>
            <td>${esc(device.last_seen)}</td>
            <td>${esc(device.operator)}</td>
            <td>${esc(device.country)}</td>
            <td>${esc(device.arfcn)}</td>
            <td>${esc(device.cell)}</td>
            <td>${esc(device.signal_dbm)}</td>
            <td>${esc(device.message_type)}</td>
            <td><span class="tag ${status}">${status}</span></td>
          </tr>
        `;
      }).join("");
    }

    async function refresh() {
      try {
        const payload = await api(`/api/state?${activeFilters()}`);
        renderState(payload);
        renderEvents(payload.events);
        renderDevices(payload.devices || []);
        renderSummaries(payload.summaries || {});
      } catch (error) {
        setLog(error.message);
      }
    }

    byId("start-btn").addEventListener("click", async () => {
      try {
        await api("/api/start", { method: "POST", body: JSON.stringify(captureForm()) });
        setLog("Capture started.");
        refresh();
      } catch (error) {
        setLog(error.message);
      }
    });

    byId("stop-btn").addEventListener("click", async () => {
      try {
        await api("/api/stop", { method: "POST", body: "{}" });
        setLog("Capture stopped.");
        refresh();
      } catch (error) {
        setLog(error.message);
      }
    });

    byId("clear-btn").addEventListener("click", async () => {
      try {
        await api("/api/clear", { method: "POST", body: "{}" });
        setLog("Session memory cleared.");
        refresh();
      } catch (error) {
        setLog(error.message);
      }
    });

    byId("event-limit").addEventListener("change", () => {
      state.limit = Number(byId("event-limit").value || 250);
      refresh();
    });

    ["search", "operator-filter", "message-filter", "cellstate-filter", "arfcn-filter"].forEach((id) => {
      byId(id).addEventListener(id === "search" ? "input" : "change", refresh);
    });

    byId("export-json").addEventListener("click", () => {
      window.open(`/api/export.json?${activeFilters()}`, "_blank");
    });

    byId("export-csv").addEventListener("click", () => {
      window.open(`/api/export.csv?${activeFilters()}`, "_blank");
    });

    document.querySelectorAll(".tab").forEach((tab) => {
      tab.addEventListener("click", () => {
        document.querySelectorAll(".tab").forEach((item) => item.classList.remove("active"));
        document.querySelectorAll(".view").forEach((item) => item.classList.remove("active"));
        tab.classList.add("active");
        byId(tab.dataset.view).classList.add("active");
      });
    });

    refresh();
    setInterval(refresh, 1500);
  </script>
</body>
</html>
"""


class CaptureManager:
    def __init__(self):
        self.lock = threading.Lock()
        self.records = deque(maxlen=5000)
        self.total_events = 0
        self.running = False
        self.stop_event = None
        self.thread = None
        self.sniffer = None
        self.sock = None
        self.tracker = None
        self.config = {
            "mode": "udp",
            "iface": "lo",
            "port": 4729,
            "imsi_filter": "",
            "all_tmsi": False,
        }
        self.last_log = "Ready."
        self.last_error = ""
        self.last_start_error = ""

    def _record_callback(self, cpt, tmsi1, tmsi2, imsi, imsicountry, imsibrand, imsioperator, mcc, mnc, lac, cell, now, packet=None, meta=None):
        tracker = self.tracker
        if tracker is None:
            return
        record = tracker.build_record(
            cpt, tmsi1, tmsi2, imsi, imsicountry, imsibrand, imsioperator, mcc, mnc, lac, cell, now, meta=meta
        )
        with self.lock:
            self.total_events += 1
            self.records.appendleft(record)
            self.last_log = f"{record['timestamp']} {record['message_type']} {record['imsi'] or record['tmsi1'] or record['tmsi2']}"
            self.last_error = ""

    def _setup_tracker(self, config):
        tracker = simple_imsi_catcher.tracker()
        tracker.show_all_tmsi = bool(config.get("all_tmsi"))
        tracker.set_output_function(self._record_callback)

        imsi_filter = config.get("imsi_filter", "").strip()
        if imsi_filter:
            tracker.track_this_imsi(simple_imsi_catcher.encode_imsi_filter(imsi_filter))

        sqlite_path = config.get("sqlite_path", "").strip()
        csv_path = config.get("csv_path", "").strip()
        if sqlite_path:
            tracker.sqlite_file(sqlite_path)
        if csv_path:
            tracker.text_file(csv_path)
        if config.get("mysql"):
            tracker.mysql_file()
        return tracker

    def _udp_loop(self, port):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.bind(("localhost", port))
            self.sock.settimeout(1.0)
            while not self.stop_event.is_set():
                try:
                    udpdata, _ = self.sock.recvfrom(4096)
                except socket.timeout:
                    continue
                simple_imsi_catcher.find_imsi(udpdata, t=self.tracker)
        except Exception as exc:
            with self.lock:
                self.last_error = f"UDP capture failed: {exc}"
                self.last_log = self.last_error
                self.running = False
        finally:
            try:
                if self.sock:
                    self.sock.close()
            except OSError:
                pass
            self.sock = None

    def _start_sniffer(self, config):
        from scapy.all import AsyncSniffer, UDP

        def process_packet(packet):
            if UDP not in packet:
                return
            udpdata = bytes(packet[UDP].payload)
            simple_imsi_catcher.find_imsi(udpdata, t=self.tracker)

        self.sniffer = AsyncSniffer(
            iface=config.get("iface") or "lo",
            filter=f"port {config['port']} and not icmp and udp",
            prn=process_packet,
            store=False,
        )
        self.sniffer.start()

    def start(self, config):
        with self.lock:
            if self.running:
                raise RuntimeError("Capture is already running")

            merged = {
                "mode": config.get("mode", "udp") or "udp",
                "iface": config.get("iface", "lo") or "lo",
                "port": int(config.get("port", 4729) or 4729),
                "imsi_filter": config.get("imsi_filter", "").strip(),
                "all_tmsi": bool(config.get("all_tmsi")),
                "sqlite_path": config.get("sqlite_path", "").strip(),
                "csv_path": config.get("csv_path", "").strip(),
                "mysql": bool(config.get("mysql")),
            }
            self.stop_event = threading.Event()
            self.tracker = self._setup_tracker(merged)
            self.config = merged
            self.last_log = f"Starting {merged['mode']} capture on {merged['iface']}:{merged['port']}"
            self.last_error = ""
            self.last_start_error = ""

            if merged["mode"] == "sniff":
                try:
                    self._start_sniffer(merged)
                except Exception:
                    self.tracker.close()
                    self.tracker = None
                    raise
                self.thread = None
                self.running = True
            else:
                bind_probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                try:
                    bind_probe.bind(("localhost", merged["port"]))
                except OSError as exc:
                    bind_probe.close()
                    self.tracker.close()
                    self.tracker = None
                    raise RuntimeError(f"Unable to bind UDP listener on port {merged['port']}: {exc}")
                bind_probe.close()
                self.thread = threading.Thread(target=self._udp_loop, args=(merged["port"],), daemon=True)
                self.thread.start()
                self.running = True

    def stop(self):
        tracker_to_close = None
        sniffer_to_stop = None
        thread = None
        with self.lock:
            if not self.running:
                return
            self.stop_event.set()
            if self.sock:
                try:
                    self.sock.close()
                except OSError:
                    pass
            sniffer_to_stop = self.sniffer
            self.sniffer = None
            thread = self.thread
            self.thread = None
            tracker_to_close = self.tracker
            self.running = False
            self.last_log = "Capture stopped."

        if sniffer_to_stop:
            try:
                sniffer_to_stop.stop()
            except Exception:
                pass
        if thread:
            thread.join(timeout=2.0)
        with self.lock:
            if self.tracker is tracker_to_close:
                self.tracker = None
        if tracker_to_close:
            tracker_to_close.close()

    def clear(self):
        with self.lock:
            self.records.clear()
            self.total_events = 0
            if self.tracker:
                self.tracker.imsistate.clear()
                self.tracker.imsis.clear()
                self.tracker.tmsis.clear()
                self.tracker.nb_IMSI = 0
            self.last_log = "Session memory cleared."
            self.last_error = ""

    def _normalize_filter_value(self, value):
        return (value or "").strip()

    def _filter_records(self, filters):
        search = self._normalize_filter_value(filters.get("search", "")).lower()
        operator = self._normalize_filter_value(filters.get("operator", ""))
        message_type = self._normalize_filter_value(filters.get("message_type", ""))
        cell_status = self._normalize_filter_value(filters.get("cell_status", ""))
        arfcn = self._normalize_filter_value(filters.get("arfcn", ""))

        results = []
        for record in self.records:
            if operator and record.get("imsioperator", "") != operator:
                continue
            if message_type and record.get("message_type", "") != message_type:
                continue
            if cell_status and record.get("cell_status", "") != cell_status:
                continue
            if arfcn and record.get("arfcn", "") != arfcn:
                continue
            if search and search not in json.dumps(record, ensure_ascii=False).lower():
                continue
            results.append(record)
        return results

    def _top_entries(self, records, key_name, fallback="unknown", limit=6):
        counts = Counter()
        for record in records:
            value = record.get(key_name, "") or fallback
            counts[value] += 1
        return [{"key": key, "count": count} for key, count in counts.most_common(limit)]

    def _top_cells(self, records, limit=6):
        counts = Counter()
        for record in records:
            if record.get("cell"):
                label = f"{record.get('mcc','?')}/{record.get('mnc','?')}:{record.get('lac','?')}:{record.get('cell','?')}@{record.get('arfcn','?')}"
            else:
                label = "unknown"
            counts[label] += 1
        return [{"key": key, "count": count} for key, count in counts.most_common(limit)]

    def _device_rows(self, records, limit=250):
        devices = {}
        chronological = list(reversed(records))
        for record in chronological:
            identity = record.get("imsi") or record.get("tmsi1") or record.get("tmsi2")
            if not identity:
                continue
            identity_type = "IMSI" if record.get("imsi") else "TMSI"
            device = devices.get(identity)
            cell = "unknown"
            if record.get("cell"):
                cell = f"{record.get('mcc','')}/{record.get('mnc','')}:{record.get('lac','')}:{record.get('cell','')}"
            if not device:
                devices[identity] = {
                    "identity": identity,
                    "identity_type": identity_type,
                    "seen_count": 1,
                    "first_seen": record.get("timestamp", ""),
                    "last_seen": record.get("timestamp", ""),
                    "operator": record.get("imsioperator", ""),
                    "country": record.get("imsicountry", ""),
                    "arfcn": record.get("arfcn", ""),
                    "cell": cell,
                    "signal_dbm": record.get("signal_dbm", ""),
                    "message_type": record.get("message_type", ""),
                    "cell_status": record.get("cell_status", ""),
                }
            else:
                device["seen_count"] += 1
                device["last_seen"] = record.get("timestamp", "")
                device["operator"] = record.get("imsioperator", "") or device["operator"]
                device["country"] = record.get("imsicountry", "") or device["country"]
                device["arfcn"] = record.get("arfcn", "") or device["arfcn"]
                device["cell"] = cell if cell != "unknown" else device["cell"]
                device["signal_dbm"] = record.get("signal_dbm", "") or device["signal_dbm"]
                device["message_type"] = record.get("message_type", "") or device["message_type"]
                device["cell_status"] = record.get("cell_status", "") or device["cell_status"]
        rows = sorted(devices.values(), key=lambda item: (-item["seen_count"], item["last_seen"]), reverse=False)
        rows.sort(key=lambda item: item["seen_count"], reverse=True)
        return rows[:limit]

    def _available_filters(self):
        operators = sorted({record.get("imsioperator", "") for record in self.records if record.get("imsioperator", "")})
        message_types = sorted({record.get("message_type", "") for record in self.records if record.get("message_type", "")})
        return {"operators": operators, "message_types": message_types}

    def snapshot(self, limit=250, filters=None):
        filters = filters or {}
        with self.lock:
            tracker = self.tracker
            filtered_records = self._filter_records(filters)
            events = filtered_records[:limit]
            last_cell = {}
            if tracker and tracker.cell:
                last_cell = {
                    "mcc": tracker.mcc,
                    "mnc": tracker.mnc,
                    "lac": tracker.lac,
                    "cell": tracker.cell,
                    "operator": tracker.operator,
                    "country": tracker.country,
                    "arfcn": tracker.cell_arfcn,
                }
            return {
                "manager": {
                    "running": self.running,
                    "config": self.config,
                    "total_events": self.total_events,
                    "unique_imsis": len(tracker.imsis) if tracker else 0,
                    "known_tmsis": len([key for key, value in (tracker.tmsis.items() if tracker else []) if value]),
                    "active_imsis": len(tracker.imsistate) if tracker else 0,
                    "last_cell": last_cell,
                    "last_log": self.last_log,
                },
                "error": self.last_error,
                "events": events,
                "devices": self._device_rows(filtered_records, limit=limit),
                "summaries": {
                    "top_operators": self._top_entries(filtered_records, "imsioperator"),
                    "top_countries": self._top_entries(filtered_records, "imsicountry"),
                    "top_messages": self._top_entries(filtered_records, "message_type"),
                    "top_cells": self._top_cells(filtered_records),
                },
                "filters": self._available_filters(),
            }

    def export_records(self, limit=5000, filters=None):
        filters = filters or {}
        with self.lock:
            return self._filter_records(filters)[:limit]


manager = CaptureManager()


class RequestHandler(BaseHTTPRequestHandler):
    server_version = "IMSIWebUI/1.0"

    def log_message(self, format, *args):
        return

    def _json_body(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        body = self.rfile.read(length).decode("utf-8")
        return json.loads(body) if body else {}

    def _send(self, status, body, content_type="application/json; charset=utf-8", headers=None):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if headers:
            for key, value in headers.items():
                self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def _filters_from_query(self, params):
        return {
            "search": params.get("search", [""])[0],
            "operator": params.get("operator", [""])[0],
            "message_type": params.get("message_type", [""])[0],
            "cell_status": params.get("cell_status", [""])[0],
            "arfcn": params.get("arfcn", [""])[0],
        }

    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        try:
            limit = int(params.get("limit", ["250"])[0])
        except ValueError:
            self._send(HTTPStatus.BAD_REQUEST, "Invalid limit value", content_type="text/plain; charset=utf-8")
            return
        if limit < 1:
            self._send(HTTPStatus.BAD_REQUEST, "limit must be >= 1", content_type="text/plain; charset=utf-8")
            return

        if parsed.path == "/":
            self._send(HTTPStatus.OK, UI_HTML, content_type="text/html; charset=utf-8")
            return

        filters = self._filters_from_query(params)

        if parsed.path == "/api/state":
            payload = manager.snapshot(limit=limit, filters=filters)
            self._send(HTTPStatus.OK, json.dumps(payload).encode("utf-8"))
            return

        if parsed.path == "/api/export.json":
            payload = manager.export_records(limit=limit, filters=filters)
            headers = {"Content-Disposition": 'attachment; filename="imsi-capture.json"'}
            self._send(HTTPStatus.OK, json.dumps(payload, ensure_ascii=False, indent=2), headers=headers)
            return

        if parsed.path == "/api/export.csv":
            rows = manager.export_records(limit=limit, filters=filters)
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow([
                "count",
                "timestamp",
                "imsi",
                "tmsi1",
                "tmsi2",
                "imsicountry",
                "imsibrand",
                "imsioperator",
                "mcc",
                "mnc",
                "lac",
                "cell",
                "arfcn",
                "timeslot",
                "sub_slot",
                "signal_dbm",
                "snr_db",
                "frame_number",
                "channel_type",
                "message_type",
                "cell_status",
            ])
            for row in rows:
                writer.writerow([
                    row.get("count", ""),
                    row.get("timestamp", ""),
                    row.get("imsi", ""),
                    row.get("tmsi1", ""),
                    row.get("tmsi2", ""),
                    row.get("imsicountry", ""),
                    row.get("imsibrand", ""),
                    row.get("imsioperator", ""),
                    row.get("mcc", ""),
                    row.get("mnc", ""),
                    row.get("lac", ""),
                    row.get("cell", ""),
                    row.get("arfcn", ""),
                    row.get("timeslot", ""),
                    row.get("sub_slot", ""),
                    row.get("signal_dbm", ""),
                    row.get("snr_db", ""),
                    row.get("frame_number", ""),
                    row.get("channel_type", ""),
                    row.get("message_type", ""),
                    row.get("cell_status", ""),
                ])
            headers = {"Content-Disposition": 'attachment; filename="imsi-capture.csv"'}
            self._send(HTTPStatus.OK, output.getvalue(), content_type="text/csv; charset=utf-8", headers=headers)
            return

        self._send(HTTPStatus.NOT_FOUND, json.dumps({"error": "Not found"}).encode("utf-8"))

    def do_POST(self):
        try:
            payload = self._json_body()
            if self.path == "/api/start":
                manager.start(payload)
                self._send(HTTPStatus.OK, json.dumps(manager.snapshot()).encode("utf-8"))
                return
            if self.path == "/api/stop":
                manager.stop()
                self._send(HTTPStatus.OK, json.dumps(manager.snapshot()).encode("utf-8"))
                return
            if self.path == "/api/clear":
                manager.clear()
                self._send(HTTPStatus.OK, json.dumps(manager.snapshot()).encode("utf-8"))
                return
            self._send(HTTPStatus.NOT_FOUND, json.dumps({"error": "Not found"}).encode("utf-8"))
        except Exception as exc:
            manager.last_error = str(exc)
            self._send(HTTPStatus.BAD_REQUEST, str(exc), content_type="text/plain; charset=utf-8")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Web UI for IMSI catcher")
    parser.add_argument("--host", default="127.0.0.1", help="HTTP bind address (default: 127.0.0.1)")
    parser.add_argument("--http-port", type=int, default=8080, help="HTTP port (default: 8080)")
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.http_port), RequestHandler)
    print(f"Web UI listening on http://{args.host}:{args.http_port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        manager.stop()
        server.server_close()


if __name__ == "__main__":
    main()
