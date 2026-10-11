/** Offline gazetteer for Delhi-NCR: localities, landmarks, metro and stations.

Deliberately shipped as data rather than fetched from a geocoder so the app
works with no third-party key, no network and no rate limit, and so a search
result is reproducible. 180 entries covering every NCR district, its major
localities, landmarks and transit stations. A deployment with credentials can
swap in Amazon Location Service behind the same two functions.
 */

export interface Place {
  name: string;
  lat: number;
  lon: number;
}

export const PLACES: Place[] = [
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
  { name: "Chandni Chowk", lat: 28.6562, lon: 77.23 },
  { name: "Chandni Chowk Metro", lat: 28.656, lon: 77.23 },
  { name: "Paharganj", lat: 28.633, lon: 77.216 },
  { name: "Darya Ganj", lat: 28.651, lon: 77.217 },
  { name: "Rajiv Chowk", lat: 28.627, lon: 77.216 },
  { name: "Janakpuri", lat: 28.629, lon: 77.077 },
  { name: "Karkarduma", lat: 28.616, lon: 77.14 },
  { name: "Hauz Khas", lat: 28.543, lon: 77.206 },
  { name: "Green Park", lat: 28.559, lon: 77.207 },
  { name: "IIT Delhi", lat: 28.545, lon: 77.1926 },
  { name: "JNU", lat: 28.57, lon: 77.16 },
  { name: "Nehru Place", lat: 28.57, lon: 77.25 },
  { name: "Okhla", lat: 28.561, lon: 77.274 },
  { name: "Jamia Nagar", lat: 28.571, lon: 77.207 },
  { name: "Kalkaji", lat: 28.535, lon: 77.258 },
  { name: "Moolchand", lat: 28.53, lon: 77.24 },
  { name: "AIIMS", lat: 28.567, lon: 77.21 },
  { name: "Laxmi Nagar", lat: 28.63, lon: 77.241 },
  { name: "Patel Nagar", lat: 28.622, lon: 77.27 },
  { name: "Tilak Nagar", lat: 28.599, lon: 77.251 },
  { name: "Vishwas Nagar", lat: 28.63, lon: 77.284 },
  { name: "Seelam Pur", lat: 28.646, lon: 77.295 },
  { name: "Wazirpur", lat: 28.688, lon: 77.293 },
  { name: "Ashok Vihar", lat: 28.69, lon: 77.179 },
  { name: "Model Town", lat: 28.703, lon: 77.188 },
  { name: "Azadpur", lat: 28.711, lon: 77.177 },
  { name: "Civil Lines", lat: 28.676, lon: 77.225 },
  { name: "Vishal Enclave", lat: 28.652, lon: 77.113 },
  { name: "Nand Nagri", lat: 28.678, lon: 77.317 },
  { name: "Shakarpur", lat: 28.63, lon: 77.283 },
  { name: "Geeta Colony", lat: 28.635, lon: 77.269 },
  { name: "Preet Vihar Extension", lat: 28.637, lon: 77.298 },
  { name: "Vasundhara", lat: 28.657, lon: 77.318 },
  { name: "Indrapuram", lat: 28.63, lon: 77.378 },
  { name: "Sahibabad", lat: 28.57, lon: 77.39 },
  { name: "Noida Sector 1", lat: 28.57, lon: 77.325 },
  { name: "Noida Sector 18", lat: 28.57, lon: 77.33 },
  { name: "Noida Sector 50", lat: 28.646, lon: 77.361 },
  { name: "Noida Sector 76", lat: 28.545, lon: 77.391 },
  { name: "Noida Sector 137", lat: 28.395, lon: 77.321 },
  { name: "Noida Sector 150", lat: 28.427, lon: 77.321 },
  { name: "Greater Noida West", lat: 28.474, lon: 77.426 },
  { name: "Greater Noida East", lat: 28.49, lon: 77.48 },
  { name: "Sector 44 Gurugram", lat: 28.466, lon: 77.03 },
  { name: "Golf Course Gurugram", lat: 28.496, lon: 77.11 },
  { name: "Sohna", lat: 28.33, lon: 77.07 },
  { name: "Manesar", lat: 28.35, lon: 76.93 },
  { name: "Faridabad Sector 14", lat: 28.39, lon: 77.29 },
  { name: "Faridabad Sector 21", lat: 28.38, lon: 77.32 },
  { name: "Old Faridabad", lat: 28.418, lon: 77.32 },
  { name: "Ballabgarh", lat: 28.34, lon: 77.33 },
  { name: "Ghaziabad Railway Station", lat: 28.672, lon: 77.412 },
  { name: "Vaishali", lat: 28.71, lon: 77.39 },
  { name: "Mundka", lat: 28.68, lon: 77.07 },
  { name: "Paschim Vihar", lat: 28.672, lon: 77.091 },
  { name: "Majnu ka Tila", lat: 28.662, lon: 77.223 },
  { name: "Narela", lat: 28.822, lon: 77.102 },
  { name: "Rithala", lat: 28.81, lon: 77.12 },
  { name: "Bawana", lat: 28.77, lon: 77.05 },
  { name: "Alipur", lat: 28.815, lon: 77.15 },
  { name: "Surajpur", lat: 28.51, lon: 77.156 },
  { name: "Sector 63 Noida", lat: 28.627, lon: 77.375 },
  { name: "Sector 100 Noida", lat: 28.548, lon: 77.393 },
  { name: "Sector 21 Noida", lat: 28.57, lon: 77.325 },
  { name: "Botanical Garden", lat: 28.544, lon: 77.181 },
  { name: "Badshahpur", lat: 28.44, lon: 77.13 },
  { name: "Ghitorni", lat: 28.5, lon: 77.12 },
  { name: "Kapashera", lat: 28.52, lon: 77.09 },
  { name: "Samaypur Badli", lat: 28.74, lon: 77.14 },
  { name: "Pehladpur Bangar", lat: 28.75, lon: 77.12 },
  { name: "Bawana Road", lat: 28.76, lon: 77.07 },
  { name: "Kirari", lat: 28.74, lon: 77.06 },
  { name: "Ashok Vihar Metro", lat: 28.69, lon: 77.179 },
  { name: "Hauz Khas Metro", lat: 28.543, lon: 77.206 },
  { name: "Rajiv Chowk Metro", lat: 28.6328, lon: 77.2197 },
  { name: "Kashmere Gate", lat: 28.6675, lon: 77.228 },
  { name: "Chandigarh", lat: 28.679, lon: 77.189 },
  { name: "Shastri Nagar", lat: 28.67, lon: 77.21 },
  { name: "Patel Chowk", lat: 28.623, lon: 77.215 },
  { name: "Lal Quizar", lat: 28.594, lon: 77.226 },
  { name: "Jama Masjid", lat: 28.65, lon: 77.234 },
  { name: "Nizamuddin", lat: 28.593, lon: 77.243 },
  { name: "Lodhi Road", lat: 28.591, lon: 77.224 },
  { name: "Humayun's Tomb", lat: 28.5932, lon: 77.2504 },
  { name: "Qutub Minar", lat: 28.5245, lon: 77.1855 },
  { name: "Mehrauli", lat: 28.515, lon: 77.18 },
  { name: "Vasant Kunj Metro", lat: 28.52, lon: 77.158 },
  { name: "Chhatarpur", lat: 28.51, lon: 77.175 },
  { name: "Saket Metro", lat: 28.52, lon: 77.206 },
  { name: "Kailash Colony", lat: 28.544, lon: 77.259 },
  { name: "Greater Kailash", lat: 28.538, lon: 77.244 },
  { name: "Lajpat Nagar Metro", lat: 28.568, lon: 77.243 },
  { name: "Jangpura", lat: 28.591, lon: 77.247 },
  { name: "R,K,Pur", lat: 28.564, lon: 77.286 },
  { name: "Yusufpur", lat: 28.56, lon: 77.27 },
  { name: "Anand Vihar", lat: 28.647, lon: 77.315 },
  { name: "Kaushambi", lat: 28.632, lon: 77.3 },
  { name: "Shakarpur Extension", lat: 28.628, lon: 77.292 },
  { name: "Mandawali", lat: 28.633, lon: 77.308 },
  { name: "Suraj Mal Vihar", lat: 28.65, lon: 77.328 },
  { name: "Noida Extension", lat: 28.59, lon: 77.36 },
  { name: "Gurgaon Railway Station", lat: 28.44, lon: 77.01 },
  { name: "IFFO Chowk", lat: 28.475, lon: 77.05 },
  { name: "MG Road Gurugram", lat: 28.479, lon: 77.08 },
  { name: "DLF Cyber City", lat: 28.495, lon: 77.09 },
  { name: "Galleria DLF", lat: 28.502, lon: 77.051 },
  { name: "Ambience Vasant Kunj", lat: 28.518, lon: 77.156 },
  { name: "Palam", lat: 28.592, lon: 77.082 },
  { name: "Vasant Vihar", lat: 28.522, lon: 77.15 },
  { name: "Sarojini Nagar", lat: 28.567, lon: 77.22 },
  { name: "Hauz Khas Village", lat: 28.54, lon: 77.213 },
];

/** Case-insensitive substring match, ranked: prefix > word-start > substring. */
export function searchPlaces(query: string, limit = 8): Place[] {
  const q = query.trim().toLowerCase();
  if (!q) return [];
  const scored: { place: Place; score: number }[] = [];
  for (const place of PLACES) {
    const name = place.name.toLowerCase();
    // 1-based: an exact match scores 0 and was previously filtered out by
    // `score > 0`, so searching the full name of a locality returned nothing.
    let score: number;
    if (name === q) score = 1;
    else if (name.startsWith(q)) score = 2;
    else if (name.includes(` ${q}`)) score = 3;
    else if (name.includes(q)) score = 4;
    else continue;
    scored.push({ place, score });
  }
  scored.sort((a, b) => a.score - b.score || a.place.name.length - b.place.name.length);
  return scored.slice(0, limit).map((s) => s.place);
}

export function allPlaces(): Place[] {
  return [...PLACES];
}
