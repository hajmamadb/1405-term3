(function(){
  var box = document.getElementById('nav--search-input');
  var ta = box && box.querySelector('textarea, input');
  if (!ta) return JSON.stringify({error: 'textarea not found in #nav--search-input', hasBox: !!box, boxHtml: box ? box.innerHTML.slice(0, 300) : ''});
  ta.focus();
  var q = window.__searchQuery || 'organizational memory newsroom';
  var proto = ta.tagName === 'TEXTAREA' ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype;
  var setter = Object.getOwnPropertyDescriptor(proto, 'value').set;
  setter.call(ta, q);
  ta.dispatchEvent(new Event('input', { bubbles: true }));
  ta.dispatchEvent(new Event('change', { bubbles: true }));
  setTimeout(function(){
    ['keydown','keypress','keyup'].forEach(function(t){
      ta.dispatchEvent(new KeyboardEvent(t, { key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true }));
    });
  }, 500);
  return JSON.stringify({ok: true, typed: q});
})()
