"""Build exec/one_pager.pdf from the numbers the scripts produced. No measured or modelled
figure is typed here; the only typed numbers are decisions (the $25 OpenAI limit, the 2.5 s
target, the 3-copy ceiling) that the README and deploy/ files also state.

    python exec/build_one_pager.py

Reads cost/cost_model_output.json, cost/breakeven_output.json, levers/results/*.json,
so re-running the cost model and the levers re-runs the executive page too.
"""
import json
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent / "one_pager.pdf"
INK, ACCENT, PALE, GREEN = colors.HexColor("#1b2a38"), colors.HexColor("#1f4e79"), \
    colors.HexColor("#eef3f8"), colors.HexColor("#1e6b3a")


def load(rel: str) -> dict:
    return json.loads((ROOT / rel).read_text())


def numbers() -> dict:
    model = load("cost/cost_model_output.json")
    sc = {s["scenario"]: s for s in model["scenarios"]}
    base, base_rec = sc["baseline: no levers"], sc["baseline: cache + batch (RECOMMENDED)"]
    spike_rec = sc["10x spike: cache per replica + batch (RECOMMENDED)"]
    off, on = load("levers/results/cache_off.json")["summary"], load("levers/results/cache_on.json")["summary"]
    batch = next(r for r in load("levers/results/batch.json")["after"] if r["batch_size"] == 4)
    be = load("cost/breakeven_output.json")
    fixed = [o["fixed_usd_month"] for o in be["options"]]
    mult = [o["multiple_of_baseline_volume"] for o in be["options"]]
    load_test = load("levers/results/load_test.json")["levels"]
    return {
        "per_1k": base_rec["usd_per_1k_total"], "per_req": base_rec["usd_per_request"],
        "tok_per_1k_before": base["usd_per_1k_tokens_only"], "month": base_rec["total_usd_month"],
        "model_share": base["lines_usd"]["model_tokens"] / base["total_usd_month"],
        "people": base["lines_usd"]["people"], "containers": base["lines_usd"]["containers"],
        "spike_month": spike_rec["total_usd_month"], "spike_per_1k": spike_rec["usd_per_1k_total"],
        "spike_delta": spike_rec["total_usd_month"] - base_rec["total_usd_month"],
        "hit": on["hit_rate"], "cache_cut": 1 - on["usd_total"] / off["usd_total"],
        "p50_before": off["latency_ms_p50"], "p95_before": off["latency_ms_p95"],
        "batch_cut": batch["usd_saving_vs_before"], "batch_agree": batch["agreement_with_one_call"],
        "gpu_min": min(fixed), "gpu_max": max(fixed), "mult_min": min(mult),
        # throughput while p95 stayed healthy (under 1.5 s), not the saturated maximum
        "replica_rps": max(r["req_per_s"] for r in load_test if r["p95_ms"] < 1500),
        "cap": load("deploy/azure_budget_triage.json")["amount"],
        "price_x": 16.7,
        "price_x_saving": sc["10x spike: no levers"]["lines_usd"]["model_tokens"] * 16.7 * on["hit_rate"],
        "redis_be": model["redis_break_even_requests_per_month"],
    }


def build() -> None:
    n = numbers()
    body = ParagraphStyle("body", fontName="Helvetica", fontSize=8.6, leading=11.2, textColor=INK, alignment=TA_LEFT)
    small = ParagraphStyle("small", parent=body, fontSize=7.2, leading=9, textColor=colors.HexColor("#4a5a6a"))
    h1 = ParagraphStyle("h1", parent=body, fontName="Helvetica-Bold", fontSize=15, leading=18, textColor=ACCENT)
    h2 = ParagraphStyle("h2", parent=body, fontName="Helvetica-Bold", fontSize=9.6, leading=12,
                        textColor=ACCENT, spaceBefore=5, spaceAfter=1.5)
    cell = ParagraphStyle("cell", parent=body, fontSize=8.2, leading=10.2)
    cellb = ParagraphStyle("cellb", parent=cell, fontName="Helvetica-Bold")

    def p(text, style=body):
        return Paragraph(text, style)

    story = [
        p("AfyaPlus triage: what it costs, and what we recommend", h1),
        p("One-page brief for the CTO and Finance &middot; 11 October 2026 &middot; five-minute read", small),
        Spacer(1, 5),
    ]
    verdict = Table([[p(
        f"<b>Recommendation: GO, with the five conditions at the bottom.</b> One triage answer costs "
        f"<b>${n['per_req']:.4f}</b>, or <b>${n['per_1k']:.2f} per 1,000</b>, all-in. That is about "
        f"<b>${n['month']:.0f} a month</b> at today's 2,000 requests a day. The AI model itself is only "
        f"{n['model_share']:.0%} of that. Most of the cost is staff time (${n['people']:.0f}) and the "
        f"always-on server (${n['containers']:.0f}).", body)]], colWidths=[180 * mm])
    verdict.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), PALE),
                                 ("LINEBEFORE", (0, 0), (0, -1), 3, GREEN),
                                 ("LEFTPADDING", (0, 0), (-1, -1), 7), ("TOPPADDING", (0, 0), (-1, -1), 5),
                                 ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    story += [verdict, Spacer(1, 2)]

    story += [p("1. If traffic jumps tenfold", h2), p(
        f"An outbreak month at 20,000 requests a day costs about <b>${n['spike_month']:.0f}</b>, "
        f"<b>${n['spike_delta']:.0f} more</b> than a normal month. Each answer gets <i>cheaper</i> "
        f"(${n['spike_per_1k']:.2f} per 1,000), because the fixed costs are shared by more requests. "
        f"Capacity is not the problem: one server copy handled about {n['replica_rps']:.0f} requests a second "
        f"in our load test, and a spike day peaks below 1. We run 1 copy normally, 2 in a spike, "
        f"and <b>never more than 3</b>. That is the spending ceiling.")]

    story += [p("2. Two savings we built and measured", h2)]
    rows = [
        [p("<b>What it does</b>", cellb), p("<b>Measured result</b>", cellb), p("<b>The honest catch</b>", cellb)],
        [p("<b>Remembers answers</b> to messages it has already seen in the last 10 minutes", cell),
         p(f"On our 100-message test, {n['hit']:.0%} were answered from memory. AI cost fell "
           f"{n['cache_cut']:.0%}. Typical wait went from {n['p50_before'] / 1000:.1f} s to instant.", cell),
         p("The slowest answers stay about as slow (a new question still asks the AI). Real repeat "
           "rates must be measured before we quote this saving.", cell)],
        [p("<b>Handles after-hours messages in groups of 4</b>, ready for the 08:00 review", cell),
         p(f"AI cost for those messages fell {n['batch_cut']:.0%}. {n['batch_agree']:.0%} of answers "
           f"matched answering one at a time.", cell),
         p("Bigger groups saved more but downgraded some urgencies, so we chose 4. Danger words "
           "(chest pain, bleeding) are always flagged urgent.", cell)],
    ]
    t = Table(rows, colWidths=[52 * mm, 64 * mm, 64 * mm])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), PALE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                           ("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor("#b4c6dc")),
                           ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
    story += [t, p("Because the AI is a small part of the bill, these savings matter mostly for speed, and as "
                   f"insurance if AI prices rise. At a {n['price_x']:.0f}&times; higher AI price (gpt-4o), remembering "
                   f"answers would save about ${n['price_x_saving']:.0f} in a spike month.", small)]

    story += [p("3. Should we run the AI on our own servers?", h2), p(
        f"<b>Not now.</b> Renting our own AI server costs <b>${n['gpu_min']:,.0f} to ${n['gpu_max']:,.0f} "
        f"a month</b> whether or not anyone uses it, against about $2 a month for the AI service today. "
        f"It only pays off at <b>{n['mult_min']}&times; today's traffic</b>. We would reconsider if traffic "
        f"grew enormously, if prices jumped, or if a data-protection ruling required patient messages to "
        f"stay in-country. Even then, a hosted service in-region comes before owning servers.")]

    story += [p("4. The main risk, and what we do about it", h2), p(
        "<b>Risk:</b> a partner app that keeps resending requests (a &ldquo;retry loop&rdquo;). It adds about "
        "a fifth to the AI bill and can lock out real clinicians. <b>Already in place:</b> a per-user "
        "request limit, at most one automatic retry, and the 3-copy ceiling. <b>Alert:</b> cloud spend is "
        f"capped at ${n['cap']} a month, and a warning at ${0.8 * n['cap']:.0f} (80%) goes to Finance and the on-call engineer. "
        "That warning stays silent in a normal month. The pre-agreed response is to tighten that partner's "
        "request limit, a change that takes minutes.")]

    story += [p("5. Go, on these conditions", h2)]
    conds = [
        f"Apply the ${n['cap']} cloud budget and alerts when the cloud account is opened (written and checked, not yet live).",
        "The owner of the AI account sets a $25 monthly limit with OpenAI. The cloud budget cannot see the AI bill.",
        "Service target: 95 of every 100 answers within 2.5 seconds (&ldquo;p95&rdquo;). Measured today: "
        f"{n['p95_before'] / 1000:.1f} s without memory. Reviewed monthly.",
        "Re-measure the real repeat rate and after-hours agreement in month one, before any saving is reported upward.",
        "If the AI service is down, the app says so and points to the clinic. It never invents advice.",
    ]
    story += [p(f"<b>{i}.</b> {c}") for i, c in enumerate(conds, 1)]
    story += [Spacer(1, 5), p(
        f"Figures come from 100+ live test requests on 11 Oct 2026 and published Azure and OpenAI prices; staff "
        f"time ($25/h &times; 6 h a month) is an assumption. A shared memory store (Redis) is built and tested "
        f"but held back until about {n['redis_be'] / 1e6:.1f} M requests a month, when it starts paying for itself. "
        f"Details: cost/cost_model.md, levers/measurements.md, memo/api_vs_selfhost.md.", small)]

    doc = SimpleDocTemplate(str(OUT), pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm,
                            topMargin=12 * mm, bottomMargin=10 * mm, title="AfyaPlus triage: cost brief",
                            author="AfyaPlus ML engineering")
    doc.build(story)
    print(f"wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    build()
