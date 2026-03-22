import { NextResponse } from "next/server";
import { db } from "@/lib/db";

// POST /api/worker/callback — worker calls this to update analysis status/results
export async function POST(req: Request) {
  const workerSecret = req.headers.get("x-worker-secret");
  if (workerSecret !== process.env.WORKER_SECRET) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { analysisId, ...data } = await req.json();

  if (!analysisId) {
    return NextResponse.json({ error: "analysisId is required" }, { status: 400 });
  }

  const analysis = await db.analysis.update({
    where: { id: analysisId },
    data: {
      ...data,
      completedAt: data.status === "COMPLETE" ? new Date() : undefined,
    },
  });

  return NextResponse.json({ id: analysis.id, status: analysis.status });
}
