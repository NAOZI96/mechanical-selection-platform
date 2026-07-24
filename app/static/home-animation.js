"use strict";

(() => {
  const consoleRoot = document.querySelector("[data-home-animation]");
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  const compactViewport = window.matchMedia("(max-width: 720px)");

  const setupModuleCarousel = () => {
    const carousel = document.querySelector("[data-module-carousel]");
    if (!carousel) return;

    const slides = [...carousel.querySelectorAll("[data-carousel-slide]")];
    const dots = [...carousel.querySelectorAll("[data-carousel-dot]")];
    const previousButton = carousel.querySelector("[data-carousel-previous]");
    const nextButton = carousel.querySelector("[data-carousel-next]");
    const currentLabel = carousel.querySelector("[data-carousel-current]");
    if (slides.length < 2 || !previousButton || !nextButton || !currentLabel) return;

    let currentIndex = 0;
    let timerId;
    let paused = false;

    const showSlide = (nextIndex, direction = 1) => {
      const normalizedIndex = (nextIndex + slides.length) % slides.length;
      if (normalizedIndex === currentIndex) return;

      slides[currentIndex].hidden = true;
      dots[currentIndex].setAttribute("aria-pressed", "false");
      currentIndex = normalizedIndex;
      const nextSlide = slides[currentIndex];
      nextSlide.hidden = false;
      dots[currentIndex].setAttribute("aria-pressed", "true");
      currentLabel.textContent = String(currentIndex + 1).padStart(2, "0");

      if (!reduceMotion.matches && typeof nextSlide.animate === "function") {
        nextSlide.animate(
          [
            { opacity: 0, transform: `translateX(${direction * 18}px)` },
            { opacity: 1, transform: "translateX(0)" },
          ],
          { duration: 360, easing: "cubic-bezier(.2,.8,.2,1)" },
        );
      }
    };

    const stopAutoRotation = () => {
      if (timerId) window.clearInterval(timerId);
      timerId = undefined;
    };

    const startAutoRotation = () => {
      stopAutoRotation();
      if (reduceMotion.matches || paused || document.hidden) return;
      timerId = window.setInterval(() => showSlide(currentIndex + 1, 1), 5600);
    };

    previousButton.addEventListener("click", () => {
      showSlide(currentIndex - 1, -1);
      startAutoRotation();
    });
    nextButton.addEventListener("click", () => {
      showSlide(currentIndex + 1, 1);
      startAutoRotation();
    });
    dots.forEach((dot, index) => {
      dot.addEventListener("click", () => {
        showSlide(index, index >= currentIndex ? 1 : -1);
        startAutoRotation();
      });
    });
    carousel.addEventListener("mouseenter", () => {
      paused = true;
      stopAutoRotation();
    });
    carousel.addEventListener("mouseleave", () => {
      paused = false;
      startAutoRotation();
    });
    carousel.addEventListener("focusin", () => {
      paused = true;
      stopAutoRotation();
    });
    carousel.addEventListener("focusout", (event) => {
      if (carousel.contains(event.relatedTarget)) return;
      paused = false;
      startAutoRotation();
    });
    document.addEventListener("visibilitychange", startAutoRotation);
    reduceMotion.addEventListener?.("change", startAutoRotation);
    startAutoRotation();
  };

  setupModuleCarousel();
  if (!consoleRoot) return;

  const replayButton = consoleRoot.querySelector(".console-replay");

  if (reduceMotion.matches || !window.anime) {
    consoleRoot.dataset.motion = reduceMotion.matches ? "reduced" : "unavailable";
    return;
  }

  const { animate, createDrawable, createTimeline, set, stagger } = window.anime;
  const heroItems = document.querySelectorAll(
    ".home-kicker, .home-hero h1, .home-intro, .home-actions, .hero-metrics > div",
  );
  const consoleReadouts = consoleRoot.querySelectorAll(
    ".console-topline > *",
  );
  const drawingText = consoleRoot.querySelectorAll(".drawing-copy text");
  const scanline = consoleRoot.querySelector(".console-scanline");
  const gridLines = createDrawable(".console-drawing .drawing-grid path");
  const machineLines = createDrawable(
    ".console-drawing .drawing-main path, .console-drawing .drawing-main ellipse, .console-drawing .drawing-main circle",
  );
  const dimensionLines = createDrawable(".console-drawing .drawing-dimension path");
  let introTimeline;
  let introComplete = false;

  document.documentElement.classList.add("home-motion-enhanced");
  replayButton.hidden = false;

  const ambientScan = animate(scanline, {
    x: [-120, () => consoleRoot.clientWidth + 120],
    opacity: [0, 0.55, 0],
    duration: compactViewport.matches ? 2600 : 3400,
    loop: true,
    loopDelay: 900,
    ease: "inOutQuad",
    autoplay: false,
  });

  const setOpeningState = () => {
    set(heroItems, { opacity: 0, y: 18 });
    set(consoleRoot, { opacity: 0, y: 22, scale: 0.985 });
    set(consoleReadouts, { opacity: 0, y: 8 });
    set(drawingText, { opacity: 0 });
    set(scanline, { opacity: 0 });
  };

  const buildIntro = () => {
    setOpeningState();
    introComplete = false;
    introTimeline = createTimeline({
      onComplete: () => {
        introComplete = true;
        ambientScan.play();
      },
    })
      .add(heroItems, {
        opacity: [0, 1],
        y: [18, 0],
        duration: compactViewport.matches ? 520 : 720,
        delay: stagger(compactViewport.matches ? 55 : 85),
        ease: "outExpo",
      })
      .add(
        consoleRoot,
        {
          opacity: [0, 1],
          y: [22, 0],
          scale: [0.985, 1],
          duration: compactViewport.matches ? 580 : 820,
          ease: "outExpo",
        },
        compactViewport.matches ? 120 : 180,
      )
      .add(
        gridLines,
        {
          draw: ["0 0", "0 1"],
          duration: compactViewport.matches ? 500 : 760,
          delay: stagger(32),
          ease: "inOutQuad",
        },
        compactViewport.matches ? 260 : 380,
      )
      .add(
        machineLines,
        {
          draw: ["0 0", "0 1"],
          duration: compactViewport.matches ? 720 : 1040,
          delay: stagger(38, { from: "center" }),
          ease: "inOutQuint",
        },
        compactViewport.matches ? 420 : 610,
      )
      .add(
        dimensionLines,
        {
          draw: ["0 0", "0 1"],
          duration: 560,
          delay: stagger(70),
          ease: "outQuad",
        },
        compactViewport.matches ? 720 : 1040,
      )
      .add(
        drawingText,
        {
          opacity: [0, 1],
          y: [5, 0],
          duration: 420,
          delay: stagger(80),
          ease: "outQuad",
        },
        compactViewport.matches ? 840 : 1220,
      )
      .add(
        consoleReadouts,
        {
          opacity: [0, 1],
          y: [8, 0],
          duration: 460,
          delay: stagger(65),
          ease: "outExpo",
        },
        compactViewport.matches ? 900 : 1320,
      );
  };

  const replay = () => {
    ambientScan.pause();
    if (introTimeline) introTimeline.pause();
    buildIntro();
  };

  replayButton.addEventListener("click", replay);

  const setupScrollReveals = () => {
    if (!("IntersectionObserver" in window)) return;

    const horizontalDistance = compactViewport.matches ? 16 : 42;
    const verticalDistance = compactViewport.matches ? 18 : 34;
    const itemDelay = compactViewport.matches ? 55 : 90;
    const returnDistance = compactViewport.matches ? 10 : 18;
    const returnDelay = compactViewport.matches ? 35 : 55;
    const stageByTrigger = new Map();
    let scrollDirection = "down";
    let previousScrollY = window.scrollY;

    const markComplete = (trigger, targets) => {
      trigger.dataset.scrollState = "visible";
      targets.forEach((target) => {
        target.style.willChange = "auto";
      });
    };

    window.addEventListener(
      "scroll",
      () => {
        const currentScrollY = window.scrollY;
        if (currentScrollY !== previousScrollY) {
          scrollDirection = currentScrollY < previousScrollY ? "up" : "down";
          previousScrollY = currentScrollY;
        }
      },
      { passive: true },
    );

    const registerStage = (trigger, targets, prepareForward, playForward) => {
      if (!trigger || !targets.length) return;
      trigger.dataset.scrollState = "pending";
      targets.forEach((target) => {
        target.style.willChange = "transform, opacity";
      });
      prepareForward();

      const prepareBackward = () => {
        set(targets, {
          opacity: 0.28,
          x: 0,
          y: -returnDistance,
          scale: 0.992,
          rotateX: 0,
        });
      };
      const playBackward = (done) =>
        animate(targets, {
          opacity: [0.28, 1],
          y: [-returnDistance, 0],
          scale: [0.992, 1],
          duration: compactViewport.matches ? 400 : 520,
          delay: stagger(returnDelay, { from: "last" }),
          ease: "outExpo",
          onComplete: done,
        });

      stageByTrigger.set(trigger, {
        activeAnimation: null,
        inside: false,
        play(direction) {
          if (this.inside) return;
          this.inside = true;
          trigger.dataset.scrollState =
            direction === "up" ? "returning" : "entering";
          const done = () => {
            this.activeAnimation = null;
            if (this.inside) markComplete(trigger, targets);
          };
          this.activeAnimation =
            direction === "up" ? playBackward(done) : playForward(done);
        },
        reset(position) {
          this.inside = false;
          if (this.activeAnimation) {
            this.activeAnimation.pause();
            this.activeAnimation = null;
          }
          trigger.dataset.scrollState =
            position === "above" ? "return-pending" : "pending";
          targets.forEach((target) => {
            target.style.willChange = "transform, opacity";
          });
          if (position === "above") prepareBackward();
          else prepareForward();
        },
      });
    };

    document.querySelectorAll(".section-heading--home").forEach((heading) => {
      const headingCopy = heading.querySelector(":scope > div");
      const headingNote = heading.querySelector(":scope > p");
      const targets = [headingCopy, headingNote].filter(Boolean);
      registerStage(
        heading,
        targets,
        () => {
          set(headingCopy, { opacity: 0, x: -horizontalDistance });
          set(headingNote, { opacity: 0, x: horizontalDistance });
        },
        (done) => {
          return createTimeline({ onComplete: done })
            .add(headingCopy, {
              opacity: [0, 1],
              x: [-horizontalDistance, 0],
              duration: 680,
              ease: "outExpo",
            })
            .add(
              headingNote,
              {
                opacity: [0, 1],
                x: [horizontalDistance, 0],
                duration: 680,
                ease: "outExpo",
              },
              90,
            );
        },
      );
    });

    const featuredModule = document.querySelector(".featured-module");
    if (featuredModule) {
      const visual = featuredModule.querySelector(".featured-module__visual");
      const glyphParts = [...featuredModule.querySelectorAll(".module-glyph > *")];
      const content = [
        ...featuredModule.querySelectorAll(
          ".module-meta, .featured-module__content > h3, .featured-module__content > p, .capability-list, .module-entry",
        ),
      ];
      const targets = [visual, ...glyphParts, ...content].filter(Boolean);
      registerStage(
        featuredModule,
        targets,
        () => {
          set(visual, { opacity: 0, x: -horizontalDistance, scale: 0.975 });
          set(glyphParts, { opacity: 0, y: verticalDistance });
          set(content, { opacity: 0, x: horizontalDistance });
        },
        (done) => {
          return createTimeline({ onComplete: done })
            .add(visual, {
              opacity: [0, 1],
              x: [-horizontalDistance, 0],
              scale: [0.975, 1],
              duration: 760,
              ease: "outExpo",
            })
            .add(
              glyphParts,
              {
                opacity: [0, 1],
                y: [verticalDistance, 0],
                duration: 620,
                delay: stagger(itemDelay, { from: "center" }),
                ease: "outBack",
              },
              180,
            )
            .add(
              content,
              {
                opacity: [0, 1],
                x: [horizontalDistance, 0],
                duration: 620,
                delay: stagger(itemDelay),
                ease: "outExpo",
              },
              220,
            );
        },
      );
    }

    const roadmapHeading = document.querySelector(".roadmap-heading");
    if (roadmapHeading) {
      const roadmapParts = [...roadmapHeading.children];
      registerStage(
        roadmapHeading,
        roadmapParts,
        () => set(roadmapParts, { opacity: 0, y: verticalDistance }),
        (done) => {
          return animate(roadmapParts, {
            opacity: [0, 1],
            y: [verticalDistance, 0],
            duration: 640,
            delay: stagger(110),
            ease: "outExpo",
            onComplete: done,
          });
        },
      );
    }

    document.querySelectorAll(".module-grid").forEach((grid) => {
      const cards = [...grid.querySelectorAll(".module-card")];
      registerStage(
        grid,
        cards,
        () => set(cards, { opacity: 0, y: verticalDistance, scale: 0.975, rotateX: 4 }),
        (done) => {
          return animate(cards, {
            opacity: [0, 1],
            y: [verticalDistance, 0],
            scale: [0.975, 1],
            rotateX: [4, 0],
            duration: compactViewport.matches ? 540 : 720,
            delay: stagger(itemDelay),
            ease: "outExpo",
            onComplete: done,
          });
        },
      );
    });

    const workflowGrid = document.querySelector(".workflow-grid");
    if (workflowGrid) {
      const workflowItems = [...workflowGrid.children];
      registerStage(
        workflowGrid,
        workflowItems,
        () => set(workflowItems, { opacity: 0, y: verticalDistance }),
        (done) => {
          return animate(workflowItems, {
            opacity: [0, 1],
            y: [verticalDistance, 0],
            duration: 680,
            delay: stagger(itemDelay),
            ease: "outExpo",
            onComplete: done,
          });
        },
      );
    }

    const extensionSection = document.querySelector(".extension-section");
    if (extensionSection) {
      const extensionCopy = extensionSection.querySelector(".extension-copy");
      const extensionSteps = [...extensionSection.querySelectorAll(".extension-steps > li")];
      const targets = [extensionCopy, ...extensionSteps].filter(Boolean);
      registerStage(
        extensionSection,
        targets,
        () => {
          set(extensionCopy, { opacity: 0, x: -horizontalDistance });
          set(extensionSteps, { opacity: 0, x: horizontalDistance });
        },
        (done) => {
          return createTimeline({ onComplete: done })
            .add(extensionCopy, {
              opacity: [0, 1],
              x: [-horizontalDistance, 0],
              duration: 680,
              ease: "outExpo",
            })
            .add(
              extensionSteps,
              {
                opacity: [0, 1],
                x: [horizontalDistance, 0],
                duration: 620,
                delay: stagger(itemDelay),
                ease: "outExpo",
              },
              120,
            );
        },
      );
    }

    const pageFooter = document.querySelector(".home-footer");
    if (pageFooter) {
      const footerBlocks = [...pageFooter.children];
      registerStage(
        pageFooter,
        footerBlocks,
        () => set(footerBlocks, { opacity: 0, y: verticalDistance }),
        (done) => {
          return animate(footerBlocks, {
            opacity: [0, 1],
            y: [verticalDistance, 0],
            duration: 620,
            delay: stagger(100),
            ease: "outExpo",
            onComplete: done,
          });
        },
      );
    }

    const revealObserver = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          const stage = stageByTrigger.get(entry.target);
          if (!stage) return;
          if (entry.isIntersecting) {
            stage.play(scrollDirection);
            return;
          }

          const viewportBottom = entry.rootBounds?.bottom ?? window.innerHeight;
          if (entry.boundingClientRect.bottom <= 0) {
            stage.reset("above");
          } else if (entry.boundingClientRect.top >= viewportBottom) {
            stage.reset("below");
          }
        });
      },
      {
        rootMargin: compactViewport.matches ? "0px 0px -4% 0px" : "0px 0px -12% 0px",
        threshold: compactViewport.matches ? 0.04 : 0.1,
      },
    );

    stageByTrigger.forEach((_, trigger) => revealObserver.observe(trigger));
  };

  setupScrollReveals();

  const heroObserver = new IntersectionObserver(
    ([entry]) => {
      if (!introComplete) return;
      if (entry.isIntersecting && !document.hidden) ambientScan.play();
      else ambientScan.pause();
    },
    { threshold: 0.1 },
  );
  heroObserver.observe(consoleRoot);

  document.addEventListener("visibilitychange", () => {
    if (document.hidden) ambientScan.pause();
    else if (introComplete) ambientScan.play();
  });

  buildIntro();
})();
