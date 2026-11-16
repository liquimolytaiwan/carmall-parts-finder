(function () {
  "use strict";
  // ---- iframe auto-height ----
  // Measure the content element, NOT documentElement.scrollHeight: inside an iframe the
  // latter is clamped to the viewport (= the height the parent just set), so it only ever
  // grows and leaves a blank gap on phones. See embed-snippet.html for the receiving side.
  // carmallFinderHeight is the shared message name for the hub and every finder added
  // after it; the snippet also accepts the two older finders' names.
  var root = document.getElementById("hub");
  function postHeight() {
    try {
      var h = Math.ceil(root.getBoundingClientRect().height);
      if (h > 0) parent.postMessage({ type: "carmallFinderHeight", height: h }, "*");
    } catch (e) {}
  }
  window.addEventListener("load", postHeight);
  window.addEventListener("resize", postHeight);
  if (window.ResizeObserver) { new ResizeObserver(postHeight).observe(root); }

  // Back on the hub: tell the store page to drop the previous finder's #f=… from its
  // address bar, or a reload (or a copied URL) would jump straight back into that finder.
  // docs/share-links.md
  try {
    if (parent !== window) parent.postMessage({ type: "carmallFinderState", finder: "", state: "" }, "*");
  } catch (e) {}
})();
