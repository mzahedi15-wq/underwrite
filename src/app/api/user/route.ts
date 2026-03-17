import { auth, currentUser } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";
import { db } from "@/lib/db";

export async function GET() {
  const { userId: clerkId } = await auth();
  if (!clerkId) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  let user = await db.user.findUnique({ where: { clerkId } });
  if (!user) {
    const clerkUser = await currentUser();
    user = await db.user.create({
      data: {
        clerkId,
        email: clerkUser?.emailAddresses[0]?.emailAddress ?? `${clerkId}@unknown`,
        firstName: clerkUser?.firstName ?? null,
        lastName: clerkUser?.lastName ?? null,
      },
    });
  }

  return NextResponse.json({
    id: user.id,
    email: user.email,
    firstName: user.firstName,
    lastName: user.lastName,
    plan: user.plan,
    createdAt: user.createdAt,
  });
}
