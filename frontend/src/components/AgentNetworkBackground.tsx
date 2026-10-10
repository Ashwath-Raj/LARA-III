import React, { useEffect, useRef } from 'react';

type Point = { x: number; y: number; phase: number; radius: number };

export const AgentNetworkBackground: React.FC = () => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const pointerRef = useRef({ x: -1000, y: -1000 });

  useEffect(() => {
    const canvas = canvasRef.current;
    const parent = canvas?.parentElement;
    const context = canvas?.getContext('2d');
    if (!canvas || !parent || !context) return;

    const media = window.matchMedia('(prefers-reduced-motion: reduce)');
    let width = 0;
    let height = 0;
    let frame = 0;
    let lastPaint = 0;
    let isVisible = !document.hidden;
    let points: Point[] = [];

    const resize = () => {
      const rect = parent.getBoundingClientRect();
      const dpr = Math.min(window.devicePixelRatio || 1, 1.5);
      width = rect.width;
      height = rect.height;
      canvas.width = Math.max(1, Math.round(width * dpr));
      canvas.height = Math.max(1, Math.round(height * dpr));
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
      context.setTransform(dpr, 0, 0, dpr, 0, 0);
      const count = Math.max(18, Math.min(38, Math.round(width / 29)));
      points = Array.from({ length: count }, (_, index) => ({
        x: ((index * 0.61803398875 + 0.13) % 1) * width,
        y: ((index * 0.7548776662 + 0.17) % 1) * height,
        phase: index * 1.71,
        radius: 1.2 + (index % 3) * 0.35,
      }));
      paint(media.matches ? 0 : performance.now());
    };

    const paint = (time: number) => {
      if (!width || !height) return;
      context.clearRect(0, 0, width, height);
      const positions = points.map((point) => {
        const drift = media.matches ? 0 : 2.4;
        let x = point.x + Math.sin(time * 0.00013 + point.phase) * drift;
        let y = point.y + Math.cos(time * 0.00011 + point.phase * 0.7) * drift;
        const dx = pointerRef.current.x - x;
        const dy = pointerRef.current.y - y;
        const distance = Math.hypot(dx, dy);
        if (!media.matches && distance < 170) {
          const pull = (1 - distance / 170) * 5;
          x += (dx / (distance || 1)) * pull;
          y += (dy / (distance || 1)) * pull;
        }
        return { x, y, radius: point.radius };
      });

      for (let from = 0; from < positions.length; from += 1) {
        for (let to = from + 1; to < positions.length; to += 1) {
          const a = positions[from];
          const b = positions[to];
          const distance = Math.hypot(a.x - b.x, a.y - b.y);
          if (distance > 116) continue;
          const middleY = (a.y + b.y) / 2;
          const textQuieting = middleY > height * 0.28 && middleY < height * 0.72 ? 0.55 : 1;
          context.strokeStyle = `rgba(73, 110, 107, ${(1 - distance / 116) * 0.095 * textQuieting})`;
          context.lineWidth = 0.7;
          context.beginPath();
          context.moveTo(a.x, a.y);
          context.lineTo(b.x, b.y);
          context.stroke();
        }
      }

      positions.forEach(({ x, y, radius }) => {
        const quieting = y > height * 0.28 && y < height * 0.72 ? 0.65 : 1;
        context.fillStyle = `rgba(73, 110, 107, ${0.16 * quieting})`;
        context.beginPath();
        context.arc(x, y, radius, 0, Math.PI * 2);
        context.fill();
      });
    };

    const animate = (time: number) => {
      if (!isVisible || media.matches) return;
      if (time - lastPaint >= 33) {
        paint(time);
        lastPaint = time;
      }
      frame = window.requestAnimationFrame(animate);
    };
    const start = () => {
      window.cancelAnimationFrame(frame);
      if (media.matches) paint(0);
      else if (isVisible) frame = window.requestAnimationFrame(animate);
    };
    const onPointerMove = (event: PointerEvent) => {
      if (event.pointerType !== 'mouse' || media.matches) return;
      const rect = parent.getBoundingClientRect();
      pointerRef.current.x = event.clientX - rect.left;
      pointerRef.current.y = event.clientY - rect.top;
    };
    const onPointerLeave = () => { pointerRef.current = { x: -1000, y: -1000 }; };
    const onVisibility = () => {
      isVisible = !document.hidden;
      if (!isVisible) window.cancelAnimationFrame(frame);
      else start();
    };

    const observer = new ResizeObserver(resize);
    observer.observe(parent);
    window.addEventListener('pointermove', onPointerMove, { passive: true });
    parent.addEventListener('pointerleave', onPointerLeave);
    document.addEventListener('visibilitychange', onVisibility);
    media.addEventListener('change', start);
    resize();
    start();

    return () => {
      observer.disconnect();
      window.removeEventListener('pointermove', onPointerMove);
      parent.removeEventListener('pointerleave', onPointerLeave);
      document.removeEventListener('visibilitychange', onVisibility);
      media.removeEventListener('change', start);
      window.cancelAnimationFrame(frame);
    };
  }, []);

  return <canvas className="agent-network-background" ref={canvasRef} aria-hidden="true" />;
};
