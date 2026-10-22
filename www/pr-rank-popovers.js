(() => {
  let trigger = null, panel = null, hideTimer = null;
  const cancelHide = () => clearTimeout(hideTimer);
  function close() {
    cancelHide();
    if (trigger) trigger.setAttribute('aria-expanded', 'false');
    if (panel) panel.remove();
    trigger = panel = null;
  }
  function position() {
    if (!trigger || !panel) return;
    if (!trigger.isConnected) return close();
    const box = trigger.getBoundingClientRect();
    const width = panel.offsetWidth, height = panel.offsetHeight;
    panel.style.left = `${Math.max(8, Math.min(box.left, innerWidth - width - 8))}px`;
    const below = box.bottom + 6;
    panel.style.top = `${below + height <= innerHeight - 8 ? below : Math.max(8, box.top - height - 6)}px`;
  }
  function open(button) {
    cancelHide();
    if (trigger === button) return;
    close();
    const template = button.parentElement.querySelector('template');
    if (!template) return;
    trigger = button;
    panel = document.createElement('div');
    panel.id = 'adl-rank-popover';
    panel.setAttribute('role', 'dialog');
    panel.setAttribute('aria-label', button.getAttribute('aria-label'));
    panel.tabIndex = 0;
    panel.append(template.content.cloneNode(true));
    document.body.append(panel);
    button.setAttribute('aria-expanded', 'true');
    panel.addEventListener('mouseenter', cancelHide);
    panel.addEventListener('mouseleave', scheduleHide);
    panel.addEventListener('focusin', cancelHide);
    position();
    const selected = panel.querySelector('.rank-selected');
    const scroll = panel.querySelector('.rank-popover-scroll');
    if (selected && scroll) scroll.scrollTop = Math.max(0, selected.offsetTop - scroll.offsetTop - scroll.clientHeight / 2);
  }
  function scheduleHide() {
    cancelHide();
    hideTimer = setTimeout(() => {
      if (panel && !panel.matches(':hover') && !panel.contains(document.activeElement)) close();
    }, 220);
  }
  document.addEventListener('mouseover', event => {
    const button = event.target.closest('.rank-popover-trigger');
    if (button) open(button);
  });
  document.addEventListener('mouseout', event => {
    if (event.target.closest('.rank-popover-trigger')) scheduleHide();
  });
  document.addEventListener('focusin', event => {
    if (event.target.matches('.rank-popover-trigger')) open(event.target);
    else if (panel && !panel.contains(event.target)) close();
  });
  document.addEventListener('focusout', scheduleHide);
  document.addEventListener('click', event => {
    const button = event.target.closest('.rank-popover-trigger');
    if (button) open(button);
    else if (panel && !panel.contains(event.target)) close();
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && panel) { const button = trigger; close(); button.blur(); }
  });
  window.addEventListener('resize', position);
  window.addEventListener('scroll', position, true);
  new MutationObserver(() => { if (trigger && !trigger.isConnected) close(); })
    .observe(document.documentElement, { childList: true, subtree: true });
})();
