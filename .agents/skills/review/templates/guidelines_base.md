# Reviewer Guidelines — [Project Name]

Welcome! This document outlines instructions, technical requirements, and reporting standards for any **reviewer** (AI agent or human engineer) auditing the **[Project Name]** project.

The goal of a technical review is to provide rigorous, evidence-based critical scrutiny to ensure reliability, safety, maintainability, and adherence to project requirements.

---

## 1. Format & Naming Conventions

### File Naming
Submit your review inside the `review/` directory using the following format:
`review/reviewXXX.md` *(e.g., `review001.md`, `review_architecture_01.md`)*.

> [!NOTE]
> **Lifecycle:** Once your review is placed in `review/`, the project team (user and AI assistant) will evaluate your observations, arbitrate each item, integrate accepted action points into `todo.md`, and then **delete** your `reviewXXX.md` file. Deletion signifies full resolution and keeps the intake clean for subsequent reviews.

### Mandatory Metadata Header
Every review **must begin** with this metadata block to guarantee full audit traceability:

```markdown
# Technical Review: [Short and descriptive title]

- **Reviewer / Agent Name:** [E.g. Claude, Gemini, Domain Expert, etc.]
- **Date:** [YYYY-MM-DD]
- **Audited Scope:** [E.g. Module / Subsystem / Architecture / PR / Release]
- **Examined Reference / Version:** [Git commit hash, tag, or document version]
- **Overall Verdict:** [🟢 Approved / 🟠 Approved with Reservations / 🔴 Rejected (Critical fixes required)]
```

---

## 2. Project Context, Audit Axes & Pitfalls to Avoid (Domain-Specific)

> [!IMPORTANT]
> **Customize this section for your project's domain** (e.g., Embedded Firmware, Hardware/PCB, Web/Backend, Mechanical CAD).

### 2.0 Universal Auditor Mindset: Tabula Rasa & Evidence-Based Scrutiny
- Disregard any prior conversational memory or unverified assumptions. Adopt the stance of an impartial third-party auditor discovering the project fresh.
- Ground every observation strictly in versioned repository artifacts (source files, specs, schematics, tests, datasheets, logs).
- Cross-check documentation claims against actual implementation and authoritative references before raising an alert.

### 2.1 Project Context & Known Constraints
- **[TODO: Target Environment & Scope]** *(Define operational limits, target platforms, or regulatory boundaries.)*
- **[TODO: Core Stack & Architecture]** *(List key frameworks, MCUs, protocols, or structural choices.)*
- **[TODO: Current Progress State]** *(Point to `todo.md` or design docs so reviewers avoid flagging already-arbitrated items.)*

### 2.2 Domain-Specific Audit Axes
- **[TODO: Axis 1 — Safety, Security & Failure Modes]**
- **[TODO: Axis 2 — Correctness, Timing & Concurrency]**
- **[TODO: Axis 3 — Interfaces, Protocols & Compatibility]**
- **[TODO: Axis 4 — Performance, Resources & Cost/DFM]**
- **[TODO: Axis 5 — Maintainability, Testing & Documentation]**

### 2.3 Known Design Decisions (Do Not Flag)
- **[TODO: Validated Trade-offs]** *(Document intentional choices that might otherwise look like defects to a fresh reviewer.)*

---

## 3. Mandatory Criticality Classification

Observations must be strictly categorized into 3 severity levels:

### 🔴 1. Blocking / Critical (*High / Critical*)
*Issues that prevent operation, break core invariants, or introduce severe safety/security/data-loss risks.*

### 🟠 2. Important (*Medium*)
*Issues that compromise robustness, reliability, edge-case handling, performance, or compliance.*

### 🟢 3. Minor / Suggestion (*Low / Info*)
*Opportunities to improve clarity, cost, ergonomics, testability, or maintainability.*

---

## 4. Expectations for High-Quality Feedback

For observations to be directly actionable, each remark must provide:

1. **Pinpoint Precision:** Cite exact file paths, line ranges, symbols, modules, or component/net identifiers.
2. **Technical Demonstration (Why?):** Support analysis with concrete evidence, calculations, traces, specs, or standards.
3. **Turnkey Actionable Solution (How to fix?):** Propose a clear, concrete remediation step without speculative placeholders.

---

## 5. Review Template (`reviewXXX.md`)

Copy and complete the template below in your `review/reviewXXX.md` file:

```markdown
# Technical Review: [Short title of your audit]

- **Reviewer / Agent Name:** [Your name / AI model]
- **Date:** [YYYY-MM-DD]
- **Audited Scope:** [Module / Subsystem / Architecture]
- **Examined Reference / Version:** [Git commit hash or document version]
- **Overall Verdict:** [🟢 Approved / 🟠 Approved with Reservations / 🔴 Rejected]

---

## Executive Summary
[3 to 5 sentence summary on overall health, compliance, and key priorities.]

---

## Observations Summary

| Ref | Severity | Target / Scope | Summary Description |
| :--- | :--- | :--- | :--- |
| **B1** | 🔴 Blocking | `...` | ... |
| **I1** | 🟠 Important | `...` | ... |
| **M1** | 🟢 Minor | `...` | ... |

---

## Detailed Observations & Recommendations

### 🔴 Blocking Observations (Critical)

#### B1. [Descriptive Title]
- **Affected Targets / Scope:** `...`
- **Technical Observation:** [Detailed problem description]
- **Justification & Risk:** [Evidence, calculation, spec, or standard demonstrating hazard]
- **Recommended Solution:** [Concrete actionable fix]

---

### 🟠 Important Observations (Robustness & Reliability)

#### I1. [Recommendation Title]
- **Affected Targets / Scope:** `...`
- **Technical Observation:** [Description]
- **Justification:** [Impact on reliability, edge cases, or compliance]
- **Recommended Solution:** [Recommended change]

---

### 🟢 Minor Observations (Optimization & Polish)

#### M1. [Optimization Title]
- **Affected Targets / Scope:** `...`
- **Observation & Proposal:** [Concrete improvement suggestion]
- **Expected Benefit:** [Maintainability, clarity, cost, or testability gain]
```
