/**
 * Layout de la COMANDERA — app dels cambrers (PWA mòbil).
 * El shell d'escriptori (sidebar) es desactiva a AppShell per la ruta /comandera.
 */
export default function ComanderaLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen" style={{ background: '#0f1729' }}>
      {children}
    </div>
  );
}