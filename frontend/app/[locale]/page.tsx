"use client";

import { useEffect } from "react";
import { useRouter, useParams } from "next/navigation";

export default function HomePage() {
  const router = useRouter();
  const params = useParams();
  const locale = params?.locale || "en";

  useEffect(() => {
    router.push(`/${locale}/login`);
  }, [router, locale]);

  return null;
}

