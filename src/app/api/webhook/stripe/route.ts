import Stripe from "stripe";
import { headers } from "next/headers";
import { NextResponse } from "next/server";
import { db } from "@/lib/db";

const stripe = new Stripe(process.env.STRIPE_SECRET_KEY ?? "");

const PLAN_MAP: Record<string, "FREE" | "STARTER" | "PRO" | "UNLIMITED"> = {
  [process.env.STRIPE_PRICE_STARTER ?? ""]: "STARTER",
  [process.env.STRIPE_PRICE_PRO ?? ""]: "PRO",
  [process.env.STRIPE_PRICE_UNLIMITED ?? ""]: "UNLIMITED",
};

export async function POST(req: Request) {
  const body = await req.text();
  const headerPayload = await headers();
  const sig = headerPayload.get("stripe-signature");

  if (!sig) return NextResponse.json({ error: "No signature" }, { status: 400 });

  let event: Stripe.Event;
  try {
    event = stripe.webhooks.constructEvent(body, sig, process.env.STRIPE_WEBHOOK_SECRET ?? "");
  } catch {
    return NextResponse.json({ error: "Invalid webhook signature" }, { status: 400 });
  }

  if (event.type === "checkout.session.completed") {
    const session = event.data.object as Stripe.Checkout.Session;
    const clerkId = session.metadata?.clerkId;
    const priceId = session.metadata?.priceId;

    if (!clerkId || !priceId) return NextResponse.json({ received: true });

    const plan = PLAN_MAP[priceId] ?? "FREE";
    await db.user.update({ where: { clerkId }, data: { plan } });
  }

  if (event.type === "customer.subscription.deleted") {
    const sub = event.data.object as Stripe.Subscription;
    const clerkId = (sub.metadata as Record<string, string>)?.clerkId;
    if (clerkId) {
      await db.user.update({ where: { clerkId }, data: { plan: "FREE" } });
    }
  }

  return NextResponse.json({ received: true });
}
