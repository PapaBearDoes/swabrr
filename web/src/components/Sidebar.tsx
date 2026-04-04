"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BarChart3,
  Target,
  Settings,
  History,
  Shield,
  Activity,
  Plug,
} from "lucide-react";

const navItems = [
  { href: "/dashboard", label: "Scores", icon: BarChart3 },
  { href: "/dashboard/candidates", label: "Candidates", icon: Target },
  { href: "/dashboard/protected", label: "Protected", icon: Shield },
  { href: "/dashboard/history", label: "Removal History", icon: History },
  { href: "/dashboard/config", label: "Configuration", icon: Settings },
  { href: "/dashboard/settings", label: "Settings", icon: Plug },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <nav className="sidebar">
      <div className="sidebar-brand">⚓ Swabrr</div>
      {navItems.map((item) => {
        const Icon = item.icon;
        const isActive = pathname === item.href;
        return (
          <Link
            key={item.href}
            href={item.href}
            className={`sidebar-link ${isActive ? "active" : ""}`}
          >
            <Icon size={18} />
            {item.label}
          </Link>
        );
      })}
      <div style={{ flex: 1 }} />
      <div
        style={{
          padding: "12px",
          fontSize: "11px",
          color: "var(--text-disabled)",
        }}
      >
        Swabrr v0.1.0
      </div>
    </nav>
  );
}
