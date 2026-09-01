(function () {
  "use strict";

  var cover = document.getElementById("cover");
  var openBtn = document.getElementById("openBtn");
  var pagesWrapper = document.getElementById("pagesWrapper");
  var track = document.getElementById("track");
  var dots = Array.prototype.slice.call(document.querySelectorAll(".dot"));
  var prevBtn = document.getElementById("prevBtn");
  var nextBtn = document.getElementById("nextBtn");
  var swipeHint = document.getElementById("swipeHint");

  var PAGE_COUNT = 2;
  var currentIndex = 0;
  var containerWidth = 0;
  var isOpened = false;

  var isDragging = false;
  var dragPointerId = null;
  var startX = 0;
  var startTranslate = 0;
  var currentTranslate = 0;
  var lastX = 0;
  var lastTime = 0;
  var velocity = 0;

  function measure() {
    containerWidth = pagesWrapper.getBoundingClientRect().width || 1;
  }

  function baseTranslateFor(index) {
    return -index * containerWidth;
  }

  function applyTransform(px, animate) {
    track.style.transition = animate ? "" : "none";
    track.style.transform = "translateX(" + px + "px)";
  }

  function updateDotsAndArrows() {
    dots.forEach(function (dot, i) {
      dot.classList.toggle("is-active", i === currentIndex);
    });
    prevBtn.hidden = currentIndex === 0;
    nextBtn.hidden = currentIndex === PAGE_COUNT - 1;
  }

  function goTo(index, animate) {
    currentIndex = Math.max(0, Math.min(PAGE_COUNT - 1, index));
    measure();
    currentTranslate = baseTranslateFor(currentIndex);
    applyTransform(currentTranslate, animate !== false);
    updateDotsAndArrows();
    if (currentIndex > 0) hideSwipeHint();
  }

  function hideSwipeHint() {
    if (swipeHint) swipeHint.classList.remove("is-visible");
  }

  /* ---------- Abertura da capa (porta dupla) ---------- */

  function openCover() {
    if (isOpened) return;
    isOpened = true;

    cover.classList.add("is-open");
    pagesWrapper.classList.add("is-revealed");

    measure();
    goTo(0, false);

    window.setTimeout(function () {
      cover.classList.add("is-removed");
    }, 1100);

    window.setTimeout(function () {
      if (swipeHint) swipeHint.classList.add("is-visible");
    }, 900);
  }

  openBtn.addEventListener("click", openCover);
  openBtn.addEventListener(
    "keydown",
    function (e) {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        openCover();
      }
    }
  );

  /* ---------- Arraste / swipe entre página 2 e 3 ---------- */

  function onPointerDown(e) {
    if (!isOpened) return;
    if (e.target.closest(".hotspot")) return; // deixa o link nativo funcionar
    if (e.button !== undefined && e.button !== 0) return;

    isDragging = true;
    dragPointerId = e.pointerId;
    measure();
    startX = e.clientX;
    lastX = e.clientX;
    lastTime = performance.now();
    velocity = 0;
    startTranslate = baseTranslateFor(currentIndex);
    currentTranslate = startTranslate;
    track.classList.add("is-dragging");
    hideSwipeHint();

    try {
      track.setPointerCapture(dragPointerId);
    } catch (err) {
      /* noop */
    }
  }

  function onPointerMove(e) {
    if (!isDragging || e.pointerId !== dragPointerId) return;

    var dx = e.clientX - startX;

    var atLeftEdge = currentIndex === 0 && dx > 0;
    var atRightEdge = currentIndex === PAGE_COUNT - 1 && dx < 0;
    if (atLeftEdge || atRightEdge) {
      dx *= 0.35; // resistência nas bordas
    }

    currentTranslate = startTranslate + dx;
    applyTransform(currentTranslate, false);

    var now = performance.now();
    var dt = now - lastTime;
    if (dt > 0) {
      velocity = (e.clientX - lastX) / dt;
    }
    lastX = e.clientX;
    lastTime = now;
  }

  function onPointerUp(e) {
    if (!isDragging || e.pointerId !== dragPointerId) return;
    isDragging = false;
    track.classList.remove("is-dragging");

    var moved = currentTranslate - startTranslate;
    var threshold = containerWidth * 0.18;
    var flick = Math.abs(velocity) > 0.5;

    var target = currentIndex;
    if (moved < -threshold || (flick && velocity < 0)) {
      target = currentIndex + 1;
    } else if (moved > threshold || (flick && velocity > 0)) {
      target = currentIndex - 1;
    }

    goTo(target, true);
  }

  track.addEventListener("pointerdown", onPointerDown);
  track.addEventListener("pointermove", onPointerMove);
  track.addEventListener("pointerup", onPointerUp);
  track.addEventListener("pointercancel", onPointerUp);

  /* ---------- Navegação de apoio (pontos, setas, teclado) ---------- */

  dots.forEach(function (dot) {
    dot.addEventListener("click", function () {
      goTo(parseInt(dot.getAttribute("data-index"), 10), true);
    });
  });

  prevBtn.addEventListener("click", function () {
    goTo(currentIndex - 1, true);
  });

  nextBtn.addEventListener("click", function () {
    goTo(currentIndex + 1, true);
  });

  document.addEventListener("keydown", function (e) {
    if (!isOpened) return;
    if (e.key === "ArrowRight") goTo(currentIndex + 1, true);
    if (e.key === "ArrowLeft") goTo(currentIndex - 1, true);
  });

  var resizeTimer = null;
  window.addEventListener("resize", function () {
    window.clearTimeout(resizeTimer);
    resizeTimer = window.setTimeout(function () {
      goTo(currentIndex, false);
    }, 120);
  });

  measure();
})();
