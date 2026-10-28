"""Build index.html (static mode) from _src/page.html. Run from the repo root: python3 _src/build_site.py"""
head = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
        '<meta name="description" content="Design, marketing and art events in San Francisco, plus the mixers where clients hang out. Updated every Friday.">'
        '<style>html,body{margin:0}:root{padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}img{max-width:100%}[hidden]{display:none!important}</style>'
        '<script>window.STATIC_SITE=true</script></head><body>')
open("index.html", "w").write(head + open("_src/page.html").read() + "</body></html>")
print("index.html built")
