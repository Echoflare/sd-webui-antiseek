onUiUpdate(function () {
  let infoBox = document.getElementById("antiseek_info_box");
  if (infoBox) return;

  var topElement = document.getElementById("txt2img_neg_prompt");
  if (!topElement) return;

  var parent = topElement.parentNode;
  infoBox = document.createElement("div");
  infoBox.id = "antiseek_info_box";
  infoBox.style.minWidth = "100%";
  infoBox.style.textAlign = "center";
  infoBox.style.opacity = 0.5;
  infoBox.style.fontSize = ".85em";
  infoBox.style.marginTop = "4px";
  
  infoBox.innerHTML = `<span>已加载 图像潜影 (Anti-Seek)</span>`;
  
  parent.appendChild(infoBox);
});