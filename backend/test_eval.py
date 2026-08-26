import asyncio, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from scrape_shop import run_opencli, SESSION
JS = '(() => { var el = document.querySelector("meta[property=\"og:image\"], meta[name=\"og:image\"]"); return el ? el.content : "NONE"; })()'
JS2 = '(() => { var imgs = document.querySelectorAll("img"); var r = []; for (var i=0;i<Math.min(imgs.length,10);i++) { var s = imgs[i].src || imgs[i].getAttribute("data-ks-lazyload") || ""; if (s) r.push(s); } return JSON.stringify(r); })()'
async def main():
    raw = await run_opencli("browser", SESSION, "eval", JS)
    print(f"OG_IMAGE raw: [{raw[:200]}]")
    raw2 = await run_opencli("browser", SESSION, "eval", JS2)
    print(f"IMGS raw: [{raw2[:300]}]")
asyncio.run(main())
