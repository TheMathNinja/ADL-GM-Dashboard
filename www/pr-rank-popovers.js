(() => {
  let trigger = null, panel = null, hideTimer = null;
  let nextSalaryRequest = 0, pendingSalaryRequest = null;
  const cancelHide = () => clearTimeout(hideTimer);
  function close() {
    cancelHide();
    if (trigger) trigger.setAttribute('aria-expanded', 'false');
    if (panel) panel.remove();
    trigger = panel = null;
    pendingSalaryRequest = null;
  }
  function computePlacement(box, width, height, viewportWidth, viewportHeight) {
    const padding = 8, gap = 12;
    const maxLeft = viewportWidth - width - padding;
    let left, top, maxHeight = viewportHeight - 2 * padding;
    if (box.right + gap + width <= viewportWidth - padding) {
      left = box.right + gap;
      top = Math.max(padding, Math.min(box.top - gap, viewportHeight - Math.min(height, maxHeight) - padding));
    } else if (box.left - gap - width >= padding) {
      left = box.left - gap - width;
      top = Math.max(padding, Math.min(box.top - gap, viewportHeight - Math.min(height, maxHeight) - padding));
    } else {
      left = Math.max(padding, Math.min(box.left + 16, maxLeft));
      const below = viewportHeight - padding - box.bottom - gap;
      const above = box.top - gap - padding;
      const useBelow = below >= height || below >= above;
      maxHeight = Math.max(0, useBelow ? below : above);
      top = useBelow ? box.bottom + gap : box.top - gap - Math.min(height, maxHeight);
    }
    return { left, top, maxHeight };
  }
  function position() {
    if (!trigger || !panel) return;
    if (!trigger.isConnected) return close();
    panel.style.maxHeight = '';
    const box = trigger.getBoundingClientRect();
    const width = panel.offsetWidth, height = panel.offsetHeight;
    const placement = computePlacement(box, width, height, innerWidth, innerHeight);
    panel.style.left = `${placement.left}px`;
    panel.style.top = `${placement.top}px`;
    panel.style.maxHeight = `${placement.maxHeight}px`;
  }
  function open(button) {
    cancelHide();
    if (trigger === button) return;
    close();
    const salary = button.dataset.salaryPosition;
    const points = button.dataset.pointsPosition;
    const template = button.parentElement.querySelector('template');
    if (!template && !salary && !points) return;
    trigger = button;
    panel = document.createElement('div');
    panel.id = 'adl-rank-popover';
    if (button.closest('#eligibility_badge')) panel.classList.add('eligibility-rank-popover');
    panel.setAttribute('role', 'dialog');
    panel.setAttribute('aria-label', button.getAttribute('aria-label'));
    panel.tabIndex = 0;
    if (template) panel.append(template.content.cloneNode(true));
    document.body.append(panel);
    button.setAttribute('aria-expanded', 'true');
    panel.addEventListener('mouseenter', cancelHide);
    panel.addEventListener('mouseleave', scheduleHide);
    panel.addEventListener('focusin', cancelHide);
    if (salary || points) {
      panel.textContent = salary ? 'Loading salary ranks...' : 'Loading points ranks...';
      pendingSalaryRequest = ++nextSalaryRequest;
      const payload = salary ? {
        id: pendingSalaryRequest, position: salary,
        week: button.dataset.salaryWeek, rank: button.dataset.salaryPr
      } : {
        id: pendingSalaryRequest, position: points, year: button.dataset.pointsYear,
        week: button.dataset.pointsWeek, metric: button.dataset.pointsMetric,
        player: button.dataset.pointsPlayer, note: button.dataset.pointsNote
      };
      window.Shiny.setInputValue(salary ? 'ext_salary_hover' : 'ext_points_hover', payload, {priority: 'event'});
    }
    positionAndScroll();
  }
  function positionAndScroll() {
    position();
    if (!panel) return;
    const selected = panel.querySelector('.rank-selected');
    const scroll = panel.querySelector('.rank-popover-scroll');
    if (selected && scroll) scroll.scrollTop = Math.max(0, selected.offsetTop - scroll.offsetTop - scroll.clientHeight / 2);
  }
  function registerSalaryHandler() {
    window.Shiny.addCustomMessageHandler('ext-salary-hover', response => {
      if (!panel || response.id !== pendingSalaryRequest) return;
      const wrapper = document.createElement('template');
      wrapper.innerHTML = response.html;
      const template = wrapper.content.querySelector('template');
      if (!template) return;
      panel.replaceChildren(template.content.cloneNode(true));
      const row = Array.from(panel.querySelectorAll('[data-salary-pr]'))
        .find(item => item.dataset.salaryPr === trigger.dataset.salaryPr);
      if (row) row.classList.add('rank-selected');
      positionAndScroll();
    });
  }
  if (window.Shiny) registerSalaryHandler();
  else document.addEventListener('DOMContentLoaded', registerSalaryHandler, {once: true});
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
