(function(){
  var out = {title: document.title, links: []};
  // Find all links and buttons that might be download-related
  var els = document.querySelectorAll('a, button, [role="button"]');
  for (var i = 0; i < els.length; i++) {
    var el = els[i];
    var text = (el.innerText || el.getAttribute('aria-label') || el.getAttribute('title') || '').trim().replace(/\n+/g, ' | ');
    var href = el.href || el.getAttribute('href') || '';
    var cls = (el.className && typeof el.className === 'string') ? el.className : '';
    if (/download|pdf/i.test(text) || /download|pdf/i.test(href) || /download/i.test(cls)) {
      out.links.push({text: text.slice(0, 80), href: href.slice(0, 200), tag: el.tagName, cls: cls.slice(0, 60)});
    }
  }
  return JSON.stringify(out);
})()
