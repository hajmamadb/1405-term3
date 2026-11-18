(function(){
  // First click full text tab
  var els = document.querySelectorAll('li, a, button, div[role="tab"]');
  var clicked = null;
  for (var i = 0; i < els.length; i++) {
    var t = (els[i].innerText || '').trim();
    if (/full text/i.test(t) && t.length < 60) { els[i].click(); clicked = t; break; }
  }
  return JSON.stringify({clicked: clicked});
})()
