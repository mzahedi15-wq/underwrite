import { auth, currentUser } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";
import { db } from "@/lib/db";

async function getOrCreateUser(clerkId: string) {
  const existing = await db.user.findUnique({ where: { clerkId } });
  if (existing) return existing;

  const clerkUser = await currentUser();
  return db.user.create({
    data: {
      clerkId,
      email: clerkUser?.emailAddresses[0]?.emailAddress ?? `${clerkId}@unknown`,
      firstName: clerkUser?.firstName ?? null,
      lastName: clerkUser?.lastName ?? null,
    },
  });
}

// GET /api/analyses — list current user's analyses
export async function GET() {
  const { userId: clerkId } = await auth();
  if (!clerkId) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const user = await getOrCreateUser(clerkId);

  const analyses = await db.analysis.findMany({
    where: { userId: user.id },
    orderBy: { createdAt: "desc" },
  });

  return NextResponse.json(analyses);
}

// POST /api/analyses — create a new analysis and dispatch to worker
export async function POST(req: Request) {
  const { userId: clerkId } = await auth();
  if (!clerkId) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const user = await getOrCreateUser(clerkId);

  // Enforce plan limits only when Stripe is configured
  const stripeEnabled = !!process.env.STRIPE_SECRET_KEY;
  if (stripeEnabled) {
    const now = new Date();
    const startOfMonth = new Date(now.getFullYear(), now.getMonth(), 1);
    const usedThisMonth = await db.analysis.count({
      where: { userId: user.id, createdAt: { gte: startOfMonth } },
    });

    const limits: Record<string, number> = {
      FREE: 1,
      STARTER: 3,
      PRO: 10,
      UNLIMITED: Infinity,
    };

    const totalEver = await db.analysis.count({ where: { userId: user.id } });
    if (user.plan === "FREE" && totalEver >= 1) {
      return NextResponse.json(
        { error: "Free plan limit reached. Upgrade to continue." },
        { status: 403 }
      );
    }

    if (user.plan !== "FREE" && usedThisMonth >= limits[user.plan]) {
      return NextResponse.json(
        { error: `${user.plan} plan limit of ${limits[user.plan]} analyses/month reached.` },
        { status: 403 }
      );
    }
  }

  const body = await req.json();
  const { propertyUrl, propertyType, strategy, renovationBudget, notes } = body;

  if (!propertyUrl) {
    return NextResponse.json({ error: "propertyUrl is required" }, { status: 400 });
  }

  // Create analysis record
  const analysis = await db.analysis.create({
    data: {
      userId: user.id,
      propertyUrl,
      propertyType,
      strategy,
      renovationBudget: renovationBudget ? parseInt(renovationBudget) : null,
      notes,
      status: "PENDING",
    },
  });

  // Dispatch to Python worker (must await — Vercel kills the function after response)
  try {
    let workerUrl = process.env.WORKER_URL;
    if (workerUrl) {
      if (!workerUrl.startsWith("http://") && !workerUrl.startsWith("https://")) {
        workerUrl = `https://${workerUrl}`;
      }
      const workerResp = await fetch(`${workerUrl}/analyze`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Worker-Secret": process.env.WORKER_SECRET ?? "",
        },
        body: JSON.stringify({ analysisId: analysis.id, propertyUrl, propertyType, strategy, renovationBudget, notes }),
      });
      if (!workerResp.ok) {
        console.error("[WORKER DISPATCH] Response:", workerResp.status, await workerResp.text());
      }
    } else {
      console.error("[WORKER DISPATCH] WORKER_URL is not set");
    }
  } catch (err) {
    console.error("[WORKER DISPATCH ERROR]", err);
  }

  return NextResponse.json(analysis, { status: 201 });
}
