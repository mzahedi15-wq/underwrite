import { Webhook } from "svix";
import { headers } from "next/headers";
import { NextResponse } from "next/server";
import { db } from "@/lib/db";

type ClerkUserEvent = {
  type: string;
  data: {
    id: string;
    email_addresses: { email_address: string; id: string }[];
    first_name: string | null;
    last_name: string | null;
  };
};

export async function POST(req: Request) {
  const webhookSecret = process.env.CLERK_WEBHOOK_SECRET;
  if (!webhookSecret) {
    return NextResponse.json({ error: "Webhook secret not configured" }, { status: 500 });
  }

  const headerPayload = await headers();
  const svixId = headerPayload.get("svix-id");
  const svixTimestamp = headerPayload.get("svix-timestamp");
  const svixSignature = headerPayload.get("svix-signature");

  if (!svixId || !svixTimestamp || !svixSignature) {
    return NextResponse.json({ error: "Missing svix headers" }, { status: 400 });
  }

  const payload = await req.text();
  const wh = new Webhook(webhookSecret);

  let event: ClerkUserEvent;
  try {
    event = wh.verify(payload, {
      "svix-id": svixId,
      "svix-timestamp": svixTimestamp,
      "svix-signature": svixSignature,
    }) as ClerkUserEvent;
  } catch {
    return NextResponse.json({ error: "Invalid webhook signature" }, { status: 400 });
  }

  const { type, data } = event;

  if (type === "user.created") {
    await db.user.create({
      data: {
        clerkId: data.id,
        email: data.email_addresses[0]?.email_address ?? "",
        firstName: data.first_name,
        lastName: data.last_name,
      },
    });
  }

  if (type === "user.updated") {
    await db.user.update({
      where: { clerkId: data.id },
      data: {
        email: data.email_addresses[0]?.email_address ?? "",
        firstName: data.first_name,
        lastName: data.last_name,
      },
    });
  }

  if (type === "user.deleted") {
    await db.user.delete({ where: { clerkId: data.id } }).catch(() => {});
  }

  return NextResponse.json({ received: true });
}
