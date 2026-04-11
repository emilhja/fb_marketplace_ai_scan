# Persistent login — downsides

This note is about **persisting a browser session** for tools like `ai-marketplace-monitor` (e.g. Playwright `storage_state`, a fixed user-data directory, or `launch_persistent_context`). Today the packaged monitor uses a **fresh browser context each run**, so Facebook does not stay logged in between process restarts.

## Security and secrecy

A persisted session is usually **one file or folder** that effectively means “logged in as you.” Anyone with disk access, backups, or a copied machine can **reuse that session** without your password. Treat it like a secret: file permissions, keep it out of git, prefer full-disk encryption, and **invalidate or delete** it if it might have leaked.

## Account and abuse risk

Automated or semi-automated access may still conflict with **Meta’s terms** and can trigger **checks, forced re-login, or account restrictions**. Persistence does not make traffic invisible; a long-lived profile can be **easier to correlate** with repeated scripted use.

## Fragility

Facebook can **invalidate** sessions (password change, security prompts, policy). Saved state can go **stale**, producing failures until you clear storage and sign in again—similar to ephemeral login, but with an extra “bad cache” debugging step.

## 2FA and checkpoints

If Meta shows a **checkpoint or 2FA**, unattended or headless runs may **stall or break** until a human completes the flow in that same profile. Persistence reduces day-to-day password prompts; it does not remove these gates.

## Privacy on shared machines

The profile keeps **cookies and identifying browser data** on disk. On a shared PC, that is a **privacy** risk compared to a throwaway context each run.

## Operational footguns

Profile **corruption**, partial writes, or **Playwright / browser upgrades** can cause hard-to-reproduce bugs. A clean context every run is simpler to reason about.

## Summary

Persistence is mainly a **convenience vs. security and operational risk** tradeoff. On a personal machine, with careful handling of the session artifact, many people accept it; for shared or high-stakes use, the downsides matter more.
