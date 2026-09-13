'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { api, getStoredStaff } from '@/lib/api';
import { LogOut } from 'lucide-react';

export default function LogoutLink() {
  const router = useRouter();
  const [staff, setStaff] = useState<{ name?: string } | null>(null);

  useEffect(() => { setStaff(getStoredStaff()); }, []);

  if (!staff) return null; // sense sessió no es mostra

  const out = async () => {
    await api.logoutServer();
    router.replace('/login');
  };

  return (
    <button onClick={out}
      className="flex items-center gap-2 w-full p-3 rounded-lg hover:bg-red-500/10 text-gray-300 hover:text-red-300 text-sm transition-colors">
      <LogOut size={16} />
      <span>Sortir{staff.name ? ` (${staff.name})` : ''}</span>
    </button>
  );
}
