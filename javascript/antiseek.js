onUiUpdate(function () {
  let infoBox = document.getElementById("antiseek_info_box");
  var topElement = document.getElementById("txt2img_neg_prompt");
  if (!topElement) return;

  if (!infoBox) {
    var parent = topElement.parentNode;
    infoBox = document.createElement("div");
    infoBox.id = "antiseek_info_box";
    infoBox.style.minWidth = "100%";
    infoBox.style.textAlign = "center";
    infoBox.style.opacity = 0.6;
    infoBox.style.fontSize = ".85em";
    infoBox.style.marginTop = "4px";
    infoBox.style.pointerEvents = "none";
    parent.appendChild(infoBox);
  }

  if (typeof window.antiseek_last_fetch === "undefined") {
    window.antiseek_last_fetch = 0;
    window.antiseek_cached_count = 0;
  }

  if (Date.now() - window.antiseek_last_fetch > 2000) {
    window.antiseek_last_fetch = Date.now();
    fetch('/antiseek/count')
      .then(res => res.json())
      .then(data => {
        window.antiseek_cached_count = data.count;
      })
      .catch(() => {});
  }

  var format = "png";
  var quality = 90;

  if (typeof opts !== "undefined") {
    if (opts.antiseek_preview_format) format = opts.antiseek_preview_format;
    if (opts.antiseek_preview_quality) quality = opts.antiseek_preview_quality;
  }

  var infoText = `传输格式: ${format.toUpperCase()}`;
  
  if (format !== 'png') {
    infoText += ` (${quality})`;
    if (format === 'webp' && quality >= 100) {
        infoText += " [Lossless]";
    }
  }

  infoText += ` | 已加密: ${window.antiseek_cached_count}`;

  var finalHTML = `<span>已加载 图像潜影 (Anti-Seek) | ${infoText}</span>`;
  
  if (infoBox.innerHTML !== finalHTML) {
    infoBox.innerHTML = finalHTML;
  }
});