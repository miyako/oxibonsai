document.querySelectorAll("pre > code").forEach((code, index) => {
  const pre = code.parentElement;
  const wrapper = document.createElement("div");
  wrapper.className = "code-wrapper";
  pre.before(wrapper);
  wrapper.append(pre);
  pre.tabIndex = 0;
  pre.setAttribute("aria-label", `Code example ${index + 1}`);

  const button = document.createElement("button");
  button.type = "button";
  button.className = "copy-btn";
  button.textContent = "Copy";
  button.setAttribute("aria-label", `Copy code example ${index + 1}`);
  wrapper.prepend(button);

  button.addEventListener("click", async () => {
    const status = document.getElementById("copy-status");
    status.textContent = "";
    try {
      if (!navigator.clipboard) {
        throw new Error("Clipboard access is unavailable in this browser context.");
      }
      await navigator.clipboard.writeText(code.textContent);
      button.textContent = "Copied";
      status.textContent = `Code example ${index + 1} copied.`;
    } catch (error) {
      button.textContent = "Select & copy";
      status.textContent = "Could not copy automatically. The code is selected; use your browser's copy command.";
      const selection = window.getSelection();
      const range = document.createRange();
      range.selectNodeContents(code);
      selection.removeAllRanges();
      selection.addRange(range);
      pre.focus();
      console.error("Could not copy code:", error);
    }
    window.setTimeout(() => { button.textContent = "Copy"; }, 2500);
  });
});
