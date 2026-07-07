export type StickerPreset = {
  id: string;
  label: string;
  imageUrl: string;
  category: string;
};

// Inline SVGs encoded as data URIs
const svgToDataUri = (svgString: string) => {
  // Ensure the SVG has explicit dimensions for WebGL texture loading
  const withDimensions = svgString.replace('<svg ', '<svg width="512" height="512" ');
  return `data:image/svg+xml;utf8,${encodeURIComponent(withDimensions)}`;
};

export const stickerPresets: StickerPreset[] = [
  {
    id: "preset_razor_flame",
    label: "Razor Flame",
    category: "popular",
    imageUrl: svgToDataUri(`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><path d="M31 5c2 13 17 18 17 35 0 12-8 20-19 20C17 60 8 51 8 39c0-8 4-14 10-20-1 8 3 14 10 16-5-10-3-21 3-30z" fill="#0f172a"/><path d="M35 11c4 10 17 16 17 29 0 14-10 23-23 23C15 63 5 53 5 40c0-10 6-17 13-25-.5 8 2 15 9 19-4-10-2-19 8-23z" fill="none" stroke="#f8fafc" stroke-width="4" stroke-linejoin="round"/><path d="M31 20c6 8 11 13 11 22 0 7-5 12-12 12-8 0-13-5-13-13 0-4 2-8 5-12 1 5 4 8 9 9-2-6-2-12 0-18z" fill="#ef233c"/><path d="M38 16l-8 23 15-4-13 18" fill="none" stroke="#facc15" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/></svg>`)
  },
  {
    id: "preset_chrome_star",
    label: "Chrome Star",
    category: "popular",
    imageUrl: svgToDataUri(`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><polygon points="32 3 39 24 61 24 43 36 50 58 32 45 14 58 21 36 3 24 25 24" fill="#111827" stroke="#f8fafc" stroke-width="4" stroke-linejoin="round"/><polygon points="32 12 36 27 52 28 39 36 44 50 32 41 20 50 25 36 12 28 28 27" fill="#d1d5db"/><path d="M20 50L52 28M12 28h40" stroke="#ef233c" stroke-width="3" stroke-linecap="round"/></svg>`)
  },
  {
    id: "preset_noir_script",
    label: "Noir Script",
    category: "type",
    imageUrl: svgToDataUri(`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><path d="M8 46c13-19 25-29 38-29 7 0 10 4 10 8 0 9-17 11-28 11 8 7 18 9 29 7" fill="none" stroke="#111827" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/><path d="M8 46c13-19 25-29 38-29 7 0 10 4 10 8 0 9-17 11-28 11 8 7 18 9 29 7" fill="none" stroke="#f8fafc" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/><text x="9" y="38" fill="#ef233c" font-family="Brush Script MT, Segoe Script, cursive" font-size="22" font-weight="700" transform="rotate(-8 9 38)">Noir</text></svg>`)
  },
  {
    id: "preset_racing_13",
    label: "Racing 13",
    category: "racing",
    imageUrl: svgToDataUri(`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><path d="M9 13h46l-4 34-19 12-19-12z" fill="#111827" stroke="#f8fafc" stroke-width="4" stroke-linejoin="round"/><path d="M14 17h36l-3 26-15 9-15-9z" fill="#ef233c"/><path d="M18 45l27-29h8L26 45z" fill="#f8fafc" opacity=".9"/><text x="31" y="42" fill="#111827" font-family="Impact, Arial Black, sans-serif" font-size="27" font-weight="900" text-anchor="middle" transform="skewX(-8)">13</text></svg>`)
  },
  {
    id: "preset_warning_label",
    label: "Warning Label",
    category: "street",
    imageUrl: svgToDataUri(`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><path d="M7 19h50v26H7z" fill="#facc15" stroke="#111827" stroke-width="4" stroke-linejoin="round"/><path d="M7 19l50 26M57 19L7 45" stroke="#111827" stroke-width="5" opacity=".18"/><path d="M14 25h36M14 39h36" stroke="#111827" stroke-width="3"/><text x="32" y="37" fill="#111827" font-family="Impact, Arial Black, sans-serif" font-size="17" font-weight="900" text-anchor="middle">RAW</text></svg>`)
  },
  {
    id: "preset_barbed_wire",
    label: "Barbed Wire",
    category: "street",
    imageUrl: svgToDataUri(`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><path d="M5 34c11-10 22-10 33 0 7 6 14 6 21 0" fill="none" stroke="#111827" stroke-width="5" stroke-linecap="round"/><path d="M5 29c11 10 22 10 33 0 7-6 14-6 21 0" fill="none" stroke="#f8fafc" stroke-width="2" stroke-linecap="round"/><path d="M16 22l5 17M25 24l-13 13M40 24l5 17M49 25L36 39" stroke="#ef233c" stroke-width="4" stroke-linecap="round"/></svg>`)
  },
  {
    id: "preset_skull_mark",
    label: "Skull Mark",
    category: "marks",
    imageUrl: svgToDataUri(`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><path d="M17 28c0-13 8-22 15-22s15 9 15 22c0 9-4 15-10 18v8H27v-8c-6-3-10-9-10-18z" fill="#111827" stroke="#f8fafc" stroke-width="4" stroke-linejoin="round"/><path d="M24 30l7 5-8 3zM40 30l-7 5 8 3z" fill="#f8fafc"/><path d="M29 45h2M34 45h2M31 51v-6M36 51v-6" stroke="#f8fafc" stroke-width="3" stroke-linecap="round"/><path d="M13 53l38-38" stroke="#ef233c" stroke-width="5" stroke-linecap="round"/></svg>`)
  },
  {
    id: "preset_graffiti_drip",
    label: "Graffiti Drip",
    category: "type",
    imageUrl: svgToDataUri(`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><text x="31" y="36" fill="#111827" stroke="#f8fafc" stroke-width="5" font-family="Impact, Arial Black, sans-serif" font-size="24" font-weight="900" text-anchor="middle" transform="rotate(-8 31 36)">DRIP</text><text x="31" y="36" fill="#ef233c" font-family="Impact, Arial Black, sans-serif" font-size="24" font-weight="900" text-anchor="middle" transform="rotate(-8 31 36)">DRIP</text><path d="M20 41v8M31 40v12M45 39v7" stroke="#111827" stroke-width="4" stroke-linecap="round"/></svg>`)
  },
  {
    id: "preset_checker_patch",
    label: "Checker Patch",
    category: "racing",
    imageUrl: svgToDataUri(`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><path d="M11 13h42v38H11z" fill="#f8fafc" stroke="#111827" stroke-width="4"/><path d="M11 13h14v13H11zM39 13h14v13H39zM25 26h14v13H25zM11 39h14v12H11zM39 39h14v12H39z" fill="#111827"/><path d="M8 52l48-38" stroke="#ef233c" stroke-width="5" stroke-linecap="round"/></svg>`)
  },
  {
    id: "preset_cyber_eye",
    label: "Cyber Eye",
    category: "marks",
    imageUrl: svgToDataUri(`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><path d="M5 33l14-16h26l14 16-14 15H19z" fill="#111827" stroke="#f8fafc" stroke-width="4" stroke-linejoin="round"/><circle cx="32" cy="33" r="11" fill="#ef233c"/><circle cx="32" cy="33" r="5" fill="#111827"/><path d="M17 33h-9M56 33h-9M32 18V8M32 58V48" stroke="#facc15" stroke-width="4" stroke-linecap="round"/></svg>`)
  },
  {
    id: "preset_hard_crown",
    label: "Hard Crown",
    category: "street",
    imageUrl: svgToDataUri(`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><path d="M9 46l5-27 13 15 5-23 7 23 12-15 4 27z" fill="#111827" stroke="#f8fafc" stroke-width="4" stroke-linejoin="round"/><path d="M14 46h41v9H14z" fill="#ef233c" stroke="#111827" stroke-width="4"/><path d="M20 45l29-24" stroke="#facc15" stroke-width="4" stroke-linecap="round"/></svg>`)
  },
  {
    id: "preset_tribal_swoosh",
    label: "Tribal Swoosh",
    category: "marks",
    imageUrl: svgToDataUri(`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><path d="M6 40c18-2 31-13 47-31-3 14-9 25-20 34l18-3c-10 9-23 14-40 15 7-4 12-9 15-15z" fill="#111827" stroke="#f8fafc" stroke-width="4" stroke-linejoin="round"/><path d="M15 45c14-5 25-14 35-29" fill="none" stroke="#ef233c" stroke-width="4" stroke-linecap="round"/><path d="M35 43l16-3" stroke="#facc15" stroke-width="4" stroke-linecap="round"/></svg>`)
  }
];
