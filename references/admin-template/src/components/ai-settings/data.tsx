import {
  BrainIcon,
  ChipIcon,
  DataBaseIcon,
  HorizontalSlideIcon,
  IntegrationAltIcon,
  SettingsAltIcon,
  SparkIcon,
  TextIcon,
  UserIcon,
} from "../../icons";
import type { ModelItem, NavGroup, Workspace } from "./types";

export const navGroups: NavGroup[] = [
  {
    title: "Account",
    items: [
      { id: "account", label: "Account", icon: UserIcon },
      { id: "general", label: "General", icon: HorizontalSlideIcon },
      { id: "billing", label: "Credit and Billing", icon: SparkIcon },
      {
        id: "personalization",
        label: "Personalization",
        icon: SettingsAltIcon,
      },
    ],
  },
  {
    title: "Features",
    items: [
      { id: "memory", label: "Memory", icon: BrainIcon },
      { id: "file-media", label: "File & Media", icon: TextIcon },
      { id: "model", label: "Model", icon: ChipIcon },
    ],
  },
  {
    title: "System",
    items: [
      { id: "connector", label: "Connector", icon: IntegrationAltIcon },
      { id: "data-control", label: "Data Control", icon: DataBaseIcon },
    ],
  },
];

export const workspaces: Workspace[] = [
  {
    id: 1,
    name: "Musharof Chy",
    plan: "Personal",
    initial: "M",
    colorClass: "bg-brand-400",
  },
  {
    id: 2,
    name: "Leonardo Dicaprio",
    plan: "Business",
    initial: "L",
    colorClass: "bg-warning-400",
  },
];

export const initialModels: ModelItem[] = [
  {
    name: "ChatGPT 5.5",
    badge: "New",
    provider: "OpenAI",
    generation: "Text",
    icon: "GPT",
    image: "/images/model/model-sm/gpt.svg",
    darkImage: "/images/model/model-sm/gpt-white.svg",
    enabled: false,
  },
  {
    name: "ChatGPT 4.5",
    provider: "OpenAI",
    generation: "Text",
    icon: "GPT",
    image: "/images/model/model-sm/gpt.svg",
    darkImage: "/images/model/model-sm/gpt-white.svg",
    enabled: true,
  },
  {
    name: "Claude Sonnet 4.6",
    badge: "New",
    provider: "Anthropic",
    generation: "Text",
    icon: "CL",
    image: "/images/model/model-sm/claude.svg",
    enabled: false,
  },
  {
    name: "Claude Sonnet 4.6",
    provider: "Anthropic",
    generation: "Text",
    icon: "CL",
    image: "/images/model/model-sm/claude.svg",
    enabled: false,
  },
  {
    name: "Gemini 3.1 Pro",
    provider: "Google",
    generation: "Text",
    icon: "GE",
    image: "/images/model/model-sm/gemini.svg",
    enabled: false,
  },
  {
    name: "Gemini 3 Flash",
    provider: "Google",
    generation: "Text",
    icon: "GE",
    image: "/images/model/model-sm/gemini.svg",
    enabled: false,
  },
  {
    name: "Grok 3",
    provider: "xAI",
    generation: "Text",
    icon: "GR",
    image: "/images/model/model-sm/grok.svg",
    darkImage: "/images/model/model-sm/grok-white.svg",
    enabled: false,
  },
  {
    name: "Grok 2.0",
    provider: "xAI",
    generation: "Text",
    icon: "GR",
    image: "/images/model/model-sm/grok.svg",
    darkImage: "/images/model/model-sm/grok-white.svg",
    enabled: false,
  },
];
