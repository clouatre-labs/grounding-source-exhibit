# Agent Infrastructure

Concepts in the agent-infrastructure cluster.

* [x402 on Cloudflare Workers: AI Agents Pay Per Call in USDC](agent-payments-x402.md) - AI agents pay per call in USDC on Base and Solana; no accounts, no API keys. The full HTTP 402 handshake, documented from a production deployment.
* [Agent-Ready Websites: The 5-Layer Implementation Stack](agent-ready-website.md) - Your website serves two audiences now: humans reading HTML and agents calling tools. Measure agent readiness across five layers and learn what to ship first.
* [Pay-Per-Call APIs: $0.005 Calls, Measured Treasury Costs](pay-per-call-margins-treasury.md) - Sub-cent API calls clear the card fee floor and settle at request; measured USDC off-ramp sweeps show deterministic treasury costs for pay-per-call revenue.
* [Verifying x402 Endpoints: The 5-Check Buyer Recipe](verify-x402-endpoints.md) - How to verify an x402 endpoint before you pay: 5 free or cheap checks, 4 of 4 hostile-seller failure modes detected, 1 of 3 live endpoints diverged.
* [Does WebMCP Pay Off for Content Sites?](webmcp-beyond-checkout.md) - Across 135 agent runs on a production blog, shrinking a four-tool WebMCP surface yielded little median-token benefit; relevance ordering mattered more.
