# Peer Review Report v2: HybridStream Paper for FGCS

**Paper:** A Hybrid Edge-Cloud Stream Processing Framework for Low-Latency Real-Time Analytics  
**Target:** Future Generation Computer Systems (Elsevier, Q1, IF ~7.5)  
**Review Type:** Pre-submission peer review (v2, post-revision)  
**Date:** 2026-03-20  
**Previous Review:** REVIEW_REPORT.md (v1)  

---

## Part A: Summary & Recommendation

**Summary:** This paper presents HybridStream, a hybrid edge-cloud stream processing framework whose Adaptive Offloading Decision Engine (AODE) dynamically places individual stateful operators across edge and cloud tiers based on a multi-factor scoring model incorporating EWMA-smoothed latency, resource utilization, SLO urgency, and transfer cost. The pause-checkpoint-transfer-resume (PCTR) protocol migrates stateful operators between tiers with bounded pause times (62–1,410 ms), and a lightweight Python-based edge runtime (HEA) reduces memory footprint by 95.3% relative to Flink TaskManagers. Experimental evaluation across three workloads, three network profiles, and 630 total runs demonstrates 99.2–99.8% SLO compliance with statistical rigor (Wilcoxon tests, bootstrap CIs, Bonferroni correction).

**Recommendation:** Minor Revision  
**Confidence:** 4/5 (high — I have reviewed extensively in stream processing, edge computing, and distributed systems)

**Rationale for Minor Revision:** The v1 review identified seven MUST-FIX items. The revised paper has addressed the majority: CRediT statement, funding statement, single-author language, and expanded related work with Cardellini, NebulaStream, Heinze, Kalavri, Dhalion, Pietzuch, Akhter, De Matteis, and others are now present. The reference count has risen from ~39 to ~58 cited unique keys. AI writing patterns have been substantially reduced ("comprehensive" and "fundamentally" appear to be eliminated). However, several issues remain that a careful reviewer will flag.

---

## Part B: Strengths

**S1. Rigorous statistical methodology.** The paper employs Wilcoxon signed-rank tests (appropriate for right-skewed latency distributions), Bonferroni correction for multiple comparisons, rank-biserial correlation effect sizes, and 95% bootstrap confidence intervals from 10,000 resamples across 10 repetitions per configuration. This is well above the field average and demonstrates genuine statistical literacy.

**S2. Well-formulated problem with clean NP-hardness argument.** The reduction from bin-packing (Section 3.2) is correctly stated and motivated. The formalization in Section 3.1 cleanly separates the model from the heuristic, and the AODE scoring model is presented as a polynomial-time heuristic rather than claiming optimality.

**S3. Thorough PCTR protocol description.** The four-phase migration protocol (Section 4.3) is described with sufficient detail that an independent implementation would be feasible. The fault-tolerance analysis (covering failures at each phase) is well-reasoned.

**S4. Honest limitations and threats to validity.** Section 7.4.2 and 7.4.3 candidly discuss single cloud instance, Python performance ceiling, hysteresis threshold tuning, and edge node failure assumptions. The paper also honestly notes that per-record SLO compliance tracking is a limitation of the current M2 metric. This is commendable.

**S5. Physical hardware evaluation.** The use of actual Intel NUC hardware (not simulation) with tc netem for WAN emulation, combined with detailed hardware/software version reporting, strengthens the evaluation's credibility.

**S6. Strong expanded related work.** The revised related work now covers Cardellini et al. (2016, 2018), NebulaStream, Heinze et al., Kalavri et al., Dhalion, Pietzuch et al., Akhter et al., De Matteis and Mencagli, Nardelli et al., and SpanEdge. Table 1 and the gap analysis are well-constructed.

**S7. Clean architectural decomposition.** The separation of concerns between HEA (edge runtime), AODE (decision engine), Flink Connector (cloud integration), and Kafka (inter-tier messaging) is principled. The design satisfies the stated requirements R1–R6 with clear traceability.

---

## Part C: Weaknesses (Exhaustive)

### STRUCTURAL COMPLETENESS

**W1. Abstract mostly matches body, but is overlong for the content.**  
The abstract (244 words) contains all key numbers (99.2–99.8%, 2.4–6.8 pp, 5.7%, 55.2 MB, etc.) and these match the body. However, the abstract reads more like a mini-conclusion than a concise summary — it packs in too many specific numbers. FGCS allows up to 400 words but shorter abstracts with fewer specific numbers and a clearer narrative arc tend to perform better.

**W2. Duplicate CRediT and Funding sections.**  
Lines 919–925 and 928–934 contain *identical* duplicates of both the CRediT authorship contribution statement and the Funding statement. This is a copy-paste error that must be fixed before submission. An editor will notice immediately.

**W3. Highlights exceed 85-character Elsevier limit.**  
The highlights.txt file contains items of 175, 179, 244, 200, and ~180 characters. Elsevier FGCS requires each highlight to be ≤85 characters. All five highlights need to be rewritten to fit this constraint. The LaTeX \begin{highlights} items are also too long (109–166 chars). This is a **desk reject risk** for FGCS.

**W4. Only 1 figure in the entire paper.**  
For a 30+ page systems paper with 10 tables, having a single architecture diagram is inadequate. Reviewers will expect at minimum:
- A time-series figure showing AODE behavior during a load spike (ingest rate, utilization, placement decisions, SLO compliance over time)
- A latency CDF or box plot comparing the three systems
- A migration timeline showing PCTR phases and their durations

Tables alone cannot convey the dynamic behavior that is the paper's core contribution.

**W5. Section cross-references use periods instead of colons in "road map" paragraph.**  
Line 95: "Section 2 surveys related work across four thematic areas. centralized stream processing frameworks..." — the period after "areas" should be a colon. Similarly, "strategies. positioning HybridStream" should be "strategies, positioning HybridStream". This produces a sentence fragment.

**W6. Line 95: Malformed citation.**  
`paradigm~\cite{yousefpour2019all}s` — the "s" is appended outside the citation, producing "paradigm[XX]s" in the rendered output. Should be "paradigms~\cite{yousefpour2019all}".

**W7. Algorithm references appear adequate** — Algorithm 1 (recalibration) is discussed in Section 4.2.3 with line-by-line explanation. ✅

**W8. Equations are numbered and referenced** — Eq. 1 (scoring model), Eq. 2 (EWMA), Eq. 3 (trend projection) are cross-referenced throughout. ✅

**W9. Gap statement between Related Work and Architecture is present** — Section 2.5 (Positioning) and the transition to Section 3 clearly articulate the gap. ✅

**W10. Conclusion is consistent with Introduction claims.** ✅ The conclusion restates the same metrics without inflation.

### TECHNICAL RIGOR

**W11. Experimental conditions are well-specified** — Hardware (Intel NUC 12 Pro, i5-1240P), OS (Ubuntu 22.04, kernel 5.15), Docker 25.0.3, Python 3.12.2, Java version for Flink are stated. ✅ (Minor: the specific Flink version number should be stated explicitly if not already — I see "Apache Flink" referenced but the exact version, e.g., 1.18.x, should be given.)

**W12. Workload generation is reproducible** — Deterministic timing, scripted Kafka producer replay controller, random seeds stated. ✅

**W13. Confidence intervals are properly computed** — 95% bootstrap CIs from 10,000 resamples. ✅

**W14. Statistical test is appropriate** — Wilcoxon signed-rank for non-Gaussian latency data. ✅

**W15. NP-hardness claim is properly stated** — Reduction from bin-packing is clean. ✅

**W16. AODE scoring model weight justification is thin.**  
The weight vector **w** = (w_l, w_r, w_n, w_s) is described as configurable with "three representative presets" (latency-first, balanced, resource-efficient) but no empirical justification is provided for *why* these specific weight values were chosen. The paper evaluates using one preset per workload (presumably latency-first for W1/W3, balanced for W2) but does not show what happens with different presets on the same workload. A sensitivity analysis showing SLO compliance and throughput across weight presets for at least one workload would strengthen the paper.

**W17. EWMA α=0.2 is calibrated** — "validated against network traces collected across the three evaluation deployments" (line 319). This is stated but the validation data is not shown. ✅ (acceptable, but showing a brief comparison of α=0.1 vs 0.2 vs 0.3 would be stronger).

**W18. Hysteresis Δ_h=0.15 is calibrated but not sensitivity-analyzed in the body.**  
The paper states (Section 4.2.3) that Δ_h=0.15 "was selected empirically by simulating recalibration over 48-hour telemetry traces" and that "it eliminates oscillation in all three workloads without delaying migrations that improve latency by more than 8% of SLO budget." However, no data is shown for alternative Δ_h values. Section 7.4.2 acknowledges this as a limitation. A reviewer may ask for at least a brief sensitivity table.

**W19. Warm-up periods are accounted for** — 10-minute warm-up with measurements discarded. ✅

**W20. Baselines are fairly configured** — Same hardware, same Kafka cluster, same network profiles. ✅ However, B1 (cloud-only) is a known strawman that will beat itself. The paper acknowledges this partially.

**W21. Contention coefficient κ=2.0 still lacks empirical justification.**  
Line 377 (or surrounding): κ=2.0 is "derived empirically from profiling" but no profiling data is shown. This was flagged in v1 and remains unaddressed. A reviewer may request the profiling methodology and results.

**W22. The B2 static hybrid baseline configuration — how was the static partition chosen?**  
The paper should clarify whether B2's static partition was chosen to be *optimal* for normal load conditions (giving B2 the best possible advantage) or arbitrary. If B2 isn't optimally configured, the comparison is unfair in HybridStream's favor.

### NOVELTY & POSITIONING

**W23. Differentiation from Cardellini et al. 2018 is now addressed** — Section 2.5 and Table 1 explicitly note that Cardellini's decentralized approach "does not include cross-tier state migration; operators are re-instantiated rather than migrated, losing accumulated state." ✅

**W24. NebulaStream differentiation is now addressed** — "operates at query granularity rather than individual operator granularity, and does not provide a state migration protocol." ✅

**W25. RL-based baseline absence is now explained** — Section 7.4.2 (or similar) notes that "existing RL-based approaches target discrete task offloading in request-response workloads rather than continuous stateful stream processing" and follows Cardellini et al.'s methodology of comparing against static and threshold baselines. This is a reasonable justification, though a reviewer may still push back.

**W26. PCTR vs. Flink's checkpoint-based migration — differentiation is implicit but not explicit.**  
The paper describes PCTR in detail but never directly states: "Here is how PCTR differs from Flink's native savepoint-based migration, and here is why that difference matters for cross-tier placement." The Flink Connector uses "savepoint-and-rescale operations" (line 300) but the distinction between PCTR (cross-tier, cross-runtime) and Flink-native (same-cluster) migration should be made explicit.

### WRITING QUALITY

**W27. AI patterns are substantially reduced but not eliminated.**  
See Part D for the full scan. The v1 paper had 108 em dashes; the current version has 28. "Comprehensive" and "fundamentally" appear to have been removed. However, several patterns remain:
- "paradigm" appears 4 times (lines 67, 95, 101, 113)
- "landscape" appears 2 times (lines 95, 115)
- "leverage" appears 1 time (line 77)
- "compelling" appears 2 times (lines 107, 117)
- "robust" appears 1 time (line 758)
- Em dashes still used 28 times (human baseline: 5–15 for a paper this length)

**W28. Massive single-paragraph sentences remain throughout.**  
The following lines contain single "paragraphs" exceeding 80 words (many exceeding 150+). This is the most persistent AI writing signal in the paper:

| Line | Word Count | Section |
|------|-----------|---------|
| 44 | 242 | Abstract |
| 65 | 152 | Introduction |
| 67 | 144 | Introduction |
| 69 | 208 | Introduction |
| 71 | 131 | Introduction |
| 77 | 183 | Introduction |
| 107 | **340** | Related Work §2.1 |
| 113 | 126 | Related Work §2.2 |
| 123 | 241 | Related Work §2.3 |
| 125 | 153 | Related Work §2.3 |
| 131 | 104 | Related Work §2.4 |
| 135 | 178 | Related Work §2.4 |
| 137 | 112 | Related Work §2.5 |
| 167 | 172 | Related Work §2.5 |
| 326 | 168 | Architecture §4.2.1 |
| 377 | 255 | Architecture §4.2.2 |
| 438 | ~200 | Architecture §4.3 |
| 440 | ~200 | Architecture §4.3 |
| 442 | ~150 | Architecture §4.3 |
| 444 | ~160 | Architecture §4.3 |
| 550 | 159 | Implementation §5 |
| 770 | 128 | Results §7.2 |
| 816 | 146 | Results §7.3 |

**Line 107 at 340 words is a single paragraph.** This is unacceptable in academic writing. It must be broken into at least 3–4 paragraphs. Similarly, the PCTR phases (lines 438–448) are each single-paragraph walls of 150–200 words.

**W29. Passive voice is used appropriately** — the paper uses active constructions with "we" frequently. ✅ Not overused.

**W30. Inconsistent terminology is minimal but present.**  
- "edge node" vs "HEA node" — the paper is mostly consistent, using "edge node" for physical hardware and "HEA" for the software agent. Acceptable.
- "recalibration cycle" vs "recalibration interval" — used interchangeably; should pick one.
- Line 105: Sentence structure is broken. "Apache Storm...demonstrated that continuous, real-time computation..." — the sentence has a parenthetical about T-Storm/R-Storm injected mid-sentence that derails the grammar. The main clause subject (Apache Storm) never reaches its main verb cleanly.

**W31. Undefined acronyms on first use — all appear to be defined.** ✅ IoT, SLO, AODE, HEA, PCTR, EWMA, MEC, RTT, DAG are all defined at first use.

**W32. Orphaned references.**  
Two .bib entries are never cited:
- `niknam2020federated` (Federated Learning for Wireless Communications)
- `sajjad2016spanedge` (SpanEdge: Multi-Span Placement)

These should be either cited in the text or removed from the .bib file. Additionally, several .bib entries are **duplicated** (same key appears twice with slightly different metadata):
- `zeuch2020nebulastream` (2 entries)
- `cardellini2016optimal` (2 entries)
- `cardellini2018decentralized` (2 entries)
- `heinze2014elastic` (2 entries)
- `kalavri2018three` (2 entries)
- `floratou2017dhalion` (2 entries)
- `pietzuch2006network` / `pietzuch2006sbon` (same paper, different keys)
- `xu2014tstorm` (2 entries)
- `peng2015rstorm` / `peng2015r` (same paper, different keys)
- `akhter2019stateful` (2 entries)
- `dematteis2017elastic` (2 entries)

This is a major .bib hygiene issue. Duplicate bib entries can cause LaTeX compilation warnings and may result in duplicate entries in the reference list. The Pietzuch and Peng papers are cited with *different* keys in different sections (pietzuch2006network in §2.1 and pietzuch2006sbon in §2.4; peng2015rstorm in §2.1 and peng2015r in §2.1), which will produce **two separate numbered references for the same paper** in the rendered bibliography. This is a glaring error.

### ELSEVIER/FGCS SPECIFIC

**W33. elsarticle class used correctly** — `\documentclass[preprint,review,12pt]{elsarticle}`. ✅

**W34. Highlights present but exceed 85-character limit.** ❌ See W3 above. Every single highlight exceeds the limit by 2–3x.

**W35. Keywords appear appropriate** — not checked in detail, but assuming standard stream processing/edge computing terms. ✅

**W36. Data Availability statement present.** ✅

**W37. CRediT statement present** — but duplicated (W2). Needs deduplication.

**W38. Declaration of Competing Interest present.** ✅

**W39. "et al." usage** — appears to be used correctly (for ≥3 authors). ✅

### REPRODUCIBILITY

**W40. Experiment reproducibility is good in principle** — hardware, software, seeds, warm-up, scripts all described. ✅

**W41. GitHub URL (github.com/umur/hybrid-stream) — accessibility not verified.**  
If this repository does not exist or is private at review time, this becomes a significant concern. The paper's Data Availability section (line 907) states the code is "publicly available." If it isn't at submission time, either make it available or note "will be made available upon acceptance."

**W42. Docker configurations described** — Docker version specified, HEA deployment described. ✅ (Though a docker-compose.yml or equivalent in the repo would be ideal.)

**W43. Random seeds specified.** ✅ — "independent random seeds for Kafka partition assignment and worker process initialization" (line 655).

**W44. W3 data availability concern persists.**  
The v1 review flagged that "publicly available NYSE/NASDAQ consolidated tape data" is not actually publicly available (CTA data requires paid subscription). The paper should clarify the exact data source. If using a filtered/derived trace, say so. If the trace is included in the GitHub repo, that resolves the concern.

---

## Part D: AI Writing Pattern Deep Scan

### Em Dashes (—)
**Count: 28 instances** (down from 108 in v1)

Key remaining instances:
1. Line 65: "processing infrastructure—in velocity and latency sensitivity"
2. Line 77: "its...AODE—a runtime architectural component"
3. Line 90: "two baselines—a cloud-only Apache Flink"
4. Line 109: "edge locations—the round-trip cost"
5. Line 113: "edge-proximate computation—motivations that remain"
6. Line 131: "key decision factors—task delay, energy expenditure"
7. Line 300: "Flink Connector—a thin adapter layer"
8. Line 326: multiple instances in telemetry collector description
9. Line 379: "constraint rather than a preference—satisfying R4"
10. Line 388: "the forward-projected ingest rate...—with lookahead horizon H = 30"
11. Line 399: "operator DAG; $\pi$—"
12. Line 438–448: Several in PCTR phases
13. Line 568: (none)
14. Line 770: "and 5.7% below for W3—all within the 6% envelope"
15. Line 789: "is additive—edge and cloud compute"
16. Line 857: "system-level concern—the PCTR protocol"
17. Line 885: "footprint—a 95.3% reduction"

**Assessment:** 28 is at the upper end of acceptable (human baseline: 5–15 for a paper this length, ~30 pages). Could reduce to ~15 for safety.

### AI Vocabulary Words
| Word | Count | Lines |
|------|-------|-------|
| paradigm | 4 | 67, 95, 101, 113 |
| landscape | 2 | 95, 115 |
| leverage | 1 | 77 |
| compelling | 2 | 107, 117 |
| robust | 1 | 758 (Finding 3: "robust to network condition degradation") |
| seamless | 0 | — |
| delve | 0 | — |
| tapestry | 0 | — |
| cutting-edge | 0 | — |
| harness | 0 | — |
| cornerstone | 0 | — |
| pivotal | 0 | — |
| myriad | 0 | — |
| plethora | 0 | — |
| intricate | 0 | — |
| nuanced | 0 | — |
| underscore | 0 | — |
| utilize | 0 | — |

**Total AI vocabulary instances: 10**

**Assessment:** Much improved from v1. "Paradigm" is the most concerning at 4 uses — consider replacing with "model", "approach", or "architecture" in 2–3 instances. "Compelling" in line 117 ("compelling latency advantages") is promotional; replace with "significant" or "measurable". "Leverage" in line 77 is borderline but common in technical writing.

### Sentences Starting with "It is" / "There is/are" / "This is"
| Pattern | Count | Notable Instance |
|---------|-------|-----------------|
| "It is" | 0 | — |
| "There is/are" | 0 | — |
| "This is" | 1 | Line 837: "This is because the AODE's scoring model..." |

**Total: 1** — Excellent. Well below AI baseline.

### Rule of Three Patterns (X, Y, and Z)
Notable instances:
1. Line 44: "resource utilization, SLO urgency, and inter-tier transfer costs"
2. Line 67: "exceptional scalability, fault tolerance, and expressiveness"
3. Line 69: "available memory, processing capacity, and storage"
4. Line 73: "computational profiles, accumulated state size, or latency sensitivity"
5. Line 77: "processing latency, resource consumption, and data transfer cost"
6. Line 86: "resource utilization, network RTT, operator complexity, and SLO constraints" (rule of four)
7. Line 90: "sustained SLO compliance..., and peak throughput..." (rule of three in results)
8. Line 95: "centralized stream processing frameworks, edge and fog computing paradigms, hybrid edge-cloud architectures, and workload offloading strategies" (rule of four)
9. Line 101: same as above
10. Line 113: "latency reduction, bandwidth conservation, and location awareness"
11. Line 113: "hardware heterogeneity, intermittent connectivity, security exposure, and the absence..." (rule of four)
12. Line 117: "compute, memory, and storage capacities"
13. Line 131: "minimizing task completion latency, reducing device energy consumption, and maximizing resource utilization"
14. Line 233: "sustained CPU saturation, concurrent memory contention, and unpredictable throughput spiking"

**Count: ~14 clear rule-of-three/four patterns**

**Assessment:** Moderate. Some are natural enumerations (listing metrics, workloads). The Introduction paragraphs (lines 65–77) have a high density — 5 rule-of-three patterns in ~200 words is noticeable. Reduce 3–4 of these to pairs or rephrase.

### Negative Parallelisms ("not X, but Y")
1. Line 65: "latency is not a quality-of-service consideration but an operational constraint"
2. Line 117: "not for edge-only or cloud-only processing, but for a principled, adaptive distribution"
3. Line 368: "not merely those that avoid outright overflow"

**Count: 3**

**Assessment:** Acceptable. These are legitimate rhetorical constructions in academic writing.

### Sentences > 80 Words
**Count: 48 lines** with paragraphs exceeding 80 words (see W28 table above for the worst offenders).

Of these, the most egregious:
- Line 107: 340 words in one paragraph
- Line 44 (abstract): 242 words in one paragraph  
- Line 123: 241 words
- Line 69: 208 words
- Line 77: 183 words
- Line 167: 172 words
- Line 135: 178 words

**Assessment:** This is the paper's most serious remaining AI signal. Human-written systems papers typically have paragraphs of 3–5 sentences (40–80 words each). Having 7+ paragraphs exceeding 150 words strongly suggests LLM generation. Even if the technical content is sound, the presentation style will trigger suspicion.

### Promotional/Inflated Adjectives
1. Line 67: "exceptional scalability" → "high scalability" or "scalability"
2. Line 107: "compelling lightweight processing option" → "lightweight processing option"
3. Line 117: "compelling latency advantages" → "significant latency advantages" or just "latency advantages"
4. Line 113: "foundational work" — borderline acceptable for Bonomi 2012, which genuinely is foundational
5. Line 885: "substantially expanding" → "expanding"

**Count: 5 mild instances**

### Overall AI Pattern Score
| Pattern | Count | Human Baseline | Status |
|---------|-------|---------------|--------|
| Em dashes | 28 | 5–15 | ⚠️ High |
| AI vocabulary | 10 | 2–5 | ⚠️ Slightly high |
| "It is"/"There is" starters | 1 | 3–8 | ✅ Good |
| Rule of three | 14 | 5–8 | ⚠️ High |
| Negative parallelisms | 3 | 1–3 | ✅ Acceptable |
| Paragraphs > 150 words | 10+ | 0–2 | ❌ Very high |
| Promotional adjectives | 5 | 2–4 | ✅ Acceptable |

**Overall assessment:** The paper has improved dramatically from v1 (no more "comprehensive" × 6, "fundamentally" × 5, 108 em dashes). The remaining signals are: (1) monster paragraphs, (2) em dashes at 28, and (3) rule-of-three density in the Introduction. A reviewer with AI awareness would flag this as "possibly AI-assisted but clearly technically competent," which is unlikely to cause rejection on its own but adds a negative impression.

---

## Part E: Prioritized Fix List

### 🔴 CRITICAL (will cause rejection or desk reject)

**C1. Highlights exceed Elsevier's 85-character limit.**  
All 5 highlights are 175–244 characters. FGCS enforces this limit. Rewrite each to ≤85 characters. Example:
- "HybridStream achieves 99.2–99.8% SLO compliance across three workloads" (71 chars)
- "AODE recalibrates operator placement in 18–36 ms with <2% CPU overhead" (71 chars)
- "PCTR migrates stateful operators with 62–1,410 ms bounded pause time" (69 chars)
- "Edge runtime uses 55 MB vs Flink's 1,187 MB (95.3% reduction)" (63 chars)
- "Adaptive placement sustains throughput within 5.7% of static baselines" (71 chars)

**C2. Duplicate CRediT and Funding sections (lines 919–925 duplicated at 928–934).**  
Remove the second copy. An editor will immediately notice.

**C3. Duplicate .bib entries causing duplicate reference numbers.**  
9 bib keys are duplicated (zeuch2020nebulastream, cardellini2016optimal, cardellini2018decentralized, heinze2014elastic, kalavri2018three, floratou2017dhalion, pietzuch2006network/pietzuch2006sbon, xu2014tstorm, peng2015rstorm/peng2015r, akhter2019stateful, dematteis2017elastic). The Pietzuch and Peng papers are cited with different keys in different sections, producing two reference numbers for the same paper. Consolidate all duplicate keys and ensure each paper has exactly one bib entry.

**C4. Orphaned .bib entries.**  
`niknam2020federated` and `sajjad2016spanedge` are in the .bib but never cited. Either cite them or remove them. LaTeX will list them in the bibliography regardless (depending on `\nocite` behavior), creating phantom references.

### 🟡 MAJOR (reviewer will flag, needs response letter)

**M1. Only 1 figure for a 30+ page systems paper.**  
Add at minimum: (a) a time-series showing AODE behavior during a load spike, (b) a latency CDF/box plot comparing the three systems, (c) a PCTR migration timeline. Three figures total (plus the existing architecture diagram) would be appropriate.

**M2. Monster paragraphs (>150 words) throughout.**  
Line 107 (340 words), line 123 (241 words), line 44/abstract (242 words), line 69 (208 words), line 77 (183 words), line 135 (178 words), line 167 (172 words). Break each into 2–4 shorter paragraphs. This is the single most impactful readability improvement available.

**M3. Line 105 grammatical derailment.**  
The sentence beginning "Apache Storm, introduced at Twitter by Toshniwal et al.~\cite{toshniwal2014storm}; resource-aware scheduling extensions such as T-Storm~\cite{xu2014tstorm} and R-Storm~\cite{peng2015rstorm} subsequently demonstrated that topology-aware placement improves throughput by 30--80\% over default schedulers, demonstrated that continuous, real-time computation..." — this sentence has two "demonstrated" verbs, a semicolon splice, and a parenthetical that derails the main clause. Rewrite as 2–3 separate sentences.

**M4. No sensitivity analysis shown for AODE weight vector, α, or Δ_h.**  
The paper *states* these parameters were calibrated but shows no data. Add at least one table or figure showing SLO compliance across 3 values of Δ_h (e.g., 0.05, 0.15, 0.25) for one workload.

**M5. PCTR vs. Flink-native migration not explicitly contrasted.**  
Add 2–3 sentences in Section 4.3 explaining how PCTR differs from Flink's savepoint-based migration and why the cross-tier, cross-runtime case requires a different protocol.

**M6. κ=2.0 contention coefficient lacks empirical justification.**  
Show the profiling data or at minimum state the profiling methodology (how many runs, what metric was optimized).

**M7. W3 data source clarification.**  
Clarify whether the NYSE/NASDAQ trace is actual CTA data (paid), a derived/filtered trace, or synthetic data modeled on market characteristics. If the trace is in the GitHub repo, state this.

**M8. Line 95: Malformed citation.**  
`paradigm~\cite{yousefpour2019all}s` → `paradigms~\cite{yousefpour2019all}`

**M9. B2 static baseline optimality.**  
Clarify whether B2's static partition was chosen to maximize B2's performance (giving the baseline its best shot) or whether it was a reasonable but not optimized partition. If the former, state it. If the latter, a reviewer will argue the comparison is unfair.

### 🟢 MINOR (nice to fix)

**m1.** Reduce em dashes from 28 to ~15. Replace the most mechanical ones (line 65, 109, 131, 770, 789) with commas or periods.

**m2.** Replace "paradigm" in 2 of its 4 uses with "model" or "approach."

**m3.** Replace "compelling" (lines 107, 117) with "significant" or remove entirely.

**m4.** Line 95: Fix periods used as colons in the road-map paragraph.

**m5.** Specify the exact Apache Flink version used (e.g., 1.18.1).

**m6.** Add the SpanEdge citation (sajjad2016spanedge is in .bib but uncited — it's directly relevant to multi-span stream processing).

**m7.** Consider adding a brief energy consumption discussion (1 paragraph in Discussion) given FGCS's green computing interest.

**m8.** Line 885: "up to 72 idle HEA instances" — add qualifier that this is idle; under load the number will be substantially lower. (The word "idle" is present but easy to miss.)

**m9.** Abstract: Consider tightening from 242 to ~180 words for readability.

**m10.** Add a "Notation" table or paragraph early in Section 3 summarizing all mathematical symbols (E, C, O, D, π, τ, β, λ, c_i, s_i, etc.) for reader reference.

---

## Delta from v1 Review

| v1 Issue | Status in v2 |
|----------|-------------|
| 🔴 Missing CRediT statement | ✅ Fixed (but duplicated) |
| 🔴 "authors" plural for single author | ✅ Fixed — now "The author declares/thanks" |
| 🔴 Missing SOTA comparisons in Related Work | ✅ Fixed — Cardellini, NebulaStream, Heinze, Kalavri, Dhalion, etc. added |
| 🔴 Increase references to 50+ | ✅ Fixed — 58 unique cited keys |
| 🔴 Reduce AI writing patterns (108 em dashes, 6× comprehensive, 5× fundamentally) | ⚠️ Partially fixed — em dashes down to 28, comprehensive/fundamentally eliminated, but monster paragraphs remain |
| 🔴 Add Funding statement | ✅ Fixed (but duplicated) |
| 🔴 Verify W3 data availability | ⚠️ Not addressed |
| 🟡 Add sensitivity analysis | ⚠️ Not addressed |
| 🟡 Add time-series figure | ⚠️ Not addressed |
| 🟡 Tighten abstract | ⚠️ Not addressed |

**Bottom line:** The paper has made substantial progress. The structural completeness issues from v1 are mostly resolved (CRediT, funding, references, related work). The remaining issues are: (1) highlights character limit (desk reject risk), (2) duplicate sections, (3) duplicate .bib entries, (4) no figures beyond architecture, (5) monster paragraphs, and (6) missing sensitivity analyses. Items 1–3 are trivial 15-minute fixes. Items 4–6 require more work but are achievable within a minor revision cycle.

The paper's technical contribution is solid and above the FGCS acceptance bar. Fix the critical items and this paper should be accepted.
