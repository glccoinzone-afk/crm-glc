import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Bell, Search, ChevronDown, LogOut, User, Building2, Check } from "lucide-react";
import api, { VERTICALS } from "@/lib/glc";
import { useAuth, useVertical } from "@/context/AuthContext";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { fmtDate } from "@/lib/glc";

export default function Topbar() {
  const { user, logout } = useAuth();
  const { vertical, setVertical } = useVertical();
  const nav = useNavigate();
  const [notifs, setNotifs] = useState({ items: [], unread: 0 });
  const [search, setSearch] = useState("");

  const loadNotifs = () => api.get("/notifications").then((r) => setNotifs(r.data)).catch(() => {});
  useEffect(() => { loadNotifs(); const t = setInterval(loadNotifs, 30000); return () => clearInterval(t); }, []);

  const currentVertical = VERTICALS.find((v) => v.key === vertical) || VERTICALS[0];

  const initials = (user?.name || "GZ").split(" ").map((s) => s[0]).join("").slice(0, 2).toUpperCase();

  return (
    <header
      data-testid="app-topbar"
      className="glass sticky top-0 z-20 h-16 border-b border-slate-200/70 flex items-center px-8"
      style={{ paddingLeft: "300px" }}
    >
      {/* Vertical switcher */}
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button
            data-testid="vertical-switcher"
            className="flex items-center gap-2 pl-2 pr-3 py-1.5 rounded-lg border border-slate-200 bg-white hover:bg-slate-50 transition-colors"
          >
            <div className="w-6 h-6 rounded-md bg-[hsl(var(--primary))] text-white grid place-items-center">
              <Building2 size={13} strokeWidth={2} />
            </div>
            <span className="text-[13px] font-medium text-slate-800">{currentVertical.name}</span>
            <ChevronDown size={14} className="text-slate-500" />
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start" className="w-56 rounded-xl">
          <DropdownMenuLabel className="text-[11px] uppercase tracking-wide text-slate-500">Business Vertical</DropdownMenuLabel>
          <DropdownMenuSeparator />
          {VERTICALS.map((v) => (
            <DropdownMenuItem
              key={v.key}
              data-testid={`vertical-option-${v.key.toLowerCase().replace(/\s+/g, "-")}`}
              onClick={() => setVertical(v.key)}
              className="cursor-pointer"
            >
              <div className="w-2 h-2 rounded-full bg-[hsl(var(--primary))] mr-2 opacity-70" />
              <span className="text-[13px]">{v.name}</span>
              {vertical === v.key && <Check size={14} className="ml-auto text-[hsl(var(--primary))]" />}
            </DropdownMenuItem>
          ))}
        </DropdownMenuContent>
      </DropdownMenu>

      {/* Search */}
      <div className="mx-4 flex-1 max-w-md">
        <div className="relative">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            data-testid="global-search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search leads, customers, invoices…"
            className="w-full h-9 pl-9 pr-16 rounded-lg bg-slate-50 border border-transparent focus:border-slate-200 focus:bg-white text-[13px] outline-none transition-colors"
          />
          <kbd className="hidden md:block absolute right-2 top-1/2 -translate-y-1/2 text-[10px] font-mono text-slate-400 border border-slate-200 rounded px-1.5 py-0.5 bg-white">⌘K</kbd>
        </div>
      </div>

      <div className="ml-auto flex items-center gap-2">
        {/* Notifications */}
        <Popover>
          <PopoverTrigger asChild>
            <button
              data-testid="notif-bell"
              className="relative w-9 h-9 rounded-lg border border-slate-200 bg-white hover:bg-slate-50 grid place-items-center"
            >
              <Bell size={16} className="text-slate-600" />
              {notifs.unread > 0 && (
                <span className="absolute -top-1 -right-1 min-w-[16px] h-4 px-1 rounded-full bg-[hsl(var(--accent))] text-white text-[10px] font-semibold grid place-items-center">
                  {notifs.unread}
                </span>
              )}
            </button>
          </PopoverTrigger>
          <PopoverContent align="end" className="w-96 rounded-2xl p-0 overflow-hidden">
            <div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between">
              <div className="text-[13px] font-semibold text-slate-900">Notifications</div>
              <button
                data-testid="notif-mark-read"
                onClick={async () => { await api.put("/notifications/read-all"); loadNotifs(); }}
                className="text-[11px] text-[hsl(var(--primary))] hover:underline"
              >
                Mark all read
              </button>
            </div>
            <div className="max-h-80 overflow-y-auto">
              {(notifs.items || []).length === 0 && (
                <div className="p-6 text-center text-[13px] text-slate-500">You're all caught up.</div>
              )}
              {(notifs.items || []).map((n) => (
                <div key={n.id} className="px-4 py-3 border-b border-slate-50 hover:bg-slate-50/60">
                  <div className="flex items-start gap-2">
                    <div className={`w-2 h-2 mt-1.5 rounded-full ${n.isRead ? "bg-slate-300" : "bg-[hsl(var(--accent))]"}`} />
                    <div className="flex-1">
                      <div className="text-[13px] font-medium text-slate-900">{n.title}</div>
                      <div className="text-[12px] text-slate-500 mt-0.5">{n.message}</div>
                      <div className="text-[10px] text-slate-400 mt-1">{fmtDate(n.createdAt)}</div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </PopoverContent>
        </Popover>

        {/* Profile */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button
              data-testid="profile-menu"
              className="flex items-center gap-2 pl-1 pr-3 py-1 rounded-lg border border-slate-200 bg-white hover:bg-slate-50"
            >
              <Avatar className="w-7 h-7">
                <AvatarImage src={user?.avatar} />
                <AvatarFallback className="bg-[hsl(var(--primary))] text-white text-[11px]">{initials}</AvatarFallback>
              </Avatar>
              <div className="text-left leading-4 hidden sm:block">
                <div className="text-[12.5px] font-medium text-slate-900">{user?.name}</div>
                <div className="text-[10px] text-slate-500">{user?.role}</div>
              </div>
              <ChevronDown size={13} className="text-slate-500" />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-56 rounded-xl">
            <DropdownMenuLabel>
              <div className="text-[13px] font-medium text-slate-900">{user?.name}</div>
              <div className="text-[11px] text-slate-500">{user?.email}</div>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={() => nav("/settings")}>
              <User size={14} className="mr-2" /> Profile & Settings
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem data-testid="logout-btn" onClick={logout} className="text-red-600">
              <LogOut size={14} className="mr-2" /> Sign out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
