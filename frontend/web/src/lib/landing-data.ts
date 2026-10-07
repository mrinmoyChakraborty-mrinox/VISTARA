export const DESK_SPOTS = [
  [190, 130, "center of desk", "10:41"],
  [130, 95, "beside laptop", "10:43"],
  [290, 105, "right side", "10:47"],
] as const;

export const HERO_NAMES = [
  "Waiting for change",
  "Analyzing event",
  "Memory saved",
] as const;

export type MarqueeItem = {
  icon: string;
  name: string;
  time: string;
  color: string;
};

export const MARQUEE_ITEMS: MarqueeItem[] = [
  { icon: "📟", name: "ESP32", time: "10:43", color: "#80AEE8" },
  { icon: "📱", name: "Phone", time: "10:47", color: "#5B0015" },
  { icon: "🔑", name: "Keys", time: "09:12", color: "#e0a93b" },
  { icon: "🎒", name: "Backpack", time: "19:14", color: "#A5BCD6" },
  { icon: "💻", name: "Laptop", time: "10:30", color: "#80AEE8" },
  { icon: "🔧", name: "Soldering iron", time: "11:02", color: "#c4572f" },
  { icon: "🎧", name: "Headphones", time: "08:55", color: "#5B0015" },
  { icon: "☕", name: "Mug", time: "10:05", color: "#e0a93b" },
  { icon: "📷", name: "Camera", time: "12:20", color: "#A5BCD6" },
  { icon: "🔋", name: "Power bank", time: "13:41", color: "#4caf7a" },
];

export type Step = { title: string; body: string };

export const STEPS: Step[] = [
  { title: "Watch", body: "A camera feed sampled at a low frame rate, right in your browser." },
  { title: "Notice", body: "A cheap local check compares frames. No change means no AI call." },
  { title: "Remember", body: "When something moves, a few frames become one saved memory with evidence." },
  { title: "Ask", body: "Ask in plain words. Vistara looks up memories and answers with the frame." },
];

export type RewindQuestion = { q: string; a: string; frame: string };

export const REWIND_QUESTIONS: RewindQuestion[] = [
  {
    q: "Where was the ESP32 before I moved it?",
    a: "It was at the center of the desk until 10:43, then moved beside the laptop.",
    frame: "frame_1041.jpg",
  },
  {
    q: "When did the ESP32 reach the right side?",
    a: "At 10:47. It moved from beside the laptop to the right side of the desk.",
    frame: "frame_1047.jpg",
  },
  {
    q: "What changed in the last 5 minutes?",
    a: "The ESP32 moved twice. The phone and laptop did not move.",
    frame: "frame_1043.jpg",
  },
];

export type FeatureCategory = "all" | "cap" | "mem" | "chat" | "priv";

export type Feature = {
  category: Exclude<FeatureCategory, "all">;
  icon: string;
  title: string;
  body: string;
  wide?: boolean;
};

export const FEATURES: Feature[] = [
  {
    category: "cap",
    icon: "🌫",
    title: "Smart change detection",
    body: "Ignores a still room and wakes up only when something moves, so it never burns AI on an empty desk.",
    wide: true,
  },
  { category: "mem", icon: "🖼", title: "Visual evidence", body: "Every memory links to the exact frame." },
  { category: "mem", icon: "🕰", title: "Object history", body: "First seen, last seen and every move between." },
  { category: "chat", icon: "🔎", title: "Semantic search", body: "Ask for “that little dev board” and find your ESP32." },
  { category: "chat", icon: "🤝", title: "Honest answers", body: "Says “likely” when it infers. Never fakes certainty." },
  { category: "priv", icon: "🔐", title: "Private by design", body: "Your cameras, your memories, isolated per user." },
  {
    category: "priv",
    icon: "🧩",
    title: "Open-weight models",
    body: "Qwen3-VL sees, GPT-OSS 20B reasons, Qwen3-Embedding finds. Raw video is never blindly embedded.",
    wide: true,
  },
];

export const FEATURE_TABS: { key: FeatureCategory; label: string }[] = [
  { key: "all", label: "All" },
  { key: "cap", label: "Capture" },
  { key: "mem", label: "Memory" },
  { key: "chat", label: "Chat" },
  { key: "priv", label: "Privacy" },
];

export const STATS = [
  { to: 12480, label: "frames ignored" },
  { to: 14, label: "memories saved" },
  { to: 100, label: "% answers with evidence" },
];

export type ObjectEntry = [string, string];

export const OBJECTS: { label: string; entries: ObjectEntry[] }[] = [
  {
    label: "ESP32",
    entries: [
      ["10:41", "center of desk"],
      ["10:43", "beside laptop"],
      ["10:47", "right side"],
    ],
  },
  {
    label: "Phone",
    entries: [
      ["09:58", "on the desk, screen up"],
      ["10:22", "left of laptop"],
      ["10:50", "gone from view"],
    ],
  },
  {
    label: "Backpack",
    entries: [
      ["08:10", "on the chair"],
      ["12:30", "under the desk"],
      ["19:14", "by the door"],
    ],
  },
];

export type Sighting = [string, string, string, number, [number, number]];

export type FindDataset = { text: string; hits: Sighting[] };

export const FIND_DATASETS: FindDataset[] = [
  {
    text: "black backpack with a red tag",
    hits: [
      ["08:52", "Main entrance", "Cam 1", 94, [60, 55]],
      ["09:03", "Lobby", "Cam 2", 91, [220, 50]],
      ["09:07", "Corridor B", "Cam 3", 88, [160, 114]],
      ["09:15", "Back exit", "Cam 5", 86, [240, 165]],
    ],
  },
  {
    text: "person in a yellow raincoat carrying a blue umbrella",
    hits: [
      ["17:41", "Parking lot", "Cam 4", 90, [80, 166]],
      ["17:46", "Main entrance", "Cam 1", 93, [60, 55]],
      ["17:49", "Lobby", "Cam 2", 89, [220, 50]],
      ["17:58", "Corridor B", "Cam 3", 84, [240, 114]],
    ],
  },
];

export const NAV_LINKS = [
  { href: "#how", label: "How it works" },
  { href: "#rewind", label: "Rewind" },
  { href: "#features", label: "Features" },
];