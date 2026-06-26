---
name: statistics-time-series-and-longitudinal-models
description: Use when designing or reviewing repeated-measure, wearable, sensor, EMA, actigraphy, symptom-diary, time-series, cross-lag, mixed-effects, or longitudinal analyses.
---

# Time-Series and Longitudinal Models

Use when designing or reviewing analyses with repeated measurements over time:
wearables, sensors, actigraphy, EMA, symptom diaries, sleep/activity rhythms,
clinical follow-up, longitudinal omics, before/after designs, or cross-lag
coupling.

These analyses fail when time origin, sampling cadence, missingness, lag choice,
autocorrelation, and within-subject dependence are treated as implementation
details rather than estimand-defining assumptions.

## Pre-Flight Checklist

1. **Define the time axis.** Calendar time, time since diagnosis, time since
   treatment, circadian clock, study day, and event-centered time answer
   different questions.
2. **Name the independent unit.** Minute-level samples, diary entries, genes, or
   visits inside a participant are repeated observations; the participant,
   animal, patient, device, or cohort is usually the independent unit.
3. **Audit sampling cadence.** Record expected cadence, observed cadence,
   gaps, bursty sampling, timezone handling, and device-off periods.
4. **State the lag structure.** Pre-specify contemporaneous, lagged,
   cumulative, rolling-window, or cross-lag effects before looking at outcomes.
5. **Separate trend, seasonality, and events.** Circadian, weekday, seasonal,
   treatment, relapse, and study-fatigue effects can mimic associations.
6. **Plan missingness handling.** Missing-at-random, device non-wear, symptom
   non-response, hospitalization gaps, and dropout have different implications.

## Minimum QA Checks

| Check | Failure mode |
|---|---|
| Per-unit observation counts | A few dense units dominate the result |
| Gap and missingness audit | Missingness tracks exposure or outcome |
| Timezone and daylight-saving audit | Artificial shifts create rhythms |
| Autocorrelation / residual ACF | Standard errors are too small |
| Pre/post balance around events | Event windows are asymmetric |
| Lag sensitivity grid | Effect exists only for a cherry-picked lag |
| Subject-level influence | One participant or device drives the signal |

## Modeling Rules

- Use models that respect within-unit dependence: mixed-effects models,
  generalized estimating equations, state-space models, functional data models,
  distributed-lag models, or subject-level summaries as appropriate.
- Do not treat high-frequency rows as independent sample size. Power and
  uncertainty are bounded by the number of independent units and the number of
  informative transitions/events.
- Pre-specify aggregation windows before fitting. Minute, hour, day, and week
  summaries can reverse the estimand.
- For cross-lag or Granger-style claims, verify temporal ordering, stationarity
  assumptions, and sensitivity to lag length.
- For intervention or perturbation timelines, distinguish baseline drift from
  treatment response and include negative-control windows when available.

## Common Failure Modes

- **Pseudoreplication.** Thousands of sensor rows are counted as thousands of
  independent participants.
- **Retrospective lag search.** The reported lag is selected after scanning many
  alternatives without a locked arbitration rule.
- **Informative missingness.** Symptoms, device wear, or visits disappear
  exactly when the state of interest changes.
- **Clock artifacts.** Timezone, daylight-saving, or device resets create false
  phase shifts.
- **Regression to the mean.** Event-triggered analyses compare extremes to
  ordinary follow-up without a control window.

## Halt-On Conditions

- Time origin or sampling cadence is unknown.
- Missingness cannot be distinguished from the outcome or exposure process.
- The analysis counts repeated rows as independent units.
- Lag/window choice is not pre-specified for a verdict-bearing claim.

## Output Package

Generate a `datapackage.json` for this directory; see [`../data/frictionless.md`](../data/frictionless.md).

```
results/<analysis>/time_series_qa/
|-- input_manifest.json
|-- time_axis_audit.parquet
|-- sampling_cadence_audit.parquet
|-- missingness_gaps.parquet
|-- lag_window_config.yaml
|-- autocorrelation_diagnostics.parquet
|-- subject_influence.parquet
|-- sensitivity_results.parquet
`-- qa_summary.md
```

The summary should state the time origin, independent unit, cadence, lag/window
rule, missingness model, and any verdict downgrade caused by autocorrelation,
lag sensitivity, or influential units.

## Companion Skills

- [`survival-and-hierarchical-models.md`](survival-and-hierarchical-models.md) - mixed-effects, hierarchical, censoring, and grouped-outcome models.
- [`sensitivity-arbitration.md`](sensitivity-arbitration.md) - pre-committed rules for lag/window and missingness sensitivity.
- [`power-floor-acknowledgement.md`](power-floor-acknowledgement.md) - independent-unit and transition-count power floors.
- [`bias-vs-variance-decomposition.md`](bias-vs-variance-decomposition.md) - separating sampling/process bias from estimator variance.
