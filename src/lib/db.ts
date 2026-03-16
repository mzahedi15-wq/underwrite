import { PrismaClient } from "@prisma/client";
import { PrismaPg } from "@prisma/adapter-pg";

declare global {
  // eslint-disable-next-line no-var
  var _prisma: PrismaClient | undefined;
}

function createPrismaClient(): PrismaClient {
  const connectionString = process.env.DATABASE_URL;
  if (!connectionString) {
    // Return a non-connected client during build — fails only if actually queried
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const adapter = new PrismaPg({ connectionString: "" } as any);
    return new PrismaClient({ adapter });
  }
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const adapter = new PrismaPg({ connectionString } as any);
  return new PrismaClient({ adapter });
}

export const db: PrismaClient =
  global._prisma ?? createPrismaClient();

if (process.env.NODE_ENV !== "production") {
  global._prisma = db;
}
