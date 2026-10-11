# Change-control brief for clinical_ops: release 1.4.0

**In one sentence:** a new version of the triage wording will answer messages from 6 of Kenya's 47 counties (about 10%). Everyone else keeps today's wording, and we can switch the trial off in minutes.

| | |
|---|---|
| **What changed** | Triage wording `1.2.0` → `1.3.0-candidate`, on **10% of counties**: Bomet, Kirinyaga, Migori, Narok, Siaya and Taita Taveta. A county always gets the same wording. |
| **Why** | Patients writing in Swahili sometimes got English replies. The new wording answers in the patient's language. It also says more firmly never to name a medicine and never to tell a patient what disease they have, even when they ask. |
| **What stays the same** | The three urgency levels and what they mean. Danger words (chest pain, bleeding, seizure and others) are always treated as urgent. The service still gives one short next step, never a diagnosis. |
| **What was tested** | 30 test messages with agreed answers (`evals/golden.jsonl`): emergencies, see-a-clinician cases, self-care cases, a patient asking for a dose, a patient trying to make the system "say" a diagnosis, and two messages in Swahili. |
| **Results** | The new wording matched the agreed answer on **28 of 30** (today's wording: 27 of 30). It made **no** safety mistakes, and it answered both Swahili messages in Swahili. The two misses are cautious ones: it sent a patient to care *sooner* than our label (a 3-week cough with night sweats, and a vomiting child). |
| **What we caught before it reached anyone** | An earlier draft, written to sound friendlier, **suggested paracetamol with a dose** to a patient who asked. Our automatic check blocked it even though its overall score passed. It never reached a patient. |
| **How we will watch it** | Each answer records which wording was used. After 7 days we compare the two groups. In particular, the new wording must not move patients toward "self-care" (no more than 5 points). clinical_ops reads 20 real answers from the trial counties before any wider rollout. |
| **Rollback** | Switch the trial off: set `PROMPT_B_PCT=0` (same software, no rebuild, minutes). If ever needed, the whole release can return to the previous version `1.3.1` (git tag `v1.3.1`). |
| **Who approved** | CODEOWNERS for `prompts/` and `config/` (clinical_ops and ml-eng) on PR #3. This is a solo teaching repo, so the owner reviewed in both roles; in the team, these are two people. |
| **Go or no-go** | **Go** if all three hold: the automatic test-message check is green (score at least 0.85 and **zero** safety mistakes); the stock-checking tool the logistics assistant uses (`check_stock`) answers our health check; and the tool error rate stays under 10%. Otherwise **no-go**: the trial stays off. |

The decision stays with people. The system suggests how urgent a message is and one safe next step. A clinician or coordinator decides what happens.
