/* ============================================
   Time Saver AI — Main JavaScript
   - Smooth scroll
   - Fade-in animations on scroll
   - Header shadow on scroll
   ============================================ */

(function () {
  'use strict';

  /* ---------- Fade-in animations ---------- */
  const animateOnScroll = () => {
    const elements = document.querySelectorAll(
      '.hero__content, .hero__visual, .section-header, .card, .case__card, .about__visual, .about__content, .cta__inner'
    );

    elements.forEach((el) => el.classList.add('fade-in'));

    if (!('IntersectionObserver' in window)) {
      elements.forEach((el) => el.classList.add('is-visible'));
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add('is-visible');
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.12, rootMargin: '0px 0px -40px 0px' }
    );

    elements.forEach((el) => observer.observe(el));
  };

  /* ---------- Header shadow on scroll ---------- */
  const headerScroll = () => {
    const header = document.querySelector('.header');
    if (!header) return;

    const onScroll = () => {
      if (window.scrollY > 10) {
        header.style.boxShadow = '0 1px 8px rgba(26, 35, 50, 0.06)';
      } else {
        header.style.boxShadow = 'none';
      }
    };

    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
  };

  /* ---------- Smooth scroll for anchor links ---------- */
  const smoothScroll = () => {
    document.querySelectorAll('a[href^="#"]').forEach((link) => {
      link.addEventListener('click', (e) => {
        const targetId = link.getAttribute('href');
        if (!targetId || targetId === '#') return;

        const target = document.querySelector(targetId);
        if (!target) return;

        e.preventDefault();
        const headerHeight = document.querySelector('.header')?.offsetHeight || 0;
        const top = target.getBoundingClientRect().top + window.scrollY - headerHeight - 16;
        window.scrollTo({ top, behavior: 'smooth' });
      });
    });
  };

  /* ---------- Init ---------- */
  const init = () => {
    animateOnScroll();
    headerScroll();
    smoothScroll();
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
