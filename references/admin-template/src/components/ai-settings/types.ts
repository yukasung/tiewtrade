import type { ComponentType, SVGProps } from "react";

export type TabId =
  | "account"
  | "general"
  | "billing"
  | "personalization"
  | "memory"
  | "file-media"
  | "model"
  | "connector"
  | "data-control";

export type IconComponent = ComponentType<SVGProps<SVGSVGElement>>;

export interface NavItem {
  id: TabId;
  label: string;
  icon: IconComponent;
}

export interface NavGroup {
  title: string;
  items: NavItem[];
}

export interface Workspace {
  id: number;
  name: string;
  plan: string;
  initial: string;
  colorClass: string;
}

export interface ModelItem {
  name: string;
  provider: string;
  generation: string;
  icon: string;
  image: string;
  darkImage?: string;
  badge?: string;
  enabled: boolean;
}
