# Epistemic Debt Report — {TARGET_NAME}

- **Date:** {YYYY-MM-DD}
- **Scope:** {whole-repo | PR/diff vs origin/main}
- **Base (PR mode):** {origin/main @ SHA}
- **Overall grade:** {GRADE} — {debt band label}
- **Debt index (scope-relative):** {0-1} — drives the grade
- **Debt index (absolute):** {0-1} — fixed 4-layer scale, for cross-PR / cross-repo ranking
- **Respondent(s):** {who was tested}
- **Probe config:** format={free-text | multiple-choice}, {N}/layer, conditions=work-realistic (open)

## Verdict

{One-paragraph plain-language summary: is this debt or credit, which
layer dominates, and why it matters. In PR mode, frame as "debt this
change introduces," not total repo debt.}

## Per-layer assessment

| Layer | Complexity (Cₛ) | Grasp (Gₑ) | Gap | Cascade ×cₖ | Weighted |
|-------|-----------------|------------|-----|-------------|----------|
| L4 Requirements  | {0-5} | {0-5} | {gap} | 30 | {w} |
| L3 Architecture  | {0-5} | {0-5} | {gap} | 10 | {w} |
| L2 Design        | {0-5} | {0-5} | {gap} | 4  | {w} |
| L1 Implementation| {0-5} | {0-5} | {gap} | 1  | {w} |

*(Gap floored at 0; a negative gap means the layer carries epistemic
**credit** — surplus grasp that buffers future complexity.)*

## Observable evidence (Cₛ)

{What was scanned and found, with file paths / metrics. Keep to signals
that actually justify each layer's complexity score.}

## Tested grasp (Gₑ)

{Per layer: the question(s) asked and which part they probed, the
respondent's answer, the score (0-1), and the resulting 0-5 Gₑ. Cite the
`file:line` reference answers used to grade, so each verdict is auditable.
For articulated answers, grading is per claim — the answer score is the mean
of its claims' correctness; note any claims that pulled the score down.}

| Layer | Question | Claims (count) | Per-claim correctness | Answer correctness |
|-------|----------|----------------|-----------------------|--------------------|
| {L#}  | {label}  | {N}            | {[0-1, …]}            | {mean} |

*(One claim per independently checkable assertion — see the granularity rule
in `references/comprehension-probes.md`. The claim count is recorded so the
decomposition itself is auditable: `grasp.py` averages over the claims, so
the split is the score's denominator. Multiple-choice answers are a single
claim by construction.)*

## Calibration (confidence vs tested grasp)

| Layer | Tested Gₑ | Mean confidence | Gap (conf − correct) | Flag |
|-------|-----------|-----------------|----------------------|------|
| L4 Requirements  | {0-5} | {0-1} | {±} | {overconfident / calibrated / underconfident} |
| L3 Architecture  | {0-5} | {0-1} | {±} | {…} |
| L2 Design        | {0-5} | {0-1} | {±} | {…} |
| L1 Implementation| {0-5} | {0-1} | {±} | {…} |

*(Gap ≳ +0.3 = **overconfident** — the confident-and-wrong danger zone the
framework warns about. Diagnostic only; it does not change the grade.)*

## Dominant risk

{Which layer's weighted debt drives the grade, and the cascade it would
trigger if left unaddressed.}

## Recommended next actions (shift t₀ left)

1. {Highest-leverage remediation, tied to the dominant layer}
2. {…}
3. {…}

## Methodology & limitations

- **Method:** system complexity scanned from the repo; grasp **tested** via
  {N} grounded question(s) per layer, sampled toward the highest-complexity
  parts, graded against code-derived reference answers.
- **Format:** {free-text | multiple-choice} — {one-line tradeoff}.
- **Conditions:** work-realistic (code access not policed); questions probe
  reasoning a glance can't answer.
- **Limitations:** measures the respondent(s) above, not "the team"; at
  low depth (few questions/layer) a single question swings a layer's Gₑ; grading is
  LLM-judged (auditable via the cited references), done per claim for
  articulated answers; confidence is self-reported, one value per answer,
  asked in the same prompt as that answer and before any grading was shown.

## Recovery estimate (default rates)

`τₖ = gapₖ / rₖ` — rates in gap-points/eng-week; the defaults are
`DEFAULT_RATES` in `scripts/recovery.py` (rationale table in
`references/framework.md`). The rₖ column is each layer's `rate` from the
script's `per_layer` output, so it stays correct when Phase 5 substitutes
the team's measured rates. **ESTIMATE from default rates**, not the team's
measured rates.

| Layer | Gap | rₖ used | τₖ (eng-weeks) |
|-------|-----|---------|----------------|
| L4 Requirements  | {gap} | {rate} | {τ} |
| L3 Architecture  | {gap} | {rate} | {τ} |
| L2 Design        | {gap} | {rate} | {τ} |
| L1 Implementation| {gap} | {rate} | {τ} |

- **Layers assessed:** {layers_assessed} — when this is 0, the zeros below
  mean *nothing was measured* (every layer carried credit or was omitted),
  not a calibrated zero-week recovery.
- **Total recovery (T_recovery = Σ τₖ):** {weeks} engineer-weeks (estimate)
- **AI break-even:** AI-assisted work is a net loss when Σ cₖ·τₖ > δ
  (δ = dev time AI saved). Cascade-weighted cost Σ cₖ·τₖ = {value}; δ is
  unknown until the team provides it.

*This is a default-rate estimate. Re-run the quantitative deepening
(Phase 5) with your team's own learning rates and δ to replace it with a
calibrated recovery time and a real break-even verdict.*

---

*Graded with the **Epistemic Debt** framework by Antonino Rau —
[the math & the cost](https://antoninorau.substack.com/p/epistemic-debt-the-math-the-cost)
· [antoninorau.substack.com](https://antoninorau.substack.com/)*
