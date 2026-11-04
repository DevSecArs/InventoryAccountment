const paths = {
  overview: 'M3 13a9 9 0 1 1 18 0v5H3z M12 13l4-4 M12 13v.01',
  units: 'M4 4h16v16H4z M8 4v4 M12 4v4 M16 4v4',
  materials: 'M12 2 3 7v10l9 5 9-5V7z M3 7l9 5 9-5 M12 12v10',
  suppliers: 'M3 5h11v12H3z M14 9h4l3 3v5h-7z M7 17a2 2 0 1 0 0 4 2 2 0 0 0 0-4 M18 17a2 2 0 1 0 0 4 2 2 0 0 0 0-4',
  receipts: 'M8 4H5v17h14V4h-3 M8 2h8v4H8z M8 11h8 M8 15h8',
  reports: 'M4 20h16 M6 17v-5 M10 17V8 M14 17v-3 M18 17V4',
  admin: 'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8z M12 2v3 M12 19v3 M2 12h3 M19 12h3 M5 5l2 2 M17 17l2 2 M19 5l-2 2 M7 17l-2 2',
  user: 'M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8 M4 21a8 8 0 0 1 16 0',
  menu: 'M3 6h18 M3 12h18 M3 18h18',
  close: 'M5 5l14 14 M19 5 5 19',
  edit: 'M4 20h4L19 9l-4-4L4 16z M13 7l4 4',
  archive: 'M3 4h18v4H3z M5 8v12h14V8 M9 12h6',
  delete: 'M4 7h16 M10 3h4 M6 7l1 13h10l1-13 M10 11v5 M14 11v5',
};

export function icon(name, size = 19) {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('viewBox', '0 0 24 24');
  svg.setAttribute('width', String(size)); svg.setAttribute('height', String(size));
  svg.setAttribute('fill', 'none'); svg.setAttribute('stroke', 'currentColor');
  svg.setAttribute('stroke-width', '2'); svg.setAttribute('stroke-linecap', 'round'); svg.setAttribute('stroke-linejoin', 'round');
  svg.setAttribute('aria-hidden', 'true');
  const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  path.setAttribute('d', paths[name]); svg.append(path); return svg;
}
