(function(){
  var out = {url: location.href, title: document.title, results: []};
  // Academia search results: each result card links to /<id>/<slug>
  var links = document.querySelectorAll('a[href*="academia.edu/"]');
  var seen = {};
  for (var i = 0; i < links.length; i++) {
    var a = links[i];
    var m = a.href.match(/academia\.edu\/(\d{4,})\/([A-Za-z0-9_\-]+)/);
    if (!m) continue;
    var id = m[1];
    if (seen[id]) continue;
    seen[id] = true;
    // climb up to the card container to get title + authors + abstract
    var card = a.closest('[class*="SearchResult"], [class*="PaperCard"], li, article, div[class*="Card"]') || a.parentElement;
    var text = (card ? card.innerText : '').replace(/\n+/g, ' | ').trim();
    out.results.push({id: id, href: a.href, text: text.slice(0, 400)});
    if (out.results.length >= 25) break;
  }
  out.bodySnippet = (document.body.innerText || '').slice(0, 800);
  return JSON.stringify(out);
})()
