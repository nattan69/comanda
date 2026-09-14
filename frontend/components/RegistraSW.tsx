'use client';

import { useEffect } from 'react';

/**
 * Registra el service worker de la PWA de la Comandera.
 * Només s'activa a la ruta /comandera (l'app dels cambrers), no al TPV d'escriptori.
 */
export default function RegistraSW() {
  useEffect(() => {
    if (typeof navigator === 'undefined' || !('serviceWorker' in navigator)) return;
    if (!window.location.pathname.startsWith('/comandera')) return;
    const id = setTimeout(() => {
      navigator.serviceWorker.register('/sw.js').catch(() => { /* PWA opcional */ });
    }, 1200);
    return () => clearTimeout(id);
  }, []);
  return null;
}