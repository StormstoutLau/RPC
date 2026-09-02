---
name: "math-finance-reasoning"
description: "Six-layer reasoning architecture for mathematical finance tasks combining theorem proving, numerical algorithms, academic taste, and cross-disciplinary associations. Invoke when user requests paper review, theorem verification, framework design, numerical result analysis, research strategy, or any task requiring rigorous mathematical reasoning with strategic judgment. AUTO-ACTIVATES when mathematical structures (operator norm, Fréchet derivative, phase transition, spectral decomposition, etc.) appear in context — proactively connects to adjacent fields. Extracted from cross-validated analysis of 12 Claude reasoning sessions."
---

# Math Finance Six-Layer Reasoning Architecture

## Overview

This skill implements a six-layer reasoning architecture distilled from cross-validated analysis of 12 Claude reasoning sessions across quantitative finance, econometrics, operator theory, mathematical finance, and cross-domain applications. It is designed specifically for tasks that combine multiple cognitive demands: mathematical proof, computational algorithms, academic judgment, and cross-disciplinary thinking.

**Engine vs Fuel**: This skill encodes the reasoning architecture (engine). Domain knowledge (fuel) must be injected by the user at each invocation — the skill does not possess domain knowledge on its own.

## When to Activate

Activate this skill when the user's request involves any of:
- Paper review, theorem verification, mathematical proof checking
- Framework design, architecture analysis, methodology evaluation
- Numerical experiment interpretation, pattern analysis in data
- Cross-domain analogy, methodological generalization
- Research strategy, publication decisions, direction selection
- Any task labeled as "review" or "rigorous analysis" in a mathematical finance context

### Automatic Triggers: Mathematical Structure Detection

**CRITICAL**: This skill must also auto-activate when any of the following mathematical structures are detected in the current context (user's papers, code, conversation, or project memory), regardless of whether the user explicitly requested review or analysis:

| Mathematical Structure | Trigger Keywords | Adjacent Fields to Connect |
|------------------------|-----------------|---------------------------|
| Operator norm on pricing function | `‖D𝒫_θ‖`, `operator norm`, `Fréchet derivative`, `tangent map` | Model uncertainty (Cont 2006), sensitivity analysis, statistical learning theory (Rademacher complexity) |
| Spectral decomposition | `λ_max`, `eigenvalue`, `spectral radius`, `principal component` | Random matrix theory, dynamical systems (Lyapunov exponents), PCA in statistics |
| Phase transition / critical threshold | `τ_c`, `critical curve`, `phase boundary`, `regime change` | Statistical physics (Ising model), bifurcation theory, change-point detection |
| Coupled SDE / feedback loop | `dβ_t = ... + η_β(p_t - p̄)`, `mutual excitation`, `cross-dependence` | Lotka-Volterra dynamics, Hawkes processes, neuroscience (coupled oscillators) |
| Copula dependence structure | `Gaussian copula`, `t-copula`, `tail dependence`, `rank correlation` | Extreme value theory, vine copulas, information geometry |
| FRTB / regulatory capital | `CVA-MR`, `capital add-on`, `model risk`, `SIMM` | Banking regulation, stress testing, systemic risk |
| Implied volatility surface | `σ_imp(K,T)`, `volatility smile`, `vol surface dynamics` | Stochastic volatility (Heston, SABR), rough volatility, optimal transport |
| Fréchet differentiability in L² | `Banach space`, `Hilbert space`, `functional derivative`, `Gateaux` | Functional analysis, calculus of variations, PDE theory |
| Conduction / propagation | `conduction intensity`, `propagation`, `contagion`, `spillover` | Network theory, epidemiology, information diffusion |
| Jacobian rank / identifiability | `rank(J)`, `local diffeomorphism`, `parameter identifiability` | Differential geometry, inverse problems, econometric identification |

**Protocol**: When any of these structures are detected:
1. Activate the full six-layer architecture, even if the user's explicit task is narrow (e.g., "edit this paragraph" or "compile the paper")
2. Execute Layer 2 (COMPETE) in cross-domain mode — search for connections to the adjacent fields listed above
3. If a non-trivial connection is found, flag it as a **Proactive Insight** before proceeding with the user's explicit task
4. Format: `[PROACTIVE] This [structure] connects to [adjacent field] via [specific bridge]. The connection is [trivial/known/novel]. [One-sentence implication for your work.]`
5. If the connection is novel (not already in the user's paper or project memory), ask the user whether to explore it

**Example**:
> [PROACTIVE] The operator norm `‖D𝒫_θ‖` in your CDO framework connects to model uncertainty (Cont 2006) via the shared structure of "worst-case sensitivity over a parameter ball." The connection is known (Cont is already in your references). Implication: your τ² can be framed as a Cont-type model uncertainty measure applied specifically to copula parameters, which strengthens your positioning in the quantitative finance literature.

---

## The Six-Layer Architecture

Execute the following layers sequentially. Each layer produces output that feeds into the next.

### Layer 1: CRACK — Fracture Detection

**Purpose**: Identify all problems, classify as fatal vs non-fatal.

**Instructions**:
1. For each claim, assumption, or derivation step in the target:
   - List all conditions under which it could fail
   - For each condition, ask: "If this fails, what is the consequence?"
   - Classify as **FATAL** (framework collapses) or **NON-FATAL** (fixable)
2. For each fatal issue, check: "Is this already covered by existing proofs/theorems in the document?"
3. Output: a ranked list of issues with `[FATAL]` / `[NON-FATAL]` tags, each with a one-sentence consequence statement.

**Pattern to avoid**: Flat listing of problems ("Problem 1, Problem 2, Problem 3"). Instead, use causal chains: "Problem A, because A's simplified form is X, and if X holds then consequence is Y."

**Real example from CDO paper analysis**:
> "Problem 1 (information increment) is FATAL — if τ is merely a relabeling of base correlation, the entire framework has no reason to exist. Test: derive the simplified expression of τ, compare it to base correlation's functional form, and check if the mapping is monotonic."

### Layer 2: COMPETE — Alternative Hypothesis Generation

**Purpose**: Construct alternatives and compare incremental value.

**Instructions**:
1. For each core claim of the target framework, construct 2-3 simpler alternatives:
   - "If we didn't use this framework, what would we do?"
   - "What is the simplest possible approach to the same problem?"
2. For each alternative, explicitly state:
   - The dimension where the target framework claims superiority
   - Whether that superiority is in predictive accuracy, interpretability, computational efficiency, or theoretical insight
3. If the incremental value is zero in all dimensions → the framework needs redesign.
4. If the incremental value is in "interpretability" rather than "predictive accuracy" → explicitly flag this.

**Real example from CDO paper analysis**:
> Alternative 1: PCA on implied correlation surface directly.
> Alternative 2: Monitor copula parameters directly with change-point detection.
> Alternative 3: End-to-end deep learning prediction.
> → CDO framework's incremental value is in interpretability, not prediction accuracy. "For market makers and risk managers, the latter matters more — they need to know why, not just what."

### Layer 3: TRACE — Root Cause Tracking

**Purpose**: Trace from surface phenomenon to fundamental mathematical fact.

**Instructions**:
1. For each numerical phenomenon or logical gap:
   - Ask "why?" repeatedly, each step going one level deeper
   - Stop only when reaching a **fundamental fact** that cannot be further decomposed
2. Termination conditions:
   - **Mathematics**: basic calculus / linear algebra / probability theory facts (e.g., `dΦ⁻¹(p)/dp = 1/φ(Φ⁻¹(p))`)
   - **Logic**: a contradiction in definitions themselves
   - **Engineering**: hardware or data structure limitations
3. When reaching the termination condition, **explicitly declare**: "This is the root. Nothing deeper."

**Real example from CDO paper analysis**:
> Three numerical phenomena → traced to common root → `∂h/∂p = (1-R)·φ(z)·(1/√(1-β²))·[1/φ(Φ⁻¹(p))]` → "The entire chain of theorems rests on the derivative of the normal CDF inverse. That's it."

### Layer 4: UPGRADE — Theorem-ization

**Purpose**: Upgrade numerical patterns to theorem candidates.

**Instructions**:
1. For each numerical pattern identified:
   - Judge: is this "theorem-grade"? (Non-trivial, not accidental, has a proof path)
   - If yes: produce a theorem statement + sketch of key proof steps
   - If no: suggest counterexample search or additional numerical experiments
2. For each theorem candidate:
   - Label the hardest step in the proof
   - Classify: requires new tools / standard tools suffice / trivial
3. Output: "Theorem N: [statement]. Key proof step: [the one non-trivial move]. Difficulty: [new/standard/trivial]."

**Pattern to avoid**: "You should prove this." Instead: "Here is a theorem. The key proof step is X. The difficulty is Y."

**Real example from CDO paper analysis**:
> Theorem A (Amplification Divergence): ∂ρ_base/∂p = 0 identically, while ∂τ/∂p ∝ A(p)² → ∞ as p → 0.
> Key proof step: show that the active region width A(p) = Φ⁻¹(1-p) - Φ⁻¹(p) grows without bound.
> Difficulty: standard (implicit function theorem + chain rule).

### Layer 5: NARRATE — Theorem-Driven Storytelling

**Purpose**: Translate theorems into practitioner language with historical anchoring.

**Instructions**:
1. For each theorem or core finding:
   - Translate to practitioner language: "If you are a risk manager, this means..."
   - Anchor to a historical event (2008 subprime, 2011 Euro crisis, 2020 COVID)
   - Ensure every sentence traces back to a specific theorem number or equation number
2. Label each sentence:
   - `[THEOREM]` — provable
   - `[COROLLARY]` — derivable from theorem
   - `[NARRATIVE]` — story-telling (not provable, but theorem-motivated)
3. Output: a 3-5 sentence narrative paragraph with labels.

**Real example from CDO paper analysis**:
> [THEOREM] The model is most fragile precisely when base correlation says it is most stable. [COROLLARY] Because low p → large A(p) → high τ, while low p → small expected loss → ρ_base stable near β². [NARRATIVE] 2006-2007: subprime default rate p began to rise, but β was almost unchanged → ρ_base was almost unchanged → risk report said "base correlation stable" → no one noticed τ was already surging due to the A(p) effect. [THEOREM] This story is no longer a narrative. It is now a theorem.

### Layer 6: DECIDE — Information-Driven Strategic Judgment

**Purpose**: Make decisions based on available information, or design paths to acquire missing information.

**Instructions**:
1. Assess: is the current information sufficient to decide?
2. If sufficient → give the optimal action (what to do now).
3. If insufficient → design a path to acquire new information: "After doing X, we will know Y, and then we can decide Z."
4. Structure output as a three-level timeline:
   - **Now** (immediate action, no prerequisites)
   - **Short-term** (1-3 months, prerequisite: now-level action complete)
   - **Long-term** (6-12 months, prerequisite: short-term action complete)
5. Each level must have explicit prerequisites.

**Real example from CDO paper analysis**:
> Priority 1 (Now): Submit CDO paper. v6 is ready.
> Priority 2 (Short-term): arXiv. Submit to arXiv simultaneously with journal submission.
> Priority 3 (Long-term): Begin Phase 2 (empirical). General theory should be a PhD-long project.
> Strategic insight: "Let the market (reviewers) tell you the direction, rather than guessing yourself."

## Domain Knowledge Injection

Before executing the layers, explicitly request from the user (or extract from context):

| What to inject | Which layer needs it | Example |
|---------------|---------------------|---------|
| Known theorems and lemmas | CRACK, TRACE, UPGRADE | "Gaussian copula has closed-form conditional loss: ℓ(q) = ..." |
| Literature landscape | COMPETE | "Gu-Kelly-Xiu (2020) already does DL-based prediction" |
| Numerical data | TRACE, UPGRADE | "τ² ranges from 171 to 1019 across 380 dates" |
| Journal strategy | DECIDE | "SIFIN accepts methodology papers; MF prefers theoretical depth" |
| Candidate mathematical tools | TRACE, UPGRADE | "Weyl inequality vs Cauchy interlacing for eigenvalue bounds" |

**Critical rule**: If domain knowledge is missing, the skill must explicitly flag the gap rather than fabricate. Say "I need to know X before I can execute Layer Y" rather than guessing.

## Output Format

Structure all outputs as:

```markdown
## Layer N: [NAME]

[Layer-specific output]

### Key Finding
[The single most important insight from this layer]

### Confidence
[★★★★★] — fully verified
[★★★★☆] — likely correct, minor assumption
[★★★☆☆] — plausible, needs verification
[★★☆☆☆] — speculative
[★☆☆☆☆] — guess
```

## Interaction with Other Skills

This skill provides a higher-level reasoning architecture. When specific sub-tasks arise, it should delegate to specialized skills:
- **academic-paper-reviewer**: for multi-perspective paper review (Layer 1 CRACK)
- **deep-research**: for literature search (Layer 2 COMPETE, Layer 4 UPGRADE)
- **scientific-critical-thinking**: for evidence quality assessment (Layer 3 TRACE)
- **citation-management**: for reference verification (cross-layer)

## Edge Cases and Failure Modes

**Over-identification**: CRACK layer may find too many "fatal" issues in a work that is fundamentally sound. Mitigation: always check "is this issue already covered by existing proofs in the document?"

**Over-tracing**: TRACE layer may continue past the termination condition, asking "why" about basic facts. Mitigation: use the explicit termination conditions (basic calculus / linear algebra / probability theory).

**Under-narrating**: NARRATE layer may produce generic stories not anchored to theorems. Mitigation: require every narrative sentence to cite a theorem or equation number.

**Premature decision**: DECIDE layer may recommend action before sufficient information is gathered. Mitigation: always start DECIDE with an explicit information assessment.

## Cross-Validation Evidence

This architecture was extracted from 12 Claude reasoning sessions and cross-validated against 6 sessions across 5 domains:

| Domain | CRACK | COMPETE | TRACE | UPGRADE | NARRATE | DECIDE |
|--------|-------|---------|-------|---------|---------|--------|
| CDO + Operator Theory | ✓✓✓ | ✓✓✓ | ✓✓✓ | ✓✓✓ | ✓✓✓ | ✓✓✓ |
| Quant Engineering | ✓✓✓ | ✓ | ✓✓ | — | — | — |
| Econometrics | ✓✓✓ | ✓✓ | ✓✓ | ✓ | — | — |
| Operator Theory + R-vine | ✓✓✓ | ✓ | ✓✓✓ | ✓✓ | — | — |
| Mathematical Finance | ✓✓✓ | ✓ | ✓✓✓ | ✓✓ | — | ✓ |
| Cross-domain Application | ✓✓ | ✓✓✓ | ✓✓ | ✓ | ✓✓✓ | ✓✓ |

**Key insight**: Full six-layer activation only occurs in complete research cycles (problem → solution → theorem → narrative → strategy). Partial activation is normal for focused tasks (e.g., pure engineering activates only CRACK + TRACE).

For full analysis documentation, see `CLAUDE_REASONING_ARCHITECTURE.md` in the project root.