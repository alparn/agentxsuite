"use client";

import { AppLayout } from "../layout-app";
import { CanvasView } from "@/components/canvas/CanvasView";
import "./canvas.css";

export default function CanvasPage() {
  return (
    <AppLayout noPadding>
      <CanvasView />
    </AppLayout>
  );
}

