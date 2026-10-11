/** Small geocoding helper: Delhi-NCR localities -> coordinates.

A real deployment uses Amazon Location Service Places; this offline-friendly
table keeps the app usable without credentials and is explicit about being
an offline list.
 */

export interface Place {
  name: string;
  lat: number;
  lon: number;
}

const PLACES: Place[] = [
  { name: "Rohini", lat: 28.7146, lon: 77.1025 },
  { name: "Karol Bagh", lat: 28.6519, lon: 77.1909 },
  { name: "Lajpat Nagar", lat: 28.5677, lon: 77.2433 },
  { name: "Dwarka", lat: 28.5921, lon: 77.046 },
  { name: "Noida Sector 62", lat: 28.6271, lon: 77.3712 },
  { name: "Gurugram Sector 29", lat: 28.4595, lon: 77.0266 },
  { name: "Connaught Place", lat: 28.6315, lon: 77.2167 },
  { name: "Mayur Vihar", lat: 28.6069, lon: 77.2939 },
  { name: "Saket", lat: 28.5245, lon: 77.2065 },
  { name: "Pitampura", lat: 28.6975, lon: 77.1312 },
  { name: "Ghaziabad", lat: 28.6692, lon: 77.4538 },
  { name: "Faridabad", lat: 28.4089, lon: 77.3178 },
  { name: "Najafgarh", lat: 28.6093, lon: 76.9854 },
  { name: "Shahdara", lat: 28.6738, lon: 77.2897 },
  { name: "Preet Vihar", lat: 28.6366, lon: 77.2954 },
  { name: "Vasant Kunj", lat: 28.5203, lon: 77.1562 },
];

export function searchPlaces(query: string, limit = 5): Place[] {
  const q = query.trim().toLowerCase();
  if (!q) return [];
  return PLACES.filter((p) => p.name.toLowerCase().includes(q)).slice(0, limit);
}

export function allPlaces(): Place[] {
  return [...PLACES];
}
