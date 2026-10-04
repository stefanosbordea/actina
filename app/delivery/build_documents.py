"""Rebuild the three competition PDFs from retained, executed evidence."""
from pathlib import Path
import json
from xml.sax.saxutils import escape

from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import A4, landscape

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "delivery"
M = json.loads((ROOT / "results/metrics.json").read_text())
R = json.loads((ROOT / "results/independent-review.json").read_text())
CHECKS = json.loads((ROOT / "results/model-checks.json").read_text())
FONT = Path("/System/Library/Fonts/Supplemental")
pdfmetrics.registerFont(TTFont("Aqua", str(FONT / "Arial.ttf")))
pdfmetrics.registerFont(TTFont("AquaBold", str(FONT / "Arial Bold.ttf")))
pdfmetrics.registerFontFamily("Aqua", normal="Aqua", bold="AquaBold", italic="Aqua", boldItalic="AquaBold")
NAVY = colors.HexColor("#153643")
TEAL = colors.HexColor("#087F8C")
PALE = colors.HexColor("#EDF5F3")
GREY = colors.HexColor("#526B75")
styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name="AquaTitle", fontName="AquaBold", fontSize=25, leading=30, textColor=NAVY, spaceAfter=17))
styles.add(ParagraphStyle(name="AquaSub", fontName="AquaBold", fontSize=14, leading=18, textColor=TEAL, spaceBefore=14, spaceAfter=8))
styles.add(ParagraphStyle(name="AquaBody", fontName="Aqua", fontSize=10.5, leading=15.5, textColor=NAVY, spaceAfter=9))
styles.add(ParagraphStyle(name="AquaSmall", fontName="Aqua", fontSize=8.5, leading=12, textColor=GREY, spaceAfter=7))
styles.add(ParagraphStyle(name="AquaCell", fontName="Aqua", fontSize=9.5, leading=13, textColor=NAVY))
styles.add(ParagraphStyle(name="AquaCanvas", fontName="Aqua", fontSize=9, leading=12.5, textColor=NAVY))

def p(text, style="AquaBody"):
    return Paragraph(text, styles[style])

def section(title, text):
    return [p(title, "AquaSub"), p(text)]

def table(rows, widths=None):
    cells = [[p(escape(str(cell)), "AquaCell") for cell in row] for row in rows]
    t = Table(cells, colWidths=widths, hAlign="LEFT", repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PALE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, 0), 1, TEAL),
        ("LINEBELOW", (0, 1), (-1, -1), 0.3, colors.HexColor("#DCE7E6")),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
    ]))
    return t

def chrome(c, doc):
    w, h = doc.pagesize
    c.setFillColor(TEAL)
    c.rect(42, h - 38, w - 84, 3, fill=1, stroke=0)
    c.setFont("AquaBold", 9)
    c.setFillColor(NAVY)
    c.drawString(42, h - 28, "AQUASHIFT")
    c.setFont("Aqua", 8)
    c.drawRightString(w - 42, h - 28, "Pafos 2.0 | University category | 2 October 2026")
    c.setStrokeColor(colors.HexColor("#DCE7E6"))
    c.line(42, 35, w - 42, 35)
    c.setFillColor(GREY)
    c.drawString(42, 22, "Working prototype | Historical evidence and declared scenarios")
    c.drawRightString(w - 42, 22, str(doc.page))

def build(name, story, pagesize=A4):
    doc = SimpleDocTemplate(str(OUT / name), pagesize=pagesize, leftMargin=42, rightMargin=42,
                            topMargin=60, bottomMargin=49, title=name.replace("-", " "),
                            author="Loucas Louka; AquaShift team", allowSplitting=0)
    doc.build(story, onFirstPage=chrome, onLaterPages=chrome)

def title(kicker, name):
    return [p(kicker.upper(), "AquaSmall"), p(name, "AquaTitle")]

def page(story, kicker, name):
    if story:
        story.append(PageBreak())
    story.extend(title(kicker, name))

def figure(name, width=490, height=235):
    return Image(str(ROOT / "results/charts" / name), width=width, height=height, kind="proportional", hAlign="LEFT")

mae_model = M["all"]["model"]["mae"]
mae_base = M["all"]["persistence"]["mae"]
rmse_model = M["all"]["model"]["rmse"]
rmse_base = M["all"]["persistence"]["rmse"]
day_model = M["daylight"]["model"]["mae"]
day_base = M["daylight"]["persistence"]["mae"]
totals = CHECKS["scheduler"]["totals"]

executive = []
page(executive, "Executive summary - 1 of 2", "Water, timed with the sun")
executive.append(p("AquaShift combines water storage scheduling with a smaller, practical sites product for irrigation budgeting and leak alerts. The proposed first market is Paphos: hotels, managed gardens and water operators that can shift some water work in time without reducing service."))
executive += section("The product", "<b>AquaShift Grid</b> recommends when an illustrative desalination or pumping unit should run, respecting modeled production capacity, water demand and tank limits. <b>AquaShift Sites</b> illustrates how a garden can compare weather-related water need with a fixed timer and review unusual overnight meter flow. Both are operator advice tools; the prototype sends no control commands.")
executive += section("What is working today", "The delivered dashboard runs locally with retained data and four views: Grid overview, Forecast evidence, Sites lab, and Assumptions &amp; handoff. It covers 92 complete held-out days in July-September 2026. A date selector, tank slider, schedule and storage charts, prediction comparison and downloadable schedule make the technical idea demonstrable.")
executive.append(table([
    ["Executed proof", "Result and scope"],
    ["Data and forecast evaluation", "19,728 retained hourly Paphos weather reconstruction records; 2,208 held-out hours; chronological and issue-cutoff checks."],
    ["Storage scheduling", f"Default fixture: {totals['water_produced_m3']:,.0f} m³ in both schedules; {totals['energy_kwh']:,.0f} kWh in both; zero modeled tank violations."],
    ["Sites leak demonstration", "Four injected overnight leak hours detected; zero alerts in the matched no-leak fixture. Synthetic data, not a field accuracy claim."],
], [145, 366]))
executive += section("Why this fits Paphos", "The proposal connects local water supply, tourism sites and solar availability through a usable planning interface. The claimed novelty is the proposed local workflow and integration. It is not a claim to have invented forecasting, linear optimization, or the first solar-water project in Cyprus.")
page(executive, "Executive summary - 2 of 2", "Evidence, business and pilot")
executive += section("The honest result", f"The independent reference model's average radiation error is <b>{mae_model:.3f} W/m²</b>, versus <b>{mae_base:.3f}</b> for the strongest same-hour observation available at the assumed previous-day 18:00 issue. The model has lower RMSE ({rmse_model:.3f} versus {rmse_base:.3f}) but worse MAE. Superior average AI prediction accuracy has not been established. This reference was created to unblock evaluation and demonstration; it is not a model supplied by Stefanos.")
executive.append(p(f"The default scheduling fixture reduces illustrative cost by <b>{totals['cost_saving_percent']:.2f}%</b> against flat production, while making equal water with equal energy and equal initial/final storage. Assumed clock tariffs drive the saving. Across 92 matched days, the model adds <b>€0 tariff saving</b> versus price-only optimization. Solar radiation is a proxy; actual curtailed electricity and avoided emissions have not been measured."))
executive += section("Business model to test", "AquaShift Sites offers the lower-friction pilot route: a paid setup and per-site service for operators that already have usable meters and irrigation records. Grid is a longer procurement and integration route, with setup plus annual support. Prices, willingness to pay, integrations, customer acquisition cost and margin remain hypotheses. No customer, contract, revenue or installed sensor is represented as existing.")
executive += section("The next pilot", "Seek one Paphos hotel or managed garden and one water operator willing to supply anonymized meter histories, operational limits and billed tariffs. First measure the current process; then run advice in shadow mode. Compare equal service against the existing schedule and a simple price-only scheduler. Continue only if measured benefit survives that comparison and staff can use the recommendations safely. Hardware purchase and automatic actuation are outside this prototype.")
executive += section("Team and AI disclosure", "<b>Technical:</b> Loucas Louka - evaluation, dashboard and prediction experiments; Στέφανος Μπορτέας - primary model and scheduler work in the roadmap. <b>Business:</b> Andreas Nikolaides and Cleopas Cleopa - business case and pitch. Codex substantially assisted implementation, evaluation, documentation and presentation preparation. The team must understand and verify the material before presentation. Lead contact and application declarations are completed separately by the team.")
executive.append(p('Requirements and dates: <link href="https://pafos.org.cy/diagonismos-kainotomias-pafos-2-0/" color="#087F8C">Official Pafos 2.0 competition page</link>. Weather: <link href="https://open-meteo.com/en/docs/historical-weather-api" color="#087F8C">Open-Meteo / ECMWF IFS historical API</link>. Exact experiment inputs and outputs are retained in the working package.', "AquaSmall"))
build("AquaShift-Executive-Summary.pdf", executive)

technical = []
page(technical, "Technical proposal - 1 of 7", "Scope and working system")
technical.append(p("AquaShift is a demonstrable advice prototype for coordinating water production with storage and electricity-price scenarios, with a separate garden and meter-flow illustration. It supports the September 30 AquaShift roadmap without attributing unsupplied code or completed model work to a teammate."))
technical.append(table([
    ["Component", "Implemented behavior", "Authority"],
    ["Grid", "24-hour linear water schedule, matched flat schedule, tank bounds, infeasibility handling, CSV export", "Illustrative plant; no controller"],
    ["Forecast", "Frozen LightGBM reference, causal persistence, climatology, hourly/monthly metrics, proxy classification and timing audit", "Historical reconstruction experiment"],
    ["Sites", "ET0 water budget and IsolationForest overnight flow alerts", "Retrospective weather + synthetic meter"],
    ["Dashboard", "Date and scenario controls, costs/water/safety, evidence and assumptions", "Local offline demonstration"],
], [68, 299, 144]))
technical += section("Division of work", "The source roadmap gives Stefanos primary ownership of data/model/scheduler handoffs and Loucas evaluation/dashboard ownership. Loucas can contribute prediction error analysis and experiments while preserving this split. Andreas Nikolaides and Cleopas Cleopa are business students responsible for the business case and pitch. The working reference provides a concrete evaluation and interface contract before Stefanos's model arrives.")
technical += section("Product boundary", "The PoC models one unit and one tank, not an operating Paphos desalination facility. It has no SCADA credentials, meter connection, valve access, customer record or control output. It demonstrates decision logic and its evaluation. Procurement, real-time integration and operational authorization belong to a later pilot.")
technical += section("Adopted components", "LightGBM supplies regression; SciPy linprog uses the upstream HiGHS linear solver; scikit-learn supplies IsolationForest; Streamlit and Plotly supply the interface and charts. Open-Meteo and ECMWF supply the gridded weather data. These are credited dependencies, not invented algorithms.")

page(technical, "Technical proposal - 2 of 7", "Data and forecast timing")
technical += section("Retained source", "Open-Meteo historical API, ECMWF IFS reconstruction, requested Paphos coordinates 34.7754, 32.4245. Returned grid point 34.76274, 32.468353, elevation 74 m. The retained 19,728 hourly rows cover local 1 July 2024 through 30 September 2026, with radiation, cloud cover, temperature, humidity, ET0 and precipitation. Raw JSON, request URL, retrieval timestamp, units and SHA-256 identities are saved.")
technical.append(p("This is downloaded real weather-product data, not direct sensor ground truth. Historical values can be reconstructed or revised. The experiment cannot establish that every value was originally available at its historical issue time. Shortwave radiation is the preceding-hour average; its timestamp is not a publication-availability guarantee."))
technical.append(table([
    ["Stage", "Frozen rule"],
    ["Training", "Target timestamps before 1 July 2026; final reference 17,444 rows. No hyperparameter search."],
    ["Threshold validation", "June 2026; model trained through May. 600 W/m² chosen before July test scoring."],
    ["Held-out test", "1 July-30 September 2026; 92 local days, 2,208 hourly records."],
    ["Forecast issue", "18:00 Asia/Nicosia on the preceding local date, for all 24 target-day hours."],
    ["Feature policy", "Calendar plus day-2/day-3 weather and issue-day data through 18:00. No target-day realized weather features."],
    ["Primary persistence", "Latest available matching local hour: day-1 for target hours 00-18; day-2 for 19-23. Assumes zero reporting delay."],
    ["Other control", "Hour/month mean fitted to training targets only. Older fixed day-2 persistence retained as secondary."],
], [135, 376]))
technical += section("Timezone and leakage checks", "UTC retrieval is converted to explicit Asia/Nicosia offsets. Tests exercise duplicated local daylight-saving hours, chronological splits, cutoff timestamps and invariance when target-day weather is changed. Publication delay, IFS revisions and original issue-time vintages remain open. A live deployment must include an explicit data-availability delay and stale-input fallback.")

page(technical, "Technical proposal - 3 of 7", "Forecast evaluation")
technical.append(table([
    ["Comparison", "All-hour MAE", "All-hour RMSE", "Daylight MAE"],
    ["Frozen LightGBM", f"{mae_model:.3f}", f"{rmse_model:.3f}", f"{day_model:.3f}"],
    ["Latest safe persistence", f"{mae_base:.3f}", f"{rmse_base:.3f}", f"{day_base:.3f}"],
    ["Train-only climatology", f"{M['all']['climatology']['mae']:.3f}", f"{M['all']['climatology']['rmse']:.3f}", f"{M['daylight']['climatology']['mae']:.3f}"],
], [166, 111, 118, 116]))
technical.append(p("Units: W/m². All hours: n=2,208. Daylight: historical target radiation &gt;20 W/m², n=1,200. Nighttime zeros make all-hour averages easier; daylight results are shown separately.", "AquaSmall"))
technical.append(figure("mae_by_month.png", height=220))
technical += section("Conclusion", "The reference's MAE is 15.37% worse than the stronger persistence control. The paired-day bootstrap 95% interval for model-minus-control error is +0.178 to +2.066 W/m² (2,000 resamples; seed 20261002). Lower RMSE suggests fewer severe errors, but does not establish overall average superiority. The bootstrap preserves days, not all seasonal dependence. Three summer months do not establish cloudy-winter accuracy.")
technical += section("Sunny-hour flag", "At 600 W/m², the model flags 612 hours: 601 correct positives, 11 false positives, six missed positives; precision 98.20%, recall 99.01%. Strong persistence has precision 98.36% and recall 98.85%. This classification concerns reconstructed solar radiation, not grid surplus. Its similarity to a simple control prevents a persuasive AI-gain claim.")

page(technical, "Technical proposal - 4 of 7", "Water and storage scheduling")
technical.append(p("Decision variables are hourly production and storage. The adopted HiGHS solver minimizes declared electricity cost, with a very small forecast preference inside equal-price hours. For hour h, storage equals previous storage plus production minus demand. Production is bounded by unit capacity; tank bounds apply at hourly endpoints. Uniform flows within an hour make these endpoint bounds consistent with the assumed within-hour trajectory."))
technical.append(table([
    ["Default assumption", "Value"],
    ["Production and demand", "500 m³/hour maximum; 120 m³/hour summer demand; assumed planning temperature 28°C"],
    ["Tank", "4,000 m³; minimum 20%; initial and final 50%"],
    ["Specific energy", "3.4 kWh/m³ for every produced cubic metre; constant in both schedules"],
    ["Price scenario", "€101/MWh at hours 10-16; €183 at 17-22; €130 otherwise; not a billed tariff"],
    ["Matched comparison", "2,880 m³, 9,792 kWh, 2,000 m³ initial/final tank in both schedules"],
    ["Default fixture result", "€1,319.880 flat → €988.992 scheduled; 25.07% scenario reduction; zero modeled violations"],
], [141, 370]))
technical += section("Forecast attribution", "All four 92-day schedules - reference model, strong persistence, training climatology and price-only - have exactly equal water, energy and scenario cost. AI adds €0 tariff saving. The reference improves actual high-radiation energy share by 0.996 percentage points versus price-only and only 0.091 points versus persistence. These are weather-proxy allocations, not recovered curtailed electricity.")
technical += section("Safety and carbon limits", "The prototype rejects infeasible capacity/demand combinations and falls back to flat production if the forecast is missing. It omits ramps, minimum run times, startup energy, maintenance, water quality and demand uncertainty. At equal energy and a constant carbon factor, physical CO2 savings are zero. A separate conditional displacement calculation is disabled by default; it cannot be reported as measured emissions avoidance.")

page(technical, "Technical proposal - 5 of 7", "Sites: garden and meter demonstration")
technical += section("Water budget", "The garden illustration computes net depth as max(0, crop coefficient × ET0 - 80% of rainfall - assumed available soil reserve). Gross irrigation divides by assumed irrigation efficiency. One millimetre over one square metre is one litre. ET0 is historical reconstructed weather. Crop coefficient, rain fraction, efficiency and soil reserve are scenario inputs, not validated site parameters or installed sensors.")
technical.append(table([
    ["Illustrative fixture", "Result"],
    ["Garden", "5,000 m²; ET0 5 mm; no rain; crop coefficient 0.7; efficiency 0.85; soil reserve 0 mm"],
    ["Water comparison", "20.588 m³ recommendation vs 30.000 m³ for a chosen 6 mm fixed timer"],
    ["Interpretation", "9.412 m³ difference against that timer, not measured saving. Hotter conditions can require more water."],
    ["Meter history", "28 synthetic normal days; query and injected leak excluded from fitting"],
    ["Leak fixture", "0.3 m³/hour injected at hours 01-04; total 1.2 m³"],
    ["Detection", "4/4 injected hours flagged; zero matched no-leak fixture alerts; seed 2026"],
], [139, 372]))
technical += section("Detector and limits", "The scikit-learn IsolationForest learns normalized hourly deviations from the simulated profile. Alerts are restricted to the declared overnight hours. Labels never enter fitting or threshold choice. This checks a controlled mechanism; it establishes neither field precision nor detection lead time. Real normal variation, occupancy, watering events, missing meters and persistent leaks require a separate field dataset.")
technical += section("Pilot interface", "A site operator would review an explanation and a timestamped alert, confirm a problem, and log its resolution. The prototype demonstrates this decision context but does not message staff, purchase sensors, or change irrigation valves. A pilot should measure actual metered water, lawn condition and false alarms before adopting recommendations.")

page(technical, "Technical proposal - 6 of 7", "Reproduction and teammate handoff")
technical.append(p("The package contains source code, pinned direct dependencies, retained weather, a text model checkpoint, prediction CSVs, charts and executed logs. The local run command is in README.md and Start AquaShift.command. The interface reads the retained files; a network request is unnecessary for the delivered demonstration."))
technical.append(table([
    ["Command / artifact", "Purpose"],
    ["data/fetch_weather.py", "Fetch source; retain raw response, metadata, hash and local hourly CSV"],
    ["model/train.py", "Fit frozen reference and June validation; save text checkpoint and predictions"],
    ["eval/evaluate.py", "Score canonical held-out CSV against matched truth and safe controls"],
    ["results/independent-review.py", "Reproduce stronger baseline and schedule-attribution conclusions"],
    ["model.test_scheduler / model.test_sites", "18 executed functional tests: storage, capacity, fallback, limits, fixtures"],
    ["eval.test_evaluation", "19 executed tests: timestamp coverage, canonical authority and causal feature rules"],
    ["tests/test_dashboard.py", "Streamlit behavior checks for complete data and scenario controls"],
], [195, 316]))
technical += section("Model replacement contract", "Stefanos's CSV needs explicit-offset time, actual, predicted and the canonical latest-safe baseline. Every test hour must be present once. The evaluator rejects wrong truth, wrong controls, negative/nonfinite predictions and out-of-period hours. Optional issue timestamps and control columns are checked. Feature-source provenance and original data availability require a separate review; a valid CSV alone does not prove a leakage-free external model.")
technical += section("A prediction contribution that ran", "An exploratory June-only residual model corrects safe persistence rather than predicting radiation directly. It improves June MAE over the direct model (11.817 to 9.997 W/m²), but remains worse than persistence (8.404). It was designed after seeing summer results, so it is development evidence, not a fresh blind claim. The frozen summer model and threshold remain unchanged. Next test: archived individual day-ahead weather runs with verified publication times and a newly frozen future period.")

page(technical, "Technical proposal - 7 of 7", "Pilot, governance and evidence")
technical.append(table([
    ["Proposed phase", "Evidence needed before proceeding"],
    ["Days 1-30: baseline", "One consenting site; anonymized meter/time/tariff records; documented operational limits; no control access"],
    ["Days 31-60: shadow advice", "Freeze method and baselines before outcomes; compare equal service; log stale inputs, false alarms and staff use"],
    ["Days 61-90: reviewed decision", "Measured benefit beyond price-only/simple controls; acceptable staff workload and safety; verified integration cost"],
], [153, 358]))
technical += section("Risk controls", "Keep advice separate from plant control. A future operator retains approval, override and recovery paths. Apply retention limits and site isolation to meter records; aggregate data can still reveal occupancy. Any later control integration requires plant-specific engineering and authorization. No prototype result justifies weakening supply protection or claiming certified safety.")
technical += section("Business validation", "Sites setup plus subscription and Grid integration plus annual support are hypotheses. Andreas and Cleopas should validate willingness to pay, procurement, integration effort, support costs and alternatives. Position the product against existing timers, meter platforms and price-only scheduling; do not claim universal uniqueness or invent clients. An operator pilot and real tariff/curtailment evidence are the proposed ask.")
technical += section("Sources and corrections", "Source concept: AquaShift Pitch.pdf and AquaShift_PoC_Work_Split.pdf emailed by Stefanos on 30 September 2026. The roadmap's weekday labels do not match 2026; use dates. The pitch's 216 GWh desalination statistic refers to 2023 in its cited article, not 2025. This proposal therefore does not use it as a current-year plant calibration. Tariff numbers remain scenarios, and no whole-country solar-curtailment percentage is asserted.")
links = [
    ("Official competition and application requirements", "https://pafos.org.cy/diagonismos-kainotomias-pafos-2-0/"),
    ("Open-Meteo historical weather / ECMWF IFS", "https://open-meteo.com/en/docs/historical-weather-api"),
    ("TSOC published day-ahead price graph - future tariff evidence", "https://tsoc.org.cy/competitive-electricity-market/dam-volume-prices-graph/"),
    ("Politis, 9 November 2025 - secondary source for 2023 energy figure and 3.4 kWh/m³", "https://en.politis.com.cy/economy/economy-hot-spot/967505/cyprus-plans-to-double-desalination-capacity-but-risks-loom"),
]
for label, url in links:
    technical.append(p(f'<link href="{url}" color="#087F8C">{escape(label)}</link>', "AquaSmall"))
technical.append(p("AI disclosure: Codex substantially assisted code, testing, documents and slides. Upstream methods and sources are credited. The team should rehearse the evidence and limitations before presenting. Application signatures and legal declarations are not completed by this package.", "AquaSmall"))
build("AquaShift-Technical-Proposal.pdf", technical)

canvas_story = [p("AquaShift - Business Model Canvas", "AquaSub")]
canvas_story.append(p("Proposed customer and revenue model. No validated customer, price, contract or revenue is claimed. Andreas Nikolaides and Cleopas Cleopa own business validation; Loucas and Stefanos support technical feasibility.", "AquaSmall"))
blocks = [
    ("Key partners", "Paphos hotel/garden pilot operator; water operator; meter/irrigation integrators; weather-data providers; university advisors. All prospective."),
    ("Key activities", "Data-quality checks; forecasting evaluation; schedule simulation; staff onboarding; monitor advice and incidents; measure benefit against simple controls."),
    ("Key resources", "Technical team; business team; tested software; site-approved meter histories; plant constraints and billed tariffs. Hardware and data agreements still required."),
    ("Value propositions", "Grid: protect modeled supply while timing equal water production to lower assumed costs. Sites: explain water budget and unusual flow. Benefits must be validated in a pilot."),
    ("Customer relationships", "Assisted setup, shadow-mode trial, operator training, support and recurring performance review. Operator approval and plain explanations build trust."),
    ("Channels", "Direct pilot outreach, local integrators, hotel and municipal networks, university demonstration. No existing distribution agreement."),
    ("Customer segments", "First: Paphos hotels and managed gardens with accessible meter data. Later: municipal spaces, golf sites and water operators with usable storage flexibility."),
    ("Cost structure", "Integration and setup time; data/hosting; support; model monitoring; field validation; privacy/security; optional sensors. Measure actual costs before pricing."),
    ("Revenue streams", "Hypotheses: paid site setup + per-site subscription; Grid integration + annual support. Price and willingness to pay untested. Verified savings may inform later pricing."),
]
cells = [p(f"<b>{escape(name)}</b><br/><br/>{escape(text)}", "AquaCanvas") for name, text in blocks]
rows = [cells[0:3], cells[3:6], cells[6:9]]
t = Table(rows, colWidths=[252, 252, 252], rowHeights=[126, 126, 126])
t.setStyle(TableStyle([
    ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ("BACKGROUND", (0, 0), (-1, -1), PALE),
    ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#B5CECC")),
    ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.white),
    ("LEFTPADDING", (0, 0), (-1, -1), 12),
    ("RIGHTPADDING", (0, 0), (-1, -1), 12),
    ("TOPPADDING", (0, 0), (-1, -1), 12),
]))
canvas_story.extend([t, Spacer(1, 8), p("Pilot decision: measured benefit beyond simple controls; equal service and safe operation; viable support cost; explicit data permission. Grid ML adds €0 tariff benefit in the tested scenario; Sites results are fixtures.", "AquaSmall")])
build("AquaShift-Business-Model-Canvas.pdf", canvas_story, landscape(A4))
print("Built executive summary, seven-page technical proposal, and business model canvas.")
