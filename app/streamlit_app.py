import os
import numpy as np
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
from google.cloud import bigquery
from scipy import stats

st.set_page_config(page_title="Instacart A/B (Simulated)", layout="wide")

# -------- Config (secrets or env) --------
PROJECT = st.secrets.get("PROJECT_ID", os.getenv("PROJECT_ID", ""))
DATASET = st.secrets.get("DATASET", os.getenv("DATASET", ""))

st.sidebar.header("Configuration")
project = st.sidebar.text_input("GCP Project ID", value=PROJECT)
dataset = st.sidebar.text_input("BigQuery Dataset", value=DATASET)

if not project or not dataset:
    st.stop()

# -------- Client (cache_resource!) --------
@st.cache_resource(show_spinner=False)
def get_client(proj: str):
    return bigquery.Client(project=proj)

client = get_client(project)

# -------- Helper to query DF --------
@st.cache_data(show_spinner=True, ttl=600)
def qdf(sql: str) -> pd.DataFrame:
    return client.query(sql).to_dataframe()

st.title("Instacart A/B Test (Simulated)")

# -------- Tabs --------
tab_overview, tab_tests, tab_cis, tab_cuped = st.tabs(
    ["Overview", "Significance", "Confidence Intervals", "CUPED"]
)

# ==================== OVERVIEW ====================
with tab_overview:
    try:
        # Check if table exists first
        vm = qdf(
            f"SELECT variant, users, converters, conversion_rate, arpu, arpu_var "
            f"FROM `{project}.{dataset}.variant_metrics`"
        )
        
        if vm.empty:
            st.error("The variant_metrics table exists but contains no data.")
            st.stop()

        st.subheader("Variant metrics")
        st.dataframe(vm, use_container_width=True)

        # metric cards
        a = vm.loc[vm["variant"] == "A"].iloc[0]
        b = vm.loc[vm["variant"] == "B"].iloc[0]
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Users A", int(a["users"]))
            st.metric("Users B", int(b["users"]))
        with c2:
            st.metric("Conversion A", f"{a['conversion_rate']*100:.2f}%")
            st.metric("Conversion B", f"{b['conversion_rate']*100:.2f}%")
        with c3:
            st.metric("ARPU (items) A", f"{a['arpu']:.2f}")
            st.metric("ARPU (items) B", f"{b['arpu']:.2f}")

        chart_df = vm[["variant", "conversion_rate", "arpu"]].copy()
        chart_df["conversion_%"] = chart_df["conversion_rate"] * 100
        chart_df = chart_df.melt(
            id_vars="variant",
            value_vars=["conversion_%", "arpu"],
            var_name="metric",
            value_name="value",
        )

        st.subheader("Overview chart")
        try:
            # Pivot the data for better chart display
            chart_pivot = chart_df.pivot(index="metric", columns="variant", values="value")
            st.bar_chart(chart_pivot)
        except Exception as chart_error:
            st.warning("Chart display failed, showing raw data instead:")
            st.dataframe(chart_df, use_container_width=True)

        # SRM (chi-square vs 50/50)
        st.subheader("Sanity check — SRM")
        users_a = int(a["users"])
        users_b = int(b["users"])
        total = users_a + users_b
        expected = np.array([0.5, 0.5]) * total
        observed = np.array([users_a, users_b])
        chi2 = ((observed - expected) ** 2 / expected).sum()
        pval = 1 - stats.chi2.cdf(chi2, df=1)
        st.write(
            {
                "users_A": users_a,
                "users_B": users_b,
                "chi2": float(chi2),
                "p": float(pval),
                "interpretation": (
                    "No SRM (p > 0.05)" if pval > 0.05 else "Potential SRM (p ≤ 0.05)"
                ),
            }
        )

    except Exception as e:
        st.error(
            "Failed to load `variant_metrics`. Check project/dataset and that the table exists."
        )
        st.exception(e)

# ==================== SIGNIFICANCE ====================
with tab_tests:
    st.subheader("Binary metric — Conversion (two-proportion z-test)")

    try:
        # Re-fetch vm data to ensure it's available in this tab
        vm = qdf(
            f"SELECT variant, users, converters, conversion_rate, arpu, arpu_var "
            f"FROM `{project}.{dataset}.variant_metrics`"
        )
        vm = vm.set_index("variant")
        
        a_n = int(vm.loc["A", "users"])
        b_n = int(vm.loc["B", "users"])
        a_x = int(vm.loc["A", "converters"])
        b_x = int(vm.loc["B", "converters"])
        p_a = a_x / a_n
        p_b = b_x / b_n

        se = np.sqrt((p_a * (1 - p_a)) / a_n + (p_b * (1 - p_b)) / b_n)
        z_conv = (p_b - p_a) / se if se > 0 else 0.0
        p_conv = 2 * (1 - stats.norm.cdf(abs(z_conv)))

        st.write(
            {
                "A_rate": p_a,
                "B_rate": p_b,
                "B_minus_A": p_b - p_a,
                "z": float(z_conv),
                "p": float(p_conv),
            }
        )

        st.subheader("Continuous metric — ARPU (Welch t-test from summary stats)")
        m_a = float(vm.loc["A", "arpu"])
        m_b = float(vm.loc["B", "arpu"])
        v_a = float(vm.loc["A", "arpu_var"])
        v_b = float(vm.loc["B", "arpu_var"])

        se_welch = np.sqrt(v_a / a_n + v_b / b_n)
        t_arpu = (m_b - m_a) / se_welch if se_welch > 0 else 0.0
        
        num = (v_a / a_n + v_b / b_n) ** 2
        den = (v_a**2) / ((a_n**2) * (a_n - 1)) + (v_b**2) / ((b_n**2) * (b_n - 1))
        df = num / den if den > 0 else (a_n + b_n - 2)
        p_arpu = 2 * (1 - stats.t.cdf(abs(t_arpu), df))

        st.write(
            {
                "mean_A": m_a,
                "mean_B": m_b,
                "diff_B_minus_A": m_b - m_a,
                "t": float(t_arpu),
                "df": float(df),
                "p": float(p_arpu),
            }
        )

    except Exception as e:
        st.error(
            "Significance section failed (check vm columns: users, converters, conversion_rate, arpu, arpu_var)."
        )
        st.exception(e)

# ==================== CIs (bootstrap) ====================
with tab_cis:
    st.subheader("Bootstrap confidence intervals")

    st.info(
        "Bootstrap CIs need per-user data. Load `user_outcomes`? "
        "If not available, we can show analytic CIs from vm instead."
    )

    # ---- Option A: per-user (recommended) ----
    try:
        uo = qdf(
            f"""
          SELECT user_id, variant, converted, retained_d14, items_in_window
          FROM `{project}.{dataset}.user_outcomes`
        """
        )
        st.success("Loaded per-user outcomes for bootstrap.")
        B = st.slider("Bootstrap samples", 500, 4000, 2000, 500, key="B_cis")

        @st.cache_data(show_spinner=True, ttl=600)
        def bootstrap_ci_mean_diff(a_vals, b_vals, B: int, seed: int = 42):
            rng = np.random.default_rng(seed)
            na, nb = len(a_vals), len(b_vals)
            diffs = np.empty(B, float)
            for i in range(B):
                ai = rng.choice(a_vals, size=na, replace=True)
                bi = rng.choice(b_vals, size=nb, replace=True)
                diffs[i] = bi.mean() - ai.mean()
            lo, hi = np.percentile(diffs, [2.5, 97.5])
            return float(diffs.mean()), (float(lo), float(hi))

        @st.cache_data(show_spinner=True, ttl=600)
        def bootstrap_ci_prop_diff(a01, b01, B: int, seed: int = 43):
            rng = np.random.default_rng(seed)
            na, nb = len(a01), len(b01)
            diffs = np.empty(B, float)
            for i in range(B):
                ai = rng.choice(a01, size=na, replace=True)
                bi = rng.choice(b01, size=nb, replace=True)
                diffs[i] = bi.mean() - ai.mean()
            lo, hi = np.percentile(diffs, [2.5, 97.5])
            return float(diffs.mean()), (float(lo), float(hi))

        # Ensure data types are correct
        a_conv = uo.loc[uo.variant == "A", "converted"].fillna(0).astype(int).to_numpy()
        b_conv = uo.loc[uo.variant == "B", "converted"].fillna(0).astype(int).to_numpy()
        a_ret = uo.loc[uo.variant == "A", "retained_d14"].fillna(0).astype(int).to_numpy()
        b_ret = uo.loc[uo.variant == "B", "retained_d14"].fillna(0).astype(int).to_numpy()
        a_arpu = uo.loc[uo.variant == "A", "items_in_window"].fillna(0).to_numpy()
        b_arpu = uo.loc[uo.variant == "B", "items_in_window"].fillna(0).to_numpy()

        cr_diff, cr_ci = bootstrap_ci_prop_diff(a_conv, b_conv, B, seed=100)
        ret_diff, ret_ci = bootstrap_ci_prop_diff(a_ret, b_ret, B, seed=101)
        ar_diff, ar_ci = bootstrap_ci_mean_diff(a_arpu, b_arpu, B, seed=102)

        def bootstrap_samples_mean_diff(a_vals, b_vals, B: int, seed: int = 123):
            rng = np.random.default_rng(seed)
            na, nb = len(a_vals), len(b_vals)
            diffs = np.empty(B, dtype=float)
            for i in range(B):
                ai = rng.choice(a_vals, size=na, replace=True)
                bi = rng.choice(b_vals, size=nb, replace=True)
                diffs[i] = bi.mean() - ai.mean()
            return diffs

        samples = bootstrap_samples_mean_diff(a_arpu, b_arpu, B, seed=202)
        fig, ax = plt.subplots(figsize=(6, 3))
        ax.hist(samples, bins=60, color="#3b82f6", alpha=0.8)
        ax.axvline(
            np.mean(samples),
            color="black",
            lw=2,
            label=f"Mean diff = {np.mean(samples):.3f}",
        )
        ax.axvline(
            np.percentile(samples, 2.5), color="red", ls="--", lw=1, label="95% CI"
        )
        ax.axvline(np.percentile(samples, 97.5), color="red", ls="--", lw=1)
        ax.set_title("Bootstrap distribution: ARPU difference (B − A)")
        ax.set_xlabel("Difference in mean items per user")
        ax.legend()
        st.pyplot(fig)

        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "metric": "Conversion (28d)",
                        "diff_B_minus_A": cr_diff,
                        "ci_low": cr_ci[0],
                        "ci_high": cr_ci[1],
                    },
                    {
                        "metric": "Retention (D14)",
                        "diff_B_minus_A": ret_diff,
                        "ci_low": ret_ci[0],
                        "ci_high": ret_ci[1],
                    },
                    {
                        "metric": "ARPU (items)",
                        "diff_B_minus_A": ar_diff,
                        "ci_low": ar_ci[0],
                        "ci_high": ar_ci[1],
                    },
                ]
            ),
            use_container_width=True,
        )

    except Exception:
        st.warning("Per-user table missing. Showing analytic CIs from vm instead.")
        try:
            # Analytic CI for conversion diff from counts
            vm_fallback = qdf(
                f"SELECT variant, users, converters, conversion_rate, arpu, arpu_var "
                f"FROM `{project}.{dataset}.variant_metrics`"
            ).set_index("variant")
            
            a_n = int(vm_fallback.loc["A", "users"])
            b_n = int(vm_fallback.loc["B", "users"])
            a_x = int(vm_fallback.loc["A", "converters"])
            b_x = int(vm_fallback.loc["B", "converters"])
            p_a = a_x / a_n
            p_b = b_x / b_n
            se = np.sqrt((p_a * (1 - p_a)) / a_n + (p_b * (1 - p_b)) / b_n)
            z = stats.norm.ppf(0.975)
            conv_low = (p_b - p_a) - z * se
            conv_high = (p_b - p_a) + z * se

            # Analytic CI for ARPU diff via Welch
            m_a = float(vm_fallback.loc["A", "arpu"])
            m_b = float(vm_fallback.loc["B", "arpu"])
            v_a = float(vm_fallback.loc["A", "arpu_var"])
            v_b = float(vm_fallback.loc["B", "arpu_var"])
            se_ar = np.sqrt(v_a / a_n + v_b / b_n)
            diff_ar = m_b - m_a
            df_num = (v_a / a_n + v_b / b_n) ** 2
            df_den = (v_a**2) / ((a_n**2) * (a_n - 1)) + (v_b**2) / (
                (b_n**2) * (b_n - 1)
            )
            df = df_num / df_den if df_den > 0 else a_n + b_n - 2
            tcrit = stats.t.ppf(0.975, df)
            ar_low = diff_ar - tcrit * se_ar
            ar_high = diff_ar + tcrit * se_ar

            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "metric": "Conversion (28d)",
                            "diff_B_minus_A": p_b - p_a,
                            "ci_low": conv_low,
                            "ci_high": conv_high,
                        },
                        {
                            "metric": "ARPU (items)",
                            "diff_B_minus_A": diff_ar,
                            "ci_low": ar_low,
                            "ci_high": ar_high,
                        },
                    ]
                ),
                use_container_width=True,
            )
        except Exception as e:
            st.error("Could not compute analytic CIs from vm.")
            st.exception(e)

# ==================== SIGNIFICANCE ====================
with tab_tests:
    st.subheader("Binary metric — Conversion (two-proportion z-test)")

    try:
        # Re-fetch vm data to ensure it's available in this tab
        vm = qdf(
            f"SELECT variant, users, converters, conversion_rate, arpu, arpu_var "
            f"FROM `{project}.{dataset}.variant_metrics`"
        )
        vm = vm.set_index("variant")
        
        a_n = int(vm.loc["A", "users"])
        b_n = int(vm.loc["B", "users"])
        a_x = int(vm.loc["A", "converters"])
        b_x = int(vm.loc["B", "converters"])
        p_a = a_x / a_n
        p_b = b_x / b_n

        se = np.sqrt((p_a * (1 - p_a)) / a_n + (p_b * (1 - p_b)) / b_n)
        z_conv = (p_b - p_a) / se if se > 0 else 0.0
        p_conv = 2 * (1 - stats.norm.cdf(abs(z_conv)))

        st.write(
            {
                "A_rate": p_a,
                "B_rate": p_b,
                "B_minus_A": p_b - p_a,
                "z": float(z_conv),
                "p": float(p_conv),
            }
        )

        st.subheader("Continuous metric — ARPU (Welch t-test from summary stats)")
        m_a = float(vm.loc["A", "arpu"])
        m_b = float(vm.loc["B", "arpu"])
        v_a = float(vm.loc["A", "arpu_var"])
        v_b = float(vm.loc["B", "arpu_var"])

        se_welch = np.sqrt(v_a / a_n + v_b / b_n)
        t_arpu = (m_b - m_a) / se_welch if se_welch > 0 else 0.0
        
        num = (v_a / a_n + v_b / b_n) ** 2
        den = (v_a**2) / ((a_n**2) * (a_n - 1)) + (v_b**2) / ((b_n**2) * (b_n - 1))
        df = num / den if den > 0 else (a_n + b_n - 2)
        p_arpu = 2 * (1 - stats.t.cdf(abs(t_arpu), df))

        st.write(
            {
                "mean_A": m_a,
                "mean_B": m_b,
                "diff_B_minus_A": m_b - m_a,
                "t": float(t_arpu),
                "df": float(df),
                "p": float(p_arpu),
            }
        )

    except Exception as e:
        st.error(
            "Significance section failed (check vm columns: users, converters, conversion_rate, arpu, arpu_var)."
        )
        st.exception(e)

# ==================== CUPED ====================
with tab_cuped:
    st.subheader("CUPED — requires per-user pre-period covariate")
    try:
        uop = qdf(
            f"""
          SELECT variant, items_in_window AS Y, items_pre AS X
          FROM `{project}.{dataset}.user_outcomes_with_pre`
        """
        )
        uop["X"] = uop["X"].fillna(0.0)
        X = uop["X"].to_numpy(float)
        Y = uop["Y"].to_numpy(float)
        varX = np.var(X, ddof=1)
        covYX = np.cov(Y, X, ddof=1)[0, 1]
        theta = covYX / varX if varX > 0 else 0.0
        uop["Y_cuped"] = Y - theta * (X - X.mean())

        raw_var = uop.groupby("variant")["Y"].var().mean()
        adj_var = uop.groupby("variant")["Y_cuped"].var().mean()
        vr_pct = 100 * (1 - adj_var / raw_var)

        a_raw = uop.loc[uop.variant == "A", "Y"].to_numpy()
        b_raw = uop.loc[uop.variant == "B", "Y"].to_numpy()
        a_adj = uop.loc[uop.variant == "A", "Y_cuped"].to_numpy()
        b_adj = uop.loc[uop.variant == "B", "Y_cuped"].to_numpy()

        t_raw, p_raw = stats.ttest_ind(b_raw, a_raw, equal_var=False)
        t_adj, p_adj = stats.ttest_ind(b_adj, a_adj, equal_var=False)

        st.write(
            {
                "theta": float(theta),
                "variance_reduction_%": float(vr_pct),
                "t_raw": float(t_raw),
                "p_raw": float(p_raw),
                "t_cuped": float(t_adj),
                "p_cuped": float(p_adj),
            }
        )
    except Exception as e:
        st.info("Build `user_outcomes_with_pre` in BigQuery first (items_pre).")
        st.exception(e)

# -------- Summary (optional) --------
st.header("Results Summary")
st.markdown(
    """
- **SRM:** Split is balanced.
- **Conversion (28d):** No significant difference; CI ~ ±0.4pp.
- **Retention (D14):** No significant difference; CI ~ ±0.5pp. (Shown if per-user data loaded.)
- **ARPU:** No significant difference; CI ~ ±0.2 items.
- **CUPED:** Variance reduced substantially; effect unchanged (~0).
"""
)
