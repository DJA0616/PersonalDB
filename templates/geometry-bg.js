/**
 * GeometryBackground — Dynamic canvas background for Summer MathPhys Training
 * ============================================================================
 * Self-contained vanilla JS. Drop into any page with a <script> tag.
 * Auto-initializes. Exposes window.GeometryBackground for programmatic use.
 *
 * Reactivity:
 *   - Mouse: grid warps toward cursor, particles glow/attract, polygons tilt, rays brighten, radial glow follows
 *   - Scroll: parallax depth layers (grid 0.3x, particles 0.5x, polygons 0.1-0.3x, orbiters 0.4x, rays 0.2x)
 *   - Time: particles drift in Lissajous orbits, multiple polygons morph slowly through keyframes,
 *           orbiters circle, floating rays drift across scene
 *
 * Configurable via data attributes on the script tag:
 *   data-accent="#7eb8d4" data-accent-alt="#a0d4b0" data-bg="#0a0a0a"
 *   data-grid-opacity="0.04" data-particle-count="28" data-mouse-glow="true"
 */

(function () {
  "use strict";

  // ═══════════════════════════════════════════════════════════════
  // CONFIGURATION
  // ═══════════════════════════════════════════════════════════════

  const CFG = {
    bg: "#0a0a0a",
    accent: "#7eb8d4",
    accentAlt: "#a0d4b0",
    accentErr: "#d47e8a",

    // Grid
    gridSpacingX: 80,
    gridSpacingY: 60,
    gridOpacity: 0.04,
    gridMouseShift: 30, // max px grid origin shifts toward mouse
    gridParallax: 0.3,

    // Constellation particles
    particleCount: 28,
    particleBaseRadius: 1.2,
    particleGlowRadius: 2.4,
    particleOpacity: 0.18,
    particleConnectionDist: 180,
    particleConnectionOpacity: 0.04,
    particleMouseReach: 200,
    particleMousePull: 0.015,
    particleDriftSpeed: 0.0003,
    particleDriftAmp: 40,
    particleParallax: 0.5,

    // Morphing polygons — multiple instances with varied shape sequences
    polygonInstances: 5,
    polygonOpacity: 0.045,
    polygonStrokeWidth: 0.5,
    polygonMorphMin: 12000,  // ms per keyframe transition (min, randomized per instance)
    polygonMorphMax: 28000,
    polygonParallaxMin: 0.08,
    polygonParallaxMax: 0.22,

    // Floating rays
    rayCount: 10,
    rayMinLength: 60,
    rayMaxLength: 200,
    rayOpacity: 0.05,
    rayWidth: 0.4,
    raySpeedMin: 8,   // px/s drift
    raySpeedMax: 25,
    rayMouseReach: 250,
    rayParallax: 0.2,

    // Orbiting nodes
    orbiterCount: 5,
    orbiterOpacity: 0.08,
    orbiterMouseSpeedup: 2.5,
    orbiterParallax: 0.4,

    // Mouse glow
    mouseGlowRadius: 300,
    mouseGlowOpacity: 0.03,
    mouseGlowFeather: 0.6,

    // Ambient gradients (corner glows, like original)
    ambientGlowTL: { x: "15%", y: "5%", r: "35%", color: "#7eb8d4", opacity: 0.04 },
    ambientGlowBR: { x: "85%", y: "95%", r: "30%", color: "#a0d4b0", opacity: 0.03 },
  };

  // Read data attributes from script tag for overrides
  (function applyDataAttrs() {
    const script = document.currentScript;
    if (!script) return;
    const map = {
      accent: "data-accent",
      accentAlt: "data-accent-alt",
      bg: "data-bg",
      gridOpacity: "data-grid-opacity",
      particleCount: "data-particle-count",
    };
    for (const [key, attr] of Object.entries(map)) {
      const v = script.getAttribute(attr);
      if (v !== null) {
        const num = parseFloat(v);
        CFG[key] = isNaN(num) ? v : num;
      }
    }
  })();

  // ═══════════════════════════════════════════════════════════════
  // POLYGON MORPH KEYFRAMES (6-point, centered at origin)
  // ═══════════════════════════════════════════════════════════════

  const pt = (deg, r) => [
    r * Math.cos((deg - 90) * Math.PI / 180),
    r * Math.sin((deg - 90) * Math.PI / 180),
  ];

  const POLY_FRAMES = [
    [pt(0, 1), pt(60, 0.44), pt(120, 1), pt(180, 0.44), pt(240, 1), pt(300, 0.44)],
    [pt(0, 1), pt(90, 1), pt(180, 1), pt(270, 1), pt(45, 0.46), pt(225, 0.46)],
    [pt(0, 1), pt(72, 1), pt(144, 1), pt(216, 1), pt(288, 1), pt(180, 0.35)],
    [pt(0, 1), pt(60, 1), pt(120, 1), pt(180, 1), pt(240, 1), pt(300, 1)],
    [pt(5, 1.18), pt(75, 0.54), pt(148, 1.07), pt(212, 0.59), pt(278, 1.11), pt(335, 0.7)],
    [pt(0, 0.7), pt(58, 1.17), pt(122, 0.65), pt(178, 1.17), pt(238, 0.7), pt(300, 1.04)],
    [pt(22, 1.07), pt(84, 0.46), pt(158, 0.93), pt(222, 0.46), pt(288, 1.07), pt(196, 0.74)],
  ];

  // 5-point star/pentagon sequences — sharper, more angular
  const SHAPE_5PT = [
    [pt(0, 1), pt(72, 0.5), pt(144, 1), pt(216, 0.5), pt(288, 1)],
    [pt(0, 0.5), pt(72, 1), pt(144, 0.5), pt(216, 1), pt(288, 0.5)],
    [pt(0, 1), pt(72, 1), pt(144, 1), pt(216, 1), pt(288, 1)],
    [pt(10, 1.2), pt(82, 0.6), pt(154, 1.1), pt(226, 0.55), pt(298, 0.9)],
    [pt(0, 0.8), pt(65, 1.15), pt(130, 0.7), pt(210, 1.15), pt(285, 0.8)],
    [pt(15, 0.55), pt(70, 0.95), pt(144, 0.5), pt(218, 0.95), pt(292, 0.55)],
    [pt(0, 0.9), pt(72, 0.4), pt(144, 0.9), pt(216, 0.4), pt(288, 0.9)],
  ];

  // 4-point diamond/rhombus sequences
  const SHAPE_4PT = [
    [pt(0, 1), pt(90, 0.6), pt(180, 1), pt(270, 0.6)],
    [pt(45, 1), pt(135, 0.5), pt(225, 1), pt(315, 0.5)],
    [pt(0, 0.55), pt(90, 1.1), pt(180, 0.55), pt(270, 1.1)],
    [pt(0, 1), pt(90, 1), pt(180, 1), pt(270, 1)],
    [pt(20, 1.15), pt(110, 0.7), pt(200, 1.05), pt(290, 0.65)],
    [pt(0, 0.7), pt(90, 1.2), pt(180, 0.7), pt(270, 1.2)],
    [pt(30, 0.5), pt(120, 1), pt(210, 0.5), pt(300, 1)],
  ];

  // 8-point octagon sequences — complex, slower-feeling
  const SHAPE_8PT = [
    [pt(0, 1), pt(45, 0.7), pt(90, 1), pt(135, 0.7), pt(180, 1), pt(225, 0.7), pt(270, 1), pt(315, 0.7)],
    [pt(0, 0.7), pt(45, 1), pt(90, 0.7), pt(135, 1), pt(180, 0.7), pt(225, 1), pt(270, 0.7), pt(315, 1)],
    [pt(0, 1), pt(45, 1), pt(90, 1), pt(135, 1), pt(180, 1), pt(225, 1), pt(270, 1), pt(315, 1)],
    [pt(10, 1.1), pt(55, 0.65), pt(100, 1.05), pt(145, 0.7), pt(190, 1.1), pt(235, 0.6), pt(280, 1.05), pt(325, 0.7)],
    [pt(0, 0.6), pt(45, 1.15), pt(90, 0.6), pt(135, 1.15), pt(180, 0.6), pt(225, 1.15), pt(270, 0.6), pt(315, 1.15)],
    [pt(22, 0.75), pt(67, 0.55), pt(112, 0.9), pt(157, 0.5), pt(202, 0.75), pt(247, 0.55), pt(292, 0.9), pt(337, 0.5)],
  ];

  const ALL_SHAPES = [POLY_FRAMES, SHAPE_5PT, SHAPE_4PT, SHAPE_8PT];

  // ═══════════════════════════════════════════════════════════════
  // UTILITY HELPERS
  // ═══════════════════════════════════════════════════════════════

  const lerp = (a, b, t) => a + (b - a) * t;
  const dist = (x1, y1, x2, y2) => Math.hypot(x2 - x1, y2 - y1);
  const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

  // Smooth-curve interpolation between two polygon frames
  const sCurve = (a, b, t) => a + (b - a) * (10 * t ** 3 - 15 * t ** 4 + 6 * t ** 5);
  const morphFrame = (f1, f2, t) =>
    f1.map((p, i) => [sCurve(p[0], f2[i][0], t), sCurve(p[1], f2[i][1], t)]);

  // ═══════════════════════════════════════════════════════════════
  // GEOMETRY BACKGROUND CLASS
  // ═══════════════════════════════════════════════════════════════

  class GeometryBackground {
    constructor(options) {
      Object.assign(CFG, options);

      this.mouse = { x: -1000, y: -1000 }; // raw mouse position
      this.smooth = { x: 0.5, y: 0.5 }; // smoothed 0..1 viewport fraction
      this.scroll = 0;
      this.smoothScroll = 0;
      this.time = 0;
      this.width = 0;
      this.height = 0;
      this.docHeight = 0;
      this.dpr = 1;

      // Polygon instances (multiple shapes, scattered)
      this.polyInstances = [];

      // Floating rays
      this.rays = [];

      // Particles
      this.particles = [];

      // Orbiters
      this.orbiters = [];

      this.init();
    }

    // ── Init ────────────────────────────────────────────────

    init() {
      this.canvas = document.createElement("canvas");
      this.canvas.className = "geo-bg-canvas";
      this.canvas.style.cssText =
        "position:fixed;inset:0;width:100%;height:100%;pointer-events:none;z-index:0;";
      document.body.prepend(this.canvas);
      this.ctx = this.canvas.getContext("2d");

      // Hide any existing static Geo SVGs
      this._hideStaticGeo();

      this.resize();
      this.createPolyInstances();
      this.createRays();
      this.createParticles();
      this.createOrbiters();
      this.bindEvents();
      this.animate(0);
    }

    _hideStaticGeo() {
      // Find SVG elements that look like the old static Geo background
      const svgs = document.querySelectorAll("svg");
      svgs.forEach((svg) => {
        const style = svg.getAttribute("style") || "";
        if (
          style.includes("position:fixed") &&
          style.includes("pointer-events:none") &&
          (style.includes("z-index:0") || style.includes("z-index: 0"))
        ) {
          svg.style.display = "none";
        }
      });
      // Also hide React-rendered Geo SVGs that don't have inline style
      // (block-kit Geo applies style via React, checks computed style)
      // We handle these after a short delay in case React hasn't rendered yet
      setTimeout(() => {
        const allSvgs = document.querySelectorAll("svg");
        allSvgs.forEach((svg) => {
          const cs = getComputedStyle(svg);
          if (
            cs.position === "fixed" &&
            cs.pointerEvents === "none" &&
            (cs.zIndex === "0" || cs.zIndex === "auto") &&
            svg.parentElement &&
            svg !== this.canvas
          ) {
            svg.style.display = "none";
          }
        });
      }, 200);
    }

    resize() {
      this.dpr = Math.min(window.devicePixelRatio || 1, 2);
      this.width = window.innerWidth;
      this.height = window.innerHeight;
      this.docHeight = Math.max(
        document.body.scrollHeight,
        document.documentElement.scrollHeight,
        this.height
      );
      this.canvas.width = this.width * this.dpr;
      this.canvas.height = this.height * this.dpr;
      this.ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
    }

    // ── Particles ───────────────────────────────────────────

    createParticles() {
      this.particles = [];
      for (let i = 0; i < CFG.particleCount; i++) {
        this.particles.push({
          bx: Math.random() * this.width, // base x (in viewport coords)
          by: Math.random() * this.docHeight, // base y (in document coords)
          phase: Math.random() * Math.PI * 2,
          driftRx: 20 + Math.random() * CFG.particleDriftAmp,
          driftRy: 15 + Math.random() * CFG.particleDriftAmp,
          speedX: (Math.random() - 0.5) * 2,
          speedY: (Math.random() - 0.5) * 2,
          r: CFG.particleBaseRadius * (0.6 + Math.random() * 0.8),
        });
      }
    }

    // ── Orbiters ────────────────────────────────────────────

    createOrbiters() {
      this.orbiters = [];
      for (let i = 0; i < CFG.orbiterCount; i++) {
        this.orbiters.push({
          cx: this.width * (0.15 + Math.random() * 0.7),
          cy: this.docHeight * (0.1 + Math.random() * 0.8),
          rx: 40 + Math.random() * 120,
          ry: 25 + Math.random() * 70,
          speed: 0.0002 + Math.random() * 0.0004,
          phase: Math.random() * Math.PI * 2,
          r: 0.6 + Math.random() * 1.0,
        });
      }
    }

    // ── Polygon Instances ──────────────────────────────────

    createPolyInstances() {
      this.polyInstances = [];
      for (let i = 0; i < CFG.polygonInstances; i++) {
        const seq = ALL_SHAPES[i % ALL_SHAPES.length];
        const startFrame = Math.floor(Math.random() * seq.length);
        this.polyInstances.push({
          sequence: seq,
          // Scatter across viewport, biasing toward edges/corners
          vx: 0.08 + Math.random() * 0.84,
          vy: 0.08 + Math.random() * 0.84,
          scale: 0.06 + Math.random() * 0.14,
          morphMs: CFG.polygonMorphMin + Math.random() * (CFG.polygonMorphMax - CFG.polygonMorphMin),
          parallax: CFG.polygonParallaxMin + Math.random() * (CFG.polygonParallaxMax - CFG.polygonParallaxMin),
          opacity: CFG.polygonOpacity * (0.5 + Math.random() * 1.0),
          frameIdx: startFrame,
          morphElapsed: Math.random() * CFG.polygonMorphMax,
          drawGhost: Math.random() > 0.4,
          drawRays: Math.random() > 0.5,
          accent: i % 2 === 0 ? CFG.accent : CFG.accentAlt,
        });
      }
    }

    // ── Floating Rays ──────────────────────────────────────

    createRays() {
      this.rays = [];
      for (let i = 0; i < CFG.rayCount; i++) {
        this.rays.push(this._spawnRay(true));
      }
    }

    _spawnRay(initial) {
      const angle = Math.random() * Math.PI * 2;
      const speed = CFG.raySpeedMin + Math.random() * (CFG.raySpeedMax - CFG.raySpeedMin);
      return {
        x: initial ? Math.random() * this.width : -100 - Math.random() * 300,
        y: initial ? Math.random() * this.height : Math.random() * this.height,
        angle: angle,
        length: CFG.rayMinLength + Math.random() * (CFG.rayMaxLength - CFG.rayMinLength),
        vx: Math.cos(angle) * speed,
        vy: Math.sin(angle) * speed,
        opacity: CFG.rayOpacity * (0.4 + Math.random() * 1.2),
        width: CFG.rayWidth * (0.5 + Math.random() * 1.0),
      };
    }

    // ── Events ──────────────────────────────────────────────

    bindEvents() {
      let rafId = null;

      window.addEventListener("resize", () => {
        this.resize();
        this.createPolyInstances();
        this.createRays();
        this.orbiters.forEach((o) => {
          o.cx = clamp(o.cx, 0, this.width);
          o.cy = clamp(o.cy, 0, this.docHeight);
        });
      });

      window.addEventListener("mousemove", (e) => {
        this.mouse.x = e.clientX;
        this.mouse.y = e.clientY;
        this.smooth.x = clamp(e.clientX / this.width, 0, 1);
        this.smooth.y = clamp(e.clientY / this.height, 0, 1);
      });

      window.addEventListener("mouseleave", () => {
        this.mouse.x = -1000;
        this.mouse.y = -1000;
      });

      window.addEventListener(
        "scroll",
        () => {
          this.scroll = window.scrollY;
          if (!rafId) {
            rafId = requestAnimationFrame(() => {
              rafId = null;
            });
          }
        },
        { passive: true }
      );
    }

    // ── Animation Loop ──────────────────────────────────────

    animate(timestamp) {
      this.time = timestamp;

      // Smooth scroll (lerp toward target)
      this.smoothScroll = lerp(this.smoothScroll, this.scroll, 0.08);

      const ctx = this.ctx;
      const W = this.width;
      const H = this.height;
      const D = this.docHeight;

      ctx.clearRect(0, 0, W, H);
      ctx.fillStyle = CFG.bg;
      ctx.fillRect(0, 0, W, H);

      // ── 1. Ambient corner gradients ──
      this.drawAmbientGradients(ctx, W, H);

      // ── 2. Grid ──
      this.drawGrid(ctx, W, H);

      // ── 3. Morphing polygons (multiple instances) ──
      this.drawMorphingPolygons(ctx, W, H);

      // ── 4. Floating rays ──
      this.drawRays(ctx, W, H);

      // ── 5. Orbiters ──
      this.drawOrbiters(ctx, W, H, D);

      // ── 6. Constellation particles ──
      this.drawConstellation(ctx, W, H, D);

      // ── 7. Mouse glow ──
      this.drawMouseGlow(ctx, W, H);

      requestAnimationFrame((t) => this.animate(t));
    }

    // ── 1. Ambient Gradients ────────────────────────────────

    drawAmbientGradients(ctx, W, H) {
      // Top-left blue glow
      const g1 = ctx.createRadialGradient(
        W * 0.15, H * 0.05, 0,
        W * 0.15, H * 0.05, Math.max(W, H) * 0.35
      );
      g1.addColorStop(0, hexToRgba(CFG.accent, CFG.ambientGlowTL.opacity));
      g1.addColorStop(1, hexToRgba(CFG.accent, 0));
      ctx.fillStyle = g1;
      ctx.fillRect(0, 0, W, H);

      // Bottom-right sage glow
      const g2 = ctx.createRadialGradient(
        W * 0.85, H * 0.95, 0,
        W * 0.85, H * 0.95, Math.max(W, H) * 0.3
      );
      g2.addColorStop(0, hexToRgba(CFG.accentAlt, CFG.ambientGlowBR.opacity));
      g2.addColorStop(1, hexToRgba(CFG.accentAlt, 0));
      ctx.fillStyle = g2;
      ctx.fillRect(0, 0, W, H);
    }

    // ── 2. Grid ─────────────────────────────────────────────

    drawGrid(ctx, W, H) {
      const scrollOff = this.smoothScroll * CFG.gridParallax;
      const mx = this.smooth.x * CFG.gridMouseShift - CFG.gridMouseShift / 2;
      const my = this.smooth.y * CFG.gridMouseShift - CFG.gridMouseShift / 2;

      // Subtle pulse on grid over time
      const pulse = 1 + Math.sin(this.time * 0.0005) * 0.15;

      ctx.save();
      ctx.globalAlpha = pulse;
      ctx.strokeStyle = hexToRgba(CFG.accent, CFG.gridOpacity);
      ctx.lineWidth = 0.4;
      ctx.beginPath();

      // Horizontal lines
      const gx = CFG.gridSpacingX;
      const gy = CFG.gridSpacingY;
      const startY = -(scrollOff % gy) - gy;
      for (let y = startY; y < H + gy; y += gy) {
        // Shift each line slightly toward mouse (stronger near mouse)
        const dy = y - this.smooth.y * H;
        const influence = Math.max(0, 1 - Math.abs(dy) / (H * 0.6));
        const shiftX = mx * influence;
        ctx.moveTo(0 + shiftX, y);
        ctx.lineTo(W + shiftX, y);
      }

      // Vertical lines
      const startX = -(scrollOff * 0.5) % gx - gx;
      for (let x = startX; x < W + gx; x += gx) {
        const dx = x - this.smooth.x * W;
        const influence = Math.max(0, 1 - Math.abs(dx) / (W * 0.6));
        const shiftY = my * influence;
        ctx.moveTo(x, 0 + shiftY);
        ctx.lineTo(x, H + shiftY);
      }

      ctx.stroke();
      ctx.restore();
    }

    // ── 3. Morphing Polygons (multiple instances) ────────────

    drawMorphingPolygons(ctx, W, H) {
      const baseScale = Math.min(W, H);

      this.polyInstances.forEach((inst) => {
        // Advance morph timer
        inst.morphElapsed += 16.67;
        if (inst.morphElapsed >= inst.morphMs) {
          inst.morphElapsed = 0;
          inst.frameIdx = (inst.frameIdx + 1) % inst.sequence.length;
        }
        const t = inst.morphElapsed / inst.morphMs;
        const from = inst.sequence[inst.frameIdx];
        const to = inst.sequence[(inst.frameIdx + 1) % inst.sequence.length];
        const morphed = morphFrame(from, to, t);

        const px = W * inst.vx + (this.smooth.x - 0.5) * 20;
        const py = H * inst.vy + (this.smooth.y - 0.5) * 20 - this.smoothScroll * inst.parallax;
        const scale = baseScale * inst.scale;
        const rotate = (this.smooth.x - 0.5) * 0.12 + (this.smooth.y - 0.5) * 0.08;

        ctx.save();
        ctx.translate(px, py);
        ctx.rotate(rotate);

        const col = inst.accent;

        // Filled polygon
        ctx.strokeStyle = hexToRgba(col, inst.opacity * 1.6);
        ctx.lineWidth = CFG.polygonStrokeWidth;
        ctx.fillStyle = hexToRgba(col, inst.opacity * 0.3);
        ctx.beginPath();
        morphed.forEach(([x, y], i) => {
          const fx = x * scale;
          const fy = y * scale;
          if (i === 0) ctx.moveTo(fx, fy);
          else ctx.lineTo(fx, fy);
        });
        ctx.closePath();
        ctx.fill();
        ctx.stroke();

        // Ghost outer ring
        if (inst.drawGhost) {
          ctx.strokeStyle = hexToRgba(col, inst.opacity * 0.5);
          ctx.lineWidth = 0.25;
          const outerScale = scale * 1.6;
          ctx.beginPath();
          morphed.forEach(([x, y], i) => {
            if (i === 0) ctx.moveTo(x * outerScale, y * outerScale);
            else ctx.lineTo(x * outerScale, y * outerScale);
          });
          ctx.closePath();
          ctx.stroke();
        }

        // Radial lines from center to vertices
        if (inst.drawRays) {
          ctx.strokeStyle = hexToRgba(col, inst.opacity * 0.7);
          ctx.lineWidth = 0.2;
          morphed.forEach(([x, y]) => {
            ctx.beginPath();
            ctx.moveTo(0, 0);
            ctx.lineTo(x * scale, y * scale);
            ctx.stroke();
          });
        }

        ctx.restore();
      });
    }

    // ── 4. Floating Rays ─────────────────────────────────────

    drawRays(ctx, W, H) {
      const dt = 16.67 / 1000; // seconds per frame (approx)
      const mouseOnScreen = this.mouse.x > 0 && this.mouse.y > 0;
      const scrollOff = this.smoothScroll * CFG.rayParallax;

      this.rays.forEach((r) => {
        // Drift
        r.x += r.vx * dt;
        r.y += r.vy * dt - scrollOff * 0.01; // subtle vertical parallax drift

        // Wrap around edges with margin
        const margin = r.length;
        if (r.x > W + margin) { r.x = -margin; r.y = Math.random() * H; }
        if (r.x < -margin) { r.x = W + margin; r.y = Math.random() * H; }
        if (r.y > H + margin) { r.y = -margin; r.x = Math.random() * W; }
        if (r.y < -margin) { r.y = H + margin; r.x = Math.random() * W; }

        const endX = r.x + Math.cos(r.angle) * r.length;
        const endY = r.y + Math.sin(r.angle) * r.length;

        let rayOpacity = r.opacity;
        let rayWidth = r.width;

        // Mouse proximity glow
        if (mouseOnScreen) {
          const midX = (r.x + endX) / 2;
          const midY = (r.y + endY) / 2;
          const d = dist(this.mouse.x, this.mouse.y, midX, midY);
          if (d < CFG.rayMouseReach) {
            const factor = 1 - d / CFG.rayMouseReach;
            rayOpacity = r.opacity + factor * 0.12;
            rayWidth = r.width * (1 + factor * 1.5);
          }
        }

        // Draw ray as a line with subtle glow
        ctx.strokeStyle = hexToRgba(CFG.accent, rayOpacity);
        ctx.lineWidth = rayWidth;
        ctx.beginPath();
        ctx.moveTo(r.x, r.y);
        ctx.lineTo(endX, endY);
        ctx.stroke();

        // Small dot at midpoint
        const midX = (r.x + endX) / 2;
        const midY = (r.y + endY) / 2;
        ctx.fillStyle = hexToRgba(CFG.accent, rayOpacity * 0.8);
        ctx.beginPath();
        ctx.arc(midX, midY, rayWidth * 1.2, 0, Math.PI * 2);
        ctx.fill();
      });
    }

    // ── 5. Orbiting Nodes ───────────────────────────────────

    drawOrbiters(ctx, W, H, D) {
      const mouseOnScreen = this.mouse.x > 0 && this.mouse.y > 0;

      this.orbiters.forEach((o) => {
        // Speed up if mouse is nearby
        let speedMult = 1;
        const screenCY = o.cy - this.smoothScroll * CFG.orbiterParallax;
        if (mouseOnScreen) {
          const d = dist(this.mouse.x, this.mouse.y, o.cx, screenCY);
          if (d < 250) {
            speedMult = 1 + (1 - d / 250) * CFG.orbiterMouseSpeedup;
          }
        }

        const angle = o.phase + this.time * o.speed * speedMult;
        const x = o.cx + Math.cos(angle) * o.rx;
        const y = screenCY + Math.sin(angle) * o.ry;

        // Draw orbit path (faint ellipse)
        ctx.strokeStyle = hexToRgba(CFG.accentAlt, CFG.orbiterOpacity * 0.4);
        ctx.lineWidth = 0.3;
        ctx.beginPath();
        ctx.ellipse(o.cx, screenCY, o.rx, o.ry, 0, 0, Math.PI * 2);
        ctx.stroke();

        // Draw node
        const glowR = mouseOnScreen && dist(this.mouse.x, this.mouse.y, x, y) < 150 ? o.r * 2.5 : o.r;
        const glowOp = mouseOnScreen && dist(this.mouse.x, this.mouse.y, x, y) < 150
          ? CFG.orbiterOpacity * 2.5
          : CFG.orbiterOpacity;

        ctx.fillStyle = hexToRgba(CFG.accentAlt, glowOp);
        ctx.beginPath();
        ctx.arc(x, y, glowR, 0, Math.PI * 2);
        ctx.fill();
      });
    }

    // ── 5. Constellation Particles ──────────────────────────

    drawConstellation(ctx, W, H, D) {
      const mouseOnScreen = this.mouse.x > 0 && this.mouse.y > 0;
      const scrollOff = this.smoothScroll * CFG.particleParallax;

      // Update and draw particles
      const positions = this.particles.map((p) => {
        const driftX = Math.cos(this.time * CFG.particleDriftSpeed + p.phase) * p.driftRx;
        const driftY = Math.sin(this.time * CFG.particleDriftSpeed * 1.3 + p.phase) * p.driftRy;
        let x = p.bx + driftX;
        let y = p.by + driftY - scrollOff;

        // Wrap if off-screen vertically (since doc height can be large)
        const viewY = y + scrollOff; // actual document position
        // Clamp to viewport (particles re-enter from other side)
        if (y < -50) y += D + 100;
        if (y > H + 50) y -= D + 100;

        // Mouse pull
        if (mouseOnScreen) {
          const d = dist(this.mouse.x, this.mouse.y, x, y);
          if (d < CFG.particleMouseReach) {
            const pull = (1 - d / CFG.particleMouseReach) * CFG.particleMousePull;
            x = lerp(x, this.mouse.x, pull);
            y = lerp(y, this.mouse.y, pull);
          }
        }

        return { x, y, p };
      });

      // Draw connections between nearby particles
      ctx.strokeStyle = hexToRgba(CFG.accent, CFG.particleConnectionOpacity);
      ctx.lineWidth = 0.3;
      for (let i = 0; i < positions.length; i++) {
        for (let j = i + 1; j < positions.length; j++) {
          const d = dist(positions[i].x, positions[i].y, positions[j].x, positions[j].y);
          if (d < CFG.particleConnectionDist) {
            const alpha = (1 - d / CFG.particleConnectionDist) * CFG.particleConnectionOpacity;
            ctx.strokeStyle = hexToRgba(CFG.accent, alpha);
            ctx.beginPath();
            ctx.moveTo(positions[i].x, positions[i].y);
            ctx.lineTo(positions[j].x, positions[j].y);
            ctx.stroke();
          }
        }
      }

      // Draw particles
      positions.forEach(({ x, y, p }) => {
        let glow = CFG.particleOpacity;
        let radius = p.r;

        if (mouseOnScreen) {
          const d = dist(this.mouse.x, this.mouse.y, x, y);
          if (d < CFG.particleMouseReach) {
            const factor = 1 - d / CFG.particleMouseReach;
            glow = CFG.particleOpacity + factor * 0.35;
            radius = p.r * (1 + factor * 1.8);
          }
        }

        // Outer glow
        ctx.fillStyle = hexToRgba(CFG.accent, glow * 0.3);
        ctx.beginPath();
        ctx.arc(x, y, radius * 3, 0, Math.PI * 2);
        ctx.fill();

        // Core
        ctx.fillStyle = hexToRgba(CFG.accent, glow);
        ctx.beginPath();
        ctx.arc(x, y, radius, 0, Math.PI * 2);
        ctx.fill();
      });
    }

    // ── 6. Mouse Glow ───────────────────────────────────────

    drawMouseGlow(ctx, W, H) {
      if (this.mouse.x < 0 || this.mouse.y < 0) return;

      const g = ctx.createRadialGradient(
        this.mouse.x, this.mouse.y, 0,
        this.mouse.x, this.mouse.y, CFG.mouseGlowRadius
      );
      g.addColorStop(0, hexToRgba(CFG.accent, CFG.mouseGlowOpacity));
      g.addColorStop(CFG.mouseGlowFeather, hexToRgba(CFG.accent, CFG.mouseGlowOpacity * 0.3));
      g.addColorStop(1, hexToRgba(CFG.accent, 0));
      ctx.fillStyle = g;
      ctx.fillRect(0, 0, W, H);
    }
  }

  // ═══════════════════════════════════════════════════════════════
  // HELPERS
  // ═══════════════════════════════════════════════════════════════

  function hexToRgba(hex, alpha) {
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    return `rgba(${r},${g},${b},${alpha})`;
  }

  // ═══════════════════════════════════════════════════════════════
  // AUTO-INIT
  // ═══════════════════════════════════════════════════════════════

  const scriptTag = document.currentScript;
  // Don't re-init if already running
  if (window.__geoBgInstance) return;

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
      window.__geoBgInstance = new GeometryBackground();
    });
  } else {
    window.__geoBgInstance = new GeometryBackground();
  }

  // Expose for programmatic use
  window.GeometryBackground = GeometryBackground;
})();
