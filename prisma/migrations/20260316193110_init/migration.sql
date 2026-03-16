-- CreateEnum
CREATE TYPE "AnalysisStatus" AS ENUM ('PENDING', 'PROCESSING', 'COMPLETE', 'FAILED');

-- CreateEnum
CREATE TYPE "Verdict" AS ENUM ('STRONG_BUY', 'BUY', 'HOLD', 'PASS');

-- CreateEnum
CREATE TYPE "Plan" AS ENUM ('FREE', 'STARTER', 'PRO', 'UNLIMITED');

-- CreateTable
CREATE TABLE "User" (
    "id" TEXT NOT NULL,
    "clerkId" TEXT NOT NULL,
    "email" TEXT NOT NULL,
    "firstName" TEXT,
    "lastName" TEXT,
    "plan" "Plan" NOT NULL DEFAULT 'FREE',
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "User_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Analysis" (
    "id" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "propertyUrl" TEXT NOT NULL,
    "address" TEXT,
    "city" TEXT,
    "state" TEXT,
    "zip" TEXT,
    "listPrice" INTEGER,
    "beds" INTEGER,
    "baths" DOUBLE PRECISION,
    "sqft" INTEGER,
    "propertyType" TEXT,
    "strategy" TEXT,
    "renovationBudget" INTEGER,
    "notes" TEXT,
    "status" "AnalysisStatus" NOT NULL DEFAULT 'PENDING',
    "verdict" "Verdict",
    "projRevenue" INTEGER,
    "cocReturn" DOUBLE PRECISION,
    "capRate" DOUBLE PRECISION,
    "irr" DOUBLE PRECISION,
    "occupancy" DOUBLE PRECISION,
    "noi" INTEGER,
    "adr" INTEGER,
    "reportJson" JSONB,
    "pitchDeckUrl" TEXT,
    "financialModelUrl" TEXT,
    "renovationScopeUrl" TEXT,
    "startedAt" TIMESTAMP(3),
    "completedAt" TIMESTAMP(3),
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "Analysis_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "User_clerkId_key" ON "User"("clerkId");

-- CreateIndex
CREATE UNIQUE INDEX "User_email_key" ON "User"("email");

-- AddForeignKey
ALTER TABLE "Analysis" ADD CONSTRAINT "Analysis_userId_fkey" FOREIGN KEY ("userId") REFERENCES "User"("id") ON DELETE CASCADE ON UPDATE CASCADE;
