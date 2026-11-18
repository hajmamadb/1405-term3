(function(){
  return JSON.stringify({
    url: location.href,
    title: document.title,
    ready: document.readyState,
    bodyLen: document.body ? document.body.innerText.length : -1,
    bodySnippet: document.body ? document.body.innerText.slice(0, 400) : ''
  });
})()
