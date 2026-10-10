import React, { useEffect, useState } from 'react';
import logoUrl from '../../../logo.png';

export function StartupIntro() {
  const [visible, setVisible] = useState(true);
  useEffect(() => {
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const timer = window.setTimeout(() => setVisible(false), reduced ? 260 : 720);
    return () => window.clearTimeout(timer);
  }, []);
  if (!visible) return null;
  return <div className="lara-startup" aria-hidden="true"><img src={logoUrl} alt="" /></div>;
}
