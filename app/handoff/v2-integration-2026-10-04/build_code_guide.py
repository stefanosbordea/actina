"""Build the 019 guide from exact source excerpts and retained validation counts."""
import argparse
import hashlib
import html
import json
from pathlib import Path
import re

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
OUTPUT=ROOT/'app/experiments/v2-019/CODE-GUIDE.html'
EXCERPTS=[('model/train_modelv2.py',24,29,'Stefanos’s original v2 settings'),
          ('app/experiments/v2-016/run.py',125,133,'Refit with training-only early stopping'),
          ('app/experiments/v2-019/run.py',35,42,'Eleven forecast features, then four past-error features'),
          ('app/experiments/v2-019/run.py',45,49,'Save every weight and the intercept'),
          ('app/experiments/v2-019/run.py',95,100,'Keep the refit curve and calculate the event call')]


def source_figure(item):
    path,first,last,title=item
    content=(ROOT/path).read_bytes()
    digest=hashlib.sha256(content).hexdigest()
    lines=content.decode().splitlines()
    assert 1<=first<=last<=len(lines)
    excerpt=''.join(f'<span class="code-line"><span class="line-number" aria-hidden="true">{i}</span><span class="source-line">{html.escape(lines[i-1])}</span></span>' for i in range(first,last+1))
    return f'<figure data-source="{path}" data-first-line="{first}" data-last-line="{last}" data-sha256="{digest}"><figcaption><strong>{title}</strong><span>{path} <b>lines {first}–{last}</b> <abbr title="SHA-256 {digest}">{digest[:12]}</abbr></span></figcaption><pre><code>{excerpt}</code></pre></figure>'


def build():
    style_source=(ROOT/'app/experiments/v2-017/CODE-GUIDE.html').read_text()
    css=re.search(r'<style>(.*?)</style>',style_source,re.S).group(1)
    css+='abbr{font:10px ui-monospace,monospace;text-decoration:none;color:#777;margin-left:8px}table{width:100%;border-collapse:collapse;margin-top:17px;font-size:13px}th,td{text-align:right;padding:8px 10px;border-bottom:1px solid #333}th:first-child,td:first-child{text-align:left}th{font-weight:400;color:#aaa}tbody tr:last-child{color:#fff}.comparison{color:#bbb}.sheet+.sheet{padding-bottom:36px}'
    metrics=json.loads((ROOT/'app/experiments/v2-019/review/review.json').read_text())
    assert metrics['status']=='PASS'
    model=json.loads((ROOT/'app/experiments/v2-019/result/expanded-final.json').read_text())
    assert len(model['features'])==len(model['coefficients'])==15
    assert metrics['thresholds']['expanded']==.49
    rows=''.join(f"<tr><td>{label}</td><td>{metrics['metrics'][name]['f1']*100:.2f}%</td><td>{metrics['metrics'][name]['fp']}</td><td>{metrics['metrics'][name]['fn']}</td></tr>" for name,label in [('supplied_v2_600','Supplied v2'),('fixed008','008 comparison'),('expanded','019 correction')])
    figures=[source_figure(item) for item in EXCERPTS]
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="dark"><title>Aktina — 019 code walkthrough</title><style>{css}</style></head><body><main>
<section class="sheet" id="forecast"><header><span class="label">Aktina / V2 source</span><a href="#correction">See the correction ↓</a></header>
<h1>Built on Stefanos’s v2.</h1>
<p class="intro">019 uses the saved 016 refit of v2. Earlier training windows produce the examples used to train the correction. Stefanos’s original source is merged unchanged.</p>
{figures[0]}
{figures[1]}
<p class="note">The refit keeps v2’s nine input features and LightGBM design, with early stopping inside the training period. <strong>Its radiation curve differs slightly from the supplied v2 CSV.</strong> 019 reuses that curve unchanged.</p>
<div class="footer"><span>Upstream 85097a560769 → merge 3f3b3038fd11</span><span>Seven added source files verified byte for byte.</span></div></section>
<section class="sheet" id="correction"><header><span class="label">Aktina / 019 correction</span><a href="#forecast">↑ V2 source</a></header>
<h2>Fifteen weights and one intercept.</h2>
<div class="flow" aria-label="Refitted v2 curve and weather context feed one logistic event correction"><b>V2 refit</b><i>→</i><span>Forecasts and past errors</span><i>→</i><b>Event probability</b></div>
<p class="intro">One logistic model reads the v2 prediction, weather forecasts and calendar features. Four inputs describe the last 14 days of v2 and ECMWF errors, using observations strictly before the decision time. 008 supplies no model weights or prediction inputs.</p>
{figures[2]}
{figures[3]}
{figures[4]}
<p class="note">The event remains observed radiation &gt;600 W/m². The correction calls an event at probability &gt;0.49, selected from earlier training predictions.</p>
<table class="comparison"><caption class="note">Same 3,566 validation hours</caption><thead><tr><th scope="col">Model</th><th scope="col">F1</th><th scope="col">False alarms</th><th scope="col">Missed events</th></tr></thead><tbody>{rows}</tbody></table>
<p class="note"><strong>Four fewer false alarms than 008, with one additional missed event.</strong> This is an observed improvement on reused validation data. Its uncertainty interval against 008 includes zero.</p>
<div class="footer"><a href="review/review.json">Independent replay and counts</a><span>Source excerpts retain their exact lines and hashes.</span></div></section>
</main></body></html>'''


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    content=build()
    if args.check:
        assert OUTPUT.read_text()==content
    else:
        with OUTPUT.open('x') as stream:
            stream.write(content)
    print(json.dumps(dict(status='PASS',excerpts=len(EXCERPTS),output=str(OUTPUT.relative_to(ROOT)),sha256=hashlib.sha256(content.encode()).hexdigest())))
