"use client";

import { useUser, useClerk } from "@clerk/nextjs";
import { useRouter } from "next/navigation";
import { LogOut, User, Mail, Calendar } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function SettingsPage() {
  const { user, isLoaded } = useUser();
  const { signOut } = useClerk();
  const router = useRouter();

  async function handleSignOut() {
    await signOut();
    router.push("/sign-in");
  }

  const initials = [user?.firstName?.[0], user?.lastName?.[0]].filter(Boolean).join("").toUpperCase() || "?";
  const fullName = [user?.firstName, user?.lastName].filter(Boolean).join(" ") || "—";
  const email = user?.emailAddresses?.[0]?.emailAddress ?? "—";
  const joinedDate = user?.createdAt
    ? new Date(user.createdAt).toLocaleDateString("en-US", { month: "long", year: "numeric" })
    : "—";

  return (
    <div className="p-8 max-w-xl">
      <div className="mb-8">
        <h1
          style={{ fontFamily: "var(--font-outfit)", fontWeight: 800, letterSpacing: "-0.5px" }}
          className="text-2xl text-[#0D0D0D] mb-1"
        >
          Settings
        </h1>
        <p className="text-sm text-[#6B6860]">Manage your account.</p>
      </div>

      <div className="flex flex-col gap-5">
        {/* Profile card */}
        <div className="bg-white rounded-xl border border-[#E5E3DE] p-6">
          <h2 className="text-xs font-medium text-[#6B6860] uppercase tracking-wider mb-5">Profile</h2>

          {!isLoaded ? (
            <div className="h-20 flex items-center justify-center">
              <div className="w-5 h-5 border-2 border-[#E5E3DE] border-t-[#6357A0] rounded-full animate-spin" />
            </div>
          ) : (
            <div className="flex flex-col gap-5">
              {/* Avatar */}
              <div className="flex items-center gap-4">
                <div className="w-14 h-14 rounded-full bg-[#6357A0] flex items-center justify-center text-white text-lg font-bold shrink-0">
                  {initials}
                </div>
                <div>
                  <p className="font-semibold text-[#0D0D0D]">{fullName}</p>
                  <p className="text-sm text-[#6B6860]">{email}</p>
                </div>
              </div>

              {/* Details */}
              <div className="flex flex-col gap-3 border-t border-[#E5E3DE] pt-5">
                <div className="flex items-center gap-3">
                  <User size={14} className="text-[#6B6860] shrink-0" />
                  <div>
                    <p className="text-xs text-[#6B6860]">Full name</p>
                    <p className="text-sm font-medium text-[#0D0D0D]">{fullName}</p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <Mail size={14} className="text-[#6B6860] shrink-0" />
                  <div>
                    <p className="text-xs text-[#6B6860]">Email</p>
                    <p className="text-sm font-medium text-[#0D0D0D]">{email}</p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <Calendar size={14} className="text-[#6B6860] shrink-0" />
                  <div>
                    <p className="text-xs text-[#6B6860]">Member since</p>
                    <p className="text-sm font-medium text-[#0D0D0D]">{joinedDate}</p>
                  </div>
                </div>
              </div>

              <p className="text-xs text-[#6B6860]">
                To update your name or email, visit your{" "}
                <a
                  href="https://accounts.clerk.dev/user"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-[#6357A0] hover:underline"
                >
                  Clerk account settings
                </a>
                .
              </p>
            </div>
          )}
        </div>

        {/* Sign out */}
        <div className="bg-white rounded-xl border border-[#E5E3DE] p-6">
          <h2 className="text-xs font-medium text-[#6B6860] uppercase tracking-wider mb-4">Session</h2>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-[#0D0D0D]">Sign out</p>
              <p className="text-xs text-[#6B6860]">Sign out of your account on this device.</p>
            </div>
            <Button
              size="sm"
              variant="outline"
              onClick={handleSignOut}
              className="gap-2 text-red-600 border-red-200 hover:bg-red-50"
            >
              <LogOut size={14} />
              Sign out
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
