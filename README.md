# ab-sql-instacart
This project simulates an A/B experiment on the Instacart Market Basket Analysis dataset. It showcases how to design, implement, and analyze experiments using SQL for data extraction, Python for statistical testing, and a Streamlit app for results visualization.

---

## Business Question
**Does Instacart's new recommendation engine (post-checkout suggestions) increase repeat purchase behavior?**

- **Variant A (Control):** Current experience.  
- **Variant B (Treatment):** New recommendation engine.  
- **Hypothesis:** Variant B increases repeat purchase rate within 28 days.

---

## Experiment Design
- **Population:** All users with at least 1 order in July 2017.  
- **Randomization:** Users assigned to A or B by hashing `user_id`.  
- **Assignment Date:** July 1, 2017.  
- **Window:** 28 days post-assignment.  
- **Metrics:**  
  - Primary: Repeat Purchase Rate (RPR).  
  - Secondary: ARPU (Average Revenue per User), Retention (D14, D28).  
- **Guardrails:**  
  - SRM check (expected 50/50 split).  
  - Contamination check (no users in both variants).  
  - Equal exposure window.

---

## Implementation
**SQL Steps**
1. **Cohort:** Randomly assign users → variants A/B.  
2. **Events:** Filter orders in 28-day window post-assignment.  
3. **Per-User Outcomes:**  
   - Conversion flag (≥1 repeat order).  
   - Revenue in window.  
   - Retention (activity by D14/D28).  
4. **Aggregates:** Variant-level metrics (CR, ARPU, Retention).  
5. **Significance:** z-tests for proportions (CR), Welch’s t-test for ARPU.

**Python (Notebook)**
- CUPED variance reduction using pre-period orders.  
- Bootstrap confidence intervals for CR/ARPU.  
- Power & Minimum Detectable Effect (MDE) analysis.

**Streamlit App**
- SRM check results.  
- Metric dashboards (CR, ARPU, retention).  
- Significance tests with interpretation badges.  
- Distribution visualizations.

---

## ✅ Results

**Decision:** Ship Variant B (better CR, retention; revenue impact needs more data).  

---
