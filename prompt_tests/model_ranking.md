# Model Comparison: Investigation Guide Quality Ranking

**Test Rule:** HackTool - Bloodhound/Sharphound Execution (f376c8a7-a2d0-4ddc-aa0c-16c17236d962)
**Prompt:** default_prompt_sample_test.txt
**Evaluation Perspective:** SOC Analyst / Incident Responder performing triage

---

## Scoring Criteria

| Criteria | Weight | Description |
|---|---|---|
| **Technical Accuracy** | High | Correct ATT&CK mappings, Event IDs, tool behavior, telemetry sources |
| **Specificity** | High | References exact Event IDs, fields, ports, file paths — not generic |
| **Actionability** | High | A Tier 1 analyst can follow the steps without guessing what to do |
| **Benign vs Malicious** | Medium | Clearly distinguishes legitimate use from attacker behavior |
| **Conciseness** | Medium | Readable in 2-3 minutes, scannable during active triage |
| **Blind Spots Quality** | Medium | Identifies real evasion techniques and useful companion detections |
| **Format Compliance** | Low | Follows the required output structure |

---

## Final Ranking

### 1. Claude Opus 4.6 — Score: 9.3/10

**Strengths:**
- Best balance of thoroughness and conciseness across all models
- Mentions Cobalt Strike `execute-assembly` as a specific evasion technique
- Unique and correct suggestion to monitor `clrjit.dll` loads (Sysmon Event ID 7) for in-memory .NET execution — this is expert-level detection engineering advice
- Clean benign/malicious distinction in every investigation step
- References specific Event IDs (4688, Sysmon 1, Sysmon 11, Sysmon 17/18), ports (389/636, 445), and file patterns
- Strong companion detection: LDAP query volume anomaly + named pipe monitoring

**Weaknesses:**
- None significant

**Verdict:** Production-ready. Reads like it was written by a senior detection engineer.

---

### 2. GPT-5.2 — Score: 9.0/10

**Strengths:**
- Very precise investigation steps with exact fields (SubjectUserName, ParentImage, ParentCommandLine)
- Good specificity: references Sysmon Event ID 11 for file staging, Security Event ID 4662 for directory service access
- Clean distinction between legitimate security assessment context and malicious indicators
- Concise — fits the 2-3 minute target well
- Correctly states what the detection does NOT confirm

**Weaknesses:**
- Blind spots section slightly less detailed than Opus 4.6 (doesn't mention in-memory execution frameworks by name)
- Companion detections are good but less specific

**Verdict:** Production-ready. Strong all-around with excellent readability.

---

### 3. Claude Opus 4.5 — Score: 8.8/10

**Strengths:**
- Excellent companion detection suggestions: Kerberoastable SPNs (T1558.003), AMSI bypass, ZIP creation alerts
- Mentions Event ID 1644 for LDAP search filter monitoring — very specific and useful
- References Event ID 5145 for SMB session enumeration
- Strong "what this does NOT confirm" statement
- Good structure and flow

**Weaknesses:**
- Slightly more verbose than the top two
- Investigation steps, while thorough, could be slightly more scannable

**Verdict:** Production-ready. Best companion detection suggestions of any model.

---

### 4. GPT-5.2 (Thinking Mode) — Score: 8.3/10

**Strengths:**
- Most thorough analysis of all models — covers every angle
- Excellent nuance: suggests escalating to Critical severity for tier-0 assets
- Best coverage of network correlation (LDAP, SMB, RPC, WinRM, ADWS port 9389)
- Detailed file staging validation with specific paths
- Strong exfiltration correlation step

**Weaknesses:**
- **Too verbose.** Exceeds the 2-3 minute reading target significantly
- Each investigation step is a paragraph rather than a scannable bullet
- During active triage, an analyst would struggle to quickly find the key action
- Diminishing returns — the extra detail doesn't proportionally increase actionability

**Verdict:** Excellent reference material, but needs editing for SOC triage use. Better suited as a wiki/runbook than an in-alert guide.

---

### 5. Gemini 3 Pro — Score: 7.8/10

**Strengths:**
- Unique and valuable suggestion: monitor LDAP Search Filter anomalies (Event ID 1644)
- Unique and valuable suggestion: Honeytoken account access detection
- Mentions SAMR enumeration and specific AD attack paths (GPO Local Admin, Unconstrained Delegation)
- Good specificity in investigation steps
- Mentions Cobalt Strike `execute-assembly`

**Weaknesses:**
- Includes trailing "Would you like me to generate a hunting query..." which breaks the output format
- Some investigation steps could be more concise
- Missing horizontal rules between some sections

**Verdict:** Good quality with unique insights not found in other models. Format issues need fixing.

---

### 6. Gemini 3 Thinking — Score: 7.3/10

**Strengths:**
- Good framing: calls BloodHound a "pre-exploitation" tool
- Mentions SAMR enumeration (specific technical detail)
- Practical suggestion about Honeytoken accounts
- Decent investigation steps with Event IDs

**Weaknesses:**
- Trailing "Would you like me to generate..." breaks format
- Less thorough investigation steps compared to top performers
- Missing some key indicators (no mention of specific staging paths or file naming patterns in investigation steps)
- Blind spots section is brief

**Verdict:** Adequate but not standout. Needs more depth in investigation steps.

---

### 7. Gemini 3 Fast — Score: 7.0/10

**Strengths:**
- Most concise of all models — easy to scan
- Good operational advice: compare execution time against change management calendar
- Specific file naming pattern example (20260213214619_BloodHound.zip)
- Mentions Event ID 4662 as companion detection

**Weaknesses:**
- Trailing "Would you like me to generate..." breaks format
- Less specific investigation steps than top performers
- Blind spots section is thin
- Missing some key telemetry references

**Verdict:** Acceptable for a fast/cheap model. Conciseness is a strength but depth suffers.

---

### 8. Claude Haiku 4.5 — Score: 5.5/10

**Strengths:**
- Investigation step content is actually very detailed and technically accurate
- Mentions specific audit policy GUID for process creation logging
- References Sysmon Event ID 7 for DLL loading, .NET reflection, PowerShell EncodedCommand
- Good companion detection suggestions (scheduled task creation, ZIP exfiltration correlation)

**Weaknesses:**
- **Exposes internal thinking/analysis** at the top of the output — this should NOT be in the final guide
- **Uses `##` headers instead of `###`** — format non-compliance
- **Extremely verbose** — each investigation step is a wall of text (150+ words per bullet)
- Not scannable during active triage — an analyst would drown in text
- Would fail the validator as-is due to header format

**Verdict:** Good knowledge, terrible packaging. The content is strong but the output format is unusable for SOC triage without heavy editing.

---

### 9. GPT-4o-mini — Score: 3.5/10

**Strengths:**
- Follows the basic structure
- Has a disclaimer

**Weaknesses:**
- **Incorrect ATT&CK technique names**: Lists T1069.001 as "Credential Dumping" (it's Permission Groups Discovery: Local Groups) and T1069.002 as "Domain Trusts" (it's Permission Groups Discovery: Domain Groups)
- **No Event IDs in investigation steps** — says "Review Process Creation Logs" but never specifies which logs
- **Completely generic** guidance: "Check for Related Network Activity" with no ports, protocols, or specific indicators
- "Correlate with User and System Behavior" is meaningless operational guidance
- No benign vs malicious distinction
- No companion detections suggested
- Telemetry sources described as "System logs that can highlight unusual access" — useless

**Verdict:** Not suitable for SOC use. Generic to the point of being unhelpful. An analyst would gain almost nothing from this guide beyond what the rule title already tells them.

---

## Summary Table

| Rank | Model | Score | Est. Cost (4K rules) | Best For |
|---|---|---|---|---|
| 1 | **Claude Opus 4.6** | 9.3 | ~$145 (batch: ~$73) | Best overall quality |
| 2 | **GPT-5.2** | 9.0 | ~$74 | Best value at high quality |
| 3 | **Claude Opus 4.5** | 8.8 | ~$145 (batch: ~$73) | Best companion detections |
| 4 | **GPT-5.2 Thinking** | 8.3 | ~$74+ | Reference/runbook material |
| 5 | **Gemini 3 Pro** | 7.8 | ~$53 (batch: ~$26) | Unique insights, good value |
| 6 | **Gemini 3 Thinking** | 7.3 | ~$53+ | Decent mid-tier option |
| 7 | **Gemini 3 Fast** | 7.0 | ~$3.70 | Budget option with acceptable quality |
| 8 | **Claude Haiku 4.5** | 5.5 | ~$29 (batch: ~$15) | Needs format fixes to be usable |
| 9 | **GPT-4o-mini** | 3.5 | ~$4 | Not recommended |

---

## Recommendations

**Best quality regardless of cost:** Claude Opus 4.6 or GPT-5.2 — both produce production-ready investigation guides.

**Best value:** GPT-5.2 at ~$74 gives you near-top-tier quality. Gemini 3 Pro batch (~$26) is the best budget-to-quality ratio.

**Current default (gpt-4o-mini) should be changed.** The output is not actionable for SOC analysts and contains factual errors in ATT&CK mappings.

**Consider for daily incremental runs:** A cheaper model (gpt-5-mini or Gemini 3 Fast) may suffice for the 5-20 new rules per day, with periodic full re-runs on a better model.
