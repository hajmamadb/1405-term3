(function(){
  var out = {url: location.href, results: []};
  // Get all links that point to academia.edu document pages (any pattern)
  var links = document.querySelectorAll('a[href*="academia.edu/"]');
  var seen = {};
  for (var i = 0; i < links.length; i++) {
    var a = links[i];
    var href = a.href;
    // Match document URLs: /<id>/<slug> or /documents/<id>
    var m = href.match(/academia\.edu\/(\d{4,})(?:\/([A-Za-z0-9_\-]+))?/) || href.match(/academia\.edu\/documents\/(\d{4,})/);
    if (!m) continue;
    var id = m[1];
    if (seen[id]) continue;
    seen[id] = true;
    var card = a.closest('li, article, div[class*="Card"], div[class*="result"]') || a.parentElement;
    var text = (card ? card.innerText : '').replace(/\n+/g, ' | ').trim();
    out.results.push({id: id, href: href.split('?')[0], text: text.slice(0, 400)});
    if (out.results.length >= 20) break;
  }
  return JSON.stringify(out);
})()
