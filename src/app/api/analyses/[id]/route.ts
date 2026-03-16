import { auth } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";
import { db } from "@/lib/db";

// GET /api/analyses/[id]
export async function GET(req: Request, { params }: { params: Promise<{ id: string }> }) {
  const { userId: clerkId } = await auth();
  if (!clerkId) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const { id } = await params;
  const user = await db.user.findUnique({ where: { clerkId } });
  if (!user) return NextResponse.json({ error: "User not found" }, { status: 404 });

  const analysis = await db.analysis.findFirst({
    where: { id, userId: user.id },
  });

  if (!analysis) return NextResponse.json({ error: "Not found" }, { status: 404 });

  return NextResponse.json(analysis);
}

// PATCH /api/analyses/[id] — used by the worker to write results back
export async function PATCH(req: Request, { params }: { params: Promise<{ id: string }> }) {
  // Worker-to-server callback — authenticated by shared secret
  const workerSecret = req.headers.get("x-worker-secret");
  if (workerSecret !== process.env.WORKER_SECRET) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { id } = await params;
  const body = await req.json();

  const analysis = await db.analysis.update({
    where: { id },
    data: {
      ...body,
      completedAt: body.status === "COMPLETE" ? new Date() : undefined,
    },
  });

  return NextResponse.json(analysis);
}
