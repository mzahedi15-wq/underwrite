import { SignUp } from "@clerk/nextjs";
import { UnderwriteLogo } from "@/components/underwrite-logo";

export default function SignUpPage() {
  return (
    <div className="min-h-screen flex">
      {/* Left: photo panel */}
      <div className="hidden lg:flex w-1/2 relative overflow-hidden flex-col">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src="/images/camelback-sunset.png"
          alt="Camelback Mountain sunset"
          className="absolute inset-0 w-full h-full object-cover"
        />
        <div className="absolute inset-0 bg-gradient-to-b from-black/20 via-black/10 to-black/70" />

        <div className="relative z-10 p-10">
          <UnderwriteLogo dark />
        </div>

        <div className="relative z-10 mt-auto p-10">
          <div className="flex flex-col gap-3 mb-6">
            {[
              "Full investment package in 15 minutes",
              "Financial model, pitch deck & renovation scope",
              "Replaces $2,000–5,000 in consultant fees",
              "First analysis completely free",
            ].map((item) => (
              <div key={item} className="flex items-center gap-3">
                <div className="w-5 h-5 rounded-full bg-[#16A34A]/20 flex items-center justify-center shrink-0">
                  <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
                    <path d="M2 5l2 2 4-4" stroke="#16A34A" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </div>
                <p className="text-white/80 text-sm">{item}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Right: Clerk form */}
      <div className="flex-1 flex items-center justify-center bg-[#F7F6F3] p-8">
        <div className="w-full max-w-sm">
          <div className="lg:hidden mb-10">
            <UnderwriteLogo />
          </div>
          <SignUp
            forceRedirectUrl="/dashboard"
            appearance={{
              elements: {
                rootBox: "w-full",
                card: "bg-transparent shadow-none p-0 w-full",
                headerTitle: "font-[Outfit] font-extrabold text-3xl text-[#0D0D0D] tracking-tight",
                headerSubtitle: "text-[#6B6860] text-sm",
                socialButtonsBlockButton:
                  "border border-[#E5E3DE] bg-white text-[#0D0D0D] hover:bg-[#F0EEE9] rounded-lg h-10 text-sm font-medium",
                dividerLine: "bg-[#E5E3DE]",
                dividerText: "text-[#6B6860] text-xs",
                formFieldLabel: "text-sm font-medium text-[#0D0D0D]",
                formFieldInput:
                  "border border-[#E5E3DE] bg-white rounded-lg h-10 px-3 text-sm text-[#0D0D0D] focus:ring-2 focus:ring-[#6357A0] focus:border-transparent",
                formButtonPrimary:
                  "bg-[#0D0D0D] hover:bg-[#1a1a1a] text-white rounded-lg h-10 text-sm font-medium",
                footerActionLink: "text-[#6357A0] hover:underline font-medium",
                formFieldInputShowPasswordButton: "text-[#6B6860]",
                alertText: "text-sm",
                formResendCodeLink: "text-[#6357A0]",
              },
              variables: {
                colorPrimary: "#6357A0",
                colorBackground: "transparent",
                colorInputBackground: "#FFFFFF",
                colorInputText: "#0D0D0D",
                borderRadius: "8px",
                fontFamily: "Inter, system-ui, sans-serif",
              },
            }}
          />
        </div>
      </div>
    </div>
  );
}
