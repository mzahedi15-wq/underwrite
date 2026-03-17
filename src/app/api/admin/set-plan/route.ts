import { auth } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";
import { db } from "@/lib/db";

// POST /api/admin/set-plan — sets the current user's plan (owner use only)
export async function POST(req: Request) {
  const { userId: clerkId } = await auth();
  if (!clerkId) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const { plan } = await req.json();
  const validPlans = ["FREE", "STARTER", "PRO", "UNLIMITED"];
  if (!validPlans.includes(plan)) {
    return NextResponse.json({ error: "Invalid plan" }, { status: 400 });
  }

  const user = await db.user.update({
    where: { clerkId },
    data: { plan },
  });

  return NextResponse.json({ id: user.id, plan: user.plan });
}
