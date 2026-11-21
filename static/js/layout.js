/**
 * Shared layout: mobile sidebar drawer (all authenticated pages).
 */
(function () {
  'use strict';

  function setupMobileMenu() {
    var openBtn = document.getElementById('mobile-menu-btn');
    var drawer = document.getElementById('mobile-drawer');
    var backdrop = document.getElementById('drawer-backdrop');
    var panel = drawer ? drawer.querySelector('aside') : null;
    var closeBtn = document.getElementById('close-drawer');

    function open() {
      if (!drawer || !backdrop || !panel) return;
      drawer.classList.remove('hidden');
      requestAnimationFrame(function () {
        backdrop.classList.add('opacity-100');
        panel.classList.remove('-translate-x-full');
      });
    }

    function close() {
      if (!drawer || !backdrop || !panel) return;
      backdrop.classList.remove('opacity-100');
      panel.classList.add('-translate-x-full');
      setTimeout(function () {
        drawer.classList.add('hidden');
      }, 200);
    }

    if (openBtn) openBtn.addEventListener('click', open);
    if (closeBtn) closeBtn.addEventListener('click', close);
    if (backdrop) backdrop.addEventListener('click', close);
  }

  document.addEventListener('DOMContentLoaded', setupMobileMenu);
})();
