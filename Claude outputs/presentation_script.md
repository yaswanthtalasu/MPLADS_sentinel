# Prototype Walkthrough Script (2:30 min)

## Opening (15 sec)

"What we've built is a risk intelligence system for infrastructure projects — instead of manually auditing thousands of projects one by one, our engine scores every single project across 6 independent risk dimensions and surfaces the ones that actually need human attention. Let me walk you through it."

---

## Page 1: Dashboard (30 sec)

"This is the Dashboard — the first thing an officer sees. It shows KPIs: total projects, how many are high/medium/low risk, and total funds at risk.

Below that, a scatter plot of utilization vs progress — this instantly shows projects where money has been spent but physical progress hasn't kept up, which is a classic red flag.

We also show a layer profile chart — average score per risk layer across the portfolio — and a distribution of *which* layer is driving risk most often. This tells leadership where systemic issues are: is it mostly financial anomalies, or execution delays, or something else?

**Why this page**: Leadership needs a bird's-eye view before drilling into individual projects."

---

## Page 2: Alert Queue (25 sec)

"This is the Alert Queue — a sortable, filterable list of all projects ranked by risk score. An officer can filter by state, risk band, activity type, or search by project name.

**Why this page**: This is the actual worklist. Instead of scrolling through a spreadsheet of 34,000 projects, the system prioritizes them so investigators only look at what matters."

---

## Page 3: Project Investigation (45 sec)

"This is the core page — when you click into a single project, you get a full investigation view.

At the top: the unified risk score and band. Below that, a breakdown of all 6 layers — financial, execution, peer deviation, semantic, spatial, and data quality — each with its own score and a plain-English reason, like 'cost exceeds peer median by 3x' or 'similar project description found nearby.'

We also show a peer comparison table — how this project compares to similar projects in the same category — and a list of similar projects flagged by our semantic similarity engine, which catches duplicate or copy-pasted project descriptions.

There's also a small map showing the project's location relative to its constituency.

**Why this page**: This is where trust is built. Every score comes with a reason — nothing is a black box. An officer can see *exactly* why a project was flagged before acting on it."

---

## Page 4: Methodology (25 sec)

"Finally, the Methodology page — this is the system explaining itself. It documents exactly how each of the 6 layers is calculated, the peer-grouping logic, the scoring curve, and the weights used to combine everything into the final score.

**Why this page**: Transparency and auditability. Anyone — auditor, official, or developer — can verify how a score was produced, which is critical for something used in financial oversight."

---

## Closing (10 sec)

"So in short: raw project data goes in, gets cleaned, passes through 6 independent ML/statistical models, and comes out as a single explainable risk score — helping a small team focus on the handful of projects that actually deserve scrutiny out of thousands."

---
---

# Anticipated Q&A

## On the AI/ML approach
1. **Why Isolation Forest and not a neural network / deep learning model?** — Isolation Forest works well on tabular, small-to-medium, unlabeled anomaly detection tasks and is interpretable; deep learning needs large labeled datasets we don't have.
2. **How do you validate the model without labeled fraud data?** — We use unsupervised anomaly detection (no labels needed) and cross-check against known legacy signals for correlation, not training.
3. **Why 6 separate layers instead of one combined model?** — Each layer captures a distinct failure mode (financial, execution, peer, semantic, spatial, quality); combining them as one black-box model would lose explainability.
4. **How were the layer weights (22%, 20%, 20%, 13%, 13%, 12%) decided?** — Based on domain judgment of which risk types are most predictive/severe; they're configurable and can be tuned with feedback data.
5. **What happens if a project has missing data?** — It's flagged under the Data Quality layer (Layer 6) rather than silently ignored or wrongly scored.

## On data & leakage
6. **Did you use the legacy/existing risk scores as training input?** — No — we explicitly excluded all legacy risk columns (anti-leakage policy) to ensure our score is independently derived, not just replicating the old system.
7. **Where does the geographic data come from?** — Official ECI (Election Commission of India) 2019 constituency centroids, not synthetic coordinates.
8. **How do you handle duplicate or template project descriptions?** — TF-IDF + cosine similarity on project names/descriptions flags near-duplicates as a semantic risk signal.

## On scalability & practicality
9. **How does this scale to new projects added daily?** — The pipeline is designed to be re-run as a batch job; peer groups and models can be recalculated incrementally.
10. **What's the false positive rate?** — We don't have ground truth fraud labels to compute a strict FPR; instead every score comes with reasons so a human makes the final call — it's decision support, not automated action.
11. **Can this run in real-time or is it batch only?** — Currently batch (scores + peer stats + similarity precomputed and stored); the API serves precomputed results instantly.

## On methodology & trust
12. **Why should we trust an anomaly score over a human auditor?** — It's not a replacement — it's a triage tool. It surfaces candidates faster; humans still make the final judgment call.
13. **How do you know the peer groups are fair (comparing similar projects)?** — Hierarchical peer grouping (activity→state→fy→scale) with a minimum group size of 25 ensures statistically meaningful comparisons.
14. **What's the correlation with the old/legacy risk score?** — Low to moderate (~0.33) — intentional, since we exclude legacy signals and derive risk independently.

## On future scope
15. **What would you add next?** — Feedback loop from investigation outcomes to retrain/calibrate weights, real-time ingestion, and expanding spatial analysis beyond constituency-level.
