export const translations = {
  ca: {
    nav: {
      sala: 'Sala',
      comandes: 'Comandes',
      tancament: 'Tancament del dia',
      carta: 'Carta',
    },
    sala: {
      title: 'Pla de Sala',
      area_terraza: 'Terrassa',
      area_interior: 'Interior',
      area_barra: 'Barra',
      status_free: 'Lliure',
      status_occupied: 'Ocupada',
    },
    comandes: {
      title: 'Presa de Comandes',
      select_table: 'Selecciona Taula',
      menu: 'Carta',
      add: 'Afegir',
      total: 'Total',
      confirm: 'Confirmar Comanda',
    },
  },
  es: {
    nav: {
      sala: 'Sala',
      comandes: 'Comandas',
      tancament: 'Cierre del día',
      carta: 'Carta',
    },
    sala: {
      title: 'Plano de Sala',
      area_terraza: 'Terraza',
      area_interior: 'Interior',
      area_barra: 'Barra',
      status_free: 'Libre',
      status_occupied: 'Ocupada',
    },
    comandes: {
      title: 'Toma de Comandas',
      select_table: 'Selecciona Mesa',
      menu: 'Carta',
      add: 'Añadir',
      total: 'Total',
      confirm: 'Confirmar Comanda',
    },
  },
  en: {
    nav: {
      sala: 'Floor Plan',
      comandes: 'Orders',
      tancament: 'Day Closure',
      carta: 'Menu',
    },
    sala: {
      title: 'Floor Plan',
      area_terraza: 'Terrace',
      area_interior: 'Interior',
      area_barra: 'Bar',
      status_free: 'Free',
      status_occupied: 'Occupied',
    },
    comandes: {
      title: 'Taking Orders',
      select_table: 'Select Table',
      menu: 'Menu',
      add: 'Add',
      total: 'Total',
      confirm: 'Confirm Order',
    },
  },
};

export type Lang = 'ca' | 'es' | 'en';

export function getT(lang: Lang = 'ca') {
  return translations[lang];
}
